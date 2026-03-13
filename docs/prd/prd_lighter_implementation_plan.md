# Lighter Trading Bot - Scalping Execution Layer

## 📋 Project Overview

Bot scalping otomatis untuk trading di **Lighter Protocol** dengan interval **4 jam**. Bot ini menggunakan Python dan mengintegrasikan:
- ✅ Signal generation (sudah selesai)
- 🔄 **Order execution layer** (sedang dikerjakan)

---

## 🏗️ Arsitektur

```
┌─────────────────────────────────────────┐
│   Signal Generation Module              │
│   (4H Candle Analysis → Buy/Sell)      │
└────────────┬────────────────────────────┘
             │
             ↓
┌─────────────────────────────────────────┐
│   Signal Output (Format TBD)            │
│   - Buy/Sell decisions                  │
│   - Quantity & entry price              │
└────────────┬────────────────────────────┘
             │
             ↓
┌─────────────────────────────────────────┐
│   Execution Layer (IN DEVELOPMENT)      │
│   - Validate signals                    │
│   - Risk checks                         │
│   - Order submission to Lighter         │
│   - Status tracking                     │
└────────────┬────────────────────────────┘
             │
             ↓
┌─────────────────────────────────────────┐
│   Lighter API (REST + WebSocket)        │
│   - sendTx / sendTxBatch                │
│   - Order monitoring                    │
└─────────────────────────────────────────┘
```

---

## 📋 Komponen Utama

### 1. **Signal Generator** ✅ (Sudah Selesai)
- Menganalisis candle 4H
- Generate buy/sell signals
- Output format: TBD (perlu dikonfirmasi)

### 2. **Execution Layer** 🔄 (Dalam Pengembangan)
- Parse signal dari signal generator
- Validasi risiko & position sizing
- Submit order ke Lighter API
- Monitor order status
- Handle errors & reconnection

### 3. **Lighter API Integration**
- REST API untuk order submission
- WebSocket untuk real-time monitoring
- Rate limit management

---

## ⚙️ Prerequisites

### Sistem
- Python 3.8+
- VPS atau server untuk 24/7 operation
- Stable internet connection

### Lighter Setup
- Lighter API credentials (API key & secret)
- Testnet account untuk testing
- Premium account (opsional, untuk higher rate limits)
- Staked LIT tokens (jika ingin high-frequency)

### Dependencies
```
requests          # REST API calls
websockets        # WebSocket connections
pandas            # Data processing
python-dotenv     # Environment variables
```

---

## 📊 Rate Limits (Lighter)

**Penting untuk scalping bot!**

| Tipe | Limit | Catatan |
|------|-------|---------|
| **REST API (Premium)** | 24,000 weighted req/min | Cukup untuk 4H scalping |
| **sendTx (Premium + Staking)** | 4,000-40,000/min | Tergantung LIT staked |
| **WebSocket** | 100 connections, 1,000 subscriptions | Per IP |
| **Error Response** | HTTP 429 | Cooldown 60s-ms |

**Untuk 4H interval:** ✅ Rate limits tidak masalah

---

## 🚀 Instalasi & Setup

### 1. Clone / Setup Project
```bash
git clone <repo>
cd lighter-trading-bot
python -m venv venv
source venv/bin/activate  # atau venv\Scripts\activate di Windows
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Konfigurasi Environment
Buat file `.env`:
```
LIGHTER_API_KEY=your_api_key
LIGHTER_API_SECRET=your_api_secret
LIGHTER_BASE_URL=https://api.lighter.xyz  # atau testnet URL
LIGHTER_WS_URL=wss://api.lighter.xyz/ws

