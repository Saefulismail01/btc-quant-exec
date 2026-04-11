# V3 Profit Protection — Parameter Sensitivity Test

Generated: 2026-03-31

```
================================================================================
BTC-QUANT V3 Parameter Sensitivity Test
Date: 2026-03-31  |  Trades: 26  |  Candles: 15m Binance BTCUSDT
================================================================================

Loading cached kline data...
  Active trades: 26/26

Model A (baseline):
  ALL  (26 trades): EV=+0.199%  WR=73.1%  CumPnL=+5.175%
  TRAIN(16 trades): EV=-0.056%  WR=62.5%  CumPnL=-0.898%
  TEST (10 trades): EV=+0.607%  WR=90.0%  CumPnL=+6.073%

================================================================================
PARAMETER GRID SEARCH — ALL VALID COMBINATIONS
================================================================================

--- Section 1: Full Grid Results (sorted by EV%, all 26 trades) ---

|  act% | close% |   WR% |    EV% |    PF | MaxDD% |  CumPnL% | note
|------|--------|-------|--------|-------|--------|----------|------
|  0.45 |   0.30 |  92.3 | +0.411 |  5.01 |  2.666 |  +10.684 | 
|  0.45 |   0.15 |  92.3 | +0.402 |  4.92 |  2.666 |  +10.454 | 
|  0.50 |   0.30 |  88.5 | +0.395 |  3.57 |  2.666 |  +10.281 | 
|  0.40 |   0.30 |  92.3 | +0.395 |  4.85 |  2.666 |  +10.274 | 
|  0.45 |   0.25 |  92.3 | +0.394 |  4.84 |  2.666 |  +10.234 | 
|  0.45 |   0.10 |  92.3 | +0.389 |  4.79 |  2.666 |  +10.104 | 
|  0.50 |   0.25 |  88.5 | +0.386 |  3.51 |  2.666 |  +10.031 | 
|  0.45 |   0.20 |  92.3 | +0.376 |  4.67 |  2.666 |   +9.784 | 
|  0.50 |   0.20 |  88.5 | +0.376 |  3.45 |  2.666 |   +9.781 | 
|  0.40 |   0.25 |  92.3 | +0.376 |  4.67 |  2.666 |   +9.774 | 
|  0.45 |   0.05 |  92.3 | +0.375 |  4.66 |  2.666 |   +9.754 | 
|  0.50 |   0.15 |  88.5 | +0.367 |  3.38 |  2.666 |   +9.531 | 
|  0.35 |   0.30 |  92.3 | +0.364 |  4.55 |  2.666 |   +9.454 | 
|  0.40 |   0.15 |  92.3 | +0.359 |  4.50 |  2.666 |   +9.334 | 
|  0.50 |   0.10 |  88.5 | +0.357 |  3.32 |  2.666 |   +9.281 | 
|  0.40 |   0.20 |  92.3 | +0.357 |  4.48 |  2.666 |   +9.274 | 
|  0.50 |   0.05 |  88.5 | +0.347 |  3.26 |  2.666 |   +9.031 | 
|  0.40 |   0.10 |  92.3 | +0.342 |  4.33 |  2.666 |   +8.884 | 
|  0.30 |   0.25 |  92.3 | +0.341 |  4.32 |  2.666 |   +8.854 | 
|  0.35 |   0.25 |  92.3 | +0.341 |  4.32 |  2.666 |   +8.854 | 
|  0.40 |   0.05 |  92.3 | +0.324 |  4.16 |  2.666 |   +8.434 | 
|  0.30 |   0.20 |  92.3 | +0.317 |  4.10 |  2.666 |   +8.254 | 
|  0.35 |   0.20 |  92.3 | +0.317 |  4.10 |  2.666 |   +8.254 | 
|  0.30 |   0.15 |  92.3 | +0.316 |  4.08 |  2.666 |   +8.214 | **CHOSEN**
|  0.35 |   0.15 |  92.3 | +0.316 |  4.08 |  2.666 |   +8.214 | 
|  0.25 |   0.20 |  92.3 | +0.298 |  3.90 |  2.666 |   +7.744 | 
|  0.30 |   0.10 |  92.3 | +0.295 |  3.87 |  2.666 |   +7.664 | 
|  0.35 |   0.10 |  92.3 | +0.295 |  3.87 |  2.666 |   +7.664 | 
|  0.25 |   0.15 |  92.3 | +0.294 |  3.87 |  2.666 |   +7.654 | 
|  0.20 |   0.15 |  96.2 | +0.287 |  6.59 |  1.333 |   +7.457 | 
|  0.30 |   0.05 |  92.3 | +0.274 |  3.67 |  2.666 |   +7.114 | 
|  0.35 |   0.05 |  92.3 | +0.274 |  3.67 |  2.666 |   +7.114 | 
|  0.25 |   0.10 |  92.3 | +0.271 |  3.65 |  2.666 |   +7.054 | 
|  0.15 |   0.10 | 100.0 | +0.264 |   inf |  0.000 |   +6.870 | 
|  0.20 |   0.10 |  96.2 | +0.256 |  5.99 |  1.333 |   +6.657 | 
|  0.15 |   0.05 | 100.0 | +0.253 |   inf |  0.000 |   +6.580 | 
|  0.20 |   0.05 |  96.2 | +0.251 |  5.89 |  1.333 |   +6.517 | 
|  0.25 |   0.05 |  92.3 | +0.248 |  3.42 |  2.666 |   +6.454 | 
|   N/A |    N/A |  73.1 | +0.199 |  1.62 |  3.202 |   +5.175 | MODEL A (baseline)

--- Section 2: EV% Heatmap (rows=activate%, cols=close%) ---

             close=0.05  close=0.10  close=0.15  close=0.20  close=0.25  close=0.30
           ------------------------------------------------------------------------
  act=0.15:   +0.253    +0.264       N/A       N/A       N/A       N/A  
  act=0.20:   +0.251    +0.256    +0.287       N/A       N/A       N/A  
  act=0.25:   +0.248    +0.271    +0.294    +0.298       N/A       N/A  
  act=0.30:   +0.274    +0.295    +0.316*   +0.317    +0.341       N/A  
  act=0.35:   +0.274    +0.295    +0.316    +0.317    +0.341    +0.364  
  act=0.40:   +0.324    +0.342    +0.359    +0.357    +0.376    +0.395  
  act=0.45:   +0.375    +0.389    +0.402    +0.376    +0.394    +0.411  
  act=0.50:   +0.347    +0.357    +0.367    +0.376    +0.386    +0.395  

  (*) = originally chosen parameters (act=0.30, close=0.15)
  Model A EV = +0.199% (reference)

--- Section 3: Robustness Analysis ---

  Total valid parameter combinations tested: 38
  Model A EV (baseline): +0.199%

  Combinations with EV > Model A (+0.199%): 38/38 (100%)
  Combinations with EV > 0%:                             38/38 (100%)

  EV range across all combinations:
    Min: +0.248%
    Max: +0.411%
    Avg: +0.332%
    Std: 0.049%

  Ridge analysis (top 5 combinations by EV):
   act%  close%      EV%
   0.45    0.30   +0.411%
   0.45    0.15   +0.402%
   0.50    0.30   +0.395%
   0.40    0.30   +0.395%
   0.45    0.25   +0.394%

  Top-5 activate% span: 0.40 to 0.50 (range=0.10%)
  Top-5 close%    span: 0.15 to 0.30 (range=0.15%)
  Verdict: MIXED — moderate clustering; interpret with caution.

--- Section 4: Walk-Forward Split ---

  Train set: trades 1-16 (Mar 10-17, 16 trades, mostly LONG)
  Test  set: trades 17-26 (Mar 17-29, 10 trades, mixed LONG+SHORT)

  Best combo on TRAIN set: activate=0.45%, close=0.15%
    Train EV:  +0.315%  WR=87.5%  CumPnL=+5.034%
    Test  EV:  +0.542%  WR=100.0%  CumPnL=+5.420%

  Chosen params (act=0.30, close=0.15) walk-forward:
    Train EV:  +0.210%  WR=87.5%  CumPnL=+3.354%
    Test  EV:  +0.486%  WR=100.0%  CumPnL=+4.860%

  Model A walk-forward:
    Train EV:  -0.056%  WR=62.5%  CumPnL=-0.898%
    Test  EV:  +0.607%  WR=90.0%  CumPnL=+6.073%

  Walk-forward degradation (chosen): train +0.210% -> test +0.486%  (delta=-0.276%)
    POSITIVE: Out-of-sample EV is HIGHER than train — no degradation observed.
    NOTE: This may reflect regime differences between periods, not parameter robustness.

================================================================================
Section 5: HONEST CONCLUSION
================================================================================

1. IS V3 ROBUST ACROSS PARAMETERS?
   - Valid combinations tested: 38
   - EV range: +0.248% to +0.411% (avg=+0.332%)
   - Combinations beating Model A: 38/38 (100%)
   - Combinations with EV > 0%:    38/38 (100%)
   - Chosen params rank: #24 of 38

   Parameter ridge: MIXED — moderate clustering; interpret with caution.

2. WALK-FORWARD PERFORMANCE (chosen 0.30/0.15):
   Train (trades 1-16): EV=+0.210%
   Test  (trades 17-26): EV=+0.486%

3. IS THE CONCEPT VALID FOR DEPLOYMENT?
   [PASS] Most parameter combinations (38/38) have EV > 0%
   [PASS] Most combinations (38/38) beat Model A baseline
   [FAIL] Chosen params underperform Model A on out-of-sample test set
   [FAIL] Sample size (26 trades) is far below the 200+ needed for statistical significance

4. CONFIDENCE LEVEL: LOW-MEDIUM
   (2/4 validation criteria passed)

5. DEPLOYMENT RECOMMENDATION:
   Concept shows some promise but evidence is weak. Shadow trade only.

6. KEY CAVEAT:
   With only 26 trades, the probability of cherry-picking optimal parameters
   by chance is high. A parameter sensitivity test on 26 trades can confirm
   that a CONCEPT works across a range of inputs, but cannot confirm that
   the EXACT parameters chosen are optimal rather than lucky.
   Minimum sample for reliable strategy comparison: 200-300 trades.

```
