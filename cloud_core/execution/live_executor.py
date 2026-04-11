"""
Live Trading Executor - Real trades via exchange API
"""
import os
from typing import Dict, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class LivePosition:
    """Live trading position."""
    symbol: str
    side: str
    entry_price: float
    size_usdt: float
    leverage: int
    order_id: str
    timestamp: datetime


class LiveExecutor:
    """
    Live trading executor using exchange API.
    Currently supports Binance Futures.
    """
    
    def __init__(self):
        self.exchange = None
        self._init_exchange()
    
    def _init_exchange(self):
        """Initialize exchange connection."""
        try:
            import ccxt
            
            api_key = os.getenv("BINANCE_API_KEY", "")
            secret = os.getenv("BINANCE_SECRET", "")
            
            if not api_key or not secret:
                print("[LiveExecutor] Warning: API keys not set")
                return
            
            self.exchange = ccxt.binance({
                "apiKey": api_key,
                "secret": secret,
                "enableRateLimit": True,
                "options": {
                    "defaultType": "future",
                }
            })
            
            print("[LiveExecutor] Exchange initialized")
            
        except Exception as e:
            print(f"[LiveExecutor] Init error: {e}")
            self.exchange = None
    
    def create_order(
        self,
        symbol: str,
        side: str,  # "buy" or "sell"
        order_type: str,  # "market" or "limit"
        amount: float,
        price: Optional[float] = None,
    ) -> Optional[Dict]:
        """
        Create order on exchange.
        
        Args:
            symbol: Trading pair
            side: buy or sell
            order_type: market or limit
            amount: Order size
            price: Limit price (for limit orders)
        
        Returns:
            Order dict or None if error
        """
        if not self.exchange:
            print("[LiveExecutor] Exchange not initialized")
            return None
        
        try:
            params = {}
            
            # Set leverage if needed
            # self.exchange.set_leverage(leverage, symbol)
            
            order = self.exchange.create_order(
                symbol=symbol,
                type=order_type,
                side=side,
                amount=amount,
                price=price,
                params=params,
            )
            
            print(f"[LiveExecutor] Order created: {order['id']}")
            return order
            
        except Exception as e:
            print(f"[LiveExecutor] Order error: {e}")
            return None
    
    def get_position(self, symbol: str) -> Optional[Dict]:
        """
        Get current position for symbol.
        
        Returns:
            Position dict or None if no position
        """
        if not self.exchange:
            return None
        
        try:
            positions = self.exchange.fetch_positions([symbol])
            
            for pos in positions:
                if float(pos.get("contracts", 0)) != 0:
                    return pos
            
            return None
            
        except Exception as e:
            print(f"[LiveExecutor] Get position error: {e}")
            return None
    
    def close_position(self, symbol: str) -> Optional[Dict]:
        """
        Close position for symbol.
        
        Returns:
            Order dict or None if error
        """
        if not self.exchange:
            return None
        
        try:
            position = self.get_position(symbol)
            
            if not position:
                print("[LiveExecutor] No position to close")
                return None
            
            side = "sell" if position["side"] == "long" else "buy"
            amount = abs(float(position["contracts"]))
            
            order = self.exchange.create_order(
                symbol=symbol,
                type="market",
                side=side,
                amount=amount,
                params={"reduceOnly": True},
            )
            
            print(f"[LiveExecutor] Position closed: {order['id']}")
            return order
            
        except Exception as e:
            print(f"[LiveExecutor] Close error: {e}")
            return None
    
    def get_balance(self) -> float:
        """Get USDT balance."""
        if not self.exchange:
            return 0.0
        
        try:
            balance = self.exchange.fetch_balance()
            return balance.get("USDT", {}).get("free", 0.0)
        except Exception as e:
            print(f"[LiveExecutor] Balance error: {e}")
            return 0.0
