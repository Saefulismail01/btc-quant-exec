"""
Signal Service — full quantitative signal pipeline.

Execution order (strict, no exceptions):
    1.  Load OHLCV + metrics from DuckDB
    2.  Compute technical indicators (EMA, ATR)
    3.  Determine trend direction and action side
    4.  Compute risk parameters (SL, TP, entry zone, leverage)
    5.  Evaluate layer booleans (L1–L4)
    6a. Legacy binary score (backward compat)
    6b. SPECTRUM score — DirectionalSpectrum.calculate() [PHASE 2+3]
    7.  Call LLM with score included as fact → get verdict + rationale
    8.  Enforce verdict consistency with score (Truth Enforcer)
    9.  Determine trade_plan status from SPECTRUM gate
   10.  Assemble and return SignalResponse

PHASE 2: DirectionalSpectrum for continuous [-1,+1] bias scoring.
PHASE 3: HMM→MLP feature cross — state sequence from L1 injected into L3.
         HMM posterior probability used for real hmm_confidence in spectrum.
"""

import threading as _threading
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pandas_ta as ta

from app.adapters.repositories.market_repository import get_market_repository
from app.use_cases.bcd_service import get_bcd_service
from app.use_cases.ai_service import get_ai_service
from app.use_cases.ema_service import get_ema_service
from app.use_cases.narrative_service import get_narrative_service
from app.use_cases.ai_agent import get_ai_agent_synthesis
from app.use_cases.paper_trade_service import PaperTradeService as _PaperTradeService
from app.schemas.signal import (
    SignalResponse,
    PriceSnapshot,
    TrendInfo,
    TradePlan,
    Confluence,
    ConfluenceLayers,
    LayerStatus,
    Volatility,
    MarketMetrics,
    RegimeBiasInfo,
    HestonVolInfo,
    SLTPPreset,
)
from app.schemas.metrics import MetricsResponse, SentimentInfo
from utils.spectrum import DirectionalSpectrum
from app.core.engines.layer1_volatility import get_vol_estimator
from app.use_cases.risk_manager import get_risk_manager


# ── Constants ──────────────────────────────────────────────────────────────────

_VALID_VERDICTS = {"STRONG BUY", "WEAK BUY", "NEUTRAL", "WEAK SELL", "STRONG SELL"}
_LAYER_WEIGHT   = 25    # Legacy: 4 layers × 25 = 100 max
_BASE_SIZE      = 5.0   # Base portfolio % for position sizing

_spectrum    = DirectionalSpectrum()    # Module-level singleton
_vol_est     = get_vol_estimator()      # ECONOPHYSICS — Modul B singleton
_risk_mgr    = get_risk_manager()       # Risk Management singleton


# ── Pure helpers ───────────────────────────────────────────────────────────────

def _compute_score(l1: bool, l2: bool, l3: bool, l4: bool) -> int:
    return _LAYER_WEIGHT * sum([l1, l2, l3, l4])


def _compute_probability(score: int) -> str:
    return "high" if score >= 70 else "med" if score >= 40 else "low"


def _enforce_verdict(score: int, trend_short: str, llm_verdict: str) -> str:
    is_bull = trend_short == "BULL"
    if score < 40:
        return "NEUTRAL"
    if score >= 80:
        return "STRONG BUY" if is_bull else "STRONG SELL"
    cleaned  = llm_verdict if llm_verdict in _VALID_VERDICTS else "NEUTRAL"
    bull_set = {"STRONG BUY", "WEAK BUY"}
    bear_set = {"STRONG SELL", "WEAK SELL"}
    if is_bull and cleaned in bull_set:
        return cleaned
    if not is_bull and cleaned in bear_set:
        return cleaned
    return "WEAK BUY" if is_bull else "WEAK SELL"


def _trade_plan_status_from_spectrum(gate: str, conviction: float, score: int) -> tuple[str, str]:
    if gate == "ACTIVE":
        return ("ACTIVE",
                f"Spectrum conviction {conviction:.1f}% (ACTIVE) | Legacy {score}/100. "
                "Execute when price enters entry zone with 15m confirmation.")
    if gate == "ADVISORY":
        return ("ADVISORY",
                f"Spectrum conviction {conviction:.1f}% (ADVISORY) | Legacy {score}/100. "
                "Reduce size, wait for 15m confirmation.")
    return ("SUSPENDED",
            f"Spectrum conviction {conviction:.1f}% below threshold | Legacy {score}/100. "
            "Do not trade. Wait for next 4H candle.")


# ── Safe wrappers ──────────────────────────────────────────────────────────────

