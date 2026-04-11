# 📊 Diagram Struktur Direktori: Current vs Proposed

## CURRENT STRUCTURE (Sekarang)

```
btc-scalping-execution_layer/
│
├── 🔴 backend/                          [🚫 PRODUCTION SYSTEM]
│   ├── app/
│   │   ├── main.py                      [🚫 ENTRY POINT]
│   │   ├── config.py                    [🚫 CONFIG]
│   │   │
│   │   ├── core/engines/
│   │   │   ├── __init__.py
│   │   │   ├── layer1_bcd.py           [🚫 L1: BCD Regime]
│   │   │   ├── layer1_volatility.py    [🚫 L1: Volatility]
│   │   │   ├── layer2_ema.py           [🚫 L2: EMA Trend]
│   │   │   ├── layer2_ichimoku.py      [🚫 L2: Ichimoku]
│   │   │   ├── layer3_ai.py            [🏆 L3: MLP PROD]
│   │   │   ├── layer5_sentiment.py     [🚫 L5: Sentiment]
│   │   │   └── experimental/           [⚠️ Can Modify]
│   │   │
│   │   ├── use_cases/
│   │   │   ├── signal_service.py       [🚫 SIGNAL CORE]
│   │   │   ├── position_manager.py     [🚫 POSITION CORE]
│   │   │   ├── risk_manager.py         [🚫 RISK CORE]
│   │   │   ├── execution_notifier_use_case.py [🚫 EXEC NOTIFIER]
│   │   │   ├── telegram_notifier_use_case.py [🚫 TG NOTIFIER]
│   │   │   ├── telegram_command_handler.py [🚫 TG HANDLER]
│   │   │   ├── paper_trade_service.py  [🚫 PAPER TRADING]
│   │   │   ├── bcd_service.py          [🚫 BCD SERVICE]
│   │   │   ├── ema_service.py          [🚫 EMA SERVICE]
│   │   │   ├── ai_service.py           [🚫 AI SERVICE]
│   │   │   ├── ai_agent.py             [🚫 AI AGENT]
│   │   │   ├── data_ingestion_use_case.py [🚫 DATA PIPE]
│   │   │   ├── lighter_nonce_manager.py [🚫 NONCE MGR]
│   │   │   ├── narrative_service.py    [🚫 NARRATIVE]
│   │   │   ├── shadow_trade_monitor.py [🚫 SHADOW MON]
│   │   │   ├── hmm_service.py          [🚫 HMM]
│   │   │   └── strategies/             [🚫 STRATEGIES]
│   │   │
│   │   ├── adapters/gateways/
│   │   │   ├── lighter_execution_gateway.py [🚫 LIGHTER EXEC]
│   │   │   ├── binance_execution_gateway.py   [🚫 BINANCE EXEC]
│   │   │   ├── binance_gateway.py      [🚫 BINANCE GW]
│   │   │   ├── telegram_gateway.py     [🚫 TELEGRAM GW]
│   │   │   ├── onchain_gateway.py      [🚫 ONCHAIN]
│   │   │   ├── multi_exchange_gateway.py [🚫 MULTI-EX]
│   │   │   └── base_execution_gateway.py [🚫 BASE CLASS]
│   │   │
│   │   ├── adapters/repositories/
│   │   │   ├── live_trade_repository.py [🚫 TRADE REPO]
│   │   │   ├── market_repository.py     [🚫 MARKET REPO]
│   │   │   └── duckdb_repo.py          [🚫 DUCKDB]
│   │   │
│   │   ├── api/routers/
│   │   │   ├── execution.py            [🚫 API EXEC]
│   │   │   ├── signal.py               [🚫 API SIGNAL]
│   │   │   ├── trading.py              [🚫 API TRADE]
│   │   │   ├── health.py               [🚫 API HEALTH]
│   │   │   └── metrics.py              [🚫 API METRICS]
│   │   │
│   │   └── schemas/
│   │       ├── signal.py               [🚫 SCHEMAS]
│   │       └── metrics.py              [🚫 SCHEMAS]
│   │
│   ├── scripts/
│   │   ├── auto_scalp.py               [🚫 AUTO SCALP]
│   │   ├── hft_bot.py                  [🚫 HFT BOT]
│   │   ├── scalp_v2.py                 [🚫 SCALP V2]
│   │   ├── walk_forward.py             [⚠️ BACKTEST]
│   │   ├── walk_forward_confluence.py  [⚠️ CONFLUENCE]
│   │   ├── position_dashboard.py       [🚫 DASHBOARD]
│   │   ├── monitor_pos.py              [🚫 MONITOR]
│   │   ├── analyze_and_trade.py        [🚫 ANALYZER]
│   │   ├── data_engine.py              [🚫 DATA ENGINE]
│   │   ├── backfill_data.py            [⚠️ BACKFILL]
│   │   ├── backfill_historical.py      [⚠️ HISTORICAL]
│   │   └── test_lighter_connection.py  [⚠️ TEST]
│   │
│   ├── live_executor.py                [🚫 LIVE EXEC]
│   ├── paper_executor.py               [🚫 PAPER EXEC]
│   ├── run.py                          [🚫 RUNNER]
│   ├── run_backtest_pipeline.py        [⚠️ BACKTEST]
│   ├── test_testnet_connection.py      [⚠️ TESTNET]
│   └── tests/                          [⚠️ TESTS]
│
├── 🔬 cloud_core/                      [✅ RESEARCH ARENA]
│   ├── engines/
│   │   ├── __init__.py
│   │   ├── layer1_bcd.py             [✅ Simplified BCD]
│   │   ├── layer2_ema.py               [✅ Simplified EMA]
│   │   ├── layer3_mlp.py               [✅ MLP Copy for Testing]
│   │   ├── layer3_logistic.py          [✅ RESEARCH: 53.8%]
│   │   ├── layer3_lightgbm.py          [✅ RESEARCH: 53.3%]
│   │   ├── layer3_xgboost.py           [✅ RESEARCH: 52.8%]
│   │   ├── layer3_lstm.py              [✅ RESEARCH: LSTM]
│   │   ├── layer3_randomforest.py      [✅ RESEARCH: RF]
│   │   ├── layer3_rules.py             [✅ RESEARCH: Rules]
│   │   ├── layer3_advanced.py          [✅ RESEARCH: Advanced]
│   │   ├── layer4_risk.py              [✅ Simplified Risk]
│   │   └── spectrum.py                 [✅ Simplified Spectrum]
│   │
│   ├── data/
│   │   ├── __init__.py
│   │   └── fetcher.py                  [✅ Data Fetcher]
│   │
│   ├── signal_service.py               [✅ Research Orchestrator]
│   ├── runner.py                       [✅ Research CLI]
│   ├── model_evaluator.py               [✅ Model Evaluator]
│   ├── quick_evaluator.py              [✅ Quick Test]
│   ├── test_local.py                   [✅ Local CSV Test]
│   ├── get_dataset.py                  [✅ Dataset Fetcher]
│   ├── colab_core.ipynb                [✅ Jupyter Notebook]
│   ├── model_evaluation_report.json   [✅ Results]
│   ├── RESEARCH_RESULTS.md             [✅ Documentation]
│   ├── README.md                       [✅ Documentation]
│   └── requirements.txt                [✅ Dependencies]
│
├── 🔌 execution_layer/                 [🚫 EXECUTION]
│   ├── __init__.py
│   ├── binance/                        [🚫 Binance Code]
│   └── lighter/                        [🚫 Lighter Code]
│
├── ⚙️ Root Config Files
│   ├── .env                            [⚠️ ENV VARS]
│   ├── .env.template                   [✅ Template]
│   ├── docker-compose.yml              [⚠️ Docker]
│   ├── Dockerfile                      [⚠️ Docker]
│   ├── Dockerfile.lighter              [⚠️ Docker]
│   ├── Dockerfile.signal               [⚠️ Docker]
│   ├── requirements.txt                [⚠️ Deps]
│   └── pyrightconfig.json              [✅ Config]
│
├── 🔍 DB & Check Scripts
│   ├── btc-quant.db                    [⚠️ PROD DB]
│   ├── check_db.py                     [⚠️ Check DB]
│   ├── check_balance.py                [⚠️ Check Balance]
│   ├── check_all_trades.py             [⚠️ Check Trades]
│   ├── check_duplicate.py              [⚠️ Check Dup]
│   ├── check_position.py               [⚠️ Check Pos]
│   ├── check_timestamps.py             [⚠️ Check Time]
│   └── query_trades.py                 [⚠️ Query]
│
├── 📚 Documentation
│   ├── README.md
│   ├── SYSTEM_FLOW.md
│   ├── PROJECT_LEDGER.md
│   ├── PHASE1_COMPLETE_SUMMARY.txt
│   ├── LIBRARY_DOCUMENTATION_INDEX.md
│   ├── lighter_gateway.md
│   ├── ARCHITECTURE_PROD_VS_RESEARCH.md
│   ├── RECOMMENDED_STRUCTURE.md
│   ├── PRODUCTION_VS_RESEARCH_CORRECTED.md
│   ├── STRUCTURE_ALT4_DOCKER.md
│   ├── STRUCTURE_FINAL.md
│   └── DIRECTORY_ANALYSIS_COMPLETE.md   [This file]
│
├── 📄 Paper
│   ├── main.tex
│   ├── references.bib
│   ├── implementation_plan.md
│   └── sections/
│       ├── 01_introduction.tex
│       ├── 02_theoretical_background.tex
│       ├── 03_architecture.tex
│       ├── 04_evolution_v4.tex
│       ├── 05_results.tex
│       └── 06_conclusion.tex
│
└── 🗄️ Large Folders (Archive Candidates)
    ├── backtest/                       [🟡 183 items]
    ├── research/                       [🟡 115 items]
    ├── rtk/                            [🟡 247 items]
    ├── learn/                          [🟡 108 items]
    ├── frontend/                       [🟡 22 items]
    ├── docs/                           [🟡 90 items]
    └── wfv_workspace/                  [🟡 Large]
```

