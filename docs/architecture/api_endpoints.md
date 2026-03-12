# Dokumentasi Endpoint

Base URL (local dev):
- `http://localhost:8000`

**Health**
- `GET /api/health`
- Deskripsi: status layanan, versi, dan timestamp
- Request JSON: tidak ada (GET tanpa body)
- Response JSON (contoh):
```json
{
  "status": "ok",
  "version": "2.1",
  "timestamp": "2026-02-26T04:40:12Z"
}
```

**Signal**
- `GET /api/signal`
- Deskripsi: ringkasan sinyal (trend, trade plan, confluence layers, volatilitas)
- Request JSON: tidak ada (GET tanpa body)
- Response JSON (contoh):
```json
{
  "timestamp": "2026-02-26T04:40:12Z",
  "price": {
    "now": 52000.0,
    "ema20": 51850.0,
    "ema50": 51200.0,
    "atr14": 650.0,
    "ema20_prev": 51780.0,
    "ema50_prev": 51150.0
  },
  "trend": {
    "bias": "Bullish",
    "short": "BULL",
    "ema_structure": "EMA20 above EMA50 → Bullish",
    "momentum": "Strong — Price above EMA20"
  },
  "trade_plan": {
    "action": "LONG",
    "entry_start": 51920.0,
    "entry_end": 52000.0,
    "sl": 51025.0,
    "tp1": 52975.0,
    "tp2": 53625.0,
    "leverage": 5,
    "position_size": "Max 5% Portfolio"
  },
  "confluence": {
    "aligned_count": 3,
    "total": 4,
    "probability": "high",
    "conclusion": "Setup solid dengan 3/4 layer aligned.",
    "layers": {
      "l1_hmm": { "aligned": true, "label": "Regime Bull", "detail": "HMM Model" },
      "l2_tech": { "aligned": true, "label": "Bullish Confirmed", "detail": "EMA + ATR" },
      "l3_ai": { "aligned": true, "label": "68.5% (BULL)", "detail": "MLP Model" },
      "l4_risk": { "aligned": false, "label": "Vol High — Caution", "detail": "ATR-based SL" }
    }
  },
  "volatility": {
    "label": "High",
    "ratio": 0.013
  },
  "market_metrics": {
    "funding_rate": 0.00012,
    "open_interest": 23145.0,
    "order_book_imbalance": 0.18,
    "global_mcap_change_pct": 0.45,
    "obi_label": "Buy Dominant",
    "funding_label": "Positive — Short Squeeze Risk"
  },
  "validity_utc": "2026-02-26 08:00 UTC"
}
```

**Metrics**
- `GET /api/metrics`
- Deskripsi: metrik mentah (funding rate, open interest, order book imbalance, MCAP change, sentiment)
- Request JSON: tidak ada (GET tanpa body)
- Response JSON (contoh):
```json
{
  "funding_rate": 0.00012,
  "open_interest": 23145.0,
  "order_book_imbalance": 0.18,
  "global_mcap_change_pct": 0.45,
  "sentiment": {
    "score": 62.5,
    "label": "Greed",
    "note": "Risk-on sentiment"
  }
}
```

**Catatan**
- Endpoint melayani metode `GET` saja.
- Pastikan `backend/data_engine.py` berjalan agar data tidak kosong.
