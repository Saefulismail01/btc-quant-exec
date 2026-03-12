import asyncio
import ccxt.async_support as ccxt_async
import json

async def test_fapi():
    exchange = ccxt_async.binance({'enableRateLimit': True})
    
    # test fetch_ohlcv to see if we can get taker buy volume easily
    # binance specific implicit API: fapiPublicGetKlines
    try:
        if hasattr(exchange, 'fapiPublicGetKlines'):
            res = await exchange.fapiPublicGetKlines({'symbol': 'BTCUSDT', 'interval': '4h', 'limit': 2})
            print(json.dumps(res, indent=2))
        else:
            print("fapiPublicGetKlines not found")
    except Exception as e:
        print(f"Error: {e}")
        
    await exchange.close()

if __name__ == "__main__":
    asyncio.run(test_fapi())