---

## PROPOSED STRUCTURE (Yang Diusulkan)

```
btc-scalping-execution_layer/
│
├── 🔴 prod/                            [🚫 PRODUCTION - From backend/]
│   ├── src/
│   │   ├── engine/
│   │   │   ├── __init__.py
│   │   │   ├── layer1_bcd.py           [🚫 BCD]
│   │   │   ├── layer1_volatility.py    [🚫 Vol]
│   │   │   ├── layer2_ema.py           [🚫 EMA]
│   │   │   ├── layer2_ichimoku.py      [🚫 Ichimoku]
│   │   │   ├── layer3_ai.py            [🏆 MLP - CORE]
│   │   │   ├── layer5_sentiment.py     [🚫 Sentiment]
│   │   │   └── experimental/           [⚠️ Can Modify]
│   │   │
│   │   ├── execution/
│   │   │   ├── lighter_gateway.py      [🚫 Lighter]
│   │   │   ├── binance_gateway.py      [🚫 Binance]
│   │   │   ├── multi_exchange.py       [🚫 Multi]
│   │   │   └── order_manager.py        [🚫 Orders]
│   │   │
│   │   ├── use_cases/
│   │   │   ├── signal_service.py       [🚫 Signal]
│   │   │   ├── position_manager.py     [🚫 Position]
│   │   │   ├── risk_manager.py         [🚫 Risk]
│   │   │   ├── telegram_handler.py     [🚫 Telegram]
│   │   │   └── [other use_cases...]    [🚫 Core Logic]
│   │   │
│   │   ├── adapters/
│   │   │   ├── gateways/               [🚫 All Gateways]
│   │   │   └── repositories/           [🚫 All Repos]
│   │   │
│   │   ├── api/                        [🚫 API Layer]
│   │   ├── schemas/                    [🚫 Schemas]
│   │   ├── config.py                   [🚫 Config]
│   │   └── main.py                     [🚫 Entry]
│   │
│   ├── scripts/
│   │   ├── auto_scalp.py               [🚫 Auto Scalp]
│   │   ├── hft_bot.py                  [🚫 HFT]
│   │   ├── scalp_v2.py                 [🚫 Scalp V2]
│   │   └── [production scripts...]     [🚫 Scripts]
│   │
│   ├── live_executor.py                [🚫 Live]
│   ├── paper_executor.py               [🚫 Paper]
│   ├── run.py                          [🚫 Run]
│   ├── Dockerfile                      [⚠️ Docker]
│   └── requirements.txt                [⚠️ Deps]
│
├── 🔬 research/                        [✅ RESEARCH - From cloud_core/]
│   ├── src/
│   │   └── models/
│   │       ├── experiments/
│   │       │   ├── __init__.py
│   │       │   ├── logistic.py         [✅ 53.8%]
│   │       │   ├── lightgbm.py         [✅ 53.3%]
│   │       │   ├── xgboost.py          [✅ 52.8%]
│   │       │   ├── mlp_test.py         [✅ MLP Test Copy]
│   │       │   ├── lstm.py             [✅ LSTM]
│   │       │   ├── random_forest.py    [✅ RF]
│   │       │   └── rule_based.py       [✅ Rules]
│   │       │
│   │       └── candidates/             [✅ Validated >60%]
│   │           └── [empty until validated]
│   │
│   ├── backtest/
│   │   ├── engine.py                   [✅ Backtest]
│   │   └── strategies/                 [✅ Strategies]
│   │
│   ├── notebooks/
│   │   └── research.ipynb              [✅ Jupyter]
│   │
│   ├── evaluation/
│   │   ├── model_evaluator.py          [✅ Evaluator]
│   │   └── quick_evaluator.py          [✅ Quick]
│   │
│   ├── data/
│   │   └── csv_loader.py               [✅ CSV Loader]
│   │
│   ├── Dockerfile                      [✅ Research Docker]
│   └── requirements.txt                [✅ Full ML Deps]
│
├── ⚠️ shared/                          [⚠️ SHARED]
│   ├── config/
│   │   ├── settings.yaml
│   │   └── constants.py
│   ├── types/
│   │   └── dataclasses.py
│   └── utils/
│       ├── time.py
│       └── math.py
│
├── 💾 data/                            [💾 SHARED DATA]
│   ├── market/                         [OHLCV Cache]
│   ├── db/                             [Database]
│   └── logs/                           [Logs]
│
├── 🔧 ops/                             [🔧 OPERATIONS]
│   ├── deployment/
│   │   ├── docker-compose.yml
│   │   └── scripts/
│   ├── monitoring/
│   │   ├── health_check.py
│   │   └── alerts.py
│   └── scripts/
│       ├── backup.sh
│       └── setup.sh
│
├── 🧪 tests/                           [🧪 TESTS]
│   ├── prod/                           [Production Tests]
│   └── research/                       [Research Tests]
│
├── 📚 docs/                            [📚 DOCS]
│   ├── ARCHITECTURE.md
│   ├── PROD_SETUP.md
│   ├── RESEARCH_GUIDE.md
│   └── API.md
│
├── 🗄️ archive/                        [🗄️ ARCHIVE]
│   ├── backend_legacy/                 [Old backend/]
│   ├── cloud_core_legacy/              [Old cloud_core/]
│   ├── backtest_results/               [Old backtest/]
│   ├── research_papers/                [Old research/]
│   └── rtk_legacy/                     [Old rtk/]
│
├── 🐳 docker-compose.yml                [🐳 Orchestration]
├── 📄 .env.prod                         [⚠️ Prod Secrets]
├── 📄 .env.research                     [✅ Research Config]
├── 📝 Makefile                          [🔧 Commands]
└── 📖 README.md                         [📖 Main README]
```

