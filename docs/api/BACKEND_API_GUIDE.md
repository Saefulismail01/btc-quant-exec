# 📖 BTC-QUANT Backend API Documentation (v2.1)

Dokumentasi ini disusun untuk mempermudah integrasi Front-End (FE) dengan sistem backend BTC-QUANT yang menggunakan arsitektur **Clean FastAPI**.

---

## 🚀 Base URL
```
http://localhost:8000
```
*Gunakan prefix `/api` untuk semua endpoint.*

---

## 🛠️ Ringkasan Endpoint

| Category | Method | Endpoint | Description |
| :--- | :--- | :--- | :--- |
| **System** | `GET` | `/api/health` | Health check & server status. |
| **System** | `GET` | `/api/cache_info` | Status training model BCD & MLP. |
| **Signal** | `GET` | `/api/signal` | **Main Signal Intelligence Report.** |
| **Market** | `GET` | `/api/metrics` | Raw market metrics (Funding, OI, FGI). |
| **Trading** | `GET` | `/api/trading/status` | Akun & posisi Paper Trading aktif. |
| **Trading** | `GET` | `/api/trading/history` | Riwayat transaksi simulai. |
| **Trading** | `POST` | `/api/trading/reset` | Reset saldo paper trading ke $10k. |

---

## 📡 Details & Contoh Integrasi

### 1. Intelligence Signal (`/api/signal`)
Endpoint utama yang digunakan oleh UI Dashboard untuk menampilkan sinyal, skor konfluensi, dan trade plan.

**Response Example:**
```json
{
  "timestamp": "2026-03-06T07:45:00Z",
  "price": {
    "now": 84250.5,
    "ema20": 83900.2,
    "ema50": 83500.0,
    "atr14": 450.5
  },
  "confluence": {
    "verdict": "STRONG BUY",
    "directional_bias": 0.85,
    "conviction_pct": 85.0,
    "rationale": "Strong alignment across BCD regime and L3 MLP. Directional spectrum confirms trend continuation.",
    "layers": {
      "l1_hmm": { "aligned": true, "label": "Bullish", "detail": "BCD confirms trend start" },
      "l3_ai": { "aligned": true, "label": "Convincing", "detail": "MLP probability > 0.72" }
    }
  },
  "trade_plan": {
    "action": "LONG",
    "entry_start": 84100,
    "entry_end": 84250,
    "sl": 83500,
    "tp1": 85500,
    "leverage": 15,
    "position_size_pct": 5.2
  },
  "regime_bias": {
    "persistence": 0.92,
    "expected_duration_candles": 12.5,
    "interpretation": "Bullish: regime sangat persistent. Trend-following valid."
  }
}
```

---

### 2. Paper Trading Status (`/api/trading/status`)
Digunakan untuk widget Portfolio di FE.

**Response Example:**
```json
{
  "account": {
    "balance": 10250.75,
    "equity": 10500.20,
    "last_update": 1741246800000
  },
  "active_position": [
    {
      "symbol": "BTC/USDT",
      "side": "LONG",
      "entry_price": 84000.0,
      "size_base": 0.15,
      "sl": 83200.0,
      "pnl": 37.5,
      "pnl_pct": 0.45
    }
  ]
}
```

---

### 3. Model Cache Info (`/api/cache_info`)
Digunakan untuk indikator "System Status" di bar navigasi FE (menandakan apakah model sudah di-*train* atau masih *cold start*).

**Response Example:**
```json
{
  "timestamp": "2026-03-06T07:47:36Z",
  "models": {
    "layer1_bcd": {
      "trained": true,
      "last_trained_len": 7206,
      "changepoints_found": 18
    },
    "layer3_mlp": {
      "trained": true,
      "version": "v1.2",
      "last_acc": 0.68
    }
  }
}
```

---

## 💡 Tips untuk Front-End
1.  **Polling vs Websocket**: Saat ini backend berbasis REST Polling. Disarankan FE melakukan request `/api/signal` setiap **60 detik** untuk data terbaru.
2.  **Error Handling**: Jika backend baru dijalankan, ada fase *warm-up* model. Berikan indikator "Loading ML Models" jika mendapatkan status code `503 Service Unavailable`.
3.  **Position Size**: Selalu gunakan field `position_size_pct` untuk kalkulasi volume di UI, jangan gunakan `position_size` (legacy string).
4.  **CORS**: Middleware CORS sudah di-allow untuk `localhost:3000` dan `localhost:5173`. Jika menggunakan port lain, update di `backend/app/config.py`.

---
*Dokumentasi ini dihasilkan secara otomatis oleh Antigravity untuk BTC-QUANT Development Team.*
