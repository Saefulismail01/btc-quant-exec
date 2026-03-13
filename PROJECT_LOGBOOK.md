# 📓 BTC-QUANT: Project Logbook & Evolution

Dokumen ini berfungsi sebagai *single source of truth* untuk melacak progres, keputusan arsitektur, dan update terbaru dalam pengembangan BTC-QUANT.

---

## 🚀 Status Saat Ini: v4.4 Golden Model
**Update Terakhir:** 13 Maret 2026
**Status Eksekusi:** Live (Binance Testnet/Mainnet) & Riset Lighter L2

### 🔝 Key Updates (v4.4)
1.  **Fix #1: L3 Disagreement Logic** - MLP NEUTRAL sekarang menjadi counter-signal (-0.3) terhadap BCD BULL/BEAR.
2.  **Fix #2: Weight Calibration** - Mengembalikan bobot ke standar emas: **L1=0.30, L2=0.25, L3=0.45**.
3.  **Fix #3: Momentum Exhaustion** - Implementasi RSI & Proximity filter pada Layer 2.
4.  **OPT-A (1-Candle Target)** - Perpindahan target MLP ke 4H (1 candle) untuk presisi scalping yang lebih tinggi.

---

## 🛠️ Riwayat Implementasi (Timeline)

### Maret 2026 (Sekarang)
- **[2026-03-13]** Inisialisasi proyek **Lighter Execution Layer**.
    - Selesai melakukan riset dokumentasi API Lighter (Nonce, Scaling, SDK).
    - Pembuatan PRD & DoD awal untuk integrasi Lighter.
- **[2026-03-12]** Validasi Bear Market (Jan 2023 - Des 2023).
    - Hasil: Win Rate 57.14% secara keseluruhan, namun Bear Regime masih di 47.1%.
- **[2026-03-11]** Penyelesaian Phase 3 Binance Live Execution.
    - Implementasi Emergency Stop, Telegram Notifications, dan Status API.

### Februari 2026
- **[2026-02-27]** Re-training model MLP dengan input Cross-Feature HMM.
- **[2026-02-25]** Migrasi dari HMM tradisional ke **Bayesian Changepoint Detection (BCD)** sebagai Layer 1.

---

## 🔬 Riwayat Pengujian Terakhir (Validation Metrics)

### 1. Robustness Validation: Bear Market (2022-11-18 sd 2023-12-31)
*   **Metode**: Walk-forward backtest menggunakan data historical 4H yang belum pernah dilihat model (Out-of-Sample).
*   **Parameter**: Bobot 0.3/0.25/0.45, Margin $1,000, Leverage 15x.
*   **Hasil Performa**:
    *   **Total Return**: +49.2%
    *   **Win Rate (Overall)**: 57.14% (455 trades)
    *   **Sharpe Ratio**: 1.267
    *   **Max Drawdown**: -17.73% (Improvement dari v3 yang -22.48%)
*   **Metrik Operasional Tambahan**:
    *   **Profit Factor**: **1.296** (Setiap $1 kerugian tertutup oleh $1.29 keuntungan).
    *   **Avg Trade PnL**: +$48.70 per trade (Mencerminkan "edge" positif setelah biaya).
    *   **Exit Distribution**:
        *   **SL (Stop Loss)**: 32.5%
        *   **TP (Take Profit)**: 29.2%
        *   **TRAIL_TP (Trailing)**: 24.8% (Penjaga profit saat trend kuat).
        *   **TIME_EXIT (24h)**: 13.4% (Safety net jika market stagnant).
    *   **Avg Duration**: 8.5 jam (Sesuai dengan target scalping 2-candle cycles).
*   **Analisa Performa per Regime**:
    *   **Bull Regime**: 58.8% WR (Profit memuaskan)
    *   **Neutral Regime**: 64.2% WR (Performa terbaik, bot sangat stabil di sideways)
    *   **Bear Regime**: 47.1% WR (**Weak Spot**, win rate di bawah 50% menunjukkan model masih butuh tuning untuk kondisi crash agresif).

### 2. Bull Market Benchmarking (2024-01-01 sd 2026-03-04)
*   **Metode**: Perbandingan Fix #1 (L3 Counter-Signal) vs Baseline.
*   **Analisa Performa**:
    *   **Win Rate**: Naik dari 58.1% menjadi **60.1%** (+2.0%).
    *   **Sharpe Ratio**: Naik signifikan dari 2.248 menjadi **2.712** (+20.6%).
    *   **Kesimpulan**: Fix #1 berhasil mengurangi "fake entries" dengan menggunakan L3 sebagai rem saat terjadi ketidakcocokan data teknikal dengan rezim pasar.

---

## 🎯 Fokus Saat Ini: Integrasi Lighter.xyz
Membangun Layer Eksekusi untuk DEX L2 Lighter agar bot dapat beroperasi secara desentralisasi.

| Task | Status | Note |
|---|---|---|
| Riset Dokumentasi API Lighter | ✅ DONE | https://apidocs.lighter.xyz |
| PRD & DoD Lighter Execution | ✅ DONE | Fokus pada Nonce & Integer Scaling |
| **Phase 1: API Client & Connectivity** | ⏳ PLANNED | Setup REST/WSS Wrapper |
| **Phase 2: Order & Nonce Engine** | 📅 BACKLOG | Implementasi offline signing |

---

## ⚠️ Tantangan & Risiko (Watchlist)
- **Bear Market WR**: Win Rate di bear market (47.1%) perlu ditingkatkan agar lebih stabil.
- **Data Leakage Check**: Memastikan tidak ada lookahead bias pada model MLP v4.4.
- **Lighter Nonce Sensitivity**: Sistem nonce Lighter sangat ketat, butuh manajemen state yang presisi.

---

## 📅 Rencana Langkah Berikutnya (Action Items)
1.  **Phase 1 Lighter**: Setup `LighterExecutionGateway` yang mendukung Testnet.
2.  **MLP Deep-dive**: Analisis *feature importance* untuk memahami mengapa Bear Market WR rendah.
3.  **Cross-Validation**: Implementasi Walk-Forward kembali untuk memvalidasi bobot 0.3/0.25/0.45 di data 2022.

---
*Log ini diperbarui setiap kali ada perubahan signifikan pada arsitektur atau status proyek.*
