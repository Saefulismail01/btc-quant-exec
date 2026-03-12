"""
╔══════════════════════════════════════════════════════════════╗
║  BTC-QUANT-BTC: LAYER 5 — SENTIMENT ANALYSIS                 ║
║  Market Psychology Filter · Crypto Fear & Greed Index       ║
║  Stack: httpx + pydantic                                     ║
║                                                              ║
║  PHASE 7 2026-02-27: Fear & Greed Integration              ║
╚══════════════════════════════════════════════════════════════╝
"""

import httpx
import logging

class SentimentEngine:
    """
    Fetches and processes market sentiment data.
    Primary source: Alternative.me Crypto Fear & Greed Index.
    """

    API_URL = "https://api.alternative.me/fng/"

    def __init__(self):
        self.last_value = 50
        self.last_label = "Neutral"

    def fetch_fear_and_greed(self) -> tuple[int, str]:
        """
        Fetches current Fear & Greed index.
        Returns (value, classification).
        """
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(self.API_URL)
                if response.status_code == 200:
                    data = response.json()
                    item = data['data'][0]
                    self.last_value = int(item['value'])
                    self.last_label = item['value_classification']
                    return self.last_value, self.last_label
        except Exception as e:
            logging.error(f"[Sentiment] Failed to fetch FnG: {e}")
        
        return self.last_value, self.last_label

    def get_sentiment_bias(self) -> float:
        """
        Maps sentiment to a bias score [-1.0, 1.0].
        Extreme Fear (0-25)   -> Often a contrarian BUY signal (+ bias)
        Extreme Greed (75-100) -> Often a contrarian SELL signal (- bias)
        
        Note: This is an ADVISORY bias, not a direct trade signal.
        """
        val, _ = self.fetch_fear_and_greed()
        
        # Contrarian mapping (Buy fear, Sell greed)
        # 0 (Fear) -> +1.0 bias
        # 100 (Greed) -> -1.0 bias
        bias = (50 - val) / 50.0
        return round(bias, 4)
