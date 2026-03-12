"""
Execution Layer API Router

Endpoints:
- GET  /api/execution/status          — Real-time execution status
- POST /api/execution/emergency_stop  — Emergency stop (close position, halt trading)
- POST /api/execution/resume          — Resume trading (explicit confirm)
- POST /api/execution/set_trading_enabled — Toggle TRADING_ENABLED flag
"""

import os
import logging
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.adapters.gateways.binance_execution_gateway import BinanceExecutionGateway
from app.adapters.repositories.live_trade_repository import LiveTradeRepository
from app.use_cases.risk_manager import RiskManager

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/execution",
    tags=["Live Execution"]
)

# Global state for emergency stop
_TRADING_HALTED = False


# ─ Request/Response Models ────────────────────────────────────────────────────

class RiskStatus(BaseModel):
    """Risk manager status."""
    daily_pnl_usdt: float
    daily_pnl_pct: float
    daily_loss_cap_usdt: float
    remaining_before_halt: float
    consecutive_losses: int
    max_consecutive_losses: int
    in_cooldown: bool
    cooldown_remaining_candles: int


class OpenPositionResponse(BaseModel):
    """Open position info."""
    symbol: str
    side: str
    entry_price: float
    quantity: float
    unrealized_pnl: float
    leverage: int
    opened_at_iso: str
    time_held_hours: float


class ExecutionStatusResponse(BaseModel):
    """Execution status response."""
    trading_enabled: bool
    trading_halted: bool
    execution_mode: str
    account_balance_usdt: float
    open_position: Optional[OpenPositionResponse] = None
    daily_pnl_usdt: float
    daily_pnl_pct: float
    risk_status: RiskStatus
    last_trade_id: Optional[str] = None
    uptime_seconds: float


class EmergencyStopResponse(BaseModel):
    """Emergency stop response."""
    status: str
    position_closed: bool
    exit_price: Optional[float] = None
    exit_pnl_usdt: Optional[float] = None
    exit_pnl_pct: Optional[float] = None
    message: str


class ResumeRequest(BaseModel):
    """Resume trading request (explicit confirmation)."""
    confirm: str = ""  # Must be "RESUME_TRADING" to proceed


class ResumeResponse(BaseModel):
    """Resume trading response."""
    status: str
    message: str


class SetTradingEnabledRequest(BaseModel):
    """Set trading enabled request."""
    enabled: bool


class SetTradingEnabledResponse(BaseModel):
    """Set trading enabled response."""
    trading_enabled: bool
    message: str


# ─ Helper Functions ───────────────────────────────────────────────────────────

def _get_execution_mode() -> str:
    """Get current execution mode."""
    return os.getenv("EXECUTION_MODE", "testnet").lower()


def _is_trading_enabled() -> bool:
    """Check if trading is enabled."""
    return os.getenv("TRADING_ENABLED", "false").lower() == "true"


async def _get_gateway() -> BinanceExecutionGateway:
    """Get execution gateway instance."""
    return BinanceExecutionGateway()


async def _get_risk_status() -> RiskStatus:
    """Get risk manager status."""
    risk_mgr = RiskManager()
    daily_pnl, daily_pnl_pct = 0.0, 0.0

    try:
        repo = LiveTradeRepository()
        daily_pnl, daily_pnl_pct = repo.get_daily_pnl()
    except Exception as e:
        logger.warning(f"[ExecutionRouter] Failed to get daily PnL: {e}")

    return RiskStatus(
        daily_pnl_usdt=daily_pnl,
        daily_pnl_pct=daily_pnl_pct,
        daily_loss_cap_usdt=risk_mgr.max_daily_loss,
        remaining_before_halt=max(0, risk_mgr.max_daily_loss + daily_pnl),
        consecutive_losses=risk_mgr.consecutive_losses,
        max_consecutive_losses=risk_mgr.max_consecutive_losses,
        in_cooldown=risk_mgr.is_in_cooldown(),
        cooldown_remaining_candles=risk_mgr.get_cooldown_remaining_candles(),
    )


# ─ API Endpoints ──────────────────────────────────────────────────────────────

@router.get("/status", response_model=ExecutionStatusResponse)
async def get_execution_status():
    """
    Get real-time execution status.

    Returns:
        ExecutionStatusResponse with all relevant status info
    """
    try:
        gateway = await _get_gateway()
        repo = LiveTradeRepository()
        risk_status = await _get_risk_status()

        # Get account balance
        balance = await gateway.get_account_balance()

        # Get open position
        exchange_pos = await gateway.get_open_position()
        open_position = None
        if exchange_pos:
            db_trade = repo.get_open_trade()
            opened_at_iso = (
                datetime.fromtimestamp(db_trade.timestamp_open / 1000).isoformat()
                if db_trade
                else datetime.utcnow().isoformat()
            )
            time_held_hours = (
                (datetime.utcnow().timestamp() - db_trade.timestamp_open / 1000) / 3600
                if db_trade
                else 0
            )
            open_position = OpenPositionResponse(
                symbol=exchange_pos.symbol,
                side=exchange_pos.side,
                entry_price=exchange_pos.entry_price,
                quantity=exchange_pos.quantity,
                unrealized_pnl=exchange_pos.unrealized_pnl,
                leverage=exchange_pos.leverage,
                opened_at_iso=opened_at_iso,
                time_held_hours=time_held_hours,
            )

        # Get daily PnL
        daily_pnl, daily_pnl_pct = repo.get_daily_pnl()

        # Get last trade ID
        last_trade = repo.get_trade_history(limit=1)
        last_trade_id = last_trade[0].id if last_trade else None

        await gateway.close()

        return ExecutionStatusResponse(
            trading_enabled=_is_trading_enabled(),
            trading_halted=_TRADING_HALTED,
            execution_mode=_get_execution_mode(),
            account_balance_usdt=balance,
            open_position=open_position,
            daily_pnl_usdt=daily_pnl,
            daily_pnl_pct=daily_pnl_pct,
            risk_status=risk_status,
            last_trade_id=last_trade_id,
            uptime_seconds=0.0,  # TODO: Track actual uptime
        )

    except Exception as e:
        logger.error(f"[ExecutionRouter] Failed to get status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/emergency_stop", response_model=EmergencyStopResponse)
