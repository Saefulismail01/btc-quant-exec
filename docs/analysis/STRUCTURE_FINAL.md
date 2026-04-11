# Struktur Final: Production (Sacred) vs Research

## 🎯 Status Model

| Model | Lokasi | Status |
|-------|--------|--------|
| **MLP** | `prod/engine/layer3_ml/mlp.py` | 🚫 **PRODUCTION - JANGAN DIUBAH** |
| Logistic | `research/models/experiments/logistic.py` | 🔬 Research |
| LightGBM | `research/models/experiments/lightgbm.py` | 🔬 Research |
| XGBoost | `research/models/experiments/xgboost.py` | 🔬 Research |
| LSTM | `research/models/experiments/lstm.py` | 🔬 Research |
| Rule-Based | `research/models/experiments/rule_based.py` | 🔬 Research |

---

## 📁 Struktur Direktori Final

```
btc-scalping-execution_layer/
│
├── 🔴 prod/                        ← 🚫 SACRED - DO NOT MODIFY
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── src/
│   │   ├── engine/
│   │   │   ├── __init__.py
│   │   │   ├── layer1_bcd.py          # Regime detection
│   │   │   ├── layer2_ema.py          # Trend confirmation
│   │   │   ├── layer3_ml/
│   │   │   │   ├── __init__.py
│   │   │   │   └── mlp.py             # 🏆 PRODUCTION MODEL
│   │   │   ├── layer4_risk.py         # Risk management
│   │   │   └── spectrum.py            # Aggregator
│   │   ├── execution/
│   │   │   ├── binance_gateway.py
│   │   │   ├── lighter_gateway.py
│   │   │   └── order_manager.py
│   │   ├── risk/
│   │   │   ├── position_sizing.py
│   │   │   └── sl_calculator.py
│   │   ├── notify/
│   │   │   ├── telegram_bot.py
│   │   │   └── templates/
│   │   └── main.py                    # Entry point
│   └── tests/
│       └── test_integration.py
│
├── 🔵 research/                    ← 🔬 PLAYGROUND - OK TO MODIFY
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── src/
│   │   └── models/
│   │       ├── experiments/           # <- SEMUA model baru
│   │       │   ├── __init__.py
│   │       │   ├── logistic.py        # 53.8% accuracy (tested)
│   │       │   ├── lightgbm.py        # 53.3% accuracy (tested)
│   │       │   ├── xgboost.py         # 52.8% accuracy (tested)
│   │       │   ├── lstm.py
│   │       │   ├── random_forest.py
│   │       │   └── rule_based.py
│   │       │
│   │       └── candidates/            # <- Kalau sudah bagus
│   │           └── [empty - waiting for >60% model]
│   │
│   ├── notebooks/
│   │   ├── model_comparison.ipynb
│   │   ├── feature_analysis.ipynb
│   │   └── backtest.ipynb
│   │
│   ├── backtest/
│   │   ├── engine.py
│   │   └── strategies/
│   │
│   └── results/
│       ├── models/                    # Saved model files
│       └── reports/                   # Generated reports
│
├── 📁 shared/                      ← ⚠️ SHARED (read-only from prod)
│   ├── config/
│   │   ├── settings.yaml
│   │   └── constants.py
│   ├── types/
│   │   └── dataclasses.py
│   └── utils/
│       ├── time.py
│       └── math.py
│
├── 📁 data/                        ← 💾 SHARED DATA
│   ├── market/                       # OHLCV cache
│   ├── db/                           # SQLite/Postgres
│   └── logs/                         # Application logs
│
├── 📁 ops/                         ← 🔧 OPERATIONS
│   ├── monitoring/
│   │   ├── health_check.py
│   │   └── prometheus.yml
│   └── deployment/
│       └── docker-compose.yml
│
├── 📁 tests/                       ← 🧪 ALL TESTS
│   ├── prod/                         # Production tests
│   │   └── test_mlp.py
│   └── research/                     # Research tests
│       └── test_new_models.py
│
├── 📁 docs/                        ← 📚 DOCUMENTATION
│   ├── ARCHITECTURE.md
│   ├── PRODUCTION_SETUP.md
│   └── RESEARCH_GUIDE.md
│
├── 📁 archive/                     ← 🗄️ OLD FILES
│   └── [legacy folders]
│
├── docker-compose.yml              # Main orchestration
├── Makefile                        # Commands
└── README.md                       # Quick start
```

