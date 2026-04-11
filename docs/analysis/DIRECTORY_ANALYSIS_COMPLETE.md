# Analisis Direktori Lengkap: Production vs Research

## 📊 Hasil Eksplorasi Repository

**Tanggal:** 11 April 2026  
**Total File Python:** ~120+ files  
**Total Direktori:** 40+ folders

---

## 🔴 PRODUCTION SYSTEM (backend/) - 🚫 DO NOT MODIFY

### 1. Core Engine (`backend/app/core/engines/`)
```
backend/app/core/engines/
├── __init__.py                          [⚠️ Gateway exports]
├── layer1_bcd.py                        [🚫 Layer 1: Bayesian Changepoint - PRODUCTION]
├── layer1_volatility.py                 [🚫 Layer 1: Volatility regime - PRODUCTION]
├── layer2_ema.py                        [🚫 Layer 2: EMA Trend - PRODUCTION]
├── layer2_ichimoku.py                   [🚫 Layer 2: Ichimoku - PRODUCTION]
├── layer3_ai.py                         [🏆 MLP MODEL - CORE PRODUCTION]
├── layer5_sentiment.py                  [🚫 Layer 5: Sentiment - PRODUCTION]
└── experimental/                        [⚠️ Only this subfolder can be modified]
```

**CRITICAL:** `layer3_ai.py` berisi MLP yang running live - **JANGAN DIUBAH**

### 2. Use Cases / Business Logic (`backend/app/use_cases/`)
```
backend/app/use_cases/
├── __init__.py
├── ai_agent.py                          [🚫 AI Agent logic]
├── ai_service.py                        [🚫 AI Service orchestration]
├── bcd_service.py                       [🚫 BCD Layer 1 service]
├── data_ingestion_use_case.py           [🚫 Data pipeline]
├── ema_service.py                       [🚫 EMA Layer 2 service]
├── execution_notifier_use_case.py       [🚫 Execution notifications]
├── hmm_service.py                       [🚫 HMM service]
├── lighter_nonce_manager.py             [🚫 Lighter SDK nonce mgmt]
├── narrative_service.py                 [🚫 Narrative analysis]
├── paper_trade_service.py               [🚫 Paper trading logic]
├── position_manager.py                  [🚫 POSITION MANAGER - CORE]
├── risk_manager.py                      [🚫 RISK MANAGER - CORE]
├── shadow_trade_monitor.py              [🚫 Shadow monitoring]
├── signal_service.py                    [🚫 SIGNAL SERVICE - CORE]
├── strategies/                          [🚫 Trading strategies]
├── telegram_command_handler.py          [🚫 Telegram bot commands]
└── telegram_notifier_use_case.py        [🚫 Telegram notifications]
```

### 3. Execution Gateways (`backend/app/adapters/gateways/`)
```
backend/app/adapters/gateways/
├── __init__.py
├── base_execution_gateway.py            [🚫 Base gateway class]
├── binance_execution_gateway.py         [🚫 BINANCE EXECUTION]
├── binance_gateway.py                   [🚫 BINANCE GATEWAY]
├── lighter_execution_gateway.py         [🚫 LIGHTER EXECUTION - CORE]
├── multi_exchange_gateway.py            [🚫 Multi-exchange]
├── onchain_gateway.py                   [🚫 On-chain data]
└── telegram_gateway.py                  [🚫 TELEGRAM GATEWAY]
```

### 4. Repositories (`backend/app/adapters/repositories/`)
```
backend/app/adapters/repositories/
├── __init__.py
├── duckdb_repo.py                       [🚫 DuckDB repository]
├── live_trade_repository.py             [🚫 Trade repository]
└── market_repository.py                 [🚫 Market data repo]
```

### 5. API Layer (`backend/app/api/routers/`)
```
backend/app/api/routers/
├── __init__.py
├── execution.py                         [🚫 Execution API]
├── health.py                            [🚫 Health checks]
├── metrics.py                           [🚫 Metrics API]
├── signal.py                            [🚫 Signal API]
└── trading.py                           [🚫 Trading API]
```

