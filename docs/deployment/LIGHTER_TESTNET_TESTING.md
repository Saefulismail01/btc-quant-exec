# Lighter Testnet Testing Guide

## Step 1: Verify .env Configuration

```bash
# Check .env file exists and has values
cd /path/to/project
cat .env | grep LIGHTER

# Should output (values filled in):
# LIGHTER_EXECUTION_MODE=testnet
# LIGHTER_TESTNET_API_KEY=<your_key>
# LIGHTER_TESTNET_API_SECRET=<your_secret>
# LIGHTER_API_KEY_INDEX=3
```

## Step 2: Test Connection Only (No Trading)

```bash
# Run bot in read-only mode first
python execution_layer/lighter/lighter_executor.py
```

**Expected output (first 30 seconds):**
```
======================================================================
[LIGHTER] BTC-QUANT v4.4 Lighter.xyz Execution Daemon
======================================================================
[LIGHTER] Mode: TESTNET
[LIGHTER] Trading: [DISABLED]
[LIGHTER] Parameters: Margin=$1,000 | Leverage=15x | SL=1.333% | TP=0.71%
[LIGHTER] TIME_EXIT: 24 hours (6 x 4h candles)
[LIGHTER] API Key Index: 3
[LIGHTER] Account Balance: $XXXX.XX USDC
[LIGHTER] Resyncing nonce from server...
[LIGHTER] Nonce resynced from server. Next nonce: X
[LIGHTER] Syncing market metadata...
[LIGHTER] Market metadata synced. Price decimals: 2, Size decimals: 6
[LIGHTER] No existing positions (clean state)
```

## Step 3: What to Check

### ✅ Success Indicators:

1. **Connection established**
   - No "connection refused" errors
   - No "credentials" errors

2. **Balance fetched**
   - Shows your testnet USDC balance
   - Amount > 0 (you deposited testnet USDC)

3. **Nonce synced**
   - Shows "Nonce resynced"
   - Next nonce is a number (0, 1, 2, etc)

4. **Market metadata synced**
   - Shows price decimals (usually 2)
   - Shows size decimals (usually 6)

5. **No positions**
   - Should say "No existing positions (clean state)"

### ❌ Error Indicators:

| Error | Cause | Fix |
|-------|-------|-----|
| "Missing credentials for testnet" | `.env` missing API key/secret | Fill in LIGHTER_TESTNET_API_KEY/SECRET |
| "Connection refused" | Testnet endpoint down | Check Lighter status page |
| "Invalid signature" | API_PRIVATE_KEY wrong | Verify in .env, regenerate if needed |
| "Insufficient balance" | No USDC in account | Deposit USDC to testnet account |
| "Account not found" | API key index wrong | Verify LIGHTER_API_KEY_INDEX matches dashboard |

## Step 4: Run Bot for 1 Hour (Read-Only)

```bash
# Keep running with trading DISABLED
# Watch logs for:
# - Consistent cycles (every 60 seconds)
# - No errors repeating
# - Balance check (every 3600 seconds = 1 hour)

# In separate terminal, watch logs:
tail -f lighter.log
```

## Step 5: Enable Trading (After 1 Hour Verification)

If everything looks good:

1. **Edit .env:**
   ```env
   LIGHTER_TRADING_ENABLED=true
   ```

2. **Restart bot:**
   ```bash
   # Ctrl+C to stop
   python execution_layer/lighter/lighter_executor.py
   ```

3. **Watch first trades:**
   - Should open position (if signal available)
   - Should place SL order
   - Should place TP order
   - Check balance changes

## Step 6: Monitor for 24-48 Hours

Watch for:
- ✅ Cycle completions (every 60s)
- ✅ Nonce increments (0 → 1 → 2 → ...)
- ✅ Orders execute properly
- ✅ Positions close on TP/SL/TIME_EXIT
- ✅ No repeated errors
- ✅ Graceful shutdown (Ctrl+C works)

## Troubleshooting

### Issue: "EOFError: read from closed file" on startup

**Cause:** .env file syntax error

**Fix:**
```bash
# Check .env format (no quotes around values)
cat .env | head -20

# Should be:
LIGHTER_EXECUTION_MODE=testnet    ✅
LIGHTER_EXECUTION_MODE="testnet"  ❌ (no quotes!)

# Verify no empty lines or weird characters
file .env  # should say "ASCII text"
```

### Issue: "Account Balance: $0.00 USDC"

**Cause:** No testnet USDC deposited

**Fix:**
1. Go to https://app.lighter.xyz (testnet)
2. Account → Deposit
3. Deposit testnet USDC
4. Wait for confirmation
5. Restart bot

### Issue: "Nonce mismatch detected"

**Cause:** Nonce out of sync with server

**Fix:**
- Bot should auto-fix (shows "Nonce resynced")
- If stuck, delete: `backend/app/infrastructure/lighter_nonce_state.json`
- Restart bot

### Issue: "Failed to sync market metadata"

**Cause:** Testnet API endpoint unreachable (warning, not critical)

**Fix:**
- Bot continues with default decimals
- Check Lighter status: https://status.lighter.xyz
- If down, wait a few minutes