# Trading params
SYMBOL=BTC/USD
POSITION_SIZE=1.0
STOP_LOSS_PCT=2.0
TAKE_PROFIT_PCT=5.0
MAX_POSITIONS=1
```

### 4. Jalankan Bot
```bash
python main.py
```

---

## 📝 Signal Format (TBD)

Perlu dikonfirmasi bagaimana signal di-output dari signal generator:

**Option 1: Dictionary/JSON**
```python
signal = {
    "action": "BUY",  # atau "SELL"
    "symbol": "BTC",
    "quantity": 1.0,
    "entry_price": 45000.50,
    "timestamp": "2025-03-12T10:00:00Z"
}
```

**Option 2: File-based (JSON/CSV)**
```json
{"action": "BUY", "symbol": "BTC", "quantity": 1.0}
```

**Option 3: Database/Queue**
- Redis queue
- Database table
- Message broker

---

## 🔧 Execution Layer Logic

### Flow
1. **Receive Signal** dari signal generator
2. **Validate**
   - Check apakah ada open positions
   - Check margin availability
   - Check exposure limits
3. **Calculate Order**
   - Size berdasarkan risk management
   - Entry/exit levels
4. **Submit to Lighter**
   - Call `sendTx` API
   - Handle response
5. **Monitor**
   - Track order status via WebSocket
   - Update database
6. **Error Handling**
   - Retry logic
   - Fallback mechanisms
   - Logging

---

## 🛡️ Risk Management

Execution layer harus include:
- ✅ Position size limits
- ✅ Stop-loss levels
- ✅ Take-profit targets
- ✅ Max open positions check
- ✅ Drawdown limits
- ✅ Slippage tolerance

---

## 📂 File Structure (Target)

```
lighter-trading-bot/
├── implementation-lighter-execution.md
├── requirements.txt
├── .env.example
├── main.py
├── config.py
├── signal_generator/
│   ├── __init__.py
│   └── analyzer.py        # Signal logic (existing)
├── execution/
│   ├── __init__.py
│   ├── executor.py        # Main execution layer
│   ├── lighter_api.py     # Lighter API wrapper
│   ├── risk_manager.py    # Risk validation
│   └── order_tracker.py   # Monitor orders
├── utils/
│   ├── __init__.py
│   ├── logger.py
│   └── helpers.py
└── tests/
    └── test_execution.py
```

---

## 🔄 Development Checklist

### Phase 1: API Integration
- [ ] Setup Lighter API client (REST + WebSocket)
- [ ] Implement authentication
- [ ] Test API connectivity

### Phase 2: Execution Core
- [ ] Build order submission logic
- [ ] Implement risk validation
- [ ] Handle error responses

### Phase 3: Monitoring & Tracking
- [ ] Order status tracking
- [ ] WebSocket listener for updates
- [ ] Logging & alerts

### Phase 4: Testing
- [ ] Testnet deployment
- [ ] Dry-run with real signals
- [ ] Risk scenario testing

### Phase 5: Production
- [ ] Mainnet deployment
- [ ] Monitoring dashboard
- [ ] Performance optimization

---

## 📊 Monitoring & Logging

Bot harus log:
- ✅ Signals received
- ✅ Validation results
- ✅ Order submissions
- ✅ Order fills/rejections
- ✅ Errors & exceptions
- ✅ PnL tracking

Log format:
```
[2025-03-12 10:00:00] SIGNAL: BUY signal received for BTC
[2025-03-12 10:00:01] VALIDATION: Risk check passed
[2025-03-12 10:00:02] ORDER: Submitted sendTx for 1 BTC at 45000.50
[2025-03-12 10:00:03] FILLED: Order filled at 45001.25
```

---

## ⚠️ Important Notes

1. **Testnet First**: Selalu test di testnet sebelum mainnet
2. **Rate Limits**: Monitor rate limit usage (terutama untuk high-frequency updates)
3. **API Latency**: Lighter API latency bisa affect fill prices
4. **Slippage**: Include slippage tolerance dalam execution
5. **Connection Stability**: Implement reconnection logic untuk WebSocket
6. **Private Keys**: JANGAN hardcode private keys, selalu gunakan environment variables

---

## 📞 Next Steps

Untuk melanjutkan development:

1. **Share signal format** dari signal generator
2. **Confirm order requirements**
   - Order type (market/limit)?
   - Leverage?
   - Token pair apa saja?
3. **Lighter account setup**
   - Testnet credentials ready?
4. **Start building execution layer**

---

## 📚 Resources

- [Lighter API Docs](https://apidocs.lighter.xyz/)
- [Rate Limits](https://apidocs.lighter.xyz/docs/rate-limits)
- [Python Requests](https://requests.readthedocs.io/)
- [Websockets](https://websockets.readthedocs.io/)

---

**Status**: 🔄 In Development | **Last Updated**: 2025-03-12