### 6. Main Application (`backend/app/`)
```
backend/app/
├── __init__.py
├── config.py                            [🚫 Configuration]
├── main.py                              [🚫 MAIN ENTRY POINT]
├── schemas/
│   ├── __init__.py
│   ├── metrics.py                       [🚫 Metrics schemas]
│   └── signal.py                        [🚫 Signal schemas]
└── utils/                               [⚠️ Utility functions]
```

### 7. Scripts (`backend/scripts/`)
```
backend/scripts/
├── __init__.py
├── analyze_and_trade.py                 [🚫 Analysis script]
├── auto_scalp.py                        [🚫 AUTO SCALP - PRODUCTION]
├── backfill_data.py                     [⚠️ Data backfill]
├── backfill_historical.py               [⚠️ Historical backfill]
├── data_engine.py                       [🚫 Data engine]
├── hft_bot.py                           [🚫 HFT BOT]
├── hft-bot.service                      [🚫 SystemD service]
├── hft_bot_monitor.sh                   [🚫 Monitor script]
├── monitor_pos.py                       [🚫 Position monitor]
├── position_dashboard.py                [🚫 Dashboard]
├── scalp_v2.py                          [🚫 SCALP V2]
├── test_lighter_connection.py           [⚠️ Test connection]
├── walk_forward.py                      [🚫 Walk-forward testing]
└── walk_forward_confluence.py           [🚫 Confluence testing]
```

### 8. Root Level Production Files
```
btc-scalping-execution_layer/
├── backend/
│   ├── live_executor.py                 [🚫 LIVE EXECUTOR]
│   ├── paper_executor.py                [🚫 PAPER EXECUTOR]
│   ├── run.py                           [🚫 RUN SCRIPT]
│   ├── run_backtest_pipeline.py         [⚠️ Backtest pipeline]
│   ├── test_testnet_connection.py       [⚠️ Testnet test]
│   └── tests/                           [⚠️ Test files]
│
├── execution_layer/
│   ├── __init__.py
│   ├── binance/                         [🚫 Binance execution]
│   └── lighter/                         [🚫 Lighter execution]
```

---

## 🔬 RESEARCH/CLOUD_CORE (cloud_core/) - ✅ CAN MODIFY

### 1. Research Engines (`cloud_core/engines/`)
```
cloud_core/engines/
├── __init__.py                          [✅ Export new models]
├── layer1_bcd.py                        [✅ Simplified BCD]
├── layer2_ema.py                        [✅ Simplified EMA]
├── layer3_advanced.py                   [✅ EXPERIMENTAL: Advanced GBM]
├── layer3_lightgbm.py                   [✅ RESEARCH: LightGBM (53.3%)]
├── layer3_logistic.py                   [✅ RESEARCH: Logistic (53.8%)]
├── layer3_lstm.py                      [✅ RESEARCH: LSTM]
├── layer3_mlp.py                        [✅ RESEARCH: MLP copy (for testing)]
├── layer3_randomforest.py               [✅ RESEARCH: Random Forest]
├── layer3_rules.py                      [✅ RESEARCH: Rule-based]
├── layer3_xgboost.py                    [✅ RESEARCH: XGBoost (52.8%)]
├── layer4_risk.py                       [✅ Simplified Risk]
└── spectrum.py                          [✅ Simplified Spectrum]
```

**Note:** `layer3_mlp.py` di sini adalah **COPY** untuk testing, bukan yang production.

### 2. Data (`cloud_core/data/`)
```
cloud_core/data/
├── __init__.py                          [✅ Data exports]
└── fetcher.py                           [✅ Binance fetcher]
```

### 3. Research Scripts (`cloud_core/`)
```
cloud_core/
├── signal_service.py                    [✅ Research orchestrator]
├── runner.py                            [✅ Research CLI]
├── model_evaluator.py                   [✅ Model evaluator]
├── quick_evaluator.py                   [✅ Quick test]
├── test_local.py                        [✅ Local CSV test]
├── get_dataset.py                       [✅ Dataset fetcher]
├── colab_core.ipynb                     [✅ Jupyter notebook]
├── model_evaluation_report.json         [✅ Results JSON]
├── RESEARCH_RESULTS.md                  [✅ Documentation]
├── README.md                            [✅ Documentation]
└── requirements.txt                     [✅ Research deps]
```

---

## 🟡 SHARED/CONFIG FILES

