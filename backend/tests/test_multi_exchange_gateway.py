"""
Tests for MultiExchangeFundingGateway — TASK-7.
All tests mock network calls (offline-safe).
"""

import asyncio
import time
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.adapters.gateways.multi_exchange_gateway import MultiExchangeFundingGateway


# ── Helpers ────────────────────────────────────────────────────────────────────

def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestMultiExchangeFundingGateway:

    def test_average_three_values(self):
        """Three valid rates → correct average."""
        gw = MultiExchangeFundingGateway()

        async def _run():
            with patch.object(gw, '_fetch_binance_funding', new=AsyncMock(return_value=0.0001)):
                with patch.object(gw, '_fetch_bybit_funding', new=AsyncMock(return_value=0.0002)):
                    with patch.object(gw, '_fetch_okx_funding', new=AsyncMock(return_value=0.0003)):
                        return await gw.fetch_cross_funding()

        result = run(_run())
        assert abs(result['avg_funding'] - 0.0002) < 1e-9
        assert result['binance_funding'] == 0.0001
        assert result['bybit_funding']   == 0.0002
        assert result['okx_funding']     == 0.0003

    def test_consensus_all_positive(self):
        """All rates > 0 → ALL_POSITIVE."""
        gw = MultiExchangeFundingGateway()

        async def _run():
            with patch.object(gw, '_fetch_binance_funding', new=AsyncMock(return_value=0.0001)):
                with patch.object(gw, '_fetch_bybit_funding', new=AsyncMock(return_value=0.0002)):
                    with patch.object(gw, '_fetch_okx_funding', new=AsyncMock(return_value=0.0003)):
                        return await gw.fetch_cross_funding()

        result = run(_run())
        assert result['funding_consensus'] == 'ALL_POSITIVE'

    def test_consensus_all_negative(self):
        """All rates < 0 → ALL_NEGATIVE."""
        gw = MultiExchangeFundingGateway()

        async def _run():
            with patch.object(gw, '_fetch_binance_funding', new=AsyncMock(return_value=-0.0001)):
                with patch.object(gw, '_fetch_bybit_funding', new=AsyncMock(return_value=-0.0002)):
                    with patch.object(gw, '_fetch_okx_funding', new=AsyncMock(return_value=-0.0003)):
                        return await gw.fetch_cross_funding()

        result = run(_run())
        assert result['funding_consensus'] == 'ALL_NEGATIVE'

    def test_consensus_mixed(self):
        """Mixed sign rates → MIXED."""
        gw = MultiExchangeFundingGateway()

        async def _run():
            with patch.object(gw, '_fetch_binance_funding', new=AsyncMock(return_value=0.0001)):
                with patch.object(gw, '_fetch_bybit_funding', new=AsyncMock(return_value=-0.0001)):
                    with patch.object(gw, '_fetch_okx_funding', new=AsyncMock(return_value=0.0002)):
                        return await gw.fetch_cross_funding()

        result = run(_run())
        assert result['funding_consensus'] == 'MIXED'

    def test_one_exchange_failure_averages_remaining(self):
        """One exchange returns None → average from the other two."""
        gw = MultiExchangeFundingGateway()

        async def _run():
            with patch.object(gw, '_fetch_binance_funding', new=AsyncMock(return_value=0.0001)):
                with patch.object(gw, '_fetch_bybit_funding', new=AsyncMock(return_value=None)):
                    with patch.object(gw, '_fetch_okx_funding', new=AsyncMock(return_value=0.0003)):
                        return await gw.fetch_cross_funding()

        result = run(_run())
        expected_avg = (0.0001 + 0.0003) / 2
        assert abs(result['avg_funding'] - expected_avg) < 1e-9
        assert result['bybit_funding'] == 0.0  # None → 0.0 in output

    def test_all_exchanges_fail_returns_defaults(self):
        """All exchanges fail → default zeros."""
        gw = MultiExchangeFundingGateway()

        async def _run():
            with patch.object(gw, '_fetch_binance_funding', new=AsyncMock(return_value=None)):
                with patch.object(gw, '_fetch_bybit_funding', new=AsyncMock(return_value=None)):
                    with patch.object(gw, '_fetch_okx_funding', new=AsyncMock(return_value=None)):
                        return await gw.fetch_cross_funding()

        result = run(_run())
        assert result['avg_funding'] == 0.0
        assert result['funding_consensus'] == 'MIXED'

    def test_cache_ttl_returns_cached_result(self):
        """Second call within TTL returns cached result without re-fetching."""
        gw = MultiExchangeFundingGateway()
        call_count = {'n': 0}

        async def _mock_binance():
            call_count['n'] += 1
            return 0.0001

        async def _run():
            with patch.object(gw, '_fetch_binance_funding', new=_mock_binance):
                with patch.object(gw, '_fetch_bybit_funding', new=AsyncMock(return_value=0.0002)):
                    with patch.object(gw, '_fetch_okx_funding', new=AsyncMock(return_value=0.0003)):
                        r1 = await gw.fetch_cross_funding()
                        r2 = await gw.fetch_cross_funding()
                        return r1, r2, call_count['n']

        r1, r2, n = run(_run())
        assert r1 == r2
        assert n == 1  # Only fetched once — second call used cache

    def test_cache_expires_after_ttl(self):
        """Cache expired → re-fetches."""
        gw = MultiExchangeFundingGateway()
        gw._cache_ttl = 0.01  # 10ms for test speed

        async def _run():
            with patch.object(gw, '_fetch_binance_funding', new=AsyncMock(return_value=0.0001)):
                with patch.object(gw, '_fetch_bybit_funding', new=AsyncMock(return_value=0.0002)):
                    with patch.object(gw, '_fetch_okx_funding', new=AsyncMock(return_value=0.0003)):
                        r1 = await gw.fetch_cross_funding()
            await asyncio.sleep(0.05)
            with patch.object(gw, '_fetch_binance_funding', new=AsyncMock(return_value=0.0005)):
                with patch.object(gw, '_fetch_bybit_funding', new=AsyncMock(return_value=0.0005)):
                    with patch.object(gw, '_fetch_okx_funding', new=AsyncMock(return_value=0.0005)):
                        r2 = await gw.fetch_cross_funding()
            return r1, r2

        r1, r2 = run(_run())
        assert r1['avg_funding'] != r2['avg_funding']

    def test_max_spread_computed(self):
        """max_spread = max(rates) - min(rates)."""
        gw = MultiExchangeFundingGateway()

        async def _run():
            with patch.object(gw, '_fetch_binance_funding', new=AsyncMock(return_value=0.0001)):
                with patch.object(gw, '_fetch_bybit_funding', new=AsyncMock(return_value=0.0005)):
                    with patch.object(gw, '_fetch_okx_funding', new=AsyncMock(return_value=0.0003)):
                        return await gw.fetch_cross_funding()

        result = run(_run())
        assert abs(result['max_spread'] - 0.0004) < 1e-9
