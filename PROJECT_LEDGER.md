# BTC-QUANT v4.6 — Project Ledger

> **Last Updated:** 2026-04-06 04:50 UTC
> **Status:** Phase 4 Mainnet — Live Execution Active
> **BTC Price:** $69,055 | **FGI:** 13 (Extreme Fear)

---

## 1. Executive Summary

BTC-QUANT adalah bot scalping Bitcoin perpetuals di **Lighter mainnet** (L2 ZK orderbook DEX). Sistem menggunakan 5-layer signal pipeline berbasis riset Renaissance Technologies + econophysics untuk menghasilkan sinyal LONG/SHORT dengan conviction scoring.

**Saat ini:** Data ingestion, API server, dan PositionManager berjalan terintegrasi di Docker. Lighter execution aktif. Sinkronisasi SL/TP bursa riil aktif.

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Signal Pipeline                       │
│                                                         │
│  L1: BCD (Bayesian Changepoint)  → Regime detection     │
│  L2: EMA Alignment               → Trend confirmation   │
│  L3: MLP Neural Network          → Next-candle predict  │
│  L4: Heston Volatility           → SL/TP sizing         │
│  L5: Narrative Engine (LLM)      → Verdict synthesis    │
│                                                         │
│         ↓ DirectionalSpectrum ↓                         │
│    directional_bias [-1, +1] + conviction_pct           │
│    Trade Gate: ACTIVE / ADVISORY / SUSPENDED            │
└─────────────────────────────────────────────────────────┘
         ↓
┌──────────────────────┐     ┌──────────────────────────┐
│  FastAPI + Ingestion │     │  PositionManager (Inside)│
│  (Docker container)  │<───>│  (INTEGRATED & LIVE)      │
│  - Fetch OHLCV 60s   │     │  - Sync Exchange Orders   │
│  - Compute signal    │     │  - RiskManager            │
│  - Cache signal      │     │  - LighterExecutionGateway│
│  - Telegram bot      │     │  - Order placement        │
└──────────────────────┘     └──────────────────────────┘
         ↓                              ↓
┌──────────────────────┐     ┌──────────────────────────┐
│  API (port 8000)     │     │  Lighter Mainnet          │
│  /api/health         │     │  BTC/USDC perpetuals      │
│  /api/signal         │     │                           │
│  /api/metrics        │     │                           │
└──────────────────────┘     └──────────────────────────┘
```

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

## 4. Current Strategy: HestonStrategy (v4.6 Adaptive)

| Parameter | Value |
|-----------|-------|
| **SL** | ATR-Adaptive (Model Heston) |
| **TP** | ATR-Adaptive (Model Heston) |
| **Leverage** | 15x (Fixed for Live) |
| **Margin** | $5 (Testing) per trade |
| **Time Exit** | 6 candles = 24 jam |
| **Risk per Trade** | Dynamic (via RiskManager) |
| **Position Sizing** | Real Balance Tracking |

### Heston SL/TP Preset (Modul A+B)
Saat ini menggunakan **Scalper-Normal**:
- SL multiplier: 1.5x ATR
- TP1 multiplier: 2.1x ATR
- TP2 multiplier: 3.15x ATR

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

**Last Signal (2026-04-06 03:42 UTC):**

| Parameter | Value |
|-----------|-------|
| **Action** | LONG |
| **Status** | ADVISORY |
| **Conviction** | 11.6% |
| **Verdict** | WEAK BUY |
| **Entry Zone** | $68,908 – $69,055 |
| **SL** | $67,955 |
| **TP1** | $70,595 |
| **TP2** | $71,365 |
| **Leverage** | 2x |
| **Sentiment Adj** | 0.75 (FGI 13 = Extreme Fear) |

### Layer Breakdown
| Layer | Status | Detail |
|-------|--------|--------|
| **L1 BCD** | ✅ Aligned | Bullish Trend, persistence 100% |
| **L2 EMA** | ❌ Not aligned | Weak/Correction — price below EMA20 |
| **L3 MLP** | ❌ NEUTRAL | 50% confidence — model tidak bisa decide |
| **L4 Risk** | ✅ Aligned | Vol Low (1.06%) — SL Safe |

**Score:** 50/100 (2/4 layers aligned)

### Market Context
- **FGI:** 13 (Extreme Fear) → sentiment_adj = 0.75
- **Funding:** +0.000085 (netral)
- **L/S Ratio:** Balanced
- **OI:** 92,593 BTC
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
- [x] Telegram notifications
- [x] Paper trading infrastructure
- [x] 133 unit tests passing
- [x] VPS deployment (Docker Compose)
- [x] Exchange-to-DB Sync (v4.6)
- [x] Integrated PositionManager

### 🔄 In Progress / Need Work
- [ ] **LLM integration** — Deepseek API key perlu divalidasi ke container
- [ ] **Balance top-up** — Perlu tambahan untuk menaikkan margin
- [x] **Shadow trade monitor** — ACTIVE (Logging enabled)

### 📋 Planned
- [x] HestonStrategy (dynamic SL/TP berbasis vol regime)
- [ ] Multi-timeframe confirmation (15m entry trigger)
- [ ] Portfolio rebalancing logic
- [ ] Backtest walk-forward validation update
- [ ] Dashboard web UI

---

## 8. Known Issues

| # | Issue | Severity | Status |
|---|-------|----------|--------|
| 1 | **Balance tipis** | High | $106.52, perlu top-up untuk naikkan risk |
| 2 | **LLM unavailable** | Medium | Fallback ke rule-based masih berjalan |
| 3 | **Label Inconsistency** | Low | Label "WAIT" di Telegram untuk sinyal ADVISORY |
| 7 | **Telegram bot offset stuck** — `offset=552185895` tidak berubah, kemungkinan ada issue | Low | Monitoring |

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
| `execution_layer/lighter/lighter_executor.py` | Lighter execution daemon |
| `execution_layer/lighter/lighter_execution_gateway.py` | Lighter API wrapper |
| `utils/spectrum.py` | DirectionalSpectrum scoring |
| `.env` | Root credentials & flags |

---

*Ledger ini adalah single source of truth. Update setiap ada perubahan signifikan.*