def _safe_hmm_posterior(
    hmm_svc, df: pd.DataFrame, trend_short: str, funding_rate: float = 0.0
) -> tuple[str, str, float]:
    """PHASE 3: (label, tag, posterior_confidence)."""
    try:
        label, tag, conf = hmm_svc.get_regime_with_posterior(df, funding_rate=funding_rate)
        return label, tag, conf
    except Exception:
        tag = "bull" if trend_short == "BULL" else "bear"
        return f"Fallback {trend_short.title()} Regime", tag, 0.25


def _safe_hmm_states(
    hmm_svc, df: pd.DataFrame
) -> tuple[np.ndarray | None, pd.Index | None]:
    """PHASE 3: Raw state array + index for MLP cross-feature."""
    try:
        return hmm_svc.get_state_sequence_raw(df)
    except Exception:
        return None, None


def _safe_ai_cross(
    ai_svc, df: pd.DataFrame,
    hmm_states: np.ndarray | None,
    hmm_index:  pd.Index   | None,
) -> tuple[str, float]:
    """PHASE 3: AI confidence with HMM cross features."""
    try:
        bias, conf = ai_svc.get_confidence(df,
                                           hmm_states=hmm_states,
                                           hmm_index=hmm_index)
        return str(bias), float(conf)
    except Exception:
        return "NEUTRAL", 50.0


def _safe_llm(market_state: dict) -> dict:
    try:
        result = get_llm_synthesis(market_state)
        return result if isinstance(result, dict) else {}
    except Exception:
        return {}


# ── Fallback ───────────────────────────────────────────────────────────────────

