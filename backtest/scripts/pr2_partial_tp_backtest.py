"""
PR-2: Partial TP Backtest
Membandingkan Fixed TP (0.71%) vs Partial TP (50% @ 0.71%, 50% trailing)

Baseline: V1 (BCD+EMA) parameters
Period: 2024-01-01 to 2026-03-25
"""

import os
import sys
import json
import duckdb
import numpy as np
import pandas as pd
import pandas_ta as ta
from pathlib import Path
from datetime import datetime

sys.path.insert(0, '/app/backend')
os.environ["BTC_QUANT_LAYER1_ENGINE"] = "bcd"
from utils.spectrum import DirectionalSpectrum

DB_PATH = '/app/backend/app/infrastructure/database/btc-quant.db'
RESULTS_DIR = Path('/app/backtest/results/pr2_results')
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# ── Parameters ─────────────────────────────────────────────────────────────────
INITIAL_CAPITAL   = 10_000.0
MARGIN_PER_TRADE  = 10.0        # $10 margin (sesuai live)
LEVERAGE          = 15          # 15x
TAKER_FEE         = 0.0004      # 0.04%
MAX_HOLD_CANDLES  = 6           # 24 jam

# Fixed TP parameters (current)
SL_PCT_FIXED      = 1.333 / 100
TP_PCT_FIXED      = 0.71  / 100

# Partial TP parameters (PR-2)
TP1_PCT_PARTIAL   = 0.71  / 100   # 50% close di sini
TP2_PCT_PARTIAL   = 1.50  / 100   # 50% close di sini (let run)
# Setelah TP1 hit: SL geser ke breakeven

WINDOW_START = "2024-01-01"
WINDOW_END   = "2026-03-25"

