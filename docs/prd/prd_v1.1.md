# ⚡ BTC-QUANT SCALPING PLATFORM
## Product Requirements & Definition of Done
### Improvement Roadmap v1.1 — March 2026

---

| Field | Detail |
|---|---|
| **Project** | BTC-Quant Scalping Platform |
| **Version** | v1.1 — Added I-00: HMM Existence Test |
| **Status** | Draft — Pending Review |
| **Priority** | High — Pre-Live Readiness |
| **Owner** | Developer |
| **Stack** | FastAPI · HMMlearn · sklearn · DuckDB · React/Vite |

**Changelog v1.1:** Added I-00 as a prerequisite existence test for Layer 1 HMM. This item must be completed before any other Phase 1 work begins, as its result determines whether HMM should be retained, tuned, or replaced entirely.

---

## 1. Overview

This document consolidates all improvements required for the BTC-Quant Scalping Platform based on a full code review and architectural analysis. Each improvement item includes a Problem Statement, proposed Solution, and a measurable Definition of Done (DoD) that can be objectively verified.

### Purpose

- Explicitly define the scope and priority of each improvement
- Provide clear DoD so each item can be declared done without ambiguity
- Establish the correct implementation order — from data foundation to model validation
- Serve as a single reference for tracking improvement progress

### Current State

Based on the source code review, the platform already has a mature architecture: a multi-layer signal pipeline (HMM → EMA → MLP → Narrative), BIC-guided n_states selection, NHHM funding rate bias, and HMM→MLP feature cross. However, several critical gaps must be resolved before signals can be trusted quantitatively.

### A Note on Evaluation Philosophy

HMM is an unsupervised model — there is no ground truth label to compare against. Asking "is the HMM accurate?" is a circular question: you would be measuring the model against its own output. The only meaningful question is: **do the regime labels produced by HMM correlate with actual future returns?** If candles labeled "Bullish Trend" are not followed by positive returns more often than chance, then all complexity built on top of Layer 1 — BIC scan, NHHM bias, HMM→MLP feature cross — is amplifying noise, not signal. This is why I-00 is the first item to be executed.

---

## 2. Priority Matrix

| ID | Item | Priority | Effort | Impact | Phase |
|---|---|---|---|---|---|
| **I-00** | **HMM Regime Predictive Power Test** | 🔴 **CRITICAL** | Low | **Existential** | **Phase 1 — First** |
| I-01 | CVD Calculation Fix (Per-Candle) | 🔴 CRITICAL | Medium | High | Phase 1 |
| I-02 | MLP Model Caching / Persistence | 🔴 CRITICAL | Low | High | Phase 1 |
| I-03 | Walk-Forward Validation Framework | 🟠 HIGH | High | Critical | Phase 1 |
| I-08 | Historical Data Expansion | 🟠 HIGH | Low | Critical | Phase 1 |
| I-04 | Sentiment Layer (L5) Integration | 🟠 HIGH | Medium | Medium | Phase 2 |
| I-05 | Regime-Aware SL/TP Multiplier | 🟠 HIGH | Medium | High | Phase 2 |
| I-06 | Enforce Verdict Logic Revision | 🟡 MEDIUM | Low | Medium | Phase 2 |
| I-07 | System Heartbeat & Alerting | 🟡 MEDIUM | Low | High | Phase 3 |

> **Effort:** Low (<1 day), Medium (1–3 days), High (>3 days).
> **I-00 is a prerequisite gate** — its result directly determines whether items I-01 through I-08 are worth pursuing in their current form.

---

## 3. Phase 1 — Foundation & Validation

Phase 1 focuses on items that directly affect data correctness and model integrity. Without completing this phase, accuracy metrics and conviction scores produced by the system cannot be trusted.

**Execution order is strict:** I-08 → I-00 → I-01 → I-02 → I-03.

---

### I-00 — HMM Regime Predictive Power Test ⚠️ PREREQUISITE

**Priority:** 🔴 CRITICAL | **Phase:** 1 — Must run second, after I-08 | **Effort:** Low

#### Why This Exists

This item is not an improvement — it is an **existence test**. Before investing further effort into optimizing Layer 1 (BIC tuning, GMMHMM migration, feature engineering), we must first establish that HMM regime labels have genuine predictive power over future price returns.

