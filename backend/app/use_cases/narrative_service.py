"""
Narrative Service — Layer 5 of BTC-QUANT.

Integrates:
1. Decision Engine output (Layer 4)
2. Market Sentiment (Fear & Greed)
3. LLM Synthesis (Kimi/DeepSeek)

Flow:
Decision Output (L4) ──┐
Market Sentiment (FnG) ├─> Narrative Service (L5) ──> LLM ──> Rationale
"""

import logging
import threading
from typing import Any, Dict, Optional
from app.core.engines.layer5_sentiment import SentimentEngine
from app.use_cases.ai_agent import get_ai_agent_synthesis

logger = logging.getLogger(__name__)

# [FIX-6] LLM timeout: maksimum waktu tunggu sebelum fallback
# Jika LLM API lambat, pipeline tidak akan terjebak menunggu
_LLM_TIMEOUT_SECONDS = 5.0


class NarrativeService:
    """
    Layer 5: LLM Narrative Engine.

    CHANGELOG fix/critical-optimizations:
    [FIX-6] LLM sekarang dipanggil dengan timeout ketat (_LLM_TIMEOUT_SECONDS).
            Jika API tidak merespons dalam batas waktu, pipeline langsung
            mendapat FALLBACK tanpa menunggu. Ini mencegah satu LLM call
            yang lambat memblok seluruh sinyal trading.

            Untuk daily trading otomatis, latency pipeline lebih penting
            daripada kesempurnaan narasi. Verdict tetap ditentukan oleh
            Truth Enforcer berbasis skor kuantitatif (bukan LLM).
    """

    def __init__(self):
        self._sent_engine = SentimentEngine()
        # Cache hasil LLM terakhir — jika LLM timeout, pakai cache
        self._last_narrative: Dict[str, str] = {
            "verdict":  "NEUTRAL",
            "rationale": "- LLM narrative pending.",
            "fng_info": "Neutral",
        }
        self._cache_lock = threading.Lock()

    def _fetch_llm_with_timeout(
        self, llm_payload: dict, timeout: float
    ) -> Optional[Dict[str, str]]:
        """
        Panggil LLM di thread terpisah dengan timeout.
        Return None jika timeout atau error.
        """
        result_container: list = []

        def _worker():
            try:
                result_container.append(get_ai_agent_synthesis(llm_payload))
            except Exception as exc:
                logger.warning("[Narrative] LLM call failed: %s", exc)

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        t.join(timeout=timeout)

        if result_container:
            return result_container[0]
        logger.warning(
            "[Narrative] LLM timeout (%.1fs) — menggunakan cached narrative.", timeout
        )
        return None

    def get_narrative(self, decision_context: Dict[str, Any]) -> Dict[str, str]:
        """
        Generate narrative dari decision output Layer 1-4.

        [FIX-6] LLM dipanggil dengan timeout. Jika timeout:
            - Return cached narrative dari call sebelumnya
            - Pipeline tidak terblok
            - Verdict tetap dikendalikan Truth Enforcer di signal_service
        """
        # 1. Fetch FGI (cepat, tidak perlu timeout khusus)
        try:
            fng_value, fng_label = self._sent_engine.fetch_fear_and_greed()
        except Exception:
            fng_value, fng_label = 50, "Neutral"

        # 2. Enrich payload
        llm_payload = decision_context.copy()
        llm_payload["external_sentiment"] = {
            "fng_value": fng_value,
            "fng_label": fng_label,
        }

        # 3. [FIX-6] Call LLM dengan timeout ketat
        synthesis = self._fetch_llm_with_timeout(llm_payload, _LLM_TIMEOUT_SECONDS)

        if synthesis is not None:
            narrative = {
                "verdict":   synthesis.get("verdict",   "NEUTRAL"),
                "rationale": synthesis.get("rationale", "- No LLM rationale."),
                "fng_info":  fng_label,
            }
            # Update cache
            with self._cache_lock:
                self._last_narrative = narrative
            return narrative

        # 4. Fallback: pakai cache + tandai
        with self._cache_lock:
            cached = dict(self._last_narrative)
        cached["rationale"] = (
            "- [LLM Timeout] Menggunakan narasi cache dari sinyal sebelumnya.\n"
            + cached.get("rationale", "")
        )
        cached["fng_info"] = fng_label
        return cached

_narrative_svc = None

def get_narrative_service() -> NarrativeService:
    global _narrative_svc
    if _narrative_svc is None:
        _narrative_svc = NarrativeService()
    return _narrative_svc
