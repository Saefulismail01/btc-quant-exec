# MLP Horizon Mismatch Backtest - Final Analysis

## Research Objective

Validate MLP model with "execution-aligned" labels and new exit strategies (partial TP, trailing stop) within a full architecture backtest. Compare performance against current 4H forward return MLP and fixed TP/SL.

## Methodology

### Agent Swarm Approach
- **Agent A (Data Engineer):** Data loading and feature extraction
- **Agent B (MLP Engineer):** MLP training for 3 variants
- **Agent C (Execution Engineer):** Exit strategies and exhaustion layer
- **Agent D (Backtest Engineer):** Backtest engine and orchestration

### MLP Variants
1. **Baseline:** 4H forward return labels (3-class: bear/neutral/bull)
2. **Variant A:** Execution-aligned labels (binary: TP hit / SL hit)
3. **Variant B:** 1H forward return labels (3-class, approximated from 4H data)

### Exit Strategies
1. **Fixed TP/SL:** TP 0.71%, SL 1.33%
2. **Partial TP:** 60% at TP1 (0.4%), trail remaining 40%
3. **Trailing Stop:** ATR-based trailing stop

### Exhaustion Layer
- Veto logic to skip trades when exhaustion score > 0.7

## Data Issues & Debugging

### Issue 1: Datetime Mismatch
- **Problem:** 1m data timestamp converted incorrectly (Unix epoch → 1970)
- **Impact:** Execution modules always returned empty window, fallback to next_bar_close
- **Fix:** Fixed timestamp conversion logic in `load_1m_data()`

### Issue 2: Timezone Mismatch
- **Problem:** 4H data tz-naive vs 1m data tz-aware
- **Impact:** Comparison errors when filtering data ranges
- **Fix:** Added timezone localization to 4H data

### Issue 3: Data Range Mismatch
- **Problem:** 1m data only 2025-2026, 4H data 2020-2026
- **Impact:** Backtest period too short for robust validation
- **Fix:** Filtered 4H data to match 1m range (942 bars vs 12,228)

### Issue 4: Label Generation
- **Problem:** ATR-based adaptive threshold resulted in all labels being single class
- **Fix:** Simplified to fixed threshold (1% for 4H, 0.5% for 1H)

## Results (Final - Data Asli)

| Config | Trades | Win Rate | R:R | EV | Sharpe | Max DD | Avg Holding |
|--------|--------|----------|-----|----|--------|--------|-------------|
| **baseline** | 408 | 68.9% | 0.81 | 0.22% | 4.68 | -6.8% | 103 min |
| **a_exec_aligned_fixed** | 293 | 64.2% | 0.87 | 0.14% | 3.34 | -6.6% | 147 min |
| **b_exec_aligned_partial** | 293 | 73.7% | 0.53 | 0.10% | 2.75 | -8.8% | 147 min |
| **c_exec_aligned_partial_veto** | 288 | 73.9% | 0.52 | 0.10% | 2.81 | -9.9% | 149 min |
| **d_exec_aligned_trailing** | 293 | 48.5% | 1.14 | 0.02% | 0.46 | -16.3% | 180 min |
| **e_1h_fixed** | 15 | 40.0% | 0.42 | -0.34% | -7.07 | -6.0% | 234 min |

## Key Findings

### 1. Baseline Outperforms Execution-Aligned
- **Sharpe:** 4.68 vs 3.34 (+40% improvement)
- **Win Rate:** 68.9% vs 64.2%
- **Trade Count:** 408 vs 293 (more opportunities)
- **Conclusion:** Execution-aligned labels do not provide edge over 4H forward return

### 2. Exit Strategies Impact
- **Partial TP:** Higher WR (73.7%) but lower R:R (0.53), Sharpe drops to 2.75
- **Trailing Stop:** Highest R:R (1.14) but lowest WR (48.5%), Sharpe very poor (0.46)
- **Fixed TP/SL:** Best risk-adjusted return (Sharpe 4.68)
- **Conclusion:** Complex exit strategies do not justify added complexity

### 3. Exhaustion Layer
- **Veto Impact:** 5 trade reduction (288 vs 293), no significant performance improvement
- **Conclusion:** Veto layer not needed, can be removed for simplification

### 4. 1H Labels
- **Data Limitation:** Only 15 trades due to limited 1m data (6 months)
- **Performance:** Negative Sharpe (-7.07)
- **Conclusion:** 1H labels not viable with current data, threshold too tight

