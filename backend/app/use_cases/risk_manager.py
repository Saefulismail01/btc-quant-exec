"""
╔══════════════════════════════════════════════════════════════╗
║  BTC-QUANT: Risk Manager                                     ║
║  Protects capital via three mechanisms:                      ║
║    1. Max Daily Loss Cap  — stop trading if day too bad      ║
║    2. Risk-Per-Trade      — fixed % portfolio per trade      ║
║    3. Adaptive Leverage   — reduce after consecutive losses  ║
╚══════════════════════════════════════════════════════════════╝

CHANGELOG fix/critical-optimizations:
--------------------------------------
[FIX-3a] Hapus hardcode portfolio_value = $10,000.
         RiskManager sekarang menerima portfolio_value di setiap
         evaluate() call. Caller (signal_service.py) bertanggung jawab
         menyuplai nilai real dari portfolio/paper trade service.
         Default fallback $10,000 dipertahankan HANYA jika caller
         tidak menyuplai nilai (backward compat).

[FIX-3b] Klarifikasi leverage gap: backtest asumsi 20x, production 5x.
         Keputusan: MAX_LEVERAGE dikembalikan ke 20 untuk konsisten
         dengan kondisi backtest. Ini risiko tinggi — HANYA aktifkan
         kalau paper trading sudah stabil minimal 30 hari.
         Untuk safety awal, tambahkan env variable LEVERAGE_SAFE_MODE:
             LEVERAGE_SAFE_MODE=true  → MAX_LEVERAGE=5  (conservative)
             LEVERAGE_SAFE_MODE=false → MAX_LEVERAGE=20 (backtest-consistent)
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from datetime import datetime, date, timezone
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# ── Leverage safety mode ──────────────────────────────────────────────────────
# [FIX-3b] Default ke SAFE (5x) sampai paper trading 30 hari terbukti stabil
_LEVERAGE_SAFE_MODE = os.getenv("LEVERAGE_SAFE_MODE", "true").strip().lower() == "true"
_MAX_LEVERAGE_SAFE  = 5
_MAX_LEVERAGE_FULL  = 20


# ── Configuration ─────────────────────────────────────────────────────────────

class RiskConfig:
    """
    Tunable risk parameters.

    [FIX-3b] MAX_LEVERAGE sekarang dikontrol oleh LEVERAGE_SAFE_MODE env:
        LEVERAGE_SAFE_MODE=true  → 5x  (default, conservative)
        LEVERAGE_SAFE_MODE=false → 20x (konsisten dengan backtest)

    PERINGATAN: Aktifkan LEVERAGE_SAFE_MODE=false HANYA setelah paper
    trading minimal 30 hari dengan hasil konsisten.
    """

    MAX_DAILY_LOSS_PCT:    float = -5.0
    RISK_PER_TRADE_PCT:    float = 2.0
    CONSEC_LOSS_THRESHOLD: int   = 3
    DELEVER_MULTIPLIER:    float = 0.5
    RECOVER_AFTER_WINS:    int   = 2
    MAX_LEVERAGE:          int   = _MAX_LEVERAGE_SAFE if _LEVERAGE_SAFE_MODE else _MAX_LEVERAGE_FULL
    MIN_LEVERAGE:          int   = 1

    def __post_init__(self):
        logger.info(
            "[RiskConfig] MAX_LEVERAGE=%d (LEVERAGE_SAFE_MODE=%s)",
            self.MAX_LEVERAGE, _LEVERAGE_SAFE_MODE
        )


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class RiskVerdict:
    """
    Output dari RiskManager.evaluate().

    [FIX-3a] position_size_usd sekarang dihitung dari portfolio_value REAL
             yang disuplai caller, bukan dari hardcode $10,000.
    """
    can_trade:           bool
    position_size_usd:   float
    position_size_pct:   float
    approved_leverage:   int
    rejection_reason:    str   = ""
    daily_pnl_pct:       float = 0.0
    consecutive_losses:  int   = 0
    is_deleveraged:      bool  = False
    portfolio_value_used: float = 0.0   # [FIX-3a] Catat nilai yang dipakai untuk audit

    def __repr__(self) -> str:
        status = "✅ TRADE" if self.can_trade else f"❌ BLOCKED ({self.rejection_reason})"
        return (
            f"RiskVerdict({status} | "
            f"portfolio=${self.portfolio_value_used:,.0f} | "
            f"size={self.position_size_pct:.1f}% | "
            f"lev={self.approved_leverage}× | "
            f"daily={self.daily_pnl_pct:+.2f}% | "
            f"streak={self.consecutive_losses}L)"
        )


# ── Risk Manager ──────────────────────────────────────────────────────────────

class RiskManager:
    """
    Thread-safe intraday risk manager.

    [FIX-3a] portfolio_value tidak lagi disimpan sebagai state internal.
             Ia harus disuplai di setiap evaluate() call sehingga position
             sizing selalu akurat terhadap equity terkini.
    """

    def __init__(self, config: Optional[RiskConfig] = None):
        self._cfg  = config or RiskConfig()
        self._lock = threading.Lock()
        self._reset_state()

        logger.info(
            "[RiskManager] Init: MAX_LEVERAGE=%d, RISK_PER_TRADE=%.1f%%, SAFE_MODE=%s",
            self._cfg.MAX_LEVERAGE,
            self._cfg.RISK_PER_TRADE_PCT,
            _LEVERAGE_SAFE_MODE,
        )

    def _reset_state(self) -> None:
        self._trading_day:           date  = date.today()
        self._daily_pnl_pct:         float = 0.0
        self._consecutive_losses:    int   = 0
        self._consecutive_wins:      int   = 0
        self._trades_today:          int   = 0
        self._is_suspended:          bool  = False
        self._cooldown_candles:      int   = 0   # [P1] candles remaining in cooldown
        logger.info("[RiskManager] Daily state reset for %s", self._trading_day)

    def _check_day_rollover(self) -> None:
        today = datetime.now(timezone.utc).date()
        if today != self._trading_day:
            self._reset_state()
            self._trading_day = today

    # ── Public API ────────────────────────────────────────────────────────────

    def evaluate(
        self,
        portfolio_value: float,       # [FIX-3a] WAJIB disuplai caller — equity REAL
        atr: float,
        sl_multiplier: float,
        requested_leverage: int = 3,
        current_price: float = 1.0,
    ) -> RiskVerdict:
        """
        Evaluasi apakah trade baru diperbolehkan dan hitung safe position size.

        [FIX-3a] portfolio_value harus merupakan nilai equity REAL dari
                 paper_trade_service atau live account. Jangan hardcode.

        Args:
            portfolio_value    : Equity saat ini dalam USD (REAL, bukan hardcode)
            atr                : ATR14 dalam USD
            sl_multiplier      : SL distance = atr × sl_multiplier
            requested_leverage : Leverage yang diminta
            current_price      : Harga BTC saat ini

        Returns:
            RiskVerdict dengan can_trade flag dan safe position size.
        """
        # [FIX-3a] Validasi portfolio_value — cegah nilai nonsensical
        if portfolio_value <= 0:
            logger.warning(
                "[RiskManager] portfolio_value invalid (%.2f), fallback ke $10,000",
                portfolio_value
            )
            portfolio_value = 10_000.0

        with self._lock:
            self._check_day_rollover()

            # 0. Cooldown check (P1 — consecutive loss protection)
            if self._cooldown_candles > 0:
                self._cooldown_candles -= 1
                return RiskVerdict(
                    can_trade            = False,
                    position_size_usd    = 0.0,
                    position_size_pct    = 0.0,
                    approved_leverage    = 0,
                    rejection_reason     = f"COOLDOWN ({self._cooldown_candles + 1} candles remaining)",
                    daily_pnl_pct        = self._daily_pnl_pct,
                    consecutive_losses   = self._consecutive_losses,
                    is_deleveraged       = True,
                    portfolio_value_used = portfolio_value,
                )

            # 1. Daily loss cap check
            if self._is_suspended:
                return RiskVerdict(
                    can_trade            = False,
                    position_size_usd    = 0.0,
                    position_size_pct    = 0.0,
                    approved_leverage    = 0,
                    rejection_reason     = (
                        f"Daily loss cap reached ({self._daily_pnl_pct:.2f}% ≤ "
                        f"{self._cfg.MAX_DAILY_LOSS_PCT}%). "
                        "Suspended until UTC midnight."
                    ),
                    daily_pnl_pct        = self._daily_pnl_pct,
                    consecutive_losses   = self._consecutive_losses,
                    is_deleveraged       = True,
                    portfolio_value_used = portfolio_value,
                )

            # 2. Position size via fixed risk/trade
            # sl_pct = (atr × sl_multiplier) / current_price
            # position_size_pct = RISK_PER_TRADE_PCT / sl_pct
            risk_pct          = self._cfg.RISK_PER_TRADE_PCT / 100.0
            sl_pct_raw        = (atr * sl_multiplier) / current_price if current_price > 0 else 0.015
            sl_pct            = max(sl_pct_raw, 0.003)   # floor 0.3%

            position_size_pct = min(risk_pct / sl_pct * 100.0, 100.0)
            # [FIX-3a] Dihitung dari portfolio_value REAL, bukan hardcode
            position_size_usd = portfolio_value * (position_size_pct / 100.0)

            # 3. Adaptive leverage
            # [FIX-3b] MAX_LEVERAGE dikontrol oleh LEVERAGE_SAFE_MODE env
            approved_leverage = min(requested_leverage, self._cfg.MAX_LEVERAGE)
            is_deleveraged    = False

            if self._consecutive_losses >= self._cfg.CONSEC_LOSS_THRESHOLD:
                approved_leverage = max(
                    self._cfg.MIN_LEVERAGE,
                    int(approved_leverage * self._cfg.DELEVER_MULTIPLIER)
                )
                is_deleveraged = True
                logger.warning(
                    "[RiskManager] De-leveraged: %d consec losses → leverage %d×",
                    self._consecutive_losses, approved_leverage
                )

            return RiskVerdict(
                can_trade            = True,
                position_size_usd    = round(position_size_usd, 2),
                position_size_pct    = round(position_size_pct, 2),
                approved_leverage    = approved_leverage,
                daily_pnl_pct        = self._daily_pnl_pct,
                consecutive_losses   = self._consecutive_losses,
                is_deleveraged       = is_deleveraged,
                portfolio_value_used = round(portfolio_value, 2),
            )

    def record_trade_result(self, pnl_pct: float) -> None:
        """Catat hasil trade. Panggil ini setelah setiap posisi ditutup."""
        with self._lock:
            self._check_day_rollover()

            portfolio_pnl        = pnl_pct * (self._cfg.RISK_PER_TRADE_PCT / 100.0)
            self._daily_pnl_pct += portfolio_pnl
            self._trades_today  += 1

            if pnl_pct < 0:
                self._consecutive_losses += 1
                self._consecutive_wins    = 0
                logger.debug(
                    "[RiskManager] Loss (%.2f%%). Streak: %dL",
                    pnl_pct, self._consecutive_losses
                )
                # [P1] Cooldown: pause entry after loss cluster
                if self._consecutive_losses == 5:
                    self._cooldown_candles = 6   # 24 jam
                    logger.warning(
                        "[RiskManager] 5 consecutive losses — COOLDOWN 6 candles (24h)"
                    )
                elif self._consecutive_losses == 3:
                    self._cooldown_candles = 2   # 8 jam
                    logger.warning(
                        "[RiskManager] 3 consecutive losses — COOLDOWN 2 candles (8h)"
                    )
            else:
                self._consecutive_wins += 1
                if self._consecutive_wins >= self._cfg.RECOVER_AFTER_WINS:
                    self._consecutive_losses = 0
                    self._cooldown_candles   = 0   # [P1] reset cooldown setelah recovery
                    logger.info(
                        "[RiskManager] Leverage recovered after %d wins.",
                        self._consecutive_wins
                    )
                logger.debug(
                    "[RiskManager] Win (%.2f%%). Wins: %d",
                    pnl_pct, self._consecutive_wins
                )

            if self._daily_pnl_pct <= self._cfg.MAX_DAILY_LOSS_PCT:
                self._is_suspended = True
                logger.warning(
                    "[RiskManager] ⚠️ Daily loss cap triggered! "
                    "Portfolio PnL today: %.2f%%. Suspending trading.",
                    self._daily_pnl_pct
                )

    def get_status(self) -> dict:
        """Return current risk state (untuk API/logging)."""
        with self._lock:
            self._check_day_rollover()
            return {
                "trading_day":         str(self._trading_day),
                "daily_pnl_pct":       round(self._daily_pnl_pct, 4),
                "is_suspended":        self._is_suspended,
                "consecutive_losses":  self._consecutive_losses,
                "consecutive_wins":    self._consecutive_wins,
                "trades_today":        self._trades_today,
                "max_daily_loss_pct":  self._cfg.MAX_DAILY_LOSS_PCT,
                "risk_per_trade_pct":  self._cfg.RISK_PER_TRADE_PCT,
                "max_leverage":        self._cfg.MAX_LEVERAGE,
                "leverage_safe_mode":  _LEVERAGE_SAFE_MODE,  # [FIX-3b]
                "cooldown_candles":    self._cooldown_candles,  # [P1]
            }

    def reset_for_testing(self) -> None:
        """Force reset — gunakan hanya di test."""
        with self._lock:
            self._reset_state()


# ── Singleton ──────────────────────────────────────────────────────────────────

_instance:  Optional[RiskManager] = None
_init_lock: threading.Lock        = threading.Lock()


def get_risk_manager(config: Optional[RiskConfig] = None) -> RiskManager:
    global _instance
    if _instance is None:
        with _init_lock:
            if _instance is None:
                _instance = RiskManager(config)
                logger.info("[RiskManager] Singleton initialized.")
    return _instance
