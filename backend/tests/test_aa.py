"""Account Aggregator import: parsing Setu's MUTUAL_FUNDS data and the consent -> session -> review flow.
No network: Setu is faked."""
import pytest
from fastapi.testclient import TestClient

from app.routes import aa as aa_routes
from app.services import aa
from app.services import nav as navs
from app.services.rankings_store import scheme_map
from main import app
from tests.test_review import histories, logged_in_client

PPFAS = "122639"
ISIN = scheme_map.schemes()[PPFAS]["isins"][0]


def rebit_account(units="120.5", txns=True):
    """MUTUAL_FUNDS data as Setu's spec describes it (ReBIT, JSON format)."""
    account = {"type": "mutual_funds", "maskedFolioNo": "XXXX1234", "summary": {
        "currentValue": "10000", "costValue": "8000",
        "investment": {"holdings": {"holding": {
            "amc": "PPFAS Mutual Fund", "registrar": "CAMS", "isin": ISIN, "amfiCode": PPFAS,
            "closingUnits": units, "lienUnits": "0", "lockinUnits": "0", "nav": "85.12", "navDate": "2026-10-23"}}}}}
    if txns:
        account["transactions"] = {"transaction": [
            {"isin": ISIN, "amfiCode": PPFAS, "type": "BUY", "amount": "5000", "units": "100.5",
             "transactionDate": "2024-01-10T00:00:00.000Z"},
            {"isin": ISIN, "amfiCode": PPFAS, "type": "BUY", "amount": "2000", "units": "30",
             "transactionDate": "2025-02-10"},
            {"isin": ISIN, "amfiCode": PPFAS, "type": "SELL", "amount": "900", "units": "10",
             "transactionDate": "2025-06-01"},
            {"isin": "INF000OTHER1", "type": "BUY", "amount": "1", "units": "1", "transactionDate": "2025-06-01"},
        ]}
    return {"account": account}


def session(*accounts, status="COMPLETED", fi_status="READY"):
    return {"id": "sess-1", "status": status, "fips": [{"fipID": "CAMS-FIP", "accounts": [
        {"linkRefNumber": f"ref{i}", "maskedAccNumber": "XXXX", "FIstatus": fi_status, "data": a}
        for i, a in enumerate(accounts)]}]}


# ── Parsing ──────────────────────────────────────────────────────────────────

def test_parses_rebit_holdings_and_matches_transactions_to_the_scheme():
    holdings, warnings = aa.parse_session(session(rebit_account()))
    assert warnings == []
    [h] = holdings
    assert (h["source"], h["code"], h["units"], h["cas_nav"]) == ("aa", PPFAS, 120.5, 85.12)
    assert [t[1] for t in h["txns"]] == ["PURCHASE", "PURCHASE", "REDEMPTION"]
    assert h["txns"][2][2:] == [-900.0, -10.0]          # money and units out are negative, as in a CAS
    assert h["open_units"] == 0.0                        # the transactions explain every unit held


def test_units_older_than_the_transactions_make_the_holding_partial():
    [h] = aa.parse_session(session(rebit_account(units="150")))[0]
    assert h["open_units"] == pytest.approx(29.5)
    [h] = aa.parse_session(session(rebit_account(txns=False)))[0]
    assert h["txns"] == [] and h["open_units"] == 0.0


def test_parses_setus_sandbox_mock_shape():
    # Setu's published mock has no "account" wrapper, extra keys and an unknown scheme.
    mock = {"type": "mutual_funds", "masked_account_number": "XXXX", "summary": {
        "currentValue": "156000", "investmentValue": "130000",
        "investment": {"holdings": {"holding": [
            {"FatcaStatus": "YES", "amc": "Apna Mutual Funds", "amfiCode": "APFMST123", "closingUnits": "26",
             "isin": "INUS-000402625-0", "nav": "512", "navDate": "2021-06-22", "registrar": "CAMS",
             "schemeCode": "APMFST", "units": "21"},
            {"amc": "PPFAS", "isin": ISIN, "closingUnits": "0", "nav": "80", "navDate": "2021-06-22"}]}}}}
    holdings, _ = aa.parse_session(session(mock))
    assert len(holdings) == 1                            # zero units are skipped
    assert holdings[0]["code"] is None and holdings[0]["name"] == "APMFST"


def test_accounts_that_were_not_shared_become_warnings():
    holdings, warnings = aa.parse_session(session(rebit_account(), fi_status="DENIED"))
    assert holdings == [] and "denied" in warnings[0]


def test_session_is_settled_when_every_account_has_answered():
    assert aa.session_settled({"status": "COMPLETED", "fips": []})
    assert aa.session_settled(session(rebit_account(), status="PARTIAL", fi_status="TIMEOUT"))
    assert not aa.session_settled(session(rebit_account(), status="PARTIAL", fi_status="PENDING"))
    assert not aa.session_settled({"status": "PENDING", "fips": []})


# ── Flow ─────────────────────────────────────────────────────────────────────

