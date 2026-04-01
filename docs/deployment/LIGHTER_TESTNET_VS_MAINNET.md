# Lighter Testnet vs Mainnet — Complete Guide

## Quick Summary

| Aspect | Testnet | Mainnet |
|--------|---------|---------|
| **Purpose** | Learning & testing | Live trading (real money) |
| **Real Money?** | ❌ No (fake USDC) | ✅ Yes (real USDC) |
| **Risk** | Safe | ⚠️ Real loss if bot fails |
| **Dashboard** | https://lighter.elliot.ai | https://lighter.xyz |
| **API Endpoint** | testnet.zklighter.elliot.ai | api.lighter.xyz |
| **When to Use** | First (48 hours) | After testnet validation |

---

## Phase 1: Testnet Setup (First 48 Hours)

### 1.1 Get Testnet Credentials

**Step 1:** Go to https://lighter.elliot.ai (Testnet)

**Step 2:** Sign up with wallet (MetaMask/WalletConnect)

**Step 3:** Navigate to: **Account → Settings → API Keys**

**Step 4:** Click **"Generate New Key"** with settings:
- Permissions: `Trading` + `Read`
- Index: Choose **2 or higher** (avoid 0-1, reserved by Lighter)
- Name: `BTC-QUANT Trading Bot` (optional)

