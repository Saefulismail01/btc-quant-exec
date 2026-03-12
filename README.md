# BTC-QUANT: Adaptive Signal Engine (v3.0)

BTC-QUANT adalah platform kuantitatif canggih untuk scalping BTC/USDT Perpetual Futures. Menggunakan arsitektur modular **6-Layer Pipeline** yang menggabungkan Bayesian inference, Machine Learning, dan Econophysics untuk menghasilkan keputusan trading yang objektif dan terukur.

---

## ⚡ Arsitektur Sistem (v3.0)

Sistem ini beroperasi dalam alur kerja linier dari data mentah hingga narasi taktis:

### **Layer 0: Data Ingestion & Storage**
*   **Engine**: Sinkronisasi real-time dari Binance Futures API ke **DuckDB**.
*   **Metrics**: Menangkap OHLCV, CVD (Cumulative Volume Delta), Open Interest, Funding Rate, dan Fear & Greed Index secara periodik.

### **Layer 1: Market Regime Detection (BCD)**
*   **Model**: Bayesian Changepoint Detection (BCD).
*   **Fungsi**: Mendeteksi perubahan struktur pasar (Bullish, Bearish, Sideways) secara probabilistik.
*   **Cross-Feature**: Output state dari L1 diinjeksikan ke L3 sebagai *contextual bridge*.

### **Layer 2: Technical Alignment**
*   **Filter**: EMA Confluence (20/50), Ichimoku Cloud, dan RSI/MACD momentum.
*   **Fungsi**: Memastikan sinyal searah dengan struktur tren makro dan momentum mikro.

### **Layer 3: AI Signal Intelligence (MLP)**
*   **Model**: Multi-Layer Perceptron (Neural Network) dengan Online Learning.
*   **Smart Labeling**: Menggunakan 3-class classifier (**Bull, Bear, Neutral**) dengan ambang batas pergerakan 0.5× ATR untuk memfilter noise.
*   **Input**: 9 fitur dasar (5 Teknikal + 4 Microstructure/Sentiment) yang membengkak menjadi **13 fitur** saat *Cross-Feature Bridge* aktif.
*   **Innovation**: Menggunakan **Regime-to-MLP Cross-Feature Bridge** (dari Layer 1) untuk memberikan konteks kondisi pasar pada prediksi AI.
*   **Architecture**: Auto-scaling neurons dari `128→64` (base) menjadi `256→128` (cross) untuk menangani kompleksitas fitur tambahan.

### **Layer 4: Risk & Decision Engine (The Brain)**
*   **Directional Spectrum**: Mengubah sinyal biner menjadi skor bias kontinu [-1, +1].
*   **Econophysics**: Estimasi volatilitas berbasis **Heston Model** untuk menentukan multiplier SL/TP yang adaptif.
*   **Risk Manager**: Position sizing (2% risk), dynamic leverage cap (up to 20x), dan proteksi Daily Loss Cap.
*   **Sentiment Filter**: Penyesuaian size otomatis berdasarkan ekstrim Fear & Greed.

### **Layer 5: Narrative & Truth Enforcer**
*   **Narrative**: LLM (Kimi/OpenAI) mensintesis semua data kuantitatif menjadi analisis taktis bahasa manusia.
*   **Truth Enforcer**: Mekanisme keamanan yang mengunci verdict LLM agar tidak bertentangan dengan skor kuantitatif (e.g., Skor < 40 dipaksa NEUTRAL).

---

## 🚀 Fitur Utama

-   **BCD Engine**: Deteksi regime pasar yang lebih akurat dibanding HMM tradisional.
-   **Adaptive SL/TP**: Target harga yang menyesuaikan diri dengan "detak jantung" volatilitas pasar (Heston SV).
-   **Multi-Source Data**: Menggabungkan harga, volume (CVD), aliran modal (OI), dan psikologi massa (FGI).
-   **Modern Stack**: Python (FastAPI), React (Vite), dan DuckDB untuk performa analisis data tinggi.

---

## 📂 Struktur Proyek

