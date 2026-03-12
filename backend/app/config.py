from pydantic_settings import BaseSettings
from pathlib import Path
import json


class Settings(BaseSettings):
    db_path: str = str(Path(__file__).parent.parent / "app" / "infrastructure" / "database" / "btc-quant.db")
    cors_origins: list[str] = ["*"] # Allow all for Docker deployment
    ohlcv_limit: int = 150   # Naik dari 100: setelah dropna rolling-20, ~129 baris valid
                               # vs ~79 sebelumnya — jauh lebih stabil untuk 4 state × 5 fitur
    log_level: str = "INFO"

    # LLM provider config
    moonshot_api_key: str = ""
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"
    llm_provider: str = "auto"

    # Telegram Bot Config (existing — signal notifications)
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Telegram Bot Config (NEW — execution layer notifications)
    execution_telegram_bot_token: str = ""
    execution_telegram_chat_id: str = ""

    # ========== EXECUTION LAYER CONFIG (NEW) ==========
    # Binance API Credentials
    binance_testnet_api_key: str = ""
    binance_testnet_secret: str = ""
    binance_live_api_key: str = ""
    binance_live_secret: str = ""

    # Execution Mode & Safety
    execution_mode: str = "testnet"  # testnet | live
    trading_enabled: bool = False    # CRITICAL: safety flag

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
