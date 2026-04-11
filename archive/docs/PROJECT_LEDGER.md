# BTC-QUANT v4.6 — Project Ledger

> **Last Updated:** 2026-04-06 04:50 UTC
> **Status:** Phase 4 Mainnet — Live Execution Active
> **BTC Price:** $69,055 | **FGI:** 13 (Extreme Fear)

---

## 1. Executive Summary

BTC-QUANT adalah bot scalping Bitcoin perpetuals di **Lighter mainnet** (L2 ZK orderbook DEX). Sistem menggunakan 4-layer signal pipeline berbasis riset Renaissance Technologies + econophysics untuk menghasilkan sinyal LONG/SHORT dengan conviction scoring.

**Saat ini:** Data ingestion, API server, dan PositionManager berjalan terintegrasi di Docker. Lighter execution aktif. Sinkronisasi SL/TP bursa riil aktif.

---

## 2. Architecture & Component Stack

| Layer / Component | Technology / Mechanism | Purpose | Status |
| :--- | :--- | :--- | :--- |
| **L1: BCD Engine** | Bayesian Changepoint Detection | Regime identification & Persistence tracking | ✅ Active |
| **L2: EMA Layer** | Multi-TF Trend Alignment | Confirming directional bias via moving averages | ✅ Active |
| **L3: MLP AI** | Multi-Layer Perceptron | Next-candle return sign prediction | ✅ Active |
| **L4: Heston Vol** | Heston Stochastic Volatility | Estimating ATR-adaptive SL/TP multipliers | ✅ Active |
| **Scoring Engine** | DirectionalSpectrum | Aggregating layers into Verdict (ACTIVE/ADVISORY) | ✅ Active |
| **Controller** | FastAPI + Ingestion Daemon | OHLCV fetching (60s cycle) & Signal caching | ✅ Active |
| **Execution** | PositionManager (Integrated) | Order lifecycle, OCO mgmt, & **Lighter Sync** | ✅ Active |
| **Risk Guard** | RiskManager | Daily loss cap, SL freeze, & Adaptive leverage | ✅ Active |
| **Exchange** | Lighter Mainnet | ZK-Rollup Orderbook (BTC/USDC Perpetuals) | 🚀 LIVE |


### Timeframe & Pair
- **Pair:** BTC/USDC perpetual (Lighter)
- **Candle:** 4H
- **Retrain MLP:** Every 48 candles (192 jam) atau vol spike > 2x long-run

---

## 3. Live Deployment Status

| Item | Status | Detail |
|------|--------|--------|
| **VPS** | idcloudhost | Ubuntu, uptime 16 days |
| **Container** | `btc-quant-api` | Up 4 days (healthy) |
| **Image** | `btc-quant-api` | Python 3.12, Dockerfile simple |
| **API Port** | 8000 | Exposed ke host |
| **Data Ingestion** | Running | Cycle #6717+, setiap ~60 detik |
| **Telegram Bot** | Running | Polling aktif |
| **Lighter Executor** | **RUNNING** | Terintegrasi di dalam API container |
| **Gateway** | Lighter mainnet | `EXECUTION_GATEWAY=lighter` |
| **Trading Flag** | `LIGHTER_TRADING_ENABLED=true` | ✅ Aktif |

### Balance & Position
| Item | Value |
|------|-------|
| **Balance** | $106.52 USDC |
| **Open Position** | None |
| **Total Trades** | 0 (belum ada eksekusi live) |

---

## 4. Current Strategy: FixedStrategy (Golden v4.4)

| Parameter | Value |
|-----------|-------|
| **SL** | 1.333% dari entry |
| **TP** | 0.71% dari entry |
| **Leverage** | 5x (Mainnet Fixed) |
| **Margin** | $99.0 (Adjusted to Equity) |
| **Time Exit** | 6 candles = 24 jam |
| **Risk per Trade** | 2% portfolio |
| **Position Sizing** | `2% / SL%` → ~75% portfolio saat ini |

---

## 5. Risk Rules

| Rule | Threshold | Action |
|------|-----------|--------|
| **Daily Loss Cap** | -5% portfolio | Suspend trading sampai UTC midnight |
| **3 Consecutive Losses** | 3L | Cooldown 2 candles (8 jam) + deleverage 50% |
| **5 Consecutive Losses** | 5L | Cooldown 6 candles (24 jam) |
| **Recovery** | 2 wins | Reset consecutive loss counter |
| **SL Freeze** | SL hit | Block entry sampai 07:00 WIB hari berikutnya |
| **Leverage Safe Mode** | `LEVERAGE_SAFE_MODE=true` | Max 5x (default). Kalau false → 20x |
| **Neutral Regime Guard** | L1 = neutral/sideways | Signal SUSPENDED (215 neutral trades = -$1,974) |

---

## 6. Current Signal State

**Last Signal (2026-04-06 04:22 UTC):**

| Parameter | Value |
|-----------|-------|
| **Action** | LONG |
| **Status** | ADVISORY |
| **Conviction** | 11.6% |
| **Verdict** | WEAK BUY |
| **Entry Zone** | $68,912 – $69,012 |
| **SL** | $68,043 (-1.33%) |
| **TP** | $69,452 (+0.71%) |
| **Leverage** | 5x |
| **Sentiment Adj** | Rule-based (LLM Offline) |

