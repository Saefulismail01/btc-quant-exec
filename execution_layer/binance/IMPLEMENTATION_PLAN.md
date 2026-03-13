# BTC-QUANT: Live Execution Layer
## Implementation Plan & Definition of Done

**Tanggal dibuat:** 2026-03-11
**Versi sistem:** BTC-QUANT v4.4 Golden Model
**Author:** BTC-QUANT Team

---

## Konteks & Tujuan

Execution layer ini adalah **komponen baru** yang ditambahkan ke sistem BTC-QUANT yang sudah ada.
Tujuannya adalah mengubah sistem dari "signal generator + paper trade simulator" menjadi
"live trading bot yang mengirim order nyata ke exchange."

**Yang TIDAK berubah (existing system):**
- L0-L5 Signal Pipeline
- BinanceGateway (data fetching)
- DuckDB data storage
- Paper trade service
- Dashboard & API

**Yang BARU (execution layer):**
- BinanceExecutionGateway (order execution)
- LiveTradeRepository (live trade tracking)
- PositionManager (execution logic)
- LiveExecutor daemon
- Emergency stop API

---

## Golden v4.4 Parameters (Fixed — Tidak Boleh Diubah Tanpa Validasi Backtest)

| Parameter | Value | Sumber |
|-----------|-------|--------|
| Margin per trade | **$1,000 USDT fixed** | Paper v4.4 |
| Leverage | **15x** (notional $15,000) | Paper v4.4 |
| Stop Loss | **1.333%** dari entry price | Paper v4.4 |
| Take Profit | **0.71%** dari entry price | Paper v4.4 |
| TIME_EXIT | **24 jam / 6 candle** | Paper v4.4 |
| Max posisi aktif | **1** | Backtest constraint |
| Entry type | **Market order** | Paper v4.4 |
| SL/TP type | **Server-side stop order** | Safety requirement |
| Fee per round-trip | **~$12** (0.04% taker × 2) | Binance Futures |

---

## Arsitektur Target

```
EXISTING (tidak ada perubahan):
┌─────────────────────────────────────────┐
│  BinanceGateway (data only)             │
│  → DuckDB                               │
│  → L1-L5 Signal Pipeline                │
│  → SignalResponse (cached per 4H)       │
└─────────────────────────────────────────┘
                    ↓
NEW (yang akan kita bangun):
┌─────────────────────────────────────────┐
│  live_executor.py (daemon)              │
│  ├── BinanceExecutionGateway  ← NEW    │
│  ├── LiveTradeRepository      ← NEW    │
│  ├── PositionManager          ← NEW    │
│  └── ExecutionNotifier        ← EXTEND │
└─────────────────────────────────────────┘
```

**File structure baru:**
```
backend/
├── app/
│   ├── adapters/
│   │   ├── gateways/
│   │   │   ├── binance_gateway.py              ← existing, tidak diubah
│   │   │   ├── base_execution_gateway.py       ← NEW
│   │   │   └── binance_execution_gateway.py    ← NEW
│   │   └── repositories/
│   │       ├── market_repository.py            ← existing, tidak diubah
│   │       └── live_trade_repository.py        ← NEW
│   ├── use_cases/
│   │   └── position_manager.py                 ← NEW
│   └── api/
│       └── routers/
│           └── execution.py                    ← NEW
└── live_executor.py                            ← NEW (main daemon)
```

---

## Exchange Strategy

| Environment | Exchange | Tujuan |
|-------------|----------|--------|
| Development & Testing | **Binance Testnet** | Zero risk, data match perfect |
| Production | **Binance Mainnet** → migrasi ke **Lighter** | Fee 0% di Lighter |

**Kenapa Binance testnet dulu:**
- `BinanceGateway` sudah ada, tinggal extend
- CCXT sudah ter-install
- BTC/USDT = exact match dengan signal data (zero basis mismatch)
- Testnet tersedia dan stabil

**Kenapa nanti migrasi ke Lighter:**
- Fee 0% (vs Binance 0.04% per side)
- User sudah punya wallet di Lighter
- Execution layer dibuat exchange-agnostic via `BaseExchangeExecutionGateway`
  sehingga migrasi = ganti 1 class, logic tidak berubah

