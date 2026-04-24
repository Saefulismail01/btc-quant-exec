# Agent Swarm Task Breakdown - Backtest Full Architecture

**Date:** 2026-04-24  
**Lead Agent:** Cascade (current)  
**Branch:** `feature/backtest-full-architecture`

## Context & Background

### Why This Backtest?

**Problem:** Production bot has high win rate (~75%) but low R:R (0.53), resulting in thin EV (+0.22% per trade).

**Research Findings (from `RESEARCH_FINDINGS.md`):**
- **Horizon mismatch confirmed:** MLP trained on 4H forward return labels, but execution happens in minutes-hours
- **Execution-aligned labels are 1.56x more predictable:** F1 0.51 vs 0.31 (baseline)
- **Recommendation:** Retrain MLP with execution-aligned labels for 64%+ improvement

**What We're Testing:**
This backtest validates whether the proposed improvements actually work in a full architecture simulation:
1. **MLP variants:** Baseline (4H) vs Execution-aligned vs 1H forward return
2. **Exit strategies:** Fixed TP/SL vs Partial TP vs Pure trailing
3. **Exhaustion layer:** Veto/reduce size at exhaustion conditions

### What Has Been Done So Far?

1. **Research phase (completed):**
   - Walk-forward validation on 180 days Binance 1m data
   - Proved execution-aligned labels are more predictable
   - Documented in `RESEARCH_FINDINGS.md`

2. **Tier 0 implementation (completed in `refactor/reconciliation-pipeline`):**
   - Reconciliation pipeline (Lighter → DuckDB)
   - Signal snapshot store
   - Ready for production deployment

3. **Current phase:**
   - Building backtest to validate strategy improvements before production deployment
   - Using existing L1/L2/L4 components (no need to reimplement)
   - Focus on MLP variants + exit strategies + exhaustion

### Success Criteria

**Primary:**
- Config A (execution-aligned MLP) shows EV improvement ≥ 50% vs baseline
- Config B (partial TP) shows avg winner improvement ≥ 50% vs baseline
- Config C (partial TP + exhaustion veto) shows best Sharpe ratio

**If successful:** Promote to production deployment
**If unsuccessful:** Re-evaluate approach or adjust parameters

## Overview

This document defines task breakdown for parallel agent swarm implementation of backtest with full Tier 0-4 architecture.

## Agent Roles

### Lead Agent (Cascade)
- **Responsibility:** Coordination, integration, final assembly
- **Tasks:** Review all agent outputs, integrate components, run final backtest
- **Deliverables:** Integrated backtest engine, final results report

### Agent A - Data Engineer
- **Responsibility:** Data loading, preprocessing, feature extraction
- **Context:** You're preparing the foundation data that all other agents will use. The backtest needs both 1m data (for accurate TP/SL simulation) and 4H data (for signal generation). You'll also extract the 8 technical features that MLP needs.
- **Tasks:** Phase 1 (Data Preparation)
- **Deliverables:** Preprocessed datasets, indicator features

### Agent B - MLP Engineer
- **Responsibility:** MLP training (3 variants)
- **Context:** You're training the core prediction models. Research showed execution-aligned labels are 1.56x more predictable. You'll train 3 variants: baseline (current), execution-aligned (research recommendation), and 1H forward return (alternative). This is the most critical component for improving EV.
- **Tasks:** Phase 2 (MLP Training)
- **Deliverables:** 3 trained MLP models

### Agent C - Execution Engineer
- **Responsibility:** Execution simulation (TP/SL, partial, trailing)
- **Context:** You're implementing how trades exit. Current fixed TP/SL limits winner magnitude. You'll implement partial TP (close 60% @ 0.4%, trail 40%) and pure trailing to capture trend continuation. This is key for improving R:R.
- **Tasks:** Phase 3 (Execution Simulation)
- **Deliverables:** Execution simulation modules

