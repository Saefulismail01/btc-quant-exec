# Telegram Setup untuk Live Execution Notifications

**Untuk notifikasi trading yang terpisah dari signal notifications**

---

## 📱 Opsi Setup

### Opsi 1: Gunakan Telegram Terpisah (Recommended ✅)

Buat bot dan chat khusus untuk live execution alerts:

1. **Buat Bot Baru di Telegram**
   - Chat dengan [@BotFather](https://t.me/botfather) di Telegram
   - Kirim: `/newbot`
   - Ikuti instruksi untuk membuat bot baru
   - **Catat Token Bot:** `123456789:ABCDEFGHIJKLMNOPqrstuvwxyz`

2. **Tentukan Chat ID**
   - Chat dengan bot baru yang dibuat
   - Kirim pesan apapun
   - Cek di: `https://api.telegram.org/bot<TOKEN>/getUpdates`
   - **Catat Chat ID:** `987654321`

3. **Setup `.env`**
   ```bash
   # Telegram untuk execution layer (TERPISAH)
   EXECUTION_TELEGRAM_BOT_TOKEN=123456789:ABCDEFGHIJKLMNOPqrstuvwxyz
   EXECUTION_TELEGRAM_CHAT_ID=987654321

   # Telegram lama (untuk signal/metrics) tetap ada
   TELEGRAM_BOT_TOKEN=...
   TELEGRAM_CHAT_ID=...
   ```

**Keuntungan:**
- ✅ Notifikasi trading terpisah dari signal (cleaner)
- ✅ Bisa disable execution bot tanpa affect signal bot
- ✅ Chat khusus untuk trading (dedicated channel/group)

---

### Opsi 2: Gunakan Telegram yang Sama (Simple)

Jika ingin pakai bot yang sudah ada:

```bash
# Cukup kosongkan variable execution (atau jangan isi)
EXECUTION_TELEGRAM_BOT_TOKEN=
EXECUTION_TELEGRAM_CHAT_ID=

# Notifier akan fallback ke telegram lama
TELEGRAM_BOT_TOKEN=123456789:ABCDEFGHIJKLMNOPqrstuvwxyz
TELEGRAM_CHAT_ID=987654321
```

**Keuntungan:**
- ✅ Simple, no extra setup
- ⚠️ Semua notifikasi campur (signal + trading)

---

## 🔧 Fallback Logic

ExecutionNotifier menggunakan logic fallback:

```python
# First priority: dedicated execution telegram
EXECUTION_TELEGRAM_BOT_TOKEN  ← Check here first
EXECUTION_TELEGRAM_CHAT_ID

# Fallback: existing signal telegram
TELEGRAM_BOT_TOKEN  ← Use if execution not configured
TELEGRAM_CHAT_ID
```

**Behavior:**
1. Jika `EXECUTION_TELEGRAM_BOT_TOKEN` dan `EXECUTION_TELEGRAM_CHAT_ID` ada → Gunakan
2. Jika kosong → Fallback ke `TELEGRAM_BOT_TOKEN` dan `TELEGRAM_CHAT_ID`
3. Jika semua kosong → Disabled (log warning)

---

## 📋 Step-by-Step Setup

### 1. Chat dengan BotFather

```
You: /newbot
BotFather: Alright! Choose a name for your bot. Each bot has a name and a username. The name just has to be clever 🤖. Remember that bots can't edit messages, only send new ones, unless they're commands. Making your bot funny is as easy as writing the right description and sticker pack.

You: BTC-QUANT Live Executor
BotFather: Good. Now let's choose a username for your bot. It must end in `bot`. Like this, for example: TetrisBot or google_rim_bot. So, what's going to be the username of your bot?

You: btc_quant_live_executor_bot
BotFather: Done! Congratulations on your new bot. You will find it at https://t.me/btc_quant_live_executor_bot. You can now add a description, about section and profile picture for your new bot, see /help for a list of commands.

Here are your bot credentials:
Bot token: 123456789:ABCDEFGHIJKLMNOPqrstuvwxyz

[Keep your token secure and store it safely!]
```

✅ **Token Bot:** `123456789:ABCDEFGHIJKLMNOPqrstuvwxyz`

### 2. Dapatkan Chat ID

```bash
# Ganti TOKEN dengan token dari step 1
curl "https://api.telegram.org/bot123456789:ABCDEFGHIJKLMNOPqrstuvwxyz/getMe"
```

Response:
```json
{
  "ok": true,
  "result": {
    "id": 1234567890,
    "is_bot": true,
    "first_name": "BTC",
    "username": "btc_quant_live_executor_bot"
  }
}
```

Sekarang chat dengan bot ini dan kirim pesan:

```bash
# Chat dengan bot yang baru dibuat
# Buka: https://t.me/btc_quant_live_executor_bot
# Kirim: /start

# Sekarang cek updates:
curl "https://api.telegram.org/bot123456789:ABCDEFGHIJKLMNOPqrstuvwxyz/getUpdates"
```

Response:
```json
{
  "ok": true,
  "result": [
    {
      "update_id": 123456789,
      "message": {
        "message_id": 1,
        "from": {
          "id": 987654321,  ← CHAT ID INI
          "is_bot": false,
          "first_name": "Your Name"
        },
        "chat": {
          "id": 987654321,  ← ATAU DARI SINI
          "first_name": "Your Name",
          "type": "private"
        },
        "date": 1234567890,
        "text": "/start"
      }
    }
  ]
}
```

✅ **Chat ID:** `987654321`

### 3. Edit `.env`

```bash
# Execution Layer — Telegram Notifications (Terpisah)
EXECUTION_TELEGRAM_BOT_TOKEN=123456789:ABCDEFGHIJKLMNOPqrstuvwxyz
EXECUTION_TELEGRAM_CHAT_ID=987654321

# Signal Notifications (Lama — tetap ada)
TELEGRAM_BOT_TOKEN=<TOKEN_LAMA>
TELEGRAM_CHAT_ID=<CHAT_ID_LAMA>
```

### 4. Test

```bash
cd backend
python -c "
from app.use_cases.execution_notifier_use_case import get_execution_notifier
import asyncio

notifier = get_execution_notifier()
asyncio.run(notifier.notify_error(
    'Test Notification',
    'Setup berhasil!'
))
"
```

Harus menerima message di Telegram dengan isi:
```
⚠️  EXECUTION ERROR
━━━━━━━━━━━━━━━━━━
Test Notification

Setup berhasil!
━━━━━━━━━━━━━━━━━━
🤖 BTC-QUANT LIVE v4.4
```

---

## 🎯 Notification Types

Setelah setup, akan terima notifikasi untuk:

### 🟢 Trade Opened
```
🟢 LIVE TRADE OPENED
━━━━━━━━━━━━━━━━━━
📈 BTC/USDT Perpetual | LONG
💰 Entry  : $83,500.00
📏 Size   : $1,000 (15x) = $15,000 notional
🛑 SL     : $82,386.00 (-1.333%)
🎯 TP     : $84,093.00 (+0.71%)
⏳ Expire : 24 hours (6 candle)
🎯 Verdict: STRONG BUY
🔥 Conviction: 🟩🟩🟩🟩🟩⬜⬜⬜⬜⬜ 67.3%
━━━━━━━━━━━━━━━━━━
🤖 BTC-QUANT LIVE v4.4
ID: 12345678
```

### ✅ Trade Closed (TP/SL/TIME_EXIT)
```
✅ LIVE TRADE CLOSED — TP
━━━━━━━━━━━━━━━━━━
📈 BTC/USDT | LONG
💰 Entry  : $83,500.00
💰 Exit   : $84,093.00
📈 PnL    : +$106.50 USDT (+10.65%)
⏱️  Hold   : 8.5 hours
🎯 Exit   : TP
━━━━━━━━━━━━━━━━━━
🤖 BTC-QUANT LIVE v4.4
ID: 12345678
```

### 🚨 Emergency Stop
```
🚨 EMERGENCY STOP TRIGGERED
━━━━━━━━━━━━━━━━━━
Position closed @ $82,386.00
PnL: -$133.50 USDT
Trading HALTED.
Resume via API.
━━━━━━━━━━━━━━━━━━
🤖 BTC-QUANT LIVE v4.4
```

### ⚠️ Errors
```
⚠️  EXECUTION ERROR
━━━━━━━━━━━━━━━━━━
SL Order Failed

Immediately closing position...
━━━━━━━━━━━━━━━━━━
🤖 BTC-QUANT LIVE v4.4
```

---

## 🔐 Security Notes

- **Token Bot:** Jangan share ke orang lain
- **Chat ID:** Relatively safe tapi jangan share di public
- **Store in `.env`:** Never commit ke git
- **`.gitignore`:** Pastikan `.env` sudah di-ignore

---

## 🚨 Troubleshooting

### "Telegram not configured. Notifications disabled."

**Penyebab:**
- `EXECUTION_TELEGRAM_BOT_TOKEN` kosong
- `EXECUTION_TELEGRAM_CHAT_ID` kosong
- Fallback ke `TELEGRAM_BOT_TOKEN` juga kosong

**Solusi:**
1. Set salah satu:
   - EXECUTION_TELEGRAM_BOT_TOKEN + EXECUTION_TELEGRAM_CHAT_ID (preferred)
   - TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID (fallback)

2. Restart daemon

### "Invalid Token"

**Penyebab:**
- Token salah copy (missing `:`)
- Token expired

**Solusi:**
1. Verify di BotFather: `/mybots` → select bot → "API Token"
2. Copy ulang dengan hati-hati
3. Update `.env`
4. Restart daemon

### "Chat not found"

**Penyebab:**
- Chat ID salah
- Bot tidak punya akses ke chat

**Solusi:**
1. Verify Chat ID dengan `getUpdates`
2. Pastikan sudah send message ke bot
3. Ulangi langkah di "Dapatkan Chat ID"

### "Notifications tidak masuk"

**Penyebab:**
- Bot tidak di-start (send `/start` belum)
- Bot muted di Telegram
- Credentials salah

**Solusi:**
1. Chat dengan bot: https://t.me/btc_quant_live_executor_bot
2. Send: `/start`
3. Verify credentials di `.env`
4. Check logs: `[ExecutionNotifier] ✅ Telegram configured`

---

## 📊 Environment Checklist

```bash
# Di .env file, pastikan ada:

# Option 1: Dedicated Execution Telegram (Recommended)
EXECUTION_TELEGRAM_BOT_TOKEN=123456789:ABCDEFGHIJKLMNOPqrstuvwxyz
EXECUTION_TELEGRAM_CHAT_ID=987654321

# Option 2: Fallback to Signal Telegram (if option 1 empty)
TELEGRAM_BOT_TOKEN=<token_lama>
TELEGRAM_CHAT_ID=<chat_id_lama>

# At least one of above options must be configured!
```

✅ **Ready for live notifications!**

---

**Last Updated:** 2026-03-11
**Version:** BTC-QUANT v4.4
