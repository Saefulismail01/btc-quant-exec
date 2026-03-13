# Lighter Execution Layer — Setup & Launch Guide

## 📋 Overview

BTC-QUANT v4.4 now supports trading on **Lighter.xyz**, a Layer 2 orderbook DEX. This guide covers:
1. Testnet setup & testing
2. Mainnet deployment checklist
3. Configuration & environment variables
4. Troubleshooting common issues

---

## 🚀 Quickstart (Testnet)

### 1. Prepare Environment

```bash
# Copy the example configuration
cp execution_layer/.env.lighter.example backend/.env

# Edit .env with your testnet credentials
nano backend/.env
```

**Required variables:**
```env
LIGHTER_EXECUTION_MODE=testnet
LIGHTER_TRADING_ENABLED=false        # Keep disabled for safety testing!
LIGHTER_TESTNET_API_KEY=your_key
LIGHTER_TESTNET_API_SECRET=your_secret
LIGHTER_API_KEY_INDEX=2               # Avoid 0-1 (reserved)
```

### 2. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 3. Start the Daemon

```bash
# Ensure you're in the repo root
python execution_layer/lighter_executor.py
```

**Expected output:**
```
======================================================================
[LIGHTER] BTC-QUANT v4.4 Lighter.xyz Execution Daemon
======================================================================
[LIGHTER] Mode: TESTNET
[LIGHTER] Trading: 🔴 DISABLED
[LIGHTER] Parameters: Margin=$1,000 | Leverage=15x | SL=1.333% | TP=0.71%
[LIGHTER] Account Balance: $XXXX.XX USDC
[LIGHTER] Nonce resynced. Next nonce: 0
[LIGHTER] Market metadata synced. Price decimals: 2, Size decimals: 6
```

### 4. Enable Trading (After Verification)

Once confident in testnet stability:

```bash
# Edit .env
LIGHTER_TRADING_ENABLED=true

# Restart the daemon
python execution_layer/lighter_executor.py
```

---

## 🔐 Security Best Practices

### API Key Management

1. **Never hardcode credentials** — Always use environment variables
2. **Separate testnet/mainnet keys** — Use different API keys for each
3. **Rotate keys regularly** — Especially after testing
4. **Use API Key Index > 1** — Indices 0-1 are reserved by Lighter

### Safety Flags

```env
# Always start with these settings:
LIGHTER_EXECUTION_MODE=testnet
LIGHTER_TRADING_ENABLED=false
```

### Credential Rotation Checklist

- [ ] Generate new API key from Lighter dashboard
- [ ] Update `.env` with new key
- [ ] Restart daemon
- [ ] Delete old key from Lighter dashboard
- [ ] Test a small trade to verify

---

## 🧪 Testing & Validation

### Unit Tests

```bash
# Run all Lighter tests
pytest backend/tests/test_lighter_*.py -v

# Run only math tests
pytest backend/tests/test_lighter_math.py -v

# Run only nonce manager tests
pytest backend/tests/test_lighter_nonce_manager.py -v

# Run with coverage
pytest backend/tests/test_lighter_*.py --cov=app.utils.lighter_math --cov=app.use_cases.lighter_nonce_manager
```

### Integration Test (Manual)

1. Start daemon with `TRADING_ENABLED=false`
2. Monitor logs for:
   - ✅ Account balance fetch
   - ✅ Nonce resync from server
   - ✅ Market metadata sync
   - ✅ Position status check
3. Stop daemon gracefully (Ctrl+C)
4. Verify clean shutdown

### 48-Hour Stability Test (Testnet)

Before mainnet, run 48 hours on testnet:

```bash
# Start in background
nohup python execution_layer/lighter_executor.py > lighter.log 2>&1 &

# Monitor
tail -f lighter.log

# Check every hour for:
# - Cycle completions (look for "Cycle N complete")
# - No repeated errors
# - Consistent nonce increments
# - Balance checks working
```

---

## 📊 Monitoring & Logs

### Log Locations

- **Main daemon log:** stdout (or redirect with `> lighter.log`)
- **DuckDB trades log:** `backend/app/infrastructure/database/btc-quant.db`
- **Nonce state file:** `backend/app/infrastructure/lighter_nonce_state.json`

### Interpreting Log Levels

```
[LIGHTER] ✅ SUCCESS        → Order/operation completed
[LIGHTER] ⚠️  WARNING        → Non-critical issue, recovery attempted
[LIGHTER] ❌ ERROR          → Critical issue, position may be affected
[LIGHTER] Nonce mismatch    → Server nonce desync, auto-corrected
```