### Agent D - Backtest Engineer
- **Responsibility:** Backtest engine, metrics calculation
- **Context:** You're building the simulation engine that ties everything together. You'll integrate with existing L1/L2/L4 code, run all 6 configurations, and calculate metrics. This determines which combination performs best.
- **Tasks:** Phase 4 (Backtest Engine)
- **Deliverables:** Backtest engine, metrics module

## Task Breakdown

### Phase 1: Data Preparation (Agent A)

**Context:** This is the foundation. Without clean, aligned data, nothing else works. You need to:
- Load 1m data (for accurate TP/SL simulation — critical because TP/SL happens in minutes)
- Load 4H data (for signal generation — MLP operates on 4H timeframe)
- Extract 8 features that MLP uses (same as production)
- Call existing L1/L2/L4 code to get regime/volatility context

**Tasks:**
1. Load 1m cached data from `.cache/btc_1m_*.parquet`
2. Load 4H data from `backtest/data/BTC_USDT_4h_2020_2026_with_real_orderflow.csv`
3. Call existing production code to get L1/L2/L4 outputs
4. Extract 8 technical features for MLP:
   - RSI 14
   - MACD histogram
   - EMA distance
   - Log return
   - Normalized ATR
   - Normalized CVD
   - Funding rate
   - OI change
5. Save preprocessed data to `backtest_full_architecture/data/processed/`

**Dependencies:** None
**Output:** `data/preprocessed_4h.parquet`, `data/preprocessed_1m.parquet`, `data/features.parquet`

**Estimated Time:** 0.5 day

---

### Phase 2: MLP Training (Agent B)

**Context:** This is the most critical phase. Research proved execution-aligned labels are 1.56x more predictable (F1 0.51 vs 0.31). You're training 3 models to compare:
- **Baseline:** Current production model (4H forward return) — this is the control
- **Variant A:** Execution-aligned (TP before SL) — this is the research recommendation
- **Variant B:** 1H forward return — alternative hypothesis

If Variant A performs best, it validates the research and justifies production retraining.

**Tasks:**
1. Train Baseline MLP (4H forward return label)
   - Use existing label generation code
   - Train on 180 days data
   - Save model to `mlp/models/baseline.joblib`
2. Train Variant A MLP (execution-aligned label)
   - Use label from execution-aligned study (TP before SL)
   - Train on 180 days data
   - Save model to `mlp/models/variant_a.joblib`
3. Train Variant B MLP (1H forward return label)
   - Generate 1H forward return labels
   - Train on 180 days data
   - Save model to `mlp/models/variant_b.joblib`
4. Validate all 3 models with walk-forward
   - Report F1, accuracy per model
   - Save validation results

**Dependencies:** Phase 1 (Agent A)
**Output:** `mlp/models/baseline.joblib`, `mlp/models/variant_a.joblib`, `mlp/models/variant_b.joblib`, `mlp/validation_results.csv`

**Estimated Time:** 1 day

---

### Phase 3: Execution Simulation (Agent C)

**Context:** Current bot has low R:R (0.53) because fixed TP 0.71% cuts winners short. You're implementing exit strategies to capture trend continuation:
- **Fixed TP/SL:** Baseline (current production)
- **Partial TP:** Close 60% @ 0.4%, trail 40% — balances banking profit vs trend capture
- **Pure trailing:** No fixed TP, trail with ATR — maximum trend capture but higher risk

You're also implementing exhaustion layer to avoid "buying at the top" by vetoing entries when market is overextended.

**Tasks:**
1. Implement fixed TP/SL execution
   - Input: Entry price, TP%, SL%
   - Output: Exit price, exit type, holding time
2. Implement partial TP + trailing
   - TP1 @ 0.4% close 60%
   - Move SL to BE
   - Trail remaining 40% with 2×ATR chandelier
3. Implement pure trailing stop
   - Initial SL 1.333%
   - Trail with 3×ATR once profit > 0.3%
