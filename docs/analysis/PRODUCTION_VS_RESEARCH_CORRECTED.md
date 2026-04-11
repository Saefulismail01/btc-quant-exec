# Koreksi: Production vs Research Boundaries

## ⚠️ PENTING: Model Status

### Model yang Baru Saja Diuji (53-54% accuracy)
| Model | Status | Lokasi |
|-------|--------|--------|
| Logistic Regression | 🔬 RESEARCH | `research/models/experiments/` |
| LightGBM | 🔬 RESEARCH | `research/models/experiments/` |
| XGBoost | 🔬 RESEARCH | `research/models/experiments/` |
| MLP | 🔬 RESEARCH | `research/models/experiments/` |
| Rule-Based | 🔬 RESEARCH | `research/models/experiments/` |

### Kenapa Masih Research?
- Accuracy hanya 53-54% (cuma 3-4% di atas random 50%)
- Belum diuji di paper trading
- Belum profitable 1+ bulan live
- Belum through strict validation

---

## 🚫 Production (SACRED) - Apa yang Ada Sekarang

```
prod/
└── engine/
    └── layer3_ml/
        ├── __init__.py
        └── [MODEL_VALIDATED_LAMA]  # <- Apapun yang sudah profit live
```

**Isi Production saat ini:**
- Model apa pun yang **sudah menghasilkan profit** di live trading
- Jika belum ada model yang validated → production layer3 kosong dulu

---

## 🔬 Research (PLAYGROUND) - Semua Eksperimen

```
research/
└── models/
    ├── experiments/              # <- SEMUA model baru di sini
    │   ├── logistic.py          # Model yang baru diuji
    │   ├── lightgbm.py
    │   ├── xgboost.py
    │   ├── mlp.py
    │   └── rule_based.py
    │
    └── candidates/               # <- Kalau sudah bagus, pindah ke sini
        └── [model_yang_lolos_backtest].py
```

**Rules:**
1. Model baru → selalu di `experiments/`
2. Kalau backtest >60% accuracy → pindah ke `candidates/`
3. Kalau paper trading 1 bulan profit → proposal ke prod

---

## 🔄 Path to Production (STRICT)

```
research/models/experiments/logistic.py
            ↓
    [Backtest: 200+ candles]
            ↓
    Accuracy > 60% ?
    ├── YES → Pindah ke candidates/
    └── NO  → Stay in experiments/ atau discard
            ↓
research/models/candidates/logistic_v2.py
            ↓
    [Paper Trading: 1 bulan]
    Profit > 0% dan Max DD < 10% ?
    ├── YES → Proposal ke prod
    └── NO  → Back to experiments/
            ↓
    [Integration Test]
    ├── Code review
    ├── Security audit
    └── Performance test
            ↓
    [Staging Deploy]
    ├── Run 1 minggu
    └── Monitor metrics
            ↓
prod/engine/layer3_ml/logistic.py  ← BARU di-add!
```

---

## 📊 Kriteria Production-Ready

### Minimum Requirements:
| Kriteria | Threshold |
|----------|-----------|
| Backtest Accuracy | > 60% |
| Paper Trading Profit | > 0% (positive) |
| Paper Trading Duration | 1 bulan |
| Max Drawdown | < 15% |
| Sharpe Ratio | > 1.0 |
| Win Rate | > 55% |

### Code Quality:
- [ ] Unit tests passing
- [ ] Integration tests passing
- [ ] Code review approved
- [ ] Documentation complete
- [ ] Error handling robust

---

## 🎯 Struktur Koreksi (Alternative 4 - Updated)

```
btc-scalping/
│
├── 🔴 prod/                        ← 🚫 VALIDATED ONLY
│   ├── engine/
│   │   ├── layer1_regime.py
│   │   ├── layer2_trend.py
│   │   ├── layer3_ml/
│   │   │   ├── __init__.py
│   │   │   └── [KOSONG ATAU MODEL_LAMA_VALIDATED]  # <- Hanya yang sudah profit
│   │   ├── layer4_risk.py
│   │   └── spectrum.py
│   ├── execution/
│   ├── risk/
│   └── notify/
│
├── 🔵 research/                    ← 🔬 ALL EXPERIMENTS
│   ├── models/
│   │   ├── experiments/           # <- SEMUA model baru
│   │   │   ├── __init__.py
│   │   │   ├── logistic.py       # Model yang baru diuji (53.8%)
│   │   │   ├── lightgbm.py       # Model yang baru diuji (53.3%)
│   │   │   ├── xgboost.py        # Model yang baru diuji (52.8%)
│   │   │   ├── mlp.py
│   │   │   ├── lstm.py
│   │   │   └── rule_based.py
│   │   │
│   │   └── candidates/            # <- Lolos backtest, belum paper trading
│   │       └── [empty until validated]
│   │
│   ├── backtest/
│   └── notebooks/
│
└── [docker-compose, docs, etc]
```

---

## ❌ Common Mistakes

### JANGAN:
1. ❌ Langsung copy model baru ke prod/
2. ❌ Ganti model prod tanpa paper trading
3. ❌ Deploy model dengan accuracy < 55%
4. ❌ Skip integration testing

### BOLEH:
1. ✅ Eksperimen bebas di research/
2. ✅ Paper trading dengan size kecil
3. ✅ Multiple model di research/candidates/
4. ✅ A/B testing di staging

---

## 🎬 Current State

### Sekarang (April 2026):
```
prod/engine/layer3_ml/
├── __init__.py
└── [???]  # <- Apa model yang sekarang di production?
```

**Pertanyaan untuk Anda:**
- Model apa yang sekarang running di live trading?
- Apakah ada model yang sudah validated sebelumnya?
- Atau production masih kosong dan perlu diisi?

### Jika Production Kosong:
Opsi A: 
- Running tanpa L3 ML (hanya Layer 1-2)
- Atau pakai rule-based sederhana yang sudah tested

Opsi B:
- Pilih best model dari research (Logistic 53.8%)
- Paper trading 1 bulan
- Kalau profit → promote ke prod

---

## 📝 Summary Koreksi

| Lokasi | Isi | Status |
|--------|-----|--------|
| `prod/engine/layer3_ml/` | Model yang **sudah profit live** atau **kosong** | 🚫 Sacred |
| `research/models/experiments/` | **Semua** model baru termasuk Logistic, LightGBM, etc | 🔬 Experiment |
| `research/models/candidates/` | Model yang **lolos backtest** (>60% acc) | 🔬 Pre-prod |

**Golden Rule Updated:**
> "Accuracy 53% = RESEARCH. Accuracy 60%+ dan paper trading profit = CANDIDATE. Live trading profit 1 bulan = PRODUCTION."

---

**Apa model yang sekarang ada di production Anda?** Saya perlu tahu untuk struktur yang tepat.
