"""
Unit tests for Order ID tracking logic.

Tests the order ID state management without requiring actual Lighter API connection.
"""

import pytest
import json
from pathlib import Path
from typing import Dict
import tempfile


# ── Order ID Tracking Functions (isolated from file I/O for testing) ─────────────

def save_order_ids_to_file(order_ids: Dict, file_path: Path) -> bool:
    """Save order IDs to file."""
    try:
        with open(file_path, "w") as f:
            json.dump(order_ids, f, indent=2)
        return True
    except Exception:
        return False


def load_order_ids_from_file(file_path: Path) -> Dict:
    """Load order IDs from file."""
    try:
        if file_path.exists():
            with open(file_path, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def clear_order_ids_from_file(file_path: Path) -> bool:
    """Clear order IDs file."""
    try:
        if file_path.exists():
            file_path.unlink()
        return True
    except Exception:
        return False


# ── Unit Tests ─────────────────────────────────────────────────────────────

class TestOrderIdTracking:
    """Test order ID tracking logic independently of file system."""
    
    def test_save_and_load_order_ids(self):
        """Test saving and loading order IDs."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_file = Path(f.name)
        
        try:
            order_ids = {
                "entry": "0x123abc",
                "sl": "0x456def",
                "tp": "0x789ghi",
                "timestamp": "2026-04-12T10:00:00Z"
            }
            
            # Save
            assert save_order_ids_to_file(order_ids, temp_file) is True
            assert temp_file.exists()
            
            # Load
            loaded = load_order_ids_from_file(temp_file)
            assert loaded == order_ids
            assert loaded["entry"] == "0x123abc"
            assert loaded["sl"] == "0x456def"
            assert loaded["tp"] == "0x789ghi"
            
        finally:
            if temp_file.exists():
                temp_file.unlink()
    
    def test_load_nonexistent_file(self):
        """Test loading order IDs from nonexistent file."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=True) as f:
            temp_file = Path(f.name)
        
        # File doesn't exist
        assert not temp_file.exists()
        loaded = load_order_ids_from_file(temp_file)
        assert loaded == {}
    
    def test_clear_order_ids(self):
        """Test clearing order IDs."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_file = Path(f.name)
        
        try:
            # Create file
            order_ids = {"entry": "0x123abc"}
            save_order_ids_to_file(order_ids, temp_file)
            assert temp_file.exists()
            
            # Clear
            assert clear_order_ids_from_file(temp_file) is True
            assert not temp_file.exists()
            
            # Load should return empty
            loaded = load_order_ids_from_file(temp_file)
            assert loaded == {}
            
        finally:
            if temp_file.exists():
                temp_file.unlink()
    
    def test_clear_nonexistent_file(self):
        """Test clearing order IDs when file doesn't exist."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=True) as f:
            temp_file = Path(f.name)
        
        # File doesn't exist
        assert not temp_file.exists()
        # Clear should still succeed
        assert clear_order_ids_from_file(temp_file) is True
    
    def test_save_invalid_json(self):
        """Test handling of invalid JSON file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_file = Path(f.name)
        
        try:
            # Write invalid JSON
            with open(temp_file, "w") as f:
                f.write("invalid json content")
            
            # Load should return empty dict on error
            loaded = load_order_ids_from_file(temp_file)
            assert loaded == {}
            
        finally:
            if temp_file.exists():
                temp_file.unlink()
    
    def test_order_ids_structure(self):
        """Test that order IDs have expected structure."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_file = Path(f.name)
        
        try:
            order_ids = {
                "entry": "0x123abc",
                "sl": "0x456def",
                "tp": "0x789ghi",
                "timestamp": "2026-04-12T10:00:00Z"
            }
            
            save_order_ids_to_file(order_ids, temp_file)
            loaded = load_order_ids_from_file(temp_file)
            
            # Check required fields
            assert "entry" in loaded
            assert "sl" in loaded
            assert "tp" in loaded
            assert "timestamp" in loaded
            
            # Check types
            assert isinstance(loaded["entry"], str)
            assert isinstance(loaded["sl"], str)
            assert isinstance(loaded["tp"], str)
            assert isinstance(loaded["timestamp"], str)
            
        finally:
            if temp_file.exists():
                temp_file.unlink()
    
    def test_partial_order_ids(self):
        """Test handling partial order IDs (some fields missing)."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_file = Path(f.name)
        
        try:
            # Only SL and TP, no entry
            order_ids = {
                "sl": "0x456def",
                "tp": "0x789ghi",
                "timestamp": "2026-04-12T10:00:00Z"
            }
            
            save_order_ids_to_file(order_ids, temp_file)
            loaded = load_order_ids_from_file(temp_file)
            
            assert loaded["sl"] == "0x456def"
            assert loaded["tp"] == "0x789ghi"
            assert loaded.get("entry") is None
            
        finally:
            if temp_file.exists():
                temp_file.unlink()
    
    def test_update_order_ids(self):
        """Test updating order IDs (save new values)."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_file = Path(f.name)
        
        try:
            # Initial save
            order_ids = {
                "entry": "0x123abc",
                "sl": "0x456def",
                "tp": "0x789ghi",
                "timestamp": "2026-04-12T10:00:00Z"
            }
            save_order_ids_to_file(order_ids, temp_file)
            
            # Update SL
            order_ids["sl"] = "0xnew_sl_id"
            order_ids["updated_at"] = "2026-04-12T11:00:00Z"
            save_order_ids_to_file(order_ids, temp_file)
            
            # Load and verify
            loaded = load_order_ids_from_file(temp_file)
            assert loaded["sl"] == "0xnew_sl_id"
            assert loaded["entry"] == "0x123abc"  # Unchanged
            assert loaded["updated_at"] == "2026-04-12T11:00:00Z"
            
        finally:
            if temp_file.exists():
                temp_file.unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
