# Telegram Isolation: Execution Layer Terpisah dari Signal

**Important:** Execution layer notifications menggunakan bot terpisah, tidak sentuh telegram signal yang lama.

---

## 🎯 Design Principle

**Execution layer notifications INDEPENDENT dari signal notifications.**

```
Signal Pipeline:
└─ TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID (existing, unchanged)

Execution Layer:
└─ EXECUTION_TELEGRAM_BOT_TOKEN + EXECUTION_TELEGRAM_CHAT_ID (new, independent)
```

---

## 📋 Konfigurasi

### Signal Notifications (Existing — DO NOT CHANGE)

```bash
# .env — Signal/Metrics notifications (existing)
TELEGRAM_BOT_TOKEN=signal_bot_token
TELEGRAM_CHAT_ID=signal_chat_id
```

**Tetap gunakan untuk:**
- Signal analysis notifications
- Metrics updates
- Dashboard alerts
- Existing functionality

---

### Execution Layer Notifications (New — Independent)

```bash
# .env — Live execution notifications (NEW)
EXECUTION_TELEGRAM_BOT_TOKEN=execution_bot_token
EXECUTION_TELEGRAM_CHAT_ID=execution_chat_id
```

**Gunakan hanya untuk:**
- Trade opened alerts
- Trade closed alerts
- Emergency stop alerts
- Execution errors

---

## 🔄 How It Works

### ExecutionNotifier Logic

```python
def __init__(self):
    # ONLY use execution telegram
    token = os.getenv("EXECUTION_TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("EXECUTION_TELEGRAM_CHAT_ID", "").strip()

    # NO fallback ke signal telegram (untuk isolation)
    # Hanya fallback jika KEDUA execution vars kosong
    # (untuk backward compatibility, bukan preference)
    if not token or not chat_id:
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    if not token or not chat_id:
        logger.warning("Telegram not configured")
        self.gateway = None
    else:
        self.gateway = TelegramGateway(token, chat_id)
```

**Priority:**
1. `EXECUTION_TELEGRAM_*` (preferred) ✅
2. `TELEGRAM_BOT_TOKEN` (fallback only if exec empty) ⚠️
3. Disabled (if both empty) ❌

---

## ✅ Best Practice Setup

### Recommended: Fully Separated (✅ Ideal)

```bash
# Signal telegram (existing — tetap ada)
TELEGRAM_BOT_TOKEN=signal_123:abc
TELEGRAM_CHAT_ID=111111

# Execution telegram (NEW — bot berbeda)
EXECUTION_TELEGRAM_BOT_TOKEN=execution_456:def
EXECUTION_TELEGRAM_CHAT_ID=222222
```

**Keuntungan:**
- ✅ Execution alerts tidak campur dengan signal
- ✅ Bisa disable/enable masing-masing independent
- ✅ Different notification channels untuk different purposes
- ✅ Cleaner notification management

**Cara setup:**
1. Buat 2 bots terpisah di BotFather
2. Isi kedua EXECUTION_TELEGRAM_* dan TELEGRAM_*

---

### Alternative: Execution Only (Fallback)

Jika hanya ingin execution notifications:

```bash
# Signal telegram (kosongkan jika tidak perlu)
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# Execution telegram HANYA (NEW)
EXECUTION_TELEGRAM_BOT_TOKEN=execution_456:def
EXECUTION_TELEGRAM_CHAT_ID=222222
```

**Keuntungan:**
- ✅ Simple, hanya satu bot
- ✅ Execution alerts tetap dikirim

---

### NOT Recommended: Mixed Mode

```bash
# Signal telegram
TELEGRAM_BOT_TOKEN=signal_123:abc
TELEGRAM_CHAT_ID=111111

# Execution telegram (empty, akan fallback)
EXECUTION_TELEGRAM_BOT_TOKEN=
EXECUTION_TELEGRAM_CHAT_ID=
```

**Hasil:**
- ⚠️ Execution akan pakai signal bot (fallback)
- ⚠️ Semua notifikasi di satu chat
- ⚠️ Tidak clean

---

## 🚫 What NOT to Do

### ❌ Do NOT modify signal telegram variables in ExecutionNotifier

```python
# WRONG! Don't do this:
def __init__(self):
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")  # ← Don't touch signal bot
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")  # ← Don't touch signal chat
```

Alasan:
- Signal notifications mungkin sedang berjalan
- Could cause conflicts or duplicate notifications
- Violates single responsibility principle

### ❌ Do NOT reuse execution telegram untuk signal

