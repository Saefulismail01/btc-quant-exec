import asyncio
import json
import os
from datetime import datetime, timezone
from app.adapters.gateways.binance_gateway import BinanceGateway
from app.adapters.repositories.market_repository import MarketRepository
from app.adapters.gateways.multi_exchange_gateway import MultiExchangeFundingGateway
from app.adapters.gateways.onchain_gateway import OnChainGateway

_CANDLE_STATE_FILE = os.path.join(
    os.path.dirname(__file__), "..", "infrastructure", "last_candle_ts.json"
)


def _load_last_candle_ts() -> int:
    try:
        if os.path.exists(_CANDLE_STATE_FILE):
            with open(_CANDLE_STATE_FILE, "r") as f:
                return int(json.load(f).get("last_notified_ts", 0))
    except Exception:
        pass
    return 0


def _save_last_candle_ts(ts: int) -> None:
    try:
        os.makedirs(os.path.dirname(_CANDLE_STATE_FILE), exist_ok=True)
        with open(_CANDLE_STATE_FILE, "w") as f:
            json.dump({"last_notified_ts": ts}, f)
    except Exception:
        pass


class DataIngestionUseCase:
    """
    Use Case untuk Ingesti Data.
    Mengatur alur kerja penarikan data dari Gateway dan menyimpannya ke Repository.
    """

    def __init__(self, gateway: BinanceGateway, repository: MarketRepository, position_manager=None):
        self.gateway = gateway
        self.repository = repository
        self.position_manager = position_manager  # Injected at startup
        # Track state to avoid duplicate processing per closed candle (persisted to disk)
        self.last_notified_ts = _load_last_candle_ts()
        self.last_regime = None
        # [TASK-7/9] Cross-exchange and on-chain gateways
        self._multi_funding_gw = MultiExchangeFundingGateway()
        self._onchain_gw = OnChainGateway()
        # Track last 4H candle ts for rate-limited fetches
        self._last_4h_ts_for_onchain = 0

    async def run_cycle(self, cycle_idx: int):
        print(f"  [{datetime.now().strftime('%H:%M:%S')}] [Ingestion] == Cycle #{cycle_idx} starting ==")

        # 1. Fetch OHLCV
        df_ohlcv = await self.gateway.fetch_historical_4h()
        new_candle_detected = False
        latest_ts = 0

        if not df_ohlcv.empty:
            self.repository.upsert_ohlcv(df_ohlcv)
            latest_ts = int(df_ohlcv['timestamp'].iloc[-1])
            print(f"  - OHLCV Upserted: {len(df_ohlcv)} rows (Latest: ${df_ohlcv['close'].iloc[-1]:,.0f})")

            # Candle timestamps are multiples of 4 hours.
            if latest_ts > self.last_notified_ts:
                new_candle_detected = True

        # 2. Fetch Market Metrics
        metrics = await self.gateway.fetch_market_metrics()
        obi = await self.gateway.fetch_order_book_imbalance()
        micro = await self.gateway.fetch_microstructure_data()
        fgi = await self.gateway.fetch_fgi()

        # [TASK-7] Cross-exchange funding rate (parallel, cached 5 min)
        cross_funding = {"avg_funding": 0.0, "funding_consensus": "MIXED", "max_spread": 0.0}
        try:
            cross_funding = await self._multi_funding_gw.fetch_cross_funding()
        except Exception as e:
            print(f"  - [TASK-7] Cross-funding fetch failed: {e}")

        # [TASK-7b] Long/Short ratio (public Binance endpoint)
        ls_data = {"long_ratio": 0.5, "short_ratio": 0.5, "ls_label": "Balanced"}
        try:
            ls_data = await self.gateway.fetch_long_short_ratio()
        except Exception as e:
            print(f"  - [TASK-7b] L/S ratio fetch failed: {e}")

        # [TASK-9] On-chain netflow — only fetch on new 4H candle (rate limited: 10/day)
        netflow_data = {"netflow_btc": 0.0, "exchange_netflow_label": "Neutral"}
        if new_candle_detected and latest_ts != self._last_4h_ts_for_onchain:
            try:
                live_price = float(df_ohlcv['close'].iloc[-1]) if not df_ohlcv.empty else 0.0
                raw_nf = await self._onchain_gw.fetch_exchange_netflow(current_price=live_price)
                netflow_data = {
                    "netflow_btc": raw_nf.get("netflow_btc", 0.0),
                    "exchange_netflow_label": raw_nf.get("flow_label", "Neutral"),
                }
                self._last_4h_ts_for_onchain = latest_ts
            except Exception as e:
                print(f"  - [TASK-9] Netflow fetch failed: {e}")

        # 3. Assemble and store metrics
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        # [TASK-7] Average cross-exchange funding (override Binance-only with consensus avg)
        avg_funding = cross_funding.get("avg_funding", 0.0)
        base_funding = metrics.get("funding_rate", 0.0)
        final_funding = avg_funding if avg_funding != 0.0 else base_funding

        metrics_row = {
            "timestamp": now_ms,
            "funding_rate": final_funding,
            "open_interest": metrics.get("open_interest", 0.0),
            "global_mcap_change": 0.0,
            "order_book_imbalance": obi,
            "cvd": micro["cvd"],
            "liquidations_buy": micro["liq_buy"],
            "liquidations_sell": micro["liq_sell"],
            "fgi_value": fgi,
            # [TASK-7/8] Cross-exchange consensus fields
            "funding_consensus": cross_funding.get("funding_consensus", "MIXED"),
            "funding_spread": cross_funding.get("max_spread", 0.0),
            "long_short_ratio": ls_data.get("long_ratio", 0.5),
            "long_short_label": ls_data.get("ls_label", "Balanced"),
            # [TASK-9] On-chain netflow
            "exchange_netflow_btc": netflow_data.get("netflow_btc", 0.0),
            "exchange_netflow_label": netflow_data.get("exchange_netflow_label", "Neutral"),
        }
        self.repository.insert_metrics(metrics_row)
        print(f"  - Metrics: Funding {metrics_row['funding_rate']:+.8f} | FGI {fgi} | L/S {ls_data['ls_label']} | Consensus {metrics_row['funding_consensus']}")

        # 4. Process signal-driven actions (Triggered by new candle)
        if new_candle_detected:
            await self._handle_notifications(latest_ts)

        print(f"  [{datetime.now().strftime('%H:%M:%S')}] [Ingestion] == Cycle done. ==")

    async def _handle_notifications(self, candle_ts: int):
        """Orchestrates signal, paper trading, and Telegram alerts from one signal source."""
        try:
            from app.use_cases.signal_service import get_signal_service
            from app.use_cases.paper_trade_service import get_paper_trade_service
            from app.use_cases.telegram_notifier_use_case import get_telegram_notifier
        except Exception as e:
            print(f"  [Ingestion] Notification init failed: {str(e)}")
            return

        # Generate signal once. Dashboard, Telegram, and paper trade use this same object.
        try:
            from app.use_cases.signal_service import get_signal_service, set_cached_signal
            sig_svc = get_signal_service()
            signal = sig_svc.get_signal()
            set_cached_signal(signal)  # Cache signal — single source of truth
            print(f"  [Signal] Cached. Verdict: {signal.confluence.verdict} | Status: {signal.trade_plan.status}")
        except Exception as e:
            print(f"  [Signal] Generation failed: {str(e)}")
            return

        # Mark this candle processed to prevent duplicate execution every minute.
        self.last_notified_ts = candle_ts
        _save_last_candle_ts(candle_ts)

        if signal.is_fallback:
            print("  [Signal] Fallback signal. Skip paper trade. Sending no-signal Telegram.")
            try:
                notifier = get_telegram_notifier()
                await notifier.notify_no_signal(signal.dict(), reason="fallback")
            except Exception as e:
                print(f"  [Telegram] Fallback notify failed: {str(e)}")
            return

        # 1) Paper trade execution from the same signal
        try:
            paper_svc = get_paper_trade_service()
            paper_svc.process_signal(signal)
            print("  [Paper] Signal processed.")
        except Exception as e:
            print(f"  [Paper] Execution failed: {str(e)}")

        # 2) Live execution via PositionManager (Lighter)
        if self.position_manager:
            try:
                just_closed = await self.position_manager.sync_position_status()
                if just_closed:
                    print("  [Execution] Position just closed this cycle — skipping open to avoid immediate re-entry.")
                else:
                    await self.position_manager.process_signal(signal)
                    print("  [Execution] PositionManager signal processed.")
            except Exception as e:
                print(f"  [Execution] PositionManager failed: {str(e)}")

        # 4) Telegram signal alert from the same signal
        notifier = get_telegram_notifier()
        try:
            sent = await notifier.notify_signal(signal.dict())
            if sent:
                print(f"  [Telegram] Signal alert sent for candle {candle_ts}")
        except Exception as e:
            print(f"  [Telegram] Signal alert failed: {str(e)}")

        # 5) Telegram regime shift alert
        try:
            current_regime = signal.confluence.layers.l1_hmm.label
            if self.last_regime and current_regime != self.last_regime:
                confidence = signal.confluence.layers.l1_hmm.contribution
                await notifier.notify_regime_shift(self.last_regime, current_regime, confidence)
                print(f"  [Telegram] Regime shift alert: {self.last_regime} -> {current_regime}")
            self.last_regime = current_regime
        except Exception as e:
            print(f"  [Telegram] Regime shift alert failed: {str(e)}")


