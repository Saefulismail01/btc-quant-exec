# Environment Configuration Setup

## 📋 Which .env File to Use?

### ✅ RECOMMENDED: Single `.env` in Root

**Use `./.env` (root directory) for:**
- All local development
- All execution layer testing (Binance, Lighter)
- All backends (app, frontend)

**Why?**
- `python-dotenv` automatically loads from root
- Single source of truth
- Easier to manage
- Less confusion

---

## 🔧 Setup Instructions

### 1. Create `.env` from template

```bash
# Copy template to actual .env
cp .env.template .env

# Edit with your credentials
nano .env
# or on Windows:
code .env
```

### 2. Fill in required variables

**For Binance Testnet execution:**
```env
EXECUTION_GATEWAY=binance
EXECUTION_MODE=testnet
TRADING_ENABLED=false
BINANCE_TESTNET_API_KEY=your_testnet_key
BINANCE_TESTNET_SECRET=your_testnet_secret
```

**For Lighter Testnet execution:**
```env
EXECUTION_GATEWAY=lighter
LIGHTER_EXECUTION_MODE=testnet
LIGHTER_TRADING_ENABLED=false
LIGHTER_TESTNET_API_KEY=your_key
LIGHTER_TESTNET_API_SECRET=your_secret
LIGHTER_API_KEY_INDEX=2
```

### 3. (Optional) Telegram notifications

```env
# Use existing signal telegram or create dedicated one
EXECUTION_TELEGRAM_BOT_TOKEN=your_bot_token
EXECUTION_TELEGRAM_CHAT_ID=your_chat_id
```

---

## ⚠️ IMPORTANT: Never Delete backend/.env

If `backend/.env` exists with test data:
- ❌ Do NOT commit it to git (already in .gitignore)
- ❌ Do NOT delete it (might have test data)
- ✅ Just leave it there (git will ignore it)

---

## 📂 File Structure After Setup

```
btc-scalping-execution_layer/
├── .env                    ← YOUR CREDENTIALS (git ignored)
├── .env.template          ← REFERENCE ONLY (can commit)
├── backend/
│   ├── .env               ← OLD (from previous setup, git ignored)
│   └── ...
├── frontend/
│   ├── .env               ← Frontend config (VITE_API_URL)
│   └── ...
└── ...
```

---

## ✅ Verify Setup

```bash
# Check that .env files are properly ignored
git check-ignore -v .env backend/.env

# Output should be:
# .gitignore:11:*.env  .env
# .gitignore:11:*.env  backend/.env

# Check that .env.template can be committed
git check-ignore .env.template
# (no output = not ignored, good!)
```

---

## 🔑 How Python Loads `.env`

When you run any Python script:

```python
from dotenv import load_dotenv
import os

# This automatically loads .env from the root directory
load_dotenv()

# Access variables
api_key = os.getenv("BINANCE_TESTNET_API_KEY")
```

**Search order:**
1. `.env` in current directory
2. `.env` in parent directory
3. `.env` in project root ← **Usually found here**

---

## 🚀 Ready to Run

Once `.env` is configured in root:

```bash
# Binance execution
python backend/paper_executor.py

# Lighter execution
python execution_layer/lighter_executor.py

# Or with subprocess (automatically loads .env from root)
cd anywhere && python /path/to/script.py
```

---

## 🛡️ Security Checklist

- [ ] `.env` is in `.gitignore`
- [ ] Never `git add .env`
- [ ] `.env` contains real credentials
- [ ] `.env.template` can be safely committed (empty values)
- [ ] Credentials rotated before sharing code/screenshots
- [ ] Never paste `.env` contents in chat/logs

