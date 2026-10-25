"""Engine tests. They run against the bundled rankings file, so no network is needed."""
import itertools
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.user import InvestmentGoal, LifeStage, RiskTolerance, UserProfile  # noqa: E402
from app.services import allocation as alloc  # noqa: E402
from app.services.amfi import parse_navall  # noqa: E402
from app.services.catalog import BUCKETS, bucket_for  # noqa: E402
from app.services.metrics import cagr, max_drawdown, percentile_ranks, to_series  # noqa: E402
from app.services.recommendation_engine import RecommendationEngine, required_sip, sip_future_value  # noqa: E402

engine = RecommendationEngine()


# ── Metrics ──────────────────────────────────────────────────────────────────

def _daily_series(years, annual):
    days = int(years * 365.25)
    dates = np.arange(np.datetime64("2015-01-01"), np.datetime64("2015-01-01") + days + 1)
    navs = 10 * (1 + annual) ** (np.arange(len(dates)) / 365.25)
    # Drop weekends so row count != calendar days, like real NAV data.
    weekday = (dates.astype("datetime64[D]").view("int64") - 4) % 7
    keep = weekday < 5
    return dates[keep], navs[keep]


def test_cagr_uses_calendar_dates_not_rows():
    dates, navs = _daily_series(6, 0.12)
    assert cagr(dates, navs, 1) == pytest.approx(0.12, abs=0.002)
    assert cagr(dates, navs, 5) == pytest.approx(0.12, abs=0.002)
    assert cagr(dates, navs, 10) is None


def test_max_drawdown():
    assert max_drawdown(np.array([100, 120, 60, 90, 130.0])) == pytest.approx(-0.5)


def test_percentile_ranks_handles_missing_and_direction():
    assert percentile_ranks([1, 2, 3], True) == [0.0, 0.5, 1.0]
    assert percentile_ranks([1, 2, 3], False) == [1.0, 0.5, 0.0]
    assert percentile_ranks([None, 5, 7], True)[0] == 0.35


def test_to_series_sorts_and_drops_bad_rows():
    d, n = to_series([("2024-01-03", 11), ("2024-01-01", 10), ("2024-01-02", "x"), ("2024-01-04", 0)])
    assert list(n) == [10, 11]


# ── Universe ─────────────────────────────────────────────────────────────────

def test_bucket_mapping_rejects_wrong_plans():
    assert bucket_for("Equity Scheme - Mid Cap Fund", "HDFC Mid Cap Fund").key == "mid_cap"
    assert bucket_for("Equity Scheme - Large & Mid Cap Fund", "X Large & Mid Cap Fund").key == "large_mid"
    assert bucket_for("Other Scheme - Index Funds", "UTI Nifty 50 Index Fund").key == "index_large"
    assert bucket_for("Other Scheme - Index Funds", "UTI Nifty Next 50 Index Fund") is None
    assert bucket_for("Index Funds - Equity Funds", "360 ONE ELSS Tax Saver Nifty 50 Index Fund") is None
    assert bucket_for("Income/Debt Oriented Schemes - Ultra Short to Short Term Fund", "X Fund") is None
    assert bucket_for("Debt Scheme - Liquid Fund", "X Liquid Fund - Segregated Portfolio 1") is None


def test_parse_navall_keeps_only_fresh_direct_growth():
    text = """Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;Plan;Option;Net Asset Value;Date

Open Ended Schemes(Equity Scheme - Mid Cap Fund)

Good AMC Mutual Fund

1;INF1;-;Good Mid Cap Fund;Direct Plan;Growth;50.1;23-Oct-2026
2;INF2;-;Good Mid Cap Fund;Regular Plan;Growth;45.0;23-Oct-2026
3;INF3;-;Good Mid Cap Fund;Direct Plan;IDCW;20.0;23-Oct-2026
4;INF4;-;Old Mid Cap Fund;Direct Plan;Growth;12.0;01-Jan-2017

Close Ended Schemes(Income)

5;INF5;-;Some FMP;Direct Plan;Growth;10.0;23-Oct-2026
"""
    rows = parse_navall(text.splitlines())
    assert [r.code for r in rows] == ["1"]
    assert rows[0].amc == "Good AMC Mutual Fund"


