"""
FixedStrategy: Golden v4.4 — parameter hardcoded.

SL=1.333%, TP=0.71%, Leverage=15x, Margin=$1000.
Ini adalah baseline strategy yang terbukti dari backtest v4.4.

Tidak boleh diubah tanpa validasi backtest ulang.
"""

from .base_strategy import BaseTradePlanStrategy, TradeParams

# Golden v4.4 Constants
SL_PCT      = 1.333   # %
TP_PCT      = 0.71    # %
LEVERAGE    = 15
MARGIN_USD  = 1.0


class FixedStrategy(BaseTradePlanStrategy):
    """
    Strategy dengan parameter tetap (Golden v4.4).
    Tidak bergantung pada kondisi pasar — cocok sebagai default/fallback.
    """

    def calculate(self, entry_price: float, action: str, signal_data: dict) -> TradeParams:
        is_long = action == "LONG"

        sl_price = entry_price * (1 - SL_PCT / 100) if is_long else entry_price * (1 + SL_PCT / 100)
        tp_price = entry_price * (1 + TP_PCT / 100) if is_long else entry_price * (1 - TP_PCT / 100)

        return TradeParams(
            sl_price      = round(sl_price, 2),
            tp_price      = round(tp_price, 2),
            leverage      = LEVERAGE,
            margin_usd    = MARGIN_USD,
            sl_pct        = SL_PCT,
            tp_pct        = TP_PCT,
            strategy_name = "FixedStrategy (Golden v4.4)",
            rationale     = f"SL={SL_PCT}% | TP={TP_PCT}% | Lev={LEVERAGE}x | Margin=${MARGIN_USD:,.0f}",
        )
