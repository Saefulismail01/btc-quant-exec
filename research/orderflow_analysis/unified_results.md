# BTC-QUANT Unified Simulation Results

Generated: 2026-03-31

```
================================================================================
BTC-QUANT v4.4 — Unified Strategy Simulation
Date: 2026-03-31  |  Candles: 15m Binance BTCUSDT  |  Trades: 26
================================================================================

[1/5] Fetching 15m kline data from Binance (cached if available)...
  Active trades: 26/26

[2/5] Running simulations...

[3/5] Per-trade detail (Model A vs V3):
--------------------------------------------------------------------------------------------------------------
 ID | Date             | Side  |   Entry |  Peak% | A_Exit   |  A_PnL% | V3_Exit   |  V3_PnL% | B_Exit       |  B_PnL%
--------------------------------------------------------------------------------------------------------------
  1 | 2026-03-10 16:05 | LONG  |   71198 |  +0.71% | SL       |  -1.333% | PP        |   +0.150% | MANUAL_LOSS  |   -1.20%
  2 | 2026-03-11 04:08 | LONG  |   69498 |  +0.77% | TP       |  +0.710% | TP        |   +0.710% | TP           |   +0.73%
  3 | 2026-03-11 08:06 | LONG  |   69620 |  +1.09% | TP       |  +0.710% | TP        |   +0.710% | MANUAL       |   +0.24%
  4 | 2026-03-12 08:05 | LONG  |   69846 |  +0.79% | TP       |  +0.710% | PP        |   +0.150% | TP           |   +0.67%
  5 | 2026-03-12 12:15 | LONG  |   70309 |  +0.50% | SL       |  -1.333% | PP        |   +0.150% | MANUAL_LOSS  |   -0.68%
  6 | 2026-03-12 20:09 | LONG  |   70401 |  +1.02% | TP       |  +0.710% | TP        |   +0.710% | TP           |   +0.77%
  7 | 2026-03-13 04:03 | LONG  |   71347 |  +1.12% | TP       |  +0.710% | PP        |   +0.150% | MANUAL       |   +0.22%
  8 | 2026-03-13 08:02 | LONG  |   71520 |  +0.87% | TP       |  +0.710% | TP        |   +0.710% | TP           |   +0.77%
  9 | 2026-03-13 14:13 | LONG  |   73500 |  +0.56% | SL       |  -1.333% | PP        |   +0.150% | MANUAL       |   +0.34%
 10 | 2026-03-13 16:02 | LONG  |   71891 |  +0.50% | SL       |  -1.333% | PP        |   +0.150% | MANUAL_LOSS  |   -0.67%
 11 | 2026-03-16 08:14 | LONG  |   73545 |  +1.31% | TP       |  +0.710% | PP        |   +0.150% | MANUAL       |   +0.42%
 12 | 2026-03-16 16:01 | LONG  |   73172 |  +1.00% | TP       |  +0.710% | TP        |   +0.710% | MANUAL       |   +0.42%
 13 | 2026-03-17 00:51 | LONG  |   74930 |  +1.40% | TP       |  +0.710% | TP        |   +0.710% | TP           |   +0.66%
 14 | 2026-03-17 02:07 | LONG  |   75287 |  +0.24% | SL       |  -1.333% | SL        |   -1.333% | MANUAL       |   +0.08%
 15 | 2026-03-17 04:02 | LONG  |   74562 |  +0.16% | SL       |  -1.333% | SL        |   -1.333% | MANUAL_LOSS  |   -0.68%
 16 | 2026-03-17 07:21 | LONG  |   74319 |  +0.77% | TP       |  +0.710% | TP        |   +0.710% | MANUAL       |   +0.03%
 17 | 2026-03-17 12:00 | LONG  |   74013 |  +1.19% | TP       |  +0.710% | TP        |   +0.710% | MANUAL       |   +0.28%
 18 | 2026-03-22 00:00 | SHORT |   68744 |  +0.75% | TP       |  +0.710% | TP        |   +0.710% | TP           |   +0.75%
 19 | 2026-03-22 08:00 | SHORT |   68860 |  +0.83% | TP       |  +0.710% | PP        |   +0.150% | MANUAL       |   +0.34%
 20 | 2026-03-22 12:00 | SHORT |   68217 |  +0.97% | TP       |  +0.710% | TP        |   +0.710% | SL           |   -0.71%
 21 | 2026-03-23 00:00 | SHORT |   67975 |  +0.78% | TP       |  +0.710% | TP        |   +0.710% | MANUAL       |   +0.35%
 22 | 2026-03-26 12:00 | SHORT |   69215 |  +0.84% | TP       |  +0.710% | TP        |   +0.710% | MANUAL_LOSS  |   -0.13%
 23 | 2026-03-26 13:44 | SHORT |   69385 |  +1.08% | TP       |  +0.710% | TP        |   +0.710% | TP           |   +0.70%
 24 | 2026-03-27 04:00 | SHORT |   68702 |  +1.59% | TP       |  +0.710% | PP        |   +0.150% | MANUAL       |   +0.35%
 25 | 2026-03-28 08:00 | SHORT |   66460 |  +0.50% | TIME     |  -0.317% | PP        |   +0.150% | MANUAL       |   +0.08%
 26 | 2026-03-28 16:00 | SHORT |   66998 |  +1.06% | TP       |  +0.710% | PP        |   +0.150% | MANUAL       |   +0.35%
--------------------------------------------------------------------------------------------------------------

[4/5] Master summary table (all models, LONG+SHORT combined):
------------------------------------------------------------------------------------------------------------------------
| Model            | Trades | Wins | Losses |    WR% |  AvgWin% |  AvgLoss% |    EV% |     PF |  MaxDD% |  CumPnL% |
------------------------------------------------------------------------------------------------------------------------
| Model_A (ALL)    |     26 |   19 |      7 |  73.1% |    0.710% |    -1.188% |  0.199% |   1.62 |   3.202% |    5.175% |
| Model_A (LONG)   |     17 |   11 |      6 |  64.7% |    0.710% |    -1.333% | -0.011% |   0.98 |   3.202% |   -0.188% |
| Model_A (SHORT)  |      9 |    8 |      1 |  88.9% |    0.710% |    -0.317% |  0.596% |  17.89 |   0.317% |    5.363% |
| Model_B (ALL)    |     26 |   20 |      6 |  76.9% |    0.428% |    -0.678% |  0.172% |   2.10 |   1.200% |    4.480% |
| Model_B (LONG)   |     17 |   13 |      4 |  76.5% |    0.433% |    -0.807% |  0.141% |   1.74 |   1.200% |    2.400% |
| Model_B (SHORT)  |      9 |    7 |      2 |  77.8% |    0.417% |    -0.420% |  0.231% |   3.48 |   0.710% |    2.080% |
| Model_V3 (ALL)   |     26 |   24 |      2 |  92.3% |    0.453% |    -1.333% |  0.316% |   4.08 |   2.666% |    8.214% |
| Model_V3 (LONG)  |     17 |   15 |      2 |  88.2% |    0.449% |    -1.333% |  0.239% |   2.52 |   2.666% |    4.064% |
| Model_V3 (SHORT) |      9 |    9 |      0 | 100.0% |    0.461% |     0.000% |  0.461% |    inf |   0.000% |    4.150% |
| Model_V3+OF (ALL) |     26 |   23 |      3 |  88.5% |    0.467% |    -1.333% |  0.259% |   2.68 |   2.666% |    6.731% |
| Model_V3+OF (LONG) |     17 |   14 |      3 |  82.4% |    0.470% |    -1.333% |  0.152% |   1.65 |   2.666% |    2.581% |
| Model_V3+OF (SHORT) |      9 |    9 |      0 | 100.0% |    0.461% |     0.000% |  0.461% |    inf |   0.000% |    4.150% |
------------------------------------------------------------------------------------------------------------------------

[5/5] V3 and V3+OF diagnostics:
  V3:     PP activated in 18 trades, exited at PP in 11 trades
  V3+OF:  PP activated in 18 trades, exited at PP+OF in 10 trades
  V3+OF:  OF blocked exit in 7 trade-candle instances

  Trades exited by PP (V3):
    Trade  1 | LONG | entry=71198 | peak=+0.71% | exit=+0.150% | actual=-1.20% (actual_exit=MANUAL_LOSS)
    Trade  4 | LONG | entry=69846 | peak=+0.39% | exit=+0.150% | actual=+0.67% (actual_exit=TP)
    Trade  5 | LONG | entry=70309 | peak=+0.44% | exit=+0.150% | actual=-0.68% (actual_exit=MANUAL_LOSS)
    Trade  7 | LONG | entry=71347 | peak=+0.41% | exit=+0.150% | actual=+0.22% (actual_exit=MANUAL)
    Trade  9 | LONG | entry=73500 | peak=+0.56% | exit=+0.150% | actual=+0.34% (actual_exit=MANUAL)
    Trade 10 | LONG | entry=71891 | peak=+0.50% | exit=+0.150% | actual=-0.67% (actual_exit=MANUAL_LOSS)
    Trade 11 | LONG | entry=73545 | peak=+0.40% | exit=+0.150% | actual=+0.42% (actual_exit=MANUAL)
    Trade 19 | SHORT | entry=68860 | peak=+0.49% | exit=+0.150% | actual=+0.34% (actual_exit=MANUAL)
    Trade 24 | SHORT | entry=68702 | peak=+0.58% | exit=+0.150% | actual=+0.35% (actual_exit=MANUAL)
    Trade 25 | SHORT | entry=66460 | peak=+0.50% | exit=+0.150% | actual=+0.08% (actual_exit=MANUAL)
    Trade 26 | SHORT | entry=66998 | peak=+0.44% | exit=+0.150% | actual=+0.35% (actual_exit=MANUAL)

  Trades exited by PP+OF (V3+OF):
    Trade  1 | LONG | entry=71198 | peak=+0.71% | exit=+0.150% | actual=-1.20% (actual_exit=MANUAL_LOSS)
    Trade  4 | LONG | entry=69846 | peak=+0.39% | exit=+0.150% | actual=+0.67% (actual_exit=TP)
    Trade  5 | LONG | entry=70309 | peak=+0.44% | exit=+0.150% | actual=-0.68% (actual_exit=MANUAL_LOSS)
    Trade  7 | LONG | entry=71347 | peak=+0.41% | exit=+0.150% | actual=+0.22% (actual_exit=MANUAL)
    Trade 10 | LONG | entry=71891 | peak=+0.50% | exit=+0.150% | actual=-0.67% (actual_exit=MANUAL_LOSS)
    Trade 11 | LONG | entry=73545 | peak=+0.40% | exit=+0.150% | actual=+0.42% (actual_exit=MANUAL)
    Trade 19 | SHORT | entry=68860 | peak=+0.49% | exit=+0.150% | actual=+0.34% (actual_exit=MANUAL)
    Trade 24 | SHORT | entry=68702 | peak=+0.58% | exit=+0.150% | actual=+0.35% (actual_exit=MANUAL)
    Trade 25 | SHORT | entry=66460 | peak=+0.50% | exit=+0.150% | actual=+0.08% (actual_exit=MANUAL)
    Trade 26 | SHORT | entry=66998 | peak=+0.44% | exit=+0.150% | actual=+0.35% (actual_exit=MANUAL)

[BONUS] Monte Carlo simulation (1000 paths x 100 trades, bootstrap):
  Using 1000 paths, 100 trades per path
----------------------------------------------------------------------
  Model        |      P5% |  Median% |     P95% |  P(profit)
----------------------------------------------------------------------
  Model_A      |    +5.60% |   +19.93% |   +34.21% |      98.6%
  Model_V3     |   +22.04% |   +31.89% |   +40.99% |     100.0%
  Model_V3+OF  |   +14.99% |   +26.32% |   +36.34% |      99.9%
  Model_B      |    +8.19% |   +17.28% |   +26.00% |      99.8%
----------------------------------------------------------------------

================================================================================
HONEST CONCLUSION
================================================================================

1. BEST MODEL BY EV (expected value per trade):
   Ranked: Model_V3 (+0.316%) > Model_V3+OF (+0.259%) > Model_A (+0.199%) > Model_B (+0.172%)

2. SAMPLE SIZE WARNING:
   Only 26 trades available. This is far below the ~200-300 minimum
   needed for statistically significant strategy comparison. All numbers have
   high uncertainty. Confidence intervals are wide — treat rankings as directional,
   not definitive.

3. MODEL CHARACTERISTICS:
   Model A (Pure Auto):
     - Systematic, removes all discretion
     - WR: 73.1%, EV: +0.199%, CumPnL: +5.17%
     - Risk: SL is 1.333% — relatively wide for scalping; a few SL hits dominate losses

   Model B (Actual Manual):
     - Represents real historical execution INCLUDING human discretion
     - WR: 76.9%, EV: +0.172%, CumPnL: +4.48%
     - WARNING: Past manual skill may not persist; highly subject to psychological bias
     - Several 'MANUAL' exits were suboptimal vs TP; others correctly avoided SL

   Model V3 (Profit Protection):
     - Locks in gains when peak >= 0.30%, exits if close retraces to 0.15%
     - WR: 92.3%, EV: +0.316%, CumPnL: +8.21%
     - Theoretically appealing but may cut winners too early in trending markets

   Model V3+OF (Profit Protection + Orderflow):
     - Adds OF4/OF5 confirmation before PP exit — reduces premature exits
     - WR: 88.5%, EV: +0.259%, CumPnL: +6.73%

4. DEPLOYMENT RECOMMENDATION:
   Given the small sample and uncertainty:
   a) Deploy Model A (Pure Auto) as primary — fully systematic, no human bias,
      results reproducible. EV is transparent.
   b) Monitor V3 in shadow mode for 50+ more trades before live switch.
   c) Do NOT deploy based on 26-trade optimization — overfitting risk is high.
   d) The most important metric to watch live: whether SL rate stays near
      historical base rate. Multiple consecutive SLs = regime change signal.

5. KEY RISK:
   The SL at -1.333% is significantly larger than TP at +0.71%. A win-rate below
   ~65.5% produces negative EV (TP/|SL| = 0.71/1.333 = 0.533; breakeven WR =
   1/(1+0.533) = 65.2%). Current WR must be verified on larger sample.

```
