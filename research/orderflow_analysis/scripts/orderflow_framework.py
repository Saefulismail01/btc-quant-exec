"""
Orderflow-Based Exit Automation Framework
Menggantikan 7 intervensi manual dengan rules berbasis data orderflow.
"""

import pandas as pd
from dataclasses import dataclass
from typing import List, Optional, Dict
from enum import Enum

class ExitSignal(Enum):
    HOLD = "hold"
    PARTIAL_TP = "partial_tp"  # Close 50% at 50% of TP
    FULL_TP = "full_tp"  # Full close, momentum confirmed
    MANUAL_CUTOFF = "manual_cutoff"  # Time-based exit
    MOMENTUM_DECAY = "momentum_decay"  # Delta divergence detected
    SL_ADJUST = "sl_adjust"  # Trailing SL


@dataclass
class OrderflowFeatures:
    """Features dari orderflow untuk decision making."""
    # Delta features
    delta_5m: float  # Net delta 5 menit terakhir
    delta_15m: float
    delta_divergence: bool  # Harga naik tapi delta negatif (bearish)
    
    # Volume features
    volume_profile_poc: float  # Point of Control
    current_volume_vs_avg: float  # Ratio volume sekarang vs average
    
    # Imbalance
    bid_ask_imbalance: float  # Positive = more bids, Negative = more asks
    
    # Time features
    hold_time_min: int
    time_since_entry_pct: float  # % dari waktu hold rata-rata
    
    # Price features
    price_vs_vwap: float  # % distance dari VWAP
    price_vs_poc: float  # % distance dari Volume POC
    
    # Volatility
    current_atr: float
    atr_percentile: float  # ATR sekarang di percentile berapa (0-100)


@dataclass
class PositionState:
    """State posisi yang sedang berjalan."""
    entry_price: float
    entry_time: pd.Timestamp
    direction: str  # "LONG" or "SHORT"
    size: float
    notional: float
    
    # Targets
    tp_target: float  # Harga TP
    sl_price: float  # Harga SL
    tp_pct: float  # Target PnL %
    
    # Current
    current_price: float
    current_pnl_pct: float
    hold_time_min: int


