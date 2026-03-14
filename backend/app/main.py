"""
BTC-QUANT-BTC FastAPI Application Factory
"""
# ── Clean Architecture: imports are now absolute or relative ──
import sys
from pathlib import Path
_BACKEND = str(Path(__file__).resolve().parent.parent)
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)
# ─────────────────────────────────────────────────────────────────────────────
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.routers import health, signal, metrics, trading, execution


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Warm-up: instantiate model singletons once at startup, start data daemon."""
    import asyncio
    from app.use_cases.bcd_service import get_bcd_service
    from app.use_cases.ai_service import get_ai_service
    from app.use_cases.signal_service import get_signal_service
    from app.use_cases.data_ingestion_use_case import start_data_daemon

    get_bcd_service()
    get_ai_service()
    get_signal_service()

    # Start data daemon in the same event loop as the server
    data_task = asyncio.create_task(start_data_daemon(interval=60))
    print("[API] Data ingestion daemon started")

    yield

    # Graceful shutdown: cancel the data daemon task
    data_task.cancel()
    try:
        await data_task
    except asyncio.CancelledError:
        print("[API] Data ingestion daemon stopped")


app = FastAPI(
    title="BTC-QUANT-BTC Signal Intelligence API",
    version="2.1",
    description="Quantitative scalping signal intelligence for BTC/USDT perpetual.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(health.router,    prefix="/api")
app.include_router(signal.router,    prefix="/api")
app.include_router(metrics.router,   prefix="/api")
app.include_router(trading.router,   prefix="/api")
app.include_router(execution.router)
