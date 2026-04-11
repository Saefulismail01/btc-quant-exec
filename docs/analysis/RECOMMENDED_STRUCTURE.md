# Struktur Direktori Yang Direkomendasikan

## Struktur Ideal (Clean & Organized)

```
btc-scalping-execution_layer/
│
├── 📁 core/                          ← **ENGINE INTI (Layer 1-4)**
│   ├── engines/
│   │   ├── layer1_regime.py        # Market regime (HMM/GMM)
│   │   ├── layer2_trend.py         # Trend confirmation (EMA/SMA)
│   │   ├── layer3_ml/              # ML Models (semua di sini)
│   │   │   ├── logistic.py         # 🏆 Recommended
│   │   │   ├── lightgbm.py
│   │   │   ├── xgboost.py
│   │   │   └── mlp.py
│   │   ├── layer4_risk.py          # Risk management
│   │   └── spectrum.py             # Aggregator
│   ├── data/
│   │   ├── fetcher.py              # Binance/CCXT
│   │   └── csv_loader.py           # Local CSV
│   ├── signal_service.py           # Main orchestrator
│   └── config.py                   # Settings & constants
│
├── 📁 execution/                    ← **TRADE EXECUTION**
│   ├── gateways/
│   │   ├── binance_gateway.py      # Binance API
│   │   └── lighter_gateway.py      # Lighter SDK
│   ├── risk_manager.py             # Position sizing
│   └── order_executor.py           # SL/TP management
│
├── 📁 research/                     ← **RESEARCH & BACKTEST**
│   ├── models/                      # Model experiments
│   │   ├── evaluator.py
│   │   └── trainer.py
│   ├── backtest/
│   │   ├── engine.py               # Walk-forward
│   │   └── metrics.py              # Sharpe, drawdown, etc
│   └── notebooks/
│       └── research.ipynb          # Colab compatible
│
├── 📁 ops/                          ← **OPERATIONS**
│   ├── monitoring/
│   │   ├── health_check.py
│   │   └── alerts.py               # Telegram notifications
│   ├── deployment/
│   │   ├── docker-compose.yml
│   │   └── Dockerfile
│   └── scripts/
│       ├── setup_env.py
│       └── data_backfill.py
│
├── 📁 tests/                        ← **UNIT & INTEGRATION TESTS**
│   ├── unit/
│   │   ├── test_engines.py
│   │   └── test_execution.py
│   └── integration/
│       └── test_full_pipeline.py
│
├── 📁 docs/                         ← **DOCUMENTATION**
│   ├── ARCHITECTURE.md
│   ├── API.md
│   ├── MODEL_RESEARCH.md           # Hasil riset model
│   └── DEPLOYMENT.md
│
├── 📁 archive/                      ← **OLD/UNUSED FILES**
│   ├── backend_legacy/              # Old backend (sebelum refactor)
│   ├── experiments/                 # One-off scripts
│   └── papers/                      # Econophysics references
│
├── 📝 README.md                     # Main documentation
├── 📝 .env.example                  # Template env vars
├── 📝 requirements-core.txt         # Minimal dependencies
├── 📝 requirements-ml.txt             # ML libraries
└── 📝 requirements-dev.txt            # Dev tools
```

---

## Perbandingan: Current vs Recommended

### Current (Berdasarkan Analisis Tadi)
```
btc-scalping-execution_layer/
├── backend/              (115 items - terlalu besar)
├── backtest/             (183 items - dump folder)
├── cloud_core/           (34 items - ✅ bagus)
├── docs/                 (90 items - tersebar)
├── execution_layer/      (18 items - ✅ bagus)
├── frontend/             (22 items - secondary)
├── learn/                (108 items - learning materials)
├── research/             (115 items - dump folder)
├── rtk/                  (247 items - terbesar!)
└── [26+ loose files]     (script-test tersebar)
```

**Masalah:**
- ❌ 8 folder utama (terlalu banyak)
- ❌ 500+ items di folder sekunder
- ❌ Script test/debug tersebar di berbagai tempat
- ❌ Duplikasi (backend vs cloud_core)

### Recommended (Clean)
```
btc-scalping-execution_layer/
├── core/                 (40 items - Layer 1-4 + Data)
├── execution/            (20 items - Trade execution)
├── research/             (30 items - Model research)
├── ops/                  (15 items - Deployment)
├── tests/                (20 items - All tests)
├── docs/                 (10 items - Consolidated)
├── archive/              (600+ items - Old files)
└── [5 config files]
```

**Keuntungan:**
- ✅ 7 folder utama saja
- ✅ Separation of concerns jelas
- ✅ Archive folder untuk file lama
- ✅ Semua script penting di `core/`

---

