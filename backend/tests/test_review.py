"""Portfolio review: ratings, returns, tax lots and portfolio checks. No network: NAV histories are faked."""
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.services import nav as navs
from app.services.rankings_store import scheme_map, store
from app.services.review import Reviewer, open_lots, xirr
from main import app

TODAY = date(2026, 10, 23)
DATA = store.get()
SCHEMES = scheme_map.schemes()


def fake_history(nav_today=100.0, yearly=0.12):
    """Two years of daily NAVs ending today at nav_today."""
    days = 730
    return [((TODAY - timedelta(days=days - i)).isoformat(), nav_today / (1 + yearly) ** ((days - i) / 365))
            for i in range(days + 1)]


def histories(overrides=None):
    overrides = overrides or {}
    return lambda codes: {c: overrides.get(c, fake_history()) for c in codes}


def ranked(bucket, where):
    funds = DATA["buckets"][bucket]["funds"]
    return funds[0] if where == "top" else funds[-1]


def regular_twin_of(direct_code):
    return next(code for code, s in SCHEMES.items() if s["twin"] == direct_code and not s["direct"] and s["growth"])


def holding(code, units=100.0, txns=None, cost=None, open_units=0.0, source="cas"):
    return {"id": f"h{code}", "source": source, "code": code, "isin": None, "name": SCHEMES[code]["name"],
            "amc": SCHEMES[code]["amc"], "units": units, "cost": cost, "cas_nav": 90.0,
            "cas_nav_date": "2026-09-30", "open_units": open_units, "txns": txns or []}


def sip(start: date, months: int, amount=1000.0, nav=80.0):
    return [[(start + timedelta(days=30 * i)).isoformat(), "PURCHASE_SIP", amount, amount / nav] for i in range(months)]


# ── Maths ────────────────────────────────────────────────────────────────────

def test_xirr_matches_a_simple_annual_return():
    assert xirr([(date(2024, 1, 1), -1000), (date(2025, 1, 1), 1100)]) == pytest.approx(0.10, abs=1e-3)
    assert xirr([(date(2024, 1, 1), -1000)]) is None


def test_fifo_lots_sell_oldest_first():
    txns = [["2023-01-01", "PURCHASE", 1000, 10], ["2024-01-01", "PURCHASE", 2000, 10],
            ["2024-06-01", "REDEMPTION", -1500, -15]]
    lots = open_lots(txns)
    assert len(lots) == 1 and lots[0][0] == date(2024, 1, 1)
    assert lots[0][1] == pytest.approx(5) and lots[0][2] == pytest.approx(1000)


# ── Ratings ──────────────────────────────────────────────────────────────────

def test_top_and_bottom_funds_are_rated_and_bottom_gets_alternatives():
    top, bottom = ranked("flexi_cap", "top"), ranked("flexi_cap", "bottom")
    r = Reviewer(fetch_histories=histories()).review([holding(top["code"]), holding(bottom["code"])], today=TODAY)
    rows = {h["code"]: h for h in r["holdings"]}
    assert rows[top["code"]]["rating"]["status"] == "in_form"
    assert rows[top["code"]]["action"]["type"] == "continue"
    worst = rows[bottom["code"]]
    assert worst["rating"]["status"] == "out_of_form" and worst["action"]["type"] == "switch"
    assert worst["alternatives"] and all(a["amc"] != bottom["amc"] for a in worst["alternatives"])
    assert any(i["key"] == "out_of_form" for i in r["insights"])


def test_regular_plan_is_rated_through_its_direct_twin_and_flagged_for_cost():
    direct = ranked("large_cap", "top")["code"]
    regular = regular_twin_of(direct)
    fake = histories({direct: fake_history(100, 0.13), regular: fake_history(90, 0.12)})
    r = Reviewer(fetch_histories=fake).review([holding(regular)], today=TODAY)
    row = r["holdings"][0]
    assert row["plan"] == "Regular" and row["rating"]["status"] == "in_form"
    assert row["cost_gap"] == pytest.approx(0.01, abs=0.002)
    regular_insight = next(i for i in r["insights"] if i["key"] == "regular_plans")
    assert "Direct" in regular_insight["text"]