-   `backend/` – FastAPI Server, Service Layers, dan Model Engines.
-   `frontend/` – React Dashboard UI (Vite).
-   `backtest/v2/` – Mesin simulasi True Walk-Forward (Zero Lookahead Bias).
-   `docs/` – Dokumentasi detail arsitektur, riset, dan API.

---

## 🛠️ Setup Cepat

### **Backend**
1. `cd backend`
2. `python -m venv .venv`
3. `.venv\Scripts\Activate.ps1` (Windows)
4. `pip install -r requirements.txt`
5. `python run.py` (Menjalankan API + Data Engine)

### **Frontend**
1. `cd frontend`
2. `npm install`
3. `npm run dev`

Buka dashboard di: `http://localhost:5173`

---

## 📈 Paper Trading (Virtual Execution)

Sistem ini dilengkapi dengan daemon eksekusi otomatis untuk melakukan simulasi perdagangan di pasar real-time tanpa risiko finansial.

### **Cara Menjalankan**
Untuk menjalankan siklus paper trade penuh, buka 3 terminal terpisah:
1.  **Terminal 1 (Data Ingest)**: `cd backend && python data_engine.py` (Mengambil data real-time).
2.  **Terminal 2 (API/Brain)**: `cd backend && python run.py` (Menghitung sinyal Layer 1-5).
3.  **Terminal 3 (Executor)**: `cd backend && python paper_executor.py` (Bot eksekusi otomatis).

### **Detail Operasional**
*   **Saldo Awal**: Akun virtual dimulai dengan **$10,000 USDT**.
- **Log Eksekusi**: Riwayat keputusan bot dapat dipantau di `backend/paper_execution.log`.
- **Manajemen Posisi**: Bot secara otomatis mengelola Stop Loss dan Take Profit berdasarkan model volatilitas Heston.
- **Reset Akun**: Gunakan endpoint API `POST /api/trading/reset` untuk mengembalikan saldo ke awal.

## 📡 Dokumentasi REST API

Backend menyediakan API berbasis REST untuk integrasi dengan frontend atau aplikasi eksternal. Semua endpoint mengembalikan data dalam format **JSON**.

### **1. Signal Intelligence**
`GET /api/signal`
Mengambil laporan sinyal lengkap hasil pemrosesan 5-Layer Pipeline.

*   **Fungsi**: Sinkronisasi dashboard, pengambilan instruksi trading (SL/TP), dan status regime market.
*   **Contoh Response**:
```json
{
  "timestamp": "2026-03-07T05:20:00Z",
  "is_fallback": false,
  "price": {
    "now": 68065.4,
    "ema20": 69553.3,
    "ema50": 68834.4,
    "atr14": 1270.4
  },
  "trend": {
    "bias": "Bearish",
    "short": "BEAR"
  },
  "trade_plan": {
    "action": "SHORT",
    "entry_start": 68065.4,
    "sl": 69335.8,
    "tp1": 66159.8,
    "status": "SUSPENDED",
    "status_reason": "Fallback — Regime neutral/sideways — no edge."
  },
  "confluence": {
    "confluence_score": 0,
    "verdict": "NEUTRAL",
    "rationale": "High Volatility Sideways detected. Avoid entry."
  }
}
```

### **2. Market Metrics**
`GET /api/metrics`
Mengambil metrik pasar mentah dan indeks sentimen.

*   **Fungsi**: Menampilkan data mikrostruktur pasar dan Fear & Greed Index.
*   **Contoh Response**:
```json
{
  "funding_rate": 0.00001927,
  "open_interest": 84201.5,
  "order_book_imbalance": 0.0341,
  "sentiment": {
    "score": 12.0,
    "label": "Extreme Fear",
    "note": "External market psychology index."
  }
}
```

### **3. Trading Status & History**
Digunakan untuk memantau performa bot *paper trading* dan riwayat eksekusi.

*   **`GET /api/trading/status`**: Mengambil saldo akun dan posisi yang sedang terbuka.
    *   **Contoh Response**:
    ```json
    {
      "account": {
        "balance": 10250.5,
        "equity": 10250.5,
        "last_update": 1709798400000
      },
      "active_position": [
        {
          "id": "trade_123",
          "symbol": "BTC/USDT",
          "side": "LONG",
          "entry_price": 67500.0,
          "size_base": 0.015,
          "sl": 66800.0,
          "tp": 69000.0,
          "status": "OPEN"
        }
      ]
    }
    ```

