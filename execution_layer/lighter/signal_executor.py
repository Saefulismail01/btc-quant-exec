#!/usr/bin/env python3
"""
BTC-QUANT v4.4 — 4H Signal-Based Execution Daemon

Reads cached signal from backend container every 4H and executes on Lighter mainnet.

Signal → Trade mapping:
  STRONG BUY/SELL  (ACTIVE)    → margin=$15, leverage=15x
  WEAK BUY/SELL    (ADVISORY)  → margin=$10, leverage=15x
  NEUTRAL                      → skip
  SUSPENDED                    → skip

SL/TP from signal.trade_plan.sl and signal.trade_plan.tp1 (Heston ATR-based).

Usage:
    python execution_layer/lighter/signal_executor.py

Environment:
    LIGHTER_EXECUTION_MODE=mainnet
    LIGHTER_TRADING_ENABLED=true
"""

import asyncio
import logging
import os
import sys
import time
import signal as sig_mod
from pathlib import Path
from datetime import datetime, timezone, timedelta
import json
from types import SimpleNamespace

# Path setup
root_path = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(root_path / "backend"))

from dotenv import load_dotenv
load_dotenv(root_path / ".env")

import lighter
import aiohttp

# ── Config ─────────────────────────────────────────────────────────────────────

BASE_URL = os.getenv("LIGHTER_MAINNET_BASE_URL", "https://mainnet.zklighter.elliot.ai")
API_SECRET = os.getenv("LIGHTER_MAINNET_API_SECRET", "")
if API_SECRET.startswith("0x"):
    API_SECRET = API_SECRET[2:]
API_KEY_INDEX = int(os.getenv("LIGHTER_API_KEY_INDEX", "3"))
ACCOUNT_INDEX = int(os.getenv("LIGHTER_ACCOUNT_INDEX", "718591"))
BTC_MARKET = 1
LEVERAGE = 15

# Margin per signal strength
MARGIN_ACTIVE = 15.0    # $15 for STRONG BUY/SELL
MARGIN_ADVISORY = 10.0  # $10 for WEAK BUY/SELL

# Slippage tolerance: 2% buffer to ensure fill
SLIPPAGE = 0.02

# Signal schedule: 03,07,11,15,19,23 WIB = 20,00,04,08,12,16 UTC
SIGNAL_HOURS_UTC = {20, 0, 4, 8, 12, 16}
# Extra wait after signal hour before reading (give pipeline 5min to finish)
SIGNAL_DELAY_MINUTES = 2

# Trading enabled flag
TRADING_ENABLED = os.getenv("LIGHTER_TRADING_ENABLED", "false").lower() == "true"

# ── Logging ────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Signal reading ─────────────────────────────────────────────────────────────

# Backend API endpoint (inside container: localhost:8000)
BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000/api/signal")

