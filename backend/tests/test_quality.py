"""Forward-looking fund quality: comparison with the category index, costs, fund size and fund manager."""
import numpy as np
import pytest

from app.services.catalog import benchmark_funds
from app.services.metrics import relative_metrics
from app.services.ranking import benchmark_series


def monthly(start_nav, returns, start="2019-01"):
    months = np.arange(np.datetime64(start), np.datetime64(start) + len(returns) + 1).astype("datetime64[D]")
    return months, start_nav * np.concatenate([[1.0], np.cumprod(1 + np.array(returns))])


def test_relative_metrics_capture_and_excess():
    rng = np.random.default_rng(7)
    market = rng.normal(0.01, 0.05, 84)
    # A fund that takes 90% of every rise and 60% of every fall beats the market with less pain.
    fund = np.where(market > 0, 0.9 * market, 0.6 * market)
    b_dates, b_navs = monthly(100, market)
    f_dates, f_navs = monthly(10, fund)
    m = relative_metrics(f_dates, f_navs, b_dates, b_navs)
    assert m["up_capture"] == pytest.approx(0.9)
    assert m["down_capture"] == pytest.approx(0.6)
    assert m["excess_return"] > 0
    assert 0.5 < m["beat_rate"] <= 1.0


def test_relative_metrics_need_enough_shared_history():
    b_dates, b_navs = monthly(100, [0.01] * 84)
    f_dates, f_navs = monthly(10, [0.01] * 20, start="2024-01")
    m = relative_metrics(f_dates, f_navs, b_dates, b_navs)
    assert m == {"excess_return": None, "up_capture": None, "down_capture": None, "beat_rate": None}


def test_blended_benchmark_mixes_monthly_returns():
    a = monthly(100, [0.02] * 12)
    b = monthly(50, [0.00] * 12)
    months, navs = benchmark_series([("A", 0.5), ("B", 0.5)], {"A": "1", "B": "2"}, {"1": a, "2": b})
    assert len(months) == 13
    assert navs[-1] / navs[0] == pytest.approx(1.01 ** 12)
    assert benchmark_series([("A", 1.0)], {}, {"1": a}) is None


def test_benchmark_funds_pick_the_oldest_plain_index_fund():
    rows = [
        {"code": "150000", "name": "New Nifty Smallcap 250 Index Fund", "direct_growth": True},
        {"code": "147623", "name": "Old Nifty Smallcap 250 Index Fund", "direct_growth": True},
        {"code": "100000", "name": "Old Nifty Smallcap 250 Index Fund", "direct_growth": False},
        {"code": "140000", "name": "Some Nifty Smallcap 250 Quality 50 Index Fund", "direct_growth": True},
        {"code": "141000", "name": "Some Nifty 100 Low Volatility 30 Index Fund", "direct_growth": True},
        {"code": "142000", "name": "Some Nifty 100 Index Fund", "direct_growth": True},
    ]
    picks = benchmark_funds(rows)
    assert picks["Nifty Smallcap 250"] == "147623"
    assert picks["Nifty 100"] == "142000"
    assert "Nifty Midcap 150" not in picks


# ── Fund facts ───────────────────────────────────────────────────────────────

from datetime import date  # noqa: E402

from app.services import fund_facts as ff  # noqa: E402


def test_size_fit_penalises_oversized_and_tiny_funds():
    assert ff.size_fit(10_000, "small_cap", "equity") == 1.0
    assert ff.size_fit(80_000, "small_cap", "equity") == pytest.approx(15_000 / 80_000, abs=1e-3)
    assert ff.size_fit(80_000, "large_cap", "equity") == 1.0          # no capacity limit for large caps
    assert ff.size_fit(100, "large_cap", "equity") == 0.0             # a fifth of the ₹500 cr floor
    assert 0 < ff.size_fit(300, "large_cap", "equity") < 1
    assert ff.size_fit(None, "small_cap", "equity") is None
    note = ff.size_note({"aum_cr": 80_000, "stocks": 256}, "small_cap", "equity", "small cap")
    assert "₹80,000 crore" in note and "256 stocks" in note
    assert ff._indian(145070.4) == "1,45,070" and ff._indian(999) == "999" and ff._indian(12345678) == "1,23,45,678"
    concentrated = ff.size_note({"aum_cr": 145_070, "stocks": 60}, "flexi_cap", "equity", "flexi cap")
    assert "₹1,45,070 crore" in concentrated and "stocks" not in concentrated
    assert ff.size_note({"aum_cr": 10_000}, "small_cap", "equity", "small cap") is None


def holding_row(name, pct, cls="Equity", rating=None, isin=None, pdate="2026-09-30"):
    return {"portfolio_date": pdate, "company_name": name, "security_name": name, "security_asset_class": cls,
            "percentage_to_aum": pct, "credit_rating": rating, "holding_isin": isin}