*   **`GET /api/trading/history`**: Mengambil daftar transaksi yang sudah selesai (limit 50).
    *   **Contoh Response**:
    ```json
    [
      {
        "id": "trade_122",
        "timestamp": 1709784000000,
        "symbol": "BTC/USDT",
        "side": "SHORT",
        "entry_price": 68000.0,
        "exit_price": 67200.0,
        "pnl": 80.0,
        "pnl_pct": 1.18,
        "status": "CLOSED"
      }
    ]
    ```

*   **`POST /api/trading/reset`**: Mengatur ulang saldo akun virtual ke $10,000 dan menghapus seluruh posisi.
    *   **Response**: `{"message": "Paper account reset successfully."}`

### **4. System Health**
`GET /api/health`
Mengecek status sistem dan versi backend.

*   **Contoh Response**: `{"status": "ok", "version": "2.1", "timestamp": "..."}`

---


## 🚀 Live Execution (v4.4 Golden — NEW!)

BTC-QUANT sekarang mendukung **live execution** di Binance Futures (testnet & mainnet).

### **Cara Memulai Live Trading**

#### 1. Setup Binance Testnet
```bash
# Edit .env (di root project)
EXECUTION_MODE=testnet
TRADING_ENABLED=false              # Start disabled!
BINANCE_TESTNET_API_KEY=...
BINANCE_TESTNET_SECRET=...
```

#### 2. Test Koneksi
```bash
cd backend
python test_testnet_connection.py
```

#### 3. Jalankan Live Executor
```bash
cd backend
python live_executor.py
```

#### 4. Monitor Status API
```bash
curl http://localhost:8000/api/execution/status | jq
```

### **API Endpoints (Live Execution)**

**GET `/api/execution/status`**
- Status real-time: akun balance, open position, daily PnL, risk status

**POST `/api/execution/emergency_stop`**
- Close semua posisi dan halt trading secara instan

**POST `/api/execution/resume`**
- Resume trading (requires explicit confirmation: `{"confirm": "RESUME_TRADING"}`)

**POST `/api/execution/set_trading_enabled`**
- Toggle trading enabled flag

### **Golden Parameters (v4.4 — Fixed)**
- **Margin per trade**: $1,000 USDT
- **Leverage**: 15x (notional $15,000)
- **Stop Loss**: 1.333% dari entry
- **Take Profit**: 0.71% dari entry
- **Time Exit**: 24 jam (6 candle × 4h)

### **Notification Telegram**
Sistem mengirim notifikasi untuk:
- Trade opened (dengan conviction level)
- Trade closed (TP/SL/TIME_EXIT/MANUAL)
- Emergency stop triggered
- Errors & warnings

Setup:
```bash
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

### **Safety Features**
✅ `TRADING_ENABLED=false` by default (manual enable required)
✅ SL order gagal → posisi langsung di-close
✅ Testnet/mainnet separation via environment
✅ Graceful shutdown dengan posisi closure
✅ Retry logic dengan exponential backoff
✅ Daily loss cap + consecutive loss cooldown

### **Dokumentasi Lengkap**
- `execution_layer/TESTNET_GUIDE.md` — Step-by-step testing guide
- `execution_layer/IMPLEMENTATION_PLAN.md` — Technical deep-dive
- `execution_layer/PHASE3_SUMMARY.md` — Complete API reference

---

## 📝 Catatan Operasional
-   Database (`btc-quant.db`) akan dibuat otomatis saat pertama kali dijalankan.
-   Pastikan `data_engine.py` berjalan untuk menjaga data tetap segar (Update setiap 4 jam/sesuai timeframe).
-   Sistem ini adalah **Decision Support System**, keputusan final dan manajemen risiko tetap di tangan trader.
-   **Live Execution**: Dimulai dengan testnet (TRADING_ENABLED=false), validasi 48 jam, kemudian mainnet.

---
*Terakhir diperbarui: Maret 2026 — Arsitektur v4.4 dengan Live Execution Layer*
