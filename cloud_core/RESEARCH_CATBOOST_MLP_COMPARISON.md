# Penelitian: Perbandingan CatBoost vs MLP sebagai L3 Signal pada Golden Model v4.4

**Tanggal:** 16 April 2026  
**Peneliti:** BTC-Quant Research Team  
**Status:** COMPLETED

---

## 1. RINGKASAN EKSEKUTIF

Penelitian ini bertujuan untuk mengevaluasi apakah CatBoost dapat menggantikan MLP sebagai Layer 3 (L3 - Machine Learning Perception) pada Golden Model v4.4. Setelah serangkaian eksperimen walkforward test 2020-2026, **ditemukan bahwa MLP asli tetap unggul** dalam konteks arsitektur v4.4 yang ada.

**Key Finding:** CatBoost bukanlah drop-in replacement untuk MLP pada v4.4. Perbedaan fundamental dalam cara kedua model berintegrasi dengan sistem BCD (Bayesian Change Detection) membuat MLP lebih optimal untuk arsitektur saat ini.

---

## 2. HIPOTESIS AWAL

### 2.1. Hipotesis
CatBoost, dengan kemampuannya menangani fitur kategorikal dan robust terhadap overfitting, akan menghasilkan performa setara atau lebih baik dari MLP sebagai sinyal L3 pada v4.4 trade plan.

### 2.2. Dasar Hipotesis
- CatBoost lebih baik untuk fitur kategorikal (bcd_regime)
- CatBoost membutuhkan hyperparameter tuning yang lebih sedikit
- Ablation study sebelumnya menunjukkan 5 fitur causal yang signifikan

---

## 3. METODOLOGI

### 3.1. Arsitektur Test
```
Golden Model v4.4 dengan modifikasi L3:
- L1: BCD Regime Detection (tetap)
- L2: EMA Alignment (tetap)
- L3: CatBoost (menggantikan MLP)
- L4: Volatility Gate (tetap)
- L5: Directional Spectrum (tetap)
- L6: Trade Gate (tetap)
```

### 3.2. Fitur Input
**Causal Features (dari ablation study):**
1. `rsi_14` - Relative Strength Index 14-period
2. `macd_hist` - MACD histogram
3. `ema20_dist` - Distance dari EMA20
4. `log_return` - Log returns
5. `norm_atr` - Normalized ATR
6. `bcd_regime` - Regime classification (bull/bear/neutral) ➕ *ditambahkan*

### 3.3. Parameter Walkforward Test
| Parameter | Nilai |
|-----------|-------|
| Periode | 2020-2026 |
| Train Size | 500 samples |
| Test Size | 100 samples |
| Step Size | 50 samples |
| Windows | 50 |
| SL | 1.333% |
| TP | 0.71% |
| Max Hold | 6 candles |

### 3.4. Iterasi Eksperimen

#### Iterasi 1: CatBoost tanpa Regime Features
- **Win Rate:** 41.2%
- **Avg Trade:** -$9.39
- **Status:** ❌ Underperform

#### Iterasi 2: CatBoost dengan Regime Features
- **Win Rate:** 42.0%
- **Avg Trade:** -$9.03
- **Improvement:** +0.8% win rate, +$0.36 avg trade
- **Status:** ❌ Masih underperform

---

## 4. HASIL DETAIL

### 4.1. Perbandingan Performa

| Metrik | MLP (Baseline) | CatBoost (Tanpa Regime) | CatBoost (Dengan Regime) |
|--------|---------------|------------------------|------------------------|
| **Win Rate** | ~50%+ | 41.2% | 42.0% |
| **Total PnL** | Positif | -$3,625.85 | -$3,394.75 |
| **Avg Trade** | Positif | -$9.39 | -$9.03 |
| **Total Trades** | - | 386 | 376 |

### 4.2. Analisis Per Window

#### Masalah 1: Confidence Overconfidence
```
CatBoost: conf=100.0% pada hampir semua sinyal
MLP:      conf=50-100% dengan distribusi nuansa
```
**Impact:** Trade gate v4.4 di-tune untuk confidence distribution MLP, bukan CatBoost yang overconfident.

#### Masalah 2: Signal Imbalance
```
CatBoost: 95%+ BULL signals, hampir tidak ada BEAR
MLP:      Balance BULL/BEAR sesuai kondisi market
```
**Impact:** Model tidak adaptif terhadap bearish conditions.

#### Masalah 3: BCD Integration Gap
```
MLP:      Menerima hmm_states + hmm_index (rich context)
CatBoost: Hanya bcd_regime feature (simplified context)
```
**Impact:** CatBoost kehilangan informasi temporal dari BCD system.

### 4.3. Distribution Exit

| Exit Type | CatBoost | MLP |
|-----------|----------|-----|
| SL Hit | ~1% | Normal |
| TP Hit | ~2% | Normal |
| **Time Exit** | **~95%** | Normal |