def _build_fallback(
    reason: str,
    price: PriceSnapshot = None,
    trend: TrendInfo = None,
    metrics: MarketMetrics = None
) -> SignalResponse:
    now_utc = datetime.utcnow()
    # Default objects if none provided
    p = price or PriceSnapshot(now=0.0, ema20=0.0, ema50=0.0, atr14=0.0,
                                ema20_prev=0.0, ema50_prev=0.0)
    t = trend or TrendInfo(bias="Neutral", short="BEAR",
                            ema_structure="N/A", momentum="N/A")
    m = metrics or MarketMetrics(funding_rate=0.0, open_interest=0.0,
                                    order_book_imbalance=0.0, global_mcap_change_pct=0.0,
                                    obi_label="N/A", funding_label="N/A")

    return SignalResponse(
        timestamp   = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        is_fallback = True,
        price       = p,
        trend       = t,
        trade_plan  = TradePlan(
            action="LONG" if t.short == "BULL" else "SHORT",
            entry_start=p.now, entry_end=p.now,
            sl=p.now, tp1=p.now, tp2=p.now, leverage=1,
            position_size="0% Portfolio", position_size_pct=0.0,
            status="SUSPENDED", status_reason=f"Fallback — {reason}",
        ),
        confluence  = Confluence(
            aligned_count=0, confluence_score=0,
            directional_bias=0.0, conviction_pct=0.0, layer_contributions={},
            probability="low", verdict="NEUTRAL",
            rationale=f"- {reason}\n- Fallback mode active.",
            conclusion="Signal unavailable.",
            layers=ConfluenceLayers(
                l1_hmm =LayerStatus(aligned=False, label="N/A", detail="Fallback", contribution=0.0),
                l2_tech=LayerStatus(aligned=False, label="N/A", detail="Fallback", contribution=0.0),
                l3_ai  =LayerStatus(aligned=False, label="N/A", detail="Fallback", contribution=0.0),
                l4_risk=LayerStatus(aligned=False, label="N/A", detail="Fallback", contribution=0.0),
            ),
        ),
        volatility     = Volatility(label="N/A", ratio=0.0),
        market_metrics = m,
        validity_utc=now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


# ── Main service ───────────────────────────────────────────────────────────────

class SignalService:

    def get_signal(self) -> SignalResponse:
        now_utc = datetime.utcnow()

        repo    = get_market_repository()
        df      = repo.get_ohlcv_with_metrics()
        metrics = repo.get_latest_metrics()

        if df is None or df.empty or len(df) < 50:
            return _build_fallback("Insufficient OHLCV data — is data_engine running?")

        try:
            # ── 2. Indicators ──────────────────────────────────────────────────
            df["EMA20"] = ta.ema(df["Close"], length=20)
            df["EMA50"] = ta.ema(df["Close"], length=50)
            df["ATR14"] = ta.atr(df["High"], df["Low"], df["Close"], length=14)

            curr = df.iloc[-1]
            prev = df.iloc[-2]

            price_now  = float(curr["Close"])
            ema20_now  = float(curr["EMA20"])
            ema50_now  = float(curr["EMA50"])
            atr14_now  = float(curr["ATR14"])
            ema20_prev = float(prev["EMA20"])
            ema50_prev = float(prev["EMA50"])

            # ── 3. EMA Trend direction — used for structural context only ─────
            # [TASK-1] Renamed action_side → ema_direction to clarify it's EMA-derived.
            # Trade direction (final_action) will be set by Spectrum AFTER scoring.
            # [TASK-2] Fixed 5-condition logic — added explicit price<EMA20 bear case.
            if ema20_now < ema50_now and price_now < ema20_now:
                trend_bias, trend_short, ema_struct, ema_direction = (
                    "Bearish", "BEAR", "EMA20 below EMA50 → Bearish", "SHORT")
                momentum_label = "Strong — Price below EMA20"
            elif ema20_now > ema50_now and price_now > ema20_now:
                trend_bias, trend_short, ema_struct, ema_direction = (
                    "Bullish", "BULL", "EMA20 above EMA50 → Bullish", "LONG")
                momentum_label = "Strong — Price above EMA20"
            elif price_now < ema50_now:
                trend_bias, trend_short, ema_struct, ema_direction = (
                    "Bearish", "BEAR", "EMA20 near EMA50 → Bearish bias", "SHORT")
                momentum_label = ("Strong — Price below EMA20"
                                  if price_now < ema20_now else "Weak — Price back above EMA20")
            elif price_now < ema20_now:
                # [TASK-2] Previously fell into the else (LONG) — correct: price below EMA20 → bearish
                trend_bias, trend_short, ema_struct, ema_direction = (
                    "Bearish", "BEAR", "Price below EMA20 (EMA20>EMA50) → Bearish", "SHORT")
                momentum_label = "Weak — Price pulled back below EMA20"
            else:
                trend_bias, trend_short, ema_struct, ema_direction = (
                    "Bullish", "BULL", "EMA20 near EMA50 → Bullish bias", "LONG")
                momentum_label = "Weak — Price back below EMA20 but above EMA50"

            # ── 4. Risk parameters (Base values, overwritten by Heston) ─────────
            # [TASK-1] Use ema_direction as structural placeholder — will be overridden
            # by final_action (from Spectrum) after scoring in step 6b.
            risk_atr = atr14_now * 1.5
            if ema_direction == "SHORT":
                sl, tp1, tp2 = (price_now + risk_atr,
                                price_now - risk_atr * 1.5,
                                price_now - risk_atr * 2.5)
                entry_start, entry_end = price_now, price_now + atr14_now * 0.2
            else:
                sl, tp1, tp2 = (price_now - risk_atr,
                                price_now + risk_atr * 1.5,
                                price_now + risk_atr * 2.5)
                entry_start, entry_end = price_now - atr14_now * 0.2, price_now

            vol_ratio = atr14_now / price_now if price_now else 0.0
            vol_label = "High" if vol_ratio > 0.012 else "Low"

            # ── 5. Layer evaluation — PHASE 3: HMM first, then MLP with cross ─
            hmm_svc = get_bcd_service()
            ai_svc  = get_ai_service()
            ema_svc = get_ema_service()

            # ── 5.0 Get current metrics for NHHM (PHASE 6) ─────────────────────
            funding_rate  = float(metrics.get("funding_rate",  0.0) or 0.0)
            open_interest = float(metrics.get("open_interest", 0.0) or 0.0)
            obi           = float(metrics.get("order_book_imbalance", 0.0) or 0.0)
            mcap_change   = float(metrics.get("global_mcap_change",   0.0) or 0.0)

            # Labels for metrics (computed early for fallback)
            funding_label = ("Positive — Short Liquidation Risk" if funding_rate > 0.0001
                             else "Negative — Long Liquidation Risk" if funding_rate < -0.0001
                             else "Neutral")
            obi_label = ("Buy Dominant" if obi > 0.2
                         else "Sell Dominant" if obi < -0.2 else "Balanced")

            # [FIX-1c] NEUTRAL REGIME GUARD
            _pre_label, _, _ = _safe_hmm_posterior(
                hmm_svc, df, trend_short, funding_rate=float(metrics.get("funding_rate", 0.0))
            )
            _neutral_kw = ("neutral", "sideways", "lv_sw", "hv_sw", "unknown")
            if any(kw in _pre_label.lower() for kw in _neutral_kw):
                return _build_fallback(
                    reason=f"Regime neutral/sideways ({_pre_label}) — no edge. "
                           "Backtest: 215 neutral trades = -$1,974. Suspended.",
                    price=PriceSnapshot(now=price_now, ema20=ema20_now, ema50=ema50_now, atr14=atr14_now,
                                        ema20_prev=ema20_prev, ema50_prev=ema50_prev),
                    trend=TrendInfo(bias=trend_bias, short=trend_short,
                                    ema_structure=ema_struct, momentum=momentum_label),
                    metrics=MarketMetrics(funding_rate=funding_rate, open_interest=open_interest,
                                          order_book_imbalance=round(obi, 6),
                                          global_mcap_change_pct=round(mcap_change, 4),
                                          obi_label=obi_label, funding_label=funding_label)
                )

            # 5a. HMM: label + tag + posterior confidence (PHASE 3 + PHASE 6)
            hmm_label, hmm_tag, hmm_post_conf = _safe_hmm_posterior(
                hmm_svc, df, trend_short, funding_rate=funding_rate
            )

            # ── ECONOPHYSICS Modul A: Regime Bias dari Matriks Transisi ──────
            regime_bias_all  = hmm_svc.get_regime_bias()
            current_bias_obj = regime_bias_all.get(hmm_label, {})
            bias_score       = float(current_bias_obj.get("bias_score", 0.5))
            persistence      = float(current_bias_obj.get("persistence", 0.5))
            expected_dur     = float(current_bias_obj.get("expected_duration_candles", 0.0))

            # ── ECONOPHYSICS Modul B: Heston Volatility Estimator ────────────
            vol_params    = _vol_est.estimate_params(df)
            vol_regime_h  = vol_params.get("vol_regime",  "Normal")
            halflife_h    = float(vol_params.get("mean_reversion_halflife_candles", 999.0))
            current_vol_h = float(vol_params.get("current_vol",  0.0))
            long_run_vol_h = float(vol_params.get("long_run_vol", 0.0))
            heston_interp = vol_params.get("interpretation", "")

            # Gabungkan Modul A + B untuk SL/TP multiplier (I-05 PRD)
            sl_tp_mults = _vol_est.get_sl_tp_multipliers(
                vol_regime  = vol_regime_h,
                halflife    = halflife_h,
                bias_score  = bias_score,
            )

            # ── MODULE F: LEVERAGE + RISK MANAGEMENT ─────────────────────────
            # [FIX-3a] Ambil portfolio_value REAL dari paper trade account
            try:
                _pt_svc = _PaperTradeService()
                _account = _pt_svc.get_account()
                _portfolio_value = float(_account.get("equity", 10_000.0))
            except Exception:
                _portfolio_value = 10_000.0

            risk_verdict = _risk_mgr.evaluate(
                portfolio_value    = _portfolio_value,   # [FIX-3a] REAL equity
                atr                = atr14_now,
                sl_multiplier      = sl_tp_mults["sl_multiplier"],
                requested_leverage = int(max(1, min(20, round(
                    0.04 / (sl_tp_mults["tp1_multiplier"] * vol_ratio)
                    if vol_ratio > 0 else 1
                )))),
                current_price      = price_now,
            )

            # ── 5.1 FGI SENTIMENT ADJUSTMENT (PHASE D) ──────────────────────
            fgi_score = float(metrics.get("fgi_value", 50.0))
            sentiment_adj = 1.0
            
            # Extreme Greed (> 80) -> Risk off (reduce all positions)
            if fgi_score > 80:
                sentiment_adj = 0.75
            # Extreme Fear (< 20) -> Reduce LONG position size (contrarian caution)
            # [TASK-5] Use ema_direction here — sentiment adj is structural, pre-Spectrum
            elif fgi_score < 20 and ema_direction == "LONG":
                sentiment_adj = 0.75

            # If daily loss cap triggered → suspend
            if not risk_verdict.can_trade:
                return _build_fallback(risk_verdict.rejection_reason)

            leverage        = risk_verdict.approved_leverage
            pos_size_pct    = risk_verdict.position_size_pct * sentiment_adj

            # [TASK-8] Long/Short ratio contrarian filter
            ls_ratio = float(metrics.get('long_short_ratio', 0.5))
            ls_label = str(metrics.get('long_short_label', 'Balanced'))
            crowded_adj = 1.0
            if ls_label == 'Extreme Long' and ema_direction == 'LONG':
                crowded_adj = 0.7
            elif ls_label == 'Extreme Short' and ema_direction == 'SHORT':
                crowded_adj = 0.7
            elif ls_label == 'Extreme Long' and ema_direction == 'SHORT':
                crowded_adj = 1.15
            elif ls_label == 'Extreme Short' and ema_direction == 'LONG':
                crowded_adj = 1.15

            # [TASK-1] SL/TP multipliers stored — will be applied AFTER Spectrum
            # determines final_action. See step 6b below.
            _sl_m  = sl_tp_mults["sl_multiplier"]
            _tp1_m = sl_tp_mults["tp1_multiplier"]
            _tp2_m = sl_tp_mults["tp2_multiplier"]

            # 5b. HMM state sequence for MLP cross-feature (PHASE 3)
            hmm_states_arr, hmm_states_idx = _safe_hmm_states(hmm_svc, df)

            # 5c. MLP with HMM feature cross (PHASE 3)
            ai_bias, ai_conf = _safe_ai_cross(
                ai_svc, df,
                hmm_states = hmm_states_arr,
                hmm_index  = hmm_states_idx,
            )
            cross_enabled = ai_svc.is_cross_enabled()

            # 5d. EMA Alignment (PHASE 5)
            l2, l2_label_custom, l2_detail = ema_svc.get_alignment(df, trend_short)

            # [FIX-SIGNAL #3] RSI + EMA Proximity Check untuk L2 modifier
            df["RSI14"] = ta.rsi(df["Close"], length=14)
            rsi_now = float(df["RSI14"].iloc[-1]) if len(df) > 0 and not pd.isna(df["RSI14"].iloc[-1]) else 50.0
            ema_distance_ratio = abs(price_now - ema20_now) / atr14_now if atr14_now > 0 else 999.0

            # L2 weakening conditions:
            # 1. RSI overbought (>68) saat trend BULL → potential reversal down
            # 2. RSI oversold (<32) saat trend BEAR → potential reversal up
            # 3. Price terlalu dekat EMA20 (< 0.2 ATR) → EMA confirmation tidak reliable
            # 4. EMA20 ≈ EMA50 (< 0.1% selisih) → transisi, tidak ada tren yang jelas
            _l2_weakened = False
            ema_gap_ratio = abs(ema20_now - ema50_now) / ema50_now if ema50_now > 0 else 0
            if trend_short == "BULL" and rsi_now > 68:
                _l2_weakened = True
            elif trend_short == "BEAR" and rsi_now < 32:
                _l2_weakened = True
            elif ema_distance_ratio < 0.2:
                _l2_weakened = True
            elif ema_gap_ratio < 0.001:  # EMA20 dan EMA50 hampir sama → ambiguous zone
                _l2_weakened = True

            l1 = hmm_tag == ("bull" if trend_short == "BULL" else "bear")
            # l2 sudah di-compute oleh ema_svc
            l3 = ai_conf >= 55.0 and ai_bias == trend_short
            l4 = vol_ratio < 0.02

            aligned_count = sum([l1, l2, l3, l4])

            # ── 6a. Legacy score ───────────────────────────────────────────────
            score = _compute_score(l1, l2, l3, l4)

            # ── 6b. Spectrum (PHASE 2 + PHASE 3 posterior) ────────────────────
            mlp_conf_norm = (max(50.0, min(100.0, ai_conf)) - 50.0) / 50.0

            # [FIX-SIGNAL #1] L3 Disagreement Detection
            # Jika L3 output NEUTRAL padahal L1 directional (fed dari HMM), itu counter-signal
            # L3 di-input hmm_states → jika tetap NEUTRAL = market data melawan regime L1
            _l3_disagrees = (
                ai_bias.upper() == "NEUTRAL"
                and hmm_tag in ("bull", "bear")
                and ai_conf <= 55.0
            )

            # Map layer outputs to continuous [-1, +1] votes for v2 Spectrum
            def _to_vote_three_state(tag: str, conf: float) -> float:
                if tag == "bull": return float(conf)
                if tag == "bear": return -float(conf)
                return 0.0  # neutral

            l1_vote = _to_vote_three_state(hmm_tag, hmm_post_conf)

            # [FIX-SIGNAL #3] L2 vote dengan weakening modifier
            # Jika L2 weakened: force l2=False (bukan sekadar reduce confidence)
            # RSI extreme / EMA ambiguous = EMA confirmation tidak bisa dipercaya
            if _l2_weakened:
                l2 = False  # Override l2 — disable alignment
            l2_base_conf = 1.0 if l2 else 0.0
            l2_vote = 1.0 * l2_base_conf if (l2 and trend_short == "BULL") else -1.0 * l2_base_conf if (l2 and trend_short == "BEAR") else 0.0

            # [FIX-SIGNAL #1] L3 vote dengan disagreement handling
            if _l3_disagrees:
                # L3 NEUTRAL padahal di-feed BULL/BEAR = counter-signal magnitude 0.3
                l3_vote = -0.3 if hmm_tag == "bull" else +0.3
            else:
                l3_vote = _to_vote_three_state(ai_bias.lower(), mlp_conf_norm)
            l4_mult = _spectrum.compute_l4_multiplier(vol_ratio)
            
            spectrum = _spectrum.calculate(
                l1_vote       = l1_vote,
                l2_vote       = l2_vote,
                l3_vote       = l3_vote,
                l4_multiplier = l4_mult,
                base_size     = _BASE_SIZE,
            )

            # [TASK-1] final_action comes from Spectrum — the validated scoring engine.
            # ema_direction is structural context only; Spectrum is the authority on direction.
            final_action = spectrum.action  # "LONG" | "SHORT" from directional_bias sign

            # [TASK-8] Apply crowded_adj after Spectrum determines final direction
            pos_size_pct = pos_size_pct * crowded_adj

            # [TASK-9] Exchange netflow filter (whale activity)
            netflow_label = str(metrics.get('exchange_netflow_label', 'Neutral'))
            if netflow_label == 'Large Inflow' and final_action == 'LONG':
                pos_size_pct *= 0.6
            elif netflow_label == 'Large Outflow' and final_action == 'SHORT':
                pos_size_pct *= 0.6
            elif netflow_label == 'Large Outflow' and final_action == 'LONG':
                pos_size_pct *= 1.1
            elif netflow_label == 'Large Inflow' and final_action == 'SHORT':
                pos_size_pct *= 1.1

            # [TASK-1] Recompute SL/TP/entry using final_action (Spectrum-derived direction)
            if final_action == "SHORT":
                sl  = price_now + atr14_now * _sl_m
                tp1 = price_now - atr14_now * _tp1_m
                tp2 = price_now - atr14_now * _tp2_m
                entry_start, entry_end = price_now, price_now + atr14_now * 0.2
            else:
                sl  = price_now - atr14_now * _sl_m
                tp1 = price_now + atr14_now * _tp1_m
                tp2 = price_now + atr14_now * _tp2_m
                entry_start, entry_end = price_now - atr14_now * 0.2, price_now

            # ── 7. Market metrics ──────────────────────────────────────────────
            # labels already defined above
            
            fgi_label = (
                "Extreme Greed" if fgi_score > 75
                else "Greed" if fgi_score > 55
                else "Fear" if fgi_score < 45
                else "Extreme Fear" if fgi_score < 25
                else "Neutral"
            )

            # ── 8. LLM synthesis ───────────────────────────────────────────────
            # Decision context for L5 Narrative
            decision_payload: dict = {
                "confluence_score"     : score,
                "directional_bias"     : spectrum.directional_bias,
                "conviction_pct"       : spectrum.conviction_pct,
                "hmm_posterior_conf"   : round(hmm_post_conf, 4),
                "mlp_cross_enabled"    : cross_enabled,
                "trend_bias"           : trend_bias,
                "hmm_state"            : hmm_label,
                "hmm_tag"              : hmm_tag,
                "ema_structure"        : ema_struct,
                "atr_14"               : round(atr14_now, 2),
                "funding_rate"         : funding_rate,
                "open_interest"        : open_interest,
                "order_book_imbalance" : round(obi, 6),
                "mlp_bias"             : ai_bias,
                "mlp_confidence"       : round(ai_conf, 1),
                # ECONOPHYSICS — Modul A + B
                "regime_bias_score"    : round(bias_score, 4),
                "regime_persistence"   : round(persistence, 4),
                "regime_expected_duration": expected_dur,
                "heston_vol_regime"    : vol_regime_h,
                "heston_current_vol"   : round(current_vol_h, 4),
                "heston_long_run_vol"  : round(long_run_vol_h, 4),
                "heston_halflife"      : halflife_h,
                "sl_tp_preset"         : sl_tp_mults.get("preset_name", ""),
                "layers": {
                    "l1": {"aligned": l1, "label": hmm_label},
                    "l2": {"aligned": l2, "label": l2_label_custom},
                    "l3": {"aligned": l3, "label": ai_bias},
                    "l4": {"aligned": l4, "label": vol_label}
                }
            }
            if mcap_change != 0.0:
                decision_payload["global_mcap_change_pct"] = round(mcap_change, 4)

            # L5 Narrative Engine call (Decision Engine -> Narrative Engine flow)
            narr_svc = get_narrative_service()
            narrative = narr_svc.get_narrative(decision_payload)
            
            raw_verdict = narrative.get("verdict", "NEUTRAL")
            rationale   = narrative.get("rationale", "- No LLM rationale available.")
            fng_status  = narrative.get("fng_info", "Neutral")

            # ── 9. Truth Enforcer ──────────────────────────────────────────────
            # [TASK-5] Use final_action (Spectrum) not trend_short (EMA) for verdict
            _final_short = "BULL" if final_action == "LONG" else "BEAR"
            verdict     = _enforce_verdict(score, _final_short, raw_verdict)
            probability = _compute_probability(score)

            # ── 10. Trade plan status from spectrum ────────────────────────────
            tp_status, tp_reason = _trade_plan_status_from_spectrum(
                gate=spectrum.trade_gate, conviction=spectrum.conviction_pct, score=score
            )

            conclusion = (
                f"High Conviction ({spectrum.conviction_pct:.1f}%) — "
                "execute when price enters entry zone."
                if spectrum.trade_gate == "ACTIVE"
                else f"Moderate Conviction ({spectrum.conviction_pct:.1f}%) — "
                "wait for 15m confirmation."
                if spectrum.trade_gate == "ADVISORY"
                else f"Low Conviction ({spectrum.conviction_pct:.1f}%) — "
                "avoid entry, wait for next 4H candle."
            )

            # Validity window
            next_h = ((now_utc.hour // 4) + 1) * 4
            if next_h >= 24:
                next_close = (now_utc + timedelta(days=1)).replace(
                    hour=next_h - 24, minute=0, second=0, microsecond=0)
            else:
                next_close = now_utc.replace(
                    hour=next_h, minute=0, second=0, microsecond=0)

            lc = spectrum.layer_contributions

            # Layer labels — include cross indicator on L3
            l2_label = l2_label_custom  # Dari ema_svc
            l3_label = (
                f"{ai_conf:.1f}% ({ai_bias})"
                + (" [+BCD]" if cross_enabled else "")
                if l3
                else f"Low Conf — {ai_conf:.1f}% ({ai_bias})"
                + (" [+BCD]" if cross_enabled else "")
            )
            l4_label = (f"Vol {vol_label} — SL Safe" if l4
                        else f"Vol {vol_label} — Caution")

            pos_size_str = (
                f"{pos_size_pct:.2f}% Portfolio "
                f"(risk 2%/trade | lev {leverage}×"
                + (f" | ⚙️ Sentiment Adj: {sentiment_adj:.2f}" if sentiment_adj != 1.0 else "")
                + (" | ⚠️ DE-LEVERAGED" if risk_verdict.is_deleveraged else "")
                + ")"
            )

            return SignalResponse(
                timestamp   = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
                is_fallback = False,
                price       = PriceSnapshot(
                    now=price_now, ema20=ema20_now, ema50=ema50_now, atr14=atr14_now,
                    ema20_prev=ema20_prev, ema50_prev=ema50_prev,
                ),
                trend       = TrendInfo(bias=trend_bias, short=trend_short,
                                        ema_structure=ema_struct, momentum=momentum_label),
                trade_plan  = TradePlan(
                    action=final_action,  # [TASK-1] Spectrum-derived direction
                    entry_start=round(entry_start, 2), entry_end=round(entry_end, 2),
                    sl=round(sl, 2), tp1=round(tp1, 2), tp2=round(tp2, 2),
                    leverage=leverage,
                    position_size=pos_size_str,
                    position_size_pct=pos_size_pct,
                    status=tp_status, status_reason=tp_reason,
                ),
                confluence  = Confluence(
                    aligned_count=aligned_count,
                    confluence_score=score,
                    directional_bias=spectrum.directional_bias,
                    conviction_pct=spectrum.conviction_pct,
                    layer_contributions=lc,
                    probability=probability,
                    verdict=verdict,
                    rationale=rationale,
                    conclusion=conclusion,
                    layers=ConfluenceLayers(
                        l1_hmm =LayerStatus(aligned=l1, label=hmm_label,  detail="BCD Model",    contribution=lc.get("l1_hmm", 0.0)),
                        l2_tech=LayerStatus(aligned=l2, label=l2_label,   detail=l2_detail,      contribution=lc.get("l2_ema", 0.0)),
                        l3_ai  =LayerStatus(aligned=l3, label=l3_label,   detail="MLP+BCD Cross" if cross_enabled else "MLP Model", contribution=lc.get("l3_mlp", 0.0)),
                        l4_risk=LayerStatus(aligned=l4, label=l4_label,   detail="ATR-based SL", contribution=lc.get("l4_risk",0.0)),
                    ),
                ),
                volatility     = Volatility(label=vol_label, ratio=round(vol_ratio, 6)),
                market_metrics = MarketMetrics(
                    funding_rate=funding_rate, open_interest=open_interest,
                    order_book_imbalance=round(obi, 6),
                    global_mcap_change_pct=round(mcap_change, 4),
                    obi_label=obi_label, funding_label=funding_label,
                    fgi_score=int(fgi_score), fgi_label=fgi_label,
                    long_short_ratio=ls_ratio,
                    long_short_label=ls_label,
                    funding_consensus=str(metrics.get('funding_consensus', 'MIXED')),
                    funding_spread=float(metrics.get('funding_spread', 0.0)),
                    exchange_netflow_btc=float(metrics.get('exchange_netflow_btc', 0.0)),
                    exchange_netflow_label=netflow_label,
                    crowded_adjustment=crowded_adj,
                ),
                validity_utc=next_close.strftime("%Y-%m-%dT%H:%M:%SZ"),
                sentiment_adjustment=sentiment_adj,
                crowded_adjustment=crowded_adj,
                # ── ECONOPHYSICS fields ─────────────────────────────────────────
                # Modul A: Regime Bias dari Transition Matrix (Proses Markov)
                regime_bias=RegimeBiasInfo(
                    persistence               = current_bias_obj.get("persistence",   0.5),
                    reversal_prob             = current_bias_obj.get("reversal_prob", 0.0),
                    bias_score                = current_bias_obj.get("bias_score",    0.5),
                    expected_duration_candles = current_bias_obj.get("expected_duration_candles", 0.0),
                    interpretation            = current_bias_obj.get("interpretation", ""),
                    next_state_probs          = current_bias_obj.get("next_state_probs", {}),
                ) if current_bias_obj else None,
                # Modul B: Heston Volatility (dv = -γ(v-η)dt + κ√v·dB_v)
                heston_vol=HestonVolInfo(
                    gamma                           = vol_params.get("gamma",       0.0),
                    eta                             = vol_params.get("eta",         0.0),
                    kappa                           = vol_params.get("kappa",       0.0),
                    current_vol                     = current_vol_h,
                    long_run_vol                    = long_run_vol_h,
                    vol_regime                      = vol_regime_h,
                    mean_reversion_halflife_candles = halflife_h,
                    interpretation                  = heston_interp,
                ),
                # SL/TP preset dari kombinasi Modul A + Modul B
                sl_tp_preset=SLTPPreset(
                    preset_name    = sl_tp_mults.get("preset_name",    "Normal"),
                    sl_multiplier  = sl_tp_mults.get("sl_multiplier",  1.5),
                    tp1_multiplier = sl_tp_mults.get("tp1_multiplier", 1.5),
                    tp2_multiplier = sl_tp_mults.get("tp2_multiplier", 2.5),
                    rationale      = sl_tp_mults.get("rationale",      ""),
                ),
            )

        except Exception as exc:
            return _build_fallback(f"Pipeline error — {type(exc).__name__}: {exc}")

    def get_metrics(self) -> MetricsResponse:
        metrics = get_market_repository().get_latest_metrics()
        # Use narrative_service's sentiment provider
        narr_svc = get_narrative_service()
        try:
            val, label = narr_svc._sent_engine.fetch_fear_and_greed()
        except Exception:
            val, label = 50, "Neutral"
        
        return MetricsResponse(
            funding_rate=metrics.get("funding_rate", 0.0),
            open_interest=metrics.get("open_interest", 0.0),
            order_book_imbalance=metrics.get("order_book_imbalance", 0.0),
            global_mcap_change_pct=metrics.get("global_mcap_change", 0.0),
            sentiment=SentimentInfo(
                score=val,
                label=label,
                note="External market psychology index."
            ),
        )


# ── Singleton ──────────────────────────────────────────────────────────────────

_svc: SignalService | None = None
_svc_lock = _threading.Lock()

# ── Signal cache — single source of truth ─────────────────────────────────────
# Dashboard, Telegram, dan Paper Trade harus selalu pakai signal yang sama.
# Cache ini di-update oleh data_ingestion_use_case setiap candle 4H baru.
# Dashboard GET /api/signal mengembalikan cache ini, bukan recompute ulang.
_cached_signal: SignalResponse | None = None
_cached_signal_lock = _threading.Lock()


def get_signal_service() -> SignalService:
    global _svc
    if _svc is None:
        with _svc_lock:
            if _svc is None:
                _svc = SignalService()
    return _svc


def set_cached_signal(signal: SignalResponse) -> None:
    """Called by data_ingestion_use_case after computing signal for a new candle."""
    global _cached_signal
    with _cached_signal_lock:
        _cached_signal = signal


def get_cached_signal() -> SignalResponse | None:
    """Returns the last signal computed for a new 4H candle. None if not yet computed."""
    return _cached_signal