class FakeSetu:
    def __init__(self):
        self.consent_status, self.session_status, self.revoked, self.sent = "PENDING", "PENDING", [], {}

    def create_consent(self, mobile, redirect_url, rng):
        self.sent = {"mobile": mobile, "redirect": redirect_url, "range": rng}
        return {"id": f"consent-{mobile}", "url": "https://fiu-sandbox.setu.co/v2/consents/webview/x", "status": "PENDING"}

    def consent(self, consent_id):
        return {"id": consent_id, "status": self.consent_status}

    def create_session(self, consent_id, rng):
        assert rng == self.sent["range"]                 # the session asks for the range the consent covers
        return {"id": "sess-1", "status": "PENDING"}

    def session(self, session_id):
        ready = self.session_status == "COMPLETED"
        return session(rebit_account(), status=self.session_status, fi_status="READY" if ready else "PENDING")

    def revoke(self, consent_id):
        self.revoked.append(consent_id)


@pytest.fixture
def setu(monkeypatch):
    fake = FakeSetu()
    monkeypatch.setattr(aa_routes, "client", fake)
    for k in ("SETU_AA_CLIENT_ID", "SETU_AA_CLIENT_SECRET", "SETU_AA_PRODUCT_INSTANCE_ID"):
        monkeypatch.setenv(k, "test")
    monkeypatch.setattr(navs, "histories", histories())
    monkeypatch.setattr(navs, "latest_nav", lambda code: (100.0, "2026-10-23"))
    return fake


def test_switched_off_without_setu_keys(monkeypatch):
    for k in ("SETU_AA_CLIENT_ID", "SETU_AA_CLIENT_SECRET", "SETU_AA_PRODUCT_INSTANCE_ID"):
        monkeypatch.delenv(k, raising=False)
    client = TestClient(app)
    assert client.get("/api/health").json()["aa_enabled"] is False
    assert client.post("/api/aa/consent", json={"mobile": "9876543210", "consent": True}).status_code == 404


def test_guest_flow_consent_then_data_then_review(setu):
    client = TestClient(app)
    assert client.get("/api/health").json()["aa_enabled"] is True
    assert client.post("/api/aa/consent", json={"mobile": "9876543210"}).status_code == 422      # no consent
    assert client.post("/api/aa/consent", json={"mobile": "12345", "consent": True}).status_code == 422

    start = client.post("/api/aa/consent", json={"mobile": "9876543210", "consent": True}).json()
    assert start["url"].startswith("https://") and start["key"]
    assert setu.sent["redirect"].endswith("/review?aa=1")
    ask = {"id": start["id"], "key": start["key"]}

    assert client.post("/api/aa/status", json={"id": start["id"], "key": "wrong"}).status_code == 404
    assert client.post("/api/aa/status", json=ask).json() == {"status": "waiting", "stage": "consent"}
    setu.consent_status = "ACTIVE"
    assert client.post("/api/aa/status", json=ask).json() == {"status": "waiting", "stage": "data"}
    setu.session_status = "COMPLETED"
    done = client.post("/api/aa/status", json=ask).json()
    assert done["status"] == "done" and done["statement"]["type"] == "AA"
    assert done["holdings"][0]["source"] == "aa" and done["review"]["holdings"][0]["code"] == PPFAS
    assert setu.revoked == [start["id"]]
    # The browser keeps the holdings; asking again doesn't hand them out a second time.
    assert client.post("/api/aa/status", json=ask).json() == {"status": "done"}
    # The guest review endpoint accepts them back, as it does CAS holdings.
    again = client.post("/api/review/guest", json={"consent": True, "holdings": done["holdings"]})
    assert again.status_code == 200, again.text


def test_declined_consent_fails_cleanly(setu):
    client = TestClient(app)
    start = client.post("/api/aa/consent", json={"mobile": "9876543211", "consent": True}).json()
    setu.consent_status = "REJECTED"
    r = client.post("/api/aa/status", json={"id": start["id"], "key": start["key"]}).json()
    assert r["status"] == "failed" and "declined" in r["message"]


def test_account_flow_saves_the_portfolio_and_keeps_funds_added_by_hand(setu, monkeypatch):
    client = logged_in_client(monkeypatch, "aa@example.com")
    monkeypatch.setattr(aa_routes, "client", setu)
    client.post("/api/review/holdings", json={"code": "118955", "value": 10_000, "consent": True})
    start = client.post("/api/aa/consent", json={"mobile": "9876543212", "consent": True}).json()
    assert start["key"] is None                          # an account's own session identifies it
    setu.consent_status, setu.session_status = "ACTIVE", "COMPLETED"
    done = client.post("/api/aa/status", json={"id": start["id"]}).json()
    assert done["status"] == "done"
    assert {h["code"] for h in done["review"]["holdings"]} == {PPFAS, "118955"}
    assert done["review"]["statement"]["type"] == "AA"
    held = client.get("/api/review/holdings").json()
    assert {h["code"] for h in held} == {PPFAS, "118955"}
    # Someone else (no session, no key) can't poll it.
    assert TestClient(app).post("/api/aa/status", json={"id": start["id"]}).status_code == 404
