# Lighter Execution Bot — Quick Start (5 Minutes)

## Step 1: Setup Environment (1 min)

```bash
# Copy template to create actual .env
cp .env.template .env

# Open and fill in credentials
code .env
```

**Minimal required variables:**
```env
EXECUTION_GATEWAY=lighter
LIGHTER_EXECUTION_MODE=testnet
LIGHTER_TRADING_ENABLED=false
LIGHTER_TESTNET_API_KEY=your_key_here
LIGHTER_TESTNET_API_SECRET=your_secret_here
LIGHTER_API_KEY_INDEX=2
```

## Step 2: Get Lighter Testnet Credentials (2 min)

1. Go to https://lighter.elliot.ai (testnet)
2. Sign up or login
3. Account Settings → API Keys
4. Create new key (make sure index > 1)
5. Copy key + secret to `.env`

## Step 3: Start the Bot (1 min)

```bash
# From project root
python execution_layer/lighter_executor.py
```

**Expected output:**
```
======================================================================
[LIGHTER] BTC-QUANT v4.4 Lighter.xyz Execution Daemon
======================================================================
[LIGHTER] Mode: TESTNET
[LIGHTER] Trading: [DISABLED]
[LIGHTER] Account Balance: $XXXX.XX USDC
[LIGHTER] Nonce resynced. Next nonce: 0
```

## Step 4: Monitor (Ongoing)

```bash
# Watch logs in separate terminal
tail -f lighter.log

# Check key metrics:
# ✓ "Cycle X complete" every 60 seconds
# ✓ "Balance check: $XXXX" every 60 minutes
# ✓ "Nonce" stays consistent (0, 1, 2, ...)
```

## Step 5: Enable Trading (After 24h validation)

Once you're confident:
```bash
# Edit .env
LIGHTER_TRADING_ENABLED=true

# Restart bot
# (Ctrl+C then run again)
```

---

## ⚠️ Safety Rules

- ❌ Never set `LIGHTER_TRADING_ENABLED=true` immediately
- ❌ Never hardcode credentials (always use .env)
- ❌ Never commit .env to git
- ✅ Always start with testnet
- ✅ Watch 24 hours before enabling trades
- ✅ Keep $1,000 USDC minimum in account

---

## 🔧 Troubleshooting

| Error | Fix |
|-------|-----|
| "Missing credentials" | Check .env file exists with LIGHTER_TESTNET_API_KEY |
| "Insufficient balance" | Deposit USDC to Lighter testnet account |
| "Nonce mismatch" | Bot auto-fixes. Check logs for confirmation |
| No signal | Signal engine might not be running. Check separately |

---

## 📞 Full Guides

- **Setup Details:** `SETUP_ENV.md`
- **Lighter Setup:** `execution_layer/lighter/LIGHTER_SETUP_GUIDE.md`
- **Binance Setup:** `execution_layer/binance/TESTNET_GUIDE.md`
- **Troubleshooting:** See respective setup guides

---

**Ready? Run:** `python execution_layer/lighter_executor.py`

