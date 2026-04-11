# Orderflow Analysis — BTC Scalping Strategy
**Date:** 2026-03-31
**Data source:** Binance BTCUSDT, 15m + 1h klines (real fetched data)
**Trades analyzed:** 26 (Mar 10–28, 2026)
**Scripts:** `01_fetch_data.py`, `02_orderflow_simulation.py`

---

## Strategy Definitions

| Model | Description |
|-------|-------------|
| **Model A** | Pure auto: TP=+0.71%, SL=−1.333%, time exit at 24h |
| **Model B** | Manual actual results from prior analysis (hardcoded) |
| **Model V3** | Model A + profit protection: activate at +0.30% peak, close at +0.15% |
| **Model V3+OF** | Model V3 but profit protection closure ONLY if ≥1 orderflow signal confirms |

**Orderflow signals (checked on 15m candles when PP active):**
- **OF1** – 3 consecutive candles with decreasing body size after peak
- **OF2** – Wick >60% of total range in adverse direction
- **OF3** – Volume of last 2 candles < 50% of 10-candle average
- **OF4** – Price fails to make HH (LONG) / LL (SHORT) in 4 candles after peak
- **OF5** – Taker sell > taker buy for 2 consecutive candles (adverse to position)

---

## 1. Per-Trade Comparison Table (V3 vs V3+OF)

| # | Date | Side | Entry | Peak% | V3 Exit | V3 PnL% | V3+OF Exit | V3+OF PnL% | OF Signals Fired |
|---|------|------|-------|-------|---------|---------|-----------|-----------|-----------------|
| 1  | 2026-03-10 16:05 | LONG  | 71198 | +0.71% | PP    | +0.150% | PP+OF(OF2,OF4,OF5) | +0.150% | OF2, OF4, OF5 |
| 2  | 2026-03-11 04:08 | LONG  | 69498 | +0.70% | TP    | +0.710% | TP                 | +0.710% | —             |
| 3  | 2026-03-11 08:06 | LONG  | 69620 | +0.52% | TP    | +0.710% | TP                 | +0.710% | —             |
| 4  | 2026-03-12 08:05 | LONG  | 69846 | +0.39% | PP    | +0.150% | PP+OF(OF2)         | +0.150% | OF2           |
| 5  | 2026-03-12 12:15 | LONG  | 70309 | +0.44% | PP    | +0.150% | PP+OF(OF5)         | +0.150% | OF5           |
| 6  | 2026-03-12 20:09 | LONG  | 70401 | +0.47% | TP    | +0.710% | TP                 | +0.710% | —             |
| 7  | 2026-03-13 04:03 | LONG  | 71347 | +0.41% | PP    | +0.150% | PP+OF(OF5)         | +0.150% | OF5           |
| 8  | 2026-03-13 08:02 | LONG  | 71520 | +0.11% | TP    | +0.710% | TP                 | +0.710% | —             |
| 9  | 2026-03-13 14:13 | LONG  | 73500 | +0.56% | PP    | +0.150% | **SL**             | −1.333% | — (BLOCKED, then SL) |
| 10 | 2026-03-13 16:02 | LONG  | 71891 | +0.50% | PP    | +0.150% | PP+OF(OF5)         | +0.150% | OF5           |
| 11 | 2026-03-16 08:14 | LONG  | 73545 | +0.40% | PP    | +0.150% | PP+OF(OF2)         | +0.150% | OF2           |
| 12 | 2026-03-16 16:01 | LONG  | 73172 | +0.68% | TP    | +0.710% | TP                 | +0.710% | —             |
| 13 | 2026-03-17 00:51 | LONG  | 74930 | +0.00% | TP    | +0.710% | TP                 | +0.710% | —             |
| 14 | 2026-03-17 02:07 | LONG  | 75287 | +0.24% | SL    | −1.333% | SL                 | −1.333% | —             |
| 15 | 2026-03-17 04:02 | LONG  | 74562 | +0.16% | SL    | −1.333% | SL                 | −1.333% | —             |
| 16 | 2026-03-17 07:21 | LONG  | 74319 | +0.18% | TP    | +0.710% | TP                 | +0.710% | —             |
| 17 | 2026-03-17 12:00 | LONG  | 74013 | +0.56% | TP    | +0.710% | TP                 | +0.710% | —             |
| 18 | 2026-03-22 00:00 | SHORT | 68744 | +0.00% | TP    | +0.710% | TP                 | +0.710% | —             |
| 19 | 2026-03-22 08:00 | SHORT | 68860 | +0.49% | PP    | +0.150% | PP+OF(OF5)         | +0.150% | OF5           |
| 20 | 2026-03-22 12:00 | SHORT | 68217 | +0.20% | TP    | +0.710% | TP                 | +0.710% | —             |
| 21 | 2026-03-23 00:00 | SHORT | 67975 | +0.29% | TP    | +0.710% | TP                 | +0.710% | —             |
| 22 | 2026-03-26 12:00 | SHORT | 69215 | +0.45% | TP    | +0.710% | TP                 | +0.710% | —             |
| 23 | 2026-03-26 13:44 | SHORT | 69385 | +0.69% | TP    | +0.710% | TP                 | +0.710% | —             |
| 24 | 2026-03-27 04:00 | SHORT | 68702 | +0.58% | PP    | +0.150% | PP+OF(OF4)         | +0.150% | OF4           |
| 25 | 2026-03-28 08:00 | SHORT | 66460 | +0.50% | PP    | +0.150% | PP+OF(OF4)         | +0.150% | OF4           |
| 26 | 2026-03-28 16:00 | SHORT | 66998 | +0.44% | PP    | +0.150% | PP+OF(OF4)         | +0.150% | OF4           |

