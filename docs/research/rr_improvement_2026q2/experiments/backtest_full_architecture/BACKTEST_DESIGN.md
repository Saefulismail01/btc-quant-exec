# Backtest Design - Full Architecture Validation

**Date:** 2026-04-24  
**Objective:** Validate strategy with full Tier 0-4 architecture using historical data  
**Branch:** `feature/backtest-full-architecture`

## 1. Overview

Backtest ini akan mensimulasikan complete trading pipeline dengan semua tier untuk memvalidasi apakah perubahan yang diusulkan (Tier 2 MLP refactor, Tier 3 asymmetric exit, Tier 4 exhaustion) benar-benar meningkatkan performa.

## 2. Architecture Components in Backtest

### Tier 0 - Foundation (Simulation)
- **Signal snapshot:** Capture L1-L4 state at signal generation
- **Trade ledger:** Simulate trade execution with TP/SL tracking
- **Reconciliation:** Not needed in backtest (data is perfect)

### Tier 1 - Data Sync
- **OHLCV 4H:** Use local CSV data (2020-2026)
- **OHLCV 1m:** Use cached Binance data (180 days)
- **Market metrics:** CVD, funding, OI (from 4H data with real orderflow)

### Tier 2 - MLP Models
- **Baseline:** Current MLP (4H forward return label)
- **Variant A:** MLP with execution-aligned label (TP before SL)
- **Variant B:** MLP with 1H forward return label (alternative)

### Tier 3 - Asymmetric Exit
- **Baseline:** Fixed TP 0.71% / SL 1.33%
- **Variant A:** Partial TP (60% @ 0.4%, trail 40%)
- **Variant B:** Pure trailing (no fixed TP)

### Tier 4 - Exhaustion Layer
- **Baseline:** No exhaustion check
- **Variant A:** Veto entry when exhaustion_score > 0.7
- **Variant B:** Reduce size 50% when 0.5 < exhaustion_score ≤ 0.7

## 3. Backtest Configuration

### Data Requirements
- **Primary:** 180 days 1m data (cached from Binance)
- **Secondary:** 4H data with microstructure (2020-2026)
- **Period:** 2025-10-26 to 2026-04-24 (180 days)

### Signal Generation
- **Frequency:** Every 4H candle close
- **Filters:**
  - L1 regime: Only trade in "trending" regime
  - L2 alignment: Only trade when EMA vote aligned
  - L3 conviction: Only trade when conviction > threshold
  - L4 volatility: Only trade when vol regime not extreme

### Execution Simulation
- **Entry:** Market order at candle close
- **TP/SL:** Simulated on 1m data (accurate intraday tracking)
- **Partial close:** Simulated by reducing position size
- **Trailing stop:** Simulated by updating SL price based on ATR

## 4. Backtest Matrix

### Configuration Combinations

| Config | MLP Label | Exit Strategy | Exhaustion |
|--------|-----------|---------------|------------|
| **Baseline** | 4H forward return | Fixed TP/SL | None |
| **A** | Execution-aligned | Fixed TP/SL | None |
| **B** | Execution-aligned | Partial TP | None |
| **C** | Execution-aligned | Partial TP | Veto |
| **D** | Execution-aligned | Pure trail | None |
| **E** | 1H forward return | Fixed TP/SL | None |

### Total Configurations: 6

## 5. Metrics to Track

### Primary Metrics
- **Win Rate:** % of trades that hit TP before SL
- **R:R:** Average winner / average loser
- **EV per trade:** Expected value
- **Sharpe Ratio:** Risk-adjusted return
- **Max Drawdown:** Maximum peak-to-trough

### Secondary Metrics
- **Profit Factor:** Gross profit / gross loss
- **Avg Winner %:** Average winning trade percentage
- **Avg Loser %:** Average losing trade percentage
- **Time in Trade:** Average holding time
- **Trade Count:** Number of trades