---

## 🎯 Color Legend

| Symbol | Meaning |
|--------|---------|
| 🔴 | Production (Sacred) |
| 🔬 | Research (Playground) |
| ⚠️ | Shared (Careful) |
| 💾 | Data |
| 🔧 | Operations |
| 🧪 | Tests |
| 📚 | Documentation |
| 🗄️ | Archive |
| 🐳 | Docker |
| 🚫 | DO NOT MODIFY |
| ✅ | CAN MODIFY |
| 🏆 | Core Production |

---

## 📊 File Count Summary

| Area | Current | Proposed | Action |
|------|---------|----------|--------|
| Production | ~60 files | ~60 files | Move to prod/ |
| Research | ~20 files | ~20 files | Move to research/ |
| Shared | ~10 files | ~10 files | Create shared/ |
| Tests | ~30 files | ~30 files | Move to tests/ |
| Docs | ~15 files | ~10 files | Consolidate |
| Archive | 0 | ~600 files | Archive old folders |
| **Total Active** | **~135** | **~100** | **-35 files** |

---

## ⚡ Migration Path

### Phase 1: Prepare
1. ✅ Backup entire repository
2. ✅ Verify MLP location in backend/app/core/engines/layer3_ai.py
3. ✅ Create archive/ folder

### Phase 2: Create Structure
```bash
mkdir -p prod/src/{engine,execution,use_cases,adapters,api,schemas}
mkdir -p research/src/models/{experiments,candidates}
mkdir -p research/{backtest,notebooks,evaluation,data}
mkdir -p shared/{config,types,utils}
mkdir -p data/{market,db,logs}
mkdir -p ops/{deployment,monitoring,scripts}
mkdir -p tests/{prod,research}
mkdir -p docs
mkdir -p archive/{backend_legacy,cloud_core_legacy}
```

### Phase 3: Move Files
```bash
# Production
mv backend/app/* prod/src/
mv backend/scripts/* prod/scripts/
mv backend/live_executor.py prod/
mv backend/paper_executor.py prod/
mv backend/run.py prod/

# Research
mv cloud_core/* research/

# Archive old folders
mv backend/ archive/backend_legacy/
mv cloud_core/ archive/cloud_core_legacy/
mv backtest/ archive/backtest_results/
mv research/ archive/research_papers/
mv rtk/ archive/rtk_legacy/
```

### Phase 4: Update Imports
- Update all Python imports to reflect new structure
- Update Docker compose paths
- Update README

---

**Diagram ini menunjukkan struktur current (kiri) dan proposed (kanan) dengan semua nama file yang ada.**