class OrderflowExitEngine:
    """
    Engine untuk menentukan exit berbasis orderflow.
    
    Goal: Gantikan 7 intervensi manual dengan rules otomatis.
    """
    
    def __init__(self):
        # Thresholds
        self.partial_tp_at = 0.50  # 50% of TP distance
        self.partial_close_pct = 0.50  # Close 50% position
        
        self.time_decay_threshold_min = 90  # 90 menit
        self.momentum_check_interval = 30  # Cek momentum tiap 30 menit
        
    def evaluate_exit(self, position: PositionState, 
                     orderflow: OrderflowFeatures) -> ExitSignal:
        """
        Evaluate apakah perlu exit berdasarkan orderflow.
        
        Returns ExitSignal dengan priority:
        1. Partial TP (scale out)
        2. Momentum decay (exit early)
        3. Time decay (cut if no progress)
        4. Hold untuk TP penuh
        """
        
        # === RULE 1: Partial TP at 50% target ===
        if self._should_partial_tp(position, orderflow):
            return ExitSignal.PARTIAL_TP
        
        # === RULE 2: Momentum Decay Detection ===
        if self._detect_momentum_decay(position, orderflow):
            return ExitSignal.MOMENTUM_DECAY
        
        # === RULE 3: Time-Based Cutoff ===
        if self._check_time_decay(position, orderflow):
            return ExitSignal.MANUAL_CUTOFF
        
        # === RULE 4: SL Adjustment (Trailing) ===
        if self._should_adjust_sl(position, orderflow):
            return ExitSignal.SL_ADJUST
        
        return ExitSignal.HOLD
    
    def _should_partial_tp(self, pos: PositionState, of: OrderflowFeatures) -> bool:
        """
        Rule: Close 50% position saat mencapai 50% dari TP target.
        
        Contoh: Entry $100, TP $110 (10%), maka partial TP di $105 (5%).
        """
        # Hitung 50% distance ke TP
        tp_distance = abs(pos.tp_target - pos.entry_price)
        half_tp_distance = tp_distance * self.partial_tp_at
        
        # Harga 50% TP
        if pos.direction == "LONG":
            half_tp_price = pos.entry_price + half_tp_distance
            reached_half_tp = pos.current_price >= half_tp_price
        else:  # SHORT
            half_tp_price = pos.entry_price - half_tp_distance
            reached_half_tp = pos.current_price <= half_tp_price
        
        return reached_half_tp and pos.current_pnl_pct > 0
    
    def _detect_momentum_decay(self, pos: PositionState, of: OrderflowFeatures) -> bool:
        """
        Rule: Exit jika momentum decay terdeteksi via orderflow.
        
        Signals:
        - Delta divergence: Harga naik tapi delta negatif (untuk LONG)
        - Imbalance flip: Bid/Ask ratio berubah arah
        - Volume climax: Spike volume tanpa continuation
        """
        if pos.direction == "LONG":
            # Untuk posisi LONG, decay signals:
            # 1. Delta divergence
            if of.delta_divergence:
                return True
            
            # 2. Strong ask imbalance (negative bid_ask_imbalance)
            if of.bid_ask_imbalance < -0.3:  # 30% more asks than bids
                return True
                
        else:  # SHORT
            # Untuk posisi SHORT, decay signals kebalikan
            # 1. Delta divergence (reverse)
            if of.delta_divergence:
                return True
            
            # 2. Strong bid imbalance
            if of.bid_ask_imbalance > 0.3:
                return True
        
        return False
    
    def _check_time_decay(self, pos: PositionState, of: OrderflowFeatures) -> bool:
        """
        Rule: Time-based exit jika hold lama tapi progress kecil.
        
        Dari analisis: Trade > 90 menit dengan PnL < 50% TP cenderung loss.
        """
        if pos.hold_time_min < self.time_decay_threshold_min:
            return False
        
        # Jika sudah > 90 menit tapi PnL belum 50% dari target
        progress_pct = pos.current_pnl_pct / pos.tp_pct
        
        if progress_pct < 0.5:  # Belum sampai 50% target
            return True
        
        return False
    
    def _should_adjust_sl(self, pos: PositionState, of: OrderflowFeatures) -> bool:
        """
        Rule: Adjust SL ke break-even atau trailing jika sudah profitable.
        """
        # Jika sudah profitable dan hold > 30 menit, adjust SL
        if pos.current_pnl_pct > 1.0 and pos.hold_time_min > 30:
            return True
        
        return False


def print_framework():
    """Print framework rules."""
    print("=" * 70)
    print("ORDERFLOW EXIT AUTOMATION FRAMEWORK")
    print("=" * 70)
    
    print("""
Tujuan: Gantikan 7 intervensi manual dengan rules otomatis

=== RULE PRIORITY (High to Low) ===

1. PARTIAL TP (Scale Out)
   Trigger: Harga mencapai 50% dari TP target
   Action: Close 50% position, biarkan 50% runner ke TP
   
   Contoh: Entry $100k, TP $100.67k (0.67% move)
           Partial TP di $100.335k (0.335% move)
           → Secure profit, reduce risk, keep upside

2. MOMENTUM DECAY (Early Exit)
   Trigger: Delta divergence atau imbalance flip
   Action: Close full position
   
   Signals:
   - Delta 5m/15m berlawanan arah dengan posisi
   - Bid/Ask imbalance > 30% di arah berlawanan
   - Volume spike tanpa price continuation

3. TIME DECAY (Cutoff)
   Trigger: Hold > 90 menit, PnL < 50% target
   Action: Close position (momentum tidak ada)
   
   Dari analisis: Trade > 90 menit cenderung reverse

4. SL ADJUSTMENT (Trailing)
   Trigger: Profitable > 1%, hold > 30 menit
   Action: Move SL ke break-even atau trailing

=== IMPLEMENTATION ===

Data yang perlu:
- Real-time orderflow (delta, volume, imbalance)
- Harga dan waktu entry
- Position state (size, direction, targets)

Integration dengan bot:
- Hook ke execution layer
- Override TP/SL manual dengan orderflow signals
- Log decisions untuk evaluasi
""")


if __name__ == '__main__':
    print_framework()
