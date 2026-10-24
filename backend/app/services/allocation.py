"""Asset allocation: how much goes to equity / hybrid / debt, and which buckets within each.

Allocation is a continuous function of the risk score, horizon, life stage and
goal, so two investors only get the same mix if their situations really match.
Hard safety rules (short horizons, emergency money) are applied last so nothing
can override them.
"""
from typing import Dict, List, Optional, Tuple

from app.models.user import InvestmentGoal, LifeStage, TaxRegime
from app.services.catalog import BUCKETS

ELSS_80C_MONTHLY_CAP = 12_500          # ₹1.5 lakh a year under Section 80C
MIN_SIP = 500                          # most AMCs accept ₹500 SIPs; some accept ₹100

LIFE_STAGE_TILT = {
    LifeStage.JUST_STARTED:     +0.05,
    LifeStage.RECENTLY_MARRIED:  0.00,
    LifeStage.NEW_PARENT:       -0.05,
    LifeStage.HOME_BUYER:       -0.10,
    LifeStage.PEAK_EARNING:      0.00,
    LifeStage.NEAR_RETIREMENT:  -0.15,
    LifeStage.RETIRED:          -0.20,
}
LIFE_STAGE_EQUITY_CAP = {
    LifeStage.NEAR_RETIREMENT: 0.50,
    LifeStage.RETIRED:         0.40,
}
GOAL_TILT = {
    InvestmentGoal.WEALTH_CREATION:   +0.05,
    InvestmentGoal.FINANCIAL_FREEDOM: +0.03,
    InvestmentGoal.RETIREMENT:         0.00,
    InvestmentGoal.CHILD_EDUCATION:    0.00,
    InvestmentGoal.TAX_SAVING:         0.00,
    InvestmentGoal.BUY_HOME:          -0.05,
    InvestmentGoal.EMERGENCY_CORPUS:   0.00,
}
DEFAULT_HORIZON = {
    InvestmentGoal.EMERGENCY_CORPUS: 1,
    InvestmentGoal.TAX_SAVING:       5,
    InvestmentGoal.BUY_HOME:         5,
    InvestmentGoal.CHILD_EDUCATION:  12,
    InvestmentGoal.RETIREMENT:       20,
    InvestmentGoal.FINANCIAL_FREEDOM:15,
    InvestmentGoal.WEALTH_CREATION:  10,
}

# When there is not enough money for every slot, a slot is folded into the
# nearest similar bucket that is already in the portfolio.
MERGE_INTO = {
    "small_cap": ["mid_cap", "flexi_cap", "large_cap", "index_large"],
    "mid_cap": ["flexi_cap", "large_cap", "index_large"],
    "large_cap": ["index_large", "flexi_cap"],
    "flexi_cap": ["index_large", "large_cap", "elss"],
    "index_large": ["flexi_cap", "large_cap", "elss"],
    "multi_asset": ["balanced_advantage", "flexi_cap", "index_large"],
    "balanced_advantage": ["index_large", "flexi_cap", "corporate_bond", "short_duration"],
    "conservative_hybrid": ["corporate_bond", "short_duration", "money_market", "liquid"],
    "gilt": ["banking_psu", "corporate_bond", "short_duration"],
    "banking_psu": ["corporate_bond", "short_duration", "money_market"],
    "corporate_bond": ["banking_psu", "short_duration", "money_market"],
    "short_duration": ["corporate_bond", "money_market", "liquid"],
    "money_market": ["liquid", "short_duration"],
    "liquid": ["money_market", "short_duration"],
}


FALLBACK_SLEEVES = {
    "equity": ["hybrid", "debt"],
    "hybrid": ["debt", "equity"],
    "debt":   ["hybrid", "equity"],
}


def risk_label(score: float) -> Tuple[str, str]:
    """(label shown to user, scoring profile used for ranking)."""
    if score < 35:
        return "Conservative", "conservative"
    if score < 70:
        return "Moderate", "balanced"
    return "Aggressive", "aggressive"


def resolve_horizon(goal: InvestmentGoal, horizon: Optional[int]) -> int:
    return int(horizon) if horizon else DEFAULT_HORIZON[goal]


def _round_to(x: float, step: float) -> float:
    return round(x / step) * step


