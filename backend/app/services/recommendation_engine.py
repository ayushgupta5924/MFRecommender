import concurrent.futures
import math
from datetime import date
from typing import Dict, List, Optional, Set, Tuple

from app.models.user import (
    ExistingFundAdvice, ExistingPortfolio, FundAlternative, FundRecommendation, InvestmentGoal, LifeStage,
    PortfolioRecommendation, Projection, RiskProfile, RiskTolerance, TaxRegime, UserProfile,
)
from app.services import allocation as alloc
from app.services import nav as navs
from app.services.catalog import BUCKETS
from app.services.fund_facts import size_note
from app.services.ranking import tidy_name
from app.services.rankings_store import RankingsStore, scheme_map, store as default_store
from app.services.review import STATUSES, category_label, rate_fund, sleeve_for

INFLATION = 0.06
# Long-run return assumptions per sleeve are clamped to these bands so a hot or
# cold few years in the data can't produce unrealistic projections.
RETURN_BANDS = {"equity": (0.08, 0.12), "hybrid": (0.07, 0.11), "debt": (0.055, 0.08)}
SCENARIO_SHIFT = {
    "pessimistic": {"equity": -0.04, "hybrid": -0.025, "debt": -0.01},
    "expected":    {"equity": 0.0,   "hybrid": 0.0,    "debt": 0.0},
    "optimistic":  {"equity": +0.03, "hybrid": +0.02,  "debt": +0.0075},
}
# Where to invest: MF Central is run by the registrars (CAMS and KFintech) and offers every fund house's Direct
# plans. Linking there rather than a distributor keeps advice and distribution separate, as SEBI requires.
INVEST_URL = "https://www.mfcentral.com/"

MIN_LUMP_SUM = 1_000                  # common minimum for a one-time purchase
LUMP_SUM_FUNDS_DIVISOR = 20           # a one-time amount supports about as many funds as a SIP 1/20th its size
STP_THRESHOLD = 100_000               # suggest phasing in equity above this much

# Prefer funds that have been through at least one full market cycle.
PREFERRED_YEARS = {"equity": 5, "hybrid": 5, "debt": 3}
# Rough equity share inside each hybrid category, used only to explain the total.
HYBRID_EQUITY_SHARE = {"multi_asset": 0.5, "balanced_advantage": 0.5, "conservative_hybrid": 0.2}
RISK_TOLERANCE_SCORE = {RiskTolerance.LOW: 20, RiskTolerance.MODERATE: 50, RiskTolerance.HIGH: 80}
GOOD_STATUSES = ("in_form", "on_track")
EXISTING_MIX_GAP = 15                 # points of equity between current funds and the plan before we point it out

PORTFOLIO_NAMES = {
    (LifeStage.JUST_STARTED,     "conservative"): ("🌱 First Step",       "A safe, habit-building start to your investment journey."),
    (LifeStage.JUST_STARTED,     "balanced"):     ("⚡ Young & Growing",   "Balanced growth for someone just getting started."),
    (LifeStage.JUST_STARTED,     "aggressive"):   ("🚀 Young Achiever",    "Aggressive growth when time is on your side."),
    (LifeStage.RECENTLY_MARRIED, "conservative"): ("🏡 Nest Builder",      "Steady returns to build a secure foundation together."),
    (LifeStage.RECENTLY_MARRIED, "balanced"):     ("⚖️ Sleep Well",        "Balanced portfolio — grow wealth without losing sleep."),
    (LifeStage.RECENTLY_MARRIED, "aggressive"):   ("🚀 Wealth Builder",    "Aggressive growth in your prime earning years."),
    (LifeStage.NEW_PARENT,       "conservative"): ("🛡️ Family Shield",     "Capital protection with steady growth for your family."),
    (LifeStage.NEW_PARENT,       "balanced"):     ("🎓 Family Builder",    "Steady long-term compounding while family costs rise."),
    (LifeStage.NEW_PARENT,       "aggressive"):   ("🎓 Future Builder",    "Equity-heavy compounding for long-term family goals."),
    (LifeStage.HOME_BUYER,       "conservative"): ("🏠 Home Saver",        "Capital-safe accumulation for your down payment."),
    (LifeStage.HOME_BUYER,       "balanced"):     ("🏠 Home Ready",        "Balanced growth while protecting your home fund."),
    (LifeStage.HOME_BUYER,       "aggressive"):   ("🏠 Home Accelerator",  "Faster accumulation if your purchase is 5+ years away."),
    (LifeStage.PEAK_EARNING,     "conservative"): ("💼 Steady Compounder", "Reliable growth in your peak earning years."),
    (LifeStage.PEAK_EARNING,     "balanced"):     ("📈 Peak Performer",    "Optimised for wealth creation in your prime years."),
    (LifeStage.PEAK_EARNING,     "aggressive"):   ("🚀 Maximum Growth",    "High equity exposure to maximise long-term wealth."),
    (LifeStage.NEAR_RETIREMENT,  "conservative"): ("🎯 Retirement Ready",  "Capital preservation with steady income generation."),
    (LifeStage.NEAR_RETIREMENT,  "balanced"):     ("🎯 Safe Landing",      "Gradual shift to safety as retirement approaches."),
    (LifeStage.NEAR_RETIREMENT,  "aggressive"):   ("🎯 Last Sprint",       "Controlled growth for last-mile corpus building."),
    (LifeStage.RETIRED,          "conservative"): ("🧓 Peaceful Income",   "Capital safety with regular income focus."),
    (LifeStage.RETIRED,          "balanced"):     ("🧓 Calm Compounder",   "Low-volatility growth to beat inflation."),
    (LifeStage.RETIRED,          "aggressive"):   ("🧓 Active Retirement", "Moderate equity for inflation-beating returns."),
}