4. Implement exhaustion score calculation
   - Components: funding z-score, price stretch, CVD divergence
   - Output: exhaustion_score ∈ [0, 1]
5. Implement veto/reduce size logic
   - exhaustion_score > 0.7 → veto entry
   - 0.5 < score ≤ 0.7 → reduce size 50%
6. Save execution modules to `backtest_full_architecture/execution/`

**Dependencies:** Phase 1 (Agent A) - for 1m data
**Output:** `execution/fixed_tp_sl.py`, `execution/partial_tp.py`, `execution/trailing_stop.py`, `exhaustion/exhaustion_score.py`

**Estimated Time:** 1 day

---

### Phase 4: Backtest Engine (Agent D)

**Context:** You're building the simulation that determines which combination works best. You'll:
- Integrate with existing L1/L2/L4 code (no need to reimplement)
- Run 6 configurations (MLP variants × exit strategies × exhaustion)
- Calculate metrics (WR, R:R, EV, Sharpe, etc.)
- Generate comparison report

This is the decision engine — it will tell us whether the research recommendations actually improve performance.

**Tasks:**
1. Implement time-series walk-forward logic
   - Train/test split by time
   - Rolling window validation
2. Implement configuration matrix
   - Define 6 configurations (baseline + variants)
   - Parameter grid for each config
3. Implement metrics calculation
   - Primary: WR, R:R, EV, Sharpe, Max DD
   - Secondary: Profit factor, avg winner/loser
   - Conditional: WR by regime/vol/exhaustion
4. Implement backtest loop
   - Integrate with existing L1/L2/L4 (call production code)
   - For each config:
     - Use appropriate MLP variant
     - Simulate execution strategy
     - Track trades
     - Calculate metrics
5. Save results to `backtest_full_architecture/results/`

**Dependencies:** Phase 2 (Agent B), Phase 3 (Agent C)
**Output:** `backtest/engine.py`, `backtest/config.py`, `backtest/metrics.py`, `results/comparison.csv`

**Estimated Time:** 1 day

---

### Phase 5: Integration & Analysis (Lead Agent)

**Context:** You're the orchestrator. After all agents complete their tasks, you'll:
- Integrate all components into a working backtest
- Run the full simulation with all 6 configurations
- Analyze results to determine which combination performs best
- Generate recommendations for production deployment

This is the final decision point — based on your analysis, we'll decide whether to promote the research recommendations to production.

**Tasks:**
1. Review all agent outputs
2. Integrate components:
   - Data loading
   - Signal generation
   - Execution simulation
   - Backtest engine
3. Create main entry point `run_backtest.py`
4. Run full backtest with all 6 configurations
5. Generate comparison report
6. Analyze results:
   - Compare configurations
   - Identify best performer
   - Analyze conditional metrics
7. Generate recommendations document

**Dependencies:** All previous phases
**Output:** `run_backtest.py`, `results/analysis.md`, final recommendations

**Estimated Time:** 0.5 day

---

## Parallel Execution Plan

### Wave 1 (Parallel)
- **Agent A:** Phase 1 (Data Preparation)
- **Agent B:** Wait for Phase 1
- **Agent C:** Wait for Phase 1
- **Agent D:** Wait for Phase 2 & 3

### Wave 2 (Parallel)
- **Agent A:** Done
- **Agent B:** Phase 2 (Signal Generation)
- **Agent C:** Phase 3 (Execution Simulation)
- **Agent D:** Wait for Phase 2 & 3

### Wave 3 (Parallel)
- **Agent A:** Done
- **Agent B:** Done
- **Agent C:** Done
- **Agent D:** Phase 4 (Backtest Engine)

### Wave 4 (Sequential)
- **Lead Agent:** Phase 5 (Integration & Analysis)

**Total Parallel Time:** ~2.5 days (vs 4 days sequential)

---

## Communication Protocol

