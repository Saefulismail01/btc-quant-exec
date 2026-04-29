# Architecture inventory — L1 through execution

**Area:** A — Arsitektur Multi-Layer  
**Status:** Complete (dari kode backend production)  
**Updated:** 2026-04-24

## TL;DR

Pipeline sinyal utama: **load DuckDB 4H** → indikator / trend → **layer booleans + DirectionalSpectrum** → optional LLM → `SignalResponse`. L1 default **BOCPD** (`layer1_bcd.py`) dengan hazard & prior NIG; L2 default **EMA20/50** (`layer2_ema.py` via `ema_service`); L3 **sklearn MLPClassifier** 3-kelas forward return (`layer3_ai.py`); L4 **Heston-style estimator** (`layer1_volatility.py`); eksekusi **Lighter** + `PositionManager` + `live_trades` DuckDB.

## Methodology

Trace dari `signal_service.py` header + implementasi engine di `backend/app/core/engines/` dan `bcd_service.py`, `ema_service.py`, `ai_service.py`, `risk_manager.py`, `position_manager.py`, `lighter_execution_gateway.py`.

## Findings — ringkas per layer

### A.1 Layer 1 — BOCPD (BCD)

| Pertanyaan | Jawaban |
|------------|---------|
| File utama | `backend/app/core/engines/layer1_bcd.py` (`BayesianChangepointModel`); servis: `backend/app/use_cases/bcd_service.py` (`Layer1EngineService`, env `LAYER1_ENGINE` default BCD, alternatif HMM) |
| Hazard / prior | `HAZARD_RATE = 1/15`; prior per dimensi `BCD_PRIOR_ALPHA/BETA/KAPPA` (baris 40–43 `layer1_bcd.py`) |
| Predictive | **Student-t** predictive posterior (fungsi bernama `_run_gaussian_bocpd` tetapi docstring menyatakan Student-t; baris 137–176 `layer1_bcd.py`) |
| Output ke downstream | Label regime string + state diskrit; `get_regime_with_posterior` → confidence; state sequence untuk cross-feature MLP |
| Frekuensi | Pada inferensi: dataset yang dipass biasanya **4H** terakhir dari DuckDB (`get_ohlcv_with_metrics`), bukan per detik |
| Lookback | `MIN_ROWS = 100`; `TRAILING_WINDOW = 36` (config label, baris 34–46) |

### A.2 Layer 2 — Teknikal

| Pertanyaan | Jawaban |
|------------|---------|
| Model | `EMAStructureModel`: EMA **20** & **50**, struktur harga vs EMA (`layer2_ema.py` baris 22–64) |
| Agregasi | Boolean `get_ema_alignment(df, trend_short)` + vote kontinu `get_directional_vote` (ATR14 normalisasi, baris 66+) |
| Mode opsional | `USE_ICHIMOKU=true` → `IchimokuCloudModel` (`ema_service.py` baris 38–68) |
| Output | `(aligned: bool, label, detail)` dan `float` vote [-1,1] |

### A.3 Layer 3 — MLP

| Pertanyaan | Jawaban |
|------------|---------|
| Target / label | **3 kelas** dari pergerakan harga **W candle forward** (`MLP_FORWARD_RETURN_WINDOW`, default **1** candle = 4H): bear / neutral / bull vs ambang `0.5 * norm_atr * sqrt(W)` — ```257:278:backend/app/core/engines/layer3_ai.py``` |
| Arsitektur | `MLPClassifier` sklearn: hidden `(128,64)` jika fitur **hanya** tech; `(256,128)` jika **cross** (lebih dari 8 fitur tech) — ```332:349:backend/app/core/engines/layer3_ai.py``` |
| Fitur tech | `rsi_14`, `macd_hist`, `ema20_dist`, `log_return`, `norm_atr`, `norm_cvd`, `funding`, `oi_change` — ```65:77:backend/app/core/engines/layer3_ai.py``` |
| Cross L1 | One-hot **4** state → total **12** kolom saat cross aktif (`_ALL_FEATURE_COLS`) |
| Train / val | `MLPClassifier(..., early_stopping=True, validation_fraction=0.15)` — split internal sklearn, **bukan** walk-forward eksplisit di service |
| Retrain | Setiap `MLP_RETRAIN_EVERY_N_CANDLES` (=48) candle baru atau vol spike (`MLP_VOL_SPIKE_RETRAIN_RATIO`) |
| Inference output | `get_ai_confidence` → bias `BULL`/`BEAR`/`NEUTRAL` + confidence 50–100% dari `predict_proba` — ```471:491:backend/app/core/engines/layer3_ai.py``` |
| Artifact | `backend/app/infrastructure/model_cache/mlp_model.joblib`, `mlp_scaler.joblib`, `mlp_meta.joblib` — **tidak** ada di git workspace saat probing |

### A.4 Layer volatilitas (L4 di stack sinyal)

| Pertanyaan | Jawaban |
|------------|---------|
| Model | **Bukan GARCH**; estimator **Heston-style** (OLS pada realized variance) `VolatilityRegimeEstimator` — `layer1_volatility.py` |
| Output | Dict: `gamma`, `eta`, `kappa`, `current_vol`, `long_run_vol`, `vol_regime`, dll. (baris 94–97) |
| Pemakaian | SL/TP multiplier & label risiko (diwire dari `signal_service` via `get_vol_estimator()`) |

### A.5 Layer eksekusi

| Pertanyaan | Jawaban |
|------------|---------|
| Gateway | `backend/app/adapters/gateways/lighter_execution_gateway.py` |
| Position logic | `backend/app/use_cases/position_manager.py` — SL wajib, TP opsional, `LiveTradeRepository` |
| SL/TP | Harga dari risk / signal path (bukan hardcode % di repository); buffer slippage di gateway (SL 0.5%, TP 0.3%) |
| Sizing | Via `RiskManager` + caller (`RiskConfig`, env `LEVERAGE_SAFE_MODE`) — `risk_manager.py` |
| Partial TP / trailing | **Tidak** sebagai fitur first-class di gateway: `close_position_market` menutup **penuh**; komentar di `position_manager` mengakui **trailing SL** bisa menyebabkan exit `SL` dengan PnL positif (uji di `backend/tests/test_sl_freeze_logic.py`) |
| Order types | Entry market (lihat alur open position); SL/TP via `create_sl_order` / `create_tp_order` SDK Lighter |

## Diagram alur (teks)

`DuckDB (btc_ohlcv_4h + market_metrics)` → `signal_service` → L1 BCD + L2 EMA + L3 MLP (+ Spectrum) → `SignalResponse` → `PositionManager` → Lighter API → `live_trades` insert/update.

## Gaps & Limitations

- Dokumentasi lama di beberapa komentar masih menyebut "5 features" / "HMM" padahal produksi BCD + **8** fitur tech; cross = **12** input.
- Metrik presisi/recall MLP **tidak** di-log ke DB dari service path produksi.

## Raw Sources

- `backend/app/use_cases/signal_service.py` baris 1–64, 278+ (layer evaluation)  
- `backend/app/core/engines/layer1_bcd.py` baris 34–43, 137–176  
- `backend/app/use_cases/bcd_service.py` baris 33–56  
- `backend/app/core/engines/layer2_ema.py`  
- `backend/app/use_cases/ema_service.py`  
- `backend/app/core/engines/layer3_ai.py`  
- `backend/app/core/engines/layer1_volatility.py` baris 1–56  
- `backend/app/use_cases/position_manager.py`, `lighter_execution_gateway.py`  
- `backend/app/use_cases/risk_manager.py` baris 48–66  
