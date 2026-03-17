"""
MultiExchangeFundingGateway — fetches BTC funding rates from Binance, Bybit, OKX in parallel.
TASK-7: Cross-Exchange Funding Rate consensus.
"""

import asyncio
import time
import httpx
from typing import Optional


class MultiExchangeFundingGateway:
    """Fetches funding rates from 3 exchanges in parallel, returns consensus metrics."""

    def __init__(self):
        self._cache: Optional[dict] = None
        self._cache_time: float = 0.0
        self._cache_ttl: float = 300.0  # 5 minutes

    async def _fetch_binance_funding(self) -> Optional[float]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    "https://fapi.binance.com/fapi/v1/fundingRate",
                    params={"symbol": "BTCUSDT", "limit": 1}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data and len(data) > 0:
                        return float(data[0].get("fundingRate", 0.0))
        except Exception as e:
            print(f"  [MultiExchangeGateway] Binance funding error: {type(e).__name__}: {e}")
        return None

    async def _fetch_bybit_funding(self) -> Optional[float]:
        try:
            import ccxt.async_support as ccxt_async
            exchange = ccxt_async.bybit({"enableRateLimit": True})
            try:
                data = await asyncio.wait_for(
                    exchange.fetch_funding_rate("BTC/USDT:USDT"),
                    timeout=5.0
                )
                rate = data.get("fundingRate", None)
                return float(rate) if rate is not None else None
            finally:
                await exchange.close()
        except Exception as e:
            print(f"  [MultiExchangeGateway] Bybit funding error: {type(e).__name__}: {e}")
        return None

    async def _fetch_okx_funding(self) -> Optional[float]:
        try:
            import ccxt.async_support as ccxt_async
            exchange = ccxt_async.okx({"enableRateLimit": True})
            try:
                data = await asyncio.wait_for(
                    exchange.fetch_funding_rate("BTC/USDT:USDT"),
                    timeout=5.0
                )
                rate = data.get("fundingRate", None)
                return float(rate) if rate is not None else None
            finally:
                await exchange.close()
        except Exception as e:
            print(f"  [MultiExchangeGateway] OKX funding error: {type(e).__name__}: {e}")
        return None

    def _compute_consensus(self, rates: list[float]) -> str:
        if not rates:
            return "MIXED"
        if all(r > 0 for r in rates):
            return "ALL_POSITIVE"
        if all(r < 0 for r in rates):
            return "ALL_NEGATIVE"
        return "MIXED"

    async def fetch_cross_funding(self) -> dict:
        """Fetch funding rates from all 3 exchanges in parallel. Returns consensus metrics."""
        # Check cache
        if self._cache is not None and (time.time() - self._cache_time) < self._cache_ttl:
            return self._cache

        _default = {
            "binance_funding": 0.0,
            "bybit_funding": 0.0,
            "okx_funding": 0.0,
            "avg_funding": 0.0,
            "funding_consensus": "MIXED",
            "max_spread": 0.0,
        }

        try:
            results = await asyncio.gather(
                self._fetch_binance_funding(),
                self._fetch_bybit_funding(),
                self._fetch_okx_funding(),
                return_exceptions=True
            )

            binance_rate = results[0] if isinstance(results[0], float) else None
            bybit_rate   = results[1] if isinstance(results[1], float) else None
            okx_rate     = results[2] if isinstance(results[2], float) else None

            available = [r for r in [binance_rate, bybit_rate, okx_rate] if r is not None]
            avg = sum(available) / len(available) if available else 0.0
            consensus = self._compute_consensus(available)
            max_spread = (max(available) - min(available)) if len(available) >= 2 else 0.0

            result = {
                "binance_funding": binance_rate if binance_rate is not None else 0.0,
                "bybit_funding":   bybit_rate   if bybit_rate   is not None else 0.0,
                "okx_funding":     okx_rate     if okx_rate     is not None else 0.0,
                "avg_funding":     avg,
                "funding_consensus": consensus,
                "max_spread": max_spread,
            }

            self._cache = result
            self._cache_time = time.time()
            return result

        except Exception as e:
            print(f"  [MultiExchangeGateway] fetch_cross_funding failed: {type(e).__name__}: {e}")
            return _default
