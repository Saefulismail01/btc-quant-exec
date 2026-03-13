# Signal Logic Fix — Implementation Plan

## Problem Summary

Bot menghasilkan WEAK BUY (LONG) saat market turun. Jika SHORT, scalper profit 3%.

**Root causes:**
- L1 BCD over-persistent (100%), lambat detect reversal
- L1 feed ke L3 sebagai input → L3 ter-bias oleh L1
- L3 output NEUTRAL 50% (padahal sudah di-bias BULL dari L1) = sebenarnya bearish
- L3 NEUTRAL → vote = 0.0 → contribution = 0 → **dibungkam**
- L2 EMA lagging, price hanya $308 di atas EMA20 tapi tetap "confirmed bullish"
- Weights: L1=0.45, L2=0.35, L3=0.20 — layer tercepat punya weight terkecil

**Critical finding:** Comment di spectrum.py bilang validated weights = L1=0.30, L2=0.25, **L3=0.45**
Tapi actual code = L1=0.45, L2=0.35, **L3=0.20** → TERBALIK dari yang ter-validasi!

**Critical finding 2:** L3 MLP sudah punya RSI(14) + MACD sebagai input features.
Jadi L3 sebenarnya sudah "tahu" momentum — tapi output-nya di-ignore.

---

## Fix #1: L3 Disagreement sebagai Counter-Signal

### Apa yang diubah
Saat L3 output NEUTRAL padahal L1 directional (BULL/BEAR), treat sebagai **counter-signal** terhadap L1, bukan netral.

### Logika
```
L1 = BULL + L3 = NEUTRAL → L3 disagree → l3_vote = -0.3 (melawan L1)
L1 = BEAR + L3 = NEUTRAL → L3 disagree → l3_vote = +0.3 (melawan L1)
L1 = NEUTRAL + L3 = apapun → normal behavior
```

### Reasoning
- L3 menerima BCD state sebagai input (hmm_state_0..3 one-hot)
- Jika L3 di-feed BULL tapi output NEUTRAL → market data kontradiksi regime
- L3 punya RSI, MACD, ema20_dist, log_return → lebih reaktif dari BCD
- NEUTRAL bukan "tidak tahu", tapi "data teknikal tidak support regime L1"

### File: `signal_service.py`

**Lokasi:** Setelah line ~394 (setelah `ai_bias, ai_conf = _safe_ai_cross(...)`)

```python
# ── FIX #1: L3 Disagreement Detection ────────────────────────
# Jika L3 NEUTRAL padahal L1 directional, itu COUNTER-SIGNAL
# L3 di-feed HMM state → kalau tetap NEUTRAL = market data melawan regime
_l3_disagrees = (
    ai_bias == "NEUTRAL"
    and hmm_tag in ("bull", "bear")
    and ai_conf <= 55.0
)
```

**Lokasi:** Line ~417 (saat menghitung l3_vote)

```python
# SEBELUM:
l3_vote = _to_vote(ai_bias.upper() == "BULL", mlp_conf_norm)

# SESUDAH:
if _l3_disagrees:
    # L3 NEUTRAL + L1 directional = counter-signal
    # Magnitude: 0.3 (moderate counter, bukan full reversal)
    l3_vote = -0.3 if hmm_tag == "bull" else +0.3
else:
    l3_vote = _to_vote(ai_bias.upper() == "BULL", mlp_conf_norm)
```

### Impact Calculation (current signal case)
```
SEBELUM:
  l1_vote = +1.0 (BCD BULL 100%)
  l2_vote = +1.0 (EMA confirmed)
  l3_vote = 0.0  (NEUTRAL → silent)
  raw = 0.45(1.0) + 0.35(1.0) + 0.20(0.0) = +0.80
  final = 0.80 × 0.2 = +0.16 → LONG, 16% conviction

SESUDAH:
  l3_vote = -0.3  (disagree → counter-signal)
  raw = 0.45(1.0) + 0.35(1.0) + 0.20(-0.3) = +0.74
  final = 0.74 × 0.2 = +0.148 → LONG, 14.8% conviction
```

Hmm, impact masih kecil karena L3 weight hanya 0.20. **Butuh Fix #2.**

---

## Fix #2: Reweight Layers

