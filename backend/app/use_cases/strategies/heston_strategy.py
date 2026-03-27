"""
HestonStrategy: SL/TP dari sl_tp_preset signal (Econophysics Modul A+B).

sl_tp_preset dihasilkan dari kombinasi:
- Modul A (Transition Matrix): regime persistence → durasi posisi
- Modul B (Heston): vol regime → lebar SL/TP

Jika sl_tp_preset tidak tersedia di signal (None / fallback),
otomatis fallback ke FixedStrategy.
"""

import logging
from .base_strategy import BaseTradePlanStrategy, TradeParams
from .fixed_strategy import FixedStrategy

logger = logging.getLogger(__name__)

# Default ATR multiplier jika ATR tidak tersedia
_DEFAULT_ATR_FALLBACK = 1500.0   # ~1500 USD — approximate ATR BTC 4H
LEVERAGE   = 7
MARGIN_USD = 20.0  # $20 margin × 7x = $140 notional


class HestonStrategy(BaseTradePlanStrategy):
    """
    Strategy berbasis Heston volatility model.

    SL distance = ATR14 × sl_multiplier  (dari sl_tp_preset)
    TP distance = ATR14 × tp1_multiplier (dari sl_tp_preset)

    Fallback ke FixedStrategy jika:
    - signal.sl_tp_preset is None
    - ATR tidak tersedia
    """

    def __init__(self):
        self._fallback = FixedStrategy()

    def calculate(self, entry_price: float, action: str, signal_data: dict) -> TradeParams:
        preset = signal_data.get("sl_tp_preset")

        # Fallback jika preset tidak ada
        if not preset:
            logger.info("[HestonStrategy] sl_tp_preset not available — falling back to FixedStrategy")
            return self._fallback.calculate(entry_price, action, signal_data)

        sl_multiplier  = float(preset.get("sl_multiplier",  1.5))
        tp1_multiplier = float(preset.get("tp1_multiplier", 1.5))
        preset_name    = preset.get("preset_name", "Normal")
        rationale      = preset.get("rationale", "")

        # Ambil ATR dari signal
        atr = float(signal_data.get("price", {}).get("atr14", 0.0))
        if atr <= 0:
            atr = _DEFAULT_ATR_FALLBACK
            logger.warning(f"[HestonStrategy] ATR not available, using fallback ${atr:,.0f}")

        sl_distance = atr * sl_multiplier
        tp_distance = atr * tp1_multiplier

        is_long  = action == "LONG"
        sl_price = entry_price - sl_distance if is_long else entry_price + sl_distance
        tp_price = entry_price + tp_distance if is_long else entry_price - tp_distance

        sl_pct = (sl_distance / entry_price) * 100
        tp_pct = (tp_distance / entry_price) * 100

        logger.info(
            f"[HestonStrategy] Preset={preset_name} | ATR=${atr:,.0f} | "
            f"SL×{sl_multiplier}=${sl_distance:,.0f} ({sl_pct:.2f}%) | "
            f"TP×{tp1_multiplier}=${tp_distance:,.0f} ({tp_pct:.2f}%)"
        )

        return TradeParams(
            sl_price      = round(sl_price, 2),
            tp_price      = round(tp_price, 2),
            leverage      = LEVERAGE,
            margin_usd    = MARGIN_USD,
            sl_pct        = round(sl_pct, 3),
            tp_pct        = round(tp_pct, 3),
            strategy_name = f"HestonStrategy ({preset_name})",
            rationale     = rationale or f"ATR={atr:,.0f} | SL×{sl_multiplier} | TP×{tp1_multiplier}",
        )
