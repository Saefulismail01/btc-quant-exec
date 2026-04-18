# BTC-QUANT Execution Layer

Live trading bot execution layer for Bitcoin on Lighter mainnet with Renaissance Technologies research framework.

**Status**: ✅ Phase 4 Production - [v4.8] Live (Trailing SL Active)

---

## 📂 Directory Structure (Optimized)

```
btc-scalping-execution_layer/
│
├── 🔴 backend/              # PRODUCTION - Core API & Services
│   ├── app/                 # Logic: Signal, Position, Risk Management
│   └── scripts/             # Production tools (auto scalp, HFT)
│
├── 🔌 execution_layer/      # EXECUTION GATEWAY (Lighter Mainnet)
│   └── lighter/             # Signal Executor & Intraday Monitor (v4.8)
│
├── 🔬 cloud_core/           # RESEARCH ENGINE (Safe to Modify)
│   ├── engines/             # Alternative Models (LightGBM, XGBoost, LSTM)
│   └── colab_core.ipynb     # Research playground for Google Colab
│
├── 🎨 frontend/             # MONITORING DASHBOARD (Vite + React)
│
├── 📚 docs/                 # DOCUMENTATION & Reports
│   ├── reports/             # Live trading logbooks & performance
│   └── PROJECT_LOGBOOK.md   # [Root Source of Truth] Evolution & History
│
└── 🗄️ archive/              # ARCHIVED STUFF (Legacy codes & experiments)
```

---

## 🎯 System Overview (v4.8 Updates)

BTC-QUANT is a **High-Frequency Scalping Bot** executing on Lighter mainnet, now featuring **Exchange-First Architecture**:
- **Signal Executor (v4.8)**: Acts as the primary execution engine. It handles trade execution, verifies **SL Freeze state**, and manages **Order ID Tracking**.
- **Intraday Monitor**: Runs a **15-minute cycle** to monitor open positions and execute **Trailing SL** (trails when profit > 1%, locking min 0.5% profit).
- **Ensemble Intelligence**: Combines Bayesian Changepoint Detection (BCD), EMA Momentum, and MLP Neural Networks for >55% accuracy.
- **Risk Shield**: Hard-coded SL Freeze mechanism that stops all entries until 07:00 WIB the next day if a Stop Loss is hit.

---

## ⚡ Recent Updates (April 2026)

- **[2026-04-18] Repository Optimization**:
  - Removed `node_modules` and heavy binaries from Git tracking.
  - History squashed for lightweight cloning and performance.
  - Updated `.gitignore` for better development hygiene.
- **[2026-04-12] v4.8 Deployment**:
  - Implemented **Order ID Tracking** via `order_ids.json`.
  - Added **Dynamic Trailing SL** (Cancel + Create pattern).
  - Fixed **Minute Overflow** bug in Intraday monitoring.
- **[2026-04-11] Cloud Core & Exchange-First**:
  - Exchange is now the **Source of Truth** for positions (Triple-checked).
  - Launched `cloud_core/` as a standalone research engine for rapid model testing.

---

## 🚀 Key Features

| Feature | Status | Details |
|---------|--------|---------|
| **Live Trading** | ✅ | Lighter Mainnet (BTC/USDC) |
| **Trailing SL** | ✅ | ATR-Adaptive + 1.0% Profit Lock |
| **SL Freeze** | ✅ | Cross-service safety (API & Executor) |
| **Research Arena** | ✅ | Standalone `cloud_core` with 5+ model types |
| **Notifications** | ✅ | Telegram: /signal, /balance, /status |

---

## 🛠️ Quick Start

### Check System Status
```bash
rtk git status # Verification: Repo should be clean and ahead/synced
```

### Run Production Executor
```bash
# Recommended: Use Docker for production
docker-compose up -d signal-executor intraday-monitor
```

### Research Mode (Safe Experimentation)
```bash
cd cloud_core
python model_evaluator.py
```

---

## 🏗️ Path to Production (Safety First)
1. Develop & Backtest in `cloud_core/`.
2. Win Rate must be > 60% (or PF > 1.3).
3. 2 Weeks Paper Trading in `cloud_core/`.
4. Replace MLP engine in `backend/app/core/engines/layer3_ai.py`.

---

**Status**: ✅ Production Running — v4.8 Active  
**Last Updated**: April 18, 2026
**Maintainer**: Mail (dev@instagram-dashboard.com)