### 1. Configuration Files
```
btc-scalping-execution_layer/
├── .env                                 [⚠️ Environment variables]
├── .env.template                        [✅ Template]
├── docker-compose.yml                   [⚠️ Docker orchestration]
├── Dockerfile                           [⚠️ Main Dockerfile]
├── Dockerfile.lighter                   [⚠️ Lighter Dockerfile]
├── Dockerfile.signal                    [⚠️ Signal Dockerfile]
├── requirements.txt                     [⚠️ Root requirements]
├── pyrightconfig.json                   [✅ Pyright config]
└── .dockerignore                        [✅ Docker ignore]
```

### 2. Database & Data
```
btc-scalping-execution_layer/
├── btc-quant.db                         [⚠️ PRODUCTION DATABASE]
├── check_db.py                          [⚠️ DB checker]
├── check_balance.py                     [⚠️ Balance checker]
├── check_all_trades.py                  [⚠️ Trade checker]
├── check_duplicate.py                   [⚠️ Duplicate checker]
├── check_position.py                    [⚠️ Position checker]
├── check_timestamps.py                  [⚠️ Timestamp checker]
└── query_trades.py                      [⚠️ Query tool]
```

---

## 🟢 DOCUMENTATION & PAPERS

```
btc-scalping-execution_layer/
├── README.md                            [✅ Main README]
├── SYSTEM_FLOW.md                       [✅ System flow docs]
├── PROJECT_LEDGER.md                    [✅ Project ledger]
├── PHASE1_COMPLETE_SUMMARY.txt          [✅ Phase 1 summary]
├── LIBRARY_DOCUMENTATION_INDEX.md       [✅ Library index]
├── ARCHITECTURE_PROD_VS_RESEARCH.md     [✅ Architecture docs]
├── RECOMMENDED_STRUCTURE.md               [✅ Structure proposal]
├── PRODUCTION_VS_RESEARCH_CORRECTED.md  [✅ Corrected docs]
├── STRUCTURE_ALT4_DOCKER.md             [✅ Docker structure]
├── STRUCTURE_FINAL.md                   [✅ Final structure]
└── lighter_gateway.md                   [✅ Lighter docs]
```

### Paper Directory
```
paper/
├── main.tex                             [✅ Paper main]
├── references.bib                       [✅ References]
├── implementation_plan.md               [✅ Implementation plan]
└── sections/
    ├── 01_introduction.tex
    ├── 02_theoretical_background.tex
    ├── 03_architecture.tex
    ├── 04_evolution_v4.tex
    ├── 05_results.tex
    └── 06_conclusion.tex
```

---

## 🟡 OTHER DIRECTORIES (Archive/Optional)

```
btc-scalping-execution_layer/
├── backtest/                            [🟡 Archive candidates]
│   ├── engine.py
│   ├── data/
│   │   ├── BTC_USDT_4h_2025.csv
│   │   └── BTC_USDT_4h_2023.csv
│   └── v4/
│
├── docs/                               [🟡 Documentation folder]
├── learn/                              [🟡 Learning materials]
├── research/                           [🟡 Old research]
├── rtk/                                [🟡 RTK components]
├── frontend/                           [🟡 Web UI]
├── infrastructure/                     [🟡 Infrastructure]
├── wfv_workspace/                    [🟡 WFV workspace]
├── artifacts/                        [🟡 Artifacts]
├── scripts/                          [🟡 Empty]
├── logs/                             [🟡 Empty]
└── .github/                          [🟡 GitHub configs]
```

---

## 📊 Ringkasan Status File

### 🔴 PRODUCTION (JANGAN DIUBAH)

**Total: ~60+ files**

#### Tier 1 - Ultra Critical (Core Engine)
| File | Status | Reason |
|------|--------|--------|
| `backend/app/core/engines/layer3_ai.py` | 🚫 | MLP Production Model |
| `backend/app/core/engines/layer1_bcd.py` | 🚫 | Layer 1 Regime |
| `backend/app/core/engines/layer2_ema.py` | 🚫 | Layer 2 Trend |
| `backend/app/use_cases/position_manager.py` | 🚫 | Position Lifecycle |
| `backend/app/use_cases/signal_service.py` | 🚫 | Signal Orchestrator |
| `backend/app/use_cases/risk_manager.py` | 🚫 | Risk Calculation |

