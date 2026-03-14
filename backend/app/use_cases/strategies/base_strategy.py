"""
BaseTradePlanStrategy: Abstract interface for all trade plan strategies.

Setiap strategy menerima entry_price dan action (LONG/SHORT),
lalu mengembalikan TradeParams berisi SL, TP, leverage, dan sizing.

PositionManager hanya perlu tahu interface ini — tidak peduli
strategy mana yang dipakai (Fixed, Heston, Kelly, dll).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class TradeParams:
    """
    Output dari TradePlanStrategy.calculate().

    Semua nilai dalam USD kecuali yang diberi label lain.
    """
    sl_price:          float   # Stop loss price
    tp_price:          float   # Take profit price
    leverage:          int     # Leverage multiplier
    margin_usd:        float   # Margin per trade (USD)
    sl_pct:            float   # SL distance as % of entry
    tp_pct:            float   # TP distance as % of entry
    strategy_name:     str     # Nama strategy yang dipakai (untuk log/audit)
    rationale:         str = ""  # Penjelasan singkat parameter ini dipilih


class BaseTradePlanStrategy(ABC):
    """
    Abstract strategy untuk menentukan SL, TP, dan leverage dari trade.

    Implementasi:
    - FixedStrategy  : Golden v4.4 — parameter hardcoded
    - HestonStrategy : SL/TP dari sl_tp_preset signal (Heston-based multiplier)
    - KellyStrategy  : Sizing dari Kelly Criterion (future)
    """

    @abstractmethod
    def calculate(
        self,
        entry_price: float,
        action: str,          # "LONG" or "SHORT"
        signal_data: dict,    # Full signal dict — strategy bisa ambil data tambahan
    ) -> TradeParams:
        """
        Hitung parameter trade dari entry price dan arah.

        Args:
            entry_price : Harga entry estimasi (dari signal.price.now)
            action      : "LONG" atau "SHORT"
            signal_data : Dict dari SignalResponse — untuk strategy yang butuh
                          data tambahan (ATR, sl_tp_preset, conviction, dll)

        Returns:
            TradeParams dengan SL, TP, leverage, margin
        """
        ...
