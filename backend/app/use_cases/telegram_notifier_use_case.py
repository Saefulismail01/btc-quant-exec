import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv

from app.config import settings
from app.adapters.gateways.telegram_gateway import TelegramGateway

# Ensure .env is loaded (defensive)
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

class TelegramNotifierUseCase:
    """
    Orchestrates Telegram notifications for BTC-QUANT.
    Aligned with v4.4 Golden Model parameters and Premium Format.
    """
    
    def __init__(self):
        self.logger = logging.getLogger("telegram_notifier")

        # Get token/chat_id directly from env (not settings cache)
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

        self.logger.info(f"[TelegramNotifier] Token: {'✅ Loaded' if token else '❌ Not set'}, Chat ID: {'✅ Loaded' if chat_id else '❌ Not set'}")

        # Fallback to settings if env not available
        if not token:
            token = settings.telegram_bot_token
        if not chat_id:
            chat_id = settings.telegram_chat_id

        self.gateway = TelegramGateway(token, chat_id)
        
        # v4.4 Constants for reference in messages
        self.v44_leverage = 15
        self.v44_position_size_raw = 1000.0  # $1,000
        self.v44_notional = self.v44_position_size_raw * self.v44_leverage 
        self.v44_sl_pct = 1.333
        self.v44_tp_pct = 0.71
        self.v44_max_hold = "24h Auto\\-Exit \\(6 Candles\\)"
        self.v44_fee_rate = 0.0004 # 0.04%

    def _esc(self, text: Any) -> str:
        """Escapes characters for MarkdownV2."""
        s = str(text)
        # Characters to escape in MarkdownV2
        chars = r'_*[]()~`>#+-=|{}.!'
        for char in chars:
            s = s.replace(char, f"\\{char}")
        return s

    def format_v44_signal(self, signal_data: Dict[str, Any]) -> str:
        """
        Formats signal according to v4.4 Premium Design.
        """
        # Data Extraction
        ts_raw = signal_data.get("timestamp", datetime.utcnow().isoformat())
        try:
            ts_dt = datetime.strptime(ts_raw, "%Y-%m-%dT%H:%M:%SZ")
            ts_display = ts_dt.strftime("%Y\\-%m\\-%d %H:%M UTC")
        except:
            ts_display = self._esc(ts_raw)

        price_obj = signal_data.get("price", {})
        price_now = float(price_obj.get("now", 0))
        
        plan = signal_data.get("trade_plan", {})
        action = plan.get("action", "WAIT")
        action_emoji = "LONG 🟢" if action == "LONG" else "SHORT 🔴"
        verdict = signal_data.get("confluence", {}).get("verdict", "NEUTRAL")
        
        # v4.4 Logic calculations
        is_long = action == "LONG"
        sl_price = price_now * (1 - self.v44_sl_pct/100) if is_long else price_now * (1 + self.v44_sl_pct/100)
        tp_price = price_now * (1 + self.v44_tp_pct/100) if is_long else price_now * (1 - self.v44_tp_pct/100)
        
        # Risk Calc
        fee_usd = self.v44_notional * self.v44_fee_rate * 2
        gross_pnl_tp = self.v44_notional * (self.v44_tp_pct/100)
        gross_pnl_sl = self.v44_notional * (self.v44_sl_pct/100)
        
        net_tp = gross_pnl_tp - fee_usd
        net_sl = -(gross_pnl_sl + fee_usd)

        # Confluence Layers
        conf = signal_data.get("confluence", {})
        layers = conf.get("layers", {})
        l1 = layers.get("l1_hmm", {})
        l2 = layers.get("l2_tech", {})
        l3 = layers.get("l3_ai", {})
        l4 = layers.get("l4_risk", {})
        
        regime = signal_data.get("regime_bias", {}) or {}
        persistence = float(regime.get("persistence", 0.0))
        
        ai_conf = float(signal_data.get("confluence", {}).get("directional_bias", 0.0))
        ai_conf_pct = abs(ai_conf) * 100
        conviction = float(conf.get('conviction_pct', 0))

        # Construct Message
        msg = (
            f"🚀 *BTC\\-QUANT SIGNAL ALERT \\| v4\\.4 GOLDEN* 🚀\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 *ASSET*      : BTC/USDT \\(Perpetual\\)\n"
            f"🕒 *TIMEFRAME*  : 4H \\(Quadrant Execution\\)\n"
            f"🕯️ *CANDLE CL*  : {ts_display}\n\n"
            
            f"⚡ *PRIMARY ACTION*: {action_emoji} \\({self._esc(verdict)}\\)\n"
            f"──────────────────────────\n"
            f"💎 *LEVERAGE*   : {self.v44_leverage}x \\(Fixed\\)\n"
            f"🎯 *ENTRY ZONE* : {self._esc(f'{price_now-50:,.0f} - {price_now+50:,.0f}')}\n"
            f"🛑 *STOP LOSS*  : {self._esc(f'{sl_price:,.0f}')}\n"
            f"🏁 *TARGET TP*  : {self._esc(f'{tp_price:,.0f}')}\n"
            f"⏳ *SAFETY NET* : {self.v44_max_hold}\n\n"
            
            f"🧠 *EDGE ANALYSIS \\(6\\-LAYER STACK\\)*\n"
            f"──────────────────────────\n"
            f"🌐 *REGIME \\(BCD\\)* : {self._esc(l1.get('label', 'N/A'))} \\(Persistence: {self._esc(f'{persistence:.0%}')}\\)\n"
            f"🤖 *AI CONF*      : {self._esc(f'{ai_conf_pct:.1f}')}% \\(MLP \\+ BCD Cross Verified\\)\n"
            f"📈 *EMA STRUCT*   : {self._esc(l2.get('label', 'N/A'))}\n"
            f"🌀 *VOLATILITY*   : {self._esc(l4.get('label', 'N/A'))}\n"
            f"🎯 *CONVICTION*   : {self._esc(f'{conviction:.1f}')}% \\(Directional Spectrum\\)\n\n"
            
            f"📝 *RATIONALE*:\n"
            f"_{self._esc(conf.get('rationale', 'Market shows alignment for continuation.'))}_\n\n"
            
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🤖 *BTC\\-QUANT SYSTEM INTELLIGENCE v4\\.4*"
        )
        return msg

    async def notify_signal(self, signal_data: Dict[str, Any]) -> bool:
        """Sends signal notification for STRONG and WEAK signals."""
        verdict = signal_data.get("confluence", {}).get("verdict", "NEUTRAL").upper()
        gate    = signal_data.get("trade_plan", {}).get("status", "SUSPENDED").upper()

        # SUSPENDED → no-signal (paper trade juga skip di kondisi ini)
        # NEUTRAL verdict → no-signal
        if verdict == "NEUTRAL" or gate == "SUSPENDED":
            reason_log = f"verdict={verdict}" if verdict == "NEUTRAL" else f"gate={gate}"
            self.logger.info(f"Signal not actionable ({reason_log}). Sending monitoring update.")
            return await self.notify_no_signal(signal_data, reason="neutral_verdict")

        msg = self.format_v44_signal(signal_data)
        return await self.gateway.send_message(msg, parse_mode="MarkdownV2")

    async def notify_no_signal(self, signal_data: Dict[str, Any], reason: str = "fallback") -> bool:
        """
        Sends a 'no signal' update to Telegram explaining why there is no entry.
        Called for both fallback signals and NEUTRAL verdicts.

        reason: "fallback"        — pipeline returned is_fallback=True
                "neutral_verdict" — signal computed but conviction too low / gate SUSPENDED
        """
        ts_raw = signal_data.get("timestamp", datetime.utcnow().isoformat())
        try:
            ts_dt = datetime.strptime(ts_raw, "%Y-%m-%dT%H:%M:%SZ")
            ts_display = ts_dt.strftime("%Y\\-%m\\-%d %H:%M UTC")
        except Exception:
            ts_display = self._esc(ts_raw)

        price_obj  = signal_data.get("price", {})
        price_now  = float(price_obj.get("now", 0))
        ema20      = float(price_obj.get("ema20", 0))
        ema50      = float(price_obj.get("ema50", 0))

        plan       = signal_data.get("trade_plan", {})
        status     = plan.get("status", "SUSPENDED")
        raw_reason = plan.get("status_reason", "")

        conf       = signal_data.get("confluence", {})
        score      = int(conf.get("confluence_score", 0))
        conviction = float(conf.get("conviction_pct", 0))
        layers     = conf.get("layers", {})
        rationale  = conf.get("rationale", "")

        l1 = layers.get("l1_hmm",  {})
        l2 = layers.get("l2_tech", {})
        l3 = layers.get("l3_ai",   {})
        l4 = layers.get("l4_risk", {})

        def _check(layer: dict) -> str:
            return "✅" if layer.get("aligned") else "❌"

        heston = signal_data.get("heston_vol", {}) or {}
        vol_regime = heston.get("vol_regime", "N/A")

        regime_bias = signal_data.get("regime_bias", {}) or {}
        persistence = float(regime_bias.get("persistence", 0))

        # Gate status emoji
        gate_emoji = {"SUSPENDED": "🔴", "ADVISORY": "🟡"}.get(status, "⏸")

        if reason == "fallback":
            # Fallback: show the blocking reason clearly
            # Trim raw_reason for display (can be long)
            short_reason = raw_reason[:200] if raw_reason else "Pipeline returned fallback"
            msg = (
                f"⏸ *BTC\\-QUANT \\| NO SIGNAL \\(SUSPENDED\\)*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🕒 *Candle* : {ts_display}\n"
                f"📊 *BTC/USDT* : {self._esc(f'${price_now:,.0f}')}\n\n"
                f"🚫 *ALASAN TIDAK ENTRY*:\n"
                f"_{self._esc(short_reason)}_\n\n"
                f"📈 *Snapshot Market*\n"
                f"──────────────────────────\n"
                f"EMA20 : {self._esc(f'${ema20:,.0f}')}\n"
                f"EMA50 : {self._esc(f'${ema50:,.0f}')}\n"
                f"Heston Vol : {self._esc(vol_regime)}\n\n"
                f"⏳ _Menunggu candle 4H berikutnya\\.\\.\\._\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🤖 *BTC\\-QUANT SYSTEM v4\\.4*"
            )
        else:
            # Neutral verdict: show full layer breakdown
            trend = signal_data.get("trend", {})
            trend_bias  = trend.get("bias", "N/A")
            ema_struct  = trend.get("ema_structure", "N/A")

            # Determine gate status label
            gate_label = {
                "SUSPENDED": "SUSPENDED — Conviction terlalu rendah",
                "ADVISORY":  "ADVISORY — Ukuran dikurangi, tunggu konfirmasi",
            }.get(status, status)

            # First line of rationale only (keep it brief)
            first_rationale = rationale.strip().split("\n")[0] if rationale else "Kondisi pasar tidak mendukung entry."

            msg = (
                f"⏸ *BTC\\-QUANT \\| MONITORING \\(NO TRADE\\)*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🕒 *Candle* : {ts_display}\n"
                f"📊 *BTC/USDT* : {self._esc(f'${price_now:,.0f}')} \\| {self._esc(trend_bias)}\n\n"
                f"{gate_emoji} *STATUS* : {self._esc(gate_label)}\n"
                f"🎯 *Conviction* : {self._esc(f'{conviction:.1f}')}% \\| Score: {self._esc(str(score))}/100\n\n"
                f"🧠 *LAYER BREAKDOWN*\n"
                f"──────────────────────────\n"
                f"{_check(l1)} *L1 BCD*  : {self._esc(l1.get('label', 'N/A'))}\n"
                f"{_check(l2)} *L2 EMA*  : {self._esc(l2.get('label', 'N/A'))}\n"
                f"{_check(l3)} *L3 MLP*  : {self._esc(l3.get('label', 'N/A'))}\n"
                f"{_check(l4)} *L4 Vol*  : {self._esc(l4.get('label', 'N/A'))}\n\n"
                f"📉 *EMA*  : {self._esc(ema_struct)}\n"
                f"🌀 *Heston* : {self._esc(vol_regime)} \\| Regime persist: {self._esc(f'{persistence:.0%}')}\n\n"
                f"📝 _{self._esc(first_rationale)}_\n\n"
                f"⏳ _Menunggu candle 4H berikutnya\\.\\.\\._\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🤖 *BTC\\-QUANT SYSTEM v4\\.4*"
            )

        return await self.gateway.send_message(msg, parse_mode="MarkdownV2")

    async def notify_regime_shift(self, old_regime: str, new_regime: str, confidence: float):
        """Sends alert when BCD detects a regime change."""
        msg = (
            f"⚡ *MARKET REGIME SHIFT DETECTED* ⚡\n"
            f"──────────────────────────\n"
            f"*From* : {self._esc(old_regime)}\n"
            f"*To*   : {self._esc(new_regime)}\n"
            f"*BCD Confidence* : {self._esc(f'{confidence:.1%}')}\n"
            f"──────────────────────────\n"
            f"⚠️ *V4\\.4 model re\\-calibrating strategy\\.*"
        )
        return await self.gateway.send_message(msg, parse_mode="MarkdownV2")

# Singleton accessor
_notifier = None

def get_telegram_notifier() -> TelegramNotifierUseCase:
    global _notifier
    if _notifier is None:
        _notifier = TelegramNotifierUseCase()
    return _notifier