```python
# WRONG! Don't do this in SignalService:
def send_signal_alert(self):
    token = os.getenv("EXECUTION_TELEGRAM_BOT_TOKEN", "")  # ← Wrong bot
```

Alasan:
- Execution bot adalah untuk trading alerts only
- Could interfere dengan execution notifications

---

## 📊 Notification Flow

```
Signal Pipeline (Existing)
├─ L0-L5 Signal Processing
├─ SignalService generates signal
└─ TelegramNotifier sends via TELEGRAM_BOT_TOKEN
   └─ Chat: Signal/Metrics alerts

Live Execution Layer (New)
├─ PositionManager opens/closes positions
├─ ExecutionNotifier sends via EXECUTION_TELEGRAM_BOT_TOKEN
└─ Chat: Trade alerts (separate!)
```

**Key Point:** Dua notification channel yang INDEPENDENT.

---

## ✅ Checklist

Sebelum mainnet:

- [ ] TELEGRAM_BOT_TOKEN dan TELEGRAM_CHAT_ID filled (signal, existing)
- [ ] EXECUTION_TELEGRAM_BOT_TOKEN dan EXECUTION_TELEGRAM_CHAT_ID filled (execution, new)
- [ ] Signal notifications working (dari existing system)
- [ ] Execution notifications working (dari execution layer)
- [ ] Two bots created (one for signal, one for execution)
- [ ] Two different chat IDs configured
- [ ] Notifications pada waktu yang sama tidak interference

---

## 🔒 Security

Both telegram tokens should be:
- ✅ In `.env` file only (never in code)
- ✅ In `.gitignore` (never committed)
- ✅ Different tokens untuk different purposes
- ✅ Stored securely

```bash
# .env (in .gitignore)
TELEGRAM_BOT_TOKEN=signal_token_here
TELEGRAM_CHAT_ID=signal_chat_here
EXECUTION_TELEGRAM_BOT_TOKEN=execution_token_here
EXECUTION_TELEGRAM_CHAT_ID=execution_chat_here
```

---

## 🚀 Deployment

### Development/Testnet
```bash
# Setup both telegrams (recommended)
TELEGRAM_BOT_TOKEN=dev_signal_bot
TELEGRAM_CHAT_ID=dev_signal_chat
EXECUTION_TELEGRAM_BOT_TOKEN=dev_execution_bot
EXECUTION_TELEGRAM_CHAT_ID=dev_execution_chat
```

### Production/Mainnet
```bash
# Setup both telegrams (strongly recommended)
TELEGRAM_BOT_TOKEN=prod_signal_bot
TELEGRAM_CHAT_ID=prod_signal_chat
EXECUTION_TELEGRAM_BOT_TOKEN=prod_execution_bot
EXECUTION_TELEGRAM_CHAT_ID=prod_execution_chat
```

**Key:** Different bots for dev vs prod, separate execution telegram.

---

## 📞 Troubleshooting

### "Execution notifications not received"

**Check:**
1. `EXECUTION_TELEGRAM_BOT_TOKEN` is set? ✓
2. `EXECUTION_TELEGRAM_CHAT_ID` is set? ✓
3. Bot was sent `/start` message? ✓
4. Token & chat ID are correct? ✓

### "Execution notifications mixed with signal notifications"

**Cause:** EXECUTION_TELEGRAM_* is empty, falling back to TELEGRAM_*

**Fix:**
1. Create separate execution bot
2. Fill EXECUTION_TELEGRAM_BOT_TOKEN
3. Fill EXECUTION_TELEGRAM_CHAT_ID
4. Restart daemon

### "Signal notifications affected after enabling execution"

**Cause:** ExecutionNotifier might be interfering with signal telegram

**Fix:**
- Ensure EXECUTION_TELEGRAM_* is properly configured
- Don't empty TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID
- Check logs: both should initialize independently

---

## Summary

| Aspect | Signal | Execution |
|--------|--------|-----------|
| Bot Token | `TELEGRAM_BOT_TOKEN` | `EXECUTION_TELEGRAM_BOT_TOKEN` |
| Chat ID | `TELEGRAM_CHAT_ID` | `EXECUTION_TELEGRAM_CHAT_ID` |
| Purpose | Signal/Metrics alerts | Trade execution alerts |
| Isolation | Independent | Independent |
| Fallback | None | To signal if not set |
| Breaking Changes | None | None (fallback available) |

---

**TL;DR:** Use **separate telegram bots** for signal and execution. No changes to existing signal telegram.

---

**Last Updated:** 2026-03-11
**Version:** BTC-QUANT v4.4
