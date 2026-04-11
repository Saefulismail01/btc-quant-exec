# Implementation Plan: BTC-QUANT Technical Paper & Documentation

Rencana ini bertujuan untuk menyusun dokumentasi teknis komprehensif (Paper) yang merangkum seluruh perjalanan riset, dari kegagalan HMM hingga penemuan Golden Model v4.4 di direktori ini.

## 📂 Struktur Direktori Target (LaTeX Project)
```text
paper/
├── figures/              # Grafik hasil backtest, visualisasi regime BCD, dll.
├── sections/             # File .tex terpisah per bab
├── main.tex              # File induk LaTeX (Preamble & Structure)
├── references.bib        # Daftar pustaka / referensi teknis
└── implementation_plan.md # File ini
```

---

## 📅 Garis Besar Fase Penyusunan

### Fase 1: Rekonstruksi Sejarah & Kegagalan HMM
*   **Tujuan:** Mengetahui akar masalah mengapa model tradisional (ML) tidak cukup untuk pasar kripto.
*   **Poin Utama:** Eksperimen awal dengan Gaussian HMM, masalah transisi statis, dan kegagalan validasi Walk-Forward (Modul C).

### Fase 2: Transisi ke Ekonofisika (The BCD Breakthrough)
*   **Tujuan:** Memperkenalkan landasan ilmiah baru.
*   **Poin Utama:** Pengenalan BCD, filosofi "Phase Transitions", dan implementasi distribusi Student-T untuk *Fat-Tails*.

### Fase 3: Arsitektur 6-Layer & Heston Model
*   **Tujuan:** Menjelaskan mesin pengolah sinyal yang sekarang digunakan.
*   **Poin Utama:** Peran krusial Model Heston sebagai "Volatility Gate" dan mekanisme Directional Spectrum.

### Fase 4: Evolusi Strategi (v3 ➔ v4.4)
*   **Tujuan:** Menjelaskan perjalanan pencarian stabilitas.
*   **Poin Utama:** Masalah *Compounding Risk*, fenomena *Alpha Decay*, dan penemuan Golden Model v4.4 tanpa breakeven lock.

### Fase 5: Validasi Hasil & Kesimpulan
*   **Tujuan:** Menyajikan bukti statistik final (2024-2026).
*   **Poin Utama:** Tabel metrik performa final dan kesimpulan "Stability is the New High Return".

---

## 🛠️ Langkah Operasional Segera

- [ ] **Step 1:** Inisialisasi struktur proyek LaTeX (`main.tex` & `sections/`).
- [ ] **Step 2:** Menyusun Bab 1: Sejarah & Kegagalan HMM (Fase Logika Awal).
- [ ] **Step 3:** Menyusun Bab 2: Landasan Ekonofisika (BCD & Student-T).
- [ ] **Step 4:** Melakukan kompilasi draf awal untuk verifikasi format.
