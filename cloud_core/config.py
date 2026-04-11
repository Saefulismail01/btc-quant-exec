"""
Core Configuration for Cloud Testing
"""
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    # Exchange
    EXCHANGE_ID: str = "binance"
    SYMBOL: str = "BTC/USDT"
    TIMEFRAME: str = "4h"
    
    # API Keys (load from env)
    BINANCE_API_KEY: str = ""
    BINANCE_SECRET: str = ""
    
    # Telegram
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    
    # Lighter (if using)
    LIGHTER_API_KEY: str = ""
    LIGHTER_PRIVATE_KEY: str = ""
    
    # Risk
    MAX_POSITION_SIZE_USDT: float = 100.0
    LEVERAGE: int = 15
    DEFAULT_SL_PCT: float = 1.5
    DEFAULT_TP_PCT: float = 3.0
    
    # Signal Thresholds
    ACTIVE_THRESHOLD: float = 0.20  # |score| >= 0.20 = ACTIVE
    ADVISORY_DISABLED: bool = False
    
    # Data
    DB_PATH: str = "./data/btc-quant.db"
    MIN_ROWS_FOR_MLP: int = 60
    
    @classmethod
    def from_env(cls) -> "Config":
        """Load config from environment variables."""
        return cls(
            BINANCE_API_KEY=os.getenv("BINANCE_API_KEY", ""),
            BINANCE_SECRET=os.getenv("BINANCE_SECRET", ""),
            TELEGRAM_BOT_TOKEN=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            TELEGRAM_CHAT_ID=os.getenv("TELEGRAM_CHAT_ID", ""),
            LIGHTER_API_KEY=os.getenv("LIGHTER_API_KEY", ""),
            LIGHTER_PRIVATE_KEY=os.getenv("LIGHTER_PRIVATE_KEY", ""),
            MAX_POSITION_SIZE_USDT=float(os.getenv("MAX_POSITION_SIZE_USDT", "100")),
            LEVERAGE=int(os.getenv("LEVERAGE", "15")),
        )


# Global config instance
settings = Config.from_env()
