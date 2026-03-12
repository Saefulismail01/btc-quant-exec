from datetime import datetime
from fastapi import APIRouter, HTTPException
from app.use_cases.signal_service import get_signal_service
from app.schemas.signal import SignalResponse

router = APIRouter(tags=["signal"])


@router.get("/signal", response_model=SignalResponse)
async def get_signal():
    """
    Full signal intelligence report:
    price snapshot, trend, trade plan, confluence layers, volatility.
    """
    try:
        svc = get_signal_service()
        return svc.get_signal()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Signal computation failed: {str(e)[:200]}")


@router.get("/price")
async def get_live_price():
    """
    Extreme-latency: fetch live price directly from Binance (bypass DB)
    to update the UI in real-time.
    """
    from app.adapters.gateways.binance_gateway import BinanceGateway
    gw = BinanceGateway()
    try:
        price = await gw.fetch_live_price()
        return {"price": price, "timestamp": str(datetime.now())}
    finally:
        await gw.close()
