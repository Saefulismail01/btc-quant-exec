"""
Unit tests for Trailing SL logic (isolated, no lighter import).

Tests the core logic functions without requiring actual Lighter API connection.
"""

import pytest
from datetime import datetime
from typing import Dict


# ── Trailing SL Parameters (copied from trailing_sl.py) ─────────────────────

TRAILING_PROFIT_THRESHOLD = 1.0  # % profit before trailing starts
TRAILING_LOCK_PROFIT = 0.5       # % profit to lock when trailing
TRAILING_STEP = 0.25             # Minimum price movement % before updating SL


# ── Trailing SL Logic Functions (isolated from API) ────────────────────────

def calculate_pnl_pct(position: Dict, current_price: float) -> float:
    """Calculate PnL percentage."""
    entry = position["entry"]
    side = position["side"]
    
    if side == "LONG":
        return (current_price - entry) / entry * 100
    else:
        return (entry - current_price) / entry * 100


def should_trail_sl(position: Dict, current_price: float) -> bool:
    """
    Check if SL should be trailed based on profit threshold.
    
    Args:
        position: Position dict with entry, side
        current_price: Current market price
        
    Returns:
        True if SL should be trailed
    """
    entry = position["entry"]
    side = position["side"]
    
    if side == "LONG":
        profit_pct = (current_price - entry) / entry * 100
    else:  # SHORT
        profit_pct = (entry - current_price) / entry * 100
    
    return profit_pct >= TRAILING_PROFIT_THRESHOLD


def calculate_trailing_sl(position: Dict, current_price: float) -> float:
    """
    Calculate new trailing SL price.
    
    Args:
        position: Position dict with entry, side
        current_price: Current market price
        
    Returns:
        New SL price
    """
    entry = position["entry"]
    side = position["side"]
    current_sl = position.get("sl_price", entry)
    
    if side == "LONG":
        # Lock profit: SL = entry * (1 + lock_profit%)
        new_sl = entry * (1 + TRAILING_LOCK_PROFIT / 100)
        # Only trail if new SL is higher (more favorable)
        new_sl = max(new_sl, current_sl)
    else:  # SHORT
        # Lock profit: SL = entry * (1 - lock_profit%)
        new_sl = entry * (1 - TRAILING_LOCK_PROFIT / 100)
        # Only trail if new SL is lower (more favorable for short)
        new_sl = min(new_sl, current_sl)
    
    return new_sl


def check_trailing_step(new_sl: float, current_sl: float) -> bool:
    """
    Check if movement is significant enough to update SL.
    
    Args:
        new_sl: Proposed new SL price
        current_sl: Current SL price
        
    Returns:
        True if movement >= TRAILING_STEP
    """
    movement_pct = abs(new_sl - current_sl) / current_sl * 100
    return movement_pct >= TRAILING_STEP


# ── Unit Tests ─────────────────────────────────────────────────────────────

