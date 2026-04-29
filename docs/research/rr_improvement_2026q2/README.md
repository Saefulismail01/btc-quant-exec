# Riset: Peningkatan R:R via Exhaustion Layer & Asymmetric Exit

**Arsip proses penuh (fase, keputusan, file index, next steps):** [`PROCESS_DOCUMENTATION.md`](./PROCESS_DOCUMENTATION.md)

**Status:** Discovery selesai untuk Tier 0 *design + proposal*; **implementasi produksi** (port branch, migrate DB, wire worker) belum.
**Owner (lead analyst):** Agent diskusi (Claude / Cursor)
**Owner (data gathering):** Sub-agent (kamu yang membaca file ini)
**Last updated:** 2026-04-24

---

## 1. Konteks & Latar Belakang

Sistem `btc-scalping-execution_layer` saat ini memakai arsitektur multi-layer:

| Layer | Komponen | Fungsi |
|---|---|---|
| L1 | Bayesian Changepoint Detection (BOCPD) | Regime macro |
| L2 | Indikator teknikal | Voting arah |
| L3 | MLP | Klasifikasi/scoring akhir |
| L4 | Volatilitas | (perlu diverifikasi) |
| L5 | Execution management | Sizing, SL/TP, order placement |

**Performa live (Mar–Apr 2026):**
- Win rate 75.9% (Long 75.0%, Short 82.4%)
- TP 0.71% / SL 1.333% → R:R = **0.53** (loss 1.88× lebih besar dari win)
- EV per trade ≈ +0.22% (positif tapi tipis)
- Total PnL adjusted: +$20.37 dari 54 posisi

**Hipotesis yang sedang divalidasi (oleh lead analyst):**

> Karena L1 (BOCPD), L2 (teknikal), dan L3 (MLP yang kemungkinan inherit fitur lagging) semuanya bersifat *trailing*, sistem secara struktural buta terhadap titik exhaustion/puncak. Akibatnya: bot streak win di trend, lalu kehilangan satu trade besar di reversal yang tidak terdeteksi.

**Dua arah solusi yang dipertimbangkan:**

1. **Exhaustion Layer baru** — pakai data non-derivatif-harga (CVD, funding, OI, liquidation, HTF stretch) sebagai *veto/sizing modifier*, bukan signal generator.
2. **Asymmetric Exit** — partial TP + trailing stop untuk memperbaiki R:R tanpa mengubah model.

Sebelum desain layer baru, kita butuh **bukti empiris** apakah hipotesis di atas benar dan layer mana yang ROI-nya tertinggi.

---

## 2. Mission untuk Sub-Agent

Tugasmu adalah **gathering & first-pass analysis**. Kamu **bukan** mendesain solusi atau mengubah kode produksi. Output kamu akan dipakai lead analyst untuk memutuskan arsitektur layer baru.

**Prinsip:**
- Read-only terhadap kode produksi (kecuali di folder `docs/research/rr_improvement_2026q2/` ini)
- Kalau perlu jalankan script analisis, taruh di `docs/research/rr_improvement_2026q2/scripts/`
- Output analisis taruh di `docs/research/rr_improvement_2026q2/findings/`
- Setiap klaim numerik harus disertai **sumber file + lokasi line / SQL query**
- Kalau data tidak tersedia, **katakan "TIDAK TERSEDIA" dengan alasan** — jangan ngarang
- Kalau ragu antara dua interpretasi, sajikan keduanya, jangan pilih sendiri

---

## 3. Investigation Areas

Ada **7 area** yang perlu diverifikasi. Prioritas urut dari yang paling penting.

### Area A — Arsitektur Multi-Layer (Pemahaman Konstrain)

**Kenapa penting:** Sebelum nambah layer, harus tahu bentuk presisi setiap layer existing supaya layer baru bisa di-wire dengan benar.

**Pertanyaan yang harus dijawab:**

#### A.1 Layer 1 — BOCPD
- File implementasi utama? (kemungkinan `src/layers/l1_*` atau sejenis — verifikasi)
- Hyperparameter: hazard rate, prior distribution (apa? Student-t? Gaussian?)
- Output ke layer berikutnya: regime label diskrit, run-length distribution, atau probability of changepoint?
- Frekuensi update (per candle? per detik?)
- Apakah ada kalibrasi/validasi historis terhadap regime aktual?
- Lookback window?

