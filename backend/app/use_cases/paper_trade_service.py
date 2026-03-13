"""
Paper Trade Service — Virtual execution layer for BTC-QUANT.
Manages account balance, positions, and SL/TP triggering.
"""
import uuid
import time
import logging
import duckdb
import pandas as pd
from typing import Optional, Dict, Any
from app.config import settings
from app.schemas.signal import SignalResponse
from app.adapters.repositories.market_repository import get_market_repository as get_repo

logger = logging.getLogger(__name__)

class PaperTradeService:
    def __init__(self, db_path: str = settings.db_path):
        self.db_path = db_path
        # Trigger repository initialization to ensure tables exist
        get_repo()

    def _nan_to_none(self, val: Any) -> Any:
        """Standardize NaN to None for JSON compliance."""
        import math
        if isinstance(val, float) and math.isnan(val):
            return None
        return val

    def get_account(self) -> Dict[str, Any]:
        """Fetch account status (balance, equity)."""
        with duckdb.connect(self.db_path, read_only=True) as con:
            row = con.execute("SELECT balance, equity, last_update FROM paper_account WHERE id = 1").fetchone()
        
        if not row:
            return {"balance": 10000.0, "equity": 10000.0, "last_update": 0}
            
        return {
            "balance": float(row[0]),
            "equity": float(row[1]),
            "last_update": int(row[2])
        }

    def get_open_position(self) -> Optional[Dict[str, Any]]:
        """Fetch the current OPEN position if it exists."""
        with duckdb.connect(self.db_path, read_only=True) as con:
            df = con.execute("SELECT * FROM paper_trades WHERE status = 'OPEN'").fetchdf()
        
        if df.empty:
            return None
            
        row = df.iloc[0]
        # Ensure standard Python types for JSON serialization (FastAPI reliability)
        return {
            "id":          str(row["id"]),
            "timestamp":   int(row["timestamp"]),
            "symbol":      str(row["symbol"]),
            "side":        str(row["side"]),
            "entry_price": self._nan_to_none(float(row["entry_price"])),
            "exit_price":  self._nan_to_none(float(row["exit_price"])) if row["exit_price"] is not None else None,
            "size_base":   self._nan_to_none(float(row["size_base"])),
            "size_quote":  self._nan_to_none(float(row["size_quote"])),
            "sl":          self._nan_to_none(float(row["sl"])),
            "tp":          self._nan_to_none(float(row["tp"])),
            "status":      str(row["status"]),
            "pnl":         self._nan_to_none(float(row["pnl"])),
            "pnl_pct":     self._nan_to_none(float(row["pnl_pct"]))
        }

    def process_signal(self, signal: SignalResponse):
        """
        Main logic for paper execution. 
        - If active signal and no position: OPEN.
        - If position exists: Check for SL/TP exit.
        """
        if signal.is_fallback:
            return

        current_pos = self.get_open_position()
        price = signal.price.now

        # 1. Existing Position Management
        if current_pos:
            self._check_exit_conditions(current_pos, price, signal.timestamp)
            return

        # 2. Logic to Open New Position
        # Only enter if status is ACTIVE and conviction is relevant
        if signal.trade_plan.status == "ACTIVE":
            self._open_position(signal)

    def _open_position(self, signal: SignalResponse):
        """Execute a virtual entry."""
        acc = self.get_account()
        price = signal.price.now
        tp1 = signal.trade_plan.tp1
        sl = signal.trade_plan.sl
        side = signal.trade_plan.action
        
        # Risk management: use 5% of balance per trade as default, 
        # or use the SPECTUM-derived position_size_pct
        risk_pct = signal.trade_plan.position_size_pct if signal.trade_plan.position_size_pct > 0 else 5.0
        # Sanity cap at 20%
        risk_pct = min(risk_pct, 20.0)
        
        risk_amount = acc["balance"] * (risk_pct / 100.0)
        # Assuming 10x leverage as a standard quantitative test multiplier
        leverage = signal.trade_plan.leverage or 10
        
        # Size in Quote (USDT)
        size_quote = risk_amount * leverage
        size_base = size_quote / price
        
        trade_id = f"virtual_{uuid.uuid4().hex[:8]}"
        ts = int(time.time() * 1000)
        
        with duckdb.connect(self.db_path) as con:
            con.execute("""
                INSERT INTO paper_trades 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                trade_id, ts, "BTC/USDT", side, price, None, 
                size_base, size_quote, sl, tp1, "OPEN", 0.0, 0.0
            ])
            # Update balance (remove margin used)
            # Actually, in perp paper trading we just track balance + unrealized pnl
            # We don't deduct the margin from balance usually, we deduct from buying power.
            # But let's stay simple: balance is static until close.
            
        logger.info(f" [PAPER] OPEN {side} @ {price} | Size: {size_quote:.2f} USDT | SL: {sl} | TP: {tp1}")

    def _check_exit_conditions(self, pos: Dict[str, Any], current_price: float, current_ts: str):
        """Check Sl/TP and close if hit."""
        side = pos["side"]
        entry = pos["entry_price"]
        sl = pos["sl"]
        tp = pos["tp"]
        size_base = pos["size_base"]
        size_quote = pos["size_quote"]
        
        exit_triggered = False
        exit_type = ""
        
        if side == "LONG":
            if current_price <= sl:
                exit_triggered = True
                exit_type = "SL"
            elif current_price >= tp:
                exit_triggered = True
                exit_type = "TP"
        else: # SHORT
            if current_price >= sl:
                exit_triggered = True
                exit_type = "SL"
            elif current_price <= tp:
                exit_triggered = True
                exit_type = "TP"
                
        if exit_triggered:
            self._close_position(pos, current_price, exit_type)

    def _close_position(self, pos: Dict[str, Any], exit_price: float, exit_type: str):
        """Calculate PnL and update account."""
        side = pos["side"]
        entry = pos["entry_price"]
        size_base = pos["size_base"]
        
        # PnL Calculation
        if side == "LONG":
            pnl = (exit_price - entry) * size_base
        else:
            pnl = (entry - exit_price) * size_base
            
        pnl_pct = (pnl / pos["size_quote"]) * 100 if pos["size_quote"] != 0 else 0
        
        acc = self.get_account()
        new_balance = acc["balance"] + pnl
        ts = int(time.time() * 1000)
        
        with duckdb.connect(self.db_path) as con:
            con.execute("UPDATE paper_trades SET exit_price = ?, status = 'CLOSED', pnl = ?, pnl_pct = ? WHERE id = ?", 
                        [exit_price, pnl, pnl_pct, pos["id"]])
            con.execute("UPDATE paper_account SET balance = ?, equity = ?, last_update = ? WHERE id = 1",
                        [new_balance, new_balance, ts])
            
        logger.info(f" [PAPER] CLOSE {side} @ {exit_price} | Exit: {exit_type} | PnL: {pnl:.2f} USDT ({pnl_pct:.2f}%)")

    def close_all_positions(self, current_price: Optional[float] = None) -> int:
        """
        Close all open positions at market price.

        Used for graceful shutdown to ensure no positions are left open.

        Args:
            current_price: Current market price. If None, uses last entry price as reference.

        Returns:
            Number of positions closed
        """
        with duckdb.connect(self.db_path) as con:
            open_trades = con.execute(
                "SELECT * FROM paper_trades WHERE status = 'OPEN'"
            ).fetchdf()

        if open_trades.empty:
            logger.info("[PAPER] No open positions to close")
            return 0

        closed_count: int = 0
        for _, trade in open_trades.iterrows():
            entry: float = float(trade["entry_price"])
            if current_price is not None:
                exit_price: float = float(current_price)
            else:
                exit_price = entry
            exit_type: str = "MANUAL_SHUTDOWN"

            try:
                self._close_position(
                    {
                        "id": str(trade["id"]),
                        "side": str(trade["side"]),
                        "entry_price": entry,
                        "size_quote": float(trade["size_quote"]),
                    },
                    exit_price=exit_price,
                    exit_type=exit_type
                )
                closed_count = closed_count + 1
            except Exception as e:
                logger.error(f"[PAPER] Failed to close position {trade['id']}: {e}")

        if closed_count > 0:
            logger.info(f"[PAPER] Closed {closed_count} position(s) during shutdown")
        return closed_count

    def reset_account(self, initial_balance: float = 10000.0):
        """Reset virtual account."""
        ts = int(time.time() * 1000)
        with duckdb.connect(self.db_path) as con:
            con.execute("DELETE FROM paper_trades")
            con.execute("UPDATE paper_account SET balance = ?, equity = ?, last_update = ? WHERE id = 1",
                        [initial_balance, initial_balance, ts])
        logger.info(f"[PAPER] Account reset to {initial_balance} USDT")

_paper_svc = None

def get_paper_trade_service() -> PaperTradeService:
    global _paper_svc
    if _paper_svc is None:
        _paper_svc = PaperTradeService()
    return _paper_svc
