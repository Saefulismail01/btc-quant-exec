# 📊 Evaluasi Cycle Theory untuk BTC-QUANT Scalper

**Tanggal:** 3 Maret 2026  
**Sumber:** `docs/research/cycle_theory.md` (dokumen teori asli)  
**Status:** ❌ TIDAK DIIMPLEMENTASI — tidak cocok untuk 4H scalping

---

## 1. Ringkasan Cycle Theory

Cycle Theory adalah teori berbasis **siklus waktu** (bukan harga) yang memprediksi kapan market akan membentuk titik terendah (lows). Prinsip utama:

- Semua cycle dihitung dari **LOWS ke LOWS**
- Cycle bersifat **berulang** dengan toleransi waktu tertentu
- Akurasi klaim: 80% (dari backtest manual oleh praktisi)

### Parameter Cycle untuk Bitcoin

| Cycle | Count | Toleransi | Range |
|---|---|---|---|
| Daily Cycle Low (DCL) | 60 hari | ±6 hari | 14 hari |
| Weekly Cycle Low (WCL) | 30 minggu | ±2 minggu | 4 minggu |
| Half Cycle Low (HCL) | ~30 hari | — | — |
| 4-Year Cycle Low | 4 tahun | — | — |

### Konsep Kunci

| Istilah | Arti | Sinyal |
|---|---|---|
| **Right Translated** | Top di kanan HCL | Bullish (trend kuat) |
| **Left Translated** | Top di kiri HCL | Bearish (trend lemah) |
| **Failed Cycle** | Harga break di bawah DCL terkonfirmasi | Bear market |
| **Cycle Low Retest** | Harga retest area DCL sebelumnya | Konfirmasi support |

---

## 2. Evaluasi untuk BTC-QUANT 4H Scalper

### ❌ Alasan Tidak Diimplementasi

#### 2.1 Mismatch Timeframe (Alasan Utama)

| Aspek | Cycle Theory | BTC-QUANT |
|---|---|---|
| Sinyal per tahun | ~6 DCL | 200+ trades |
| Timeframe input | Daily/Weekly chart | 4H candle |
| Holding period | Minggu-bulan | Jam-hari |
| Frekuensi keputusan | 1× per 2 bulan | Beberapa × per hari |

Cycle Theory memberikan **6 sinyal per tahun**. Bot kita membutuhkan sinyal per hari. Informasinya terlalu lambat berubah untuk berguna di scalping.

#### 2.2 Redundansi dengan Engine yang Sudah Ada

| Fitur Cycle Theory | Sudah Ditangkap Oleh | Redundansi |
|---|---|---|
| Deteksi titik balik (lows) | **BCD (Layer 1)** — Bayesian Changepoint Detection | 80% |
| Right/Left Translation | **EMA (Layer 2)** — Price vs EMA20 vs EMA50 | 90% |
| Cycle position (awal/akhir trend) | **BCD regime duration** — sudah tracking | 70% |
| Failed Cycle | **BCD** — regime flip ke Bearish | 60% |

BCD **lebih unggul** daripada Cycle Theory karena:
- BCD adaptif (mendeteksi dari data aktual) vs Cycle Theory rigid (pakai hitungan tetap 60 hari)
- BCD tidak mengasumsikan cycle length konstan — market nyata tidak selalu 60 hari
- BCD sudah terbukti **66.4% WR** di 3 tahun walk-forward data

#### 2.3 Subjektivitas

Dokumen Cycle Theory sendiri menyatakan: *"Setiap trader memiliki versi count cycle lows nya sendiri."*

Ini problematik untuk sistem otomatis:
- Tidak ada definisi objektif kapan cycle dimulai/berakhir
- Interpretasi Left/Right Translation bergantung pada judgment visual
- Sulit dikodekan tanpa ambiguitas

#### 2.4 Estimasi Impact vs Effort