def test_summarise_holdings_equity_and_debt():
    rows = [holding_row(f"Co {i}", 9.0, isin=f"INE{i:03d}") for i in range(11)]
    rows += [holding_row("Triparty Repo", 1.0, cls=""), holding_row("Old", 50.0, pdate="2026-08-31")]
    s = ff.summarise_holdings(rows)
    assert s["stocks"] == 11 and s["top10_pct"] == 90.0 and s["cash_pct"] == 1.0
    assert s["portfolio_date"] == "2026-09-30" and s["holdings"][0][0] == "INE000"

    debt = [holding_row("Gilt", 40, cls="", rating="Sovereign"), holding_row("NBFC bond", 30, cls="", rating="CRISIL - AA"),
            holding_row("PSU bond", 25, cls="", rating="CRISIL - AAA"), holding_row("Net Current Assets", 5, cls="")]
    s = ff.summarise_holdings(debt)
    assert s["stocks"] == 0 and s["low_grade_pct"] == 30 and s["cash_pct"] == 5
    assert ff.summarise_holdings([holding_row("Partial", 30)]) is None        # doesn't add up to ~100%


def test_kuvera_facts_maps_isins_and_batches_politely():
    listing = {"Equity": {"Small Cap Fund": {"X_MF": [
        {"c": "AAA-GR", "n": "X Small Cap Growth Direct Plan", "re": "Z"},
        {"c": "AAA-DP", "n": "X Small Cap IDCW Direct Plan", "re": "N"},
        {"c": "BBB-GR", "n": "X Small Cap Growth Regular Plan", "re": "Z"}]}}}
    calls, sleeps = [], []

    def get_json(url):
        calls.append(url)
        if url == ff.KUVERA_LIST_URL:
            return listing
        if "fund_schemes/" in url:
            return [{"code": "AAA-GR", "ISIN": "INF000A", "aum": 809055, "expense_ratio": "0.69",
                     "expense_ratio_date": "2026-09-30", "fund_manager": "A Person; B Person"}]
        return {"AAA-GR": [holding_row("Co", 99.0, isin="INE1"), holding_row("Cash", 1.0, cls="")]}

    facts = ff.kuvera_facts(get_json, {"INF000A": "118778"}, {"118778"}, sleep=sleeps.append)
    f = facts["118778"]
    assert f["ter"] == 0.69 and f["aum_cr"] == 80905.5 and f["managers"] == ["A Person", "B Person"]
    assert f["stocks"] == 1 and f["holdings"] == [["INE1", "Co", 99.0]]
    assert "AAA-GR.json" in calls[1] and len(calls) == 3
    assert sleeps == [ff.KUVERA_DELAY_SECONDS] * 2


def test_reconcile_aum_falls_back_to_amfi_when_scales_disagree():
    amfi = {str(i): 1000.0 for i in range(60)}
    good = {str(i): {"aum_cr": 1100.0} for i in range(60)}
    assert ff.reconcile_aum(good, amfi) == "kuvera" and good["0"]["aum_cr"] == 1100.0
    wrong_unit = {str(i): {"aum_cr": 11.0} for i in range(60)}
    assert ff.reconcile_aum(wrong_unit, amfi) == "amfi" and wrong_unit["0"]["aum_cr"] == 1000.0


def test_amfi_scheme_aum_adds_up_every_plan_of_a_scheme():
    responses = {
        ff.AMFI_AAUM_URL: {"data": [{"id": 1}]},
        f"{ff.AMFI_AAUM_URL}&fyId=1": {"data": {"periods": [{"id": 1}]}},
        f"{ff.AMFI_AAUM_URL}&fyId=1&periodId=1": {"data": [{"schemes": [
            {"AMFI_Code": 1, "AverageAumForTheMonth": {"a": 100.0, "b": 0}},
            {"AMFI_Code": 2, "AverageAumForTheMonth": {"a": 300.0, "b": 0}}]}]},
    }
    scheme_map = {"1": {"twin": "1"}, "2": {"twin": "1"}}
    assert ff.amfi_scheme_aum(responses.__getitem__, scheme_map) == {"1": 4.0}     # ₹ lakh -> crore


def test_manager_changes_are_dated_from_when_we_saw_them():
    seen = {}
    ff.update_managers(seen, {"1": {"managers": ["Old"]}}, "2026-10-25")
    ff.update_managers(seen, {"1": {"managers": ["Old", "New"]}}, "2027-03-01")
    info = ff.manager_info(seen["1"], ["Old", "New"], "2026-10-25", date(2027, 6, 1))
    assert info == {"manager_since": "2027-03-01", "manager_changed": True}
    info = ff.manager_info(seen["1"], ["Old"], "2026-10-25", date(2027, 6, 1))
    assert info == {"manager_since": None, "manager_changed": False}         # there since tracking began
    assert ff.manager_info({}, [], "2026-10-25", date(2027, 6, 1))["manager_changed"] is None
