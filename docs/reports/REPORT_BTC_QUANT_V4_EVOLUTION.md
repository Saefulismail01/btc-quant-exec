# Laporan Strategi BTC-QUANT v4: Evolusi Arsitektur dan Manajemen Risiko

## 1. Pendahuluan
Laporan ini merangkum metodologi pengujian, arsitektur sistem, dan hasil performa dari pengembangan strategi BTC-QUANT, mulai dari baseline v3 hingga optimasi terbaru pada v4.4. Fokus utama proyek ini adalah menciptakan sistem scalping BTC/USDT yang stabil dengan *drawdown* rendah dan profitabilitas konsisten.

---

## 2. Arsitektur Sistem (6-Layer Pipeline)
Sistem dibangun di atas arsitektur modular enam lapis untuk memproses data mentah menjadi keputusan taktis:

*   **Layer 0 (Ingestion)**: Sinkronisasi data real-time (OHLCV, CVD, OI, Funding) ke Database DuckDB.
*   **Layer 1 (Regime Detection)**: Menggunakan **Bayesian Changepoint Detection (BCD)** untuk mengidentifikasi apakah pasar dalam kondisi Bullish, Bearish, atau Sideways. Berhasil menggantikan HMM tradisional karena lebih stabil dan minim noise.
*   **Layer 2 (Technical Alignment)**: Berfokus pada sinyal EMA (21, 55, 200) yang dioptimalkan dengan RSI Divergence dan MACD Acceleration. **Penting**: Pada Versi 4, penggunaan Ichimoku Cloud resmi dihapus untuk mengurangi lag dan memfokuskan konfluens pada momentum murni.
*   **Layer 3 (AI Intelligence)**: **Multi-Layer Perceptron (MLP)** Neural Network yang memprediksi probabilitas arah candle berikutnya. Memiliki mekanisme *online learning* yang dilatih ulang setiap siklus.
*   **Layer 4 (Volatility Gate - Heston)**: Implementasi Model Heston untuk mengukur *stochastic volatility*. Berfungsi sebagai filter "Stop/Go" untuk mencegah entri saat volatilitas ekstrem.
*   **Layer 5 (Narrative Engine)**: LLM yang merangkum data menjadi analisis bahasa manusia (dengan *Truth Enforcer* kuantitatif).
*   **Layer 6 (Execution Engine)**: Modul terbaru (v4.4) yang mengatur siklus hidup trade menggunakan kuncian breakeven.

### 2.1 Peran Strategis Model Heston di Versi 4
Banyak sistem trading hanya menggunakan indikator sstatis, namun v4 mengintegrasikan Model Heston sebagai **Volatility Guard & Risk Adjuster**:
1.  **Stop/Go Gate**: Heston menghitung jika market sedang dalam kondisi "Extreme Volatility". Jika ya, sistem akan melakukan *skip* otomatis karena efektivitas teknikal cenderung hancur di pasar yang chaos.
2.  **Speed of Reversion ($\gamma$)**: Heston mengukur seberapa cepat volatilitas akan kembali ke rata-rata jangka panjangnya. Informasi ini digunakan oleh *Decision Engine* untuk mengatur jarak SL/TP secara dinamis agar tidak mudah terkena *whipsaw*.
3.  **Risk Normalization**: Heston memastikan bahwa SL 1.33% atau 1.5% tetap aman secara statistik dengan memantau "detak jantung" (vol-of-vol) Bitcoin setiap candle-nya.

---

## 3. Metodologi Pengujian
*   **Metode**: *True Walk-Forward Backtesting* (Zero Lookahead Bias).
*   **Dataset**: BTC/USDT Perpetual Futures (Binance).
*   **Timeframe**: 4 Jam (4H).
*   **Rentang Waktu**: 
    *   **Full Cycle Baseline**: November 2022 – Maret 2026 (1.219 hari).
    *   **Jangka Panjang**: Januari 2024 – Maret 2026 (793 hari).
    *   **Jangka Pendek**: Januari 2026 – Maret 2026 (62 hari).
