# Arsitektur: Production (Sacred) vs Research (Playground)

## 🎯 Konsep Utama

```
┌─────────────────────────────────────────────────────────────────┐
│                     PRODUCTION (SACRED)                          │
│              🚫 JANGAN DIUBAH - SUDAH VALIDATED                  │
├─────────────────────────────────────────────────────────────────┤
│  • Signal Engine (Layer 1-4)                                     │
│  • Trade Execution (Binance/Lighter)                             │
│  • Risk Management                                               │
│  • Telegram Notifications                                        │
│  • Position Lifecycle                                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     RESEARCH (PLAYGROUND)                      │
│              🔬 EKSPERIMEN - BOLEH OTAK-ATIK                   │
├─────────────────────────────────────────────────────────────────┤
│  • Model baru (LSTM, Transformer, etc)                          │
│  • Feature engineering experiments                               │
│  • Backtest historis                                           │
│  • Hyperparameter tuning                                       │
│  • Paper trading tests                                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📁 Struktur Direktori

```
btc-scalping-execution_layer/
│
├── 🔴 prod/                          ← 🚫 SACRED - DO NOT MODIFY
│   │
│   ├── engine/                      # Signal Generation Core
│   │   ├── layer1_regime.py         # HMM Market Regime
│   │   ├── layer2_trend.py          # EMA Confirmation
│   │   ├── layer3_ml/               # 🏆 VALIDATED MODELS
│   │   │   ├── __init__.py          # Exports only validated
│   │   │   └── logistic.py          # 🏆 Production Model
│   │   ├── layer4_risk.py           # Risk Calculator
│   │   └── spectrum.py              # Layer Aggregator
│   │
│   ├── execution/                   # Trade Execution
│   │   ├── binance_gateway.py       # Binance Futures
│   │   ├── lighter_gateway.py       # Lighter SDK
│   │   ├── order_manager.py         # SL/TP Management
│   │   └── position_tracker.py      # Position Lifecycle
│   │
│   ├── risk/                        # Risk Management
│   │   ├── position_sizing.py       # Kelly/Sizing algo
│   │   ├── sl_calculator.py         # Stop Loss logic
│   │   └── max_drawdown_guard.py    # Circuit breaker
│   │
│   ├── notify/                      # Notifications
│   │   ├── telegram_bot.py            # Telegram integration
│   │   ├── alert_manager.py         # Alert routing
│   │   └── templates/               # Message templates
│   │       ├── entry_alert.txt
│   │       ├── exit_alert.txt
│   │       └── error_alert.txt
│   │
│   ├── data/                        # Data Infrastructure
│   │   ├── fetcher.py               # Binance OHLCV
│   │   ├── validator.py             # Data quality check
│   │   └── cache.py                 # Local cache
│   │
│   └── main.py                      # Entry point production
│
├── 🔵 research/                      ← 🔬 PLAYGROUND - OK TO MODIFY
│   │
│   ├── models/                      # Model Experiments
│   │   ├── experiments/             # New model trials
│   │   │   ├── lstm_test.py
│   │   │   ├── transformer_test.py
│   │   │   └── attention_mechanism.py
│   │   ├── evaluator.py             # Model comparison
│   │   ├── trainer.py               # Training pipeline
│   │   └── validator.py             # Validation framework
│   │
│   ├── features/                    # Feature Engineering
│   │   ├── experiments/
│   │   │   ├── order_flow_features.py
│   │   │   ├── sentiment_analysis.py
│   │   │   └── on_chain_metrics.py
│   │   └── selector.py              # Feature selection
│   │
│   ├── backtest/                    # Backtesting
│   │   ├── engine.py                # Walk-forward
│   │   ├── strategies/              # Strategy variants
│   │   │   ├── aggressive.py
│   │   │   ├── conservative.py
│   │   │   └── regime_adaptive.py
│   │   └── reports/                 # Results (auto-generated)
│   │
│   ├── notebooks/                   # Jupyter/Colab
│   │   ├── model_research.ipynb
│   │   ├── feature_analysis.ipynb
│   │   └── backtest_analysis.ipynb
│   │
│   └── results/                     # Research Outputs
│       ├── model_comparison.json
│       ├── feature_importance.png
│       └── equity_curves/
│
├── 🟡 shared/                        ← ⚠️ SHARED COMPONENTS
│   │                                  # (Prod uses, Research extends)
│   ├── config/
│   │   ├── settings.py              # Environment config
│   │   └── constants.py             # Trading constants
│   ├── utils/
│   │   ├── math_helpers.py
│   │   ├── time_helpers.py
│   │   └── logging.py
│   └── types/
│       ├── signal_types.py          # Dataclasses
│       └── trade_types.py
│
├── 🟢 ops/                           ← 🔧 OPERATIONS
│   ├── deployment/
│   │   ├── docker-compose.prod.yml
│   │   ├── docker-compose.dev.yml
│   │   └── Dockerfile
│   ├── monitoring/
│   │   ├── health_check.py
│   │   ├── metrics_exporter.py
│   │   └── dashboard.json           # Grafana
│   └── scripts/
│       ├── setup.sh
│       └── data_backfill.py
│
├── 📝 docs/                          ← 📚 DOCUMENTATION
│   ├── PROD_README.md               # Production setup
│   ├── RESEARCH_GUIDE.md            # Research workflow
│   ├── API_REFERENCE.md
│   └── ARCHITECTURE.md
│
├── 📁 archive/                       ← 🗄️ OLD FILES
│   ├── backend_legacy/              # Pre-refactor
│   ├── old_backtests/
│   └── deprecated/
│
├── 🧪 tests/                         ← ✅ TESTS
│   ├── prod/                        # Production tests
│   │   ├── test_engine.py
│   │   ├── test_execution.py
│   │   └── test_integration.py
│   └── research/                    # Research tests
│       ├── test_models.py
│       └── test_features.py
│
├── .env.prod                         # Production secrets
├── .env.research                     # Research config
├── requirements-prod.txt             # Minimal deps
└── requirements-research.txt         # Full ML deps
```

---

## 🔴 Production (prod/) - Sacred Rules

### ✅ Boleh Dilakukan:
- Bug fixes (tanpa mengubah logika)
- Performance optimization
- Logging improvements
- Monitoring additions

### 🚫 JANGAN Dilakukan:
- Mengubah model architecture
- Mengubah signal weights
- Mengubah risk parameters
- Menambah dependency baru tanpa testing
- Direct commit ke `main` branch

### 📝 Workflow:
```
1. Production issue detected
2. Fix di branch `hotfix/xxx`
3. Testing di staging
4. PR dengan review strict
5. Merge ke `main`
6. Deploy dengan rollback plan
```

---

## 🔵 Research (research/) - Playground Rules

### ✅ Bebas Dilakukan:
- Eksperimen model baru
- Ganti-ganti hyperparameter
- Feature engineering crazy
- Hapus/tambah file sembarang
- Break things (it's ok!)

### 📋 Workflow:
```
1. Ide baru muncul
2. Buat branch `research/xxx`
3. Hack di `research/` folder
4. Backtest & validate
5. Kalau bagus → Proposal ke prod
6. Code review & integration
```

### 🔄 Path to Production:
```
research/models/experiments/lstm_test.py
              ↓ (validate & approved)