---

## Phase 1: Foundation
**Estimasi: 2-3 hari**

### Task 1.1 — Binance Testnet Setup & Credential Management

**Yang dikerjakan:**
- Setup Binance Futures Testnet account di `https://testnet.binancefuture.com`
- Tambah env variables untuk testnet credentials
- Verifikasi koneksi dan fetch balance

**File yang diubah:**
- `.env` — tambah keys baru
- `backend/app/config.py` — tambah execution config fields

**Env variables baru:**
```
BINANCE_TESTNET_API_KEY=...
BINANCE_TESTNET_SECRET=...
BINANCE_LIVE_API_KEY=...
BINANCE_LIVE_SECRET=...
EXECUTION_MODE=testnet        # testnet | live
TRADING_ENABLED=false         # safety flag, harus di-set true secara explicit
```

**Definition of Done (Task 1.1):**
- [ ] `.env` memiliki semua credential testnet
- [ ] Script test sederhana bisa print testnet account balance tanpa error
- [ ] `EXECUTION_MODE` bisa switch antara `testnet` dan `live` via env
- [ ] `TRADING_ENABLED=false` by default — trading tidak jalan sampai di-set `true`
- [ ] Private credentials tidak ter-commit ke git (`.gitignore` verified)

---

### Task 1.2 — BaseExchangeExecutionGateway

**Yang dikerjakan:**
Abstract base class sebagai contract untuk semua exchange gateway.
Memastikan `BinanceExecutionGateway` dan `LighterExecutionGateway` (nanti)
implement interface yang sama.

**File yang dibuat:**
- `backend/app/adapters/gateways/base_execution_gateway.py`

**Interface:**
```python
class BaseExchangeExecutionGateway(ABC):
    @abstractmethod
    async def place_market_order(
        self, side: str, size_usdt: float, leverage: int
    ) -> OrderResult: ...

    @abstractmethod
    async def place_sl_order(
        self, side: str, trigger_price: float, quantity: float
    ) -> OrderResult: ...

    @abstractmethod
    async def place_tp_order(
        self, side: str, trigger_price: float, quantity: float
    ) -> OrderResult: ...

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool: ...

    @abstractmethod
    async def get_open_position(self) -> PositionInfo | None: ...

    @abstractmethod
    async def close_position_market(self) -> OrderResult: ...

    @abstractmethod
    async def get_account_balance(self) -> float: ...
```

**Dataclasses:**
```python
@dataclass
class OrderResult:
    success: bool
    order_id: str | None
    filled_price: float
    filled_quantity: float
    error_message: str = ""

@dataclass
class PositionInfo:
    symbol: str
    side: str                  # LONG | SHORT
    entry_price: float
    quantity: float
    unrealized_pnl: float
    leverage: int
    sl_order_id: str | None
    tp_order_id: str | None
    opened_at_ts: int          # unix ms
```

**Definition of Done (Task 1.2):**
- [ ] Abstract class terdefinisi dengan semua method signatures
- [ ] `OrderResult` dan `PositionInfo` dataclass lengkap dengan type hints
- [ ] Docstring jelas untuk setiap method
- [ ] File bisa di-import tanpa error

---

### Task 1.3 — BinanceExecutionGateway

**Yang dikerjakan:**
Implementasi concrete class untuk Binance Futures.
Testnet dan mainnet dikontrol via `EXECUTION_MODE` env variable.

**File yang dibuat:**
- `backend/app/adapters/gateways/binance_execution_gateway.py`

