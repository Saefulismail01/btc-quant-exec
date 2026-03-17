"""
Tests for OnChainGateway — TASK-9.
All tests mock network calls (offline-safe).
"""

import asyncio
import time
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.adapters.gateways.onchain_gateway import OnChainGateway, _classify_flow


# ── Helpers ────────────────────────────────────────────────────────────────────

def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ── Unit tests for _classify_flow ──────────────────────────────────────────────

class TestClassifyFlow:

    def test_large_inflow(self):
        label, mag = _classify_flow(1500.0)
        assert label == 'Large Inflow'
        assert mag == 'large'

    def test_small_inflow(self):
        label, mag = _classify_flow(500.0)
        assert label == 'Small Inflow'
        assert mag == 'small'

    def test_neutral(self):
        label, mag = _classify_flow(0.0)
        assert label == 'Neutral'
        assert mag == 'normal'

    def test_small_outflow(self):
        label, mag = _classify_flow(-500.0)
        assert label == 'Small Outflow'
        assert mag == 'small'

    def test_large_outflow(self):
        label, mag = _classify_flow(-1500.0)
        assert label == 'Large Outflow'
        assert mag == 'large'

    def test_boundary_exactly_1000(self):
        label, _ = _classify_flow(1000.0)
        assert label == 'Small Inflow'  # > 200 but not > 1000

    def test_boundary_exactly_200(self):
        label, _ = _classify_flow(200.0)
        assert label == 'Neutral'  # not > 200


# ── Integration tests for OnChainGateway ──────────────────────────────────────

class TestOnChainGateway:

    def test_no_api_key_returns_defaults(self):
        """No CRYPTOQUANT_API_KEY → returns Neutral defaults immediately."""
        gw = OnChainGateway()
        gw._api_key = ''  # force no key

        result = run(gw.fetch_exchange_netflow())
        assert result['flow_label'] == 'Neutral'
        assert result['netflow_btc'] == 0.0
        assert result['source'] == 'fallback'

    def test_api_key_success_parses_csv(self):
        """Valid API key + successful response → parse netflow."""
        gw = OnChainGateway()
        gw._api_key = 'test_key_123'

        csv_response = "date,netflow\n2026-03-17T00:00:00,1250.5"

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = csv_response

        async def _mock_get(*args, **kwargs):
            return mock_resp

        async def _run():
            with patch('httpx.AsyncClient') as mock_client_cls:
                mock_client = MagicMock()
                mock_client.get = AsyncMock(return_value=mock_resp)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_cls.return_value = mock_client
                return await gw.fetch_exchange_netflow(current_price=70000.0)

        result = run(_run())
        assert result['netflow_btc'] == 1250.5
        assert result['flow_label'] == 'Large Inflow'
        assert result['netflow_usd'] == pytest.approx(1250.5 * 70000.0)
        assert result['source'] == 'cryptoquant'

    def test_rate_limit_returns_defaults(self):
        """429 rate limit response → returns Neutral defaults."""
        gw = OnChainGateway()
        gw._api_key = 'test_key'

        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.text = ''

        async def _run():
            with patch('httpx.AsyncClient') as mock_client_cls:
                mock_client = MagicMock()
                mock_client.get = AsyncMock(return_value=mock_resp)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_cls.return_value = mock_client
                return await gw.fetch_exchange_netflow()

        result = run(_run())
        assert result['flow_label'] == 'Neutral'
        assert result['source'] == 'fallback'

    def test_cache_returns_cached_on_second_call(self):
        """Second call within TTL returns cached result."""
        gw = OnChainGateway()
        gw._api_key = 'test_key'

        csv_response = "date,netflow\n2026-03-17T00:00:00,500.0"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = csv_response

        call_count = {'n': 0}

        async def _run():
            with patch('httpx.AsyncClient') as mock_client_cls:
                mock_client = MagicMock()

                async def _mock_get(*args, **kwargs):
                    call_count['n'] += 1
                    return mock_resp

                mock_client.get = _mock_get
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_cls.return_value = mock_client

                r1 = await gw.fetch_exchange_netflow()
                r2 = await gw.fetch_exchange_netflow()
                return r1, r2, call_count['n']

        r1, r2, n = run(_run())
        assert r1 == r2
        assert n == 1  # Only fetched once

    def test_exception_during_fetch_returns_defaults(self):
        """Exception in HTTP call → returns Neutral defaults (never crash)."""
        gw = OnChainGateway()
        gw._api_key = 'test_key'

        async def _run():
            with patch('httpx.AsyncClient') as mock_client_cls:
                mock_client = MagicMock()
                mock_client.get = AsyncMock(side_effect=Exception("Network error"))
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_cls.return_value = mock_client
                return await gw.fetch_exchange_netflow()

        result = run(_run())
        assert result['flow_label'] == 'Neutral'
        assert result['source'] == 'fallback'
