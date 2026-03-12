"""
╔══════════════════════════════════════════════════════════════════════╗
║  BTC-QUANT-BTC: SPECTRUM DIRECTIONAL ACCURACY & CALIBRATION EVALUATOR ║
║                                                                      ║
║  Objective:                                                          ║
║    Measure the predictive power (Hit Rate) of the combined Spectrum  ║
║    Directional Bias against actual future price movements.           ║
║                                                                      ║
║  Key Question:                                                       ║
║    When Bias = +0.7, how often does Price actually go UP?            ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import sys
import warnings
from pathlib import Path
from collections import defaultdict
from datetime import datetime

import numpy as np
import pandas as pd
import pandas_ta as ta

warnings.filterwarnings("ignore")

_BACKTEST_DIR = Path(__file__).resolve().parent
_BACKEND_DIR  = _BACKTEST_DIR.parent / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from engines.layer1_hmm import MarketRegimeModel
from engines.layer2_ichimoku import IchimokuCloudModel
from utils.spectrum import DirectionalSpectrum

# ════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ════════════════════════════════════════════════════════════════════

LOG_DIR              = _BACKTEST_DIR / "logs"
WARMUP               = 250    # candles for HMM/indicators
MOVE_THRESHOLD       = 0.005  # 0.5% return for "significant" move

# Horizons to evaluate (in 4H candles)
HORIZONS = {
    "4H (1c) ": 1,
    "12H (3c)": 3,
    "24H (6c)": 6,
}

# ════════════════════════════════════════════════════════════════════
#  CORE EVALUATOR
# ════════════════════════════════════════════════════════════════════

def run_accuracy_test(year: int):
    path = _BACKTEST_DIR / "data" / f"BTC_USDT_4h_{year}.csv"
    if not path.exists():
        print(f"  ❌ Data for {year} not found.")
        return

    df = pd.read_csv(path, index_col=0, parse_dates=True)
    df.rename(columns={"open":"Open","high":"High","low":"Low","close":"Close","volume":"Volume"}, inplace=True)
    
    hmm = MarketRegimeModel()
    ichi = IchimokuCloudModel()
    spec_calc = DirectionalSpectrum()
    
    records = []
    total_len = len(df)
    max_h = max(HORIZONS.values())

    print(f"  🚀 Starting Accuracy Test for {year} ({total_len} candles)...")
    
    # ──── Walk-Forward Loop ────
    for i in range(WARMUP, total_len - max_h):
        if i % 200 == 0:
            print(f"    Progress: {i}/{total_len} candles...", end="\r")
            
        df_window = df.iloc[i-WARMUP : i+1].copy()
        
        # 1. Get layer votes
        l1_vote = hmm.get_directional_vote(df_window)
        l2_vote = ichi.get_directional_vote(df_window)
        
        # L3 Proxy (MACD Tanh)
        df_window["ATR"] = ta.atr(df_window["High"], df_window["Low"], df_window["Close"], length=14)
        macd = ta.macd(df_window["Close"])
        l3_vote = 0.0
        if macd is not None and "MACDh_12_26_9" in macd.columns:
            ah = float(macd["MACDh_12_26_9"].iloc[-1])
            atr = float(df_window["ATR"].iloc[-1])
            l3_vote = float(np.tanh(ah / (atr + 1e-9)))
            
        # 2. Spectrum Aggregation
        spec = spec_calc.calculate(l1_vote, l2_vote, l3_vote, l4_multiplier=1.0)
        bias = spec.directional_bias
        gate = spec.trade_gate
        
        # 3. Ground Truth (Future Returns)
        price_now = float(df["Close"].iloc[i])
        fwd_rets = {}
        for hname, h in HORIZONS.items():
            price_fwd = float(df["Close"].iloc[i+h])
            fwd_rets[hname] = (price_fwd - price_now) / price_now
            
        records.append({
            "ts": df.index[i],
            "bias": bias,
            "gate": gate,
            "rets": fwd_rets
        })

    print(f"\n  ✅ Collected {len(records)} predictions.")
    return records

# ════════════════════════════════════════════════════════════════════
#  ANALYSIS
# ════════════════════════════════════════════════════════════════════

def analyze_accuracy(records: list[dict]):
    """
    Groups results into ACTIVE BULL, ADVISORY BULL, NEUTRAL, etc.
    Calculates hit rate per group.
    """
    def get_bucket(r):
        b = r["bias"]
        g = r["gate"]
        if g == "ACTIVE" and b > 0: return "ACTIVE BULL (>0.65)"
        if g == "ACTIVE" and b < 0: return "ACTIVE BEAR (<-0.65)"
        if b >= 0.10: return "ADVISORY BULL (0.1..0.65)"
        if b <= -0.10: return "ADVISORY BEAR (-0.1..-0.65)"
        return "NEUTRAL (-0.1..0.1)"

    by_bucket = defaultdict(list)
    for r in records:
        bucket = get_bucket(r)
        by_bucket[bucket].append(r)
        
    results = {}
    for bucket, recs in by_bucket.items():
        n = len(recs)
        stats = {"count": n, "horizons": {}}
        
        is_bull = "BULL" in bucket
        is_bear = "BEAR" in bucket
        
        for hname in HORIZONS.keys():
            rets = np.array([r["rets"][hname] for r in recs])
            
            if is_bull:
                hit_rate = (rets > 0).mean()
            elif is_bear:
                hit_rate = (rets < 0).mean()
            else:
                # Neutral accuracy = how often it stays within MOVE_THRESHOLD
                hit_rate = (np.abs(rets) < MOVE_THRESHOLD).mean()
                
            stats["horizons"][hname] = {
                "hit_rate": float(hit_rate),
                "avg_ret": float(rets.mean() * 100)
            }
        results[bucket] = stats
        
    return results

# ════════════════════════════════════════════════════════════════════
#  MAIN & REPORTING
# ════════════════════════════════════════════════════════════════════

def print_report(year: int, results: dict):
    sep = "═" * 75
    line = "─" * 75
    
    print(f"\n{sep}")
    print(f"  SPECTRUM CALIBRATION REPORT — {year}")
    print(f"{sep}")
    
    headers = f"{'Conviction Bucket':<28} {'Count':>6}  " + "  ".join(f"{h:>12}" for h in HORIZONS.keys())
    print(headers)
    print(line)
    
    # Sort buckets logically
    order = ["ACTIVE BULL (>0.65)", "ADVISORY BULL (0.1..0.65)", "NEUTRAL (-0.1..0.1)", "ADVISORY BEAR (-0.1..-0.65)", "ACTIVE BEAR (<-0.65)"]
    
    for bucket in order:
        if bucket not in results: continue
        res = results[bucket]
        row = f"{bucket:<28} {res['count']:>6}  "
        
        for hname in HORIZONS.keys():
            hr = res["horizons"][hname]["hit_rate"] * 100
            mr = res["horizons"][hname]["avg_ret"]
            icon = "✅" if hr >= 55 else ("❌" if hr < 45 else "🟡")
            row += f"{hr:>5.1f}% {icon} ({mr:>+4.1f}%) "
            
        print(row)
    
    print(f"{line}")
    print("  Note: Hit Rate for Neutral = % of time price stayed within +/- 0.5%")
    print(f"{sep}\n")

if __name__ == "__main__":
    records_2025 = run_accuracy_test(2025)
    if records_2025:
        stats = analyze_accuracy(records_2025)
        print_report(2025, stats)