### Key Metrics to Monitor

```
Balance Check        → Should appear every 3600s
Cycle Completion     → Should appear every 60s
Nonce Status         → Should appear every 3600s
Market Metadata Sync → Should appear every 86400s (24h)
```

---

## 🔄 Nonce Management

### What is a Nonce?

Lighter requires each transaction to have a sequential nonce (0, 1, 2, ...). If nonce is wrong, the transaction fails.

### How BTC-QUANT Handles Nonces

1. **Persistence**: Nonces are saved to `lighter_nonce_state.json` after each trade
2. **Server Sync**: On startup, we resync from the server (mandatory safety check)
3. **Auto-Correction**: If nonce mismatch occurs, the daemon auto-resyncs
4. **Telegram Alert**: Nonce errors are logged; integration with Telegram is optional

### Debugging Nonce Issues

```bash
# Check current nonce state
cat backend/app/infrastructure/lighter_nonce_state.json

# Expected format:
# {
#   "api_key_index": 2,
#   "next_nonce": 42,
#   "last_synced_at": 1234567890,
#   "updated_at": "2026-03-13T10:00:00.000000"
# }

# If nonce is stuck, manually reset (LAST RESORT):
# 1. Stop the daemon
# 2. Delete lighter_nonce_state.json
# 3. Resync nonce from Lighter dashboard
# 4. Update .env with correct LIGHTER_API_KEY_INDEX
# 5. Restart daemon
```

---

## 💳 Account & Balance Management

### Minimum Balance Requirements

```
Testnet: Any USDC (for testing)
Mainnet: $1,200 USDC minimum
  - $1,000 for margin
  - $200 buffer for fees/slippage
```

### Check Balance

```bash
# Via API (automatic, logged hourly):
# Look for: "[LIGHTER] Balance check: $XXXX.XX USDC"

# Manual check:
# Use Lighter dashboard → Account → USDC balance
```

### Deposit USDC (Testnet)

1. Go to Lighter testnet dashboard
2. Click "Deposit" → "USDC"
3. Complete bridge transaction
4. Wait 10-30 min for confirmation
5. Balance should update in daemon logs

### Deposit USDC (Mainnet)

1. Bridge mainnet USDC from Ethereum Layer 1
2. Transfer via Lighter's fast withdrawal bridge
3. Wait for confirmation (usually <1 hour)

---

## 🆘 Troubleshooting

### Issue: "Missing Lighter credentials"

**Solution:**
```bash
# Check .env exists and has these variables:
grep "LIGHTER_TESTNET_API_KEY" backend/.env

# Should output:
LIGHTER_TESTNET_API_KEY=your_key_here

# If empty, get credentials from:
# 1. Go to Lighter dashboard
# 2. Account Settings → API Keys
# 3. Create new key (keep index > 1)
# 4. Copy key + secret
# 5. Update .env
```

### Issue: "Insufficient balance for mainnet"

**Solution:**
```bash
# The daemon requires at least $1,200 USDC on mainnet

# Check balance:
# Look in logs for: "[LIGHTER] Account Balance: $XXXX.XX USDC"

# If insufficient:
# 1. Deposit more USDC
# 2. Wait for confirmation
# 3. Restart daemon
```

### Issue: "Nonce mismatch detected"

**Solution (automatic):**
The daemon automatically resyncs with the server. Check logs for:
```
[LIGHTER] Nonce mismatch detected and corrected. Next nonce: X
```

**Solution (manual):**
```bash
# 1. Stop the daemon
# 2. Get current nonce from Lighter API:
curl https://testnet.zklighter.elliot.ai/account -H "X-API-Key: YOUR_KEY"
# Note the nonce field

# 3. Reset state file:
rm backend/app/infrastructure/lighter_nonce_state.json

# 4. Update LIGHTER_API_KEY_INDEX in .env if changed

# 5. Restart daemon (it will resync automatically)
```

### Issue: "No valid signal or fallback signal"

**Info (not an error):**
This is normal when the signal engine hasn't generated a signal yet. The daemon waits.

**Solution:**
```bash
# Ensure signal engine is running:
ps aux | grep "signal_service\|backtest"

# Check signal service is producing output:
# The daemon should show signals like:
# [LIGHTER] Signal available | Verdict: BULL | Conviction: 85.0%
```

### Issue: "Failed to sync market metadata"

**Solution:**
```bash
# This is a warning, not critical. Daemon uses cached decimals.
# To debug:
# 1. Check network connectivity
# 2. Verify Lighter API is up: https://status.lighter.xyz
# 3. Check API credentials are correct
# 4. Restart daemon
```

