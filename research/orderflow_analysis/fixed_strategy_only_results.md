# BTC-QUANT FixedStrategy Only Simulation Results

Generated: 2026-03-31  |  22 trades (HestonStrategy excluded)

```
==========================================================================================
BTC-QUANT v4.4 — FixedStrategy Only Simulation (22 trades)
HestonStrategy trades excluded (old #22-25, Mar 26-28)
Date: 2026-03-31  |  Candles: 15m Binance BTCUSDT  |  Trades: 22
==========================================================================================

[1/4] Loading 15m kline data (cached where available)...
  Active trades: 22/22

[2/4] Running simulations (Model A, Model B, Model V3)...

[3/4] Per-trade table (Model A vs V3):
-------------------------------------------------------------------------------------------------------------------
 ID | Date             | S     |   Entry |   Peak% | A_Exit   |  A_PnL% | V3_Exit  |  V3_PnL% | B_Exit       |  B_PnL%
-------------------------------------------------------------------------------------------------------------------
  1 | 2026-03-10 16:05 | LONG  |   71198 |   +0.71% | SL       |  -1.333% | PP       |   +0.150% | MANUAL_LOSS  |   -1.20%
  2 | 2026-03-11 04:08 | LONG  |   69498 |   +0.77% | TP       |  +0.710% | TP       |   +0.710% | TP           |   +0.73%
  3 | 2026-03-11 08:06 | LONG  |   69620 |   +1.09% | TP       |  +0.710% | TP       |   +0.710% | MANUAL       |   +0.24%
  4 | 2026-03-12 08:05 | LONG  |   69846 |   +0.79% | TP       |  +0.710% | PP       |   +0.150% | TP           |   +0.67%
  5 | 2026-03-12 12:15 | LONG  |   70309 |   +0.50% | SL       |  -1.333% | PP       |   +0.150% | MANUAL_LOSS  |   -0.68%
  6 | 2026-03-12 20:09 | LONG  |   70401 |   +1.02% | TP       |  +0.710% | TP       |   +0.710% | TP           |   +0.77%
  7 | 2026-03-13 04:03 | LONG  |   71347 |   +1.12% | TP       |  +0.710% | PP       |   +0.150% | MANUAL       |   +0.22%
  8 | 2026-03-13 08:02 | LONG  |   71520 |   +0.87% | TP       |  +0.710% | TP       |   +0.710% | TP           |   +0.77%
  9 | 2026-03-13 14:13 | LONG  |   73500 |   +0.56% | SL       |  -1.333% | PP       |   +0.150% | MANUAL       |   +0.34%
 10 | 2026-03-13 16:02 | LONG  |   71891 |   +0.50% | SL       |  -1.333% | PP       |   +0.150% | MANUAL_LOSS  |   -0.67%
 11 | 2026-03-16 08:14 | LONG  |   73545 |   +1.31% | TP       |  +0.710% | PP       |   +0.150% | MANUAL       |   +0.42%
 12 | 2026-03-16 16:01 | LONG  |   73172 |   +1.00% | TP       |  +0.710% | TP       |   +0.710% | MANUAL       |   +0.42%
 13 | 2026-03-17 00:51 | LONG  |   74930 |   +1.40% | TP       |  +0.710% | TP       |   +0.710% | TP           |   +0.66%
 14 | 2026-03-17 02:07 | LONG  |   75287 |   +0.24% | SL       |  -1.333% | SL       |   -1.333% | MANUAL       |   +0.08%
 15 | 2026-03-17 04:02 | LONG  |   74562 |   +0.16% | SL       |  -1.333% | SL       |   -1.333% | MANUAL_LOSS  |   -0.68%
 16 | 2026-03-17 07:21 | LONG  |   74319 |   +0.77% | TP       |  +0.710% | TP       |   +0.710% | MANUAL       |   +0.03%
 17 | 2026-03-17 12:00 | LONG  |   74013 |   +1.19% | TP       |  +0.710% | TP       |   +0.710% | MANUAL       |   +0.28%
 18 | 2026-03-22 00:00 | SHORT |   68744 |   +0.75% | TP       |  +0.710% | TP       |   +0.710% | TP           |   +0.75%
 19 | 2026-03-22 08:00 | SHORT |   68860 |   +0.83% | TP       |  +0.710% | PP       |   +0.150% | MANUAL       |   +0.34%
 20 | 2026-03-22 12:00 | SHORT |   68217 |   +0.97% | TP       |  +0.710% | TP       |   +0.710% | SL           |   -0.71%
 21 | 2026-03-23 00:00 | SHORT |   67975 |   +0.78% | TP       |  +0.710% | TP       |   +0.710% | MANUAL       |   +0.35%
 22 | 2026-03-29 23:00 | SHORT |   66480 |   +0.93% | TP       |  +0.710% | TP       |   +0.710% | TP           |   +0.88%
-------------------------------------------------------------------------------------------------------------------

[4/4] Master summary — all models, LONG/SHORT breakdown:
----------------------------------------------------------------------------------------------------------------------
| Model              | Trades | Wins | Losses |    WR% |  AvgWin% |  AvgLoss% |    EV% |     PF |  MaxDD% |  CumPnL% |
----------------------------------------------------------------------------------------------------------------------
| Model_A (ALL)      |     22 |   16 |      6 |  72.7% |    0.710% |    -1.333% |  0.153% |   1.42 |   3.202% |    3.362% |
| Model_A (LONG)     |     17 |   11 |      6 |  64.7% |    0.710% |    -1.333% | -0.011% |   0.98 |   3.202% |   -0.188% |
| Model_A (SHORT)    |      5 |    5 |      0 | 100.0% |    0.710% |     0.000% |  0.710% |    inf |   0.000% |    3.550% |
| Model_B (ALL)      |     22 |   17 |      5 |  77.3% |    0.468% |    -0.788% |  0.182% |   2.02 |   1.200% |    4.010% |
| Model_B (LONG)     |     17 |   13 |      4 |  76.5% |    0.433% |    -0.807% |  0.141% |   1.74 |   1.200% |    2.400% |
| Model_B (SHORT)    |      5 |    4 |      1 |  80.0% |    0.580% |    -0.710% |  0.322% |   3.27 |   0.710% |    1.610% |
| Model_V3 (ALL)     |     22 |   20 |      2 |  90.9% |    0.486% |    -1.333% |  0.321% |   3.65 |   2.666% |    7.054% |
| Model_V3 (LONG)    |     17 |   15 |      2 |  88.2% |    0.449% |    -1.333% |  0.239% |   2.52 |   2.666% |    4.064% |
| Model_V3 (SHORT)   |      5 |    5 |      0 | 100.0% |    0.598% |     0.000% |  0.598% |    inf |   0.000% |    2.990% |
----------------------------------------------------------------------------------------------------------------------

Monte Carlo (1000 paths x 100 trades, bootstrap with replacement):
-----------------------------------------------------------------
  Model        |      P5% |  Median% |     P95% |  P(profit)
-----------------------------------------------------------------
  Model_A      |    -0.50% |   +15.84% |   +30.14% |      94.3%
  Model_V3     |   +22.60% |   +32.09% |   +41.38% |     100.0%
  Model_B      |    +8.93% |   +18.39% |   +28.27% |      99.9%
-----------------------------------------------------------------

V3 diagnostics: PP activated in 13 trades, exited early in 8 trades
  Trades exited by V3 PP (peak>=0.30%, close<=0.15%):
    Trade  1 | LONG | entry=71198 | peak=+0.71% -> exit PP +0.150% | actual=-1.20% (MANUAL_LOSS)
    Trade  4 | LONG | entry=69846 | peak=+0.39% -> exit PP +0.150% | actual=+0.67% (TP)
    Trade  5 | LONG | entry=70309 | peak=+0.44% -> exit PP +0.150% | actual=-0.68% (MANUAL_LOSS)
    Trade  7 | LONG | entry=71347 | peak=+0.41% -> exit PP +0.150% | actual=+0.22% (MANUAL)
    Trade  9 | LONG | entry=73500 | peak=+0.56% -> exit PP +0.150% | actual=+0.34% (MANUAL)
    Trade 10 | LONG | entry=71891 | peak=+0.50% -> exit PP +0.150% | actual=-0.67% (MANUAL_LOSS)
    Trade 11 | LONG | entry=73545 | peak=+0.40% -> exit PP +0.150% | actual=+0.42% (MANUAL)
    Trade 19 | SHORT | entry=68860 | peak=+0.49% -> exit PP +0.150% | actual=+0.34% (MANUAL)

==========================================================================================
HONEST CONCLUSION
==========================================================================================

1. WINNER BY EV (expected value per trade):
   Model_V3 (+0.321%) > Model_B (+0.182%) > Model_A (+0.153%)

2. LONG vs SHORT performance (Model A):
   LONG  (17 trades):  WR=64.7%,  EV=-0.011%,  CumPnL=-0.19%
   SHORT (5 trades): WR=100.0%, EV=+0.710%, CumPnL=+3.55%

3. EV RELIABILITY:
   Breakeven WR = 1/(1 + TP/|SL|) = 1/(1 + 0.71/1.333) = 65.2%
   Model A WR=72.7% — ABOVE breakeven, positive EV confirmed
   WARNING: 22 trades is well below the 200+ minimum for statistical significance.
   All rankings are directional estimates only — high variance, wide confidence intervals.

4. V3 vs A comparison:
   V3 EV=+0.321% vs A EV=+0.153%
   V3 WINS — profit protection adds value on this sample
   V3 cut 8 trades early at +0.15% (instead of waiting for TP +0.71%).

5. RECOMMENDATION:
   a) Deploy Model A (Pure Auto) as primary — fully systematic, reproducible, no bias.
   b) V3 may add value but needs 100+ more trades before a live switch is justified.
   c) SHORT side is a new regime (Mar 22+) — watch SL rate closely in live trading.
   d) The most dangerous scenario: consecutive SL hits. Monitor SL rate vs base rate.

```