### Apa yang diubah
Kembalikan ke validated walk-forward weights: L1=0.30, L2=0.25, L3=0.45

### Reasoning
- Comment di spectrum.py sendiri bilang L1=0.30, L2=0.25, L3=0.45 = **+597.89% / 3 tahun**
- Actual code pakai L1=0.45, L2=0.35, L3=0.20 → **belum ter-validasi** (ini malah yang seharusnya tidak boleh di production)
- L3 punya RSI + MACD + momentum features → paling reaktif untuk scalping
- L1 (BCD) proven lambat di reversal → weight harus dikurangi

### File: `spectrum.py`

**Lokasi:** Line 58-60

```python
# SEBELUM:
_L1_WEIGHT = 0.45   # BCD  — macro regime, proven, dominant
_L2_WEIGHT = 0.35   # EMA  — structural confirmation
_L3_WEIGHT = 0.20   # MLP  — short-term, supporting weight

# SESUDAH (kembali ke VALIDATED weights):
_L1_WEIGHT = 0.30   # BCD  — macro regime context
_L2_WEIGHT = 0.25   # EMA  — structural confirmation
_L3_WEIGHT = 0.45   # MLP  — short-term predictive, highest alpha
```

### Impact Calculation (with Fix #1 + Fix #2)
```
SESUDAH Fix #1 + #2:
  l1_vote = +1.0 (BCD BULL)
  l2_vote = +1.0 (EMA confirmed)
  l3_vote = -0.3 (disagree counter-signal)

  raw = 0.30(1.0) + 0.25(1.0) + 0.45(-0.3) = +0.415
  final = 0.415 × 0.2 = +0.083 → SUSPENDED (< 0.10)
```

**Dengan Fix #1 + #2: Signal menjadi SUSPENDED** — tidak akan trade LONG yang salah!

---

## Fix #3: RSI Reversal Check sebagai L2 Modifier

### Apa yang diubah
Tambah RSI(14) check untuk modify L2 vote. Jika EMA bilang "bullish" tapi RSI overbought (>70) dan menurun, downgrade L2.

### Reasoning
- L3 sudah punya RSI sebagai internal feature — tapi outputnya bisa di-dampen oleh HMM input
- RSI sebagai **independent modifier untuk L2** = defense-in-depth
- Bukan layer baru, hanya memodifikasi confidence L2
- EMA structure saja tidak cukup (price $308 di atas EMA20 = meaningless)

### File: `signal_service.py`

**Lokasi:** Setelah EMA alignment (line ~398), sebelum spectrum calculation

```python
# ── FIX #3: RSI Reversal Modifier untuk L2 ───────────────────
# Jika RSI(14) overbought/oversold, EMA confirmation dilemahkan
df["RSI14"] = ta.rsi(df["Close"], length=14)
rsi_now = float(df["RSI14"].iloc[-1]) if not pd.isna(df["RSI14"].iloc[-1]) else 50.0

# EMA proximity check: jarak price ke EMA20
ema_distance_ratio = abs(price_now - ema20_now) / atr14_now if atr14_now > 0 else 999

# Downgrade L2 jika:
# 1. RSI > 70 (overbought) dan trend_short == BULL → potential reversal down
# 2. RSI < 30 (oversold) dan trend_short == BEAR → potential reversal up
# 3. Price terlalu dekat EMA20 (< 0.3 ATR) → EMA confirmation tidak reliable
_l2_weakened = False
if trend_short == "BULL" and rsi_now > 70:
    _l2_weakened = True
elif trend_short == "BEAR" and rsi_now < 30:
    _l2_weakened = True
elif ema_distance_ratio < 0.3:
    _l2_weakened = True
```

**Lokasi:** Line ~418 (saat menghitung l2_vote)

```python
# SEBELUM:
l2_vote = _to_vote(trend_short == "BULL", 1.0 if l2 else 0.0)

# SESUDAH:
if _l2_weakened and l2:
    # L2 technically aligned tapi RSI/proximity says unreliable
    l2_vote = _to_vote(trend_short == "BULL", 0.3)  # Reduced from 1.0 to 0.3
else:
    l2_vote = _to_vote(trend_short == "BULL", 1.0 if l2 else 0.0)
```

