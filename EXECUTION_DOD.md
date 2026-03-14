# Execution Layer — Definition of Done (DoD)

**Last Updated:** 2026-03-14
**Status:** In Progress

---

## Phase 1: Wire PositionManager into Pipeline

> **Goal:** Signal yang dihasilkan setiap 4H candle otomatis diteruskan ke PositionManager → LighterGateway → Telegram trade alert.

### DoD Checklist

#### 1.1 — Connect PositionManager to DataIngestion
- [x] `data_ingestion_use_case._handle_notifications()` memanggil `PositionManager.process_signal(signal)` setelah paper trade
- [x] `LighterExecutionGateway` diinstansiasi dan di-inject ke `PositionManager` di `start_data_daemon()`
- [x] `LIGHTER_TRADING_ENABLED=false` by default — PositionManager berjalan read-only (dry-run log tanpa kirim order)
- [x] Tidak ada exception yang menyebabkan pipeline berhenti (semua dibungkus try/except dengan log)
- [x] `_is_trading_enabled()` membaca `LIGHTER_TRADING_ENABLED` (bukan `TRADING_ENABLED`)

#### 1.2 — Dry-Run Validation (LIGHTER_TRADING_ENABLED=false)
- [ ] Log menunjukkan: `[PositionManager] [DRY-RUN] Would open LONG @ $XXXXX | SL: $XXXXX | TP: $XXXXX`
- [ ] Log menunjukkan: `[PositionManager] [DRY-RUN] No entry (status=SUSPENDED ...)` saat tidak ada sinyal
- [ ] Tidak ada order terkirim ke Lighter
- [ ] Tidak ada error saat pipeline berjalan 3 candle berturut-turut (12 jam)

#### 1.3 — ExecutionNotifier Connected
- [ ] Trade alert Telegram terkirim saat ada sinyal ACTIVE (dry-run mode boleh pakai flag `[DRY-RUN]`)
- [ ] Format pesan: action, entry, SL, TP (dari Golden params), leverage, conviction

---

## Phase 2: Strategy Pattern untuk Trade Plan

> **Goal:** PositionManager tidak hardcode SL/TP — bisa swap strategy tanpa ubah core logic.

### DoD Checklist

#### 2.1 — TradePlanStrategy Interface
- [ ] Abstract class `BaseTradePlanStrategy` dengan method `calculate(entry_price, action) -> TradeParams`
- [ ] `TradeParams` dataclass: `sl_price`, `tp_price`, `leverage`, `margin_usd`, `position_size_pct`

#### 2.2 — FixedStrategy (Golden v4.4)
- [ ] Implementasi `FixedStrategy(BaseTradePlanStrategy)`
- [ ] Parameter: `SL=1.333%`, `TP=0.71%`, `LEVERAGE=15x`, `MARGIN=$1000`
- [ ] Unit test: LONG @ $83000 → SL=$81892, TP=$83590

#### 2.3 — HestonStrategy
- [ ] Implementasi `HestonStrategy(BaseTradePlanStrategy)`
- [ ] Pakai `signal.sl_tp_preset.sl_multiplier` × ATR sebagai SL distance
- [ ] Pakai `signal.sl_tp_preset.tp1_multiplier` × ATR sebagai TP distance
- [ ] Fallback ke FixedStrategy jika `sl_tp_preset` is None
- [ ] Unit test: preset `sl_multiplier=2.0` menghasilkan SL lebih lebar dari Fixed

#### 2.4 — PositionManager Refactor
- [ ] `PositionManager.__init__()` menerima `strategy: BaseTradePlanStrategy` (default: FixedStrategy)
- [ ] `_try_open_position()` memanggil `self.strategy.calculate()` — tidak ada hardcode SL/TP lagi
- [ ] Semua test Phase 1 masih lulus setelah refactor

---

## Phase 3: Testnet Validation

> **Goal:** 48 jam testnet berjalan stabil sebelum go-live mainnet.

### DoD Checklist

#### 3.1 — Lighter Testnet Connected
- [ ] `LIGHTER_TRADING_ENABLED=true` di testnet
- [ ] Order LONG/SHORT berhasil dikirim dan dikonfirmasi oleh Lighter testnet
- [ ] SL order berhasil dipasang setelah market order fill
- [ ] Telegram notifikasi: OPEN, CLOSE (TP/SL/TIME_EXIT), ERROR

#### 3.2 — 48-Hour Stability
- [ ] Pipeline berjalan 48 jam tanpa crash
- [ ] Tidak ada duplicate order untuk candle yang sama
- [ ] TIME_EXIT berfungsi: posisi ditutup setelah 6 candle (24h) jika SL/TP belum hit
- [ ] PnL calculation akurat (dibandingkan manual)

#### 3.3 — Pre-Mainnet Checklist
- [ ] Semua Phase 3.2 lulus
- [ ] Mainnet credentials tersimpan di `.env` VPS
- [ ] `LIGHTER_EXECUTION_MODE=mainnet` dan `LIGHTER_TRADING_ENABLED=true` di docker-compose VPS
- [ ] Emergency stop endpoint `/api/execution/emergency-stop` diuji dan berfungsi
- [ ] Balance minimum mainnet terverifikasi ($1000+ available margin)

---

## Architecture Reference

```
[4H Candle Close]
      │
      ▼
DataIngestionUseCase.run_cycle()
      │
      ├─► SignalService.get_signal()          → SignalResponse
      │         └─► set_cached_signal()
      │
      ├─► PaperTradeService.process_signal()  → paper trades DB
      │
      ├─► PositionManager.process_signal()    ← PHASE 1 (missing link)
      │         │
      │         ├─► TradePlanStrategy.calculate(entry, action)  ← PHASE 2
      │         │         ├── FixedStrategy   (default)
      │         │         ├── HestonStrategy  (from signal.sl_tp_preset)
      │         │         └── KellyStrategy   (future)
      │         │
      │         ├─► LighterExecutionGateway.submit_order()
      │         └─► ExecutionNotifier.notify_open/close()
      │
      └─► TelegramNotifier.notify_signal()    → signal Telegram
```

---

## Key Constants (Golden v4.4 — Fixed)

| Parameter | Value |
|-----------|-------|
| Margin | $1,000 USD |
| Leverage | 15x |
| Notional | $15,000 |
| SL | 1.333% dari entry |
| TP | 0.71% dari entry |
| Time Exit | 6 candles (24h) |
| Fee rate | 0.04% per side |

---

## Files To Create / Modify

| File | Action | Phase |
|------|--------|-------|
| `backend/app/use_cases/data_ingestion_use_case.py` | MODIFY — tambah PositionManager call | 1.1 |
| `backend/app/use_cases/position_manager.py` | MODIFY — inject gateway, dry-run flag | 1.1 |
| `backend/app/main.py` | MODIFY — instantiate PositionManager di lifespan | 1.1 |
| `backend/app/use_cases/strategies/base_strategy.py` | CREATE — abstract interface | 2.1 |
| `backend/app/use_cases/strategies/fixed_strategy.py` | CREATE — Golden v4.4 | 2.2 |
| `backend/app/use_cases/strategies/heston_strategy.py` | CREATE — Heston-based | 2.3 |