**Logic utama:**
```python
async def place_market_order(self, side, size_usdt, leverage):
    # 1. Set leverage via fapiPrivatePostLeverage
    # 2. Fetch current price
    # 3. Hitung quantity = size_usdt * leverage / current_price
    # 4. Round quantity ke Binance lot size precision
    # 5. Place MARKET order via CCXT create_order()
    # 6. Return OrderResult

async def place_sl_order(self, side, trigger_price, quantity):
    # Order type: STOP_MARKET
    # Side: berlawanan dengan posisi
    #   LONG position → side = "sell"
    #   SHORT position → side = "buy"
    # params: {"stopPrice": trigger_price, "closePosition": True}

async def place_tp_order(self, side, trigger_price, quantity):
    # Order type: TAKE_PROFIT_MARKET
    # Side: berlawanan dengan posisi
    # params: {"stopPrice": trigger_price, "closePosition": True}

async def get_open_position(self):
    # fetch_positions() via CCXT
    # Filter symbol BTC/USDT:USDT
    # Return None jika tidak ada posisi (positionAmt == 0)

async def close_position_market(self):
    # Hitung current position size
    # Place market order berlawanan arah
    # Arah: LONG → sell, SHORT → buy
```

**Definition of Done (Task 1.3):**
- [ ] `place_market_order()` berhasil submit order ke testnet, return order ID valid
- [ ] `place_sl_order()` berhasil place STOP_MARKET order di testnet
- [ ] `place_tp_order()` berhasil place TAKE_PROFIT_MARKET order di testnet
- [ ] `get_open_position()` return `PositionInfo` yang akurat saat ada posisi
- [ ] `get_open_position()` return `None` saat tidak ada posisi
- [ ] `close_position_market()` berhasil close posisi, return filled price
- [ ] `get_account_balance()` return USDT balance yang akurat
- [ ] Semua method handle exception: tidak crash, return `OrderResult(success=False)`
- [ ] **Manual test di testnet:** open LONG → verify position → close → verify closed
- [ ] **Manual test di testnet:** open SHORT → verify position → close → verify closed

---

### Task 1.4 — LiveTradeRepository

**Yang dikerjakan:**
Tabel DuckDB baru untuk track live trades.
Terpisah dari `paper_trades` yang sudah ada.

**File yang dibuat:**
- `backend/app/adapters/repositories/live_trade_repository.py`

**Schema:**
```sql
CREATE TABLE live_trades (
    id                  VARCHAR PRIMARY KEY,   -- exchange order ID
    timestamp_open      BIGINT,                -- unix ms
    timestamp_close     BIGINT,                -- unix ms, NULL jika masih open
    symbol              VARCHAR,               -- BTC/USDT
    side                VARCHAR,               -- LONG | SHORT
    entry_price         DOUBLE,
    exit_price          DOUBLE,                -- NULL jika masih open
    size_usdt           DOUBLE,                -- $1,000 fixed
    size_base           DOUBLE,                -- BTC quantity
    leverage            INTEGER,               -- 15
    sl_price            DOUBLE,
    tp_price            DOUBLE,
    sl_order_id         VARCHAR,
    tp_order_id         VARCHAR,
    exit_type           VARCHAR,               -- SL | TP | TIME_EXIT | MANUAL | NULL
    status              VARCHAR,               -- OPEN | CLOSED
    pnl_usdt            DOUBLE,                -- NULL jika masih open
    pnl_pct             DOUBLE,                -- NULL jika masih open
    signal_verdict      VARCHAR,               -- dari SignalResponse.confluence.verdict
    signal_conviction   DOUBLE,                -- dari SignalResponse.confluence.conviction_pct
    candle_open_ts      BIGINT                 -- timestamp candle yang trigger signal
)
```

**Definition of Done (Task 1.4):**
- [ ] Tabel ter-create otomatis saat pertama kali dijalankan
- [ ] `insert_trade()` berfungsi dan data tersimpan dengan benar
- [ ] `update_trade_on_close()` update semua fields close dengan benar
- [ ] `get_open_trade()` return satu trade OPEN atau `None`
- [ ] `get_trade_history(limit)` return N trade terakhir yang CLOSED
- [ ] Schema tidak conflict dengan `paper_trades` yang sudah ada
- [ ] `_retry_write()` pattern dipakai (konsisten dengan `market_repository.py`)

---

## Phase 2: Core Execution Logic
**Estimasi: 3-4 hari**

### Task 2.1 — PositionManager

**Yang dikerjakan:**
Otak dari execution layer. Menerima `SignalResponse` dan
memutuskan apakah open, hold, atau close posisi.