async def start_data_daemon(interval=60):
    gateway = BinanceGateway()
    repository = MarketRepository()

    # Instantiate PositionManager with LighterExecutionGateway
    position_manager = None
    try:
        from app.adapters.gateways.lighter_execution_gateway import LighterExecutionGateway
        from app.adapters.repositories.live_trade_repository import LiveTradeRepository
        from app.use_cases.position_manager import PositionManager

        lighter_gateway = LighterExecutionGateway()
        live_repo = LiveTradeRepository()
        from app.use_cases.strategies.fixed_strategy import FixedStrategy, MARGIN_USD, LEVERAGE
        position_manager = PositionManager(gateway=lighter_gateway, repo=live_repo, strategy=FixedStrategy())
        print(f"  [Ingestion Daemon] PositionManager initialized with LighterExecutionGateway + FixedStrategy (${MARGIN_USD:.0f} margin × {LEVERAGE}x = ${MARGIN_USD*LEVERAGE:.0f} notional)")
    except Exception as e:
        print(f"  [Ingestion Daemon] PositionManager init failed (execution disabled): {e}")

    use_case = DataIngestionUseCase(gateway, repository, position_manager=position_manager)

    # Startup sync: detect if position was closed while bot was offline
    if position_manager:
        try:
            print("  [Ingestion Daemon] Startup sync: checking position status...")
            await position_manager.sync_position_status()
            print("  [Ingestion Daemon] Startup sync complete.")
        except Exception as e:
            print(f"  [Ingestion Daemon] Startup sync failed (non-fatal): {e}")

    print("\n  [Ingestion Daemon] STARTING CLEAN PIPELINE...")
    cycle = 0
    try:
        while True:
            cycle += 1
            try:
                await use_case.run_cycle(cycle)
            except Exception as e:
                print(f"  [{datetime.now().strftime('%H:%M:%S')}] [Ingestion] Cycle #{cycle} FAILED: {e}. Continuing...")
            await asyncio.sleep(interval)
    finally:
        await gateway.close()
