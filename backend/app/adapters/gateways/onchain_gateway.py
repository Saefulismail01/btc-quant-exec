"""
OnChainGateway — fetches BTC exchange netflow from CryptoQuant.
TASK-9: Exchange Net Flow (whale activity indicator).
Cache: 4 hours aggressive (only 10 req/day on free tier).
"""

import os
import time
from datetime import datetime, timezone, timedelta
from typing import Optional


_FLOW_THRESHOLDS = [
    (1000.0,  "Large Inflow"),
    (200.0,   "Small Inflow"),
    (-200.0,  "Neutral"),
    (-1000.0, "Small Outflow"),
]


def _classify_flow(netflow_btc: float) -> tuple[str, str]:
    """Returns (flow_label, flow_magnitude)."""
    if netflow_btc > 1000.0:
        return "Large Inflow", "large"
    if netflow_btc > 200.0:
        return "Small Inflow", "small"
    if netflow_btc < -1000.0:
        return "Large Outflow", "large"
    if netflow_btc < -200.0:
        return "Small Outflow", "small"
    return "Neutral", "normal"


class OnChainGateway:
    """Fetches BTC exchange netflow from CryptoQuant with aggressive 4H caching."""

    def __init__(self):
        self._cache: Optional[dict] = None
        self._cache_time: float = 0.0
        self._cache_ttl: float = 14400.0  # 4 hours
        self._api_key: str = os.getenv("CRYPTOQUANT_API_KEY", "")

    async def fetch_exchange_netflow(self, current_price: float = 0.0) -> dict:
        """
        Fetch BTC exchange netflow from CryptoQuant.
        Falls back to Neutral defaults if no API key or on error.
        """
        _default = {
            "netflow_btc": 0.0,
            "netflow_usd": 0.0,
            "flow_label": "Neutral",
            "flow_magnitude": "normal",
            "source": "fallback",
        }

        # Check cache
        if self._cache is not None and (time.time() - self._cache_time) < self._cache_ttl:
            return self._cache

        # No API key → return default immediately (no request)
        if not self._api_key:
            return _default

        try:
            import httpx

            # CryptoQuant: fetch last 4H window
            now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            from_ms = now_ms - (4 * 60 * 60 * 1000)  # 4 hours ago

            url = "https://api.cryptoquant.com/live/v1/charts/37/csv"
            params = {
                "window": "HOUR_4",
                "from": str(from_ms),
                "limit": 1,
            }
            headers = {"Authorization": f"Bearer {self._api_key}"}

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, params=params, headers=headers)

            if resp.status_code == 200:
                lines = resp.text.strip().splitlines()
                # CSV: skip header, parse last row
                data_lines = [l for l in lines if l and not l.startswith("#") and not l.lower().startswith("date")]
                if data_lines:
                    last = data_lines[-1].split(",")
                    # CryptoQuant netflow CSV columns: date, all_exchanges_netflow
                    if len(last) >= 2:
                        netflow_btc = float(last[-1].strip())
                        netflow_usd = netflow_btc * current_price if current_price > 0 else 0.0
                        flow_label, flow_magnitude = _classify_flow(netflow_btc)
                        result = {
                            "netflow_btc":    netflow_btc,
                            "netflow_usd":    netflow_usd,
                            "flow_label":     flow_label,
                            "flow_magnitude": flow_magnitude,
                            "source":         "cryptoquant",
                        }
                        self._cache = result
                        self._cache_time = time.time()
                        return result

            elif resp.status_code in (429, 403):
                print(f"  [OnChainGateway] Rate limited or forbidden (status {resp.status_code}). Using defaults.")

        except Exception as e:
            print(f"  [OnChainGateway] fetch_exchange_netflow error: {type(e).__name__}: {e}")

        return _default