**File yang dibuat:**
- `backend/app/use_cases/position_manager.py`

**Logic flow lengkap:**
```
process_signal(signal: SignalResponse):
    │
    ├── Cek TRADING_ENABLED flag
    │   TIDAK → log "trading disabled", return
    │
    ├── Sync position status dari exchange
    │   (detect SL/TP fills yang terjadi sejak cycle terakhir)
    │
    ├── Ada open position di DB?
    │   ├── YA → _manage_existing_position(signal)
    │   └── TIDAK → _try_open_position(signal)

_manage_existing_position(signal):
    │
    ├── Verify posisi masih open di exchange
    │   TIDAK ADA → posisi sudah closed (SL/TP hit)
    │              → update DB, record PnL, send notification, return
    │
    └── Cek TIME_EXIT
        YA (6 candle sudah lewat):
          → cancel SL order di exchange
          → cancel TP order di exchange
          → close_position_market()
          → update DB dengan exit_type=TIME_EXIT
          → send Telegram notification
          → risk_manager.record_trade_result()

_try_open_position(signal):
    │
    ├── Cek signal.trade_plan.status == "ACTIVE"?
    │   TIDAK → log "signal not active", return
    │
    ├── Cek RiskManager.evaluate()
    │   BLOCKED → log reason, return
    │
    ├── Hitung parameter:
    │   entry_price  = signal.price.now
    │   size_usdt    = $1,000 (FIXED)
    │   leverage     = 15 (FIXED)
    │   sl_price     = entry ± 1.333% (LONG: -, SHORT: +)
    │   tp_price     = entry ∓ 0.71%  (LONG: +, SHORT: -)
    │
    ├── place_market_order(side, size_usdt, leverage)
    │   GAGAL → log error, return (jangan lanjut)
    │
    ├── place_sl_order(sl_price, quantity)
    │   GAGAL → IMMEDIATELY close_position_market() + return
    │           (tidak boleh ada posisi tanpa SL)
    │
    ├── place_tp_order(tp_price, quantity)
    │   GAGAL → log warning, lanjut (SL masih ada, posisi terlindungi)
    │
    ├── insert ke live_trades DB
    │
    └── send Telegram open notification
```

**Definition of Done (Task 2.1):**
- [ ] `process_signal()` tidak pernah throw uncaught exception
- [ ] Tidak bisa open posisi baru jika sudah ada open position (idempotent)
- [ ] SL selalu di-place setelah entry — jika gagal, posisi langsung di-close
- [ ] TIME_EXIT ter-trigger dengan benar setelah 6 candle (24 jam)
- [ ] Semua decision di-log dengan level yang tepat (INFO/WARNING/ERROR)
- [ ] `RiskManager.evaluate()` selalu dikonsultasi sebelum open
- [ ] `RiskManager.record_trade_result()` selalu dipanggil setelah close
- [ ] Golden v4.4 parameters tidak bisa di-override dari luar (hardcoded constants)

---

### Task 2.2 — SL/TP Fill Detection (Polling)

**Yang dikerjakan:**
Detect ketika SL atau TP ter-hit di exchange dan sync ke database.
MVP menggunakan polling approach (bukan WebSocket).

**Logic:**
```python
async def sync_position_status():
    db_trade = repo.get_open_trade()
    if not db_trade:
        return  # tidak ada posisi, skip

    exchange_pos = await gateway.get_open_position()

    if exchange_pos is None:
        # Posisi sudah closed di exchange
        # Cari tau kenapa (SL atau TP hit)
        closed_order = await gateway.get_last_closed_order()
        exit_price = closed_order.filled_price
        exit_type  = _determine_exit_type(closed_order, db_trade)
        pnl_usdt   = _calculate_pnl(db_trade, exit_price)
        pnl_pct    = pnl_usdt / db_trade.size_usdt * 100

        repo.update_trade_on_close(exit_price, exit_type, pnl_usdt, pnl_pct)
        risk_manager.record_trade_result(pnl_pct)
        await notifier.notify_trade_closed(db_trade, exit_price, exit_type, pnl_usdt)
```

