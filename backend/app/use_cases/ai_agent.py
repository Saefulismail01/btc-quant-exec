"""
LLM Agent — AI Agent synthesis layer.

Responsibility:
    - Receive a pre-computed market state dict (including confluence_score
      already calculated by the Python engine).
    - Return ONLY verdict + rationale in natural language.
    - Never compute or return a confluence_score — that is Python's authority.

Providers (priority via LLM_PROVIDER env):
    auto     → try Moonshot first, fall back to DeepSeek
    moonshot → Moonshot only
    deepseek → DeepSeek only
"""

import json
import os
from pathlib import Path

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

# ── Provider config ────────────────────────────────────────────────────────────

MOONSHOT_API_KEY  = os.getenv("MOONSHOT_API_KEY", "")
MOONSHOT_BASE_URL = os.getenv("MOONSHOT_BASE_URL", "https://api.moonshot.cn/v1")
MOONSHOT_MODEL    = os.getenv("MOONSHOT_MODEL", "moonshot-v1-8k")

DEEPSEEK_API_KEY  = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
DEEPSEEK_MODEL    = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "auto").strip().lower()

# ── Constants ──────────────────────────────────────────────────────────────────

_VALID_VERDICTS = {"STRONG BUY", "WEAK BUY", "NEUTRAL", "WEAK SELL", "STRONG SELL"}

_FALLBACK = {
    "verdict": "NEUTRAL",
    "rationale": (
        "- LLM unavailable — signal engine operating in rule-based mode.\n"
        "- Verdict and score are determined by quantitative layers only.\n"
        "- Wait for next cycle for full synthesis."
    ),
}

_SYSTEM_PROMPT = """You are a ruthless, highly logical Senior Quantitative Analyst specialized in Econophysics.

You will receive a market_state JSON. It includes a pre-computed `confluence_score` (0–100) and detailed quantitative metrics from the BCD (Bayesian Changepoint Detection) and Heston Volatility layers.

Your ONLY task: interpret the provided facts and return a directional verdict that is STRICTLY CONSISTENT with the score:
  - score >= 70  → STRONG BUY or STRONG SELL
  - score 40–69  → WEAK BUY or WEAK SELL
  - score < 40   → NEUTRAL (no other option)

Econophysics Guidelines for Rationale:
1. Regime (BCD): Interpret "persistence" as the physical stability of the current phase. High persistence in a trend confirms Lévy Flight momentum.
2. Volatility (Heston): Use "mean-reversion speed" to judge if current volatility spikes are transient or structural shifts. Mention long-run variance equilibrium.
3. Risk: Mention "Fat-Tails" if BCD/Heston detect anomalies that technical indicators (EMA/ATR) might miss.

Return ONLY a JSON object with exactly 2 keys:
  "verdict"   — one of: STRONG BUY, WEAK BUY, NEUTRAL, WEAK SELL, STRONG SELL
  "rationale" — concise string with exactly 3 short bullet points (use \\n- as separator)

No markdown, no backticks, no extra keys, no preamble."""


# ── Internal helpers ───────────────────────────────────────────────────────────

def _parse_response(raw: str) -> dict:
    """Extract and validate verdict + rationale from raw LLM text."""
    text = (raw or "").strip()

    # Strip markdown fences if present
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()

    # Extract first JSON object
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No valid JSON object found in LLM response")

    parsed = json.loads(text[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("LLM response is not a JSON object")

    verdict   = parsed.get("verdict", "NEUTRAL")
    rationale = parsed.get("rationale", _FALLBACK["rationale"])

    if verdict not in _VALID_VERDICTS:
        verdict = "NEUTRAL"
    if not isinstance(rationale, str) or not rationale.strip():
        rationale = _FALLBACK["rationale"]

    return {"verdict": verdict, "rationale": rationale}


def _call_provider(api_key: str, base_url: str, model: str, market_state: dict) -> dict:
    """Call a single LLM provider and return parsed result."""
    client   = OpenAI(api_key=api_key, base_url=base_url)
    response = client.chat.completions.create(
        model=model,
        temperature=0.1,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": "market_state:\n" + json.dumps(market_state, ensure_ascii=True)},
        ],
    )
    content = response.choices[0].message.content if response.choices else ""
    return _parse_response(content)


# ── Public API ─────────────────────────────────────────────────────────────────

def get_ai_agent_synthesis(market_state: dict) -> dict:
    """
    Request verdict + rationale from the configured LLM provider.

    Args:
        market_state: dict containing at minimum:
            - confluence_score (int)  ← computed by Python, passed as fact
            - trend_bias (str)
            - plus any layer metrics for context

    Returns:
        {"verdict": str, "rationale": str}
        Falls back to _FALLBACK on any error.
    """
    providers = []

    if LLM_PROVIDER == "moonshot":
        providers = [("moonshot", MOONSHOT_API_KEY, MOONSHOT_BASE_URL, MOONSHOT_MODEL)]
    elif LLM_PROVIDER == "deepseek":
        providers = [("deepseek", DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL)]
    else:
        # auto: try both in order
        providers = [
            ("moonshot", MOONSHOT_API_KEY, MOONSHOT_BASE_URL, MOONSHOT_MODEL),
            ("deepseek", DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL),
        ]

    for name, api_key, base_url, model in providers:
        if not api_key:
            continue
        try:
            return _call_provider(api_key, base_url, model, market_state)
        except Exception:
            continue  # Try next provider

    return _FALLBACK.copy()