research/models/candidates/lstm.py
              ↓ (integration test)
prod/engine/layer3_ml/lstm.py ( baru di-add )
```

---

## 🔀 Alur Kerja Produksi vs Riset

### Scenario 1: Bug di Production
```bash
# Hotfix flow
$ git checkout -b hotfix/sl-calculation
# Edit: prod/risk/sl_calculator.py
# Test: tests/prod/test_risk.py
$ git commit -m "HOTFIX: Correct SL calculation edge case"
$ git push origin hotfix/sl-calculation
# PR → Review → Merge → Deploy
```

### Scenario 2: Eksperimen Model Baru
```bash
# Research flow
$ git checkout -b research/transformer-model
# Create: research/models/experiments/transformer.py
# Create: research/notebooks/transformer_analysis.ipynb
# Hack freely, no review needed
# Backtest di research/backtest/
$ git commit -m "WIP: Transformer architecture test"
$ git push origin research/transformer-model
```

### Scenario 3: Research → Production
```bash
# Integration flow (only when validated)
# 1. Model performs >60% accuracy di backtest
# 2. Paper trading 1 bulan profit
# 3. Proposal: "Add transformer as alternative L3"
# 4. Code review & security audit
# 5. Add to: prod/engine/layer3_ml/transformer.py
# 6. Update: prod/engine/layer3_ml/__init__.py
```

---

## 📊 File Status Cheat Sheet

| File Path | Status | Modify? |
|-----------|--------|---------|
| `prod/engine/layer3_ml/logistic.py` | 🏆 Production | ❌ No |
| `prod/execution/binance_gateway.py` | 🔴 Core | ❌ No |
| `prod/risk/sl_calculator.py` | 🔴 Core | ❌ No |
| `prod/notify/telegram_bot.py` | 🔴 Core | ❌ No |
| `research/models/experiments/*` | 🔬 Playground | ✅ Yes |
| `research/features/experiments/*` | 🔬 Playground | ✅ Yes |
| `research/backtest/strategies/*` | 🔬 Playground | ✅ Yes |
| `shared/config/settings.py` | ⚠️ Shared | ⚠️ Careful |
| `tests/prod/*` | ✅ Test | ✅ Yes |
| `ops/monitoring/*` | 🟢 Ops | ✅ Yes |

---

## 🚦 Decision Tree

```
Mau ngapain?
│
├── Fix bug di sistem live?
│   └── → Branch: hotfix/xxx
│   └── → Edit: prod/
│   └── → Testing: strict
│   └── → Review: required
│   └── → Deploy: careful
│
├── Eksperimen model baru?
│   └── → Branch: research/xxx
│   └── → Edit: research/
│   └── → Testing: backtest
│   └── → Review: none (self)
│   └── → Deploy: n/a
│
├── Tambah monitoring/alert?
│   └── → Branch: ops/xxx
│   └── → Edit: ops/
│   └── → Testing: staging
│   └── → Review: light
│   └── → Deploy: auto
│
└── Integrasi model riset ke prod?
    └── → Branch: integration/xxx
    └── → Source: research/
    └── → Target: prod/
    └── → Testing: full suite
    └── → Review: mandatory
    └── → Deploy: staged rollout
```

---

## 🔒 Protection Rules (GitHub/GitLab)

```yaml
# Branch: main (production)
protection_rules:
  require_pull_request: true
  required_approvers: 2
  require_tests_pass: true
  allow_force_push: false
  allow_deletion: false
  code_owner_approval: true

# Folder: prod/**
code_owners:
  - @lead-dev
  - @quant-researcher

# Folder: research/**
code_owners:
  - anyone  # No restrictions
```

---

## 🎯 Summary

| Area | Path | Status | Policy |
|------|------|--------|--------|
| **Production Engine** | `prod/engine/` | 🔴 Sacred | No change without approval |
| **Production Execution** | `prod/execution/` | 🔴 Sacred | No change without approval |
| **Production Risk** | `prod/risk/` | 🔴 Sacred | No change without approval |
| **Research Models** | `research/models/` | 🔬 Playground | Experiment freely |
| **Research Features** | `research/features/` | 🔬 Playground | Experiment freely |
| **Research Backtest** | `research/backtest/` | 🔬 Playground | Experiment freely |
| **Shared** | `shared/` | ⚠️ Shared | Careful changes |
| **Operations** | `ops/` | 🟢 Support | Flexible |

**Golden Rule:**
> "Jika code sudah menghasilkan profit di live trading, masukkan ke `prod/` dan jangan diubah. Eksperimen selalu di `research/`."
