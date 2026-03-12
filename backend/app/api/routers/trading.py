from fastapi import APIRouter, Depends
from typing import Dict, Any, List
from app.use_cases.paper_trade_service import get_paper_trade_service, PaperTradeService
from app.adapters.repositories.market_repository import get_market_repository as get_repo, MarketRepository as DuckDBRepository

router = APIRouter(tags=["Paper Trading"])

@router.get("/trading/status")
async def get_trading_status(
    paper_svc: PaperTradeService = Depends(get_paper_trade_service)
):
    """Get summarized account performance."""
    acc = paper_svc.get_account()
    pos = paper_svc.get_open_position()
    return {
        "account": acc,
        "active_position": pos
    }

@router.get("/trading/history")
async def get_trading_history(
    repo: DuckDBRepository = Depends(get_repo)
):
    """Get trade history."""
    df = repo.get_trade_history(limit=50)
    return df.to_dict(orient="records")

@router.post("/trading/reset")
async def reset_trading_account(
    paper_svc: PaperTradeService = Depends(get_paper_trade_service)
):
    """Reset the paper trading account to $10,000."""
    paper_svc.reset_account()
    return {"message": "Paper account reset successfully."}
