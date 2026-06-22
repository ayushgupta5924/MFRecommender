from app.models.user import UserProfile, FundRecommendation, RiskTolerance, InvestmentGoal
from app.services.mf_service import MutualFundService
from typing import List

class RecommendationEngine:
    def __init__(self):
        self.mf_service = MutualFundService()

    def _get_safe_attr(self, profile, attr_name, default=None):
        val = None
        if hasattr(profile, attr_name):
            val = getattr(profile, attr_name)
        elif isinstance(profile, dict):
            val = profile.get(attr_name, default)
        return val if val is not None else default

    def get_recommendations(self, profile: UserProfile) -> List[FundRecommendation]:
        budget = self._get_safe_attr(profile, 'budget', 0)
        allocation = self._get_allocation_strategy(profile)
        recommendations = []

        scheme_map = {
            'Equity': '120503',
            'Debt': '118989',
            'Hybrid': '118590',
            'Liquid': '120505',
            'Mid Cap': '119551',
            'Large Cap': '120503',
        }

        total_percentage = 0
        for category, percentage in allocation.items():
            scheme_code = scheme_map.get(category)
            if scheme_code:
                try:
                    details = self.mf_service.get_scheme_details(scheme_code)
                    if details and details.get('data'):
                        nav_data = details['data']
                        meta = details.get('meta', {})
                        recommendations.append(FundRecommendation(
                            scheme_name=meta.get('scheme_name', f'{category} Fund'),
                            scheme_code=scheme_code,
                            category=category,
                            nav=float(nav_data[0]['nav']),
                            returns_1y=self.mf_service.calculate_returns(nav_data, 1),
                            returns_3y=self.mf_service.calculate_returns(nav_data, 3),
                            returns_5y=self.mf_service.calculate_returns(nav_data, 5),
                            risk_level=self._map_risk_level(category),
                            allocation_percentage=percentage,
                            allocation_amount=budget * (percentage / 100),
                            reason=self._get_reason(category, profile),
                            investment_url=f"https://www.mfapi.in/mf/{scheme_code}"
                        ))
                        total_percentage += percentage
                except Exception as e:
                    print(f"Error fetching {category}: {e}")
                    continue

        if recommendations and total_percentage != 100:
            adjustment = 100 - total_percentage
            recommendations[0].allocation_percentage += adjustment
            recommendations[0].allocation_amount = budget * (recommendations[0].allocation_percentage / 100)

        return recommendations

    def _get_allocation_strategy(self, profile: UserProfile) -> dict:
        budget = self._get_safe_attr(profile, 'budget', 0)
        risk_tolerance = self._get_safe_attr(profile, 'risk_tolerance')

        if budget < 5000:
            if risk_tolerance == RiskTolerance.LOW:
                return {'Debt': 100}
            elif risk_tolerance == RiskTolerance.MODERATE:
                return {'Hybrid': 100}
            else:
                return {'Equity': 100}
        elif budget < 10000:
            if risk_tolerance == RiskTolerance.LOW:
                return {'Debt': 70, 'Liquid': 30}
            elif risk_tolerance == RiskTolerance.MODERATE:
                return {'Hybrid': 60, 'Debt': 40}
            else:
                return {'Equity': 70, 'Debt': 30}
        elif budget < 25000:
            if risk_tolerance == RiskTolerance.LOW:
                return {'Debt': 50, 'Liquid': 30, 'Hybrid': 20}
            elif risk_tolerance == RiskTolerance.MODERATE:
                return {'Hybrid': 50, 'Debt': 30, 'Equity': 20}
            else:
                return {'Equity': 50, 'Mid Cap': 30, 'Debt': 20}
        elif budget < 50000:
            if risk_tolerance == RiskTolerance.LOW:
                return {'Debt': 40, 'Liquid': 30, 'Hybrid': 20, 'Equity': 10}
            elif risk_tolerance == RiskTolerance.MODERATE:
                return {'Hybrid': 35, 'Debt': 30, 'Equity': 25, 'Liquid': 10}
            else:
                return {'Equity': 40, 'Mid Cap': 30, 'Large Cap': 20, 'Debt': 10}
        else:
            if risk_tolerance == RiskTolerance.LOW:
                return {'Debt': 35, 'Liquid': 25, 'Hybrid': 20, 'Equity': 15, 'Large Cap': 5}
            elif risk_tolerance == RiskTolerance.MODERATE:
                return {'Hybrid': 30, 'Equity': 25, 'Debt': 20, 'Mid Cap': 15, 'Liquid': 10}
            else:
                return {'Equity': 35, 'Mid Cap': 25, 'Large Cap': 20, 'Hybrid': 10, 'Debt': 10}

    def _map_risk_level(self, category: str) -> str:
        if any(x in category.lower() for x in ['equity', 'mid cap', 'small cap']):
            return 'High'
        if any(x in category.lower() for x in ['hybrid', 'balanced']):
            return 'Moderate'
        return 'Low'

    def _get_reason(self, category: str, profile) -> str:
        goals = self._get_safe_attr(profile, 'goals', [])
        horizon = self._get_safe_attr(profile, 'investment_horizon', 0)

        reasons = {
            'Equity': "Equity funds offer high long-term growth potential, suited for your aggressive risk profile.",
            'Mid Cap': "Mid Cap funds provide strong growth opportunities with moderate-to-high risk, ideal for wealth creation.",
            'Large Cap': "Large Cap funds offer stability with steady returns from well-established companies.",
            'Hybrid': "Hybrid funds balance growth and stability, matching your moderate risk tolerance.",
            'Debt': "Debt funds provide stable, low-risk returns to protect a portion of your portfolio.",
            'Liquid': "Liquid funds ensure quick access to funds with minimal risk, ideal for short-term parking.",
            'Ultra Short': "Ultra Short Duration funds offer better returns than savings accounts with low risk.",
            'ELSS': "ELSS funds provide tax savings under Section 80C along with equity growth potential.",
            'Balanced': "Balanced funds spread risk across equity and debt for steady, moderate returns.",
            'Short Duration': "Short Duration funds suit your shorter investment horizon with low interest rate risk.",
        }

        goal_hints = []
        if InvestmentGoal.TAX_SAVING in goals:
            goal_hints.append("tax saving")
        if InvestmentGoal.RETIREMENT in goals:
            goal_hints.append("retirement planning")
        if InvestmentGoal.WEALTH_CREATION in goals:
            goal_hints.append("wealth creation")

        base_reason = reasons.get(category, f"{category} fund recommended based on your profile.")
        if goal_hints:
            base_reason += f" Aligned with your goals: {', '.join(goal_hints)}."
        if horizon and horizon > 5:
            base_reason += " Your long investment horizon further supports this choice."

        return base_reason