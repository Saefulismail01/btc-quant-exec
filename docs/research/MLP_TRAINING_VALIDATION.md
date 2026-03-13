# MLP Training Methodology — Deep Validation Analysis

**Analysis Date:** 2026-03-13
**Scope:** Layer 3 MLP training process, lookahead bias detection, validation methodology

---

## Executive Summary

**Verdict:** ✅ **NO CATASTROPHIC LOOKAHEAD BIAS**, but **2 important caveats**:

1. ✅ **Training uses proper forward-looking target** (next N-candle return)
2. ✅ **Features are contemporaneous** (don't use future data)
3. ✅ **Last row excluded from training** (prevents target leakage)
4. ⚠️ **However: Re-training happens EVERY 48 CANDLES** (on live data)
5. ⚠️ **Validation split only 15%** (small hold-out set)

---

## 1. TRAINING PIPELINE OVERVIEW

### Location: `backend/app/core/engines/layer3_ai.py`

**Flow:**
```
get_ai_confidence()
    ├─ prepare_data()       [features + target engineering]
    │   ├─ Calculate 8 technical features
    │   ├─ Create target = future price movement (W=1 candle ahead)
    │   ├─ Drop last row (no target available)
    │   └─ Return (X_train, Y, X_latest)
    │
    ├─ fit scaler on X_train only
    │
    ├─ train_model()         [MLPClassifier.fit()]
    │   ├─ Validation split: 15% hold-out
    │   ├─ Early stopping: True
    │   └─ Architecture: (128,64) or (256,128)
    │
    └─ predict on X_latest (inference)
```

---

## 2. DATA LEAKAGE ANALYSIS: ✅ CLEAN

### A. Target Definition (Lines 257-278)

```python
W = MLP_FORWARD_RETURN_WINDOW  # = 1 (OPT-A)

df_feat["future_close"] = df_feat["Close"].shift(-W)  # NEXT candle close
df_feat["price_move_pct"] = (
    (df_feat["future_close"] - df_feat["Close"]) / df_feat["Close"]
)

# Smart thresholding to create 3-class target
target_threshold = 0.5 * norm_atr * sqrt(W)
target = {
    2 (BULL)    if move > +threshold
    0 (BEAR)    if move < -threshold
    1 (NEUTRAL) else
}
```

**Analysis:**
- ✅ `future_close` uses `.shift(-1)` → future value relative to current row
- ✅ Target represents: "Will next 1 candle go up/down/sideways?"
- ✅ Threshold scales with volatility (0.5 × ATR × √W)

**Risk Assessment:** 🟢 **ZERO lookahead bias here**
- Target depends on `Close[t+1]`, which is NOT in features
- Features only use `Close[t]` and prior candles

---

### B. Feature Engineering (Lines 229-253)

```python
df_feat["rsi_14"]      = ta.rsi(df["Close"], length=14)      # ✅ Uses close[t]
df_feat["macd_hist"]   = ta.macd(df["Close"], ...)           # ✅ Uses close[t]
df_feat["ema20_dist"]  = (close[t] - ema20[t]) / ema20[t]    # ✅ Uses close[t]
df_feat["log_return"]  = log(close[t] / close[t-1])          # ✅ Uses t and t-1
df_feat["norm_atr"]    = atr[t] / close[t]                   # ✅ Uses atr[t]
df_feat["norm_cvd"]    = cvd[t] / volume[t]                  # ✅ Uses cvd[t]
df_feat["funding"]     = funding_rate[t]                     # ✅ Uses t
df_feat["oi_change"]   = oi[t].pct_change()                  # ✅ Uses t and t-1
```

**Analysis:**
- ✅ All features are **contemporaneous** (use data up to candle t, not beyond)
- ✅ No future prices embedded
- ✅ RSI, MACD, EMA use lookback windows but NO forward data

**Risk Assessment:** 🟢 **ZERO lookahead bias**

---

### C. Training/Inference Split (Lines 310-325)

```python
# BEFORE dropna and feature generation:
last_row = df_feat[active_feat_cols].iloc[[-1]]  # Get last row FEATURES
X_latest_raw = last_row.values                   # shape (1, 5 or 9)

# AFTER extracting inference row:
df_train = df_feat.iloc[:-1].dropna(...)         # DROP last row
X_train_raw = df_train[active_feat_cols].values  # EXCLUDE last row
Y = df_train["target"].values                    # EXCLUDE last target
```

**Sequence:**
```
Row t-2: features[t-2], target[t-2] (next candle direction) → TRAIN ✅
Row t-1: features[t-1], target[t-1] (next candle direction) → TRAIN ✅
Row t:   features[t],   target[t]   (UNKNOWN yet)          → INFERENCE ONLY ✅
```

**Analysis:**
- ✅ Last row (current candle) excluded from training
- ✅ No training on row where target isn't known yet
- ✅ Prevents catastrophic data leakage

**Risk Assessment:** 🟢 **ZERO lookahead bias here**

---

## 3. TRAINING METHODOLOGY: ⚠️ IMPORTANT CAVEATS

### A. sklearn MLPClassifier Parameters (Lines 353-363)

```python
self.model = MLPClassifier(
    hidden_layer_sizes = (128, 64) or (256, 128),  # Scales with features
    activation         = "relu",
    solver             = "adam",
    max_iter           = 300,
    early_stopping     = True,               # ← STOPS if val loss doesn't improve
    validation_fraction = 0.15,              # ← 15% HOLD-OUT SET
    random_state       = 42,                 # ← DETERMINISTIC (good)
)
self.model.fit(X_train_scaled, Y)
```

**Issues:**

1. **Validation split only 15%** (of training set)
   - With 455 backtest trades → ~10-15 data points per fold
   - **Statistically weak** for proper cross-validation
   - Better: 5-fold cross-validation

2. **No explicit test set mentioned**
   - MLPClassifier trains on (X_train, Y)
   - 15% validation automatically reserved
   - But **entire training set is same data as backtest test set**
   - = **Weak generalization test**

3. **Early stopping on validation loss**
   - Good for preventing overfitting
   - But validation set might be cherry-picked (not uniform distribution)

### B. Re-training Frequency (Lines 441-447)

```python
needs_retrain = (
    not self._is_trained
    or self.model is None
    or (current_len - self._last_trained_len) >= MLP_RETRAIN_EVERY_N_CANDLES
    or current_len < self._last_trained_len
    or _vol_spike   # [FIX-5b]
)

# MLP_RETRAIN_EVERY_N_CANDLES = 48
```

**Problem:** Every 48 candles (192 hours = 8 days), model retrains on NEW data.

**Implication:**
- ✅ Adapts to changing market
- ⚠️ But **introduces look-ahead bias in live training**:
  ```
  Candle 48: Retrain using candles 0-48 (target[48] = "is candle 49 up?")
  Live signal at candle 48: Uses model trained ON CANDLE 48'S TARGET
  ```

**Risk:** Model trained on most recent candles = latest regime only, could overfit to last week's pattern.

---

## 4. VALIDATION METHODOLOGY: ⚠️ INSUFFICIENT

### Current Approach:
1. Feature engineering on full historical dataset
2. Train on ALL data except last row
3. Use 15% internal validation split
4. Predict on current candle

### Missing:
- ❌ **Walk-forward validation** (train on 1-6 months, test on next month)
- ❌ **Out-of-sample test set** (separate final evaluation period)
- ❌ **Time-series cross-validation** (proper temporal splits)
- ❌ **Feature importance analysis** (which features actually matter?)
- ❌ **Ablation study** (performance without each feature)

### Why This Matters:

**Backtest WR by regime:**
```
Bear:    47.1% ← BELOW 50%, statistically weak
Bull:    58.8%
Neutral: 64.2%
```

**Question:** If model was properly cross-validated with bear data:
- Would bear WR still be 47% or is this overfitting to 2024-26 bull market?
- Current approach trains on ALL data → includes recent bull bias

---

## 5. FEATURE IMPORTANCE: ⚠️ UNKNOWN

**Current features:**
```
rsi_14        — RSI momentum
macd_hist     — MACD momentum
ema20_dist    — Price proximity to trend
log_return    — Price change magnitude
norm_atr      — Volatility normalization
norm_cvd      — Cumulative volume delta (microstructure)
funding       — Funding rate (futures sentiment)
oi_change     — Open interest change rate
```

**Missing:** Which ones actually matter?

```python
# NOT in code:
# mlp.feature_importances_  # sklearn MLPClassifier doesn't expose
# Need: Permutation importance or SHAP values
```

**Risk:** Some features could be:
- **Noise** (decreases performance)
- **Redundant** (correlated with others)
- **Unstable** (changes meaning in different markets)

**Example:** `funding` is futures sentiment
- In bull market: funding > 0 → confirm buy
- In bear market: funding < 0 → confirm sell
- In ranging market: funding noise
- No interaction logic visible

---

## 6. LIVE RETRAINING SAFETY: ⚠️ CONCERNING

### Scenario: Live Trading at Candle 1000

**What happens:**
1. At candle 1000: `current_len=1000, last_trained_len=960` → needs_retrain=True
2. Feature engineer on **rows 0-1000**
3. Drop row 1000 (no target yet)
4. Train on rows 0-999
5. Use row 1000 features for signal → TRADE

**Problem:** Model trained on **most recent 1000 candles** = recent market bias

**Example Bear Market Scenario:**
- Week 1 (bull): WR 65%, model absorbs "bull signals" heavily
- Week 2 (sudden bearish): Model still biased toward bull interpretation
- All week 2 signals might be BULL → loses money

**Mitigation:** Re-training happens, but with lag:
- Takes 8 days (48 candles) to detect regime shift
- In volatile market, 8 days = too slow

---

## 7. CONFIDENCE INTERVALS & STATISTICAL POWER

### From Backtest (455 trades, 57% WR):

```
Population: True WR = p
Sample:     Observed WR = 57% (n=455)
Confidence: 95% CI = 57% ± 4.6% = [52.4%, 61.6%]

By regime:
Bear (n=119): WR=47.1%, 95% CI = [38.1%, 56.1%] ← INCLUDES 50% ✗
Bull (n=216): WR=58.8%, 95% CI = [52.2%, 65.4%] ← EXCLUDES 50% ✓
Neutral (n=120): WR=64.2%, 95% CI = [55.2%, 73.2%] ← EXCLUDES 50% ✓
```

**Interpretation:**
- **Bear WR statistically INDISTINGUISHABLE from 50%** (random chance)
- Bull/Neutral are significant
- = Model has NO edge in bear markets

---

## 8. LOOKAHEAD BIAS VERDICT: ✅ TECHNICALLY CLEAN, BUT...

### What We Know:

1. ✅ **No forward data in features**
   - All features use contemporaneous or past data
   - No `Close[t+1]` or `Close[t+2]` sneaking in

2. ✅ **Target is proper forward-looking**
   - Target = "will next 1 candle return > threshold?"
   - Created from `Close.shift(-1)` (future value)
   - NOT available at training time

3. ✅ **Training/inference properly separated**
   - Last row excluded from training
   - Prevents leaking current row's target

### But We Should Worry About:

1. ⚠️ **Live re-training on recent data**
   - Every 48 candles: retrain on latest market state
   - Could amplify recent regime bias
   - Takes 8 days to detect regime shift

2. ⚠️ **No proper walk-forward validation**
   - Backtest trains on ALL historical data
   - Real WR on unseen data unknown
   - Could be 50% if overfitted to bull market (2024-26)

3. ⚠️ **Bear regime WR = 47.1%**
   - Statistically NOT better than random
   - Suggests model overfitted to bull data
   - In real bear market: **expect WR to collapse**

---

## 9. RECOMMENDATIONS

### Immediate (Before Testnet):

- [ ] **Run permutation feature importance**
  ```python
  from sklearn.inspection import permutation_importance
  perm = permutation_importance(mlp, X_test, Y_test, n_repeats=10)
  # See which features actually help
  ```

- [ ] **Walk-forward validation on historical data**
  ```python
  # Train on 2023-Q1 to Q3, test on Q4
  # Train on 2023-Q2 to Q4, test on 2024-Q1
  # ... repeat for 8 windows
  # Report WR by regime per window
  ```

- [ ] **Test on bear market only**
  ```python
  # 2022-06 to 2022-11 (pure bear)
  # Model trained on: 2019-2022-05
  # Test on: 2022-06 to 2022-11
  # Actual WR = ?
  ```

### Before Mainnet:

- [ ] **Reduce retrain frequency** (48 → 200 candles)
  - Current 8-day window too aggressive
  - More stable model, slower adaptation trade-off

- [ ] **Implement proper cross-validation**
  - 5-fold temporal cross-validation
  - Report per-fold WR metrics

- [ ] **Add outlier detection**
  - Monitor if live WR drops below 54%
  - Trigger circuit breaker

- [ ] **Feature stability analysis**
  - How do feature distributions differ bull/bear/neutral?
  - Which features flip sign?
  - Any features that are regime-specific?

---

## 10. MAINNET SAFETY ASSESSMENT

### Risk Matrix:

| Scenario | Probability | Impact | Mitigation |
|----------|------------|--------|-----------|
| **No lookahead bias** | **HIGH** | Model valid | ✅ CONFIRMED |
| **Bear WR collapses to <45%** | **MEDIUM** | Losses mount | Testnet validation |
| **Live retraining amplifies bias** | **MEDIUM** | Performance degradation | Reduce retrain freq |
| **Unseen data WR lower than backtest** | **MEDIUM** | 10-15% slippage | Walk-forward validation |

### Go-Live Checklist:

- [x] **No forward data leakage** — ✅ CONFIRMED
- [ ] **Proper cross-validation methodology** — ⚠️ PENDING
- [ ] **Bear market performance** — ⚠️ PENDING (47% WR is weak)
- [ ] **Feature stability across regimes** — ⚠️ PENDING
- [ ] **Live retraining impact** — ⚠️ PENDING

---

## Honest Summary

**Good News:**
- ✅ Training code is clean, no catastrophic lookahead bias
- ✅ Feature engineering proper, no future data sneaking
- ✅ Training/inference separated correctly

**Concerns:**
- ⚠️ Model trained on **all data** — weak generalization test
- ⚠️ Bear market WR = **47.1%** — statistically weak
- ⚠️ Live retraining every 48 candles — could amplify bias
- ⚠️ No feature importance analysis — unknown which features work

**Verdict for Testnet:**
- ✅ **Proceed to testnet**, but with bear market focus
- ⚠️ Monitor WR closely in each regime
- ⚠️ Be ready to reduce position size if WR diverges

**Verdict for Mainnet:**
- ⏳ **NOT READY** until:
  - Walk-forward validation shows consistent WR
  - Bear market testnet run (2+ weeks minimum)
  - Feature importance analysis complete
  - Live retraining frequency tuned