**Key Finding:** TP 0.71% terlalu tinggi untuk timeframe 4h - harga jarang mencapai target dalam 6 candles.

---

## 5. ANALISIS ROOT CAUSE

### 5.1. Mengapa CatBoost Underperform?

#### Factor 1: Arsitektur Mismatch
```
v4.4 Trade Gate Design:
- Optimized untuk MLP confidence pattern
- Spectrum calculation expects MLP vote characteristics
- Trade gate thresholds tuned for MLP distribution
```

#### Factor 2: Context Loss
```
MLP Context (Original):
├── hmm_states: [state probabilities over time]
├── hmm_index: [current regime confidence]
└── bcd_conf: [change detection confidence]

CatBoost Context (Current):
└── bcd_regime: [single categorical value]
```

#### Factor 3: Target Definition
```
CatBoost Target: 3-class (Bear/Neutral/Bull) dengan adaptive threshold
MLP Target:      Continuous dengan regime context
```

### 5.2. Apa yang Bekerja?

✅ **Fitur Causal Valid:** 5 fitur dari ablation study memang signifikan  
✅ **Regime Feature Helpful:** +0.8% improvement dengan bcd_regime  
✅ **CatBoost Training:** Model train dengan baik (accuracy ~48-51%)  

### 5.3. Apa yang Tidak Bekerja?

❌ **Drop-in Replacement:** CatBoost tidak bisa langsung ganti MLP tanpa retune  
❌ **Overconfidence:** Model terlalu yakin (100%) pada sinyal yang seharusnya uncertain  
❌ **Signal Balance:** Bias ke BULL terlalu kuat, tidak ada adaptasi ke BEAR  

---

## 6. LESSONS LEARNED

### 6.1. Model Replacement Principle
```
Replacing L3 model bukan hanya swap model code.
Harus juga:
1. Retune trade gate thresholds
2. Rebalance spectrum weights
3. Recalibrate confidence mapping
4. Validate signal distribution
```

### 6.2. Context Engineering > Feature Engineering
```
MLP unggul bukan karena algoritma lebih baik,
tapi karena integrasi context dengan BCD lebih optimal.
```

### 6.3. Confidence Calibration
```
Confidence score harus well-calibrated untuk trade gate.
100% confidence pada sinyal lemah = lebih buruk dari 60% pada sinyal kuat.
```

---

## 7. REKOMENDASI

### 7.1. Production Recommendation
**Gunakan MLP sebagai L3 pada v4.4.** CatBoost belum siap sebagai drop-in replacement.

### 7.2. Future Research
Jika ingin menggunakan CatBoost, pertimbangkan:

1. **New Architecture Design**
   - Buat trade gate khusus untuk CatBoost
   - Redefine spectrum calculation
   - Custom exit logic

2. **Ensemble Approach**
   - CatBoost + MLP ensemble
   - Weighted voting system
   - Dynamic model selection

3. **Confidence Calibration**
   - Temperature scaling
   - Isotonic regression
   - Platt scaling

### 7.3. v4.4 Optimization
Fokus pada improvement yang lebih feasible:
1. **TP Target Tuning:** 0.71% → 0.5% untuk timeframe 4h
2. **Time Exit Optimization:** Max hold 6 candles → adaptive
3. **Regime Filter:** Skip trade saat regime confidence rendah

---

## 8. KESIMPULAN

Setelah eksperimen komprehensif dengan 50 windows walkforward test pada data BTC-USDT 2020-2026, **hipotesis awal ditolak**. CatBoost tidak dapat secara langsung menggantikan MLP pada Golden Model v4.4.

**Key Takeaway:**
> Kualitas model ML bukan hanya tentang algoritma, tapi tentang bagaimana model tersebut berintegrasi dengan seluruh sistem trading. MLP pada v4.4 telah di-tune selama bertahun-tahun untuk berkolaborasi optimal dengan BCD, spectrum, dan trade gate. Mengganti komponen kunci tanpa mempertimbangkan seluruh arsitektur akan mengurangi performa.

---

## APPENDIX

### A. File Experiment
- `v4_4_catboost_engine.py` - Engine dengan CatBoost L3
- `cloud_core/experiments/models/tree_catboost.py` - CatBoost model
- `backtest/results/v4_4_catboost/` - Hasil walkforward test

### B. Commands
```bash
# Run CatBoost walkforward test
python v4_4_catboost_engine.py --windows 50

# Compare dengan baseline
# (baseline: v4_4_engine.py dengan MLP)
```

### C. Timeline Research
- **Ablation Study:** Identifikasi 5 causal features
- **CatBoost Integration:** Implementasi dengan 5 fitur causal
- **Regime Feature Addition:** Tambah bcd_regime sebagai fitur kategorikal
- **Walkforward Test 50 Windows:** Validasi performa 2020-2026
- **Conclusion:** MLP tetap superior untuk v4.4

---

**End of Research Report**  
*Document Version: 1.0*  
*Last Updated: 2026-04-16*