# ── SIP maths ────────────────────────────────────────────────────────────────

def test_sip_formulas_are_inverse():
    fv = sip_future_value(10_000, 10, 0.12)
    assert required_sip(fv, 10, 0.12) == pytest.approx(10_000)
    # Annuity-due with monthly compounding of a 12% effective annual rate.
    assert fv == pytest.approx(2_240_359, rel=0.001)


# ── Allocation rules ─────────────────────────────────────────────────────────

def test_emergency_and_short_horizon_hold_no_equity():
    for goal, horizon in [(InvestmentGoal.EMERGENCY_CORPUS, 15), (InvestmentGoal.WEALTH_CREATION, 2)]:
        mix = alloc.sleeve_mix(90, horizon, LifeStage.JUST_STARTED, goal)
        assert mix["equity"] == 0 and mix["hybrid"] == 0


def test_retired_equity_is_capped():
    mix = alloc.sleeve_mix(100, 20, LifeStage.RETIRED, InvestmentGoal.WEALTH_CREATION)
    assert mix["equity"] <= 0.40


def test_equity_rises_with_risk_and_horizon():
    low = alloc.sleeve_mix(20, 10, LifeStage.PEAK_EARNING, InvestmentGoal.WEALTH_CREATION)["equity"]
    high = alloc.sleeve_mix(80, 10, LifeStage.PEAK_EARNING, InvestmentGoal.WEALTH_CREATION)["equity"]
    short = alloc.sleeve_mix(80, 4, LifeStage.PEAK_EARNING, InvestmentGoal.WEALTH_CREATION)["equity"]
    assert low < high and short < high


# ── End-to-end invariants across every combination ───────────────────────────

BUDGETS = [500, 1_500, 4_000, 12_000, 30_000, 75_000]
HORIZONS = [1, 2, 3, 4, 6, 10, 20]


@pytest.mark.parametrize("life_stage,goal", list(itertools.product(LifeStage, InvestmentGoal)))
def test_portfolio_invariants(life_stage, goal):
    for risk, budget, horizon in itertools.product(RiskTolerance, BUDGETS, HORIZONS):
        p = engine.get_portfolio(UserProfile(
            life_stage=life_stage, goal=goal, risk_tolerance=risk,
            monthly_budget=budget, horizon_years=horizon, tax_regime="old"))
        ctx = (life_stage.value, goal.value, risk.value, budget, horizon)

        assert p.funds, ctx
        assert sum(f.allocation_amount for f in p.funds) == pytest.approx(budget), ctx
        assert sum(f.allocation_percentage for f in p.funds) == pytest.approx(100, abs=0.2), ctx
        assert len({f.scheme_code for f in p.funds}) == len(p.funds), ctx
        assert len(p.funds) <= alloc.max_funds_for(budget), ctx
        assert all(f.allocation_amount >= alloc.MIN_SIP for f in p.funds), ctx
        # The category label must match the fund actually picked (the original bug).
        for f in p.funds:
            assert bucket_for(f.sebi_category, f.scheme_name) is not None, (ctx, f.scheme_name)

        if goal == InvestmentGoal.EMERGENCY_CORPUS or horizon < 3:
            assert p.asset_mix["equity"] == 0 and p.asset_mix["hybrid"] == 0, ctx
        if life_stage == LifeStage.RETIRED:
            assert p.asset_mix["equity"] <= 40.5, ctx
        if horizon < 5:
            assert p.asset_mix["equity"] <= 35.5, ctx
        exp = p.projections
        assert exp["pessimistic"].corpus <= exp["expected"].corpus <= exp["optimistic"].corpus, ctx


def test_target_only_sizes_the_sip():
    p = engine.get_portfolio(UserProfile(life_stage="new_parent", goal="child_education",
                                         risk_tolerance="moderate", target_amount=5_000_000, target_years=15))
    assert p.monthly_investment == p.monthly_sip_required
    assert p.goal_status == "on_track"