def sleeve_mix(score: float, horizon: int, life_stage: LifeStage, goal: InvestmentGoal) -> Dict[str, float]:
    """Fractions of the portfolio in equity / hybrid / debt (sum to 1)."""
    if goal == InvestmentGoal.EMERGENCY_CORPUS or horizon < 3:
        return {"equity": 0.0, "hybrid": 0.0, "debt": 1.0}

    s = score / 100
    equity = 0.15 + 0.70 * s + LIFE_STAGE_TILT[life_stage] + GOAL_TILT[goal]
    # Longer horizons can carry a little more equity, shorter ones less.
    equity += max(-0.10, min(0.10, (horizon - 7) * 0.02))

    if horizon < 4:
        cap = 0.25
    elif horizon < 5:
        cap = 0.35
    elif horizon < 7:
        cap = 0.60
    else:
        cap = 0.90
    cap = min(cap, LIFE_STAGE_EQUITY_CAP.get(life_stage, 1.0))
    if goal == InvestmentGoal.BUY_HOME and horizon <= 5:
        cap = min(cap, 0.30)
    equity = max(0.0, min(equity, cap))

    # A hybrid sleeve smooths the ride for middle-of-the-road mixes.
    if 0.20 <= equity <= 0.75:
        hybrid = 0.20
        equity -= 0.10
    elif equity < 0.20:
        hybrid = 0.15
    else:
        hybrid = 0.0

    equity = _round_to(equity, 0.05)
    hybrid = _round_to(hybrid, 0.05)
    debt = max(0.0, 1 - equity - hybrid)
    return {"equity": round(equity, 4), "hybrid": round(hybrid, 4), "debt": round(debt, 4)}


def equity_split(score: float, horizon: int) -> Dict[str, float]:
    """Core (index / large cap) shrinks and satellite (mid / small) grows with risk and time."""
    s = score / 100
    split = {
        "index_large": 0.45 - 0.25 * s,
        "large_cap":   0.25 - 0.15 * s,
        "flexi_cap":   0.20 + 0.05 * s,
        "mid_cap":     (0.05 + 0.20 * s) if horizon >= 7 else (0.10 * s if horizon >= 5 else 0.0),
        "small_cap":   0.15 * s if (horizon >= 7 and s >= 0.6) else 0.0,
    }
    total = sum(split.values())
    return {k: v / total for k, v in split.items() if v > 0}


def hybrid_bucket(equity_fraction: float, score: float, horizon: int) -> str:
    if equity_fraction == 0 or score < 25:
        return "conservative_hybrid"
    if horizon < 5 or score < 55:
        return "balanced_advantage"
    return "multi_asset"


def debt_split(horizon: int, goal: InvestmentGoal) -> Dict[str, float]:
    if goal == InvestmentGoal.EMERGENCY_CORPUS:
        return {"liquid": 0.7, "money_market": 0.3}
    if horizon < 1:
        return {"liquid": 1.0}
    if horizon < 3:
        return {"money_market": 0.5, "short_duration": 0.5} if horizon >= 2 else {"liquid": 0.4, "money_market": 0.6}
    if horizon < 5:
        return {"short_duration": 0.5, "corporate_bond": 0.5}
    return {"corporate_bond": 0.45, "banking_psu": 0.35, "gilt": 0.20}


def build_slots(score: float, horizon: int, life_stage: LifeStage, goal: InvestmentGoal,
                budget: float, tax_regime: Optional[TaxRegime]) -> Tuple[Dict[str, float], Dict[str, float]]:
    """Return (sleeve mix, bucket -> fraction of portfolio)."""
    mix = sleeve_mix(score, horizon, life_stage, goal)
    slots: Dict[str, float] = {}

    if mix["equity"] > 0:
        eq_split = equity_split(score, horizon)
        use_elss = goal == InvestmentGoal.TAX_SAVING and tax_regime != TaxRegime.NEW
        if use_elss:
            # ELSS takes as much of the equity sleeve as the 80C limit allows.
            elss_share = min(1.0, ELSS_80C_MONTHLY_CAP / max(budget * mix["equity"], 1))
            slots["elss"] = mix["equity"] * elss_share
            rest = mix["equity"] * (1 - elss_share)
            for k, v in eq_split.items():
                slots[k] = slots.get(k, 0) + rest * v
        else:
            for k, v in eq_split.items():
                slots[k] = mix["equity"] * v

    if mix["hybrid"] > 0:
        slots[hybrid_bucket(mix["equity"], score, horizon)] = mix["hybrid"]

    if mix["debt"] > 0:
        for k, v in debt_split(horizon, goal).items():
            slots[k] = slots.get(k, 0) + mix["debt"] * v

    return mix, {k: v for k, v in slots.items() if v > 1e-6}


