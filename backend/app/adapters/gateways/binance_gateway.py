import asyncio
import os
import ccxt.async_support as ccxt_async
import aiohttp
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

# Load .env (ensure the relative path points to the root)
load_dotenv(Path(__file__).resolve().parent.parent.parent.parent / ".env")

class BinanceGateway:
    """
    Adapter Gateway untuk Binance via CCXT.
    Mengambil data publik dari bursa (OHLCV, Metrics, Microstructure).
    """

    def __init__(self, symbol="BTC/USDT", timeframe="4h"):
        self.symbol = symbol
        self.perp_symbol = f"{symbol}:USDT"
        self.timeframe = timeframe
        self.limit = 500
        
        # Proxy config
        http_proxy = os.getenv("HTTP_PROXY", "").strip()
        https_proxy = os.getenv("HTTPS_PROXY", "").strip()
        proxy_config = {}
        if http_proxy or https_proxy:
            proxy_config["proxies"] = {"http": http_proxy or https_proxy, "https": https_proxy or http_proxy}
            proxy_config["aiohttp_proxy"] = https_proxy or http_proxy

        self.exchange = ccxt_async.binance({
            "enableRateLimit": True,
            "options": {"defaultType": "future"},
            "headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            },
            **proxy_config,
        })
        self.exchange.timeout = 20000  # 20 seconds

        # Force aiohttp to use ThreadedResolver (Python's getaddrinfo) instead
        # of aiodns/c-ares which fails to resolve DNS inside Docker containers.
        connector = aiohttp.TCPConnector(resolver=aiohttp.ThreadedResolver(), ssl=False)
        self.exchange.session = aiohttp.ClientSession(
            connector=connector,
            trust_env=True,
        )

    async def close(self):
        await self.exchange.close()

    async def fetch_live_price(self) -> float:
        """Fetch current BTC/USDT perpetual futures price via httpx."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    "https://fapi.binance.com/fapi/v1/ticker/price",
                    params={"symbol": "BTCUSDT"}
                )
                if resp.status_code == 200:
                    return float(resp.json()["price"])
        except Exception as e:
            print(f"  [Gateway] Live Price Error: {type(e).__name__}: {str(e)}")
        return 0.0

    async def fetch_historical_4h(self) -> pd.DataFrame:
        try:
            if hasattr(self.exchange, 'fapiPublicGetKlines'):
                klines = await self.exchange.fapiPublicGetKlines({
                    'symbol': self.symbol.replace("/", ""),
                    'interval': self.timeframe,
                    'limit': self.limit
                })
                data = []
                for k in klines:
                    total_vol = float(k[5])
                    taker_buy_vol = float(k[9])
                    cvd = 2 * taker_buy_vol - total_vol
                    data.append([int(k[0]), float(k[1]), float(k[2]), float(k[3]), float(k[4]), total_vol, cvd])
                df = pd.DataFrame(data, columns=["timestamp", "open", "high", "low", "close", "volume", "cvd"])
            else:
                ohlcv = await self.exchange.fetch_ohlcv(self.symbol, self.timeframe, limit=self.limit)
                df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
                df["cvd"] = 0.0
            return df
        except Exception as e:
            print(f"  [Gateway] OHLCV Error: {self.symbol} - {type(e).__name__}: {str(e)}")
            return pd.DataFrame()

    async def fetch_market_metrics(self) -> dict:
        result = {"funding_rate": 0.0, "open_interest": 0.0}
        try:
            funding_data = await self.exchange.fetch_funding_rate(self.perp_symbol)
            result["funding_rate"] = funding_data.get("fundingRate", 0.0) or 0.0
            try:
                oi_data = await self.exchange.fetch_open_interest(self.perp_symbol)
                result["open_interest"] = float(oi_data.get("openInterestAmount", 0.0) or 0.0)
            except: pass
        except Exception as e:
            print(f"  [Gateway] Market Metrics Error: {type(e).__name__}: {str(e)}")
        return result

    async def fetch_order_book_imbalance(self) -> float:
        try:
            order_book = await self.exchange.fetch_order_book(symbol=self.symbol, limit=10)
            total_bid_vol = sum(bid[1] for bid in order_book.get("bids", []))
            total_ask_vol = sum(ask[1] for ask in order_book.get("asks", []))
            total = total_bid_vol + total_ask_vol
            return (total_bid_vol - total_ask_vol) / total if total > 0 else 0.0
        except: return 0.0

    async def fetch_microstructure_data(self) -> dict:
        res = {"cvd": 0.0, "liq_buy": 0.0, "liq_sell": 0.0}
        try:
            if hasattr(self.exchange, 'fapiPublicGetKlines'):
                klines = await self.exchange.fapiPublicGetKlines({
                    'symbol': self.symbol.replace("/", ""), 'interval': '4h', 'limit': 1
                })
                if klines:
                    k = klines[-1]
                    res["cvd"] = float(k[9]) - (float(k[5]) - float(k[9]))
            try:
                liqs = await self.exchange.fetch_liquidations(self.perp_symbol, limit=100)
                for l in liqs:
                    if l["side"] == "buy": res["liq_buy"] += l.get("amount", 0.0) * l.get("price", 0.0)
                    else: res["liq_sell"] += l.get("amount", 0.0) * l.get("price", 0.0)
            except: pass
        except Exception as e:
            print(f"  [Gateway] Microstructure Error: {type(e).__name__}: {str(e)}")
        return res

    async def fetch_fgi(self) -> float:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get("https://api.alternative.me/fng/")
                if resp.status_code == 200:
                    return float(resp.json()['data'][0]['value'])
        except: pass
        return 50.0