# ── Load Data ──────────────────────────────────────────────────────────────────
def load_data():
    conn = duckdb.connect(DB_PATH, read_only=True)
    df = conn.execute(f"""
        SELECT timestamp, open, high, low, close, volume
        FROM btc_ohlcv_4h
        WHERE timestamp >= {int(pd.Timestamp(WINDOW_START).timestamp() * 1000)}
          AND timestamp <= {int(pd.Timestamp(WINDOW_END).timestamp() * 1000)}
        ORDER BY timestamp ASC
    """).df()
    conn.close()

    df.columns = ['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df.set_index('timestamp')

    # Indicators
    df['EMA20'] = ta.ema(df['Close'], length=20)
    df['EMA50'] = ta.ema(df['Close'], length=50)
    df['ATR14'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)
    df['RSI14'] = ta.rsi(df['Close'], length=14)

    return df.dropna()


# ── Signal Generation (simplified V1 logic) ────────────────────────────────────
def get_signal(row):
    """
    Simplified V1 signal: BCD regime + EMA alignment
    Returns: 'LONG', 'SHORT', or None
    """
    price   = row['Close']
    ema20   = row['EMA20']
    ema50   = row['EMA50']

    # EMA trend
    if ema20 < ema50 and price < ema20:
        trend = 'BEAR'
    elif ema20 > ema50 and price > ema20:
        trend = 'BULL'
    elif price < ema50:
        trend = 'BEAR'
    elif price < ema20:
        trend = 'BEAR'
    else:
        trend = 'BULL'

    # Volatility gate
    atr     = row['ATR14']
    vol_ratio = atr / price if price > 0 else 0
    if vol_ratio >= 0.020:
        return None  # SUSPENDED

    return 'LONG' if trend == 'BULL' else 'SHORT'


# ── Backtest Engine ────────────────────────────────────────────────────────────
def run_backtest(df, mode='fixed'):
    """
    mode: 'fixed' = current Fixed TP | 'partial' = PR-2 Partial TP
    """
    trades = []
    capital = INITIAL_CAPITAL
    position = None

    for i in range(50, len(df)):
        row     = df.iloc[i]
        price   = row['Close']
        atr     = row['ATR14']

        # ── Manage open position ───────────────────────────────────────────────
        if position:
            candles_held = i - position['entry_idx']
            side         = position['side']
            entry        = position['entry_price']
            sl           = position['sl']
            tp1          = position['tp1']

            exit_price = None
            exit_type  = None

            if mode == 'fixed':
                # Check SL
                if side == 'LONG' and row['Low'] <= sl:
                    exit_price, exit_type = sl, 'SL'
                elif side == 'SHORT' and row['High'] >= sl:
                    exit_price, exit_type = sl, 'SL'
                # Check TP
                elif side == 'LONG' and row['High'] >= tp1:
                    exit_price, exit_type = tp1, 'TP'
                elif side == 'SHORT' and row['Low'] <= tp1:
                    exit_price, exit_type = tp1, 'TP'
                # Time exit
                elif candles_held >= MAX_HOLD_CANDLES:
                    exit_price, exit_type = price, 'TIME_EXIT'

            elif mode == 'partial':
                tp2     = position['tp2']
                partial = position.get('partial_done', False)

                # If partial TP1 already hit, use breakeven SL
                if partial:
                    be_sl = position['breakeven_sl']
                    if side == 'LONG' and row['Low'] <= be_sl:
                        exit_price, exit_type = be_sl, 'SL_BE'
                    elif side == 'SHORT' and row['High'] >= be_sl:
                        exit_price, exit_type = be_sl, 'SL_BE'
                    elif side == 'LONG' and row['High'] >= tp2:
                        exit_price, exit_type = tp2, 'TP2'
                    elif side == 'SHORT' and row['Low'] <= tp2:
                        exit_price, exit_type = tp2, 'TP2'
                    elif candles_held >= MAX_HOLD_CANDLES:
                        exit_price, exit_type = price, 'TIME_EXIT'
                else:
                    # Check SL first
                    if side == 'LONG' and row['Low'] <= sl:
                        exit_price, exit_type = sl, 'SL'
                    elif side == 'SHORT' and row['High'] >= sl:
                        exit_price, exit_type = sl, 'SL'
                    # Check TP1 (partial)
                    elif side == 'LONG' and row['High'] >= tp1:
                        # Hit TP1: close 50%, set breakeven SL for remaining 50%
                        position['partial_done'] = True
                        position['breakeven_sl'] = entry  # SL geser ke breakeven

                        # Record partial close
                        pnl = (tp1 - entry) / entry * LEVERAGE * MARGIN_PER_TRADE * 0.5
                        pnl -= TAKER_FEE * MARGIN_PER_TRADE * LEVERAGE  # fee
                        position['partial_pnl'] = pnl
                        continue
                    elif side == 'SHORT' and row['Low'] <= tp1:
                        position['partial_done'] = True
                        position['breakeven_sl'] = entry

                        pnl = (entry - tp1) / entry * LEVERAGE * MARGIN_PER_TRADE * 0.5
                        pnl -= TAKER_FEE * MARGIN_PER_TRADE * LEVERAGE
                        position['partial_pnl'] = pnl
                        continue
                    elif candles_held >= MAX_HOLD_CANDLES:
                        exit_price, exit_type = price, 'TIME_EXIT'

            # Close position
            if exit_price and exit_type:
                if mode == 'fixed':
                    if side == 'LONG':
                        pnl = (exit_price - entry) / entry * LEVERAGE * MARGIN_PER_TRADE
                    else:
                        pnl = (entry - exit_price) / entry * LEVERAGE * MARGIN_PER_TRADE
                    pnl -= TAKER_FEE * MARGIN_PER_TRADE * LEVERAGE * 2

                elif mode == 'partial':
                    partial_pnl = position.get('partial_pnl', 0)
                    if position.get('partial_done', False):
                        # Remaining 50%
                        if side == 'LONG':
                            remain_pnl = (exit_price - entry) / entry * LEVERAGE * MARGIN_PER_TRADE * 0.5
                        else:
                            remain_pnl = (entry - exit_price) / entry * LEVERAGE * MARGIN_PER_TRADE * 0.5
                        remain_pnl -= TAKER_FEE * MARGIN_PER_TRADE * LEVERAGE
                        pnl = partial_pnl + remain_pnl
                    else:
                        # Full close (SL hit before TP1)
                        if side == 'LONG':
                            pnl = (exit_price - entry) / entry * LEVERAGE * MARGIN_PER_TRADE
                        else:
                            pnl = (entry - exit_price) / entry * LEVERAGE * MARGIN_PER_TRADE
                        pnl -= TAKER_FEE * MARGIN_PER_TRADE * LEVERAGE * 2

                pnl_pct = pnl / MARGIN_PER_TRADE * 100
                capital += pnl

                trades.append({
                    'entry_time':  position['entry_time'],
                    'exit_time':   row.name,
                    'side':        side,
                    'entry_price': entry,
                    'exit_price':  exit_price,
                    'exit_type':   exit_type,
                    'pnl_usdt':    round(pnl, 4),
                    'pnl_pct':     round(pnl_pct, 2),
                    'hold_candles': candles_held,
                })
                position = None

        # ── Try open new position ──────────────────────────────────────────────
        if position is None:
            signal = get_signal(row)
            if signal is None:
                continue

            entry_price = price
            atr_val     = atr

            if signal == 'LONG':
                sl_price  = entry_price * (1 - SL_PCT_FIXED)
                tp1_price = entry_price * (1 + TP_PCT_FIXED)
                tp2_price = entry_price * (1 + TP2_PCT_PARTIAL)
            else:
                sl_price  = entry_price * (1 + SL_PCT_FIXED)
                tp1_price = entry_price * (1 - TP_PCT_FIXED)
                tp2_price = entry_price * (1 - TP2_PCT_PARTIAL)

            position = {
                'side':         signal,
                'entry_price':  entry_price,
                'entry_time':   row.name,
                'entry_idx':    i,
                'sl':           sl_price,
                'tp1':          tp1_price,
                'tp2':          tp2_price,
                'partial_done': False,
                'partial_pnl':  0.0,
                'breakeven_sl': entry_price,
            }

    return pd.DataFrame(trades)


# ── Analysis ───────────────────────────────────────────────────────────────────
def analyze(trades_df, mode_label):
    if trades_df.empty:
        print(f"{mode_label}: No trades!")
        return {}

    wins = trades_df[trades_df['pnl_usdt'] > 0]
    loss = trades_df[trades_df['pnl_usdt'] <= 0]

    n       = len(trades_df)
    wr      = len(wins) / n * 100
    total   = trades_df['pnl_usdt'].sum()
    avg_win = wins['pnl_usdt'].mean() if len(wins) > 0 else 0
    avg_los = loss['pnl_usdt'].mean() if len(loss) > 0 else 0
    pf      = abs(wins['pnl_usdt'].sum() / loss['pnl_usdt'].sum()) if len(loss) > 0 and loss['pnl_usdt'].sum() != 0 else 999

    # Daily return
    days = (trades_df['exit_time'].max() - trades_df['entry_time'].min()).days
    daily = total / INITIAL_CAPITAL * 100 / days if days > 0 else 0

    # Max drawdown
    equity = INITIAL_CAPITAL + trades_df['pnl_usdt'].cumsum()
    peak = equity.cummax()
    dd = ((equity - peak) / peak * 100).min()

    # Exit distribution
    exit_dist = trades_df['exit_type'].value_counts().to_dict()

    result = {
        'mode':         mode_label,
        'n_trades':     n,
        'win_rate_pct': round(wr, 2),
        'total_pnl':    round(total, 2),
        'daily_pct':    round(daily, 4),
        'max_dd_pct':   round(dd, 2),
        'profit_factor':round(pf, 3),
        'avg_win':      round(avg_win, 4),
        'avg_loss':     round(avg_los, 4),
        'exit_dist':    exit_dist,
    }

    print(f"\n{'='*50}")
    print(f"  {mode_label}")
    print(f"{'='*50}")
    for k, v in result.items():
        print(f"  {k}: {v}")

    return result


# ── Main ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Loading data...")
    df = load_data()
    print(f"Data: {len(df)} candles, {df.index[0]} to {df.index[-1]}")

    print("\nRunning FIXED TP backtest...")
    fixed_trades = run_backtest(df, mode='fixed')
    fixed_result = analyze(fixed_trades, "FIXED TP (current)")

    print("\nRunning PARTIAL TP backtest (PR-2)...")
    partial_trades = run_backtest(df, mode='partial')
    partial_result = analyze(partial_trades, "PARTIAL TP (PR-2)")

    # Save results
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    out = {
        'timestamp': ts,
        'window': f"{WINDOW_START} to {WINDOW_END}",
        'fixed':   fixed_result,
        'partial': partial_result,
    }
    out_path = RESULTS_DIR / f"pr2_comparison_{ts}.json"
    with open(out_path, 'w') as f:
        json.dump(out, f, indent=2)
    print(f"\nResults saved: {out_path}")
