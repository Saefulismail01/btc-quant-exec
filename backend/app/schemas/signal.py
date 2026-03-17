from pydantic import BaseModel, Field
from typing import Literal, Optional


# ─────────────────────────────────────────────
#  Market snapshot
# ─────────────────────────────────────────────

class PriceSnapshot(BaseModel):
    now: float
    ema20: float
    ema50: float
    atr14: float
    ema20_prev: float
    ema50_prev: float


class TrendInfo(BaseModel):
    bias: str
    short: Literal["BULL", "BEAR"]
    ema_structure: str
    momentum: str


class Volatility(BaseModel):
    label: str
    ratio: float


class MarketMetrics(BaseModel):
    funding_rate: float
    open_interest: float
    order_book_imbalance: float
    global_mcap_change_pct: float
    obi_label: str
    funding_label: str
    fgi_score: int = 50
    fgi_label: str = "Neutral"
    # [TASK-7/8] Cross-exchange & L/S ratio fields
    long_short_ratio: float = 0.5
    long_short_label: str = "Balanced"
    funding_consensus: str = "MIXED"
    funding_spread: float = 0.0
    # [TASK-9] On-chain netflow fields
    exchange_netflow_btc: float = 0.0
    exchange_netflow_label: str = "Neutral"
    # [TASK-8] Crowded position adjustment applied
    crowded_adjustment: float = 1.0


# ─────────────────────────────────────────────
#  Trade plan
# ─────────────────────────────────────────────

class TradePlan(BaseModel):
    action: Literal["LONG", "SHORT"]
    entry_start: float
    entry_end: float
    sl: float
    tp1: float
    tp2: float
    leverage: int
    position_size: str          # Legacy: human-readable string e.g. "Max 5% Portfolio"
    position_size_pct: float = 0.0   # SPECTRUM: exact % derived from conviction
    status: Literal["ACTIVE", "ADVISORY", "SUSPENDED"] = "SUSPENDED"
    status_reason: str = ""


# ─────────────────────────────────────────────
#  Confluence — single source of truth for all
#  signal authority fields (score, verdict, rationale)
# ─────────────────────────────────────────────

class LayerStatus(BaseModel):
    aligned: bool
    label: str
    detail: str
    contribution: float = 0.0   # SPECTRUM: this layer's weighted contribution


class ConfluenceLayers(BaseModel):
    l1_hmm: LayerStatus
    l2_tech: LayerStatus
    l3_ai: LayerStatus
    l4_risk: LayerStatus


class Confluence(BaseModel):
    # Quantitative — legacy
    aligned_count: int
    total: int = 4
    confluence_score: int                              # 0–100, binary banded (legacy)
    probability: Literal["high", "med", "low"]

    # SPECTRUM — new continuous scoring fields
    directional_bias: float = Field(
        default=0.0,
        ge=-1.0,
        le=1.0,
        description=(
            "Continuous directional score in [-1.0, +1.0]. "
            "Positive = bullish conviction, negative = bearish. "
            "Magnitude = strength of conviction."
        ),
    )
    conviction_pct: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="abs(directional_bias) × 100. Used for position sizing.",
    )
    layer_contributions: dict = Field(
        default_factory=dict,
        description="Per-layer weighted contribution breakdown.",
    )

    # Qualitative (LLM-generated, score-constrained)
    verdict: Literal["STRONG BUY", "WEAK BUY", "NEUTRAL", "WEAK SELL", "STRONG SELL"]
    rationale: str
    conclusion: str
    layers: ConfluenceLayers


# ─────────────────────────────────────────────
#  Top-level response
# ─────────────────────────────────────────────

# ─────────────────────────────────────────────
#  ECONOPHYSICS OUTPUT SCHEMAS
#  Modul A (Transition Matrix) + Modul B (Heston)
# ─────────────────────────────────────────────

class RegimeBiasInfo(BaseModel):
    """
    ECONOPHYSICS Modul A: Output dari Transition Probability Matrix.
    P[i,j] = P(X_{t+1}=j | X_t=i) dari teori Proses Markov.
    """
    persistence:               float = 0.5   # P[i,i] — peluang regime berlanjut
    reversal_prob:             float = 0.0   # P[i, berlawanan] — peluang reversal
    bias_score:                float = 0.5   # persistence - reversal_prob
    expected_duration_candles: float = 0.0   # E[T] = 1/(1-P[i,i])
    interpretation:            str   = ""
    next_state_probs:          dict  = Field(default_factory=dict)


class HestonVolInfo(BaseModel):
    """
    ECONOPHYSICS Modul B: Parameter Model Heston.
    dv(t) = -γ(v-η)dt + κ√v·dB_v
    """
    gamma:                             float = 0.0    # mean-reversion speed
    eta:                               float = 0.0    # long-run variance
    kappa:                             float = 0.0    # vol of vol
    current_vol:                       float = 0.0
    long_run_vol:                      float = 0.0
    vol_regime:                        str   = "Normal"   # High / Normal / Low
    mean_reversion_halflife_candles:   float = 999.0
    interpretation:                    str   = ""


class SLTPPreset(BaseModel):
    """SL/TP multiplier preset dari kombinasi Modul A + Modul B."""
    preset_name:    str   = "Normal"
    sl_multiplier:  float = 1.5
    tp1_multiplier: float = 1.5
    tp2_multiplier: float = 2.5
    rationale:      str   = ""


class SignalResponse(BaseModel):
    timestamp: str
    is_fallback: bool = False
    price: PriceSnapshot
    trend: TrendInfo
    trade_plan: TradePlan
    confluence: Confluence
    volatility: Volatility
    market_metrics: MarketMetrics
    validity_utc: str
    sentiment_adjustment: float = 1.0                    # Multiplier applied to position_size_pct
    crowded_adjustment: Optional[float] = None           # [TASK-8] L/S ratio contrarian modifier
    # ECONOPHYSICS fields (optional — default empty jika fallback)
    regime_bias:   Optional[RegimeBiasInfo] = None
    heston_vol:    Optional[HestonVolInfo]  = None
    sl_tp_preset:  Optional[SLTPPreset]     = None