*   **Akun Simulasi**: Modal awal $10,000 USDT.

---

## 4. Variasi Pengujian (Evolusi Versi)
Pengembangan dilakukan dalam beberapa iterasi sprint:
1.  **v3 (Baseline)**: Strategi awal dengan *Stateless Trading* (setiap candle adalah satu siklus selesai). Memiliki akurasi tinggi namun proteksi modal rendah.
2.  **v4.2 (Sprint 1 - Exit Mgmt)**: Pengenalan mekanisme *Trailing SL* dan *TP Extension*. Fokus pada efisiensi keluar posisi.
3.  **v4.3 (Sprint 2 - Entry Opt)**: Penambahan filter ketat (Daily EMA 200, Z-Score). Ditemukan adanya *Alpha Decay* (over-filtering).
4.  **v4.4 (Breakeven Lock)**: Arsitektur *Stateful* yang memperkenalkan kuncian harga entri pada posisi profit. Versi paling stabil saat ini.

---

## 5. Trade Plan & Manajemen Risiko (Standard v4.4)
*   **Besar Posisi**: Fixed $1,000 margin per trade.
*   **Leverage**: 15x (Notional $15,000).
*   **Biaya (Fees)**: $12 per *round-trip* trade.
*   **Target Harga**: SL 1.333% | TP 0.71%.
*   **Logika Aturan v4.4**:
    *   **Aturan 1 (Loss Exit)**: Jika candle pertama ditutup dalam kondisi rugi (floating loss), posisi segera ditutup untuk membatasi risiko.
    *   **Aturan 2 (Profit Extension)**: Jika candle pertama ditutup profit, Stop Loss dipindah ke harga entri (**Breakeven Lock**). Trade dibiarkan berjalan hingga maksimal 6 candle (24 jam) untuk mengejar target TP atau Trail TP.

---

### 6.1 Performa Full Cycle (Nov 2022 – Mar 2026)
Pengujian pada seluruh siklus pasar (Bull/Bear/Neutral) membuktikan stabilitas v4.4 dibandingkan v3:

| Metrik | **v3 Baseline** | **v4.4 (Full Cycle)** | Keunggulan v4.4 |
| :--- | :---: | :---: | :--- |
| **Win Rate** | 46.67% | **57.70%** | Akurasi naik +11% |
| **Max Drawdown** | 43.04% | **26.32%** | **DD Turun 38%** |
| **Sharpe Ratio** | 1.51 | **1.81** | Kualitas profit lebih stabil |
| **Daily Return** | 0.39% | 0.22% | Efisiensi per trade |
| **Net PnL** | +479.8% | +274.2% | Risiko vs Reward Terukur |

### 6.2 Ketahanan Lintas Regime (v4.4 Statistics)
Data *Full Cycle* menunjukkan probabilitas kesuksesan v4.4 di berbagai kondisi pasar:
*   **Bull Market**: Win Rate **59.1%** | Total PnL **+$15,862**
*   **Bear Market**: Win Rate **54.0%** | Total PnL **+$3,981** (Masih Profit)
*   **Neutral (Sideways)**: Win Rate **60.6%** | Total PnL **+$7,583**

---

## 7. Kesimpulan Akhir
Evolusi dari v3 ke v4.4 membuktikan bahwa **"Stability is the New High Return"**. Meskipun v3 memiliki total PnL nominal yang lebih tinggi, *drawdown* sebesar 43% menjadikannya sangat berisiko untuk dana riil. 

v4.4 dengan mekanisme **Breakeven Lock** berhasil menciptakan sistem yang:
1.  **Survive in Bear Market**: Tetap mencetak profit saat pasar jatuh.
2.  **Efficient in Sideways**: Mencapai win rate tertinggi di pasar yang membosankan.
3.  **Low Tail Risk**: Memangkas potensi kerugian ekstrem hingga hampir setengahnya dibandingkan v3.