def test_budget_is_never_overridden_by_target():
    p = engine.get_portfolio(UserProfile(life_stage="peak_earning", goal="retirement", risk_tolerance="high",
                                         monthly_budget=20_000, target_amount=50_000_000, target_years=10))
    assert p.monthly_investment == 20_000
    assert p.goal_status == "shortfall" and p.shortfall_monthly > 0


def test_new_tax_regime_skips_elss():
    p = engine.get_portfolio(UserProfile(life_stage="peak_earning", goal="tax_saving", risk_tolerance="moderate",
                                         monthly_budget=20_000, horizon_years=7, tax_regime="new"))
    assert all(f.bucket != "elss" for f in p.funds)


def test_risk_score_changes_the_plan():
    base = dict(life_stage="peak_earning", goal="wealth_creation", risk_tolerance="moderate",
                monthly_budget=30_000, horizon_years=12)
    low = engine.get_portfolio(UserProfile(**base, risk_score=30))
    high = engine.get_portfolio(UserProfile(**base, risk_score=85))
    assert low.asset_mix["equity"] < high.asset_mix["equity"]
    assert {f.scheme_code for f in low.funds} != {f.scheme_code for f in high.funds}


def test_rejects_missing_amount():
    with pytest.raises(ValueError):
        engine.get_portfolio(UserProfile(life_stage="retired", goal="retirement", risk_tolerance="low"))


def test_every_bucket_has_ranked_funds():
    data = engine.rankings.get()
    for key in BUCKETS:
        assert len(data["buckets"][key]["funds"]) >= 5, key


# ── Suitability inputs ───────────────────────────────────────────────────────

BASE = dict(life_stage="peak_earning", goal="wealth_creation", risk_tolerance="moderate",
            monthly_budget=20_000, horizon_years=12)


def test_lower_of_capacity_and_willingness_is_used():
    p = engine.get_portfolio(UserProfile(**BASE, capacity_score=30, willingness_score=85))
    assert p.risk_profile.score == 30 and p.risk_profile.limited_by == "capacity"
    assert any("finances can absorb" in w for w in p.warnings)
    p = engine.get_portfolio(UserProfile(**BASE, capacity_score=85, willingness_score=30))
    assert p.risk_profile.score == 30 and p.risk_profile.limited_by == "willingness"


def test_fixed_deadline_lowers_equity():
    flexible = alloc.sleeve_mix(60, 6, LifeStage.PEAK_EARNING, InvestmentGoal.BUY_HOME, False)["equity"]
    fixed = alloc.sleeve_mix(60, 6, LifeStage.PEAK_EARNING, InvestmentGoal.BUY_HOME, True)["equity"]
    assert fixed < flexible


def test_target_in_todays_money_is_inflated():
    common = dict(life_stage="new_parent", goal="child_education", risk_tolerance="moderate",
                  target_amount=2_000_000, horizon_years=15)
    nominal = engine.get_portfolio(UserProfile(**common))
    today = engine.get_portfolio(UserProfile(**common, target_in_today_value=True))
    assert today.target_amount_today == 2_000_000
    assert today.target_amount == pytest.approx(2_000_000 * 1.06 ** 15, rel=0.001)
    assert today.monthly_investment > nominal.monthly_investment


def test_suitability_warnings():
    p = engine.get_portfolio(UserProfile(**BASE, monthly_income=50_000, monthly_expenses=30_000, monthly_emi=25_000,
                                         emergency_months=1, dependents=2,
                                         has_health_insurance=False, has_term_insurance=False))
    text = " ".join(p.warnings)
    for phrase in ("after expenses and EMIs", "EMIs take", "emergency fund", "health insurance", "term insurance"):
        assert phrase in text, phrase
    clean = engine.get_portfolio(UserProfile(**BASE, monthly_income=200_000, monthly_expenses=50_000, monthly_emi=0,
                                             emergency_months=6, dependents=2,
                                             has_health_insurance=True, has_term_insurance=True))
    assert not any(w for w in clean.warnings if "insurance" in w or "EMI" in w or "emergency" in w)


