from pydantic import BaseModel


class SentimentInfo(BaseModel):
    score: float
    label: str
    note: str


class MetricsResponse(BaseModel):
    funding_rate: float
    open_interest: float
    order_book_imbalance: float
    global_mcap_change_pct: float
    sentiment: SentimentInfo
