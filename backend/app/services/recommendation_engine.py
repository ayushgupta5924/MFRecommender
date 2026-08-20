import math
from app.models.user import (
    UserProfile, FundRecommendation, PortfolioRecommendation,
    RiskTolerance, InvestmentGoal, LifeStage
)
from app.services.mf_service import MutualFundService
from typing import List, Dict, Tuple


class RecommendationEngine:
    def __init__(self):
        self.mf_service = MutualFundService()

    SCHEME_MAP = {
        "Equity":    "120503",  # Axis Bluechip Fund Direct Growth
        "Mid Cap":   "119551",  # Axis Midcap Fund Direct Growth
        "Large Cap": "118701",  # SBI Bluechip Fund Direct Growth
        "Hybrid":    "118590",  # HDFC Balanced Advantage Direct Growth
        "Debt":      "118989",  # HDFC Corporate Bond Direct Growth
        "Liquid":    "120505",  # Axis Liquid Fund Direct Growth
        "ELSS":      "120594",  # Axis Long Term Equity Direct Growth
        "Index":     "120716",  # UTI Nifty 50 Index Direct Growth
    }

    # Expected annual returns per risk level (used for SIP math)
    EXPECTED_RETURNS = {
        RiskTolerance.LOW:      0.07,   # 7% p.a.
        RiskTolerance.MODERATE: 0.10,   # 10% p.a.
        RiskTolerance.HIGH:     0.13,   # 13% p.a.
    }

    # Named portfolios mapped to (life_stage, goal, risk)
    PORTFOLIO_NAMES = {
        (LifeStage.JUST_STARTED,     RiskTolerance.LOW):      ("🌱 First Step",       "A safe, habit-building start to your investment journey."),
        (LifeStage.JUST_STARTED,     RiskTolerance.MODERATE): ("⚡ Young & Growing",   "Balanced growth for someone just getting started."),
        (LifeStage.JUST_STARTED,     RiskTolerance.HIGH):     ("🚀 Young Achiever",    "Aggressive growth when time is on your side."),
        (LifeStage.RECENTLY_MARRIED, RiskTolerance.LOW):      ("🏡 Nest Builder",      "Steady returns to build a secure foundation together."),
        (LifeStage.RECENTLY_MARRIED, RiskTolerance.MODERATE): ("⚖️ Sleep Well",        "Balanced portfolio — grow wealth without losing sleep."),
        (LifeStage.RECENTLY_MARRIED, RiskTolerance.HIGH):     ("🚀 Wealth Builder",    "Aggressive growth in your prime earning years."),
        (LifeStage.NEW_PARENT,       RiskTolerance.LOW):      ("🛡️ Family Shield",     "Capital protection with steady growth for your family."),
        (LifeStage.NEW_PARENT,       RiskTolerance.MODERATE): ("🎓 Education Fund",    "15–18 year compounding plan for your child's education."),
        (LifeStage.NEW_PARENT,       RiskTolerance.HIGH):     ("🎓 Education Builder", "Equity-heavy education corpus for long-term compounding."),
        (LifeStage.HOME_BUYER,       RiskTolerance.LOW):      ("🏠 Home Saver",        "Capital-safe accumulation for your down payment."),
        (LifeStage.HOME_BUYER,       RiskTolerance.MODERATE): ("🏠 Home Ready",        "Balanced growth while protecting your home fund."),
        (LifeStage.HOME_BUYER,       RiskTolerance.HIGH):     ("🏠 Home Accelerator",  "Faster accumulation if your purchase is 5+ years away."),
        (LifeStage.PEAK_EARNING,     RiskTolerance.LOW):      ("💼 Steady Compounder", "Reliable growth in your peak earning years."),
        (LifeStage.PEAK_EARNING,     RiskTolerance.MODERATE): ("📈 Peak Performer",    "Optimised for wealth creation in your prime years."),
        (LifeStage.PEAK_EARNING,     RiskTolerance.HIGH):     ("🚀 Maximum Growth",    "Full equity exposure to maximise long-term wealth."),
        (LifeStage.NEAR_RETIREMENT,  RiskTolerance.LOW):      ("🎯 Retirement Ready",  "Capital preservation with steady income generation."),
        (LifeStage.NEAR_RETIREMENT,  RiskTolerance.MODERATE): ("🎯 Safe Landing",      "Gradual shift to safety as retirement approaches."),
        (LifeStage.NEAR_RETIREMENT,  RiskTolerance.HIGH):     ("🎯 Last Sprint",       "Controlled aggression for last-mile corpus building."),
        (LifeStage.RETIRED,          RiskTolerance.LOW):      ("🧓 Peaceful Income",   "Capital safety with regular income focus."),
        (LifeStage.RETIRED,          RiskTolerance.MODERATE): ("🧓 Calm Compounder",   "Low-volatility growth to beat inflation."),
        (LifeStage.RETIRED,          RiskTolerance.HIGH):     ("🧓 Active Retirement", "Moderate equity for inflation-beating returns."),
    }

    # ── SIP Calculator ─────────────────────────────────────────────────────────

    def calculate_required_sip(self, target: float, years: int, annual_rate: float) -> float:
        """
        Calculate monthly SIP needed to reach a target amount.
        Formula: SIP = FV * r / ((1+r)^n - 1)
        where r = monthly rate, n = months
        """
        if years <= 0 or target <= 0:
            return 0
        r = annual_rate / 12          # monthly rate
        n = years * 12                # total months
        sip = target * r / ((math.pow(1 + r, n)) - 1)
        return round(sip, 2)

    def calculate_future_value(self, monthly_sip: float, years: int, annual_rate: float) -> float:
        """Calculate future value of a monthly SIP."""
        if years <= 0 or monthly_sip <= 0:
            return 0
        r = annual_rate / 12
        n = years * 12
        fv = monthly_sip * (math.pow(1 + r, n) - 1) / r * (1 + r)
        return round(fv, 2)

    # ── Main entry point ───────────────────────────────────────────────────────

    def get_recommendations(self, profile: UserProfile) -> List[FundRecommendation]:
        """Returns flat list of FundRecommendation for API backward compatibility."""
        portfolio = self.get_portfolio(profile)
        return portfolio.funds

    def get_portfolio(self, profile: UserProfile) -> PortfolioRecommendation:
        """Returns a full named portfolio with SIP math and fund recommendations."""
        budget    = float(profile.monthly_budget or profile.budget or 0)
        risk      = profile.risk_tolerance
        horizon   = int(profile.target_years or profile.investment_horizon or 5)
        life_stage= profile.life_stage
        goal      = profile.goal
        target    = profile.target_amount
        years     = profile.target_years or horizon

        expected_return = self.EXPECTED_RETURNS[risk]

        # SIP Math
        sip_required = None
        if target and years:
            sip_required = self.calculate_required_sip(target, years, expected_return)

        effective_budget = sip_required if sip_required else budget

        # Build allocation
        allocation = self._build_allocation(risk, life_stage, goal, horizon, effective_budget)
        allocation = self._normalize(allocation)

        # Portfolio name
        key = (life_stage, risk)
        name, description = self.PORTFOLIO_NAMES.get(
            key, ("📊 Custom Portfolio", "A personalised fund mix based on your profile.")
        )

        # Fetch funds
        funds = self._fetch_funds(allocation, effective_budget, risk, goal, horizon, life_stage)

        return PortfolioRecommendation(
            portfolio_name=name,
            portfolio_emoji=name.split()[0],
            portfolio_description=description,
            monthly_sip_required=sip_required,
            target_amount=target,
            target_years=years,
            expected_return=expected_return * 100,
            funds=funds,
        )

    # ── Allocation Builder ─────────────────────────────────────────────────────

    def _build_allocation(
        self,
        risk: RiskTolerance,
        life_stage: LifeStage,
        goal: InvestmentGoal,
        horizon: int,
        budget: float
    ) -> dict:

        # Start with life-stage base
        alloc = self._life_stage_base(life_stage, risk)

        # Overlay goal-specific adjustments
        alloc = self._apply_goal(alloc, goal, horizon)

        # Overlay horizon adjustments
        alloc = self._apply_horizon(alloc, horizon)

        return alloc

    def _life_stage_base(self, life_stage: LifeStage, risk: RiskTolerance) -> dict:
        """
        Life stage determines the fundamental asset mix.
        Risk tolerance then tilts it more aggressive or conservative.
        """
        base = {
            LifeStage.JUST_STARTED: {
                RiskTolerance.LOW:      {"Debt": 50, "Hybrid": 30, "Liquid": 20},
                RiskTolerance.MODERATE: {"Equity": 40, "Hybrid": 30, "Debt": 20, "Index": 10},
                RiskTolerance.HIGH:     {"Equity": 50, "Mid Cap": 30, "Index": 20},
            },
            LifeStage.RECENTLY_MARRIED: {
                RiskTolerance.LOW:      {"Debt": 40, "Hybrid": 35, "Liquid": 25},
                RiskTolerance.MODERATE: {"Hybrid": 40, "Equity": 30, "Debt": 20, "Liquid": 10},
                RiskTolerance.HIGH:     {"Equity": 45, "Mid Cap": 30, "Hybrid": 15, "Debt": 10},
            },
            LifeStage.NEW_PARENT: {
                RiskTolerance.LOW:      {"Debt": 45, "Hybrid": 30, "Liquid": 25},
                RiskTolerance.MODERATE: {"Hybrid": 35, "Equity": 30, "Debt": 25, "Liquid": 10},
                RiskTolerance.HIGH:     {"Equity": 40, "Mid Cap": 25, "Hybrid": 20, "Debt": 15},
            },
            LifeStage.HOME_BUYER: {
                RiskTolerance.LOW:      {"Debt": 55, "Liquid": 30, "Hybrid": 15},
                RiskTolerance.MODERATE: {"Debt": 40, "Hybrid": 35, "Liquid": 25},
                RiskTolerance.HIGH:     {"Hybrid": 40, "Equity": 35, "Debt": 25},
            },
            LifeStage.PEAK_EARNING: {
                RiskTolerance.LOW:      {"Debt": 40, "Hybrid": 35, "Equity": 15, "Liquid": 10},
                RiskTolerance.MODERATE: {"Equity": 40, "Hybrid": 25, "Debt": 20, "Index": 15},
                RiskTolerance.HIGH:     {"Equity": 40, "Mid Cap": 25, "Large Cap": 20, "Index": 15},
            },
            LifeStage.NEAR_RETIREMENT: {
                RiskTolerance.LOW:      {"Debt": 55, "Liquid": 30, "Hybrid": 15},
                RiskTolerance.MODERATE: {"Debt": 45, "Hybrid": 30, "Equity": 15, "Liquid": 10},
                RiskTolerance.HIGH:     {"Debt": 35, "Hybrid": 30, "Equity": 25, "Liquid": 10},
            },
            LifeStage.RETIRED: {
                RiskTolerance.LOW:      {"Debt": 60, "Liquid": 30, "Hybrid": 10},
                RiskTolerance.MODERATE: {"Debt": 50, "Hybrid": 30, "Liquid": 20},
                RiskTolerance.HIGH:     {"Debt": 40, "Hybrid": 30, "Equity": 20, "Liquid": 10},
            },
        }
        return dict(base[life_stage][risk])

    def _apply_goal(self, alloc: dict, goal: InvestmentGoal, horizon: int) -> dict:
        a = dict(alloc)

        if goal == InvestmentGoal.TAX_SAVING:
            # Replace up to 50% of equity with ELSS
            eq = a.pop("Equity", 0)
            elss = round(eq * 0.6)
            a["ELSS"]   = a.get("ELSS", 0) + elss
            a["Equity"] = eq - elss

        elif goal == InvestmentGoal.EMERGENCY_CORPUS:
            # Safety first — all liquid and debt
            total = sum(a.values())
            a = {"Liquid": round(total * 0.6), "Debt": round(total * 0.4)}

        elif goal == InvestmentGoal.BUY_HOME and horizon <= 4:
            # Short home-buy horizon — protect capital
            equity = a.pop("Equity", 0) + a.pop("Mid Cap", 0)
            a["Debt"]   = a.get("Debt", 0) + round(equity * 0.6)
            a["Liquid"] = a.get("Liquid", 0) + round(equity * 0.4)

        elif goal == InvestmentGoal.CHILD_EDUCATION and horizon >= 10:
            # Long education horizon — add index for low-cost equity
            eq = a.get("Equity", 0)
            shift = round(eq * 0.25)
            a["Equity"] = eq - shift
            a["Index"]  = a.get("Index", 0) + shift

        elif goal == InvestmentGoal.RETIREMENT and horizon >= 15:
            # Very long term — maximize equity compounding
            debt = a.get("Debt", 0)
            shift = round(debt * 0.3)
            a["Debt"]   = debt - shift
            a["Index"]  = a.get("Index", 0) + shift

        elif goal == InvestmentGoal.FINANCIAL_FREEDOM:
            # Financial freedom — balanced growth + index
            eq = a.get("Equity", 0)
            shift = round(eq * 0.2)
            a["Equity"] = eq - shift
            a["Index"]  = a.get("Index", 0) + shift

        return a

    def _apply_horizon(self, alloc: dict, horizon: int) -> dict:
        a = dict(alloc)

        if horizon < 3:
            # Short term — move all equity to debt/liquid
            risky = a.pop("Equity", 0) + a.pop("Mid Cap", 0) + a.pop("ELSS", 0)
            if risky:
                a["Liquid"] = a.get("Liquid", 0) + round(risky * 0.5)
                a["Debt"]   = a.get("Debt", 0)   + round(risky * 0.5)

        elif horizon >= 10:
            # Long term — move liquid to equity
            liquid = a.pop("Liquid", 0)
            if liquid:
                a["Equity"] = a.get("Equity", 0) + liquid

        return a

    # ── Normalize ──────────────────────────────────────────────────────────────

    def _normalize(self, allocation: dict) -> dict:
        alloc = {k: v for k, v in allocation.items() if v and v > 0}
        total = sum(alloc.values())
        if not total:
            return {"Debt": 100}
        normalized = {k: round(v * 100 / total) for k, v in alloc.items()}
        # Fix rounding so it always sums to 100
        diff = 100 - sum(normalized.values())
        if diff and normalized:
            largest = max(normalized, key=normalized.get)
            normalized[largest] += diff
        return normalized

    # ── Fetch Funds ────────────────────────────────────────────────────────────

    def _fetch_funds(
        self,
        allocation: dict,
        budget: float,
        risk: RiskTolerance,
        goal: InvestmentGoal,
        horizon: int,
        life_stage: LifeStage,
    ) -> List[FundRecommendation]:
        funds = []
        for category, percentage in allocation.items():
            scheme_code = self.SCHEME_MAP.get(category)
            if not scheme_code:
                continue
            try:
                details = self.mf_service.get_scheme_details(scheme_code)
                if details and details.get("data"):
                    nav_data = details["data"]
                    meta     = details.get("meta", {})
                    monthly_sip = round(budget * percentage / 100)
                    funds.append(FundRecommendation(
                        scheme_name=meta.get("scheme_name", f"{category} Fund"),
                        scheme_code=scheme_code,
                        category=category,
                        nav=float(nav_data[0]["nav"]),
                        returns_1y=self.mf_service.calculate_returns(nav_data, 1),
                        returns_3y=self.mf_service.calculate_returns(nav_data, 3),
                        returns_5y=self.mf_service.calculate_returns(nav_data, 5),
                        risk_level=self._map_risk_level(category),
                        allocation_percentage=float(percentage),
                        allocation_amount=round(budget * percentage / 100),
                        monthly_sip_amount=float(monthly_sip),
                        reason=self._get_reason(category, risk, goal, horizon, life_stage),
                        investment_url=f"https://www.mfapi.in/mf/{scheme_code}",
                    ))
            except Exception as e:
                print(f"Error fetching {category} ({scheme_code}): {e}")
        return funds

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _map_risk_level(self, category: str) -> str:
        if category in ["Equity", "Mid Cap", "ELSS"]:    return "High"
        if category in ["Hybrid", "Large Cap", "Index"]: return "Moderate"
        return "Low"

    def _get_reason(
        self,
        category: str,
        risk: RiskTolerance,
        goal: InvestmentGoal,
        horizon: int,
        life_stage: LifeStage,
    ) -> str:
        base = {
            "Equity":    "Equity funds provide strong long-term capital appreciation.",
            "Mid Cap":   "Mid Cap funds offer high growth potential for aggressive investors.",
            "Large Cap": "Large Cap funds deliver stable returns from established companies.",
            "Hybrid":    "Hybrid funds balance growth and stability in a single fund.",
            "Debt":      "Debt funds protect capital with predictable, low-risk returns.",
            "Liquid":    "Liquid funds offer instant access with near-zero risk.",
            "ELSS":      "ELSS funds grow your wealth while saving tax under Section 80C.",
            "Index":     "Index funds offer low-cost, passive exposure to market returns.",
        }.get(category, f"{category} fund suits your profile.")

        extras = []

        # Goal-specific
        if goal == InvestmentGoal.TAX_SAVING and category == "ELSS":
            extras.append("Saves up to ₹46,800 in tax annually under Section 80C")
        if goal == InvestmentGoal.CHILD_EDUCATION and category == "Index":
            extras.append("Low expense ratio maximises corpus over a 15+ year education horizon")
        if goal == InvestmentGoal.EMERGENCY_CORPUS and category == "Liquid":
            extras.append("Redeemable within 1 business day — ideal for emergencies")
        if goal == InvestmentGoal.RETIREMENT and category in ["Index", "Equity"]:
            extras.append("Long compounding runway makes this ideal for retirement corpus")

        # Life stage specific
        if life_stage == LifeStage.NEW_PARENT and category == "Hybrid":
            extras.append("Reduces volatility — important when family expenses are high")
        if life_stage == LifeStage.NEAR_RETIREMENT and category == "Debt":
            extras.append("Protects your corpus from market swings close to retirement")
        if life_stage == LifeStage.JUST_STARTED and category in ["Equity", "Mid Cap"]:
            extras.append("Starting early with equity maximises compounding benefit")
        if life_stage == LifeStage.HOME_BUYER and category in ["Liquid", "Debt"]:
            extras.append("Capital protection ensures your down payment is safe")

        # Horizon specific
        if horizon >= 10 and category == "Equity":
            extras.append(f"Over {horizon} years, equity historically delivers 12–15% annually")
        if horizon < 3 and category in ["Liquid", "Debt"]:
            extras.append("Short horizon demands capital safety over growth")

        if extras:
            return base + " " + extras[0] + "."
        return base