"""
Paper Trading Executor - Simulated trading without real money
"""
import pandas as pd
from typing import Dict, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import json


@dataclass
class PaperPosition:
    """Paper trading position."""
    id: str
    symbol: str
    side: str  # LONG / SHORT
    entry_price: float
    size_usdt: float
    leverage: int
    sl_price: float
    tp_price: float
    timestamp_open: datetime
    pnl_usdt: float = 0.0
    pnl_pct: float = 0.0
    is_open: bool = True
    timestamp_close: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None


class PaperExecutor:
    """
    Paper trading executor for backtesting and simulation.
    Tracks PnL without real trades.
    """
    
    def __init__(self, initial_balance: float = 10000.0, save_path: Optional[str] = None):
        self.balance = initial_balance
        self.initial_balance = initial_balance
        self.positions: List[PaperPosition] = []
        self.open_position: Optional[PaperPosition] = None
        self.save_path = Path(save_path) if save_path else None
        
        # Stats
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        
        # Load state if exists
        self._load_state()
    
    def open_position(
        self,
        symbol: str,
        side: str,
        price: float,
        size_usdt: float,
        leverage: int,
        sl_price: float,
        tp_price: float,
    ) -> Optional[PaperPosition]:
        """
        Open a paper position.
        
        Returns:
            PaperPosition or None if already has open position
        """
        if self.open_position is not None:
            print(f"[PaperExecutor] Position already open: {self.open_position.side}")
            return None
        
        if size_usdt > self.balance:
            print(f"[PaperExecutor] Insufficient balance: {self.balance} < {size_usdt}")
            return None
        
        pos = PaperPosition(
            id=f"paper_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            symbol=symbol,
            side=side,
            entry_price=price,
            size_usdt=size_usdt,
            leverage=leverage,
            sl_price=sl_price,
            tp_price=tp_price,
            timestamp_open=datetime.utcnow(),
        )
        
        self.positions.append(pos)
        self.open_position = pos
        self.balance -= size_usdt  # Reserve margin
        
        print(f"[PaperExecutor] OPEN {side} @ {price:,.0f} | Size: ${size_usdt} | Leverage: {leverage}x")
        
        self._save_state()
        return pos
    
    def close_position(
        self,
        price: float,
        reason: str = "manual",
    ) -> Optional[PaperPosition]:
        """
        Close open position.
        
        Returns:
            Closed PaperPosition or None if no open position
        """
        if self.open_position is None:
            print("[PaperExecutor] No open position to close")
            return None
        
        pos = self.open_position
        
        # Calculate PnL
        if pos.side == "LONG":
            pnl_pct = (price - pos.entry_price) / pos.entry_price * 100 * pos.leverage
        else:
            pnl_pct = (pos.entry_price - price) / pos.entry_price * 100 * pos.leverage
        
        pnl_usdt = pos.size_usdt * (pnl_pct / 100)
        
        # Update position
        pos.pnl_usdt = pnl_usdt
        pos.pnl_pct = pnl_pct
        pos.is_open = False
        pos.timestamp_close = datetime.utcnow()
        pos.exit_price = price
        pos.exit_reason = reason
        
        # Update balance
        self.balance += pos.size_usdt + pnl_usdt
        
        # Stats
        self.total_trades += 1
        if pnl_usdt > 0:
            self.winning_trades += 1
        else:
            self.losing_trades += 1
        
        print(f"[PaperExecutor] CLOSE @ {price:,.0f} | PnL: ${pnl_usdt:+.2f} ({pnl_pct:+.2f}%) | Reason: {reason}")
        
        self.open_position = None
        self._save_state()
        return pos
    
    def check_sl_tp(self, current_price: float) -> Optional[str]:
        """
        Check if SL or TP hit.
        
        Returns:
            "SL", "TP", or None
        """
        if self.open_position is None:
            return None
        
        pos = self.open_position
        
        if pos.side == "LONG":
            if current_price <= pos.sl_price:
                return "SL"
            if current_price >= pos.tp_price:
                return "TP"
        else:  # SHORT
            if current_price >= pos.sl_price:
                return "SL"
            if current_price <= pos.tp_price:
                return "TP"
        
        return None
    
    def update(self, current_price: float) -> Optional[PaperPosition]:
        """
        Update position with current price.
        Check SL/TP and auto-close if hit.
        
        Returns:
            Closed position if SL/TP hit, else None
        """
        exit_reason = self.check_sl_tp(current_price)
        
        if exit_reason:
            return self.close_position(current_price, exit_reason)
        
        return None
    
    def get_stats(self) -> Dict:
        """Get trading statistics."""
        total_return = (self.balance - self.initial_balance) / self.initial_balance * 100
        
        win_rate = 0.0
        if self.total_trades > 0:
            win_rate = self.winning_trades / self.total_trades * 100
        
        # Calculate PnL from closed positions
        total_pnl = sum(p.pnl_usdt for p in self.positions if not p.is_open)
        
        return {
            "initial_balance": self.initial_balance,
            "current_balance": round(self.balance, 2),
            "total_pnl": round(total_pnl, 2),
            "total_return_pct": round(total_return, 2),
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate_pct": round(win_rate, 1),
            "open_position": self.open_position is not None,
        }
    
    def _save_state(self):
        """Save state to disk."""
        if not self.save_path:
            return
        
        try:
            self.save_path.parent.mkdir(parents=True, exist_ok=True)
            
            state = {
                "balance": self.balance,
                "total_trades": self.total_trades,
                "winning_trades": self.winning_trades,
                "losing_trades": self.losing_trades,
                "positions": [
                    {
                        "id": p.id,
                        "symbol": p.symbol,
                        "side": p.side,
                        "entry_price": p.entry_price,
                        "size_usdt": p.size_usdt,
                        "leverage": p.leverage,
                        "sl_price": p.sl_price,
                        "tp_price": p.tp_price,
                        "pnl_usdt": p.pnl_usdt,
                        "pnl_pct": p.pnl_pct,
                        "is_open": p.is_open,
                        "timestamp_open": p.timestamp_open.isoformat(),
                        "timestamp_close": p.timestamp_close.isoformat() if p.timestamp_close else None,
                        "exit_price": p.exit_price,
                        "exit_reason": p.exit_reason,
                    }
                    for p in self.positions
                ],
            }
            
            with open(self.save_path, "w") as f:
                json.dump(state, f, indent=2)
                
        except Exception as e:
            print(f"[PaperExecutor] Save error: {e}")
    
    def _load_state(self):
        """Load state from disk."""
        if not self.save_path or not self.save_path.exists():
            return
        
        try:
            with open(self.save_path, "r") as f:
                state = json.load(f)
            
            self.balance = state.get("balance", self.initial_balance)
            self.total_trades = state.get("total_trades", 0)
            self.winning_trades = state.get("winning_trades", 0)
            self.losing_trades = state.get("losing_trades", 0)
            
            # Restore positions
            for p_data in state.get("positions", []):
                pos = PaperPosition(
                    id=p_data["id"],
                    symbol=p_data["symbol"],
                    side=p_data["side"],
                    entry_price=p_data["entry_price"],
                    size_usdt=p_data["size_usdt"],
                    leverage=p_data["leverage"],
                    sl_price=p_data["sl_price"],
                    tp_price=p_data["tp_price"],
                    timestamp_open=datetime.fromisoformat(p_data["timestamp_open"]),
                    pnl_usdt=p_data.get("pnl_usdt", 0.0),
                    pnl_pct=p_data.get("pnl_pct", 0.0),
                    is_open=p_data.get("is_open", False),
                    timestamp_close=datetime.fromisoformat(p_data["timestamp_close"]) if p_data.get("timestamp_close") else None,
                    exit_price=p_data.get("exit_price"),
                    exit_reason=p_data.get("exit_reason"),
                )
                
                self.positions.append(pos)
                if pos.is_open:
                    self.open_position = pos
            
            print(f"[PaperExecutor] Loaded {len(self.positions)} positions from disk")
            
        except Exception as e:
            print(f"[PaperExecutor] Load error: {e}")
    
    def print_summary(self):
        """Print trading summary."""
        stats = self.get_stats()
        
        print("\n" + "=" * 50)
        print("PAPER TRADING SUMMARY")
        print("=" * 50)
        print(f"Initial Balance: ${stats['initial_balance']:,.2f}")
        print(f"Current Balance: ${stats['current_balance']:,.2f}")
        print(f"Total PnL: ${stats['total_pnl']:+,.2f}")
        print(f"Total Return: {stats['total_return_pct']:+.2f}%")
        print(f"-" * 50)
        print(f"Total Trades: {stats['total_trades']}")
        print(f"Winning: {stats['winning_trades']}")
        print(f"Losing: {stats['losing_trades']}")
        print(f"Win Rate: {stats['win_rate_pct']:.1f}%")
        print(f"Open Position: {stats['open_position']}")
        print("=" * 50)