def inr(amount: float) -> str:
    """Rupees with Indian digit grouping: 4,00,000 rather than 400,000."""
    digits = f"{abs(round(amount)):d}"
    head, tail = digits[:-3], digits[-3:]
    while len(head) > 2:
        tail = f"{head[-2:]},{tail}"
        head = head[:-2]
    return f"{'-' if amount < 0 else ''}₹{head + ',' if head else ''}{tail}"


def pct(v: Optional[float], digits: int = 2) -> Optional[float]:
    return None if v is None else round(v * 100, digits)


def monthly_rate(annual: float) -> float:
    return (1 + annual) ** (1 / 12) - 1


def sip_future_value(monthly: float, years: int, annual: float) -> float:
    """Future value of a SIP paid at the start of each month (how SIPs actually work)."""
    if monthly <= 0 or years <= 0:
        return 0.0
    i, n = monthly_rate(annual), years * 12
    if i == 0:
        return monthly * n
    return monthly * ((1 + i) ** n - 1) / i * (1 + i)


def lump_future_value(amount: float, years: int, annual: float) -> float:
    return amount * (1 + annual) ** years if amount > 0 and years > 0 else max(amount, 0.0)


def required_sip(target: float, years: int, annual: float) -> float:
    unit = sip_future_value(1, years, annual)
    return target / unit if unit > 0 else 0.0


