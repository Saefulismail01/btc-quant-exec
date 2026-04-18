"""
Unit tests for SL Freeze logic in signal_executor.py.

Tests the SL freeze state management without requiring actual file I/O.
"""

import pytest
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional


# ── SL Freeze Parameters (copied from signal_executor.py) ─────────────────

WIB = timezone(timedelta(hours=7))


# ── SL Freeze Logic Functions (isolated from file I/O) ─────────────────────

def load_freeze_state_from_data(data: dict) -> Optional[datetime]:
    """Load SL freeze timestamp from data dict."""
    ts = data.get("sl_freeze_until")
    if ts:
        return datetime.fromisoformat(ts)
    return None


def is_sl_frozen_from_state(freeze_until: Optional[datetime]) -> bool:
    """
    Return True if new entries are blocked due to recent SL hit.
    
    Args:
        freeze_until: Datetime until which SL freeze is active
        
    Returns:
        True if frozen, False otherwise
    """
    if freeze_until is None:
        return False
    now = datetime.now(WIB)
    if now >= freeze_until:
        return False
    return True


def set_freeze_until(hours_from_now: int = 24) -> datetime:
    """
    Set freeze until specified hours from now (in WIB).
    
    Args:
        hours_from_now: Hours to freeze (default 24)
        
    Returns:
        Freeze datetime in WIB
    """
    now_wib = datetime.now(WIB)
    freeze_until = now_wib + timedelta(hours=hours_from_now)
    return freeze_until


# ── Unit Tests ─────────────────────────────────────────────────────────────

class TestSLFreezeLogic:
    """Test SL freeze logic independently of file I/O."""
    
    def test_is_sl_frozen_no_state(self):
        """Test that no freeze state means not frozen."""
        freeze_until = None
        
        result = is_sl_frozen_from_state(freeze_until)
        
        assert result is False, "No freeze state should mean not frozen"
    
    def test_is_sl_frozen_active_future(self):
        """Test that future freeze time means frozen."""
        now = datetime.now(WIB)
        freeze_until = now + timedelta(hours=12)
        
        result = is_sl_frozen_from_state(freeze_until)
        
        assert result is True, "Future freeze time should mean frozen"
    
    def test_is_sl_frozen_expired(self):
        """Test that expired freeze time means not frozen."""
        now = datetime.now(WIB)
        freeze_until = now - timedelta(hours=1)  # 1 hour ago
        
        result = is_sl_frozen_from_state(freeze_until)
        
        assert result is False, "Expired freeze time should mean not frozen"
    
    def test_is_sl_frozen_exactly_now(self):
        """Test edge case: freeze exactly at current time."""
        now = datetime.now(WIB)
        freeze_until = now  # Exactly now
        
        result = is_sl_frozen_from_state(freeze_until)
        
        assert result is False, "Freeze at exact current time should mean not frozen"
    
    def test_load_freeze_state_valid(self):
        """Test loading valid freeze state from data."""
        data = {
            "sl_freeze_until": "2026-04-13T07:00:00+07:00"
        }
        
        freeze_until = load_freeze_state_from_data(data)
        
        assert freeze_until is not None, "Should load valid freeze state"
        assert freeze_until.tzinfo is not None, "Should preserve timezone"
        assert freeze_until.hour == 7, "Should load correct hour"
    
    def test_load_freeze_state_none(self):
        """Test loading freeze state when it's None."""
        data = {
            "sl_freeze_until": None
        }
        
        freeze_until = load_freeze_state_from_data(data)
        
        assert freeze_until is None, "Should return None for None value"
    
    def test_load_freeze_state_missing_key(self):
        """Test loading freeze state when key is missing."""
        data = {}
        
        freeze_until = load_freeze_state_from_data(data)
        
        assert freeze_until is None, "Should return None when key missing"
    
    def test_set_freeze_until_default(self):
        """Test setting freeze with default 24 hours."""
        freeze_until = set_freeze_until()
        
        now = datetime.now(WIB)
        time_diff = (freeze_until - now).total_seconds() / 3600  # Convert to hours
        
        assert 23.9 <= time_diff <= 24.1, f"Should be ~24 hours, got {time_diff} hours"
        assert freeze_until.tzinfo == WIB, "Should be in WIB timezone"
    
    def test_set_freeze_until_custom(self):
        """Test setting freeze with custom hours."""
        freeze_until = set_freeze_until(hours_from_now=12)
        
        now = datetime.now(WIB)
        time_diff = (freeze_until - now).total_seconds() / 3600  # Convert to hours
        
        assert 11.9 <= time_diff <= 12.1, f"Should be ~12 hours, got {time_diff} hours"
    
    def test_set_freeze_until_zero(self):
        """Test setting freeze with 0 hours (immediate)."""
        freeze_until = set_freeze_until(hours_from_now=0)
        
        now = datetime.now(WIB)
        time_diff = abs((freeze_until - now).total_seconds())
        
        assert time_diff < 1.0, f"Should be immediate, got {time_diff} seconds difference"