#### A.2 Layer 2 — Teknikal
- Daftar lengkap indikator yang dipakai
- Parameter masing-masing
- Mekanisme aggregation: voting, weighted sum, atau rule-based?
- Output: arah (long/short/flat), score kontinu, atau confidence?
- Apakah ada filter timeframe (HTF confirmation)?

#### A.3 Layer 3 — MLP
- **PALING PENTING:** Definisi label/target — apa yang diprediksi?
  - Next-candle direction?
  - TP-hit-before-SL?
  - Multi-class regime?
  - Continuous PnL forecast?
- Arsitektur (hidden layers, neurons, activation, dropout)
- Daftar input feature lengkap
- Training data range (tanggal mulai-akhir)
- Train/val/test split metodologi (random? walk-forward? purged k-fold?)
- Performance metrics terakhir: precision, recall, AUC, log-loss
- Calibration check: apakah probabilitas 0.7 dari MLP benar-benar berarti 70% chance? (reliability diagram)
- Inference latency
- File model artifact disimpan di mana?
- File training pipeline?

#### A.4 Layer Volatilitas
- Model apa: Heston (sesuai nama strategy lama), GARCH, realized vol, ATR-based?
- Output: vol forecast (single value), regime cluster (diskrit), atau distribution?
- Bagaimana digunakan di production: sizing, SL/TP adaptive, atau cuma logging?
- File implementasi

#### A.5 Layer Execution
- File handler utama (lighter gateway? `src/execution/*`?)
- Logika sizing: fixed margin × leverage, Kelly, vol-targeting?
- Logika SL/TP: fixed %, ATR multiplier, adaptive?
- Apakah ada partial TP / trailing stop di codebase (mungkin disabled)?
- Order types yang dipakai: limit, market, stop?
- Slippage handling

**Output yang diharapkan untuk Area A:**
File `findings/A_architecture_inventory.md` berisi tabel ringkas + diagram alur signal dari L1 → execution + path file untuk setiap layer.

---

### Area B — Data Availability (Feasibility Check)

**Kenapa penting:** Lead analyst mengasumsikan akses ke CVD, OI, funding, liq, HTF (berdasarkan jawaban user "punya"). Perlu verifikasi konkret: punya berapa lama, granularitas berapa, bisa diakses real-time atau historis-only.

**Untuk setiap data source di bawah, jawab format ini:**

```
Source: [nama]
Provider/exchange: [Lighter, Binance, Coinglass, dll]
Path/connector di codebase: [file]
Granularity: [tick / 1s / 1m / 5m / 1h]
Historical depth: [tanggal mulai - sekarang]
Real-time available: [yes/no, latency berapa]
Storage: [DuckDB table / parquet / API call]
Sample query: [contoh cara akses]
```

**Data yang harus diverifikasi:**

- B.1 OHLCV BTC perpetual (timeframe yang sudah ada: 1m, 5m, 15m, 1h, 4h, 1d?)
- B.2 CVD / cumulative volume delta
- B.3 Order book snapshot / L2 depth
- B.4 Open Interest BTC perpetual
- B.5 Funding rate (per exchange)
- B.6 Liquidation data (per exchange / aggregate)
- B.7 Spot vs perp basis (premium/discount)
- B.8 BTC dominance / total market cap (kalau dipakai sebagai macro context)
- B.9 News/event calendar (FOMC, CPI dates) — manual atau ada feed?

**Output:** `findings/B_data_inventory.md`

---

### Area C — Trade Log & Telemetry Schema

**Kenapa penting:** Empirical analysis di Area D-F sangat tergantung pada apa yang tersimpan di trade log. Kalau snapshot indikator pada saat entry tidak tersimpan, analisis conditional WR per regime tidak bisa dilakukan retroaktif (harus replay engine).

**Pertanyaan:**

