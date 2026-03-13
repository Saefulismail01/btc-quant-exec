# Lighter Execution Layer — Quick Reference

## 📋 File Structure

```
backend/
├── app/
│   ├── adapters/gateways/
│   │   └── lighter_execution_gateway.py      (550 lines, 8 abstract methods)
│   ├── use_cases/
│   │   └── lighter_nonce_manager.py          (250 lines, persistent state)
│   ├── utils/
│   │   └── lighter_math.py                   (300 lines, scaling helpers)
│   └── config.py                             (updated with Lighter vars)
└── tests/
    ├── test_lighter_math.py                  (40+ tests)
    └── test_lighter_nonce_manager.py         (30+ async tests)

execution_layer/
├── lighter_executor.py                       (300 lines, main daemon)
├── .env.lighter.example                      (config template)
├── LIGHTER_SETUP_GUIDE.md                    (comprehensive guide)
└── LIGHTER_IMPLEMENTATION_SUMMARY.md         (this implementation doc)
```

## 🚀 Get Started (5 minutes)

```bash
# 1. Copy template
cp execution_layer/.env.lighter.example backend/.env

# 2. Edit with your testnet credentials
nano backend/.env

# 3. Run daemon
python execution_layer/lighter_executor.py

# 4. Watch logs for:
# ✅ "[LIGHTER] Account Balance: $XXXX.XX USDC"
# ✅ "[LIGHTER] Nonce resynced. Next nonce: 0"
# ✅ "[LIGHTER] Market metadata synced..."
```

## 🔑 Key Components

| Component | Purpose | Key Methods | Test Coverage |
|-----------|---------|------------|---|
| **lighter_math.py** | Integer scaling for Lighter | `scale_price()`, `calculate_btc_quantity()` | 40+ tests |
| **lighter_nonce_manager.py** | Persistent transaction sequencing | `get_next_nonce()`, `resync_from_server()` | 30+ tests |
| **lighter_execution_gateway.py** | Order execution (Lighter) | `place_market_order()`, `close_position_market()` | Integrates with tests |
| **lighter_executor.py** | Main daemon loop | `run()`, `startup_checks()`, `shutdown()` | Ready for testnet |

## 🔧 Environment Variables

**Required (Testnet):**
```env
LIGHTER_EXECUTION_MODE=testnet
LIGHTER_TESTNET_API_KEY=your_key
LIGHTER_TESTNET_API_SECRET=your_secret
```

**Optional:**
```env
LIGHTER_TRADING_ENABLED=false              # Default: false (safety)
LIGHTER_API_KEY_INDEX=2                    # Default: 2 (avoid 0-1)
EXECUTION_TELEGRAM_BOT_TOKEN=...           # For alerts
```

## 📊 Architecture

```
Signal Engine → PositionManager → LighterExecutionGateway
                                  ├─ lighter_math (scaling)
                                  ├─ lighter_nonce_manager (nonce)
                                  └─ HTTP/WebSocket (Lighter API)
                                       ↓
                                  DuckDB (live_trades table)
                                  Telegram (notifications)
```

## ✅ Testing

```bash
# Unit tests (local, no credentials needed)
pytest backend/tests/test_lighter_*.py -v

# Coverage report
pytest backend/tests/test_lighter_math.py --cov=app.utils.lighter_math -v

# Specific test
pytest backend/tests/test_lighter_math.py::TestScalePrice -v
```

## 🛑 Common Commands

| Task | Command |
|------|---------|
| Start daemon | `python execution_layer/lighter_executor.py` |
| Stop gracefully | `Ctrl+C` in running daemon |
| Check nonce state | `cat backend/app/infrastructure/lighter_nonce_state.json` |
| View logs | `tail -f lighter.log` (if redirected) |
| Run tests | `pytest backend/tests/test_lighter_*.py -v` |
| View current setup | `grep LIGHTER backend/.env` |

## 📈 Monitoring

**Key Logs to Watch:**

```
[LIGHTER] Cycle N — Syncing position...      # Every 60 seconds
[LIGHTER] Balance check: $XXXX.XX USDC       # Every 3600 seconds
[LIGHTER] Nonce status: next=X, synced=true  # Every 3600 seconds
[LIGHTER] Market metadata synced...          # Every 86400 seconds
```

**Issues to Watch For:**

```
❌ "Nonce mismatch detected"     → Auto-corrected, check logs
⚠️  "Failed to sync metadata"     → Warning only, uses cached values
❌ "Insufficient balance"         → Need to deposit USDC
❌ "Trading disabled"             → Set LIGHTER_TRADING_ENABLED=true
```

## 🔐 Security Checklist

- [ ] Never commit `.env` file
- [ ] Use `LIGHTER_TRADING_ENABLED=false` initially
- [ ] Keep testnet/mainnet credentials separate
- [ ] Use API Key Index > 1 (avoid reserved 0-1)
- [ ] Rotate API keys monthly
- [ ] Monitor all trades via logs/DuckDB
- [ ] Test emergency stop before mainnet

## 🎯 Next Steps

### Immediate
1. Setup testnet credentials in `.env`
2. Run `python execution_layer/lighter_executor.py`
3. Verify logs show no errors

### After Testnet Verification
1. Run 48-hour stability test
2. Monitor cycle completions (~2,880 in 48h)
3. Check nonce state file updates
4. Review DuckDB trade logs

### Before Mainnet
1. Complete testnet checklist
2. Prepare mainnet credentials
3. Verify $1,200+ USDC balance
4. Enable `TRADING_ENABLED=true` carefully

## 📞 Helpful Resources

- **Setup Guide:** `execution_layer/LIGHTER_SETUP_GUIDE.md`
- **Implementation Details:** `execution_layer/LIGHTER_IMPLEMENTATION_SUMMARY.md`
- **Lighter API Docs:** https://apidocs.lighter.xyz
- **Lighter Status:** https://status.lighter.xyz

## 📊 Golden Parameters (Immutable)

```
Margin:        $1,000 USDT
Leverage:      15x
Stop Loss:     1.333% below entry
Take Profit:   0.71% above entry
Time Exit:     24 hours (6 × 4h candles)
```

## 🚨 Emergency Procedures

**Graceful Stop:**
```bash
# Press Ctrl+C in running daemon
# Daemon will close positions and save state
```

**Manual Position Close:**
```bash
# If daemon crashes, check Lighter dashboard:
# Account → Positions → Close manually if needed
```

**Reset Nonce (Last Resort):**
```bash
# 1. Stop daemon
# 2. Delete: backend/app/infrastructure/lighter_nonce_state.json
# 3. Verify correct LIGHTER_API_KEY_INDEX in .env
# 4. Restart (auto-resync from server)
```

---

**Version:** 1.0.0 (Phase 1)
**Status:** Testnet-Ready
**Last Updated:** March 2026

For detailed information, see `LIGHTER_SETUP_GUIDE.md` and `LIGHTER_IMPLEMENTATION_SUMMARY.md`.
