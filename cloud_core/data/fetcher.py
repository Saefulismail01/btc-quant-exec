"""
Data Fetcher - Get OHLCV from Binance
"""
import pandas as pd
import ccxt
from typing import Optional, Dict
import os


class DataFetcher:
    """
    Fetch OHLCV data from Binance (or other exchanges).
    """
    
    def __init__(self, exchange_id: str = "binance"):
        self.exchange_id = exchange_id
        self.exchange = None
        self._init_exchange()
    
    def _init_exchange(self):
        """Initialize CCXT exchange."""
        try:
            api_key = os.getenv("BINANCE_API_KEY", "")
            secret = os.getenv("BINANCE_SECRET", "")
            
            self.exchange = getattr(ccxt, self.exchange_id)({
                "apiKey": api_key,
                "secret": secret,
                "enableRateLimit": True,
                "options": {
                    "defaultType": "future",  # Use futures
                }
            })
        except Exception as e:
            print(f"[DataFetcher] Exchange init error: {e}")
            self.exchange = None
    
    def fetch_ohlcv(
        self,
        symbol: str = "BTC/USDT",
        timeframe: str = "4h",
        limit: int = 500,
    ) -> Optional[pd.DataFrame]:
        """
        Fetch OHLCV candles.
        
        Args:
            symbol: Trading pair
            timeframe: Candle timeframe (1m, 5m, 15m, 1h, 4h, 1d)
            limit: Number of candles
        
        Returns:
            DataFrame with columns: [Timestamp, Open, High, Low, Close, Volume]
        """
        if not self.exchange:
            print("[DataFetcher] Exchange not initialized")
            return None
        
        try:
            print(f"[DataFetcher] Fetching {limit} {timeframe} candles for {symbol}")
            
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            
            if not ohlcv or len(ohlcv) == 0:
                print("[DataFetcher] No data returned")
                return None
            
            df = pd.DataFrame(
                ohlcv,
                columns=["Timestamp", "Open", "High", "Low", "Close", "Volume"]
            )
            
            # Convert timestamp
            df["Timestamp"] = pd.to_datetime(df["Timestamp"], unit="ms")
            df.set_index("Timestamp", inplace=True)
            
            print(f"[DataFetcher] Fetched {len(df)} candles from {df.index[0]} to {df.index[-1]}")
            
            return df
            
        except Exception as e:
            print(f"[DataFetcher] Fetch error: {e}")
            return None
    
    def fetch_with_indicators(
        self,
        symbol: str = "BTC/USDT",
        timeframe: str = "4h",
        limit: int = 500,
    ) -> Optional[pd.DataFrame]:
        """
        Fetch OHLCV with basic indicators added.
        """
        import pandas_ta as ta
        
        df = self.fetch_ohlcv(symbol, timeframe, limit)
        if df is None:
            return None
        
        # Add basic indicators
        df["RSI_14"] = ta.rsi(df["Close"], length=14)
        df["EMA_20"] = ta.ema(df["Close"], length=20)
        df["EMA_50"] = ta.ema(df["Close"], length=50)
        
        return df
    
    def get_latest_price(self, symbol: str = "BTC/USDT") -> Optional[float]:
        """Get latest ticker price."""
        if not self.exchange:
            return None
        
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return ticker.get("last")
        except Exception as e:
            print(f"[DataFetcher] Price fetch error: {e}")
            return None
