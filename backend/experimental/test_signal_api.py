import asyncio
import sys
import json
from pathlib import Path

_BACKEND_DIR = str(Path(__file__).resolve().parent)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.services.signal_service import get_signal_service
from app.repository.duckdb_repo import DuckDBRepository

def test_signal():
    print("Testing SignalService for Modul A & B outputs...")
    svc = get_signal_service()
    res = svc.get_signal()
    
    if res.is_fallback:
        print("Fallback trigger:", res.trade_plan.status_reason)
        return
        
    print(f"\nTime: {res.timestamp}")
    print(f"Action: {res.trade_plan.action}")
    print(f"Price: {res.price.now}")
    
    print("\n--- Modul A (Regime Bias) ---")
    if res.regime_bias:
        print(f"Bias Score: {res.regime_bias.bias_score}")
        print(f"Persistence: {res.regime_bias.persistence}")
        print(f"Reversal Prob: {res.regime_bias.reversal_prob}")
        print(f"Expected Duration: {res.regime_bias.expected_duration_candles} candles")
        print(f"Interp: {res.regime_bias.interpretation}")
    else:
        print("No regime bias data found in signal.")
        
    print("\n--- Modul B (Heston Volatility) ---")
    if res.heston_vol:
        print(f"Regime: {res.heston_vol.vol_regime}")
        print(f"Current Vol: {res.heston_vol.current_vol}")
        print(f"Long-run Vol: {res.heston_vol.long_run_vol}")
        print(f"Half-life: {res.heston_vol.mean_reversion_halflife_candles}")
        print(f"Interp: {res.heston_vol.interpretation}")
    else:
        print("No Heston vol data found in signal.")
        
    print("\n--- I-05 Dynamic SL/TP Presets ---")
    if res.sl_tp_preset:
        print(f"Preset Name: {res.sl_tp_preset.preset_name}")
        print(f"SL Mult: {res.sl_tp_preset.sl_multiplier}")
        print(f"TP1 Mult: {res.sl_tp_preset.tp1_multiplier}")
        print(f"TP2 Mult: {res.sl_tp_preset.tp2_multiplier}")
        print(f"Rationale: {res.sl_tp_preset.rationale}")
        print(f"\nCalculated ABS SL: {res.trade_plan.sl}")
        print(f"Calculated ABS TP1: {res.trade_plan.tp1}")
        print(f"Calculated ABS TP2: {res.trade_plan.tp2}")
    else:
        print("No SL/TP preset found in signal.")

    print("\n--- Confluence & AI Agent Rationale ---")
    print(f"Verdict: {res.confluence.verdict}")
    print(f"Directional Bias: {res.confluence.directional_bias}")
    print(f"Conviction: {res.confluence.conviction_pct}%")
    print(f"Layer Contributions: {res.confluence.layer_contributions}")
    rat = res.confluence.rationale.replace("\\n-", "\n-")
    print(f"Rationale:\n{rat}")

if __name__ == "__main__":
    test_signal()
