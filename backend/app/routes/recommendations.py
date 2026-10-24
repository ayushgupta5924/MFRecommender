from fastapi import APIRouter, HTTPException
from app.models.user import UserProfile, FundRecommendation, PortfolioRecommendation
from app.services.catalog import BUCKETS
from app.services.recommendation_engine import RecommendationEngine
from typing import List

from app.services.auth import accounts_enabled
import logging

logger = logging.getLogger(__name__)
router = APIRouter()
engine = RecommendationEngine()


def _build(profile: UserProfile) -> PortfolioRecommendation:
    try:
        return engine.get_portfolio(profile)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        logger.exception("Failed to build portfolio")
        raise HTTPException(status_code=500, detail="Could not build a portfolio right now. Please try again.")


@router.post("/portfolio", response_model=PortfolioRecommendation)
def get_portfolio(profile: UserProfile):
    """Named portfolio with fund picks, projections and the evidence behind each pick."""
    logger.info("portfolio: life_stage=%s goal=%s risk=%s score=%s horizon=%s",
                profile.life_stage.value, profile.goal.value, profile.risk_tolerance.value,
                profile.risk_score, profile.get_horizon())
    return _build(profile)


@router.post("/recommend", response_model=List[FundRecommendation])
def get_recommendations(profile: UserProfile):
    """Backward-compatible endpoint — returns flat fund list."""
    funds = _build(profile).funds
    if not funds:
        raise HTTPException(status_code=404, detail="No suitable funds found")
    return funds


@router.get("/health")
def health():
    data = engine.rankings.get()
    return {
        "status": "ok",
        "data_as_of": data.get("nav_date"),
        "generated_at": data.get("generated_at"),
        "funds_ranked": sum(len(b["funds"]) for b in data["buckets"].values()),
        "accounts_enabled": accounts_enabled(),
    }


@router.get("/categories")
def categories():
    """Category medians, so the UI can explain what 'good' looks like in each bucket."""
    data = engine.rankings.get()
    return [
        {"key": k, "label": BUCKETS[k].label, "sleeve": BUCKETS[k].sleeve, "risk_level": BUCKETS[k].risk_level,
         **data["buckets"].get(k, {}).get("stats", {})}
        for k in BUCKETS
    ]