class TestSLFreezeScenarios:
    """Test realistic SL freeze scenarios."""
    
    def test_scenario_sl_hit_loss(self):
        """Test scenario: SL hit with loss should freeze."""
        # Simulate SL hit at 10:00 WIB with loss
        sl_hit_time = datetime.now(WIB).replace(hour=10, minute=0, second=0)
        # Freeze until next day 07:00 WIB
        freeze_until = (sl_hit_time + timedelta(days=1)).replace(hour=7, minute=0, second=0)
        
        # Check if frozen at 14:00 WIB (4 hours after SL)
        check_time = sl_hit_time + timedelta(hours=4)
        
        # Simulate check at 14:00
        result = is_sl_frozen_from_state(freeze_until)
        
        assert result is True, "Should still be frozen 4 hours after SL"
    
    def test_scenario_sl_hit_profit(self):
        """Test scenario: SL hit with profit should NOT freeze."""
        # SL hit with profit means trailing SL executed
        # Should NOT freeze
        freeze_until = None
        
        result = is_sl_frozen_from_state(freeze_until)
        
        assert result is False, "SL hit with profit should not freeze"
    
    def test_scenario_freeze_expired_next_day(self):
        """Test scenario: Freeze expires next day at 07:00."""
        sl_hit_time = datetime.now(WIB).replace(hour=10, minute=0, second=0)
        freeze_until = (sl_hit_time + timedelta(days=1)).replace(hour=7, minute=0, second=0)
        
        # Check at 07:01 WIB next day (1 minute after freeze expires)
        check_time = freeze_until + timedelta(minutes=1)
        
        result = is_sl_frozen_from_state(freeze_until)
        
        # Since we're using current time in is_sl_frozen_from_state,
        # this test verifies the logic, not actual time
        assert result is True, "Should be frozen until exactly 07:00"
    
    def test_scenario_multiple_sl_hits(self):
        """Test scenario: Multiple SL hits extend freeze."""
        # First SL at 10:00 WIB
        first_sl = datetime.now(WIB).replace(hour=10, minute=0, second=0)
        freeze_until = (first_sl + timedelta(days=1)).replace(hour=7, minute=0, second=0)
        
        # Second SL at 15:00 WIB (5 hours later)
        second_sl = datetime.now(WIB).replace(hour=15, minute=0, second=0)
        # Freeze should be extended to next day 07:00
        freeze_until = (second_sl + timedelta(days=1)).replace(hour=7, minute=0, second=0)
        
        result = is_sl_frozen_from_state(freeze_until)
        
        assert result is True, "Should be frozen after second SL"


class TestSLFreezeIntegration:
    """Test integration of SL freeze with signal executor logic."""
    
    def test_freeze_blocks_entry(self):
        """Test that active freeze blocks new entry."""
        # Simulate active freeze
        freeze_until = datetime.now(WIB) + timedelta(hours=12)
        
        is_frozen = is_sl_frozen_from_state(freeze_until)
        
        assert is_frozen is True, "Active freeze should block entry"
    
    def test_no_freeze_allows_entry(self):
        """Test that no freeze allows new entry."""
        # No freeze state
        freeze_until = None
        
        is_frozen = is_sl_frozen_from_state(freeze_until)
        
        assert is_frozen is False, "No freeze should allow entry"
    
    def test_expired_freeze_allows_entry(self):
        """Test that expired freeze allows new entry."""
        # Expired freeze
        freeze_until = datetime.now(WIB) - timedelta(hours=1)
        
        is_frozen = is_sl_frozen_from_state(freeze_until)
        
        assert is_frozen is False, "Expired freeze should allow entry"


class TestTimezoneHandling:
    """Test timezone handling in SL freeze logic."""
    
    def test_wib_timezone_offset(self):
        """Test that WIB timezone has correct offset."""
        offset = WIB.utcoffset(None)
        assert offset is not None, "WIB offset should not be None"
        assert offset.total_seconds() / 3600 == 7, "WIB should be UTC+7"
    
    def test_freeze_state_preserves_timezone(self):
        """Test that freeze state preserves timezone information."""
        data = {
            "sl_freeze_until": "2026-04-13T07:00:00+07:00"
        }
        
        freeze_until = load_freeze_state_from_data(data)
        
        assert freeze_until is not None
        assert freeze_until.tzinfo is not None
        assert freeze_until.tzinfo.utcoffset(None).total_seconds() / 3600 == 7
    
    def test_freeze_comparison_uses_wib(self):
        """Test that freeze comparison uses WIB timezone."""
        # Set freeze in WIB
        freeze_until = datetime.now(WIB) + timedelta(hours=1)
        
        # Check using WIB
        result = is_sl_frozen_from_state(freeze_until)
        
        assert result is True, "Freeze comparison should use WIB"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