The reason "is this HMM accurate?" is the wrong question: HMM is unsupervised, so there is no external ground truth to compare against. Measuring accuracy against the model's own labels is circular and meaningless.

The right question is: **do the regime labels produced by HMM correlate with forward returns?** Specifically — do candles labeled "Bullish Trend" tend to be followed by positive returns, "Bearish Trend" by negative returns, and "Sideways" by returns near zero?

- If **PASS** → HMM has predictive power. Retain and proceed with I-01 onwards.
- If **FAIL** → Layer 1 is generating noise. Replace before building further.

#### Problem

Currently there is no measurement of whether HMM regime labels are predictive of future price movement. All downstream complexity — NHHM funding bias, BIC-guided n_states, HMM→MLP feature cross — is built on the assumption that regime labels are meaningful. This assumption has never been validated.

#### Solution

Implement `backtest/hmm_predictive_power_test.py` as a standalone script. The script should:

1. Load full historical OHLCV from DuckDB
2. Run HMM inference across the entire dataset to generate a regime label for each candle
3. For each candle, compute forward returns at 1-candle, 3-candle, and 5-candle horizons
4. Group candles by regime label and compute mean forward return, win-rate, and t-statistic per group
5. Run the same test across at least 3 non-overlapping time windows to check consistency
6. Output a summary table and save results to CSV

Minimum bar for PASS:
- Mean forward return of "Bullish Trend" candles is **positive** and statistically significant (p < 0.1) in at least 2 of 3 windows
- Mean forward return of "Bearish Trend" candles is **negative** and statistically significant in at least 2 of 3 windows
- Win-rate (return > 0) for Bullish candles exceeds **53%** out-of-sample

#### Definition of Done

- [ ] `backtest/hmm_predictive_power_test.py` runs standalone with no manual input required
- [ ] Script outputs: mean forward return (1C, 3C, 5C), win-rate, and p-value per regime label
- [ ] Test is run across 3 non-overlapping historical windows — results saved to `backtest/results/hmm_power_test.csv`
- [ ] Results are reviewed and a formal decision is documented:
  - **PASS** → HMM labels show directional correlation with forward returns. Proceed with I-01 onwards.
  - **FAIL** → HMM labels show no predictive power. Layer 1 to be replaced or fundamentally redesigned before Phase 1 continues.
- [ ] Decision and supporting evidence are recorded in `backtest/results/hmm_power_test_decision.md`
- [ ] If FAIL: a replacement candidate (e.g., `GMMHMM`, Markov Switching, Change Point Detection) is nominated with rationale

---

### I-08 — Historical Data Expansion

**Priority:** 🟠 HIGH | **Phase:** 1 — Must run first | **Effort:** Low

> **This is the actual first step.** Everything else — I-00's existence test, I-01's CVD quality, I-03's walk-forward — depends on having sufficient historical data. Run this before anything else in Phase 1.

#### Problem

`OHLCV_LIMIT` is currently 100 candles (less than 17 days of 4H data). This is far too little for HMM, which needs to observe multiple complete regime cycles. A BIC scan on 100 candles yields a non-representative optimal `n_states` due to insufficient regime diversity. `GLOBAL_TRAIN_MIN_ROWS = 50` is even more concerning — that is only 8 days of data.

#### Solution

Add a `backfill_historical.py` script that fetches at least 1 year (365 days ≈ 2190 candles) of 4H data from Binance using `ccxt` pagination. Update `OHLCV_LIMIT` to 500 for runtime inference context (~83 days). Raise `GLOBAL_TRAIN_MIN_ROWS` to 500. HMM global training uses the full history; inference uses the recent context window.

#### Definition of Done

- [ ] Database contains at least 1000 4H historical candles after backfill (optimal: 2000+)
- [ ] `GLOBAL_TRAIN_MIN_ROWS` raised to at least 200 (ideally 500)
- [ ] HMM BIC scan is performed with >500 rows for reliable model selection
- [ ] Backfill script is idempotent — can be re-run without creating duplicates (via upsert)
- [ ] HMM global training time with 1000+ candles is measured and acceptable (<30 seconds)

---

### I-01 — CVD Calculation Fix (Per-Candle)

**Priority:** 🔴 CRITICAL | **Phase:** 1 | **Effort:** Medium

> **Dependency:** Run after I-08 (more data improves CVD signal quality) and after I-00 PASS verdict.