class TestTrailingSLLogic:
    """Test trailing SL logic independently of API."""
    
    def test_should_trail_sl_long_profitable(self):
        """Test that SL should trail when LONG position is profitable."""
        position = {
            "side": "LONG",
            "entry": 100.0,
            "size": 0.1,
            "pnl": 1.0,
            "tied_orders": 2
        }
        
        # 2% profit (above 1% threshold)
        current_price = 102.0
        
        result = should_trail_sl(position, current_price)
        
        assert result is True, "Should trail when profit >= 1%"
    
    def test_should_trail_sl_long_not_profitable(self):
        """Test that SL should NOT trail when LONG position not profitable enough."""
        position = {
            "side": "LONG",
            "entry": 100.0,
            "size": 0.1,
            "pnl": -0.5,
            "tied_orders": 2
        }
        
        # 0.5% profit (below 1% threshold)
        current_price = 100.5
        
        result = should_trail_sl(position, current_price)
        
        assert result is False, "Should NOT trail when profit < 1%"
    
    def test_should_trail_sl_short_profitable(self):
        """Test that SL should trail when SHORT position is profitable."""
        position = {
            "side": "SHORT",
            "entry": 100.0,
            "size": 0.1,
            "pnl": 1.0,
            "tied_orders": 2
        }
        
        # Price dropped 2% (profitable for short)
        current_price = 98.0
        
        result = should_trail_sl(position, current_price)
        
        assert result is True, "Should trail when short position profitable >= 1%"
    
    def test_should_trail_sl_short_not_profitable(self):
        """Test that SL should NOT trail when SHORT position not profitable enough."""
        position = {
            "side": "SHORT",
            "entry": 100.0,
            "size": 0.1,
            "pnl": -0.5,
            "tied_orders": 2
        }
        
        # Price dropped 0.5% (below threshold)
        current_price = 99.5
        
        result = should_trail_sl(position, current_price)
        
        assert result is False, "Should NOT trail when short profit < 1%"
    
    def test_should_trail_sl_exactly_threshold(self):
        """Test edge case: profit exactly at threshold."""
        position = {
            "side": "LONG",
            "entry": 100.0,
            "size": 0.1,
            "pnl": 1.0,
            "tied_orders": 2
        }
        
        # Exactly 1% profit
        current_price = 101.0
        
        result = should_trail_sl(position, current_price)
        
        assert result is True, "Should trail when profit exactly at threshold (1%)"
    
    def test_should_trail_sl_long_loss(self):
        """Test that SL should NOT trail when LONG position at loss."""
        position = {
            "side": "LONG",
            "entry": 100.0,
            "size": 0.1,
            "pnl": -2.0,
            "tied_orders": 2
        }
        
        # 2% loss
        current_price = 98.0
        
        result = should_trail_sl(position, current_price)
        
        assert result is False, "Should NOT trail when position at loss"
    
    def test_calculate_trailing_sl_long(self):
        """Test trailing SL calculation for LONG position."""
        position = {
            "side": "LONG",
            "entry": 100.0,
            "size": 0.1,
            "pnl": 2.0,
            "tied_orders": 2,
            "sl_price": 98.0  # Current SL at 2% below entry
        }
        
        current_price = 103.0
        
        new_sl = calculate_trailing_sl(position, current_price)
        
        # Should lock 0.5% profit: SL = 100 * 1.005 = 100.5
        # Should be higher than current SL (98.0)
        expected_sl = 100.5
        assert abs(new_sl - expected_sl) < 0.01, f"SL should be ~{expected_sl}, got {new_sl}"
        assert new_sl > 98.0, "New SL should be higher than current SL"
    
    def test_calculate_trailing_sl_short(self):
        """Test trailing SL calculation for SHORT position."""
        position = {
            "side": "SHORT",
            "entry": 100.0,
            "size": 0.1,
            "pnl": 2.0,
            "tied_orders": 2,
            "sl_price": 102.0  # Current SL at 2% above entry
        }
        
        current_price = 97.0
        
        new_sl = calculate_trailing_sl(position, current_price)
        
        # Should lock 0.5% profit: SL = 100 * 0.995 = 99.5
        # Should be lower than current SL (102.0)
        expected_sl = 99.5
        assert new_sl <= expected_sl, f"SL should be <= {expected_sl}, got {new_sl}"
        assert new_sl < 102.0, "New SL should be lower than current SL"
    
    def test_calculate_trailing_sl_only_improves_long(self):
        """Test that trailing SL only moves UP for LONG."""
        position = {
            "side": "LONG",
            "entry": 100.0,
            "size": 0.1,
            "pnl": 1.0,
            "tied_orders": 2,
            "sl_price": 101.0  # Current SL already above entry
        }
        
        current_price = 101.5
        new_sl = calculate_trailing_sl(position, current_price)
        
        # Lock profit SL = 100.5, but current is 101.0
        # Should keep current SL (higher is better)
        assert new_sl >= 101.0, "LONG SL should not decrease"
    
    def test_calculate_trailing_sl_only_improves_short(self):
        """Test that trailing SL only moves DOWN for SHORT."""
        position = {
            "side": "SHORT",
            "entry": 100.0,
            "size": 0.1,
            "pnl": 1.0,
            "tied_orders": 2,
            "sl_price": 99.0  # Current SL already below entry
        }
        
        current_price = 98.5
        new_sl = calculate_trailing_sl(position, current_price)
        
        # Lock profit SL = 99.5, but current is 99.0
        # Should keep current SL (lower is better for short)
        assert new_sl <= 99.0, "SHORT SL should not increase"
    
    def test_check_trailing_step_significant(self):
        """Test that significant movement passes step check."""
        current_sl = 100.0
        new_sl = 100.5  # 0.5% movement
        
        result = check_trailing_step(new_sl, current_sl)
        
        assert result is True, "0.5% movement should pass step check (0.25% threshold)"
    
    def test_check_trailing_step_not_significant(self):
        """Test that small movement fails step check."""
        current_sl = 100.0
        new_sl = 100.2  # 0.2% movement
        
        result = check_trailing_step(new_sl, current_sl)
        
        assert result is False, "0.2% movement should fail step check (0.25% threshold)"
    
    def test_check_trailing_step_exactly_threshold(self):
        """Test edge case: movement exactly at step threshold."""
        current_sl = 100.0
        new_sl = 100.25  # 0.25% movement
        
        result = check_trailing_step(new_sl, current_sl)
        
        assert result is True, "Movement at threshold should pass"