- C.1 Lokasi trade log production: DuckDB? Path file? Tabel apa?
- C.2 Schema lengkap tabel trades: list semua kolom + tipe data
- C.3 Apakah disimpan: entry timestamp, exit timestamp, side, size, entry price, exit price, fees, realized PnL, exit reason (TP/SL/manual/time)?
- C.4 Apakah disimpan **snapshot signal state pada saat entry**:
  - L1 regime label / probability
  - L2 indicator values
  - L3 MLP score
  - Volatility forecast
  - ATR pada entry
- C.5 Apakah disimpan **MFE/MAE** (Maximum Favorable/Adverse Excursion) per trade?
- C.6 Apakah ada audit log tick-by-tick PnL selama posisi terbuka?
- C.7 CSV export Lighter ada di `docs/reports/data/` — periode coverage?
- C.8 Total jumlah trade closed yang available untuk analisis

**Output:** `findings/C_trade_log_schema.md` berisi schema, sample 5 baris, dan **gap analysis** (apa yang BELUM tersimpan padahal dibutuhkan).

---

### Area D — Empirical Loss Pattern Analysis

**Kenapa penting:** Lead analyst butuh tahu apakah loss benar-benar cluster di "puncak" atau menyebar acak. Kalau acak, hipotesis exhaustion-blindspot salah dan strategi mitigasi berubah.

**Analisis yang diminta** (asumsikan trade log lengkap; kalau tidak, sebut keterbatasannya):

#### D.1 Distribusi loss berdasarkan posisi-dalam-streak
- Group loss berdasarkan: "ini loss ke berapa setelah berapa win berturut-turut hari itu?"
- Tabel: `n_wins_before_loss` → `count`, `avg_loss_pct`
- Kalau pola "loss after long streak" lebih besar dari random expectation → bukti hipotesis kuat

#### D.2 Holding time distribution
- Histogram durasi posisi (entry → exit)
- Split: winner vs loser
- Median, p25, p75, p95
- Per-side (long vs short)

#### D.3 MFE/MAE analysis (kalau data tersedia)
- Untuk setiap trade: berapa max profit yang sempat tersedia sebelum exit?
- Untuk winner: rata-rata berapa % MFE vs final PnL? (berapa banyak profit yang "ditinggalkan" karena TP terlalu tight?)
- Untuk loser: berapa MAE vs SL? (apakah loss kena di harga ekstrem atau modest)

#### D.4 Time-of-day & day-of-week heatmap
- WR & avg PnL per jam UTC
- WR & avg PnL per hari dalam minggu
- Identify: ada jam/hari problematik?

#### D.5 Side bias di kondisi tertentu
- Apakah long-loss cluster di kondisi yang berbeda dari short-loss?

**Output:** `findings/D_loss_pattern_analysis.md` + plots di `findings/plots/D_*.png` (kalau scripting feasible)

---

### Area E — Conditional Performance vs Exhaustion Proxies

**Kenapa penting:** Ini bukti utama untuk justifikasi exhaustion layer. Kalau WR di kondisi "exhausted" (funding tinggi, HTF stretched, dll) jauh lebih rendah dari baseline → layer baru worth dibangun.

**Untuk setiap proxy di bawah, hitung conditional WR & avg PnL per bucket:**

#### E.1 Funding rate bucket
- Bagi funding rate pada saat entry ke quintile (atau threshold: <0%, 0–0.01%, 0.01–0.05%, >0.05%)
- WR & avg PnL per bucket, split long/short

#### E.2 HTF z-score bucket (price stretch)
- Hitung z-score harga entry vs EMA-50 di 4H (dalam unit ATR-4H)
- Bucket: <-2, -2..-1, -1..1, 1..2, >2
- WR & avg PnL per bucket

#### E.3 OI delta vs price delta divergence
- 24h sebelum entry: apakah price ↑ + OI ↓ (atau sebaliknya)?
- Flag boolean: divergence yes/no
- WR conditional pada flag

#### E.4 CVD divergence flag
- Definisi sederhana: di window 1h sebelum entry, apakah price HH tapi CVD LH (untuk long) atau price LL tapi CVD HL (untuk short)?
- WR conditional pada flag

#### E.5 Streak position
- WR pada trade ke-1, ke-2, ke-3, ke-4+ dalam satu hari (consecutive same-direction)