def max_funds_for(budget: float) -> int:
    if budget < 3_000:
        n = 2
    elif budget < 10_000:
        n = 3
    elif budget < 25_000:
        n = 4
    elif budget < 50_000:
        n = 5
    else:
        n = 6
    return max(1, min(n, int(budget // MIN_SIP)))


def consolidate(slots: Dict[str, float], budget: float, hybrid_key: str, protected: List[str] = ()) -> Dict[str, float]:
    """Merge the smallest slots until the count fits the budget and every SIP is at least MIN_SIP.

    Slots merge into a similar bucket first. When a whole equity or debt sleeve is
    too small to keep, it goes into a hybrid fund rather than the other sleeve, so a
    small budget never silently turns a balanced plan into an all-equity one.
    """
    slots = dict(slots)
    limit = max_funds_for(budget)
    sleeve_of = lambda k: BUCKETS[k].sleeve  # noqa: E731
    has_equity = any(sleeve_of(k) == "equity" for k in slots)
    has_debt = any(sleeve_of(k) == "debt" for k in slots)

    if limit == 1:
        # One fund has to represent the whole plan, so pick by the overall mix.
        totals = {s: sum(v for k, v in slots.items() if sleeve_of(k) == s) for s in ("equity", "hybrid", "debt")}
        if totals["equity"] >= 0.65:
            sleeve = "equity"
        elif totals["equity"] + totals["hybrid"] <= 0.15:
            sleeve = "debt"
        else:
            return {hybrid_key: 1.0}
        best = max((k for k in slots if sleeve_of(k) == sleeve), key=slots.get)
        return {best: 1.0}

    if has_equity and has_debt:
        for sleeve in ("equity", "debt"):
            keys = [k for k in slots if sleeve_of(k) == sleeve and k not in protected]
            if keys and sum(slots[k] for k in keys) * budget < MIN_SIP:
                for k in keys:
                    slots[hybrid_key] = slots.get(hybrid_key, 0) + slots.pop(k)

    def too_small(k):
        return slots[k] * budget < MIN_SIP

    def same_sleeve_target(k):
        return next((t for t in MERGE_INTO.get(k, [])
                     if t in slots and t != k and BUCKETS[t].sleeve == BUCKETS[k].sleeve), None)

    while len(slots) > 1:
        # A protected slot (ELSS) only stays separate if it is big enough on its own.
        candidates = [k for k in slots if k not in protected or too_small(k)] or list(slots)
        undersized = [k for k in candidates if too_small(k)]
        if undersized:
            pick = min(undersized, key=slots.get)
        elif len(slots) > limit:
            # Too many funds: shrink within a sleeve before touching the equity/debt balance.
            mergeable = [k for k in candidates if same_sleeve_target(k)]
            pick = min(mergeable or candidates, key=slots.get)
        else:
            break
        target = same_sleeve_target(pick) or next(
            (t for t in MERGE_INTO.get(pick, []) if t in slots and t != pick), None)
        if target is None and BUCKETS[pick].sleeve != "hybrid":
            # Crossing sleeves: prefer a hybrid fund over the other sleeve.
            target = next((k for k in slots if k != pick and BUCKETS[k].sleeve == "hybrid"), None)
            if target is None and has_equity and has_debt and len(slots) <= limit:
                target = hybrid_key
                slots.setdefault(hybrid_key, 0.0)
        if target is None:
            # Last resort: move towards the safer sleeve so merging never adds risk.
            for sleeve in FALLBACK_SLEEVES[sleeve_of(pick)]:
                same = [k for k in slots if k != pick and sleeve_of(k) == sleeve]
                if same:
                    target = max(same, key=slots.get)
                    break
        slots[target] += slots.pop(pick)
    return slots


def to_amounts(slots: Dict[str, float], budget: float) -> Dict[str, int]:
    """Whole-rupee SIP amounts (multiples of ₹100 where possible) that add up exactly to the budget."""
    step = 100 if budget >= 100 * len(slots) else 1
    amounts = {k: int(_round_to(v * budget, step)) for k, v in slots.items()}
    diff = int(round(budget)) - sum(amounts.values())
    if amounts:
        largest = max(amounts, key=amounts.get)
        amounts[largest] += diff
    return amounts