async def get_signal_from_api():
    """Fetch cached signal from backend HTTP API."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(BACKEND_API_URL, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data
                else:
                    logger.error(f"API returned {resp.status}")
                    return None
    except asyncio.TimeoutError:
        logger.error(f"API timeout fetching signal")
        return None
    except Exception as e:
        logger.error(f"Failed to get signal from API: {e}")
        return None


def parse_signal(signal) -> dict | None:
    """
    Parse signal into execution params.

    Returns dict with:
        action: LONG | SHORT
        margin: float
        sl: float (price)
        tp: float (price)
    Or None if signal should be skipped.
    """
    if signal is None or signal.is_fallback:
        logger.info("No signal or fallback signal — skip")
        return None

    verdict = signal.confluence.verdict
    status = signal.trade_plan.status

    logger.info(f"Signal: verdict={verdict}, status={status}, conviction={signal.confluence.conviction_pct:.1f}%")

    if status == "SUSPENDED":
        logger.info("Signal SUSPENDED — skip")
        return None

    if verdict in ("STRONG BUY", "STRONG SELL"):
        margin = MARGIN_ACTIVE
    elif verdict in ("WEAK BUY", "WEAK SELL"):
        margin = MARGIN_ADVISORY
    else:
        logger.info(f"Verdict {verdict} → skip")
        return None

    action = "LONG" if "BUY" in verdict else "SHORT"
    sl_price = signal.trade_plan.sl
    tp_price = signal.trade_plan.tp1

    if not sl_price or not tp_price or sl_price <= 0 or tp_price <= 0:
        logger.error(f"Invalid SL/TP from signal: SL={sl_price}, TP={tp_price}")
        return None

    return {
        "action": action,
        "margin": margin,
        "sl": float(sl_price),
        "tp": float(tp_price),
    }


# ── Price fetching ─────────────────────────────────────────────────────────────

async def get_current_price() -> float:
    """Fetch current BTC price from Lighter orderbook."""
    config = lighter.Configuration(host=BASE_URL)
    async with lighter.ApiClient(config) as api:
        order_api = lighter.OrderApi(api)
        book = await order_api.order_book_details(market_id=BTC_MARKET)
        return float(book.order_book_details[0].last_trade_price)


async def get_nonce() -> int:
    """Fetch current nonce from Lighter API."""
    config = lighter.Configuration(host=BASE_URL)
    async with lighter.ApiClient(config) as api:
        tx_api = lighter.TransactionApi(api)
        resp = await tx_api.next_nonce(
            account_index=ACCOUNT_INDEX, api_key_index=API_KEY_INDEX
        )
        return resp.nonce


async def get_open_position() -> dict | None:
    """Check if there's an open position."""
    config = lighter.Configuration(host=BASE_URL)
    async with lighter.ApiClient(config) as api:
        acc_api = lighter.AccountApi(api)
        r = await acc_api.account(by="index", value=str(ACCOUNT_INDEX))
        acc = r.accounts[0]
        if acc.positions and float(acc.positions[0].position) > 0:
            pos = acc.positions[0]
            return {
                "side": "LONG" if pos.sign == 1 else "SHORT",
                "size": float(pos.position),
                "entry": float(pos.avg_entry_price),
                "pnl": float(pos.unrealized_pnl),
                "tied_orders": pos.position_tied_order_count,
            }
        return None


async def get_balance() -> float:
    """Get account USDC balance."""
    config = lighter.Configuration(host=BASE_URL)
    async with lighter.ApiClient(config) as api:
        acc_api = lighter.AccountApi(api)
        r = await acc_api.account(by="index", value=str(ACCOUNT_INDEX))
        return float(r.accounts[0].collateral)


# ── Order execution ────────────────────────────────────────────────────────────