### 5. Execution Modules
- **After Fix:** Working correctly (varying holding times: 103-180 min)
- **Before Fix:** All configs identical due to datetime mismatch
- **Conclusion:** Intraday TP/SL tracking now functional

## MLP Validation Results

| Model | Accuracy | Balanced Acc | F1 Score | Label Type |
|-------|----------|--------------|----------|------------|
| baseline | 33.1% | 34.4% | 0.290 | 3-class 4H forward return |
| variant_a | 45.3% | 49.5% | 0.403 | Binary execution-aligned |
| variant_b | 91.7% | 35.6% | 0.890 | 3-class 1H forward return |

**Note:** Variant_a has best balanced accuracy (49.5%), but this does not translate to better backtest performance.

## Final Recommendation

### ✅ ADOPT: Baseline Configuration
- **MLP Variant:** 4H forward return labels (3-class: bear/neutral/bull)
- **Exit Strategy:** Fixed TP 0.71% / SL 1.33%
- **Exhaustion Layer:** Not needed (veto provides no value)
- **Expected Performance:** Sharpe 4.68, WR 68.9%, Max DD -6.8%

### ❌ REJECT
- Execution-aligned labels (variant_a) - Lower Sharpe
- Partial TP exit - Higher WR but lower R:R, Sharpe drops
- Trailing stop exit - Very low WR, poor Sharpe
- 1H labels (variant_b) - Data limited, negative performance
- Veto layer - Minimal impact, unnecessary complexity

### Production Deployment
1. **Model:** `mlp/models/baseline.joblib`
2. **Scaler:** `mlp/models/baseline_scaler.joblib`
3. **Signal Generation:** `mlp/generate_signals.py`
4. **Execution:** `execution/fixed_tp_sl.py`
5. **Monitoring:** Track Sharpe, WR, Max DD vs backtest baseline

## Future Work

### 1. Data Expansion
- Collect longer 1m data (2-3 years)
- Backtest with longer period for robust validation

### 2. Alternative Horizons
- Try 2H or 8H labels (not 1H)
- 1H too short for 4H timeframe

### 3. Exit Optimization
- Explore dynamic TP/SL based on volatility
- ATR-based exit levels

### 4. LLM Layer (Optional)
- **Purpose:** Filter signals based on news/events, sentiment weighting, position sizing adjustment
- **Implementation:** GPT-4o-mini for cost efficiency (~$18/month)
- **Use Cases:** Event detection, sentiment analysis, regime detection
- **Note:** Suitable for 4H signal system (latency not an issue)

## Conclusion

This research did **not** find significant improvements over the baseline. Execution-aligned labels and new exit strategies do not provide sufficient edge to justify added complexity.

**Decision:** Deploy baseline configuration for production with close monitoring to ensure performance consistency with backtest results.

---

## Appendix: Files Generated

### Data
- `data/processed/preprocessed_4h.parquet` - 4H data with features
- `data/processed/preprocessed_1m.parquet` - 1m data for execution
- `data/processed/features.parquet` - Technical features

### MLP
- `mlp/train_baseline.py` - Baseline MLP training
- `mlp/train_exec_aligned.py` - Execution-aligned MLP training
- `mlp/train_1h.py` - 1H MLP training
- `mlp/generate_signals.py` - Signal generation for all variants
- `mlp/models/baseline.joblib` - Baseline model
- `mlp/models/variant_a.joblib` - Execution-aligned model
- `mlp/models/variant_b.joblib` - 1H model
- `mlp/models/*_scaler.joblib` - Feature scalers
- `mlp/validation_results.csv` - Validation metrics

### Execution
- `execution/fixed_tp_sl.py` - Fixed TP/SL execution
- `execution/partial_tp.py` - Partial TP execution
- `execution/trailing_stop.py` - Trailing stop execution

### Exhaustion
- `exhaustion/exhaustion_score.py` - Exhaustion score calculation
- `exhaustion/veto_logic.py` - Veto logic

### Backtest
- `backtest/engine.py` - Backtest engine
- `backtest/config.py` - Configuration matrix
- `backtest/metrics.py` - Metrics calculation
- `run_phase4.py` - Entry point

### Results
- `results/comparison.csv` - Backtest comparison results

### Documentation
- `AGENT_SWARM_TASKS.md` - Agent task breakdown
- `BACKTEST_DESIGN.md` - Backtest design
- `FINAL_ANALYSIS.md` - This document