def test_value_gain_xirr_and_tax_lots_from_transactions():
    code = ranked("elss", "top")["code"]
    txns = sip(TODAY - timedelta(days=24 * 30), 24)          # monthly SIP for two years
    units = sum(t[3] for t in txns)
    r = Reviewer(fetch_histories=histories()).review([holding(code, units=units, txns=txns)], today=TODAY)
    row, s = r["holdings"][0], r["summary"]
    assert row["value"] == pytest.approx(units * 100, rel=1e-6)
    assert row["invested"] == pytest.approx(24_000)
    assert s["xirr"] is not None and s["xirr"] > 0
    assert row["lt_gain"] > 0 and row["st_gain"] > 0
    # Every ELSS instalment from the last three years is still locked in.
    assert row["elss_locked"] == pytest.approx(row["value"], rel=1e-6)
    assert r["tax"]["complete"]


def test_statement_without_full_history_skips_xirr_and_tax():
    code = ranked("mid_cap", "top")["code"]
    r = Reviewer(fetch_histories=histories()).review(
        [holding(code, txns=sip(TODAY - timedelta(days=90), 3), cost=5000, open_units=40)], today=TODAY)
    assert r["holdings"][0]["xirr"] is None and r["holdings"][0]["invested"] == 5000
    assert not r["tax"]["complete"]
    assert any(i["key"] == "partial" for i in r["insights"])


# ── Portfolio checks ─────────────────────────────────────────────────────────

def test_duplicates_too_many_funds_drift_and_unrated():
    funds = DATA["buckets"]["flexi_cap"]["funds"][:3] + DATA["buckets"]["small_cap"]["funds"][:2] \
        + DATA["buckets"]["mid_cap"]["funds"][:2]
    sectoral = next(c for c, s in SCHEMES.items() if "sectoral" in s["category"].lower() and s["direct"] and s["growth"])
    hs = [holding(f["code"]) for f in funds] + [holding(sectoral)]
    target = {"name": "My plan", "asset_mix": {"equity": 50, "hybrid": 20, "debt": 30}}
    r = Reviewer(fetch_histories=histories()).review(hs, target=target, today=TODAY)
    keys = {i["key"] for i in r["insights"]}
    assert "duplicate:Flexi Cap" in keys and "too_many" in keys and "drift" in keys and "unrated" in keys
    assert r["allocation"]["equity"] == 100.0


def test_healthy_portfolio_says_so():
    hs = [holding(ranked("index_large", "top")["code"]), holding(ranked("corporate_bond", "top")["code"])]
    r = Reviewer(fetch_histories=histories()).review(hs, today=TODAY)
    assert r["insights"][0]["key"] == "healthy"
    assert r["health"]["good_pct"] == 100.0


def test_unknown_schemes_are_listed_not_dropped():
    r = Reviewer(fetch_histories=histories()).review(
        [{"id": "x", "source": "cas", "code": None, "name": "Mystery Fund", "units": 5, "txns": []}], today=TODAY)
    assert r["unrecognised"][0]["name"] == "Mystery Fund"


# ── API ──────────────────────────────────────────────────────────────────────

def logged_in_client(monkeypatch, email):
    from app.routes import auth as auth_routes
    from app.services import auth
    codes = {}
    monkeypatch.setattr(auth_routes, "send_otp", lambda to, code, purpose, minutes: codes.update({to: code}))
    auth._ip_hits.clear()
    client = TestClient(app)
    client.post("/api/auth/signup/start", json={"full_name": "Review User", "email": email, "consent": True})
    client.post("/api/auth/verify", json={"email": email, "code": codes[email], "purpose": "signup", "consent": True})
    return client


def test_review_api_manual_holdings_and_bad_uploads(monkeypatch):
    monkeypatch.setattr(navs, "histories", histories())
    assert TestClient(app).get("/api/review").status_code == 401
    client = logged_in_client(monkeypatch, "review@example.com")
    assert client.get("/api/review").json()["empty"]

    hits = client.get("/api/funds/search", params={"q": "parag parikh flexi"}).json()
    assert hits and hits[0]["plan"] == "Direct" and hits[0]["option"] == "Growth"

    r = client.post("/api/review/holdings", json={"code": hits[0]["code"], "value": 50_000, "invested": 40_000,
                                                          "consent": True})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["summary"]["value"] == pytest.approx(50_000, rel=1e-6)
    assert body["holdings"][0]["source"] == "manual"

    hid = body["holdings"][0]["ids"][0]
    assert client.delete(f"/api/review/holdings/{hid}").json()["empty"]

    r = client.post("/api/review/upload", files={"file": ("cas.pdf", b"not a pdf", "application/pdf")},
                    data={"password": "x", "consent": "true"})
    assert r.status_code == 422 and "PDF" in r.json()["detail"]
