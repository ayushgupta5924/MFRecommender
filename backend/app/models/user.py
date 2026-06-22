from pydantic import BaseModel
from typing import List, Optional
from enum import Enum

class RiskTolerance(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"

class InvestmentGoal(str, Enum):
    RETIREMENT = "retirement"
    WEALTH_CREATION = "wealth_creation"
    EDUCATION = "education"
    TAX_SAVING = "tax_saving"
    SHORT_TERM = "short_term"

class UserProfile(BaseModel):
    budget: float
    risk_tolerance: RiskTolerance
    investment_horizon: int
    goals: List[InvestmentGoal]
    age: int
    monthly_income: Optional[float] = None

class FundRecommendation(BaseModel):
    scheme_name: str
    scheme_code: str
    category: str
    nav: float
    returns_1y: Optional[float]
    returns_3y: Optional[float]
    returns_5y: Optional[float]
    risk_level: str
    allocation_percentage: float
    allocation_amount: float
    reason: str
    investment_url: str

    class Config:
        use_enum_values = True