**Definition of Done (Task 2.2):**
- [ ] Setiap cycle, `sync_position_status()` dipanggil sebelum `process_signal()`
- [ ] Ketika SL hit → DB diupdate: `exit_type=SL`, `exit_price` benar, `pnl_usdt` benar
- [ ] Ketika TP hit → DB diupdate: `exit_type=TP`, `exit_price` benar, `pnl_usdt` benar
- [ ] `risk_manager.record_trade_result()` dipanggil dengan `pnl_pct` yang akurat
- [ ] Telegram notification dikirim saat posisi closed dengan summary lengkap
- [ ] Tidak ada duplicate detection (idempotent jika dipanggil 2x)

---

### Task 2.3 — LiveExecutor Daemon

**Yang dikerjakan:**
Main daemon loop yang mengikat semua komponen.

**File yang dibuat:**
- `backend/live_executor.py`

```python
async def run_live_executor():
    logger.info("[LIVE] Starting Live Execution Daemon")
    logger.info(f"[LIVE] Mode: {EXECUTION_MODE}")
    logger.info(f"[LIVE] Parameters: Margin=$1,000 | Leverage=15x | SL=1.333% | TP=0.71%")

    gateway = BinanceExecutionGateway()
    repo    = LiveTradeRepository()
    manager = PositionManager(gateway, repo)

    # Safety check saat startup
    balance = await gateway.get_account_balance()
    logger.info(f"[LIVE] Account balance: ${balance:,.2f} USDT")

    if balance < 1000 and EXECUTION_MODE == "live":
        logger.error("[LIVE] Insufficient balance for $1,000 margin. Aborting.")
        return

    while True:
        try:
            # 1. Sync: detect SL/TP fills
            await manager.sync_position_status()

            # 2. Get latest cached signal (updated per 4H candle)
            signal = get_cached_signal()

            if signal and not signal.is_fallback:
                await manager.process_signal(signal)
            else:
                logger.info("[LIVE] No valid signal. Waiting.")

            await asyncio.sleep(60)

        except Exception as e:
            logger.error(f"[LIVE] Loop error: {e}", exc_info=True)
            await asyncio.sleep(10)
```

**Definition of Done (Task 2.3):**
- [ ] Daemon berjalan tanpa crash selama minimal 48 jam di testnet
- [ ] Log output jelas setiap cycle (timestamp, status, balance)
- [ ] Graceful shutdown saat `KeyboardInterrupt`:
      cancel semua pending orders → close posisi jika ada → exit
- [ ] Balance check saat startup — abort jika insufficient
- [ ] `TRADING_ENABLED=false` → daemon jalan tapi tidak execute order apapun

---

## Phase 3: Safety & Monitoring
**Estimasi: 2 hari**

### Task 3.1 — Emergency Stop

**Yang dikerjakan:**
API endpoints untuk kontrol manual execution layer.

**File yang dibuat:**
- `backend/app/api/routers/execution.py`

**Endpoints:**
```
POST /api/execution/emergency_stop
  → Set TRADING_HALTED = True
  → Cancel semua open orders (SL, TP)
  → Close posisi aktif dengan market order
  → Return: { "status": "halted", "position_closed": true, "exit_price": ... }

GET /api/execution/status
  → Return: {
      "trading_enabled": bool,
      "trading_halted": bool,
      "execution_mode": "testnet" | "live",
      "open_position": PositionInfo | null,
      "daily_pnl_usdt": float,
      "daily_pnl_pct": float,
      "risk_status": { ... dari RiskManager.get_status() }
    }

POST /api/execution/resume
  → Clear TRADING_HALTED flag
  → Require body: { "confirm": "RESUME_TRADING" }
  → Return: { "status": "resumed" }

POST /api/execution/set_trading_enabled
  → Body: { "enabled": true | false }
  → Toggle TRADING_ENABLED flag
```

**Definition of Done (Task 3.1):**
- [ ] `POST /api/execution/emergency_stop` berhasil close posisi dalam < 10 detik
- [ ] Setelah emergency stop, daemon tidak bisa open posisi baru
- [ ] `GET /api/execution/status` return data akurat dan real-time
- [ ] `POST /api/execution/resume` memerlukan explicit confirm string
- [ ] Semua endpoints ter-dokumentasi di README