---

## 🚫 Rules untuk Production (`prod/`)

### File yang JANGAN DIUBAH:
- `prod/src/engine/layer3_ml/mlp.py` ← 🚫 Model yang running live
- `prod/src/engine/layer1_bcd.py` ← 🚫 Regime detection
- `prod/src/engine/layer2_ema.py` ← 🚫 Trend confirmation
- `prod/src/engine/layer4_risk.py` ← 🚫 Risk calculator
- `prod/src/engine/spectrum.py` ← 🚫 Aggregator
- `prod/src/execution/` ← 🚫 All execution code
- `prod/src/risk/` ← 🚫 Risk management
- `prod/src/notify/` ← 🚫 Telegram notifications

### Boleh Diubah:
- `prod/src/notify/templates/` ← ✅ Message templates
- `prod/tests/` ← ✅ Add more tests
- `prod/requirements.txt` ← ⚠️ Careful (bug fixes only)

---

## 🔬 Rules untuk Research (`research/`)

### Bebas Diubah:
- `research/src/models/experiments/*` ← ✅ All new models
- `research/notebooks/*` ← ✅ Jupyter notebooks
- `research/backtest/*` ← ✅ Backtest strategies
- `research/results/*` ← ✅ Generated outputs

### Workflow:
```
1. Eksperimen di research/models/experiments/
2. Backtest & validate
3. Kalau >60% accuracy → pindah ke candidates/
4. Paper trading 1 bulan
5. Kalau profit → proposal untuk ganti MLP di prod
```

---

## 🔄 Path: Research → Production (STRICT)

```
research/models/experiments/logistic.py
            ↓
    [Test dengan local_evaluator.py]
            ↓
    Accuracy > 60% ?
    ├── YES → Pindah ke research/models/candidates/logistic_v1.py
    └── NO  → Stay di experiments/ atau improve
            ↓
    [Paper trading 1 bulan]
    Profit > 0% ?
    ├── YES → Proposal ke prod
    └── NO  → Back to experiments/
            ↓
    [Code review & testing]
    ├── Integration test
    ├── Security review
    └── Performance benchmark
            ↓
    [Staging deploy]
    Run parallel dengan MLP 1 minggu
    Compare performance
            ↓
    [Decision]
    New model > MLP ?
    ├── YES → Replace prod/src/engine/layer3_ml/mlp.py
    └── NO  → Keep MLP, model baru stay di candidates/
```

---

## 🛡️ Protection

### Git Rules:
```yaml
# prod/src/engine/layer3_ml/* - Protected
code_owners:
  - @lead-dev
  - @quant-researcher

required_checks:
  - integration_tests
  - backtest_validation
  - security_scan

# research/* - Open
code_owners: anyone
required_checks: none
```

---

## 📊 Summary

| Area | Contains | Modify? |
|------|----------|---------|
| `prod/src/engine/layer3_ml/mlp.py` | 🏆 Production MLP | ❌ NO |
| `prod/src/engine/*` (other layers) | Core engine | ❌ NO |
| `prod/src/execution/` | Trade execution | ❌ NO |
| `prod/src/risk/` | Risk management | ❌ NO |
| `prod/src/notify/` | Notifications | ⚠️ Templates only |
| `research/models/experiments/` | New models | ✅ YES |
| `research/notebooks/` | Analysis | ✅ YES |
| `research/backtest/` | Testing | ✅ YES |

---

## 🎯 Golden Rule

> **"MLP di prod/ adalah yang running live. Semua eksperimen (Logistic, LightGBM, dll) di research/. Kalau ada model baru yang lebih bagus dari MLP, lewati full validation dulu sebelum replace."**

---

**Struktur ini sudah final. MLP di production, semua model baru di research.**