### Agent A → Agent B & C
- **When:** Phase 1 complete
- **What:** Location of preprocessed data files
- **Format:** "Phase 1 complete. Data at: `data/preprocessed_4h.parquet`, `data/preprocessed_1m.parquet`"

### Agent B → Agent D
- **When:** Phase 2 complete
- **What:** Location of signal files
- **Format:** "Phase 2 complete. Signals at: `signals/signals_*.parquet`"

### Agent C → Agent D
- **When:** Phase 3 complete
- **What:** Location of execution modules
- **Format:** "Phase 3 complete. Modules at: `execution/*.py`, `exhaustion/*.py`"

### Agent D → Lead Agent
- **When:** Phase 4 complete
- **What:** Location of backtest engine
- **Format:** "Phase 4 complete. Engine at: `backtest/engine.py`"

### All Agents → Lead Agent
- **When:** Any error/blocker
- **What:** Error details, what's blocking
- **Format:** "BLOCKED: [description]. Need: [what's needed]"

---

## File Structure After Implementation

```
backtest_full_architecture/
├── data/
│   ├── load_data.py           # Agent A
│   ├── extract_features.py    # Agent A
│   └── processed/
│       ├── preprocessed_4h.parquet
│       ├── preprocessed_1m.parquet
│       └── features.parquet
├── mlp/
│   ├── train_baseline.py      # Agent B
│   ├── train_exec_aligned.py # Agent B
│   ├── train_1h.py            # Agent B
│   ├── models/
│   │   ├── baseline.joblib
│   │   ├── variant_a.joblib
│   │   └── variant_b.joblib
│   └── validation_results.csv
├── execution/
│   ├── fixed_tp_sl.py         # Agent C
│   ├── partial_tp.py          # Agent C
│   └── trailing_stop.py       # Agent C
├── exhaustion/
│   ├── exhaustion_score.py    # Agent C
│   └── veto_logic.py          # Agent C
├── backtest/
│   ├── engine.py              # Agent D
│   ├── config.py              # Agent D
│   └── metrics.py             # Agent D
├── results/
│   ├── comparison.csv         # Agent D
│   └── analysis.md            # Lead Agent
├── run_backtest.py            # Lead Agent
├── BACKTEST_DESIGN.md         # Lead Agent
└── AGENT_SWARM_TASKS.md       # Lead Agent
```

---

## Success Criteria per Agent

### Agent A (Data Engineer)
- ✅ Preprocessed data files created
- ✅ All indicators computed correctly
- ✅ Data aligned between 1m and 4H

### Agent B (MLP Engineer)
- ✅ 3 MLP models trained successfully
- ✅ All models validated with walk-forward
- ✅ Models saved to correct locations
- ✅ Validation results documented

### Agent C (Execution Engineer)
- ✅ All execution strategies implemented
- ✅ Exhaustion score calculation working
- ✅ Veto logic implemented
- ✅ Modules tested on sample data

### Agent D (Backtest Engineer)
- ✅ Backtest engine working
- ✅ All 6 configurations runnable
- ✅ Metrics calculation correct
- ✅ Results saved to CSV

### Lead Agent
- ✅ All components integrated
- ✅ Full backtest runs successfully
- ✅ Analysis report generated
- ✅ Recommendations documented

---

## Next Steps for User

1. **Assign Agent A** to start Phase 1 (Data Preparation)
2. **Wait for Agent A completion** before assigning Agents B & C
3. **Assign Agents B & C in parallel** after Phase 1 complete
4. **Assign Agent D** after Phases 2 & 3 complete
5. **Lead Agent (Cascade)** handles Phase 5 integration

**Command to start Agent A:**
"Start as Agent A - Data Engineer. Implement Phase 1: Data Preparation following AGENT_SWARM_TASKS.md. Use cached 1m data from docs/research/rr_improvement_2026q2/experiments/execution_aligned_label_study/.cache/ and 4H data from backtest/data/BTC_USDT_4h_2020_2026_with_real_orderflow.csv."