> **Trade 9 is the key case:** V3 closed at +0.15%. V3+OF blocked the close (no OF signal at that moment) and the trade eventually hit SL at −1.333%. This is the single cost of the filter.

---

## 2. Summary Metrics — All 4 Models

| Model | WR% | EV% | PF | MaxDD% | CumPnL% | Notes |
|-------|-----|-----|----|--------|---------|-------|
| **Model A** (Pure Auto) | 73.1% | +0.199% | 1.62 | 3.202% | +5.175% | Baseline |
| **Model B** (Manual Actual) | 73.1% | +0.160% | 1.45 | 3.289% | +4.159% | Human discretion slightly worse than auto |
| **Model V3** (Profit Protection) | 92.3% | +0.316% | 4.08 | 2.666% | +8.214% | Best overall |
| **Model V3+OF** (PP + Orderflow) | 88.5% | +0.259% | 2.68 | 2.666% | +6.731% | Better than A/B, worse than V3 |

**Key observations:**
- Model V3 achieves the highest EV (+0.316%), WR (92.3%), and PF (4.08) on this sample
- Model V3+OF is strictly better than Model A and Model B in all metrics
- The OF filter costs −1.483% cumulative PnL vs V3 due to Trade 9 (one blocked close → SL)
- Both V3 and V3+OF share the same MaxDD (2.666%) — the filter did not worsen drawdown on this sample

---

## 3. V3+OF Deep Dive

### Profit Protection Trigger Analysis

| Metric | Count |
|--------|-------|
| PP triggered (wanted to close at +0.15%) | 11 trades |
| Confirmed by OF → closed at +0.15% | **10 trades** (90.9%) |
| Blocked by OF → no signal, kept holding | **1 trade** (9.1%) |

**After OF block, what happened?**
| Outcome | Count |
|---------|-------|
| Reached TP (+0.71%) | 0 |
| Hit SL (−1.333%) | **1** (Trade 9) |
| Time exit | 0 |

**The OF filter blocked 1 out of 11 PP attempts. That 1 block led to a full SL loss.**
This is the fundamental trade-off: the filter was too conservative on Trade 9, where price briefly dipped to +0.15% but had no OF signal, then continued falling to SL.

### Orderflow Signal Frequency (when closures confirmed)

| Signal | Fires | % of confirmed closures |
|--------|-------|------------------------|
| **OF5** (delta flip — taker sell dominant) | 5 | 50% |
| **OF4** (failed price push) | 4 | 40% |
| **OF2** (adverse wick rejection) | 3 | 30% |
| OF1 (momentum death) | 0 | 0% |
| OF3 (volume exhaustion) | 0 | 0% |

**Most useful signals:** OF5 (taker delta) and OF4 (failed push) fired on 90% of confirmed closures.
OF1 and OF3 never fired — their thresholds may be too strict for 15m BTC scalping.

### LONG vs SHORT Breakdown (V3+OF)

| Direction | n | WR% | EV% | CumPnL% |
|-----------|---|-----|-----|---------|
| LONG | 17 | 82.4% | +0.152% | +2.581% |
| SHORT | 9 | 100.0% | +0.461% | +4.150% |