#### E.6 Volatility regime
- Pakai output Layer Volatilitas (atau ATR percentile rolling 30 hari)
- Bucket: low / medium / high vol
- WR per bucket

**Output:** `findings/E_conditional_performance.md` berisi tabel-tabel + interpretasi singkat *per bucket* (jangan rekomendasi solusi, biarkan lead analyst yang putuskan).

**Catatan statistik:** sebut sample size per bucket. Kalau bucket cuma punya 3-5 trade, **flag sebagai "tidak signifikan secara statistik"** dengan jelas.

---

### Area F — Asymmetric Exit Feasibility

**Kenapa penting:** Salah satu kandidat solusi adalah partial TP + trailing. Perlu verifikasi: (a) apakah secara historis simulasi simple ini akan meningkatkan EV; (b) apakah engine eksekusi support partial close & trailing.

#### F.1 Engine capability check
- Lighter SDK support partial close? (verifikasi dari `src/execution/lighter_*` atau sejenis)
- Trailing stop server-side atau harus di-emulate client-side?
- Kalau emulate client-side: apa frekuensi polling? Apakah ada risk gap?

#### F.2 Counterfactual simulation (offline, dari trade log + OHLCV)
**Skenario simulasi:**

1. **Baseline (current):** TP 0.71%, SL 1.333%
2. **Skenario A (partial TP):** TP1 0.4% close 60%, sisa SL pindah ke BE, trail 3×ATR
3. **Skenario B (full trail):** SL 1.333%, no fixed TP, trail dari entry pakai chandelier exit (3×ATR-22)
4. **Skenario C (partial + wider TP2):** TP1 0.4% close 50%, TP2 1.5% close 50%

Untuk setiap skenario, hitung:
- Total PnL
- Win rate (sebut definisi win: any profit / hit TP1 / hit TP2)
- Max drawdown
- Profit factor
- Avg winner / avg loser
- Sharpe (asumsikan 0 risk-free)

**Output:** `findings/F_asymmetric_exit_simulation.md` berisi tabel komparasi.

**Catatan penting:** Simulasi ini **butuh tick-level atau setidaknya 1m OHLCV** selama posisi terbuka untuk akurat. Kalau cuma punya 5m, sebut keterbatasannya (misal: trailing stop bisa false-trigger di intra-candle).

---

### Area G — MLP Specific Deep Dive

**Kenapa penting:** Kalau MLP overfit / di-train dengan label yang bias trend-following, fixing MLP-nya bisa jadi solusi paling impactful. Ini sub-investigasi paling teknis.

#### G.1 Training data temporal coverage
- Range tanggal: berapa banyak regime berbeda tercakup?
- Berapa % data train dari pasar bull, bear, choppy?

#### G.2 Feature importance
- Kalau ada (SHAP, permutation importance, atau simple weight magnitudes): top 10 feature
- Apakah feature didominasi oleh derivatif harga (lagging)?

#### G.3 Out-of-sample performance vs in-sample
- Train metrics vs test/val metrics — gap berapa?
- Performance per regime (kalau bisa dipisah)

#### G.4 Calibration
- Reliability diagram atau kalimat singkat: "MLP score 0.7 → actual win rate berapa pada test set?"

#### G.5 Confusion vs market regime
- Cross-tab: prediksi MLP vs aktual outcome, dipisah per regime BOCPD
- Identify: apakah MLP mis-classify lebih banyak di regime tertentu?

**Output:** `findings/G_mlp_deep_dive.md`

**Catatan:** Untuk Area G, jangan re-train model. Cukup analisis artifact + log training existing. Kalau dokumentasi training tidak ada, sebut sebagai **gap dokumentasi**.

---

## 4. Output Format & Struktur Folder

Buat struktur ini di `docs/research/rr_improvement_2026q2/`:

```
rr_improvement_2026q2/
├── README.md                          ← file ini (jangan diubah)
├── PROGRESS.md                        ← log progress harian agent (buat & update)
├── findings/
│   ├── A_architecture_inventory.md
│   ├── B_data_inventory.md
│   ├── C_trade_log_schema.md
│   ├── D_loss_pattern_analysis.md
│   ├── E_conditional_performance.md
│   ├── F_asymmetric_exit_simulation.md
│   ├── G_mlp_deep_dive.md
│   ├── SUMMARY.md                     ← rangkuman eksekutif (1-2 halaman) untuk lead analyst
│   └── plots/
│       └── *.png
├── scripts/                           ← script analisis ad-hoc (Python)
│   └── *.py
└── data/                              ← intermediate dataset (parquet/csv)
    └── *.parquet
```

