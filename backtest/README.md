# Index Dokumentasi Backtest (BTC-Quant)

Halaman ini merangkum seluruh pengujian (backtest) yang telah dilakukan, diurutkan berdasarkan versi dan jenis pengujian untuk memudahkan penelusuran hasil.

## 📁 Struktur Folder
- `data/`: Dataset historis BTC/USDT (4H) untuk setiap tahun.
- `results/`: Hasil eksekusi strategi (CSV, JSON, Report) dengan prefix versi.
- `logs/`: Log teknis proses backtest (dikelompokkan per versi).
- `scripts/`: Skrip Python untuk menjalankan dan menganalisis hasil backtest.

---

## 🚀 Riwayat Pengujian (Versioning)

### [V1] Full System Confluence (True Walk-Forward)
**Tanggal:** 2026-03-03  
**Fokus:** Simulasi lengkap 6 Layer (L1-L6) dengan modal USD 10,000.  
**File Hasil:**
- Trade Log: `results/v1_walkforward_trades.csv`
- Laporan Utama: `results/v1_walkforward_report.md`
- Ekuitas: `results/v1_walkforward_equity.csv`
- Leverage Test: `results/calculate_leveraged_return.py`

### [V1-Ablation] Studi Komponen Layer
**Tanggal:** 2026-03-03  
**Fokus:** Membandingkan efektivitas tiap layer (L1 saja vs L1+L2 vs Full).  
**File Hasil:**
- Folder: `results/ablation/`
- Summary L1 (v1.1): `results/ablation/v1_ablation_l1_summary.json`
- Summary L1+L2 (v1.2): `results/ablation/v1_ablation_l12_summary.json`

### [V0.1-Experimental] Preliminary & Isolated Tests
**Fokus:** Riset awal komponen individu (HMM, BCD, Spectrum).  
**File Hasil:**
- Folder: `results/preliminary/`
- BCD Analysis: `results/v0.1_experimental_bcd_analysis.md`
- HMM Test: `results/preliminary/hmm_power_test_decision.md`
- Distribution: `results/preliminary/return_distribution_by_regime.csv`

---

## 📊 Metrik Utama (V1)
- **Net PnL:** +597.89%
- **Win Rate:** 46.61%
- **Profit Factor:** 1.209
- **Risk per Trade:** 2.0% (Adaptive ATR)
- **Realized RR:** 1 : 1.38

---
*Catatan: Setiap pengujian baru wajib mencantumkan versi berikutnya (V2, V3, dst) dan memperbarui file index ini.*