#### Tier 2 - Critical (Execution)
| File | Status | Reason |
|------|--------|--------|
| `backend/app/adapters/gateways/lighter_execution_gateway.py` | 🚫 | Lighter Execution |
| `backend/app/adapters/gateways/binance_execution_gateway.py` | 🚫 | Binance Execution |
| `backend/app/adapters/gateways/telegram_gateway.py` | 🚫 | Telegram Notif |
| `backend/app/use_cases/execution_notifier_use_case.py` | 🚫 | Execution Alerts |
| `backend/app/use_cases/telegram_notifier_use_case.py` | 🚫 | Telegram Handler |
| `backend/app/use_cases/telegram_command_handler.py` | 🚫 | Bot Commands |

#### Tier 3 - Important (Supporting)
| File | Status | Reason |
|------|--------|--------|
| `backend/app/main.py` | 🚫 | Entry Point |
| `backend/app/config.py` | 🚫 | Configuration |
| `backend/scripts/auto_scalp.py` | 🚫 | Auto Scalp Script |
| `backend/scripts/hft_bot.py` | 🚫 | HFT Bot |
| `backend/scripts/scalp_v2.py` | 🚫 | Scalp V2 |
| `backend/live_executor.py` | 🚫 | Live Executor |
| `backend/paper_executor.py` | 🚫 | Paper Executor |

### 🔬 RESEARCH (BOLEH DIUBAH)

**Total: ~20+ files**

| File | Status | Notes |
|------|--------|-------|
| `cloud_core/engines/layer3_logistic.py` | ✅ | Research model (53.8%) |
| `cloud_core/engines/layer3_lightgbm.py` | ✅ | Research model (53.3%) |
| `cloud_core/engines/layer3_xgboost.py` | ✅ | Research model (52.8%) |
| `cloud_core/engines/layer3_lstm.py` | ✅ | Experimental |
| `cloud_core/engines/layer3_rules.py` | ✅ | Rule-based test |
| `cloud_core/model_evaluator.py` | ✅ | Evaluator tool |
| `cloud_core/quick_evaluator.py` | ✅ | Quick test |
| `cloud_core/colab_core.ipynb` | ✅ | Jupyter notebook |

---

## 🎯 Final Structure Proposal

Berdasarkan analisis, struktur yang diusulkan:

```
btc-scalping-execution_layer/
│
├── 🔴 prod/                    [🚫 Production - Current backend/]
│   ├── engine/                 [Core Layer 1-4]
│   ├── execution/              [Trade execution]
│   ├── use_cases/              [Business logic]
│   ├── gateways/               [Exchange adapters]
│   ├── notify/                 [Telegram/notifications]
│   └── scripts/                [Production scripts]
│
├── 🔬 research/                [✅ Research - Current cloud_core/]
│   ├── models/                 [Model experiments]
│   ├── backtest/               [Backtesting]
│   ├── notebooks/              [Jupyter/Colab]
│   └── evaluation/             [Model evaluation]
│
├── ⚠️ shared/                  [Shared components]
├── 🟢 docs/                    [Documentation]
├── 🗄️ archive/                [Old files to archive]
└── 🔧 ops/                     [Operations/Deployment]
```

---

## ❗ Action Items

### Immediate (Before Restructure):
1. ✅ **BACKUP** seluruh `backend/` (production)
2. ✅ **VERIFY** MLP di `backend/app/core/engines/layer3_ai.py` adalah yang running
3. ✅ **COPY** MLP ke `cloud_core/engines/layer3_mlp.py` untuk reference

### Restructure Phase:
1. 🟡 Move `backend/` → `prod/`
2. 🟡 Move `cloud_core/` → `research/`
3. 🟡 Create `archive/` for old folders
4. 🟡 Create `shared/` for common code
5. 🟡 Create `ops/` for deployment

---

**Total Analysis Complete:**
- 🔴 Production files: ~60 (DO NOT MODIFY)
- 🔬 Research files: ~20 (CAN MODIFY)
- 🟡 Shared/Config: ~30 (Careful modification)
- 🟢 Docs: ~15 (Safe to modify)