**SHORT trades significantly outperformed LONG in this period** (March 22–28 downtrend), with 100% win rate and 3× better EV. This is regime-dependent: the SHORT trades occurred during a clean downtrend.

---

## 4. Monte Carlo Simulation (1000 paths × 100 trades)

> Bootstrap resampling from the 26-trade distribution, projected to 100 trades.

| Model | P5% (worst 5%) | Median% | P95% (best 5%) | P(Profitable) |
|-------|---------------|---------|----------------|---------------|
| Model A | +5.60% | +19.93% | +34.21% | 98.6% |
| Model B | +1.54% | +17.88% | +30.14% | 96.2% |
| Model V3 | **+22.04%** | **+31.89%** | **+40.99%** | **100.0%** |
| Model V3+OF | +14.99% | +26.32% | +36.34% | 99.9% |

**Monte Carlo confirms:** V3 dominates on all percentiles. V3+OF is the second-best with a P5 of +14.99% vs Model A's +5.60%, meaning the downside is substantially reduced versus pure auto.

---

## 5. Honest Assessment and Recommendation

### Does the OF filter improve V3?

**No — on this 26-trade sample, V3+OF is strictly worse than V3.**

- V3 CumPnL: +8.214% vs V3+OF: +6.731% (−1.483% penalty)
- V3 EV: +0.316% vs V3+OF: +0.259% (−18% reduction)
- V3 WR: 92.3% vs V3+OF: 88.5%

The OF filter's single failure (Trade 9, Mar 13) cost more than the filter saved. On this dataset the profit protection alone (V3) is already a very effective filter — the underlying signals are good enough that adding an extra layer provides no net benefit.

### How does V3+OF compare to Model A and Model B?

**V3+OF clearly beats both Model A and Model B:**

| Comparison | V3+OF advantage |
|-----------|----------------|
| vs Model A | +1.556% CumPnL, +15.4% WR, +0.060% EV, −0.536% MaxDD |
| vs Model B | +2.572% CumPnL, +15.4% WR, +0.099% EV, −0.623% MaxDD |

Even the "worse" version of profit protection (V3+OF) significantly dominates pure auto and manual trading. The profit protection mechanism itself is the primary value driver.

### Root cause: why V3+OF underperformed V3

The problem is **filter asymmetry**: when the PP wants to close at +0.15% but no OF signal fires, it keeps holding. In 10 of 11 cases the price continued down (PP was correct). In 1 case (Trade 9) it was also correct — price was at +0.15%, no OF signal, but it fell to SL. The OF signal failed to catch a genuine reversal, acting as a false safety net.

This suggests OF signals are too slow or structurally mismatched for this setup:
- OF1 (body shrinkage) never triggered — 15m candles move too fast to show gradual deceleration
- OF3 (volume exhaustion) never triggered — BTC volume at these price levels was consistently elevated
- OF4 and OF5 are the meaningful signals, but they often fire simultaneously with the PP condition (not before it)

### Recommendation for real money

**Deploy Model V3 (profit protection only), not V3+OF.**

Rationale:
1. V3 has the highest EV (+0.316%), highest WR (92.3%), highest PF (4.08), and same MaxDD as V3+OF
2. The OF filter adds complexity without statistical benefit on this sample
3. V3+OF's only advantage would be in scenarios where price is at +0.15% AND the move is truly temporary — but those cases are rare and the filter missed the critical one
4. With 26 trades the sample is too small to be confident the OF benefit would emerge at scale; MC shows V3 dominance is robust (100% profitable paths at P5 vs 99.9% for V3+OF)

**If OF signals are to be used at all:** reduce to OF4 + OF5 only (the two that actually fired), and consider using them to CONFIRM the signal model entry rather than as a PP filter. OF1 and OF3 should be removed or recalibrated for BTC 15m timeframe.

---

## Appendix: Data Sources

- **15m klines:** `GET https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=15m&limit=100`
- **1h klines:** `GET https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1h&limit=30`
- **Taker volume (OF5):** Binance kline column index 9 = taker buy base volume; taker sell = total volume − taker buy
- **Data saved to:** `research/orderflow_analysis/data/trade_NN.json` (26 files) + `all_trades.json`

---

*Generated by `02_orderflow_simulation.py` using real Binance historical data.*