#### Problem

CVD is currently calculated from `fetch_trades(limit=1000)`, which fetches the last 1000 trades without any time boundary. In an active BTC market, 1000 trades can represent only a few minutes — not a full 4H candle. As a result, the CVD value fed into HMM as a microstructure feature is temporally inconsistent noise with no meaningful candle alignment.

#### Solution

Replace the CVD implementation with a per-candle accumulated delta. When fetching 4H OHLCV, for each candle compute `net_buy_volume - net_sell_volume` within that candle's open–close timestamp range. Use `fetch_trades` with `since` and `until` timestamp parameters. A more efficient alternative: use Binance's `aggTrades` endpoint (already aggregated) filtered by candle timestamp range.

#### Definition of Done

- [ ] CVD is calculated based on the open–close timestamp range of each 4H candle, not a snapshot of the last 1000 trades
- [ ] Implementation verified by comparing CVD per candle vs price action: a large bullish candle must show a significantly positive CVD
- [ ] No two consecutive candles have identical CVD values (indicator of stale data)
- [ ] Existing CVD data in the database is backfilled or invalidated after the fix is applied
- [ ] Unit tests cover edge cases: very low-volume candles, market halts, missing trades

---

### I-02 — MLP Model Caching / Persistence

**Priority:** 🔴 CRITICAL | **Phase:** 1 | **Effort:** Low

#### Problem

`SignalIntelligenceModel` currently retrains `MLPClassifier` from scratch on every call to `get_ai_confidence()` — which happens on every `/signal` API request. This means: (1) every response incurs full training latency, (2) results can differ between requests due to non-determinism in the Adam optimizer even with `random_state=42`, and (3) the model never incrementally benefits from new candles.

#### Solution

Implement a caching mechanism identical to what already exists in Layer 1 HMM: add `_is_trained`, `_last_trained_len`, and `_last_trained_hash` flags to `SignalIntelligenceModel`. Define `MLP_RETRAIN_EVERY_N_CANDLES` (suggested: 12–24 candles). If new candles since last training are below the threshold, reuse the existing model — only transform the new input without retraining. For persistence across restarts, add optional `joblib.dump/load`.

#### Definition of Done

- [ ] `MLPClassifier` only retrains if at least N new candles have arrived since last training
- [ ] Two consecutive API requests with identical data return the same confidence value
- [ ] `cache_info()` endpoint exposes `is_trained`, `last_trained_len`, `next_retrain_in` for MLP
- [ ] `/signal` response time drops measurably (benchmark before vs after)
- [ ] Model is never stale beyond `GLOBAL_RETRAIN_EVERY_N` candles

---

### I-03 — Walk-Forward Validation Framework

**Priority:** 🟠 HIGH | **Phase:** 1 | **Effort:** High

> **Dependency:** Run last in Phase 1. Requires I-00 PASS, I-01 clean CVD data, I-08 sufficient history, and I-02 stable MLP.

#### Problem

There is currently no mechanism to measure whether the system's signals are predictive out-of-sample. The conviction% and probability values shown to the user have no empirically verified basis. This is the most fundamental reliability gap — the system can appear highly confident while performing no better than random on unseen data.

#### Solution

Implement walk-forward validation in the `backtest/` folder with a minimum 70/30 split. Walk-forward means: train on an initial window, predict on the next window, slide the window, repeat. Measure: win-rate per regime type (Bullish/Bearish/Sideways), average return per signal, maximum drawdown per signal batch, and a simple Sharpe ratio. Minimum acceptable bar: >52% out-of-sample win-rate consistently across 3+ distinct non-overlapping periods before production use.

#### Definition of Done

- [ ] `backtest/walk_forward.py` runs standalone using data from DuckDB
- [ ] Output includes: win-rate per regime, per layer alignment count, per conviction level bucket
- [ ] Validation is performed across at least 3 non-overlapping windows (e.g., Q3/Q4 2024, Q1 2025, Q2 2025)
- [ ] Results are saved to CSV for tracking model improvement across iterations
- [ ] Out-of-sample win-rate exceeds 52% in at least 2 of 3 windows before results are surfaced in the dashboard
- [ ] Backtest uses data the model has never seen during training (strict no-lookahead guarantee)

---

## 4. Phase 2 — Signal Quality & Risk Logic