---

### Task 3.2 — Telegram Notifications Update

**Yang dikerjakan:**
Tambah notification templates untuk live execution events.

**Notification templates:**

```
🟢 LIVE TRADE OPENED
━━━━━━━━━━━━━━━━━━
📊 BTC/USDT Perpetual | LONG
💰 Entry : $83,500
📏 Size  : $1,000 (15x) = $15,000 notional
🛑 SL    : $82,386 (-1.333%)
🎯 TP    : $84,093 (+0.71%)
⏳ Expire: 2026-03-12 08:00 UTC (6 candle)
🎯 Conviction: 67.3%
━━━━━━━━━━━━━━━━━━
🤖 BTC-QUANT LIVE v4.4

---

✅ LIVE TRADE CLOSED — TP HIT
━━━━━━━━━━━━━━━━━━
📊 BTC/USDT | LONG
💰 Entry : $83,500 → Exit: $84,093
📈 PnL   : +$106.50 USDT (+10.65%)
⏱️ Hold  : 8.5 jam
📊 Daily PnL: +$106.50 USDT
━━━━━━━━━━━━━━━━━━
🤖 BTC-QUANT LIVE v4.4

---

❌ LIVE TRADE CLOSED — SL HIT
━━━━━━━━━━━━━━━━━━
📊 BTC/USDT | LONG
💰 Entry : $83,500 → Exit: $82,386
📉 PnL   : -$133.50 USDT (-13.35%)
⏱️ Hold  : 4.2 jam
📊 Daily PnL: -$133.50 USDT
━━━━━━━━━━━━━━━━━━
🤖 BTC-QUANT LIVE v4.4

---

⏰ LIVE TRADE CLOSED — TIME EXIT
━━━━━━━━━━━━━━━━━━
📊 BTC/USDT | SHORT
💰 Entry : $83,500 → Exit: $83,200
📈 PnL   : +$45.00 USDT (+4.5%)
⏱️ Hold  : 24 jam (timeout)
📊 Daily PnL: +$45.00 USDT
━━━━━━━━━━━━━━━━━━
🤖 BTC-QUANT LIVE v4.4

---

🚨 EMERGENCY STOP TRIGGERED
━━━━━━━━━━━━━━━━━━
Semua posisi ditutup secara manual.
Daily PnL: -$133.30 USDT
Trading HALTED. Resume via API.
━━━━━━━━━━━━━━━━━━
🤖 BTC-QUANT LIVE v4.4
```

**Definition of Done (Task 3.2):**
- [ ] Notifikasi open dikirim dalam 30 detik setelah order fill
- [ ] Notifikasi close dikirim dalam 30 detik setelah posisi closed
- [ ] Format pesan tidak ada MarkdownV2 escape error
- [ ] Tidak ada duplicate notification untuk event yang sama
- [ ] Emergency stop notification dikirim saat triggered

---

### Task 3.3 — Testnet Integration Test

**Yang dikerjakan:**
End-to-end test semua scenario di Binance testnet.

**Test Scenarios:**

| # | Scenario | Expected Result |
|---|----------|-----------------|
| 1 | Signal ACTIVE LONG → TP hit | Position opened, TP closed, DB updated, Telegram sent |
| 2 | Signal ACTIVE SHORT → TP hit | Idem untuk SHORT |
| 3 | Signal ACTIVE → SL hit | Position opened, SL closed, DB updated, PnL negatif |
| 4 | Signal ACTIVE → 6 candle timeout | TIME_EXIT triggered, market close, DB updated |
| 5 | Signal SUSPENDED | No position opened |
| 6 | Signal ACTIVE saat posisi sudah open | No new position (idempotent) |
| 7 | Emergency stop saat posisi open | Position closed, HALTED flag set |
| 8 | Daily loss cap triggered | RiskManager blocks new entries |
| 9 | 3 consecutive losses | Cooldown 2 candles, no new entry |
| 10 | Gateway API timeout | Retry 3x, graceful error, daemon continues |