class RecommendationEngine:
    def __init__(self, rankings: RankingsStore = default_store):
        self.rankings = rankings

    # ── Public API ───────────────────────────────────────────────────────────

    def get_recommendations(self, profile: UserProfile) -> List[FundRecommendation]:
        return self.get_portfolio(profile).funds

    def get_portfolio(self, profile: UserProfile) -> PortfolioRecommendation:
        data = self.rankings.get()
        score, limited_by = self._risk_score(profile)
        label, scoring_profile = alloc.risk_label(score)
        horizon = alloc.resolve_horizon(profile.goal, profile.get_horizon())
        fixed = bool(profile.fixed_deadline)
        target = profile.target_amount or None
        target_today = None
        if target and profile.target_in_today_value:
            target_today = target
            target = round(target * (1 + INFLATION) ** horizon)
        warnings: List[str] = []

        # 0. Funds already held: valued and rated, and counted towards the goal unless the investor says not to.
        held, unpriced = self._held(profile, data)
        held_value = sum(h["value"] or 0 for h in held)
        counted = held_value if profile.count_existing else 0.0

        # 1. Decide the monthly amount. The investor's own budget always wins;
        #    a target only tells us whether that budget (plus any one-time amount) is enough.
        budget = profile.get_budget()
        lump = float(profile.lump_sum or 0)
        if 0 < lump < MIN_LUMP_SUM:
            raise ValueError(f"The minimum one-time amount is {inr(MIN_LUMP_SUM)}.")
        # ELSS's 80C limit is yearly, so a one-time amount counts towards it like a year of SIPs.
        yearly_view = budget + lump / 12
        provisional_mix, provisional_slots = alloc.build_slots(
            score, horizon, profile.life_stage, profile.goal, max(yearly_view, 10_000), profile.tax_regime, fixed)
        expected_rate = self._portfolio_rate(provisional_mix, provisional_slots, data, "expected")
        sip_needed = self._sip_needed(target, lump + counted, horizon, expected_rate) if target else None
        if budget <= 0 and not lump:
            if not sip_needed:
                if target and counted:
                    raise ValueError("The funds you already hold should reach this target on their own. Enter a "
                                     "monthly or one-time amount if you want to invest more.")
                raise ValueError("Enter a monthly amount, a one-time amount or a target.")
            budget = max(float(sip_needed), alloc.MIN_SIP)
        if 0 < budget < alloc.MIN_SIP:
            raise ValueError(f"The minimum monthly SIP is ₹{alloc.MIN_SIP}.")

        # 2. Allocation. The SIP sets how many funds there are (each SIP must be at least
        #    ₹500); with no SIP, the one-time amount does.
        sizing = budget if budget > 0 else lump / LUMP_SUM_FUNDS_DIVISOR
        base = budget if budget > 0 else lump
        mix, slots = alloc.build_slots(score, horizon, profile.life_stage, profile.goal, yearly_view,
                                       profile.tax_regime, fixed)
        hybrid_key = alloc.hybrid_bucket(max(mix["equity"], 0.2), score, horizon)
        slots = alloc.consolidate(slots, sizing, hybrid_key, protected=["elss"])
        amounts = alloc.to_amounts(slots, base)

        # 3. Pick the best fund in each bucket for this investor.
        # A fund the investor already holds is used for its category when it ranks in the top half.
        prefer: Dict[str, str] = {}
        for h in held:
            if h["bucket"] and h["rating"]["status"] in GOOD_STATUSES:
                prefer.setdefault(h["bucket"], h["twin"])
        funds = self._select_funds(slots, amounts, data, scoring_profile, profile, horizon, prefer)
        self._renormalise(funds, base)
        self._split_lump_sum(funds, budget, lump)
        held_twins = {h["twin"] for h in held}
        for f in funds:
            rating = rate_fund(f.scheme_code, f.bucket, data)
            f.rating_status, f.rating_label = rating["status"], STATUSES[rating["status"]][0]
            f.already_held = f.scheme_code in held_twins
            if prefer.get(f.bucket) == f.scheme_code:
                f.reason += (" You already hold this fund and it ranks in the top half of its category, "
                             "so the plan keeps using it rather than adding another.")

        # 4. Projections at three return scenarios.
        projections = {}
        for scenario in SCENARIO_SHIFT:
            rate = self._portfolio_rate(mix, slots, data, scenario)
            corpus = (sip_future_value(budget, horizon, rate) + lump_future_value(lump, horizon, rate)
                      + lump_future_value(counted, horizon, rate))
            projections[scenario] = Projection(
                annual_return=round(rate * 100, 2),
                corpus=round(corpus),
                corpus_today=round(corpus / (1 + INFLATION) ** horizon),
            )
        expected = projections["expected"].annual_return / 100

        goal_status = shortfall = None
        if target:
            sip_needed = self._sip_needed(target, lump + counted, horizon, expected)
            goal_status = "on_track" if projections["expected"].corpus >= target else "shortfall"
            if goal_status == "shortfall":
                shortfall = float(max(sip_needed - budget, 0))

        if lump and mix["equity"] * lump >= STP_THRESHOLD:
            warnings.append(f"Consider moving the equity part of your one-time amount (about "
                            f"{inr(mix['equity'] * lump)}) in over 6-12 months through an STP from a liquid fund, "
                            "so it doesn't all go in just before a fall.")
        warnings += self._suitability_warnings(profile, budget, limited_by)
        warnings += self._warnings(profile, horizon, funds, data)

        name, description = self._name(profile, scoring_profile, mix, horizon)
        plan_note = self._plan_note(profile, score, label, horizon, fixed)
        actual_mix = self._actual_mix(funds)
        existing = (self._existing_advice(held, unpriced, funds, actual_mix, horizon, held_value,
                                          profile.count_existing)
                    if held or unpriced else None)

        return PortfolioRecommendation(
            portfolio_name=name,
            portfolio_emoji=name.split()[0],
            portfolio_description=description,
            monthly_sip_required=float(sip_needed) if sip_needed else None,
            target_amount=target,
            target_amount_today=target_today,
            target_years=horizon if target else profile.target_years,
            expected_return=round(expected * 100, 2),
            funds=funds,
            monthly_investment=budget,
            lump_sum=lump,
            horizon_years=horizon,
            total_invested=budget * 12 * horizon + lump,
            asset_mix=actual_mix,
            plan_note=plan_note,
            mix_reasons=self._mix_reasons(profile, score, label, horizon, fixed, mix, actual_mix, budget, lump, len(funds)),
            projections=projections,
            goal_status=goal_status,
            shortfall_monthly=shortfall,
            existing=existing,
            risk_profile=RiskProfile(score=round(score, 1), label=label, profile=scoring_profile,
                                     capacity=profile.capacity_score, willingness=profile.willingness_score,
                                     limited_by=limited_by),
            inflation_assumption=INFLATION * 100,
            warnings=warnings,
            data_as_of=data.get("nav_date"),
            generated_at=data.get("generated_at"),
        )

    @staticmethod
    def _plan_note(profile: UserProfile, score: float, label: str, horizon: int, fixed: bool) -> Optional[str]:
        """When a safety rule holds equity well below what the risk profile points to, say so up front,
        so an Aggressive label next to a debt-heavy plan doesn't look like a mistake."""
        cap, _, why = alloc.equity_limit(horizon, profile.life_stage, profile.goal)
        target = alloc.target_equity(score, horizon, profile.life_stage, profile.goal, fixed)
        if why and target - cap >= 0.15:
            return f"{label} investor, cautious plan: {why}"
        return None

    @staticmethod
    def _sip_needed(target: float, lump: float, horizon: int, rate: float) -> int:
        """Monthly SIP that, with the money already there (one-time amount and counted holdings), reaches the
        target; 0 if that money is enough."""
        remaining = target - lump_future_value(lump, horizon, rate)
        return math.ceil(required_sip(remaining, horizon, rate) / 100) * 100 if remaining > 0 else 0

    @staticmethod
    def _split_lump_sum(funds: List[FundRecommendation], budget: float, lump: float) -> None:
        """Give each fund its share of the one-time amount, in the same proportions as the plan."""
        if not funds or not lump:
            return
        if budget <= 0:
            # One-time only: the amounts computed so far are the one-time amounts.
            for f in funds:
                f.lump_sum_amount, f.allocation_amount, f.monthly_sip_amount = f.allocation_amount, 0.0, 0.0
            return
        step = 100 if lump >= 100 * len(funds) else 1
        for f in funds:
            f.lump_sum_amount = float(round(lump * f.allocation_percentage / 100 / step) * step)
        funds[0].lump_sum_amount += lump - sum(f.lump_sum_amount for f in funds)

    @staticmethod
    def _mix_reasons(profile: UserProfile, score: float, label: str, horizon: int, fixed: bool,
                     mix: Dict[str, float], actual: Dict[str, float], budget: float, lump: float,
                     n_funds: int) -> List[str]:
        """Why the plan holds this much equity, hybrid and debt, using the same rules that built it."""
        cap, cap_reason, _ = alloc.equity_limit(horizon, profile.life_stage, profile.goal)
        if cap == 0:
            return [cap_reason or "", "The plan uses liquid and short-term debt funds, which rarely fall in value."]

        target = min(alloc.target_equity(score, horizon, profile.life_stage, profile.goal, fixed), 1.0)
        hybrid_key = alloc.hybrid_bucket(mix["equity"], score, horizon)
        total = mix["equity"] + mix["hybrid"] * HYBRID_EQUITY_SHARE[hybrid_key]
        basis = f"Your {label} risk profile, {horizon}-year timeline, life stage and goal point to about"
        if target > cap:
            out = [f"{basis} {alloc._round_to(target, 0.05):.0%} equity.",
                   cap_reason or f"No plan holds more than {cap:.0%} equity, so some stays in debt."]
        else:
            out = [f"{basis} {alloc._round_to(total, 0.05):.0%} equity."]
            if fixed and horizon < 10:
                out.append("Your date can't move, so the plan takes a little less equity than it otherwise would.")
        if mix["hybrid"] > 0:
            out.append(f"{mix['hybrid']:.0%} goes into a {BUCKETS[hybrid_key].label} fund, which holds both equity "
                       f"and debt to soften market falls. Counting the equity inside it, your total equity is about "
                       f"{alloc._round_to(total, 0.05):.0%}.")
        if mix["debt"] > 0:
            out.append(f"The remaining {mix['debt']:.0%} is in debt funds for stability.")
        if any(abs(actual[k] - mix[k] * 100) >= 5 for k in mix):
            amount = (f"a {inr(budget)} monthly SIP (each SIP must be at least ₹500)" if budget > 0
                      else f"a {inr(lump)} one-time amount")
            out.append(f"With {n_funds} fund{'s' if n_funds != 1 else ''} for {amount}, "
                       "some categories were combined, so the final mix "
                       "differs a little from this.")
        return out

    @staticmethod
    def _risk_score(profile: UserProfile):
        """(score used for the plan, which side limited it when capacity and willingness differ)."""
        cap, will = profile.capacity_score, profile.willingness_score
        if cap is not None and will is not None:
            if cap == will:
                return cap, None
            return min(cap, will), ("capacity" if cap < will else "willingness")
        if profile.risk_score is not None:
            return profile.risk_score, None
        return RISK_TOLERANCE_SCORE[profile.risk_tolerance], None

    @staticmethod
    def _name(profile: UserProfile, scoring_profile: str, mix: Dict[str, float], horizon: int):
        if profile.goal == InvestmentGoal.EMERGENCY_CORPUS:
            return "🛟 Safety Net", "Instantly accessible, low-risk funds for life's surprises."
        if profile.goal == InvestmentGoal.TAX_SAVING and profile.tax_regime != TaxRegime.NEW:
            return "🧾 Tax Smart", "Section 80C savings alongside a diversified long-term mix."
        if mix["equity"] == 0:
            return "🔒 Capital Shield", f"Debt-focused plan for money you need within {horizon} years."
        return PORTFOLIO_NAMES.get((profile.life_stage, scoring_profile),
                                   ("📊 Custom Portfolio", "A fund mix based on your profile."))

    # ── Funds already held ───────────────────────────────────────────────────

    def _held(self, profile: UserProfile, data: dict) -> Tuple[List[dict], List[str]]:
        """The investor's funds merged by scheme, valued today and rated, largest first; and the ones we couldn't use."""
        if not profile.existing_holdings:
            return [], []
        schemes = scheme_map.schemes()
        merged: Dict[str, dict] = {}
        unpriced: List[str] = []
        for h in profile.existing_holdings:
            s = schemes.get(h.code)
            if not s:
                unpriced.append(f"Scheme {h.code} (not recognised: closed or merged)")
                continue
            m = merged.setdefault(h.code, {"scheme": s, "units": 0.0, "value": 0.0})
            if h.value is not None:
                m["value"] += h.value
            elif h.units is not None:
                m["units"] += h.units

        # Units need today's NAV: ranked Direct-Growth funds have it already, others are looked up.
        ranked_nav = {f["code"]: f.get("nav") for b in data["buckets"].values() for f in b.get("funds", [])}
        lookup = [c for c, m in merged.items() if m["units"] and not ranked_nav.get(c)]
        fetched: Dict[str, Optional[tuple]] = {}
        if lookup:
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                fetched = dict(zip(lookup, pool.map(navs.latest_nav, lookup)))

        rows = []
        for code, m in merged.items():
            s = m["scheme"]
            value: Optional[float] = m["value"]
            if m["units"]:
                price = ranked_nav.get(code) or (fetched.get(code) or (None,))[0]
                value = value + m["units"] * price if price else (value or None)
            name = tidy_name(s["name"]).rstrip(". ")
            if not value:
                unpriced.append(f"{name} (couldn't get today's price)")
            rows.append({"code": code, "name": name, "scheme": s, "twin": s["twin"], "bucket": s["bucket"],
                         "sleeve": sleeve_for(s), "direct": s["direct"], "value": round(value, 2) if value else None,
                         "rating": rate_fund(s["twin"], s["bucket"], data)})
        rows.sort(key=lambda r: -(r["value"] or 0))
        return rows, unpriced

    @staticmethod
    def _existing_advice(held: List[dict], unpriced: List[str], funds: List[FundRecommendation],
                         plan_mix: Dict[str, float], horizon: int, value: float, counted: bool) -> ExistingPortfolio:
        """What to do with each fund already held, given the plan built for this goal."""
        pick_for = {f.bucket: f for f in funds}
        no_equity = plan_mix.get("equity", 0) == 0 and plan_mix.get("hybrid", 0) == 0
        advice = []
        for h in held:
            status = h["rating"]["status"]
            pick = pick_for.get(h["bucket"])
            in_plan = bool(pick and pick.scheme_code == h["twin"])
            switch_to = None
            if no_equity and h["sleeve"] in ("equity", "hybrid"):
                action = "move"
                text = (f"This goal is {horizon} year{'s' if horizon != 1 else ''} away, too soon for equity, so this "
                        "fund doesn't suit it. Keep it for a longer goal, or move it to the plan's debt funds well "
                        "before you need the money (check exit load and capital gains tax first).")
            elif pick and in_plan:
                action = "keep"
                text = f"This is the plan's pick for {pick.category}: keep it, and the plan's SIP goes here too."
                if not h["direct"]:
                    text += (" Put new money in its Direct plan: you hold the Regular plan, which costs more "
                             "every year for the same portfolio.")
            elif status in GOOD_STATUSES:
                action, text = "keep", "Keep it. It ranks in the top half of its category, so there's no reason to switch."
            elif status == "off_track":
                action, text = "watch", STATUSES["off_track"][1]
            elif status == "out_of_form" and pick:
                action, switch_to = "switch", pick.scheme_name
                text = (f"It's in the bottom quarter of its category. Stop new SIPs here: the plan's "
                        f"{pick.category} fund is {pick.scheme_name}. Before selling existing units, check exit load "
                        "and capital gains tax.")
            elif status == "out_of_form":
                action, text = "switch", STATUSES["out_of_form"][1]
            elif h["sleeve"] == "other":
                action, text = "review", "We don't rate gold and similar funds, and they aren't part of this plan's mix."
            else:
                action, text = "review", h["rating"]["reason"]
            if not h["direct"] and action in ("keep", "watch") and not in_plan:
                text += " You hold the Regular plan; its Direct plan holds the same portfolio for a lower yearly cost."
            advice.append(ExistingFundAdvice(
                scheme_code=h["code"], scheme_name=h["name"], category=category_label(h["scheme"]),
                plan="Direct" if h["direct"] else "Regular", value=h["value"],
                rating_status=status, rating_label=STATUSES[status][0], action=action, advice=text,
                switch_to=switch_to))

        mix = {k: 0.0 for k in ("equity", "hybrid", "debt", "other")}
        for h in held:
            if h["value"]:
                mix[h["sleeve"]] += h["value"]
        mix = {k: round(100 * v / value, 1) if value else 0.0 for k, v in mix.items()}

        notes = []
        if value and counted:
            notes.append(f"The {inr(value)} you already hold counts towards this goal, assumed to grow at the "
                         "plan's rate, so you need a smaller SIP.")
        elif value:
            notes.append("Not counted towards this goal, as you asked. The advice on each fund still applies.")
        if value and abs(mix["equity"] - plan_mix.get("equity", 0)) >= EXISTING_MIX_GAP:
            notes.append(f"Your current funds are {mix['equity']:.0f}% equity against {plan_mix.get('equity', 0):.0f}% "
                         "in the plan. New money follows the plan, so the gap narrows as you invest; look at the "
                         "split again once a year.")
        return ExistingPortfolio(value=round(value, 2), counted=counted and value > 0, asset_mix=mix,
                                 funds=advice, notes=notes, unpriced=unpriced)

    # ── Fund selection ───────────────────────────────────────────────────────

    def _candidates(self, bucket_key: str, data: dict, scoring_profile: str) -> List[dict]:
        bucket = BUCKETS[bucket_key]
        funds = data["buckets"].get(bucket_key, {}).get("funds", [])
        ranked = sorted(funds, key=lambda f: f["scores"][scoring_profile], reverse=True)
        seasoned = [f for f in ranked if f["years_history"] >= PREFERRED_YEARS[bucket.sleeve]]
        return seasoned if len(seasoned) >= 3 else ranked

    def _seasoned_note(self, bucket_key: str, rank_of: int, data: dict) -> str:
        total = data["buckets"][bucket_key]["stats"]["count"]
        years = PREFERRED_YEARS[BUCKETS[bucket_key].sleeve]
        return f" with {years}+ years of history" if rank_of < total else ""

    def _select_funds(self, slots: Dict[str, float], amounts: Dict[str, int], data: dict,
                      scoring_profile: str, profile: UserProfile, horizon: int,
                      prefer: Optional[Dict[str, str]] = None) -> List[FundRecommendation]:
        used_amcs: Set[str] = set()
        picks = []
        # Biggest slots choose first so they get first pick of fund houses.
        for bucket_key in sorted(slots, key=lambda k: -slots[k]):
            candidates = self._candidates(bucket_key, data, scoring_profile)
            if not candidates:
                continue
            # Spread across fund houses: take the best fund from an AMC not already used, if it is in the top 5.
            # A track record belongs to the managers who built it, so skip funds whose managers changed this year.
            # A good fund the investor already holds comes first: no need to add another in the same category.
            choice = (next((f for f in candidates if f["code"] == (prefer or {}).get(bucket_key)), None)
                      or next((f for f in candidates[:5] if f["amc"] not in used_amcs and not f.get("manager_changed")), None)
                      or next((f for f in candidates[:5] if f["amc"] not in used_amcs), candidates[0]))
            used_amcs.add(choice["amc"])
            rank = candidates.index(choice) + 1
            alternatives = [f for f in candidates if f["code"] != choice["code"]][:2]
            picks.append(self._to_recommendation(
                bucket_key, choice, rank, len(candidates), alternatives, amounts[bucket_key],
                slots[bucket_key], data, scoring_profile, profile, horizon))
        picks.sort(key=lambda f: -f.allocation_amount)
        return picks

    def _to_recommendation(self, bucket_key, f, rank, rank_of, alternatives, amount, fraction, data,
                           scoring_profile, profile, horizon) -> FundRecommendation:
        bucket = BUCKETS[bucket_key]
        stats = data["buckets"][bucket_key]["stats"]
        return FundRecommendation(
            scheme_name=f["name"],
            scheme_code=f["code"],
            category=bucket.label,
            nav=f["nav"],
            returns_1y=pct(f.get("cagr_1y")),
            returns_3y=pct(f.get("cagr_3y")),
            returns_5y=pct(f.get("cagr_5y")),
            risk_level=bucket.risk_level,
            allocation_percentage=round(fraction * 100, 2),
            allocation_amount=float(amount),
            monthly_sip_amount=float(amount),
            reason=self._reason(bucket, f, rank, rank_of, stats, scoring_profile, profile, horizon,
                                self._seasoned_note(bucket_key, rank_of, data)),
            investment_url=INVEST_URL,
            isin=scheme_map.isin(f["code"]),
            info_url=scheme_map.fund_page_url(f["code"]),
            amc=f["amc"],
            bucket=bucket_key,
            sebi_category=f.get("category", ""),
            nav_date=f.get("nav_date"),
            rank=rank,
            rank_of=rank_of,
            score=f["scores"][scoring_profile],
            volatility=pct(f.get("volatility")),
            max_drawdown=pct(f.get("max_drawdown")),
            rolling_return_median=pct(f.get("rolling_median")),
            rolling_years=f.get("rolling_years"),
            category_median_3y=pct(stats.get("median_cagr_3y")),
            category_median_5y=pct(stats.get("median_cagr_5y")),
            years_history=round(f["years_history"], 1),
            lock_in_years=bucket.lock_in_years,
            expense_ratio=f.get("ter"),
            category_median_expense_ratio=stats.get("median_ter"),
            aum_cr=f.get("aum_cr"),
            size_note=size_note(f, bucket_key, bucket.sleeve, bucket.label.lower()),
            benchmark=data["buckets"][bucket_key].get("benchmark"),
            excess_return=pct(f.get("excess_return")),
            beat_rate=pct(f.get("beat_rate"), 0),
            down_capture=pct(f.get("down_capture"), 0),
            managers=f.get("managers") or [],
            manager_since=f.get("manager_since"),
            manager_changed=f.get("manager_changed"),
            stocks=f.get("stocks") or None,
            top10_pct=f.get("top10_pct"),
            cash_pct=f.get("cash_pct"),
            portfolio_date=f.get("portfolio_date"),
            alternatives=[FundAlternative(
                scheme_name=a["name"], scheme_code=a["code"], amc=a["amc"],
                info_url=scheme_map.fund_page_url(a["code"]),
                returns_3y=pct(a.get("cagr_3y")), returns_5y=pct(a.get("cagr_5y")),
                score=a["scores"][scoring_profile]) for a in alternatives],
        )

    @staticmethod
    def _renormalise(funds: List[FundRecommendation], budget: float) -> None:
        """If a bucket had no funds, spread its money over the rest so totals still add up."""
        total = sum(f.allocation_amount for f in funds)
        if not funds or abs(total - budget) < 1:
            return
        for f in funds:
            f.allocation_amount = f.monthly_sip_amount = float(round(f.allocation_amount * budget / total))
        funds[0].allocation_amount += budget - sum(f.allocation_amount for f in funds)
        funds[0].monthly_sip_amount = funds[0].allocation_amount
        for f in funds:
            f.allocation_percentage = round(f.allocation_amount * 100 / budget, 2)

    @staticmethod
    def _actual_mix(funds: List[FundRecommendation]) -> Dict[str, float]:
        mix = {"equity": 0.0, "hybrid": 0.0, "debt": 0.0}
        for f in funds:
            mix[BUCKETS[f.bucket].sleeve] += f.allocation_percentage
        return {k: round(v, 1) for k, v in mix.items()}

    # ── Projections ──────────────────────────────────────────────────────────

    def _portfolio_rate(self, mix: Dict[str, float], slots: Dict[str, float], data: dict, scenario: str) -> float:
        """Weighted long-run return from each bucket's median rolling return (category, not top fund)."""
        total = sum(slots.values()) or 1
        rate = 0.0
        for key, weight in slots.items():
            sleeve = BUCKETS[key].sleeve
            stats = data["buckets"].get(key, {}).get("stats", {})
            assumed = stats.get("median_rolling_median") or stats.get("median_cagr_5y") or stats.get("median_cagr_3y")
            lo, hi = RETURN_BANDS[sleeve]
            assumed = min(max(assumed if assumed is not None else lo, lo), hi)
            rate += weight / total * (assumed + SCENARIO_SHIFT[scenario][sleeve])
        return max(rate, 0.0)

    # ── Explanations ─────────────────────────────────────────────────────────

    def _rankings_bucket(self, key: str) -> Optional[dict]:
        return self.rankings.get()["buckets"].get(key)

    def _reason(self, bucket, f, rank, rank_of, stats, scoring_profile, profile, horizon, seasoned="") -> str:
        profile_word = {"conservative": "a conservative", "balanced": "a moderate", "aggressive": "an aggressive"}[scoring_profile]
        parts = [bucket.role, f"Ranked #{rank} of {rank_of} {bucket.label} funds{seasoned} for {profile_word} investor."]

        ret_key, ret_label = ("cagr_5y", "5-yr") if f.get("cagr_5y") is not None else ("cagr_3y", "3-yr")
        fund_ret, cat_ret = f.get(ret_key), stats.get(f"median_{ret_key}")
        if fund_ret is not None and cat_ret is not None:
            parts.append(f"{ret_label} return {fund_ret * 100:.1f}% p.a. vs category median {cat_ret * 100:.1f}%.")
        dd, cat_dd = f.get("max_drawdown"), stats.get("median_max_drawdown")
        if dd is not None and cat_dd is not None and bucket.sleeve != "debt":
            parts.append(f"Worst fall in 5 yrs {dd * 100:.0f}% vs category {cat_dd * 100:.0f}%.")
        index = (self._rankings_bucket(bucket.key) or {}).get("benchmark")
        if index and f.get("beat_rate") is not None and f.get("down_capture") is not None:
            parts.append(f"Beat the {index} index in {f['beat_rate'] * 100:.0f}% of 3-year periods and took "
                         f"{f['down_capture'] * 100:.0f}% of its monthly falls.")
        ter, cat_ter = f.get("ter"), stats.get("median_ter")
        if ter is not None and cat_ter is not None:
            parts.append(f"Expense ratio {ter:.2f}% a year vs category median {cat_ter:.2f}%.")
        note = size_note(f, bucket.key, bucket.sleeve, bucket.label.lower())
        if note:
            parts.append(note)

        if bucket.key == "elss" and profile.goal == InvestmentGoal.TAX_SAVING:
            parts.append("Up to ₹1.5 lakh a year is deductible under Section 80C (old tax regime only).")
        elif profile.goal == InvestmentGoal.EMERGENCY_CORPUS and bucket.key == "liquid":
            parts.append("Redemptions are typically paid the next working day.")
        elif profile.life_stage == LifeStage.NEAR_RETIREMENT and bucket.sleeve == "debt":
            parts.append("Protects what you have built from market swings close to retirement.")
        elif profile.life_stage == LifeStage.HOME_BUYER and bucket.sleeve == "debt":
            parts.append("Keeps your down payment safe from equity market falls.")
        return " ".join(parts)

    @staticmethod
    def _suitability_warnings(profile: UserProfile, budget: float, limited_by: Optional[str]) -> List[str]:
        """Checks on the investor's finances. Each only fires when the answer was given."""
        out = []
        if limited_by == "capacity":
            out.append("You're comfortable with more risk than your finances can absorb right now "
                       "(age, income, dependents, loans or savings), so the plan uses the lower of the two.")
        income = profile.monthly_income
        if income:
            emi = profile.monthly_emi or 0
            surplus = income - (profile.monthly_expenses or 0) - emi
            if budget > max(surplus, 0):
                out.append(f"This SIP is more than you have left each month after expenses and EMIs "
                           f"(about {inr(max(surplus, 0))}). Make sure you can keep it going.")
            if emi / income > 0.4:
                out.append(f"Your EMIs take {emi / income:.0%} of your income. Prepaying costly loans "
                           "can be a better first step than investing.")
        if (profile.emergency_months is not None and profile.emergency_months < 3
                and profile.goal != InvestmentGoal.EMERGENCY_CORPUS):
            out.append("You have under 3 months of expenses saved. Build an emergency fund first "
                       "or alongside this plan, so you're never forced to sell in a bad market.")
        if profile.has_health_insurance is False:
            out.append("You don't have health insurance. One hospital bill can undo years of investing; "
                       "consider a health cover before or alongside this plan.")
        if profile.has_term_insurance is False and (profile.dependents or 0) > 0:
            out.append("People depend on your income but you have no term insurance. A term plan "
                       "protects them if something happens to you.")
        return out

    def _warnings(self, profile: UserProfile, horizon: int, funds: List[FundRecommendation], data: dict) -> List[str]:
        out = []
        buckets = {f.bucket for f in funds}
        if horizon < 3 and profile.goal != InvestmentGoal.EMERGENCY_CORPUS:
            out.append("Your horizon is under 3 years, so the plan holds no equity: equity can fall sharply over short periods.")
        if "elss" in buckets:
            out.append("ELSS units are locked in for 3 years from each SIP instalment.")
        if profile.goal == InvestmentGoal.TAX_SAVING and profile.tax_regime == TaxRegime.NEW:
            out.append("Under the new tax regime ELSS gives no deduction, so the plan uses regular equity funds instead.")
        if "small_cap" in buckets or "mid_cap" in buckets:
            out.append("Mid and small cap funds can fall 30-50% in bad years; stay invested through the full horizon.")
        if any((f.years_history or 0) < 5 and BUCKETS[f.bucket].sleeve != "debt" for f in funds):
            out.append("Some picks have under 5 years of history; past results cover less than a full market cycle.")
        nav_date = data.get("nav_date")
        if nav_date:
            try:
                age = (date.today() - date.fromisoformat(nav_date)).days
                if age > 5:
                    out.append(f"Fund data is {age} days old (NAV date {nav_date}).")
            except ValueError:
                pass
        return out
