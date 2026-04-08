"""
Tests untuk bugfix PnL calculation (08 April 2026).

Bug 1: fetch_entry_fill_quote tidak filter by order_id
        → bisa salah capture fill dari signal lain yang overlap

Bug 2: SL/TP trigger orders punya filled_quote=0
        → fallback ke _calculate_pnl dengan fee rate salah (0.02% vs ~0.2%)
        → Fix: Branch 2 hitung exit_quote dari entry_base × exit_price
"""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from types import SimpleNamespace


# ─── Helpers ────────────────────────────────────────────────────────────────

def make_gateway():
    with patch.dict(os.environ, {
        "LIGHTER_EXECUTION_MODE": "mainnet",
        "LIGHTER_TRADING_ENABLED": "false",
        "LIGHTER_MAINNET_API_KEY": "test_key",
        "LIGHTER_MAINNET_API_SECRET": "test_secret",
        "LIGHTER_API_KEY_INDEX": "3",
        "LIGHTER_ACCOUNT_INDEX": "3",
    }, clear=False):
        from app.adapters.gateways.lighter_execution_gateway import LighterExecutionGateway
        return LighterExecutionGateway()


def make_db_trade(**kwargs):
    defaults = dict(
        id=1,
        side="LONG",
        entry_price=68845.1,
        size_usdt=495.0,
        leverage=15,
        sl_price=67656.0,
        tp_price=69336.0,
        entry_filled_quote=494.996269,
        timestamp_open=1000000,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


# ─── fetch_entry_fill_quote: filter by order_id ──────────────────────────────

class TestFetchEntryFillQuote:

    @pytest.mark.asyncio
    async def test_returns_fill_for_correct_order_id(self):
        """Harus return filled_quote dari order yang order_id-nya cocok."""
        gw = make_gateway()
        gw._make_request = AsyncMock(return_value={
            "orders": [
                {
                    "order_id": "order_ABC",
                    "type": "market",
                    "status": "filled",
                    "filled_quote_amount": "494.996269",
                    "filled_base_amount": "0.007190",
                },
            ]
        })

        result = await gw.fetch_entry_fill_quote("order_ABC")
        assert result == pytest.approx(494.996269, rel=1e-5)

    @pytest.mark.asyncio
    async def test_ignores_different_order_id(self):
        """Tidak boleh return fill dari order lain meski type dan status cocok."""
        gw = make_gateway()
        gw._make_request = AsyncMock(return_value={
            "orders": [
                {
                    "order_id": "order_OTHER",   # order dari signal lain (overlap)
                    "type": "market",
                    "status": "filled",
                    "filled_quote_amount": "257.920498",
                    "filled_base_amount": "0.003740",
                },
                {
                    "order_id": "order_TARGET",
                    "type": "market",
                    "status": "filled",
                    "filled_quote_amount": "494.996269",
                    "filled_base_amount": "0.007190",
                },
            ]
        })

        result = await gw.fetch_entry_fill_quote("order_TARGET")
        assert result == pytest.approx(494.996269, rel=1e-5)

    @pytest.mark.asyncio
    async def test_returns_none_when_order_id_not_found(self):
        """Return None jika order_id tidak ada di response."""
        gw = make_gateway()
        gw._make_request = AsyncMock(return_value={
            "orders": [
                {
                    "order_id": "order_OTHER",
                    "type": "market",
                    "status": "filled",
                    "filled_quote_amount": "494.99",
                    "filled_base_amount": "0.00719",
                },
            ]
        })

        result = await gw.fetch_entry_fill_quote("order_MISSING")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_fill_amounts_zero(self):
        """Return None jika order ditemukan tapi fill amounts = 0."""
        gw = make_gateway()
        gw._make_request = AsyncMock(return_value={
            "orders": [
                {
                    "order_id": "order_XYZ",
                    "type": "market",
                    "status": "filled",
                    "filled_quote_amount": "0",
                    "filled_base_amount": "0",
                },
            ]
        })

        result = await gw.fetch_entry_fill_quote("order_XYZ")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_api_exception(self):
        """Return None jika API call gagal, tidak raise exception."""
        gw = make_gateway()
        gw._make_request = AsyncMock(side_effect=Exception("network error"))

        result = await gw.fetch_entry_fill_quote("order_XYZ")
        assert result is None


# ─── PnL Branch selection via sync_position_status ───────────────────────────

class TestPnlBranchSelection:
    """
    Test bahwa sync_position_status memilih branch yang benar dan menghasilkan
    PnL yang sesuai dengan ground truth Lighter CSV export.

    Semua test memanggil kode asli di position_manager.py, bukan formula ulang.
    """

    def _make_pm(self):
        from app.use_cases.position_manager import PositionManager
        pm = PositionManager.__new__(PositionManager)
        pm.gateway = MagicMock()
        pm.repo = MagicMock()
        pm.risk_manager = None
        pm.notifier = AsyncMock()
        pm.shadow_monitor = MagicMock()
        pm._sl_freeze_until = None
        return pm

    def _make_last_order(self, filled_price, filled_quote=0, filled_base=0, order_type="stop_loss"):
        return {
            "order_id": "order_exit_001",
            "filled_price": filled_price,
            "filled_quote": filled_quote,
            "filled_base": filled_base,
            "order_type": order_type,
            "status": "filled",
            "timestamp": 9999999,
        }

    @pytest.mark.asyncio
    async def test_branch1_both_fills_available(self):
        """
        Branch 1: exit_filled_quote tersedia (market exit).
        PnL = exit_filled_quote - entry_filled_quote langsung.
        Ground truth: trade 4/7 Lighter = +$0.121511
        """
        pm = self._make_pm()
        db_trade = make_db_trade(
            side="LONG",
            entry_price=68845.1,
            entry_filled_quote=494.996269,
            size_usdt=495.0,
        )
        pm.repo.get_open_trade.return_value = db_trade
        pm.gateway.get_open_position = AsyncMock(return_value=None)  # posisi sudah closed
        pm.gateway.fetch_last_closed_order = AsyncMock(return_value=self._make_last_order(
            filled_price=68862.0,
            filled_quote=495.117780,  # exit_filled_quote tersedia
            filled_base=0.007190,
            order_type="stop_loss",
        ))

        captured = {}
        def capture_update(trade_id, exit_price, exit_type, pnl_usdt, pnl_pct):
            captured["pnl_usdt"] = pnl_usdt
        pm.repo.update_trade_on_close.side_effect = capture_update

        await pm.sync_position_status()

        # Branch 1: 495.117780 - 494.996269 = +0.121511
        assert captured["pnl_usdt"] == pytest.approx(0.121511, abs=0.01)

    @pytest.mark.asyncio
    async def test_branch2_sl_trigger_no_exit_fill(self):
        """
        Branch 2: SL trigger order, exit_filled_quote = 0.
        PnL dihitung dari entry_base × exit_price.
        Ground truth: trade 4/7 Lighter = +$0.121511
        """
        pm = self._make_pm()
        db_trade = make_db_trade(
            side="LONG",
            entry_price=68845.1,
            entry_filled_quote=494.996269,
            size_usdt=495.0,
        )
        pm.repo.get_open_trade.return_value = db_trade
        pm.gateway.get_open_position = AsyncMock(return_value=None)
        pm.gateway.fetch_last_closed_order = AsyncMock(return_value=self._make_last_order(
            filled_price=68862.0,
            filled_quote=0,    # SL trigger: tidak ada fill amount
            filled_base=0,
            order_type="stop_loss",
        ))

        captured = {}
        def capture_update(trade_id, exit_price, exit_type, pnl_usdt, pnl_pct):
            captured["pnl_usdt"] = pnl_usdt
        pm.repo.update_trade_on_close.side_effect = capture_update

        await pm.sync_position_status()

        # Branch 2: entry_base=494.996269/68845.1=0.007190, exit=0.007190×68862=495.117
        # PnL = 495.117 - 494.996 = +0.121
        assert captured["pnl_usdt"] == pytest.approx(0.121511, abs=0.01)

    @pytest.mark.asyncio
    async def test_branch2_sl_loss(self):
        """
        Branch 2: SL loss. Ground truth trade 4/5 Lighter = -$2.992
        """
        pm = self._make_pm()
        db_trade = make_db_trade(
            side="LONG",
            entry_price=67249.0,
            entry_filled_quote=494.952640,
            size_usdt=495.0,
        )
        pm.repo.get_open_trade.return_value = db_trade
        pm.gateway.get_open_position = AsyncMock(return_value=None)
        pm.gateway.fetch_last_closed_order = AsyncMock(return_value=self._make_last_order(
            filled_price=66842.5,
            filled_quote=0,
            filled_base=0,
            order_type="stop_loss",
        ))

        captured = {}
        def capture_update(trade_id, exit_price, exit_type, pnl_usdt, pnl_pct):
            captured["pnl_usdt"] = pnl_usdt
        pm.repo.update_trade_on_close.side_effect = capture_update

        await pm.sync_position_status()

        assert captured["pnl_usdt"] == pytest.approx(-2.992, abs=0.05)

    @pytest.mark.asyncio
    async def test_branch2_breakeven_does_not_trigger_sl_freeze(self):
        """
        SL hit di breakeven (PnL >= 0) — SL freeze tidak boleh aktif.
        Bug lama: freeze aktif di semua SL exit tanpa cek PnL.
        """
        pm = self._make_pm()
        pm._set_sl_freeze = MagicMock()
        pm._clear_sl_freeze = MagicMock()
        db_trade = make_db_trade(
            side="LONG",
            entry_price=68845.1,
            entry_filled_quote=494.996269,
            size_usdt=495.0,
        )
        pm.repo.get_open_trade.return_value = db_trade
        pm.gateway.get_open_position = AsyncMock(return_value=None)
        pm.gateway.fetch_last_closed_order = AsyncMock(return_value=self._make_last_order(
            filled_price=68862.0,
            filled_quote=0,
            filled_base=0,
            order_type="stop_loss",
        ))
        pm.repo.update_trade_on_close.return_value = None

        await pm.sync_position_status()

        pm._set_sl_freeze.assert_not_called()

    @pytest.mark.asyncio
    async def test_branch2_real_loss_triggers_sl_freeze(self):
        """
        SL hit dengan loss nyata — SL freeze harus aktif.
        """
        pm = self._make_pm()
        pm._set_sl_freeze = MagicMock()
        pm._clear_sl_freeze = MagicMock()
        db_trade = make_db_trade(
            side="LONG",
            entry_price=67249.0,
            entry_filled_quote=494.952640,
            size_usdt=495.0,
        )
        pm.repo.get_open_trade.return_value = db_trade
        pm.gateway.get_open_position = AsyncMock(return_value=None)
        pm.gateway.fetch_last_closed_order = AsyncMock(return_value=self._make_last_order(
            filled_price=66842.5,
            filled_quote=0,
            filled_base=0,
            order_type="stop_loss",
        ))
        pm.repo.update_trade_on_close.return_value = None

        await pm.sync_position_status()

        pm._set_sl_freeze.assert_called_once()

    @pytest.mark.asyncio
    async def test_branch3_fallback_no_entry_fill(self):
        """
        Branch 3: entry_filled_quote tidak ada → fallback _calculate_pnl.
        Pastikan tidak crash dan masih menghasilkan nilai numerik.
        """
        pm = self._make_pm()
        db_trade = make_db_trade(
            side="LONG",
            entry_price=68845.1,
            entry_filled_quote=None,  # tidak ter-capture saat entry
            size_usdt=495.0,
            leverage=15,
        )
        pm.repo.get_open_trade.return_value = db_trade
        pm.gateway.get_open_position = AsyncMock(return_value=None)
        pm.gateway.fetch_last_closed_order = AsyncMock(return_value=self._make_last_order(
            filled_price=68862.0,
            filled_quote=0,
            filled_base=0,
            order_type="stop_loss",
        ))

        captured = {}
        def capture_update(trade_id, exit_price, exit_type, pnl_usdt, pnl_pct):
            captured["pnl_usdt"] = pnl_usdt
        pm.repo.update_trade_on_close.side_effect = capture_update

        await pm.sync_position_status()

        # Branch 3 dipakai — hasilnya numerik (formula lokal, bukan crash)
        assert "pnl_usdt" in captured
        assert isinstance(captured["pnl_usdt"], float)