## Langkah Migrasi

### Step 1: Buat Struktur Baru
```bash
mkdir -p core/engines/layer3_ml
mkdir -p core/data
mkdir -p execution/gateways
mkdir -p research/{models,backtest,notebooks}
mkdir -p ops/{monitoring,deployment,scripts}
mkdir -p tests/{unit,integration}
mkdir -p docs
mkdir -p archive/{backend_legacy,experiments,papers}
```

### Step 2: Pindahkan Core Files
```bash
# Core engines (dari cloud_core/)
mv cloud_core/engines/*.py core/engines/
mv cloud_core/signal_service.py core/
mv cloud_core/data/ core/
mv cloud_core/config.py core/

# Layer 3 ML models
mkdir core/engines/layer3_ml
mv core/engines/layer3_logistic.py core/engines/layer3_ml/logistic.py
mv core/engines/layer3_mlp.py core/engines/layer3_ml/mlp.py
mv core/engines/layer3_xgboost.py core/engines/layer3_ml/xgboost.py
mv core/engines/layer3_lightgbm.py core/engines/layer3_ml/lightgbm.py
```

### Step 3: Archive Folder Besar
```bash
# Archive old folders
mv backend/ archive/backend_legacy/
mv backtest/ archive/
mv research/ archive/papers/
mv rtk/ archive/
mv learn/ archive/
mv frontend/ archive/  # if not used
```

### Step 4: Consolidate Scripts
```bash
# Keep only important scripts
mkdir -p ops/scripts
mv backend/scripts/auto_scalp.py ops/scripts/
mv backend/scripts/data_engine.py ops/scripts/
mv backend/scripts/walk_forward.py ops/scripts/

# Archive the rest
mv backend/scripts/hft_bot.py archive/experiments/
mv backend/scripts/scalp_v2.py archive/experiments/
# ... etc
```

### Step 5: Consolidate Docs
```bash
# Merge all docs
cat SYSTEM_FLOW.md >> docs/ARCHITECTURE.md
cat PROJECT_LEDGER.md >> docs/ARCHITECTURE.md
cat cloud_core/RESEARCH_RESULTS.md >> docs/MODEL_RESEARCH.md
cat LIBRARY_DOCUMENTATION_INDEX.md >> docs/API.md

# Remove duplicates
rm SYSTEM_FLOW.md PROJECT_LEDGER.md LIBRARY_DOCUMENTATION_INDEX.md
```

---

## Prioritas File (Setelah Migrasi)

### 🔴 Critical (Tidak Boleh Hilang)
```
core/
├── signal_service.py
├── engines/
│   ├── layer1_regime.py
│   ├── layer2_trend.py
│   ├── layer3_ml/logistic.py  # 🏆
│   └── layer4_risk.py
└── data/fetcher.py

execution/
└── gateways/
    ├── binance_gateway.py
    └── lighter_gateway.py
```

### 🟡 Important (Secondary)
```
core/engines/layer3_ml/
├── lightgbm.py          # Alternative model
├── xgboost.py           # Alternative model
└── ensemble.py          # Model combiner

research/
├── models/evaluator.py
└── backtest/engine.py
```

### 🟢 Optional (Nice to Have)
```
ops/monitoring/
├── health_check.py
└── alerts.py            # Telegram

frontend/                # Only if using web UI
```

---

## Keuntungan Struktur Baru

### 1. **Fokus Jelas**
- `core/` = Signal generation only
- `execution/` = Trade execution only
- `research/` = Backtest & model research
- `ops/` = Production operations

### 2. **Maintenance Mudah**
- Semua engine di satu tempat
- Archive folder untuk file lama
- Tidak ada duplikasi

### 3. **Onboarding Cepat**
- Struktur intuitif
- Dokumentasi konsolidated
- No hunting for files

### 4. **Deploy Lebih Cepat**
- Hanya `core/` + `execution/` yang di-deploy
- `research/` tidak ikut ke production
- Docker image lebih kecil

---

## Estimasi Ukuran Setelah Cleanup

| Component | Current | After | Reduction |
|-----------|---------|-------|-----------|
| Core files | ~150 | ~50 | 67% |
| Test files | ~30 | ~20 | 33% |
| Docs | ~90 | ~10 | 89% |
| Archive | 0 | ~600 | N/A |
| **Total Active** | **~270** | **~80** | **70%** |

**Hasil:** 70% reduction in active codebase, lebih mudah maintain.

---

## Scripts Helper

Saya bisa bantu buat:
1. **migration_script.py** - Automate pemindahan file
2. **cleanup_script.sh** - Archive file lama
3. **verify_structure.py** - Check apakah struktur benar

Mau saya buatkan script migrasi otomatisnya?