| Fitur | Impact | Effort | Worth It? |
|---|---|---|---|
| cycle_position sebagai fitur MLP | ⭐ (marginal) | 2-3 jam | ❌ 70% redundan dengan BCD |
| Left/Right Translation detector | ⭐ (marginal) | 1 hari | ❌ 90% redundan dengan EMA |
| Failed Cycle detector | ⭐⭐ (mungkin) | 1 hari | ❌ 60% redundan dengan BCD regime |
| WCL leverage scaling | ⭐ | 2 jam | ❌ Hanya 2× per tahun |

**Total effort: 3-5 hari. Estimasi impact: marginal.** Prioritas MLP upgrade (#3-#5) jauh lebih tinggi karena non-redundan dan terukur.

---

## 3. Kapan Cycle Theory Cocok Digunakan?

### ✅ Situasi yang Cocok

| Situasi | Kenapa |
|---|---|
| **Swing trading** (hold 1-4 minggu) | Timeframe DCL 60 hari cocok untuk entry/exit swing |
| **Portfolio allocation** | 4-Year Cycle → kapan all-in vs cash |
| **Manual trading** | Butuh judgment visual — manusia lebih baik dari kode |
| **Menentukan bias macro** | "Di fase mana kita dalam bull/bear cycle?" |
| **Aset tradisional** (S&P500, Emas) | Market yang lebih predictable cycle-nya |

### ❌ Situasi yang Tidak Cocok

| Situasi | Kenapa |
|---|---|
| **Scalping 4H** (kita) | Frekuensi sinyal terlalu rendah |
| **Bot otomatis** | Terlalu subjektif untuk dikodekan |
| **Timeframe < 1 hari** | Cycle Theory melihat hari/minggu, bukan jam |

---

## 4. Kemungkinan Penggunaan Sebagai Macro Overlay

Meskipun tidak cocok untuk dikodekan ke bot, Cycle Theory bisa digunakan oleh **trader (manusia)** sebagai overlay macro untuk mengatur parameter bot secara manual.

### Arsitektur Overlay

```
MACRO LAYER (Cycle Theory — manusia yang baca)
  "Kita di hari ke-50 dari DCL, mendekati koreksi"
  → Keputusan manusia: turunkan leverage bot

    MICRO LAYER (Bot Scalper — otomatis)
      BCD + EMA + Spectrum → per-candle decision
      → Keputusan bot: long/short/skip
```

### Aturan Sederhana untuk Overlay

| Macro (Cycle) | Micro (Bot) | Aksi | Alasan |
|---|---|---|---|
| Bull (awal cycle) | LONG | ✅ Full size | Keduanya setuju |
| Bull (awal cycle) | SHORT | ⚠️ Size kecil | Koreksi normal di bull cycle |
| **Bear (akhir cycle)** | **LONG** | **❌ Skip** | **Bull trap — paling berbahaya** |
| Bear (akhir cycle) | SHORT | ✅ Full size | Keduanya setuju |
| Netral | Apapun | ✅ Normal | Macro tidak punya opini |

### Risiko Overlay

1. **Cycle Theory akurasi 80%** → 20% waktu, macro-nya salah
2. **Override bot yang benar** → kehilangan profit tanpa alasan
3. **BCD 66.4% WR tanpa macro** → sudah proven, menambah layer subjektif bisa merusak konsistensi
4. **Dua sistem yang tidak terintegrasi** → sumber konflik dan bias

> **Rekomendasi:** Jika menggunakan overlay, **hanya** di satu skenario: macro bear + micro long (bull trap). Sisanya biarkan bot jalan tanpa intervensi.

---

## 5. Keputusan Final

| Pertanyaan | Jawaban |
|---|---|
| Apakah Cycle Theory diimplementasi di bot? | **TIDAK** |
| Apakah Cycle Theory berguna? | Ya, tapi untuk **swing trading manual**, bukan bot scalper |
| Apakah informasinya redundan? | Ya, 70-90% sudah ditangkap oleh BCD dan EMA |
| Apakah bisa sebagai overlay macro? | Bisa, tapi dengan risiko override yang salah |
| Prioritas vs MLP upgrade? | MLP upgrade **jauh lebih penting** — non-redundan dan terukur |

---

*Sumber teori: `docs/research/cycle_theory.md`*  
*Evaluasi dilakukan: 3 Maret 2026*
