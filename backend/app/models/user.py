from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


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


class TaxRegime(str, Enum):
    OLD = "old"
    NEW = "new"


class UserProfile(BaseModel):
    # Core inputs
    life_stage:         LifeStage
    goal:               InvestmentGoal
    risk_tolerance:     RiskTolerance
    risk_score:         Optional[float] = Field(None, ge=0, le=100)   # from the risk questionnaire
    # Ability (finances) and willingness (attitude) to take risk, scored separately.
    # When both are given the plan uses the lower one.
    capacity_score:     Optional[float] = Field(None, ge=0, le=100)
    willingness_score:  Optional[float] = Field(None, ge=0, le=100)
    monthly_budget:     Optional[float] = Field(None, ge=0, le=10_000_000)
    lump_sum:           Optional[float] = Field(None, ge=0, le=10_000_000_000)   # one-time amount invested now

    # Goal-based SIP calculator inputs
    target_amount:      Optional[float] = Field(None, ge=0, le=10_000_000_000)   # e.g. 5000000 (50 lakhs)
    target_years:       Optional[int]   = Field(None, ge=1, le=40)
    horizon_years:      Optional[int]   = Field(None, ge=1, le=40)
    tax_regime:         Optional[TaxRegime] = None
    target_in_today_value: bool = False          # target is in today's rupees; grow it by inflation
    fixed_deadline:     Optional[bool]  = None   # True if the date can't move should markets be down

    # Finances, used for suitability checks
    age:                Optional[int]   = Field(None, ge=0, le=120)
    monthly_income:     Optional[float] = Field(None, ge=0, le=1_000_000_000)
    monthly_expenses:   Optional[float] = Field(None, ge=0, le=1_000_000_000)   # excluding EMIs
    monthly_emi:        Optional[float] = Field(None, ge=0, le=1_000_000_000)
    dependents:         Optional[int]   = Field(None, ge=0, le=20)
    emergency_months:   Optional[float] = Field(None, ge=0, le=120)
    has_health_insurance: Optional[bool] = None
    has_term_insurance:   Optional[bool] = None

    # Legacy support
    budget:             Optional[float] = None
    investment_horizon: Optional[int]   = None
    goals:              Optional[List[str]] = None

    def get_budget(self) -> float:
        return float(self.monthly_budget or self.budget or 0)

    def get_horizon(self) -> Optional[int]:
        return self.horizon_years or self.target_years or self.investment_horizon


class FundAlternative(BaseModel):
    scheme_name:  str
    scheme_code:  str
    amc:          str
    returns_3y:   Optional[float]
    returns_5y:   Optional[float]
    score:        float


class FundRecommendation(BaseModel):
    scheme_name:          str
    scheme_code:          str
    category:             str
    nav:                  float
    returns_1y:           Optional[float]     # % p.a. (CAGR)
    returns_3y:           Optional[float]
    returns_5y:           Optional[float]
    risk_level:           str
    allocation_percentage:float
    allocation_amount:    float
    monthly_sip_amount:   float
    reason:               str
    investment_url:       str                   # neutral: MF Central, the RTAs' platform for Direct plans
    isin:                 Optional[str] = None

    # Evidence behind the pick
    amc:                  str = ""
    bucket:               str = ""
    sebi_category:        str = ""
    nav_date:             Optional[str] = None
    rank:                 Optional[int] = None
    rank_of:              Optional[int] = None
    score:                Optional[float] = None
    volatility:           Optional[float] = None    # % p.a.
    max_drawdown:         Optional[float] = None    # %, negative
    rolling_return_median:Optional[float] = None    # % p.a.
    rolling_years:        Optional[int] = None
    category_median_3y:   Optional[float] = None
    category_median_5y:   Optional[float] = None
    years_history:        Optional[float] = None
    lock_in_years:        int = 0
    lump_sum_amount:      float = 0             # this fund's share of the one-time amount
    alternatives:         List[FundAlternative] = []


class Projection(BaseModel):
    annual_return:    float     # % p.a.
    corpus:           float
    corpus_today:     float     # in today's rupees after inflation


class RiskProfile(BaseModel):
    score:   float
    label:   str
    profile: str
    capacity:    Optional[float] = None
    willingness: Optional[float] = None
    limited_by:  Optional[str] = None    # "capacity" | "willingness" when the two differ


class PortfolioRecommendation(BaseModel):
    portfolio_name:        str
    portfolio_emoji:       str
    portfolio_description: str
    monthly_sip_required:  Optional[float]
    target_amount:         Optional[float]          # in rupees at the end of the horizon
    target_years:          Optional[int]
    expected_return:       float
    funds:                 List[FundRecommendation]

    monthly_investment:    float = 0
    lump_sum:              float = 0
    horizon_years:         int = 0
    total_invested:        float = 0
    asset_mix:             Dict[str, float] = {}
    mix_reasons:           List[str] = []           # plain-language "why this mix"
    plan_note:             Optional[str] = None     # e.g. "Aggressive investor, cautious plan: goal 4 years away"
    projections:           Dict[str, Projection] = {}
    target_amount_today:   Optional[float] = None   # the target as entered, when given in today's rupees
    goal_status:           Optional[str] = None     # "on_track" | "shortfall"
    shortfall_monthly:     Optional[float] = None
    risk_profile:          Optional[RiskProfile] = None
    inflation_assumption:  float = 6.0
    warnings:              List[str] = []
    data_as_of:            Optional[str] = None
    generated_at:          Optional[str] = None
    methodology_version:   str = "2.0"