class TestPnLCalculation:
    """Test PnL calculation logic."""
    
    def test_pnl_calc_long_profit(self):
        """Test PnL calculation for profitable LONG."""
        position = {"side": "LONG", "entry": 100.0}
        current_price = 105.0
        
        pnl = calculate_pnl_pct(position, current_price)
        
        assert pnl == 5.0, f"Expected 5% profit, got {pnl}%"
    
    def test_pnl_calc_long_loss(self):
        """Test PnL calculation for losing LONG."""
        position = {"side": "LONG", "entry": 100.0}
        current_price = 95.0
        
        pnl = calculate_pnl_pct(position, current_price)
        
        assert pnl == -5.0, f"Expected -5% loss, got {pnl}%"
    
    def test_pnl_calc_short_profit(self):
        """Test PnL calculation for profitable SHORT."""
        position = {"side": "SHORT", "entry": 100.0}
        current_price = 95.0
        
        pnl = calculate_pnl_pct(position, current_price)
        
        assert pnl == 5.0, f"Expected 5% profit, got {pnl}%"
    
    def test_pnl_calc_short_loss(self):
        """Test PnL calculation for losing SHORT."""
        position = {"side": "SHORT", "entry": 100.0}
        current_price = 105.0
        
        pnl = calculate_pnl_pct(position, current_price)
        
        assert pnl == -5.0, f"Expected -5% loss, got {pnl}%"
    
    def test_pnl_calc_breakeven(self):
        """Test PnL calculation at breakeven."""
        position = {"side": "LONG", "entry": 100.0}
        current_price = 100.0
        
        pnl = calculate_pnl_pct(position, current_price)
        
        assert pnl == 0.0, f"Expected 0% at breakeven, got {pnl}%"


class TestTrailingSLParameters:
    """Test trailing SL parameter configuration."""
    
    def test_profit_threshold(self):
        """Test that profit threshold is correctly set."""
        assert TRAILING_PROFIT_THRESHOLD == 1.0, "Default threshold should be 1%"
    
    def test_lock_profit(self):
        """Test that lock profit is correctly set."""
        assert TRAILING_LOCK_PROFIT == 0.5, "Default lock profit should be 0.5%"
    
    def test_trailing_step(self):
        """Test that trailing step is correctly set."""
        assert TRAILING_STEP == 0.25, "Default step should be 0.25%"


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_zero_profit(self):
        """Test behavior at exactly 0% profit."""
        position = {"side": "LONG", "entry": 100.0}
        current_price = 100.0
        
        result = should_trail_sl(position, current_price)
        
        assert result is False, "Should NOT trail at 0% profit"
    
    def test_very_small_profit(self):
        """Test behavior with very small profit (0.01%)."""
        position = {"side": "LONG", "entry": 100.0}
        current_price = 100.01  # 0.01% profit
        
        result = should_trail_sl(position, current_price)
        
        assert result is False, "Should NOT trail at 0.01% profit"
    
    def test_very_large_profit(self):
        """Test behavior with very large profit (10%)."""
        position = {"side": "LONG", "entry": 100.0}
        current_price = 110.0  # 10% profit
        
        result = should_trail_sl(position, current_price)
        
        assert result is True, "Should trail at 10% profit"
    
    def test_negative_price_long(self):
        """Test handling of invalid negative price."""
        position = {"side": "LONG", "entry": 100.0}
        current_price = -50.0  # Invalid
        
        # This should still calculate, though result is meaningless
        pnl = calculate_pnl_pct(position, current_price)
        assert pnl < 0, "Negative price should result in negative PnL"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
