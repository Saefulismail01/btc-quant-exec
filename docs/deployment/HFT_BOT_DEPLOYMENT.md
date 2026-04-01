# HFT Bot Deployment - Lighter Mainnet

**Status:** ✅ LIVE on VPS
**Date:** 2026-03-15
**Current BTC Price:** $71,490.00

## Overview

Professional autonomous HFT bot deployed on Lighter.xyz mainnet with:
- Real-time BTC price monitoring (2s intervals)
- Technical momentum analysis
- Autonomous LONG/SHORT trade execution
- Atomic entry + SL/TP order placement
- Position tracking and PnL monitoring

## Configuration

```
TRADE_SIZE = 0.00021 BTC per trade
TP_PROFIT = $0.01 USD per trade
SL_LOSS = $0.01 USD per trade
MOMENTUM_WINDOW = 10 candles
PRICE_THRESHOLD = $0.50 minimum move to trigger
MAX_OPEN_TRADES = 1 (safety limit)
POLL_INTERVAL = 2 seconds
MIN_TRADE_INTERVAL = 5 seconds (rate limiting)
```

## Running the Bot

### Option 1: Direct execution on VPS (ACTIVE)

```bash
ssh vps-rumah "cd /home/saeful/vps/projects/btc-quant-lighter"
source /tmp/hft_venv/bin/activate
python -u backend/scripts/hft_bot.py
```

**Current Status:** Bot running with PID 2892756

### Option 2: Systemd service (recommended for production)

```bash
# Copy service file
scp backend/scripts/hft-bot.service vps-rumah:/tmp/

# On VPS:
sudo mv /tmp/hft-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable hft-bot.service
sudo systemctl start hft-bot.service
sudo journalctl -u hft-bot.service -f
```

## Trading Logic

### Entry Conditions

**LONG Trade:**
- Trend detection: `momentum > $0.50` (10-candle average)
- Positive price movement detected
- No open positions active

**SHORT Trade:**
- Trend detection: `momentum < -$0.50` (10-candle average)
- Negative price movement detected
- No open positions active

### Order Execution

1. **Entry** - Market order (BUY/SELL at market)
   - Size: 0.00021 BTC
   - Slippage allowance: ±2%

2. **Stop Loss** - STOP_LOSS_LIMIT order
   - Price: Entry ± ($0.01 / 0.00021) per unit
   - Closes at $0.01 loss if triggered

3. **Take Profit** - TAKE_PROFIT_LIMIT order
   - Price: Entry ± ($0.01 / 0.00021) per unit
   - Closes at $0.01 profit if triggered

## Monitoring

Watch the bot output:
```
[12:51:12] 🚀 HFT Bot started (monitoring BTC 0.00021 BTC trades)
   TP: $0.01, SL: $0.01, Max open: 1
   Poll interval: 2s, Min trade interval: 5s

[12:51:12] BTC $71,520.90
[12:51:14] BTC $71,520.90 | Open: 1 | PnL: $0.0050
[12:51:16] BTC $71,530.40
```

### Key Output Indicators

- **BTC price** - Current market price from Lighter
- **Open** - Number of active positions (0 or 1)
- **PnL** - Realized profit/loss for closed positions
- **NEW TRADE** - Entry with side, price, TP, SL
- **✅ Entry TX / SL TX / TP TX** - Successful order submissions
- **⚠️ warnings** - Order failures that don't stop execution

## Safety Features

1. **Max Open Trades:** Hard limit of 1 position
2. **Rate Limiting:** Minimum 5 seconds between trades
3. **Stop Loss:** Automatic loss limit at -$0.01
4. **Take Profit:** Automatic profit target at +$0.01
5. **Atomic Orders:** SL/TP placed immediately with entry
6. **No Over-trading:** Momentum threshold prevents noise trades

## Risk Management

Per-trade risk:
- **Entry size:** 0.00021 BTC (~$15.50 at $71k)
- **Max loss:** $0.01 USD per trade
- **Max profit:** $0.01 USD per trade
- **Risk/Reward:** 1:1 ratio
- **Equity required:** $15-20 USD per trade

**Total capital efficiency:** ~$0.01-0.02 at risk when positioned

## Previous Trades (Session)

From prior conversation:
1. **SHORT @ $71,611** - Entry + SL/TP placed
   - Status: Awaiting fill (market at $71,490)
   - TP @ $71,563.38 (-$0.01)
   - SL @ $71,801.48 (+$0.04)

## Next Steps

1. Monitor live bot execution for 24-48 hours
2. Log trades to DuckDB for analytics
3. Tune momentum thresholds based on actual fills
4. Add WebSocket support for faster signals
5. Implement circuit breaker at -$0.10 daily loss

## Technical Stack

- **SDK:** lighter-sdk 1.0.6 (Python)
- **Async:** asyncio with aiohttp
- **Market:** Lighter.xyz mainnet (BTC/USD market_id=1)
- **Account:** Index 718591, API Key Index 3
- **Deployment:** VPS (Linux Ubuntu 20.04)

## Troubleshooting

### Bot not trading?
Check momentum threshold (currently $0.50):
```python
# In hft_bot.py:
PRICE_THRESHOLD = 0.50  # Increase sensitivity
```

### Orders failing?
- Verify `LIGHTER_TRADING_ENABLED=false` safety lock
- Check account has sufficient balance
- Ensure nonce is incrementing (SDK handles this)

### Connection issues?
```bash
# Test connection
curl https://mainnet.zklighter.elliot.ai/order_books | jq '.order_books[0]'
```

## Future Enhancements

- [ ] WebSocket streaming instead of polling
- [ ] Multi-position support (grid trading)
- [ ] Dynamic position sizing (risk %)
- [ ] RSI / MACD confirmation signals
- [ ] Database logging for backtesting
- [ ] Telegram notifications for fills
- [ ] Circuit breaker and daily loss limits
- [ ] Manual override via HTTP API