def test_mix_reasons_name_the_limiting_rule():
    short = engine.get_portfolio(UserProfile(life_stage="peak_earning", goal="wealth_creation", risk_tolerance="high",
                                             risk_score=85, monthly_budget=20_000, horizon_years=4))
    assert any("4 years away" in r and "35%" in r for r in short.mix_reasons)
    home = engine.get_portfolio(UserProfile(life_stage="home_buyer", goal="buy_home", risk_tolerance="high",
                                            risk_score=85, monthly_budget=20_000, horizon_years=5))
    assert any("down payment" in r for r in home.mix_reasons)
    long = engine.get_portfolio(UserProfile(life_stage="peak_earning", goal="wealth_creation", risk_tolerance="high",
                                            risk_score=85, monthly_budget=20_000, horizon_years=12))
    assert not any("limited to" in r for r in long.mix_reasons)
    emergency = engine.get_portfolio(UserProfile(life_stage="peak_earning", goal="emergency_corpus",
                                                 risk_tolerance="high", monthly_budget=5_000))
    assert "Emergency money" in emergency.mix_reasons[0]


# ── One-time (lump sum) amounts ──────────────────────────────────────────────

@pytest.mark.parametrize("life_stage,goal", list(itertools.product(LifeStage, InvestmentGoal)))
def test_lump_sum_invariants(life_stage, goal):
    for lump, budget, horizon in itertools.product([1_000, 25_000, 300_000, 5_000_000], [0, 2_000, 30_000], [1, 4, 12]):
        p = engine.get_portfolio(UserProfile(life_stage=life_stage, goal=goal, risk_tolerance="high",
                                             monthly_budget=budget or None, lump_sum=lump, horizon_years=horizon,
                                             tax_regime="old"))
        ctx = (life_stage.value, goal.value, lump, budget, horizon)
        assert p.funds, ctx
        assert sum(f.lump_sum_amount for f in p.funds) == pytest.approx(lump), ctx
        assert sum(f.monthly_sip_amount for f in p.funds) == pytest.approx(budget), ctx
        if budget:
            assert all(f.monthly_sip_amount >= alloc.MIN_SIP for f in p.funds), ctx
        assert p.total_invested == pytest.approx(budget * 12 * horizon + lump), ctx
        assert p.projections["expected"].corpus >= lump, ctx


def test_lump_sum_reduces_the_sip_needed_for_a_target():
    common = dict(life_stage="new_parent", goal="child_education", risk_tolerance="moderate",
                  target_amount=3_000_000, horizon_years=12)
    without = engine.get_portfolio(UserProfile(**common))
    with_lump = engine.get_portfolio(UserProfile(**common, lump_sum=500_000))
    assert with_lump.monthly_sip_required < without.monthly_sip_required
    enough = engine.get_portfolio(UserProfile(**common, lump_sum=3_000_000))
    assert enough.monthly_sip_required is None and enough.goal_status == "on_track"


def test_large_equity_lump_sum_suggests_an_stp_and_small_one_is_rejected():
    p = engine.get_portfolio(UserProfile(**BASE, lump_sum=1_000_000))
    assert any("STP" in w for w in p.warnings)
    with pytest.raises(ValueError):
        engine.get_portfolio(UserProfile(life_stage="peak_earning", goal="wealth_creation",
                                         risk_tolerance="high", lump_sum=500, horizon_years=10))


def test_rupees_use_indian_grouping():
    from app.services.recommendation_engine import inr
    assert [inr(n) for n in (500, 1_000, 99_999, 400_000, 12_345_678, -150_000)] == \
        ["₹500", "₹1,000", "₹99,999", "₹4,00,000", "₹1,23,45,678", "-₹1,50,000"]


def test_plan_note_explains_a_cautious_plan_for_a_bold_investor():
    capped = engine.get_portfolio(UserProfile(life_stage="home_buyer", goal="buy_home", risk_tolerance="high",
                                              risk_score=85, monthly_budget=20_000, horizon_years=4))
    assert capped.plan_note == "Aggressive investor, cautious plan: home purchase within 5 years"
    free = engine.get_portfolio(UserProfile(life_stage="peak_earning", goal="wealth_creation", risk_tolerance="high",
                                            risk_score=85, monthly_budget=20_000, horizon_years=15))
    assert free.plan_note is None


# ── Funds already held ───────────────────────────────────────────────────────