async def execute_trade(action: str, margin: float, sl_price: float, tp_price: float) -> bool:
    """
    Execute entry + SL + TP orders.

    Uses proven pattern:
    - Entry: market order with 2% slippage buffer
    - SL: STOP_LOSS_LIMIT, reduce_only
    - TP: TAKE_PROFIT_LIMIT, reduce_only
    - 3s delay between each order to avoid nonce conflict

    Returns True if entry succeeded.
    """
    if not TRADING_ENABLED:
        logger.warning("TRADING_ENABLED=false — DRY RUN only")
        return False

    current_price = await get_current_price()
    notional = margin * LEVERAGE
    # base_amount in units of 1e-5 BTC
    btc_qty = notional / current_price
    base_amount = int(btc_qty * 1e5)

    is_ask = (action == "SHORT")
    # Slippage: LONG uses higher price (1.02x), SHORT uses lower price (0.98x)
    avg_price = int(current_price * 10 * (0.98 if is_ask else 1.02))
    sl_scaled = int(sl_price * 10)
    tp_scaled = int(tp_price * 10)

    logger.info(
        f"[EXEC] {action} | margin=${margin} | leverage={LEVERAGE}x | "
        f"notional=${notional:.2f} | qty={btc_qty:.5f} BTC (base_amount={base_amount})"
    )
    logger.info(
        f"[EXEC] Entry ~${current_price:,.2f} | SL=${sl_price:,.2f} | TP=${tp_price:,.2f}"
    )

    nonce = await get_nonce()
    client = lighter.SignerClient(
        url=BASE_URL,
        account_index=ACCOUNT_INDEX,
        api_private_keys={API_KEY_INDEX: API_SECRET},
    )

    try:
        # ── 1. Entry order ─────────────────────────────────────────────────────
        _, resp, err = await client.create_market_order(
            market_index=BTC_MARKET,
            client_order_index=0,
            base_amount=base_amount,
            avg_execution_price=avg_price,
            is_ask=is_ask,
            nonce=nonce,
            api_key_index=API_KEY_INDEX,
        )
        if err:
            logger.error(f"[EXEC] Entry FAILED: {err}")
            return False
        logger.info(f"[EXEC] Entry OK | tx={getattr(resp, 'tx_hash', 'n/a')}")
        nonce += 1
        time.sleep(3)  # CRITICAL: wait for entry to settle

        # ── 2. Stop-loss order ─────────────────────────────────────────────────
        _, _, err_sl = await client.create_order(
            market_index=BTC_MARKET,
            client_order_index=1,
            base_amount=base_amount,
            price=sl_scaled,
            is_ask=(action == "LONG"),   # SL closes position (opposite side)
            order_type=lighter.SignerClient.ORDER_TYPE_STOP_LOSS_LIMIT,
            time_in_force=lighter.SignerClient.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME,
            trigger_price=sl_scaled,
            reduce_only=1,
            nonce=nonce,
            api_key_index=API_KEY_INDEX,
        )
        if err_sl:
            logger.error(f"[EXEC] SL FAILED: {err_sl}")
        else:
            logger.info(f"[EXEC] SL OK @ ${sl_price:,.2f}")
        nonce += 1
        time.sleep(3)  # CRITICAL: avoid nonce conflict

        # ── 3. Take-profit order ───────────────────────────────────────────────
        _, _, err_tp = await client.create_order(
            market_index=BTC_MARKET,
            client_order_index=2,
            base_amount=base_amount,
            price=tp_scaled,
            is_ask=(action == "LONG"),   # TP closes position (opposite side)
            order_type=lighter.SignerClient.ORDER_TYPE_TAKE_PROFIT_LIMIT,
            time_in_force=lighter.SignerClient.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME,
            trigger_price=tp_scaled,
            reduce_only=1,
            nonce=nonce,
            api_key_index=API_KEY_INDEX,
        )
        if err_tp:
            logger.error(f"[EXEC] TP FAILED: {err_tp}")
        else:
            logger.info(f"[EXEC] TP OK @ ${tp_price:,.2f}")

        # ── 4. Verify position ─────────────────────────────────────────────────
        time.sleep(3)
        pos = await get_open_position()
        if pos:
            logger.info(
                f"[EXEC] VERIFIED: {pos['side']} {pos['size']:.5f} BTC @ ${pos['entry']:,.2f} "
                f"| tied_orders={pos['tied_orders']}"
            )
        else:
            logger.warning("[EXEC] WARNING: Position not detected after entry")

        return True

    finally:
        await client.close()


# ── Scheduling ─────────────────────────────────────────────────────────────────

def seconds_until_next_signal() -> int:
    """
    Calculate seconds until the next signal window.
    Signal fires at SIGNAL_HOURS_UTC (e.g. 0,4,8,12,16,20 UTC),
    then we wait SIGNAL_DELAY_MINUTES extra for the pipeline to finish.
    Minimum wait: 60s (avoid re-running the same window immediately).
    """
    now = datetime.now(timezone.utc)
    # Try each signal hour today and tomorrow, find the nearest future one
    candidates = []
    for day_offset in (0, 1):
        for h in SIGNAL_HOURS_UTC:
            candidate = now.replace(hour=h, minute=SIGNAL_DELAY_MINUTES, second=0, microsecond=0)
            candidate += timedelta(days=day_offset)
            diff = (candidate - now).total_seconds()
            if diff > 60:  # at least 60s in the future
                candidates.append(diff)
    return int(min(candidates)) if candidates else 3600


# ── Main loop ──────────────────────────────────────────────────────────────────

_running = True


def handle_shutdown(signum, frame):
    global _running
    logger.info("[DAEMON] Shutdown signal received")
    _running = False