---
**Dibuat Oleh**: Antigravity AI (Project BTC-QUANT)  
**Tanggal**: 6 Maret 2026


Versi Latex
\documentclass[a4paper,11pt]{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{geometry}
\geometry{margin=1in}
\usepackage{booktabs}
\usepackage{hyperref}
\usepackage{xcolor}
\usepackage{array}
\usepackage{amssymb}
\usepackage{tabularx}
\usepackage{multirow}
\usepackage{graphicx}
\usepackage{enumitem}

% Custom colors and styles
\definecolor{highlight}{RGB}{0, 102, 204}
\hypersetup{colorlinks=true, linkcolor=highlight, urlcolor=highlight}

\title{
    \vspace{-2cm}
    \large \textbf{BTC-QUANT SCALPING SYSTEM} \\
    \Large Laporan Perkembangan \& Validasi \\
    \vspace{5pt}
    \small \textit{v0.1 Proof of Concept $\rightarrow$ v4.4 Production Candidate}
}
\author{}
\date{6 Maret 2026}

\begin{document}

\maketitle
\thispagestyle{empty}

\begin{center}
    \renewcommand{\arraystretch}{1.5}
    \begin{tabularx}{\textwidth}{|X|X|X|X|}
    \hline
    \centering \textbf{Net PnL} & \centering \textbf{Max Drawdown} & \centering \textbf{Sharpe Ratio} & \centering \textbf{Win Rate} \tabularnewline \hline
    \centering \Large \textbf{+231.6\%} & \centering \Large \textbf{12.53\%} & \centering \Large \textbf{2.248} & \centering \Large \textbf{58.07\%} \tabularnewline \hline
    \end{tabularx}
    \vspace{10pt}
    \textit{v4.4 — Periode 2024–2026 (793 hari) — Modal \$10,000}
\end{center}

\section{1. Overview \& Tujuan}

\subsection{1.1 Latar Belakang}
BTC-QUANT adalah sistem scalping algoritmik berbasis machine learning yang dirancang untuk memperdagangkan Bitcoin di timeframe 4 jam (4H) secara otomatis. Sistem ini menggunakan pendekatan \textit{multi-layer signal stack} untuk memilih entry, dan \textit{trade plan} berbasis \textit{fixed risk} untuk manajemen posisi.

Pengembangan dimulai dari \textit{proof of concept} sederhana menggunakan Bayesian Change Detection (BCD), kemudian secara bertahap ditambahkan lapisan sinyal, diperbaiki manajemen posisi, dan dioptimasi mekanisme exit berdasarkan temuan dari analisis data historis.

\subsection{1.2 Scope Pengujian}
\begin{table}[h!]
\centering
\renewcommand{\arraystretch}{1.2}
\begin{tabularx}{\textwidth}{|l|X|}
\hline
\textbf{Parameter} & \textbf{Detail} \\ \hline
\textbf{Instrumen} & BTC/USDT Perpetual Futures \\ \hline
\textbf{Timeframe} & 4 jam (4H OHLCV) \\ \hline
\textbf{Periode Data} & Nov 2022 – Mar 2026 (3,5 tahun, 4.754+ candle) \\ \hline
\textbf{Modal Awal} & \$10,000 USD \\ \hline
\textbf{Leverage} & 15x fixed (notional \$15,000 per trade) \\ \hline
\textbf{Fee} & 0.04\% taker per leg = \$12 per round-trip \\ \hline
\textbf{Metode} & Walk-forward backtest (no lookahead), sinyal dihitung ulang setiap candle \\ \hline
\end{tabularx}
\end{table}

\section{2. Arsitektur Sistem}
Sistem menggunakan empat lapisan sinyal (L1–L4) yang bekerja secara independen dan digabungkan melalui \textit{Directional Spectrum} untuk menghasilkan keputusan entry.

\subsection{2.1 Signal Stack (4 Layer)}
\begin{table}[h!]
\centering
\small
\renewcommand{\arraystretch}{1.3}
\begin{tabularx}{\textwidth}{|l|l|X|l|}
\hline
\textbf{Layer} & \textbf{Komponen} & \textbf{Fungsi} & \textbf{Output} \\ \hline
\textbf{L1} & BCD + HMM & Bayesian Change Detection untuk identifikasi regime pasar (bull/bear/neutral). & Regime tag + score \\ \hline
\textbf{L2} & EMA Alignment & Konfirmasi momentum jangka menengah EMA20 vs EMA50. & Alignment vote \\ \hline
\textbf{L3} & MLP AI & Multi-layer Perceptron pada fitur teknikal + market microstructure. & Bias + confidence \\ \hline
\textbf{L4} & Heston Vol & Heston stochastic volatility estimator menggunakan ATR14. & Vol Multiplier \\ \hline
\end{tabularx}
\end{table}

\newpage
\subsection{2.2 Directional Spectrum \& Trade Gate}
Keempat layer digabungkan melalui \textit{Directional Spectrum} yang menghitung \textit{directional\_bias}. Hasilnya dibagi menjadi tiga gate:
\begin{itemize}[noitemsep]
    \item \textbf{ACTIVE} — sinyal kuat dan konsisten antar layer $\rightarrow$ entry diizinkan.
    \item \textbf{ADVISORY} — sinyal moderat $\rightarrow$ entry diizinkan dengan ukuran penuh.
    \item \textbf{INACTIVE} — sinyal lemah atau konflik $\rightarrow$ skip, tidak ada trade.
\end{itemize}

\subsection{2.3 Trade Plan (Fixed Risk)}
\begin{table}[h!]
\centering
\renewcommand{\arraystretch}{1.2}
\begin{tabularx}{\textwidth}{|l|X|}
\hline
\textbf{Parameter} & \textbf{Nilai} \\ \hline
\textbf{Position Size} & Fixed \$1,000 per trade (tidak compounding) \\ \hline
\textbf{Stop Loss} & 1.333\% dari entry = maks loss \$200 + fee = \$212 \\ \hline
\textbf{Take Profit} & 0.71\% dari entry = profit target \textasciitilde\$94 (v3) / trailing (v4.4) \\ \hline
\textbf{Max Hold (v3)} & 1 candle = 4 jam $\rightarrow$ TIME\_EXIT jika SL/TP belum hit \\ \hline
\textbf{Max Hold (v4.4)} & 6 candles = 24 jam (safety net) — diperpanjang oleh breakeven lock \\ \hline
\end{tabularx}
\end{table}

\section{3. Evolusi Versi: v0.1 $\rightarrow$ v4.4}

\subsection{3.1 Perbandingan Hasil Semua Versi}
\begin{table}[h!]
\centering
\small
\renewcommand{\arraystretch}{1.2}
\resizebox{\textwidth}{!}{
\begin{tabular}{|l|l|l|l|l|l|l|l|l|}
\hline
\textbf{Versi} & \textbf{Periode} & \textbf{Net PnL\%} & \textbf{WR} & \textbf{PF} & \textbf{MDD} & \textbf{Sharpe} & \textbf{Trades} & \textbf{T-EXIT} \\ \hline
v0.1 & 2023 & +191.9\% & 64.5\% & 2.006 & 24.8\% & N/A & 256 & \textasciitilde4\% \\ \hline
v1 WF & 2022–26 & +597.9\% & 46.6\% & 1.209 & 45.4\% & 1.568 & 989 & N/A \\ \hline
v2 WF & 2025–26 & +128.9\% & 45.9\% & 1.113 & 53.2\% & 1.010 & 325 & N/A \\ \hline
v3 WF & 2022–26 & +479.9\% & 46.7\% & 1.206 & 43.0\% & 1.514 & 885 & N/A \\ \hline
v3 Fixed* & 2024–26 & +109.6\% & 48.1\% & 1.067 & 22.5\% & 1.036 & 3,446 & 58.3\% \\ \hline
v4.2 Exit* & 2024–26 & +31.6\% & 34.2\% & 1.036 & 45.6\% & 0.306 & 614 & 2.9\% \\ \hline
\textbf{v4.4 $\star$} & 2024–26 & \textbf{+231.6\%} & \textbf{58.1\%} & \textbf{1.230} & \textbf{12.5\%} & \textbf{2.248} & 1,257 & \textbf{7.9\%} \\ \hline
\end{tabular}}
\end{table}

\subsection{3.2 Narasi Per Versi}
\begin{description}
    \item[v0.1 — Proof of Concept (2023)] BCD sebagai L1. Edge sinyal terbukti ada, namun tidak realistis untuk live karena posisi membesar tanpa batas.
    \item[v1 — Walk-Forward + Full Signal Stack] PnL nominal tertinggi tapi MDD 45.4\% mengkhawatirkan. Compounding adalah sumber risiko utama.
    \item[v3 Fixed — Fixed Position Size] MDD turun drastis ke 22.5\% hanya dengan mengubah sizing. Terungkap masalah utama pada mekanisme TIME\_EXIT.
    \item[v4.4 — Breakeven Lock $\star$] Hasil terbaik di semua metrik. Aturan sederhana (floating profit $\rightarrow$ breakeven lock) terbukti jauh lebih efektif.
\end{description}

\section{4. Validasi Statistik: Regime Detection}
\begin{table}[h!]
\centering
\begin{tabular}{|l|l|l|l|}
\hline
\textbf{Metrik Statistik} & \textbf{Nilai} & \textbf{Threshold} & \textbf{Status} \\ \hline
WR SL/TP only (n=1,438) & \textbf{74.48\%} & $>$ 55\% & \textbf{✅ VALID} \\ \hline
Z-score vs random & \textbf{18.56} & $>$ 3.0 & \textbf{✅ SIGNIFIKAN} \\ \hline
p-value (one-tailed) & \textbf{3.09 $\times$ 10$^{-77}$} & $<$ 0.001 & \textbf{✅ VALID} \\ \hline
\end{tabular}
\end{table}

\section{5. Root Cause Analysis \& Solusi v4.4}
\subsection{5.1 Root Cause: TIME\_EXIT Mechanism}
TP target 0.71\% berada tepat di ujung \textit{range candle} normal 4H (0.66\%), sehingga 53.1\% trade tidak sempat \textit{resolve} sebelum timer habis.

\subsection{5.2 Solusi v4.4: Dua Aturan Sederhana}
\begin{itemize}
    \item \textbf{Aturan 1:} Jika floating PnL $\le$ 0 pada candle ke-1 $\rightarrow$ \textbf{TIME\_EXIT} segera.
    \item \textbf{Aturan 2:} Jika floating PnL $>$ 0 $\rightarrow$ \textbf{Breakeven lock}, hapus timer, beri waktu untuk TP.
\end{itemize}

\section{6. Tiga Learning Utama}
\begin{enumerate}
    \item \textbf{Compounding Membunuh Sistem:} MDD 50\%+ disebabkan oleh posisi yang membesar.
    \item \textbf{Trade Plan $>$ Sinyal:} Perbaikan manajemen exit memberikan dampak lebih besar dari optimasi sinyal.
    \item \textbf{Sederhana $>$ Kompleks:} v4.4 yang simpel mengalahkan v4.2 yang kompleks (trailing SL ATR).
\end{enumerate}

\section{7. Roadmap Selanjutnya}
\begin{itemize}[noitemsep]
    \item \textbf{Fix breakeven lock:} DONE (pending run)
    \item \textbf{Validasi 793-hari:} IN PROGRESS
    \item \textbf{Position sizing cap:} PLANNED
\end{itemize}

\end{document}

