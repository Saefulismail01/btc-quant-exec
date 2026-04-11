# BTC-QUANT Execution Layer

Live trading bot execution layer for Bitcoin on Lighter mainnet with Renaissance Technologies research framework.

**Status**: ✅ Phase 3 Mainnet - Production Running

---

## � Directory Structure (Cleaned)

```
btc-scalping-execution_layer/
│
├── 🔴 backend/              (115 items)  ← PRODUCTION - Do Not Modify
│   ├── app/
│   │   ├── core/engines/
│   │   │   └── layer3_ai.py           # 🏆 MLP Model (Running Live)
│   │   ├── use_cases/                 # Signal, Position, Risk
│   │   └── adapters/gateways/         # Execution gateways
│   └── scripts/                       # Auto scalp, HFT bot
│
├── 🔬 cloud_core/           (34 items)   ← RESEARCH - Safe to Modify
│   ├── engines/
│   │   ├── layer3_logistic.py         # 53.8% accuracy
│   │   ├── layer3_lightgbm.py         # 53.3% accuracy
│   │   ├── layer3_xgboost.py          # 52.8% accuracy
│   │   └── layer3_lstm.py             # Experimental
│   ├── model_evaluator.py             # Model comparison
│   └── colab_core.ipynb               # Jupyter research
│
├── 📚 docs/                (103 items)   ← DOCUMENTATION
│   ├── START_HERE.md
│   ├── analysis/                      # Structure analysis files
│   └── setup/                         # Setup guides
│
├── 🗄️ archive/             (499 items)  ← ARCHIVED
│   ├── old_stuff/                     # rtk/, learn/, research/
│   ├── scripts/                       # Cleanup scripts
│   └── paper/                         # Academic paper
│
├── 🔌 execution_layer/     (18 items)   ← EXECUTION
├── 🎨 frontend/            (22 items)   ← WEB UI
├── 📊 backtest/            (176 items)  ← BACKTEST DATA
│
└── ⚙️ [config & database]
    ├── .env
    ├── docker-compose.yml
    ├── btc-quant.db                     # Production DB
    └── README.md                        # This file
```

---

## 🎯 What Is This?

BTC-QUANT is a **live trading bot** that executes orders on Lighter mainnet for Bitcoin perpetuals, powered by:
- ✅ Renaissance Technologies algorithmic methods
- ✅ 4-Layer Ensemble Architecture (Layer 1-4)
- ✅ MLP Neural Network for signal generation
- ✅ Telegram notifications & monitoring

---

## 🚀 Key Features

| Feature | Status | Details |
|---------|--------|---------|
| **Live Trading** | ✅ | Mainnet execution on Lighter |
| **ML Model** | ✅ | MLP (layer3_ai.py) running production |
| **Risk Management** | ✅ | Position sizing, SL/TP |
| **Notifications** | ✅ | Telegram alerts |
| **Research** | ✅ | Model evaluation framework |

---

## 📖 Quick Access

### I want to trade (Production)
→ `backend/` - Production system
→ `backend/app/core/engines/layer3_ai.py` - MLP Model (Sacred)
→ `backend/scripts/auto_scalp.py` - Auto trading

### I want to research (New Models)
→ `cloud_core/` - Research arena
→ `cloud_core/engines/layer3_logistic.py` - Best research model (53.8%)
→ `cloud_core/model_evaluator.py` - Compare models
→ `cloud_core/colab_core.ipynb` - Jupyter experiments

### I need documentation
→ `docs/` - All documentation
→ `docs/START_HERE.md` - Entry point

### I want archived/old stuff
→ `archive/` - Old folders & files
→ `archive/old_stuff/` - rtk/, learn/, research/

---

## 🛠️ Quick Setup

### Test Production Connection
```bash
python backend/scripts/test_lighter_connection.py
```

### Run Production
```bash
cd backend
python live_executor.py
```

### Run Model Evaluation (Research)
```bash
cd cloud_core
python model_evaluator.py
```

### Run Quick Test (Research)
```bash
cd cloud_core
python quick_evaluator.py
```

---

## 📊 Project Statistics

- � **Production**: 115 files (backend/)
- � **Research**: 34 files (cloud_core/)
- �️ **Archived**: 499 files (archive/)
- � **Documentation**: 103 files (docs/)
- � **Database**: btc-quant.db (production)

---

## ⚠️ Important Rules

### 🔴 Production (`backend/`) - DO NOT MODIFY
- `backend/app/core/engines/layer3_ai.py` - MLP Model running live
- `backend/app/use_cases/` - Signal, Position, Risk managers
- `backend/app/adapters/gateways/` - Execution gateways
- `backend/scripts/` - Production scripts

### 🔬 Research (`cloud_core/`) - Safe to Modify
- All `layer3_*.py` models for experimentation
- `model_evaluator.py` - Test and compare models
- `colab_core.ipynb` - Jupyter notebook

### 🏆 Path to Production
1. Experiment in `cloud_core/engines/`
2. Backtest > 60% accuracy
3. Paper trading 1 month (profit)
4. Integration test
5. Replace MLP in `backend/`

---

## ⚙️ Configuration

Required: `.env` file (template: `.env.template`)

**Key variables**:
```
LIGHTER_MAINNET_API_KEY=...
LIGHTER_MAINNET_API_SECRET=...
LIGHTER_ACCOUNT_INDEX=...
LIGHTER_TRADING_ENABLED=false  # false by default (safe)
TELEGRAM_BOT_TOKEN=...
```

---

**Status**: ✅ Production Running — MLP Active  
**Last Updated**: April 11, 2026
