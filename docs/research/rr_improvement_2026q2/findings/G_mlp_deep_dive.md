# MLP (Layer 3) — deep dive dari kode & artefak

**Area:** G — MLP Specific Deep Dive  
**Status:** Partial — **tanpa re-train**; artefak `joblib` **tidak** ada di workspace git  
**Updated:** 2026-04-24

## TL;DR

`SignalIntelligenceModel` memprediksi **3 kelas** (bear / neutral / bull) dari **forward return** 4H sejumlah `MLP_FORWARD_RETURN_WINDOW` candle (default **1**), dengan ambang adaptif `0.5 * norm_atr * sqrt(W)`. Fitur utama **8** kolom teknikal (+ **4** one-hot regime saat cross aktif = **12** input). Training memakai **early stopping 15%** internal sklearn — **bukan** walk-forward terpisah. **SHAP / reliability diagram / metrik OOS tersimpan:** **TIDAK TERSEDIA** di repo untuk sesi ini.

## Methodology

- File utama: `backend/app/core/engines/layer3_ai.py`  
- Wrapper: `backend/app/use_cases/ai_service.py`  
- Pencarian artefak: glob `**/mlp_model.joblib` di workspace → **0 file**

## Findings

### G.1 Training data temporal coverage

- Model dilatih **on-the-fly** dari DataFrame OHLCV terakhir yang dipass ke `get_ai_confidence` (panjang bar = sejarah yang tersedia di caller).  
- **TIDAK TERSEDIA** ringkasan persen bull/bear/choppy terpisah — tidak ada log training persisten di DB.

### G.2 Feature importance

**TIDAK TERSEDIA** — tidak ada SHAP / permutation importance tersimpan. Daftar fitur dari kode:

`rsi_14`, `macd_hist`, `ema20_dist`, `log_return`, `norm_atr`, `norm_cvd`, `funding`, `oi_change` (+ `hmm_state_0..3` jika cross).

Dominasi derivatif harga: **ya** (RSI, MACD, EMA distance, log return, norm ATR); microstructure: `norm_cvd`, `funding`, `oi_change`.

### G.3 Out-of-sample vs in-sample

- `MLPClassifier(early_stopping=True, validation_fraction=0.15)` → holdout **internal** satu kali per `fit`, **bukan** laporan metrik tersimpan.  
- Gap train vs test: **TIDAK TERSEDIA** angka tersimpan.

### G.4 Calibration

- Output inferensi: probabilitas kelas → mapping ke `BULL`/`BEAR`/`NEUTRAL` + confidence 50–100% — ```471:491:backend/app/core/engines/layer3_ai.py```  
- Reliability diagram (apakah 70% = 70% win): **TIDAK TERSEDIA** (perlu log prediksi vs outcome).

### G.5 Confusion vs regime BOCPD

**TIDAK TERSEDIA** — tidak ada cross-tab tersimpan; membutuhkan batch replay dengan label outcome terdefinisi.

## Gaps & Limitations

- Path artefak: `backend/app/infrastructure/model_cache/mlp_*.joblib` — **kosong** di clone yang diperiksa → tidak bisa inspeksi `n_iter_`, loss, atau `classes_` aktual.  
- Dokumentasi/komentar lama di beberapa file masih menyebut “HMM” / “5 features”; produksi memakai **BCD + 8 (+4)** sesuai `layer3_ai.py`.

## Raw Sources

- `backend/app/core/engines/layer3_ai.py` baris 43–77, 257–365, 400–491  
- `backend/app/use_cases/ai_service.py`  
- `backend/app/use_cases/signal_service.py` (wire L3)