PPFAS_FLEXI = "122639"          # Parag Parikh Flexi Cap, Direct Growth: in form, not the default flexi cap pick
SHRIRAM_FLEXI_REGULAR = "144902"  # bottom of the flexi cap ranking, Regular plan
GOLD_ETF = "153357"


def _balanced(**kw):
    base = dict(life_stage="peak_earning", goal="wealth_creation", risk_tolerance="moderate", risk_score=55,
                monthly_budget=20_000, horizon_years=10)
    return UserProfile(**{**base, **kw})


def test_plan_funds_carry_the_review_rating_label():
    plan = engine.get_portfolio(_balanced())
    assert all(f.rating_label in ("In form", "On track", "Off track", "Out of form") for f in plan.funds)
    assert all(not f.already_held for f in plan.funds)
    assert plan.existing is None


def test_existing_holdings_get_advice_and_a_good_one_is_kept_in_the_plan():
    held = [{"code": PPFAS_FLEXI, "value": 200_000}, {"code": SHRIRAM_FLEXI_REGULAR, "value": 50_000},
            {"code": GOLD_ETF, "value": 30_000}, {"code": "999999999", "value": 10_000}]
    plan = engine.get_portfolio(_balanced(existing_holdings=held))
    flexi = next(f for f in plan.funds if f.bucket == "flexi_cap")
    assert flexi.scheme_code == PPFAS_FLEXI and flexi.already_held
    assert "already hold this fund" in flexi.reason

    advice = {a.scheme_code: a for a in plan.existing.funds}
    assert advice[PPFAS_FLEXI].action == "keep" and "plan's pick" in advice[PPFAS_FLEXI].advice
    shriram = advice[SHRIRAM_FLEXI_REGULAR]
    assert (shriram.action, shriram.rating_status, shriram.plan) == ("switch", "out_of_form", "Regular")
    assert shriram.switch_to == flexi.scheme_name
    assert advice[GOLD_ETF].action == "review"
    assert any("999999999" in u for u in plan.existing.unpriced)
    assert plan.existing.value == 280_000 and plan.existing.counted


def test_counted_holdings_raise_the_projection_and_lower_the_sip_needed():
    goal = dict(target_amount=10_000_000, target_years=10)
    without = engine.get_portfolio(_balanced(**goal))
    counted = engine.get_portfolio(_balanced(existing_holdings=[{"code": PPFAS_FLEXI, "value": 1_000_000}], **goal))
    ignored = engine.get_portfolio(_balanced(existing_holdings=[{"code": PPFAS_FLEXI, "value": 1_000_000}],
                                             count_existing=False, **goal))
    assert counted.projections["expected"].corpus > without.projections["expected"].corpus
    assert counted.monthly_sip_required < without.monthly_sip_required
    assert ignored.projections["expected"].corpus == without.projections["expected"].corpus
    assert ignored.monthly_sip_required == without.monthly_sip_required
    assert not ignored.existing.counted and ignored.existing.funds


def test_units_are_valued_at_the_ranked_nav():
    nav = next(f["nav"] for f in engine.rankings.get()["buckets"]["flexi_cap"]["funds"] if f["code"] == PPFAS_FLEXI)
    plan = engine.get_portfolio(_balanced(existing_holdings=[{"code": PPFAS_FLEXI, "units": 10}]))
    assert plan.existing.funds[0].value == pytest.approx(10 * nav, abs=0.01)


def test_equity_held_for_a_short_goal_is_flagged_to_move():
    plan = engine.get_portfolio(_balanced(goal="buy_home", life_stage="home_buyer", horizon_years=2,
                                          existing_holdings=[{"code": PPFAS_FLEXI, "value": 100_000}]))
    assert plan.asset_mix["equity"] == 0
    assert plan.existing.funds[0].action == "move"
    assert plan.existing.asset_mix["equity"] == 100


def test_holdings_that_already_reach_the_target_need_an_amount_to_invest():
    with pytest.raises(ValueError, match="already hold should reach this target"):
        engine.get_portfolio(_balanced(monthly_budget=None, target_amount=500_000, target_years=10,
                                       existing_holdings=[{"code": PPFAS_FLEXI, "value": 1_000_000}]))