### Issue: Daemon crashes on startup

**Solution:**
```bash
# Check error message in logs
# Common causes:
# 1. Missing .env file → cp execution_layer/.env.lighter.example backend/.env
# 2. Invalid credentials → verify in Lighter dashboard
# 3. No USDC balance → deposit USDC first
# 4. Port conflict → change port in config (if applicable)

# For detailed debugging:
python -c "from app.adapters.gateways.lighter_execution_gateway import LighterExecutionGateway; import asyncio; asyncio.run(LighterExecutionGateway()._sync_market_metadata())"
```

---

## 📈 Mainnet Deployment Checklist

Before switching to mainnet, verify:

- [ ] 48-hour testnet stability test completed
- [ ] Nonce management working reliably
- [ ] Balance checks passing hourly
- [ ] Market metadata syncs every 24h
- [ ] All trades logged correctly to DuckDB
- [ ] Emergency stop tested and working
- [ ] Telegram alerts (optional) configured
- [ ] Mainnet API keys generated in Lighter dashboard
- [ ] `LIGHTER_API_KEY_INDEX > 1` (not 0 or 1)
- [ ] Minimum $1,200 USDC balance on mainnet
- [ ] Updated `LIGHTER_EXECUTION_MODE=mainnet` in .env
- [ ] `LIGHTER_TRADING_ENABLED=false` initially (enable after one clean cycle)
- [ ] Emergency contact details recorded (for support)

**Mainnet .env Example:**
```env
LIGHTER_EXECUTION_MODE=mainnet
LIGHTER_TRADING_ENABLED=false              # Start disabled!
LIGHTER_MAINNET_API_KEY=your_mainnet_key
LIGHTER_MAINNET_API_SECRET=your_mainnet_secret
LIGHTER_API_KEY_INDEX=3                    # Different from testnet!
```

---

## 🚨 Emergency Stop

### Manual Stop (Graceful)

```bash
# Press Ctrl+C in the running daemon
# Daemon will:
# 1. Close any open positions
# 2. Save trade state to DuckDB
# 3. Close WebSocket connections
# 4. Persist nonce state
# 5. Exit cleanly

# Expected output:
# [LIGHTER] Received SIGINT, initiating graceful shutdown...
# [LIGHTER] Shutting down gracefully...
# [LIGHTER] Position closed | Exit: $XXXX.XX
# [LIGHTER] Shutdown complete. Bye!
```

### Force Stop (Emergency Only)

```bash
# Last resort if daemon hangs
kill -9 <pid>

# WARNING: May leave position open!
# Always check Lighter dashboard manually after force stop:
# 1. Go to Account → Positions
# 2. If position still open, close manually via dashboard
```

### Telegram Alert (Optional)

If configured, daemon will send Telegram alert on:
- Emergency stop
- Nonce mismatch (auto-corrected)
- Order failures
- Critical errors

---

## 📞 Support & Resources

### Lighter Protocol Documentation
- API Docs: https://apidocs.lighter.xyz
- SDK: https://github.com/elliottech/lighter-python
- Status: https://status.lighter.xyz

### BTC-QUANT Project
- Repository: https://github.com/your-repo/btc-quant
- Issues: https://github.com/your-repo/btc-quant/issues
- Documentation: `/docs` directory

### Contact
- For Lighter issues: support@lighter.xyz
- For BTC-QUANT issues: Create GitHub issue or contact maintainers

---

## ✅ Implementation Summary

| Component | Status | Location |
|-----------|--------|----------|
| **lighter_math.py** | ✅ Complete | `backend/app/utils/lighter_math.py` |
| **lighter_nonce_manager.py** | ✅ Complete | `backend/app/use_cases/lighter_nonce_manager.py` |
| **lighter_execution_gateway.py** | ✅ Complete | `backend/app/adapters/gateways/lighter_execution_gateway.py` |
| **lighter_executor.py** | ✅ Complete | `execution_layer/lighter_executor.py` |
| **Unit tests** | ✅ Complete | `backend/tests/test_lighter_*.py` |
| **Configuration** | ✅ Updated | `backend/app/config.py` |
| **Environment template** | ✅ Complete | `execution_layer/.env.lighter.example` |

**Golden Parameters (Immutable):**
```
Margin: $1,000 USDT
Leverage: 15x
SL: 1.333% below entry
TP: 0.71% above entry
Time Exit: 24 hours (6 × 4h candles)
```

---

**Last Updated:** March 2026
**Version:** 1.0.0
**Status:** Phase 1 (Testnet-ready)
