from fastapi import APIRouter
from datetime import datetime

from app.use_cases.bcd_service import get_bcd_service
from app.use_cases.ai_service import get_ai_service

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "2.1",
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

@router.get("/cache_info")
async def cache_info():
    """Returns training cache state of all ML models"""
    
    bcd_info = get_bcd_service().cache_info()
    mlp_info = get_ai_service().cache_info()
    
    return {
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "models": {
            "layer1_bcd": bcd_info,
            "layer3_mlp": mlp_info
        }
    }
