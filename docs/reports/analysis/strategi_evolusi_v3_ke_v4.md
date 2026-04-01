# Analisis Komprehensif Evolusi Strategi BTC-QUANT (v3 s/d v4.3)

---

## 📊 Ringkasan Performa Lintas Generasi

Berikut adalah perbandingan metrik utama dari tiga fase pengembangan besar sistem BTC-QUANT:

| Metrik Utama | **v3 Baseline** (Statis) | **v4.2 Sprint 1** (Exit Mgmt) | **v4.3 Sprint 2** (Entry Opt) |
| :--- | :---: | :---: | :---: |
| **Status Strategi** | Stable Legacy | **Golden Standard** | Experimental (Regresi) |
| **Win Rate** | **46.67%** | 40.00% | 34.37% |
| **R:R Ratio** | 1 : 1.38 | **1 : 2.28** | 1 : 1.64 |
| **Profit Factor** | 1.206 | **1.518** | 0.82 (Estimasi) |
| **Max Drawdown** | 43.04% | **13.20%** | - |
| **Daily Return** | 0.394% | **0.447%** | Negatif |
| **Fokus Utama** | Akurasi Entri | Proteksi Modal & Profit Run | Filter Ketat & Momentum |

---

## 🔍 Analisa Detail per Fase

### 1. Fase v3: Akurasi Tinggi, Risiko Eksponensial
Versi ini mengandalkan akurasi entri yang solid (47%). Namun, tanpa manajemen exit yang dinamis, sistem ini sangat rentan terhadap pembalikan harga yang tajam.
*   **Keunggulan**: Sinyal entri sangat tajam dalam menangkap pergerakan awal.
*   **Kelemahan**: Drawdown sebesar 43% adalah risiko sistemik yang tidak bisa diterima untuk *live trading* skala besar. Kerugian yang besar memakan waktu terlalu lama untuk dipulihkan.

### 2. Fase v4.2 (Sprint 1): Kemenangan Manajemen Risiko
Implementasi *Trailing SL* dan *TP Extension* di fase ini membuktikan bahwa **"How you exit is more important than how you enter."**
*   **Efek Trailing SL**: Meskipun *Win Rate* turun secara alami (dari 46% ke 40%) karena banyak trade yang terhenti di posisi breakeven, efisiensi modal meningkat drastis.
*   **Hasil**: *Profit Factor* naik menjadi 1.518 dan yang paling krusial, *Max Drawdown* ditekan hingga ke level aman 13.2%. Ini adalah titik di mana strategi menjadi layak digunakan untuk dana besar.

### 3. Fase v4.3 (Sprint 2): Jebakan Optimasi Berlebihan (*Over-Filtering*)
Pada fase terbaru, penambahan filter berlapis (Master Scoring, Daily Trend Blocker, Z-Score) justru membawa hasil negatif.
*   **Fenomena Alpha Decay**: Filter yang terlalu ketat menghilangkan peluang profit yang seharusnya ditangkap oleh mesin manajemen exit v4.2. 
*   **Analisa Kegagalan**: Ambang batas entri yang terlalu tinggi (+5/7) menyebabkan sistem hanya masuk di akhir tren (*late entry*), sehingga sering terkena koreksi tajam.

---

## 💡 Kesimpulan & Pelajaran Utama

1.  **Prioritas Risiko**: Penurunan drawdown dari 43% ke 13% di v4.2 adalah keberhasilan terbesar proyek ini. Keamanan modal jauh lebih berharga daripada kenaikan win rate 5%.
2.  **R:R adalah Kunci**: Dengan R:R 1 : 2.28 (v4.2), strategi tetap profitabel meskipun akurasi hanya di angka 35-40%. Ini memberikan ruang nafas yang besar bagi sistem di kondisi market bergejolak.
3.  **Hati-hati dengan Filter**: Menambah indikator (v4.3) tidak selalu meningkatkan performa. Kadang indikator yang terlalu banyak justru menciptakan kontradiksi sinyal yang melumpuhkan performa sistem secara keseluruhan.

---

## 🚀 Rekomendasi Langkah Selanjutnya

1.  **Rollback ke Logika v4.2**: Tetapkan v4.2 sebagai "Master Branch" untuk parameter eksekutif.
2.  **Iterasi Ringan pada Entri**: Jangan gunakan filter "Hard Blocker" seperti Daily EMA 200, melainkan gunakan sebagai pembobot skor tambahan agar sistem tetap bisa mengambil peluang *counter-trend* yang berkualitas.
3.  **Fokus pada Frekuensi**: Daripada mencoba menaikkan win rate kembali ke 46%, lebih baik fokus pada peningkatan jumlah trade per hari di atas 1.0 agar target profit harian 1-3% dapat tercapai secara statistik.

---
**Status Dokumen**: Final Analysis  
**Tanggal**: 5 Maret 2026  
**Engineer**: Antigravity AI (BTC-QUANT Team)