async def run_cycle():
    """Single execution cycle: read signal → decide → execute."""
    logger.info("=" * 60)
    logger.info(f"[DAEMON] Cycle start at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")

    # 1. Check if already in position
    try:
        pos = await get_open_position()
        if pos:
            logger.info(
                f"[DAEMON] Active position: {pos['side']} {pos['size']:.5f} BTC "
                f"@ ${pos['entry']:,.2f} | PnL=${pos['pnl']:+.4f} | tied_orders={pos['tied_orders']}"
            )
            logger.info("[DAEMON] Skipping — position already open")
            return
    except Exception as e:
        logger.error(f"[DAEMON] Failed to check position: {e}")
        return

    # 2. Read signal from API
    signal_data = await get_signal_from_api()
    if signal_data is None:
        logger.info("[DAEMON] No signal from API this cycle")
        return

    # Parse signal_data (dict from API) into object-like access
    conf = signal_data.get("confluence", {})
    plan = signal_data.get("trade_plan", {})
    signal = SimpleNamespace(
        is_fallback=signal_data.get("is_fallback", False),
        confluence=SimpleNamespace(
            verdict=conf.get("verdict", "NEUTRAL"),
            conviction_pct=float(conf.get("conviction_pct", 0))
        ),
        trade_plan=SimpleNamespace(
            status=plan.get("status", "SUSPENDED"),
            sl=float(plan.get("sl", 0)),
            tp1=float(plan.get("tp1", 0))
        )
    )
    params = parse_signal(signal)
    if params is None:
        logger.info("[DAEMON] No actionable signal this cycle")
        return

    logger.info(
        f"[DAEMON] Actionable signal: {params['action']} | "
        f"margin=${params['margin']} | SL=${params['sl']:,.2f} | TP=${params['tp']:,.2f}"
    )

    # 3. Execute
    try:
        success = await execute_trade(
            action=params["action"],
            margin=params["margin"],
            sl_price=params["sl"],
            tp_price=params["tp"],
        )
        if success:
            bal = await get_balance()
            logger.info(f"[DAEMON] Trade executed. Balance: ${bal:,.2f} USDC")
        else:
            logger.warning("[DAEMON] Trade execution failed or skipped (dry run)")
    except Exception as e:
        logger.error(f"[DAEMON] Execution error: {e}", exc_info=True)


async def main():
    global _running

    logger.info("=" * 60)
    logger.info("[DAEMON] BTC-QUANT v4.4 — 4H Signal Executor")
    logger.info(f"[DAEMON] Mode: {'LIVE TRADING' if TRADING_ENABLED else 'DRY RUN'}")
    logger.info(f"[DAEMON] Account: {ACCOUNT_INDEX} | API Key: {API_KEY_INDEX}")
    logger.info(f"[DAEMON] ACTIVE margin: ${MARGIN_ACTIVE} | ADVISORY margin: ${MARGIN_ADVISORY} | Leverage: {LEVERAGE}x")
    logger.info(f"[DAEMON] Signal hours (UTC): {sorted(SIGNAL_HOURS_UTC)}")
    logger.info("=" * 60)

    # Startup: print balance
    try:
        bal = await get_balance()
        price = await get_current_price()
        logger.info(f"[DAEMON] Balance: ${bal:,.2f} USDC | BTC price: ${price:,.2f}")
    except Exception as e:
        logger.error(f"[DAEMON] Startup check failed: {e}")

    while _running:
        try:
            await run_cycle()
        except Exception as e:
            logger.error(f"[DAEMON] Cycle error: {e}", exc_info=True)

        if not _running:
            break

        wait_secs = seconds_until_next_signal()
        wake_at = datetime.now(timezone.utc) + timedelta(seconds=wait_secs)
        logger.info(
            f"[DAEMON] Sleeping {wait_secs // 60}m until next signal at "
            f"{wake_at.strftime('%Y-%m-%d %H:%M')} UTC "
            f"({(wake_at + timedelta(hours=7)).strftime('%H:%M')} WIB)"
        )
        # Sleep in 60s intervals so we can respond to shutdown quickly
        for _ in range(wait_secs // 60 + 1):
            if not _running:
                break
            await asyncio.sleep(60)

    logger.info("[DAEMON] Shutdown complete")


if __name__ == "__main__":
    sig_mod.signal(sig_mod.SIGINT, handle_shutdown)
    sig_mod.signal(sig_mod.SIGTERM, handle_shutdown)
    asyncio.run(main())