### Format setiap file `findings/X_*.md`:

```markdown
# [Title]

**Area:** X — [nama area]
**Status:** [Complete / Partial / Blocked]
**Updated:** YYYY-MM-DD

## TL;DR
[2-3 kalimat: temuan paling penting]

## Methodology
[Sumber data, query/script yang dipakai, asumsi]

## Findings
[Tabel + narasi. Setiap angka cite source]

## Gaps & Limitations
[Apa yang TIDAK bisa dijawab dan kenapa]

## Raw Sources
[Path file, query SQL, line numbers]
```

### Format `SUMMARY.md`:

Maksimal 2 halaman, struktur:

1. **Hipotesis tervalidasi / tidak** — 1 paragraf per hipotesis utama
2. **Top 3 actionable insight** — masing-masing dengan bukti numerik
3. **Top 3 gap data/tooling** yang harus ditutup sebelum desain layer
4. **Rekomendasi prioritas** untuk lead analyst (asymmetric exit dulu vs exhaustion layer dulu)

### Format `PROGRESS.md`:

Update setiap session dengan format:

```markdown
## YYYY-MM-DD HH:MM
- Done: [apa yang selesai]
- In progress: [yang sedang dikerjakan]
- Blocked: [butuh input lead analyst untuk apa]
- Next: [rencana berikutnya]
```

---

## 5. Constraints & Don'ts

- ❌ **Jangan mengubah kode produksi** di `src/`, `engine/`, atau direktori execution lainnya
- ❌ **Jangan menjalankan bot live** atau mengirim order ke exchange
- ❌ **Jangan retrain model MLP** atau ubah artifact model existing
- ❌ **Jangan menarik kesimpulan strategi** — hanya laporkan temuan + gaps
- ❌ **Jangan mengarang angka** kalau data tidak tersedia, sebut "TIDAK TERSEDIA"
- ✅ Boleh menulis script read-only / analysis di `scripts/`
- ✅ Boleh query DuckDB read-only
- ✅ Boleh fetch historical data baru dari exchange API (dengan rate limit hati-hati)
- ✅ Boleh menulis di `docs/research/rr_improvement_2026q2/**`

---

## 6. Eskalasi ke Lead Analyst

Stop dan minta klarifikasi (tulis di `PROGRESS.md` section "Blocked") kalau menemui:

1. Trade log corrupt atau schema tidak konsisten
2. Conflict antara dokumentasi & implementasi aktual
3. Kebutuhan data yang tidak tersedia & butuh keputusan: skip vs fetch dari source baru
4. Hasil analisis menunjukkan hipotesis lead analyst kemungkinan **salah** — laporkan dengan bukti, jangan paksakan narasi
5. Sample size terlalu kecil untuk kesimpulan signifikan — flag eksplisit

---

## 7. Ringkasan Prioritas (untuk eksekusi cepat)

Kalau waktu terbatas, urutan prioritas:

1. **Area C** (schema trade log) — prerequisite untuk semua analisis lain
2. **Area A** (arsitektur inventory) — prerequisite untuk desain layer baru
3. **Area D.1, D.2** (loss pattern dasar) — validasi hipotesis utama
4. **Area E.1, E.2, E.5** (conditional WR di funding, HTF stretch, streak) — bukti kunci exhaustion layer
5. **Area F.2** (asymmetric exit simulation) — kandidat solusi termurah
6. **Area B** (data inventory) — untuk feasibility layer baru
7. **Area G** (MLP deep dive) — bisa di-defer kalau A-F sudah cukup
8. **Sisanya** (D.3-D.5, E.3-E.4, E.6) — nice to have

Estimasi effort: 1 sub-agent fokus penuh ≈ 2-3 sesi panjang.

---

**End of brief. Mulai dengan membuat `PROGRESS.md` dan kerjakan Area C dulu.**