**Step 5:** Copy immediately (won't show again!):
```
API Key:    abc123xyz...
API Secret: xyz789abc...
Index:      2
```

### 1.2 Configure .env for Testnet

Edit `.env` file:
```env
# Mode
LIGHTER_EXECUTION_MODE=testnet
LIGHTER_TRADING_ENABLED=false        # Keep disabled for safety testing!

# Testnet Credentials (REQUIRED)
LIGHTER_TESTNET_API_KEY=abc123xyz...
LIGHTER_TESTNET_API_SECRET=xyz789abc...
LIGHTER_API_KEY_INDEX=2

# Mainnet Credentials (LEAVE EMPTY for now)
LIGHTER_MAINNET_API_KEY=
LIGHTER_MAINNET_API_SECRET=
```

### 1.3 Start & Monitor

```bash
# Start daemon
python execution_layer/lighter_executor.py

# Expected output:
# [LIGHTER] Mode: TESTNET
# [LIGHTER] Trading: [DISABLED]
# [LIGHTER] Account Balance: $XXXX.XX USDC
# [LIGHTER] Nonce resynced. Next nonce: 0
```

### 1.4 Watch for 48 Hours

Monitor logs for:
- ✅ **Cycle completions** (every 60 seconds)
- ✅ **Balance checks** (every 3600 seconds)
- ✅ **Nonce increments** (0 → 1 → 2 → 3 ...)
- ✅ **No errors or crashes**

Once confident → Move to Phase 2

---

## Phase 2: Mainnet Deployment (After 48h Testnet)

### 2.1 Get Mainnet Credentials

⚠️ **Only do this after testnet is 100% stable!**

**Step 1:** Go to https://lighter.xyz (Mainnet)

**Step 2:** Sign in with same wallet

**Step 3:** Navigate to: **Account → Settings → API Keys**

**Step 4:** Click **"Generate New Key"** with settings:
- Permissions: `Trading` + `Read`
- Index: Choose **DIFFERENT index** from testnet
  - Example: Used `2` for testnet? Use `3` for mainnet
- Name: `BTC-QUANT Trading Bot` (optional)

**Step 5:** Copy immediately:
```
API Key:    def456uvw...
API Secret: uvw123def...
Index:      3 (different from testnet!)
```

### 2.2 Deposit USDC to Mainnet

**Minimum required:** $1,200 USDC
- $1,000 for margin
- $200 buffer for fees/slippage

**How to deposit:**
1. Go to Lighter.xyz mainnet
2. Account → Deposit
3. Select USDC
4. Bridge from Ethereum L1 (or use Lighter bridge)
5. Wait for confirmation

### 2.3 Update .env for Mainnet

Edit `.env` file:
```env
# Mode (CHANGED)
LIGHTER_EXECUTION_MODE=mainnet       # MAINNET!
LIGHTER_TRADING_ENABLED=false        # Keep disabled initially!

# Testnet Credentials (can leave as-is)
LIGHTER_TESTNET_API_KEY=abc123xyz...
LIGHTER_TESTNET_API_SECRET=xyz789abc...
LIGHTER_API_KEY_INDEX=2

# Mainnet Credentials (NOW REQUIRED)
LIGHTER_MAINNET_API_KEY=def456uvw...
LIGHTER_MAINNET_API_SECRET=uvw123def...
```

### 2.4 Verify Balance

```bash
# Start daemon (still with trading disabled)
python execution_layer/lighter_executor.py

# Expected output:
# [LIGHTER] Mode: MAINNET
# [LIGHTER] Trading: [DISABLED]
# [LIGHTER] Account Balance: $XXXX.XX USDC (REAL MONEY!)
```

**Check balance matches your deposit!**

### 2.5 Test One Clean Cycle

Let the daemon run one complete cycle with trading disabled:
- Should sync nonce
- Should check balance
- Should verify position status
- No trades should execute

If everything looks good → Enable trading

### 2.6 Enable Trading (Final Step)

Edit `.env`:
```env
LIGHTER_TRADING_ENABLED=true         # ENABLE TRADING
```

Restart bot:
```bash
# Ctrl+C to stop current
python execution_layer/lighter_executor.py
```

**You're live!** 🚀

---

## How Code Chooses Testnet vs Mainnet

### Automatic Mode Selection

File: `backend/app/adapters/gateways/lighter_execution_gateway.py` (lines 90-119)

```python
def __init__(self):
    # Read mode from .env
    mode = os.getenv("LIGHTER_EXECUTION_MODE")  # "testnet" or "mainnet"

    if mode == "testnet":
        # Load TESTNET credentials
        self.api_key = os.getenv("LIGHTER_TESTNET_API_KEY")
        self.api_secret = os.getenv("LIGHTER_TESTNET_API_SECRET")
        self.base_url = "https://testnet.zklighter.elliot.ai"

    else:  # mainnet
        # Load MAINNET credentials
        self.api_key = os.getenv("LIGHTER_MAINNET_API_KEY")
        self.api_secret = os.getenv("LIGHTER_MAINNET_API_SECRET")
        self.base_url = "https://mainnet.zklighter.elliot.ai"
```

### Key Point

**You only change ONE .env variable:**

```
LIGHTER_EXECUTION_MODE = testnet or mainnet
         ↓
Code automatically chooses the right:
  - Credentials
  - API endpoint
  - WebSocket URL
```

**Everything else stays the same!** ✨

---

## Nonce Management

### What is Nonce?

Nonce = Sequential transaction number (0, 1, 2, 3, ...)

**Lighter requires:** Each transaction must use correct nonce in order

### Testnet vs Mainnet Nonces

- **Testnet nonce:** Separate counter (starts at 0 for testnet)
- **Mainnet nonce:** Separate counter (starts at 0 for mainnet)
- **Independent:** Testnet nonce doesn't affect mainnet nonce

### Nonce State File

```json
{
  "api_key_index": 2,
  "next_nonce": 42,
  "last_synced_at": 1234567890,
  "updated_at": "2026-03-13T10:00:00"
}
```

**Location:** `backend/app/infrastructure/lighter_nonce_state.json`

### On Startup

Bot automatically:
1. Loads nonce state from file
2. **Resyncs with server** to verify correctness
3. Updates state file

### Switching Testnet → Mainnet

⚠️ **Important:** Different API keys = different nonce counters

When you switch LIGHTER_EXECUTION_MODE to `mainnet`:
- Code loads LIGHTER_MAINNET_API_KEY
- Server has fresh nonce counter (0 if new key)
- Bot resyncs automatically on startup

**No manual reset needed!**

---

## Troubleshooting

### Issue: "Missing Lighter credentials for testnet mode"

**Cause:** `LIGHTER_TESTNET_API_KEY` or `LIGHTER_TESTNET_API_SECRET` is empty

**Solution:**
```bash
# Check .env has these:
grep "LIGHTER_TESTNET_API_KEY" .env
grep "LIGHTER_TESTNET_API_SECRET" .env

# Should show values, not empty
```

---

### Issue: "Insufficient balance for mainnet"

**Cause:** Balance < $1,200 USDC on mainnet

**Solution:**
1. Go to Lighter.xyz mainnet
2. Deposit more USDC
3. Wait for confirmation
4. Restart bot

---

### Issue: "Mode: TESTNET but trying to load MAINNET credentials"

**Cause:** .env has mixed configuration

**Solution:** Check .env is one of these:

```env
# Testnet (Phase 1)
LIGHTER_EXECUTION_MODE=testnet
LIGHTER_TESTNET_API_KEY=... (required)
LIGHTER_TESTNET_API_SECRET=... (required)
LIGHTER_MAINNET_API_KEY=... (empty)
LIGHTER_MAINNET_API_SECRET=... (empty)

# Mainnet (Phase 2)
LIGHTER_EXECUTION_MODE=mainnet
LIGHTER_TESTNET_API_KEY=... (can be old value)
LIGHTER_TESTNET_API_SECRET=... (can be old value)
LIGHTER_MAINNET_API_KEY=... (required)
LIGHTER_MAINNET_API_SECRET=... (required)
```

---

## Deployment Timeline

```
DAY 1 (T+0):
├─ Get testnet credentials
├─ Configure .env for testnet
├─ Start daemon with TRADING_ENABLED=false
└─ Watch for 24 hours

DAY 2 (T+24):
├─ Verify 24h stability
├─ Check nonce increments
└─ Continue watching 24 more hours

DAY 3 (T+48):
├─ Get mainnet credentials (OK)
├─ Deposit $1,200+ USDC to mainnet
├─ Update .env for mainnet
├─ Verify balance with TRADING_ENABLED=false
├─ Watch 1 clean cycle
└─ Set TRADING_ENABLED=true
    LIVE TRADING STARTS!
```

---

## Safety Checklist

### Before Mainnet

- [ ] 48-hour testnet validation completed
- [ ] Nonce management working (increments correctly)
- [ ] Balance checks passing hourly
- [ ] All trades logged to database
- [ ] Emergency stop tested and works
- [ ] Mainnet API keys generated
- [ ] $1,200+ USDC deposited to mainnet
- [ ] .env configured for mainnet
- [ ] One clean cycle verified with trading disabled
- [ ] Ready for real money trading

### During Live Trading

- [ ] Monitor logs daily
- [ ] Check PnL calculations
- [ ] Verify positions close on TP/SL
- [ ] Watch for nonce errors
- [ ] Keep emergency contact details
- [ ] Have manual trader (in case bot stops)

---

## Support Resources

- **Lighter Protocol Docs:** https://apidocs.lighter.xyz
- **BTC-QUANT Docs:** See `docs/` directory
- **Lighter Status:** https://status.lighter.xyz
- **This Project:** `QUICK_START_LIGHTER.md`

---

**Last Updated:** March 2026
**Status:** Testnet-ready, Mainnet deployment ready