**Definition of Done (Task 3.3):**
- [ ] Semua 10 scenario ter-execute tanpa manual intervention
- [ ] DB records akurat untuk setiap scenario
- [ ] Telegram notifications terkirim untuk setiap event
- [ ] Log tidak ada ERROR atau WARNING yang unexpected
- [ ] Daemon berjalan stabil **48 jam** tanpa crash di testnet
- [ ] PnL calculation verified: entry price vs exit price vs fee

---

## Phase 4: Mainnet Go-Live
**Estimasi: 1 hari**

### Task 4.1 — Mainnet Checklist

**Semua harus ✅ sebelum switch ke mainnet:**

**Testing:**
- [ ] Testnet stabil 48 jam tanpa crash
- [ ] Semua 10 integration test scenarios passed
- [ ] PnL calculation verified akurat
- [ ] Emergency stop tested dan berfungsi
- [ ] Daily loss cap tested dan berfungsi

**Configuration:**
- [ ] `.env` mainnet credentials di-setup
- [ ] `EXECUTION_MODE=live` di env
- [ ] `TRADING_ENABLED=false` saat pertama kali deploy (manual enable)
- [ ] Binance Futures mainnet account dengan minimum **$1,200 USDT**
      ($1,000 margin + $200 buffer untuk fee dan margin call)

**Monitoring:**
- [ ] Telegram bot aktif dan terverifikasi menerima notifications
- [ ] `GET /api/execution/status` berfungsi dan accessible
- [ ] Log file configured dan accessible

**Deployment:**
- [ ] Code review selesai
- [ ] Semua sensitive credentials di `.env`, tidak ada di code
- [ ] `live_executor.py` bisa di-restart tanpa data loss
      (state diambil dari DB dan exchange, bukan memory)

---

## Risk Mitigation

| Risk | Probability | Impact | Mitigasi |
|------|-------------|--------|---------|
| SL/TP gagal di-place | Low | High | Auto close posisi dengan market order |
| Exchange API timeout | Medium | Medium | Retry 3x dengan exponential backoff |
| Duplicate order (double entry) | Low | High | Check open position sebelum setiap entry |
| Signal service down | Low | Low | `get_cached_signal()` return last known signal |
| Daily loss cap breach | Medium | Medium | RiskManager sudah handle + Telegram alert |
| Network disconnect | Medium | Medium | Reconnect logic di daemon loop |
| Mainnet credentials leak | Low | Critical | `.gitignore` + env variables only |
| Exchange maintenance | Low | Medium | Daemon retry dengan backoff, alert via Telegram |

---

## Future: Migrasi ke Lighter

Setelah sistem proven di Binance mainnet:

1. Buat `LighterExecutionGateway(BaseExchangeExecutionGateway)`
2. Install `lighter-sdk`
3. Implement semua abstract methods
4. Test di Lighter testnet (jika tersedia) atau mainnet kecil
5. Switch via config: `EXCHANGE=lighter`

**Yang TIDAK perlu diubah:**
- Signal pipeline (L0-L5)
- PositionManager logic
- LiveTradeRepository
- Telegram notifications
- Emergency stop

**Yang perlu diubah:**
- Hanya `BinanceExecutionGateway` → `LighterExecutionGateway`
- Quote currency: USDT → USDC (minor adjustment di sizing)
- Authentication: API key → private key signing

---

## Summary Timeline

| Phase | Tasks | Estimasi | Output |
|-------|-------|----------|--------|
| **Phase 1** | Foundation (1.1–1.4) | 2-3 hari | Gateway + DB ready |
| **Phase 2** | Core Logic (2.1–2.3) | 3-4 hari | Execution working di testnet |
| **Phase 3** | Safety (3.1–3.3) | 2 hari | Emergency stop + 48 jam testnet stable |
| **Phase 4** | Mainnet Go-Live (4.1) | 1 hari | Live trading active |
| **Total** | | **8-10 hari** | |

---

*Dokumen ini dibuat berdasarkan hasil diskusi pada 2026-03-11.*
*Update dokumen ini jika ada perubahan scope atau parameter.*