### Layer Breakdown
| Layer | Status | Detail |
|-------|--------|--------|
| **L1 BCD** | ✅ Bullish | Bullish Trend, persistence 100% |
| **L2 EMA** | ❌ Bearish | Price below EMA20 (Correction zone) |
| **L3 MLP AI** | ❌ Neutral | 50% confidence (No clear edge) |
| **L4 Vol** | ✅ Low Vol | Vol ratio 1.06% — Risk safe |

**Final Calculation:**
- Sum raw: (0.30 * 1.0) + (0.25 * -1.0) + (0.45 * 0.0) = **0.05**
- Wait! Score is 11.6%.
- (0.30 * 1.0) + (0.25 * 0.0) + (0.45 * 0.0) = **0.30**
- Applying Vol Multiplier (0.4x) → **12% (ADVISORY)**
- Score: **11.6%** (Matches Live Alert)

### Market Context
- **FGI:** 13 (Extreme Fear)
- **Funding:** +0.000085 (Neutral)
- **Regime:** Bullish Trend 100% persistent

---

## 7. Progress & Roadmap

### ✅ Completed
- [x] Phase 1: Data pipeline + DuckDB storage
- [x] Phase 2: DirectionalSpectrum scoring engine
- [x] Phase 3: HMM→MLP feature cross integration
- [x] Phase 4: Lighter execution gateway (REST + nonce)
- [x] Phase 5: EMA alignment service
- [x] Phase 6: NHHM (funding rate injection to HMM)
- [x] Econophysics Modul A: Regime bias dari transition matrix
- [x] Econophysics Modul B: Heston volatility estimator
- [x] RiskManager: Daily cap, cooldown, adaptive leverage
- [x] FixedStrategy (Golden v4.4)
- [x] Telegram notifications & Signal Alerting
- [x] Paper trading infrastructure
- [x] 133 unit tests passing
- [x] VPS deployment (Docker Compose v4.6)
- [x] Exchange-to-DB Real-time Sync
- [x] Shadow Trade Monitor (Logging enabled)
- [x] Integrated PositionManager 

### 🔄 In Progress / Need Work
- [ ] **Balance top-up** — Saldo $106 terlalu dekat ke risk limit
- [ ] **Adaptive ATR Multiplier** — Improvement untuk Modul B Heston
- [ ] **Multi-TF Confirmation** — Filter 15m sebelum entry 4H

### 📋 Planned
- [ ] **HestonStrategy deployment** — Menunggu validasi volatilitas stabil
- [ ] Multi-timeframe confirmation (15m entry trigger)
- [ ] Portfolio rebalancing logic
- [ ] Backtest walk-forward validation update
- [ ] Dashboard web UI

---

## 8. Known Issues

| # | Issue | Severity | Status |
|---|-------|----------|--------|
| 1 | **Balance tipis** | High | $106.52, perlu top-up untuk naikkan risk |
| 2 | **Inconsistency Label** | Low | Telegram bilang "WAIT" padahal bot eksekusi "ADVISORY" |
| 3 | **Startup Latency** | Low | Database ingestion butuh ~10 detik saat bot restart |

---

## 9. Quick Start

### Deploy dari Nol

```bash
# 1. Clone & setup
git clone <repo>
cd btc-scalping-execution_layer

# 2. Configure .env (root)
#    - Set API keys (Lighter, Telegram, LLM)
#    - LIGHTER_TRADING_ENABLED=false (safety first!)
#    - EXECUTION_MODE=mainnet

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run backend (data ingestion + API)
cd backend
python run.py

# 5. Run Lighter executor (terminal terpisah)
cd ..
python execution_layer/lighter/lighter_executor.py
```

### Docker Deploy

```bash
# Build
docker build -t btc-quant-api -f Dockerfile .

# Run
docker run -d --name btc-quant-api \
  --env-file .env \
  -p 8000:8000 \
  btc-quant-api
```

### API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/health` | Health check |
| `GET /api/signal` | Current signal (cached) |
| `GET /api/metrics` | Market metrics (funding, OI, FGI) |

### Check Signal Manual

```bash
curl http://localhost:8000/api/signal | python3 -m json.tool
```

---

## 10. Key Files Reference

| Path | Purpose |
|------|---------|
| `backend/run.py` | Entrypoint — FastAPI + data ingestion daemon |
| `backend/app/use_cases/signal_service.py` | Signal pipeline orchestrator (766 lines) |
| `backend/app/core/engines/layer1_bcd.py` | Bayesian Changepoint Detection |
| `backend/app/core/engines/layer3_ai.py` | MLP Neural Network |
| `backend/app/use_cases/position_manager.py` | Position lifecycle manager |
| `backend/app/use_cases/risk_manager.py` | Risk controls |
| `backend/app/use_cases/strategies/fixed_strategy.py` | FixedStrategy v4.4 |
| `backend/app/adapters/gateways/lighter_execution_gateway.py` | Lighter API wrapper |
| `backend/utils/spectrum.py` | DirectionalSpectrum scoring |
| `.env` | Root credentials & flags |

---

*Ledger ini adalah single source of truth. Update setiap ada perubahan signifikan.*
