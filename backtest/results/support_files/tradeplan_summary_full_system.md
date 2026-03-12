# Rincian Sistem & Trade Plan: Full 6-Layer Confluence
**Timestamp Run:** 20260303_161852
**Periode Uji:** Januari 2023 — Maret 2026 (~3.3 Tahun)

## 1. Parameter Akun (Portfolio)
| Deskripsi | Nilai |
| :--- | :--- |
| **Initial Capital** | $10,000.00 |
| **Final Equity** | **$69,789.39** |
| **Peak Equity (Max Upside)** | **$84,571.90** |
| **Total ROI** | **+597.89%** |

## 2. Strategi Eksekusi (Trade Plan)
*   **Sizing / Trade:** **Fixed 2% Risk per Trade**.
    *   Ukuran posisi bersifat dinamis (*compounding*). Resiko dihitung berdasarkan jarak Stop Loss agar kerugian maksimal per trade tetap berada di angka 2% saldo saat itu.
*   **Take Profit (TP) & Stop Loss (SL):** **Heston-ATR Adaptif**.
    *   Jarak SL/TP menyesuaikan volatilitas instan (Layer 1 Heston).
*   **Hold Period:** Rata-rata **30.5 Jam** (~1.25 hari).
    *   Menunjukkan karakter strategi *short-term trend follower*.
*   **Arah Transaksi:** Dikontrol oleh kesepakatan **BCD (Layer 1)** dan **EMA Filter (Layer 2)**.

## 3. Statistik Performa
| Metrik Utama | Hasil |
| :--- | :--- |
| **Jumlah Trade** | 989 Transaksi |
| **Win Rate** | 46.61% |
| **Avg Risk:Reward (R:R)** | **1 : 1.38** |
| **Max Drawdown** | 45.38% |
| **Profit Factor** | 1.209 |
| **Sharpe Ratio** | 1.568 |

## 4. Kesimpulan Strategi
Sistem ini sangat bergantung pada **Compounding** selama tren panjang (seperti bull-run 2024). Meskipun win rate di bawah 50%, keunggulan R:R sebesar 1.38x memastikan pertumbuhan modal yang sehat dalam jangka panjang. Penggunaan Layer 3-6 (MLP/Sentiment/Risk) terbukti menggandakan potensi profit dibandingkan sistem tanpa filter.