### Impact Calculation (Fix #1 + #2 + #3, assuming RSI > 70 atau EMA proximity < 0.3 ATR)
```
Current case: ema_distance_ratio = 308 / 1199 = 0.257 (< 0.3!) → L2 WEAKENED

SESUDAH Fix #1 + #2 + #3:
  l1_vote = +1.0 (BCD BULL)
  l2_vote = +0.3 (EMA weakened by proximity)
  l3_vote = -0.3 (disagree counter-signal)

  raw = 0.30(1.0) + 0.25(0.3) + 0.45(-0.3) = +0.24
  final = 0.24 × 0.2 = +0.048 → SUSPENDED (< 0.10)
```

---

## Combined Impact Analysis

### Skenario: Current Signal (2026-03-12)

| Version | l1_vote | l2_vote | l3_vote | raw | l4 | final | Gate | Direction |
|---------|---------|---------|---------|-----|-----|-------|------|-----------|
| **Current (broken)** | +1.0 | +1.0 | 0.0 | +0.80 | 0.2 | **+0.16** | ADVISORY | LONG ❌ |
| **Fix #1 only** | +1.0 | +1.0 | -0.3 | +0.74 | 0.2 | +0.148 | ADVISORY | LONG ❌ |
| **Fix #1 + #2** | +1.0 | +1.0 | -0.3 | +0.415 | 0.2 | +0.083 | **SUSPENDED** | - ✅ |
| **Fix #1 + #2 + #3** | +1.0 | +0.3 | -0.3 | +0.24 | 0.2 | **+0.048** | **SUSPENDED** | - ✅ |

### Skenario: Strong Bullish Signal (semua layer aligned)

| Version | l1_vote | l2_vote | l3_vote | raw | l4 | final | Gate | Direction |
|---------|---------|---------|---------|-----|-----|-------|------|-----------|
| **Current** | +1.0 | +1.0 | +0.6 | +0.92 | 0.8 | +0.736 | ACTIVE | LONG ✅ |
| **Fix #1 + #2 + #3** | +1.0 | +1.0 | +0.6 | +0.82 | 0.8 | +0.656 | ACTIVE | LONG ✅ |

Strong signal tetap ACTIVE — fix tidak merusak sinyal bagus.

### Skenario: Kasus yang harusnya SHORT (L3 detect bearish 60%)

| Version | l1_vote | l2_vote | l3_vote | raw | l4 | final | Gate | Direction |
|---------|---------|---------|---------|-----|-----|-------|------|-----------|
| **Current** | +1.0 | +1.0 | -0.2 | +0.76 | 0.5 | +0.38 | ACTIVE | LONG ❌ |
| **Fix #1 + #2 + #3** | +1.0 | +0.3 | -0.2 | +0.285 | 0.5 | +0.1425 | ADVISORY | LONG ⚠️ |

Masih LONG tapi downgraded ke ADVISORY. L1 terlalu kuat — tapi ini normal, BCD regime belum flip.

---

## Files to Modify

| File | Changes | Priority |
|------|---------|----------|
| `backend/utils/spectrum.py` (line 58-60) | Revert weights ke validated L1=0.30, L2=0.25, L3=0.45 | **Fix #2** |
| `backend/app/use_cases/signal_service.py` (line ~394, ~417) | L3 disagreement detection + counter-signal vote | **Fix #1** |
| `backend/app/use_cases/signal_service.py` (line ~398, ~418) | RSI check + EMA proximity modifier untuk L2 | **Fix #3** |

---

## Testing Plan

### Step 1: Unit Test
- Hitung manual spectrum result untuk 5 skenario (tabel di atas)
- Verifikasi output match

### Step 2: Backtest Validation
- Run walk-forward backtest dengan weights baru
- Compare equity curve vs current weights (0.45/0.35/0.20)
- Target: WR ≥ 65%, total return ≥ +500%

### Step 3: Live Validation
- Deploy ke VPS container
- Monitor 24-48 jam (12 candle cycles)
- Compare signal quality vs sebelum fix
- Pastikan strong signals tetap ACTIVE

---

## Rollback Plan

Jika backtest results buruk:
1. Revert spectrum.py weights ke 0.45/0.35/0.20
2. Remove L3 disagreement logic
3. Remove RSI modifier
4. Semua changes isolated → easy rollback per-fix