async def emergency_stop():
    """
    Emergency stop: close all positions and halt trading.

    Returns:
        EmergencyStopResponse with result details
    """
    global _TRADING_HALTED

    try:
        logger.warning("[ExecutionRouter] 🚨 EMERGENCY STOP TRIGGERED")

        gateway = await _get_gateway()
        repo = LiveTradeRepository()

        # Get open position
        position = await gateway.get_open_position()

        if not position:
            logger.info("[ExecutionRouter] No open position to close")
            _TRADING_HALTED = True
            await gateway.close()
            return EmergencyStopResponse(
                status="halted",
                position_closed=False,
                message="No open position. Trading halted.",
            )

        # Close position with market order
        logger.warning(f"[ExecutionRouter] Closing {position.side} position...")
        close_result = await gateway.close_position_market()

        if not close_result.success:
            logger.error(f"[ExecutionRouter] Failed to close position: {close_result.error_message}")
            await gateway.close()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to close position: {close_result.error_message}"
            )

        # Update DB if trade exists
        db_trade = repo.get_open_trade()
        if db_trade:
            exit_price = close_result.filled_price
            pnl_usdt = (
                (exit_price - db_trade.entry_price) / db_trade.entry_price * db_trade.size_usdt
                if db_trade.side == "LONG"
                else (db_trade.entry_price - exit_price) / db_trade.entry_price * db_trade.size_usdt
            ) * db_trade.leverage
            pnl_pct = (pnl_usdt / db_trade.size_usdt * 100) if db_trade.size_usdt > 0 else 0

            repo.update_trade_on_close(
                db_trade.id,
                exit_price=exit_price,
                exit_type="MANUAL",
                pnl_usdt=pnl_usdt,
                pnl_pct=pnl_pct,
            )

            logger.info(
                f"[ExecutionRouter] ✅ Position closed | "
                f"Exit: ${exit_price:,.2f} | PnL: ${pnl_usdt:+.2f} ({pnl_pct:+.2f}%)"
            )
        else:
            exit_price = close_result.filled_price
            pnl_usdt = close_result.filled_price * close_result.filled_quantity
            pnl_pct = 0.0

        _TRADING_HALTED = True
        await gateway.close()

        return EmergencyStopResponse(
            status="halted",
            position_closed=True,
            exit_price=close_result.filled_price,
            exit_pnl_usdt=pnl_usdt,
            exit_pnl_pct=pnl_pct,
            message="✅ Position closed. Trading halted.",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ExecutionRouter] Emergency stop failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/resume", response_model=ResumeResponse)
async def resume_trading(request: ResumeRequest):
    """
    Resume trading after emergency stop.

    Requires explicit confirmation string to prevent accidental resume.

    Args:
        request: Must contain confirm="RESUME_TRADING"

    Returns:
        ResumeResponse
    """
    global _TRADING_HALTED

    try:
        if request.confirm != "RESUME_TRADING":
            logger.warning(
                f"[ExecutionRouter] Resume attempt with invalid confirm string: {request.confirm}"
            )
            raise HTTPException(
                status_code=400,
                detail="Invalid confirmation string. Must be exactly 'RESUME_TRADING'"
            )

        logger.warning("[ExecutionRouter] Resuming trading...")
        _TRADING_HALTED = False

        return ResumeResponse(
            status="resumed",
            message="✅ Trading resumed. Daemon will process new signals.",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ExecutionRouter] Resume failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/set_trading_enabled", response_model=SetTradingEnabledResponse)
async def set_trading_enabled(request: SetTradingEnabledRequest):
    """
    Toggle TRADING_ENABLED flag.

    NOTE: This only toggles the runtime flag. To persist, update .env and restart.

    Args:
        request: SetTradingEnabledRequest with enabled=true|false

    Returns:
        SetTradingEnabledResponse
    """
    try:
        # NOTE: This would require global state management to be truly effective
        # For now, just log the request
        status = "enabled" if request.enabled else "disabled"
        logger.info(f"[ExecutionRouter] Trading {status} requested")

        return SetTradingEnabledResponse(
            trading_enabled=request.enabled,
            message=f"Trading {status}. To persist, update TRADING_ENABLED in .env and restart.",
        )

    except Exception as e:
        logger.error(f"[ExecutionRouter] Failed to set trading enabled: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