### Conditional Metrics
- **WR by L1 regime:** Performance in different regimes
- **WR by L4 volatility:** Performance in different vol regimes
- **WR by exhaustion score:** Performance vs exhaustion level

## 6. Implementation Plan

### Phase 1: Data Preparation
1. Load 1m cached data (180 days)
2. Load 4H data with microstructure
3. Resample 1m to 4H for signal generation
4. Precompute indicators (RSI, MACD, EMA, ATR, etc.)

### Phase 2: Signal Generation
1. Implement L1 regime detection (BOCPD)
2. Implement L2 EMA voting
3. Implement L3 MLP prediction (baseline + variants)
4. Implement L4 volatility regime
5. Generate signals with filters

### Phase 3: Execution Simulation
1. Implement fixed TP/SL execution
2. Implement partial TP + trailing
3. Implement pure trailing stop
4. Implement exhaustion veto logic
5. Track MFE/MAE per trade

### Phase 4: Backtest Engine
1. Implement time-series walk-forward
2. Run all 6 configurations
3. Collect metrics per configuration
4. Generate comparison report

### Phase 5: Analysis
1. Compare all configurations
2. Identify best performing config
3. Analyze conditional metrics
4. Generate recommendations

## 7. File Structure

```
backtest_full_architecture/
├── data/
│   ├── load_data.py           # Load 1m + 4H data
│   └── preprocess.py          # Compute indicators
├── signals/
│   ├── l1_regime.py           # BOCPD regime detection
│   ├── l2_ema.py              # EMA voting logic
│   ├── l3_mlp.py              # MLP prediction (variants)
│   └── l4_volatility.py       # Volatility regime
├── execution/
│   ├── fixed_tp_sl.py         # Fixed TP/SL simulation
│   ├── partial_tp.py          # Partial TP + trailing
│   └── trailing_stop.py       # Pure trailing stop
├── exhaustion/
│   ├── exhaustion_score.py    # Compute exhaustion score
│   └── veto_logic.py          # Veto/reduce size logic
├── backtest/
│   ├── engine.py              # Main backtest engine
│   ├── config.py              # Configuration matrix
│   └── metrics.py             # Metrics calculation
├── results/
│   ├── comparison.csv         # Config comparison
│   └── analysis.md            # Analysis report
└── run_backtest.py            # Main entry point
```

## 8. Success Criteria

### Primary Success
- **Config A (execution-aligned)** shows EV improvement ≥ 50% vs baseline
- **Config B (partial TP)** shows avg winner improvement ≥ 50% vs baseline
- **Config C (partial TP + veto)** shows best overall Sharpe ratio

### Secondary Success
- Identify which MLP label performs best
- Identify which exit strategy performs best
- Determine if exhaustion layer adds value

### Failure Criteria
- No configuration shows meaningful improvement
- All variants underperform baseline
- Results are inconsistent across time periods

## 9. Risk Mitigation

### Data Quality
- Use cached 1m data (already validated)
- Cross-check with 4H data for consistency
- Handle missing data gracefully

### Model Quality
- Use pre-trained MLP for baseline
- Train new MLP variants on same data
- Validate with walk-forward

### Simulation Accuracy
- Use 1m data for TP/SL simulation (accurate)
- Implement proper order of operations (low before high)
- Track slippage (assume 0 for now, can add later)

## 10. Timeline Estimate

- **Phase 1:** 0.5 day (data loading + preprocessing)
- **Phase 2:** 1 day (signal generation)
- **Phase 3:** 1 day (execution simulation)
- **Phase 4:** 1 day (backtest engine)
- **Phase 5:** 0.5 day (analysis)

**Total:** ~4 days

## 11. Next Steps

1. Create file structure
2. Implement Phase 1 (data preparation)
3. Implement Phase 2 (signal generation)
4. Implement Phase 3 (execution simulation)
5. Implement Phase 4 (backtest engine)
6. Run backtest and analyze results