Phase 2 focuses on improving signal output quality and refining risk management logic. Items in this phase can be worked on in parallel after Phase 1 is complete.

> **Gate:** Phase 2 should only begin after I-00 returns a PASS verdict. If I-00 returns FAIL, Phase 2 scope may change significantly depending on what replaces Layer 1.

---

### I-04 — Sentiment Layer (L5) Integration into Voting

**Priority:** 🟠 HIGH | **Phase:** 2 | **Effort:** Medium

#### Problem

`layer5_sentiment.py` exists and the Fear & Greed Index is already being fetched, but it only appears in `MetricsResponse` without influencing signal logic. An FGI reading in Extreme Greed (>80) while the system outputs STRONG BUY should be a warning flag — it need not block the signal, but it should at minimum reduce position size or lower conviction.

#### Solution

Integrate FGI as a soft filter in `DirectionalSpectrum.calculate()`. At Extreme Greed (>80): reduce `position_size_pct` by 20–30%. At Extreme Fear (<20): reduce `position_size_pct` for LONG signals. Sentiment does not veto signals — it only modulates conviction. Add a `sentiment_adjustment` field to `SpectrumResult` for transparency.

#### Definition of Done

- [ ] FGI value is an explicit input to the spectrum calculation, not just a display metric
- [ ] Position size automatically decreases under Extreme Greed/Fear per a defined formula
- [ ] `sentiment_adjustment` field appears in the API response with value and reasoning
- [ ] Frontend dashboard displays the sentiment adjustment explicitly
- [ ] Unit tests cover: FGI=90 + STRONG BUY, FGI=15 + STRONG SELL, FGI=50 (neutral, no adjustment)

---

### I-05 — Regime-Aware SL/TP Multiplier

**Priority:** 🟠 HIGH | **Phase:** 2 | **Effort:** Medium

#### Problem

SL/TP currently uses flat multipliers (`ATR*1.5` for SL, `ATR*2.5` for TP2) regardless of market regime. In a High Volatility Sideways regime, price is more likely to mean-revert — a wide TP is rarely hit and a tight SL frequently trips on noise. In a Bullish/Bearish Trend regime, these parameters are more appropriate since momentum supports extended moves.

#### Solution

Create a `REGIME_SL_TP_MULTIPLIERS` config dict in `signal_service.py`:

- **Bullish/Bearish Trend:** SL=1.5x ATR, TP1=2.0x, TP2=3.5x (allow runners)
- **High Volatility Sideways:** SL=2.0x ATR (wider, to absorb noise), TP1=1.2x, TP2=1.8x (tighter, mean-revert targets)
- **Low Volatility Sideways:** SL=1.0x ATR, TP1=1.5x, TP2=2.0x

Multipliers are selected based on `hmm_label` from the current regime.

#### Definition of Done

- [ ] SL/TP multipliers differ per regime type (minimum 3 presets: Trending, HV-Sideways, LV-Sideways)
- [ ] API response includes `regime_sl_tp_preset` field for transparency
- [ ] Backtest mode can measure win-rate per regime with old vs new multipliers for comparison
- [ ] No hardcoded multipliers in `signal_service.py` — all via config dict
- [ ] Edge case: Unknown/Data Insufficient regime falls back to a defined conservative default multiplier

---

### I-06 — Enforce Verdict Logic Revision

**Priority:** 🟡 MEDIUM | **Phase:** 2 | **Effort:** Low

#### Problem

`_enforce_verdict()` is currently too aggressive: if `score >= 80`, the verdict is hardcoded to STRONG BUY/SELL without considering LLM output at all. This renders LLM synthesis completely useless in high-conviction scenarios, even though the LLM may have more nuanced market context (e.g., upcoming macro events, sentiment anomalies).

#### Solution

Change `_enforce_verdict()` to a hybrid approach: at `score >= 80`, the LLM verdict is still considered but with relaxed constraints. If the LLM outputs NEUTRAL at `score >= 80`, downgrade to WEAK BUY/SELL instead of overriding to STRONG. Add an `llm_override_reason` field in the response for transparency about when the LLM successfully modified the verdict.

#### Definition of Done

