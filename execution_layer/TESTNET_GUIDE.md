# Binance Testnet Integration Guide

## Quick Start

### 1. Setup Testnet Credentials

Get credentials from: https://testnet.binancefuture.com

```bash
# Edit .env in project root
EXECUTION_MODE=testnet
TRADING_ENABLED=false         # Start with disabled!
BINANCE_TESTNET_API_KEY=your_testnet_key
BINANCE_TESTNET_SECRET=your_testnet_secret
```

### 2. Test Connection

```bash
cd backend
python test_testnet_connection.py
```

Expected output:
```
📡 Connecting to Binance Futures Testnet...
1️⃣  Fetching account balance...
   ✅ Account Balance (USDT):
      Free:  $5,000.00
      Total: $5,000.00
✅ TESTNET CONNECTION SUCCESSFUL
```

### 3. Start API Server

```bash
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Check: http://localhost:8000/docs (Swagger UI)

### 4. Start Live Executor (Read-Only Mode)

```bash
cd backend
python live_executor.py
```

This will run in **read-only mode** because `TRADING_ENABLED=false`.

Output:
```
[LIVE] Mode: TESTNET
[LIVE] Trading: 🔴 DISABLED
[LIVE] Account Balance: $5,000.00 USDT
[LIVE] No existing positions (clean state)
[LIVE] Starting main execution loop...
```

### 5. Enable Trading (Optional)

Only after verifying everything works:

```bash
# Edit .env
TRADING_ENABLED=true
```

Then restart the daemon.

---

## Integration Test Scenarios

### Scenario 1: Signal ACTIVE LONG → TP Hit

**Setup:**
- Daemon running in testnet
- Manual market order for LONG
- TP order pending

**Expected:**
- Position opens with market order
- SL and TP orders placed
- Trade recorded to DB
- Notification sent

**Verify:**
```bash
curl http://localhost:8000/api/execution/status
```

### Scenario 2: Emergency Stop

**Action:**
```bash
curl -X POST http://localhost:8000/api/execution/emergency_stop
```

**Expected:**
- Position closed immediately (if open)
- `trading_halted=true`
- Notification sent

### Scenario 3: Resume Trading

**Action:**
```bash
curl -X POST http://localhost:8000/api/execution/resume \
  -H "Content-Type: application/json" \
  -d '{"confirm": "RESUME_TRADING"}'
```

**Expected:**
- `trading_halted=false`
- Daemon resumes processing signals

---

## Manual Testing: Open/Close Trade

### Open LONG Trade

1. **Get current price:**
   ```bash
   curl https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT
   ```
   Example: `$83,500`

2. **Manually place market order on testnet:**
   - Side: LONG
   - Margin: $1,000 USDT
   - Leverage: 15x
   - Entry: $83,500

3. **Set SL:**
   - Price: $82,386 (1.333% below)
   - Type: STOP_MARKET

4. **Set TP:**
   - Price: $84,093 (0.71% above)
   - Type: TAKE_PROFIT_MARKET

5. **Verify DB:**
   ```bash
   duckdb app/infrastructure/database/btc-quant.db
   > SELECT * FROM live_trades WHERE status='OPEN';
   ```

### Close Trade

- Wait for TP to hit (price reaches $84,093+)
- Or trigger SL manually (price drops to $82,386-)
- Or wait 24 hours for TIME_EXIT

---

## Monitoring

### Check Status
```bash
curl http://localhost:8000/api/execution/status | jq
```

### View Trade History
```bash
duckdb app/infrastructure/database/btc-quant.db
> SELECT id, side, entry_price, exit_price, pnl_usdt, exit_type
  FROM live_trades
  ORDER BY timestamp_open DESC LIMIT 10;
```

### Follow Logs
```bash
tail -f backend/live_executor.log
```

---

## Telegram Notifications

Setup terpisah untuk execution layer (optional):

```bash
# .env — Option 1: Dedicated bot for execution (Recommended)
EXECUTION_TELEGRAM_BOT_TOKEN=your_execution_bot_token
EXECUTION_TELEGRAM_CHAT_ID=your_execution_chat_id

# .env — Option 2: Use existing signal telegram (fallback)
TELEGRAM_BOT_TOKEN=your_signal_bot_token
TELEGRAM_CHAT_ID=your_signal_chat_id
```

**Full setup guide:** `execution_layer/TELEGRAM_SETUP.md`

Restart daemon. Notifications akan muncul untuk:
- Trade opened (dengan conviction level)
- Trade closed (TP/SL/TIME_EXIT)
- Emergency stop
- Errors & warnings

---

## Safety Checks

✅ **Before mainnet:**

- [ ] 48-hour testnet run without crash
- [ ] 10 trades completed successfully
- [ ] All notifications received
- [ ] Emergency stop works instantly (< 10 sec)
- [ ] Daily PnL calculation accurate
- [ ] Risk manager blocking works
- [ ] Balance check passes

---

## Troubleshooting

### "API keys not found"
- Check `.env` file exists in project root
- Verify `BINANCE_TESTNET_API_KEY` and `BINANCE_TESTNET_SECRET` are set
- No spaces around values

### "Connection failed"
- Verify internet connectivity
- Check Binance testnet status: https://testnet.binancefuture.com
- Try proxy settings if behind corporate firewall

### "Trade not opening"
- Check `TRADING_ENABLED=true`
- Verify signal is `ACTIVE` (not `SUSPENDED`)
- Check account balance >= $1,000
- View daemon logs for error details

### "Telegram not sending"
- Verify bot token is valid
- Check chat ID is numeric and correct
- Bot must be admin in the group (if using group chat)
- Test bot: `/start` command in Telegram

---

## Binance Testnet Links

- **Web:** https://testnet.binancefuture.com
- **Documentation:** https://binance-docs.github.io/apidocs/futures/cn_operation/
- **API Status:** Check API docs for endpoint status

---

## Duration Expectations

| Phase | Duration | Notes |
|-------|----------|-------|
| Setup | 15 min | Create testnet account + API keys |
| Connection test | 1 min | Verify credentials work |
| Read-only daemon | 1 hour | Confirm no errors, logs clean |
| First trade | 10-30 min | Manual trade + SL/TP setup |
| 5-10 trades | 2-4 hours | Validate all scenarios |
| 48-hour stability | 48h | Let daemon run unattended |
| **Total** | **2-3 days** | Conservative estimate |

---

**Last updated:** 2026-03-11
**Version:** BTC-QUANT v4.4
