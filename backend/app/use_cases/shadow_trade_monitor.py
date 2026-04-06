"""
ShadowTradeMonitor — Counterfactual trade tracking.

After a manual close, continues monitoring price to determine
what WOULD have happened if the bot's TP/SL were left in place.

This provides clean data to evaluate bot-only EV for scale-up decisions.
"""

import logging
import time
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ShadowResult:
    """Result of a shadow trade evaluation."""
    trade_id: str
    shadow_exit_type: str  # WOULD_BE_TP | WOULD_BE_SL | WOULD_BE_TIMEOUT
    shadow_exit_price: float
    shadow_pnl_usdt: float
    shadow_pnl_pct: float
    actual_pnl_usdt: float
    difference_usdt: float  # shadow - actual (positive = bot would've done better)


class ShadowTradeMonitor:
    """
    Monitors price after manual close to track counterfactual outcomes.

    Usage:
        monitor = ShadowTradeMonitor(repo)

        # When manual close detected:
        monitor.start_shadow(trade)

        # Every cycle (called from ingestion loop):
        results = monitor.check_shadows(current_price)
    """

    # Max time to monitor a shadow trade before calling it TIMEOUT
    SHADOW_TIMEOUT_MS = 24 * 3600 * 1000  # 24 hours

    def __init__(self, repo):
        """
        Args:
            repo: LiveTradeRepository instance (for DB access)
        """
        self.repo = repo
        self._ensure_table()

    def _ensure_table(self):
        """Create shadow_trades table if not exists."""
        import duckdb
        try:
            with duckdb.connect(self.repo.db_path) as con:
                con.execute("""
                    CREATE TABLE IF NOT EXISTS shadow_trades (
                        trade_id            VARCHAR PRIMARY KEY,
                        side                VARCHAR NOT NULL,
                        entry_price         DOUBLE NOT NULL,
                        sl_price            DOUBLE NOT NULL,
                        tp_price            DOUBLE NOT NULL,
                        size_usdt           DOUBLE NOT NULL,
                        leverage            INTEGER NOT NULL,
                        actual_exit_price   DOUBLE NOT NULL,
                        actual_pnl_usdt     DOUBLE NOT NULL,
                        shadow_started_ts   BIGINT NOT NULL,
                        shadow_status       VARCHAR NOT NULL,
                        shadow_exit_type    VARCHAR,
                        shadow_exit_price   DOUBLE,
                        shadow_exit_ts      BIGINT,
                        shadow_pnl_usdt     DOUBLE,
                        shadow_pnl_pct      DOUBLE
                    )
                """)
            logger.info("[ShadowMonitor] Table initialized")
        except Exception as e:
            logger.warning(f"[ShadowMonitor] Table init skipped: {e}")

    def start_shadow(self, trade) -> bool:
        """
        Start shadow monitoring for a manually closed trade.

        Args:
            trade: LiveTradeRecord with original TP/SL levels

        Returns:
            True if shadow started successfully
        """
        import duckdb
        try:
            with duckdb.connect(self.repo.db_path) as con:
                con.execute("""
                    INSERT INTO shadow_trades (
                        trade_id, side, entry_price, sl_price, tp_price,
                        size_usdt, leverage,
                        actual_exit_price, actual_pnl_usdt,
                        shadow_started_ts, shadow_status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    trade.id, trade.side, trade.entry_price,
                    trade.sl_price, trade.tp_price,
                    trade.size_usdt, trade.leverage,
                    trade.exit_price or trade.entry_price,
                    trade.pnl_usdt or 0.0,
                    int(time.time() * 1000),
                    "MONITORING",
                ])
            logger.info(
                f"[ShadowMonitor] Started shadow for {trade.id} | "
                f"{trade.side} @ ${trade.entry_price:,.2f} | "
                f"SL=${trade.sl_price:,.2f} TP=${trade.tp_price:,.2f}"
            )
            return True
        except Exception as e:
            logger.error(f"[ShadowMonitor] Failed to start shadow: {e}")
            return False

    def check_shadows(self, current_price: float) -> list[ShadowResult]:
        """
        Check all active shadow trades against current price.

        Args:
            current_price: Current BTC price

        Returns:
            List of ShadowResult for any shadows that completed this cycle
        """
        import duckdb
        results = []

        try:
            with duckdb.connect(self.repo.db_path, read_only=True) as con:
                rows = con.execute("""
                    SELECT trade_id, side, entry_price, sl_price, tp_price,
                           size_usdt, leverage, actual_exit_price, actual_pnl_usdt,
                           shadow_started_ts
                    FROM shadow_trades
                    WHERE shadow_status = 'MONITORING'
                """).fetchall()
        except Exception as e:
            logger.error(f"[ShadowMonitor] Failed to fetch shadows: {e}")
            return results

        now_ms = int(time.time() * 1000)

        for row in rows:
            trade_id, side, entry_price, sl_price, tp_price, \
                size_usdt, leverage, actual_exit_price, actual_pnl_usdt, \
                shadow_started_ts = row

            is_long = side == "LONG"

            # Check TP hit
            tp_hit = (current_price >= tp_price) if is_long else (current_price <= tp_price)
            # Check SL hit
            sl_hit = (current_price <= sl_price) if is_long else (current_price >= sl_price)
            # Check timeout
            timed_out = (now_ms - shadow_started_ts) > self.SHADOW_TIMEOUT_MS

            if tp_hit:
                exit_type = "WOULD_BE_TP"
                exit_price = tp_price
            elif sl_hit:
                exit_type = "WOULD_BE_SL"
                exit_price = sl_price
            elif timed_out:
                exit_type = "WOULD_BE_TIMEOUT"
                exit_price = current_price
            else:
                continue  # Still monitoring

            # Calculate shadow PnL
            if is_long:
                shadow_pnl_usdt = (exit_price - entry_price) / entry_price * size_usdt * leverage
            else:
                shadow_pnl_usdt = (entry_price - exit_price) / entry_price * size_usdt * leverage

            shadow_pnl_pct = (shadow_pnl_usdt / size_usdt * 100) if size_usdt > 0 else 0
            difference = shadow_pnl_usdt - actual_pnl_usdt

            # Update DB
            self._complete_shadow(
                trade_id, exit_type, exit_price, shadow_pnl_usdt, shadow_pnl_pct
            )

            result = ShadowResult(
                trade_id=trade_id,
                shadow_exit_type=exit_type,
                shadow_exit_price=exit_price,
                shadow_pnl_usdt=shadow_pnl_usdt,
                shadow_pnl_pct=shadow_pnl_pct,
                actual_pnl_usdt=actual_pnl_usdt,
                difference_usdt=difference,
            )
            results.append(result)

            emoji = "✅" if shadow_pnl_usdt > actual_pnl_usdt else "❌"
            logger.info(
                f"[ShadowMonitor] {emoji} Shadow completed: {trade_id} | "
                f"{exit_type} @ ${exit_price:,.2f} | "
                f"Shadow PnL: ${shadow_pnl_usdt:+.2f} vs Actual: ${actual_pnl_usdt:+.2f} | "
                f"Diff: ${difference:+.2f}"
            )

        return results

    def _complete_shadow(
        self, trade_id: str, exit_type: str, exit_price: float,
        pnl_usdt: float, pnl_pct: float
    ):
        """Mark a shadow trade as completed."""
        import duckdb
        try:
            with duckdb.connect(self.repo.db_path) as con:
                con.execute("""
                    UPDATE shadow_trades
                    SET shadow_status = 'COMPLETED',
                        shadow_exit_type = ?,
                        shadow_exit_price = ?,
                        shadow_exit_ts = ?,
                        shadow_pnl_usdt = ?,
                        shadow_pnl_pct = ?
                    WHERE trade_id = ?
                """, [exit_type, exit_price, int(time.time() * 1000),
                      pnl_usdt, pnl_pct, trade_id])
        except Exception as e:
            logger.error(f"[ShadowMonitor] Failed to complete shadow {trade_id}: {e}")

    def get_shadow_summary(self) -> dict:
        """
        Get summary stats of all completed shadow trades.

        Returns:
            Dict with comparison stats: bot vs manual
        """
        import duckdb
        try:
            with duckdb.connect(self.repo.db_path, read_only=True) as con:
                rows = con.execute("""
                    SELECT shadow_exit_type, shadow_pnl_usdt, actual_pnl_usdt
                    FROM shadow_trades
                    WHERE shadow_status = 'COMPLETED'
                """).fetchall()
        except Exception as e:
            logger.error(f"[ShadowMonitor] Failed to get summary: {e}")
            return {}

        if not rows:
            return {"total_trades": 0, "message": "No completed shadow trades yet"}

        total = len(rows)
        bot_wins = sum(1 for r in rows if r[1] > r[2])
        bot_total_pnl = sum(r[1] for r in rows)
        actual_total_pnl = sum(r[2] for r in rows)
        tp_count = sum(1 for r in rows if r[0] == "WOULD_BE_TP")
        sl_count = sum(1 for r in rows if r[0] == "WOULD_BE_SL")
        timeout_count = sum(1 for r in rows if r[0] == "WOULD_BE_TIMEOUT")
        bot_wr = tp_count / total * 100 if total > 0 else 0

        return {
            "total_trades": total,
            "bot_wins": bot_wins,
            "human_wins": total - bot_wins,
            "bot_total_pnl": round(bot_total_pnl, 2),
            "human_total_pnl": round(actual_total_pnl, 2),
            "bot_edge": round(bot_total_pnl - actual_total_pnl, 2),
            "bot_wr": round(bot_wr, 1),
            "bot_tp_count": tp_count,
            "bot_sl_count": sl_count,
            "bot_timeout_count": timeout_count,
        }
