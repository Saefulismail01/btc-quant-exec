"""
╔══════════════════════════════════════════════════════════════╗
║  BTC-QUANT: DATA INGESTION ENGINE (CLEAN FACADE)             ║
║  Transitioning to: app/use_cases/data_ingestion_use_case.py  ║
╚══════════════════════════════════════════════════════════════╝
"""

import asyncio
import os
import time
from pathlib import Path
from dotenv import load_dotenv

# NEW IMPORTS (Clean Architecture)
from app.adapters.repositories.market_repository import MarketRepository as DuckDBManager
from app.adapters.gateways.binance_gateway import BinanceGateway as CryptoDataFetcher
from app.use_cases.data_ingestion_use_case import start_data_daemon as _run_data_pipeline

def run_data_pipeline():
    """Facade for Clean Data Ingestion Daemon."""
    asyncio.run(_run_data_pipeline(interval=60))

def get_latest_market_data():
    """Facade for Streamlit Bridge."""
    repo = DuckDBManager()
    df = repo.get_latest_ohlcv(limit=500)
    metrics = repo.get_latest_metrics()
    return df, metrics

def _log(source: str, message: str):
    """Timestamped terminal log in clean format."""
    ts = time.strftime("%H:%M:%S")
    print(f"  [{ts}] [{source:>8}]  {message}")

if __name__ == "__main__":
    run_data_pipeline()
