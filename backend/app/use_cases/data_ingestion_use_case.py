import asyncio
from datetime import datetime, timezone
from app.adapters.gateways.binance_gateway import BinanceGateway
from app.adapters.repositories.market_repository import MarketRepository


class DataIngestionUseCase:
    """
    Use Case untuk Ingesti Data.
    Mengatur alur kerja penarikan data dari Gateway dan menyimpannya ke Repository.
    """

    def __init__(self, gateway: BinanceGateway, repository: MarketRepository):
        self.gateway = gateway
        self.repository = repository
        # Track state to avoid duplicate processing per closed candle
        self.last_notified_ts = 0
        self.last_regime = None

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

        # 3. Assemble and store metrics
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        metrics_row = {
            "timestamp": now_ms,
            "funding_rate": metrics.get("funding_rate", 0.0),
            "open_interest": metrics.get("open_interest", 0.0),
            "global_mcap_change": 0.0,
            "order_book_imbalance": obi,
            "cvd": micro["cvd"],
            "liquidations_buy": micro["liq_buy"],
            "liquidations_sell": micro["liq_sell"],
            "fgi_value": fgi,
        }
        self.repository.insert_metrics(metrics_row)
        print(f"  - Metrics: Funding {metrics_row['funding_rate']:+.8f} | FGI {fgi}")

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

        # 2) Telegram signal alert from the same signal
        notifier = get_telegram_notifier()
        try:
            sent = await notifier.notify_signal(signal.dict())
            if sent:
                print(f"  [Telegram] Signal alert sent for candle {candle_ts}")
        except Exception as e:
            print(f"  [Telegram] Signal alert failed: {str(e)}")

        # 3) Telegram regime shift alert
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
    use_case = DataIngestionUseCase(gateway, repository)

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
