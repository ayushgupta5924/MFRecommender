from fastapi import APIRouter, HTTPException
from app.models.user import UserProfile, FundRecommendation, PortfolioRecommendation
from app.services.recommendation_engine import RecommendationEngine
from typing import List
import logging

logger = logging.getLogger(__name__)
router = APIRouter()
engine = RecommendationEngine()


@router.post("/recommend", response_model=List[FundRecommendation])
async def get_recommendations(profile: UserProfile):
    """Backward-compatible endpoint — returns flat fund list."""
    try:
        logger.info(f"recommend: life_stage={profile.life_stage}, goal={profile.goal}, risk={profile.risk_tolerance}")
        funds = engine.get_recommendations(profile)
        if not funds:
            raise HTTPException(status_code=404, detail="No suitable funds found")
        return funds
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in /recommend: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/portfolio", response_model=PortfolioRecommendation)
async def get_portfolio(profile: UserProfile):
    """New endpoint — returns named portfolio with SIP math."""
    try:
        logger.info(f"portfolio: life_stage={profile.life_stage}, goal={profile.goal}, target={profile.target_amount}")
        portfolio = engine.get_portfolio(profile)
        return portfolio
    except Exception as e:
        logger.error(f"Error in /portfolio: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/schemes")
async def get_all_schemes():
    try:
        return engine.mf_service.get_all_schemes()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scheme/{scheme_code}")
async def get_scheme_details(scheme_code: str):
    try:
        details = engine.mf_service.get_scheme_details(scheme_code)
        if not details:
            raise HTTPException(status_code=404, detail="Scheme not found")
        return details
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))