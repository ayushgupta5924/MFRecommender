from fastapi import APIRouter, HTTPException
from app.models.user import UserProfile, FundRecommendation
from app.services.recommendation_engine import RecommendationEngine
from typing import List
import logging
logger = logging.getLogger(__name__)
router = APIRouter()
engine = RecommendationEngine()

@router.post("/recommend", response_model=List[FundRecommendation])
async def get_recommendations(profile: UserProfile):
    try:
        logger.info(f"Received request: budget={profile.budget}, risk={profile.risk_tolerance}")
        recommendations = engine.get_recommendations(profile)
        if not recommendations:
            raise HTTPException(status_code=404, detail="No suitable funds found")
        logger.info(f"Returning {len(recommendations)} recommendations")
        return recommendations
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/schemes")
async def get_all_schemes():
    try:
        schemes = engine.mf_service.get_all_schemes()
        return schemes
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/scheme/{scheme_code}")
async def get_scheme_details(scheme_code: str):
    try:
        details = engine.mf_service.get_scheme_details(scheme_code)
        if not details:
            raise HTTPException(status_code=404, detail="Scheme not found")
        return details
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))