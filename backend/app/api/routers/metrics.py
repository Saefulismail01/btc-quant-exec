from fastapi import APIRouter, HTTPException
from app.use_cases.signal_service import get_signal_service
from app.schemas.metrics import MetricsResponse

router = APIRouter(tags=["metrics"])


@router.get("/metrics", response_model=MetricsResponse)
async def get_metrics():
    """
    Raw market metrics: funding rate, open interest,
    order book imbalance, MCAP change, sentiment.
    """
    try:
        svc = get_signal_service()
        return svc.get_metrics()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Metrics fetch failed: {str(e)[:200]}")
