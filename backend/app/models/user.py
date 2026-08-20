from pydantic import BaseModel
from typing import List, Optional
from enum import Enum


class LifeStage(str, Enum):
    JUST_STARTED    = "just_started"
    RECENTLY_MARRIED= "recently_married"
    NEW_PARENT      = "new_parent"
    HOME_BUYER      = "home_buyer"
    PEAK_EARNING    = "peak_earning"
    NEAR_RETIREMENT = "near_retirement"
    RETIRED         = "retired"


class InvestmentGoal(str, Enum):
    FINANCIAL_FREEDOM = "financial_freedom"
    BUY_HOME          = "buy_home"
    CHILD_EDUCATION   = "child_education"
    RETIREMENT        = "retirement"
    TAX_SAVING        = "tax_saving"
    EMERGENCY_CORPUS  = "emergency_corpus"
    WEALTH_CREATION   = "wealth_creation"


class RiskTolerance(str, Enum):
    LOW      = "low"
    MODERATE = "moderate"
    HIGH     = "high"


class UserProfile(BaseModel):
    # Core inputs
    monthly_budget:     float
    life_stage:         LifeStage
    goal:               InvestmentGoal
    risk_tolerance:     RiskTolerance

    # Goal-based SIP calculator inputs
    target_amount:      Optional[float] = None   # e.g. 5000000 (50 lakhs)
    target_years:       Optional[int]   = None   # e.g. 10

    # Legacy support
    budget:             Optional[float] = None
    age:                Optional[int]   = None
    investment_horizon: Optional[int]   = None
    goals:              Optional[List[str]] = None

    def get_budget(self) -> float:
        return self.monthly_budget or self.budget or 0

    def get_horizon(self) -> int:
        return self.target_years or self.investment_horizon or 5


class FundRecommendation(BaseModel):
    scheme_name:          str
    scheme_code:          str
    category:             str
    nav:                  float
    returns_1y:           Optional[float]
    returns_3y:           Optional[float]
    returns_5y:           Optional[float]
    risk_level:           str
    allocation_percentage:float
    allocation_amount:    float
    monthly_sip_amount:   float
    reason:               str
    investment_url:       str


class PortfolioRecommendation(BaseModel):
    portfolio_name:        str
    portfolio_emoji:       str
    portfolio_description: str
    monthly_sip_required:  Optional[float]
    target_amount:         Optional[float]
    target_years:          Optional[int]
    expected_return:       float
    funds:                 List[FundRecommendation]