- [ ] LLM verdict is never completely ignored when `score >= 80`
- [ ] If LLM returns NEUTRAL at `score >= 80`, final verdict is WEAK BUY/SELL (not STRONG)
- [ ] `llm_override_reason` field appears in the confluence response
- [ ] Unit tests cover all combinations of (score × llm_verdict × trend_short)
- [ ] No verdict is directionally inconsistent with `trend_short` (Bullish trend cannot produce a SELL verdict)

---

## 5. Phase 3 — Observability & Reliability

Phase 3 focuses on monitoring infrastructure and reliability so the system can operate unattended without losing data or generating signals based on stale inputs.

---

### I-07 — System Heartbeat & Alerting

**Priority:** 🟡 MEDIUM | **Phase:** 3 | **Effort:** Low

#### Problem

There is no alerting mechanism if `data_engine.py` crashes or stops ingesting data. If the pipeline dies overnight, signals displayed on the dashboard will be based on stale data with no clear visual indication. A trader could make decisions based on data that is hours old.

#### Solution

Implement a heartbeat check: persist a `last_pipeline_run` timestamp to DuckDB on every successful pipeline cycle. Add a `GET /health` endpoint in FastAPI that checks whether `last_pipeline_run` is more than 2 hours ago. If stale, return HTTP 503 with a detailed status payload. Optional: send a Telegram notification via bot if no new data has arrived within X minutes. The frontend dashboard should display a data freshness indicator.

#### Definition of Done

- [ ] `GET /health` returns `{ status: ok | degraded | stale, last_update: ISO8601 }`
- [ ] If data has not been updated in 2 hours, `/signal` response includes a `staleness_warning` field
- [ ] Frontend dashboard displays a color-coded freshness indicator: green (<1 hr), yellow (1–2 hrs), red (>2 hrs)
- [ ] Optional Telegram alert: notification sent if pipeline is down for >30 minutes
- [ ] Heartbeat timestamp is stored in a `pipeline_health` table in DuckDB

---

## 6. Execution Order Summary

```
Phase 1 (strict order):
    I-08  →  Expand historical data first (everything else depends on this)
    I-00  →  HMM existence test — PASS/FAIL gate for all subsequent work
    I-01  →  Fix CVD per-candle (cleaner microstructure features)
    I-02  →  Cache MLP model (prerequisite for reliable walk-forward)
    I-03  →  Walk-forward validation (full pipeline out-of-sample test)

Phase 2 (parallel, after Phase 1 PASS):
    I-04  →  Sentiment layer voting integration
    I-05  →  Regime-aware SL/TP multipliers
    I-06  →  Enforce verdict logic revision

Phase 3 (can run any time):
    I-07  →  Heartbeat & alerting
```

> If I-00 returns **FAIL**: stop Phase 1 after I-08 and I-01. Redesign Layer 1 before proceeding.
> Document the replacement decision in `backtest/results/hmm_power_test_decision.md`.

---

## 7. Global Acceptance Criteria

The full improvement set is considered complete and the platform is ready for more serious use when **all** of the following criteria are met:

### Layer 1 Validity

- [ ] I-00 returned PASS — HMM regime labels show statistically significant correlation with forward returns in at least 2 of 3 out-of-sample windows
- [ ] If I-00 returned FAIL — Layer 1 has been replaced with a model that passes the same predictive power test

### Data Integrity

- [ ] CVD per-candle is implemented and verified against price action visually
- [ ] Database contains at least 1000 4H historical candles
- [ ] No NaN, infinite, or stale values in the HMM and MLP feature matrices

### Model Reliability

- [ ] MLP does not retrain on every request — caching is active with a defined threshold
- [ ] Walk-forward validation shows >52% out-of-sample win-rate in at least 2 of 3 windows
- [ ] HMM regime distribution is reasonable — no single regime dominates >80% in a normal market window

### Signal Quality

- [ ] SL/TP multipliers vary per regime — not flat `ATR*1.5` for all market conditions
- [ ] LLM verdict is not fully overridden at `score >= 80`
- [ ] Sentiment (FGI) automatically affects position size under Extreme Greed/Fear

### Observability

- [ ] `GET /health` endpoint is available and accurate
- [ ] Dashboard displays a data freshness indicator
- [ ] `cache_info()` is available for both HMM and MLP with full training status information

---

*This is a living document — update as implementation progresses.*
*v1.1: Added I-00 HMM Predictive Power Test as prerequisite gate for all Phase 1 work.*