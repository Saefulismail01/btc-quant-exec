# Cloud Core - BTC Scalping System Core

Simplified, self-contained version of BTC-Quant execution system for cloud testing.

## Architecture

4-Layer Ensemble for Signal Generation:

```
┌─────────────────────────────────────────────────────────┐
│  LAYER 1: BCD (Bayesian Changepoint Detection)          │
│  ├─ HMM-based regime detection                            │
│  ├─ Detects: bull / bear / sideways                       │
│  └─ Weight: 30%                                          │
├─────────────────────────────────────────────────────────┤
│  LAYER 2: EMA (Trend Confirmation)                       │
│  ├─ Multi-timeframe EMA alignment                        │
│  ├─ EMA20/50/200 structure                               │
│  └─ Weight: 25%                                          │
├─────────────────────────────────────────────────────────┤
│  LAYER 3: AI (MLP or XGBoost)                            │
│  ├─ Next-candle direction predictor                       │
│  ├─ Features: RSI, MACD, ATR, Funding, OI, CVD          │
│  └─ Weight: 45% (HIGHEST - gatekeeper)                  │
├─────────────────────────────────────────────────────────┤
│  LAYER 4: Risk (ATR-based Position Sizing)               │
│  ├─ Volatility multiplier [0.0, 1.0]                   │
│  ├─ Higher vol = lower size                              │
│  └─ Applied to final score                              │
└─────────────────────────────────────────────────────────┘
                              │
                              ▼
                    DirectionalSpectrum
                              │
                    Final Score [-1.0, +1.0]
                              │
                    ┌─────────┴─────────┐
                    │                   │
              |score| >= 0.20     |score| < 0.20
                    │                   │
                 ACTIVE            SUSPENDED
                 (Entry OK)        (No Entry)
```

## Quick Start

### 1. Setup Environment

```bash
cd cloud_core
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create `.env` file:

```bash
# Optional: For live data fetch
BINANCE_API_KEY=your_api_key
BINANCE_SECRET=your_secret

# Optional: For Telegram notifications
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### 3. Test Signal Generation

```bash
# Test with MLP model
python runner.py signal --model mlp

# Test with XGBoost model
python runner.py signal --model xgboost
```

### 4. Run Backtest

```bash
# Walk-forward backtest
python runner.py backtest --model mlp
```

### 5. Compare Models

```bash
python runner.py compare
```

### 6. Paper Trading

```bash
python runner.py paper
```

## Usage Examples

### Basic Signal Generation

```python
from signal_service import SignalService

# Create service with MLP
service = SignalService(ai_model="mlp")

# Generate signal
signal = service.generate_signal(
    symbol="BTC/USDT",
    timeframe="4h"
)

print(f"Action: {signal.action}")
print(f"Conviction: {signal.conviction_pct}%")
print(f"Gate: {signal.trade_gate}")
```

### Paper Trading

```python
from execution.paper_executor import PaperExecutor
from signal_service import SignalService

# Create executor
executor = PaperExecutor(
    initial_balance=10000.0,
    save_path="./data/paper_state.json"
)

# Generate signal and trade
service = SignalService(ai_model="mlp")
signal = service.generate_signal()

if signal.trade_gate == "ACTIVE":
    position = executor.open_position(
        symbol="BTC/USDT",
        side=signal.action,
        price=signal.price,
        size_usdt=100.0,
        leverage=signal.leverage,
        sl_price=signal.price * 0.985,  # 1.5% SL
        tp_price=signal.price * 1.03,   # 3% TP
    )
```

### Custom Backtest

```python
from signal_service import SignalService
from data.fetcher import DataFetcher

# Fetch data
fetcher = DataFetcher()
df = fetcher.fetch_ohlcv("BTC/USDT", "4h", limit=1000)

# Run backtest
service = SignalService(ai_model="xgboost")
results = service.run_backtest(df, verbose=True)

# Analyze
active_signals = results[results["gate"] == "ACTIVE"]
print(f"ACTIVE signals: {len(active_signals)}")
```

## Switching AI Models

The system supports two Layer 3 models:

| Model | Pros | Cons | Best For |
|-------|------|------|----------|
| **MLP** | Fast inference, proven track record | Can overfit | Production trading |
| **XGBoost** | Better with imbalance, feature importance | Slower training | Research, comparison |

To switch models, simply change the `ai_model` parameter:

```python
# MLP (default)
service = SignalService(ai_model="mlp")

# XGBoost
service = SignalService(ai_model="xgboost")
```

## File Structure

```
cloud_core/
├── README.md                    # This file
├── requirements.txt             # Dependencies
├── config.py                    # Configuration
├── runner.py                    # CLI entry point
│
├── engines/                     # Core ML engines
│   ├── layer1_bcd.py           # BCD/HMM regime detection
│   ├── layer2_ema.py           # EMA trend confirmation
│   ├── layer3_mlp.py           # MLP predictor
│   ├── layer3_xgboost.py       # XGBoost predictor
│   ├── layer4_risk.py          # Risk/position sizing
│   └── spectrum.py             # 4-layer aggregation
│
├── data/                        # Data layer
│   └── fetcher.py              # Binance data fetcher
│
├── execution/                   # Execution layer
│   ├── paper_executor.py       # Paper trading
│   └── live_executor.py        # Live trading (binance)
│
├── signal_service.py           # Main signal orchestrator
└── tests/                      # Unit tests (optional)
```

## Key Concepts

### Directional Spectrum

The spectrum aggregates 4 layer votes into a final directional score:

```
raw_score = L1*0.30 + L2*0.25 + L3*0.45
final_score = raw_score * L4_multiplier
```

Score interpretation:
- `|score| >= 0.20`: ACTIVE (can enter trade)
- `|score| < 0.20`: SUSPENDED (wait)

### Why MLP is Gatekeeper

L3 (MLP) has highest weight (45%) because:
1. Shortest-term predictive power
2. Adapts to market changes via retraining
3. Directly predicts next candle direction

### Retraining

AI models retrain every 48 candles (~8 days on 4H timeframe) or when volatility spikes >2x.

## Cloud Deployment

### Upload to Cloud VM

```bash
# 1. Zip the folder
zip -r cloud_core.zip cloud_core/

# 2. Upload to cloud VM
scp cloud_core.zip user@your-cloud-vm:/home/user/

# 3. Unzip on VM
ssh user@your-cloud-vm "unzip /home/user/cloud_core.zip"

# 4. Setup on VM
cd /home/user/cloud_core
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 5. Run tests
python runner.py signal
```

### Docker (Optional)

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "runner.py", "signal"]
```

## Testing

### Unit Tests

```bash
pytest tests/ -v
```

### Manual Tests

```bash
# Signal generation
python runner.py signal --model mlp

# Paper trading simulation
python runner.py paper

# Full backtest
python runner.py backtest --model mlp

# Model comparison
python runner.py compare
```

## Performance

Based on walk-forward testing (2023-2026):

| Metric | MLP | XGBoost |
|--------|-----|---------|
| Total Return | +597.89% | TBD |
| Win Rate | 58.2% | TBD |
| Sharpe | 1.84 | TBD |
| Max DD | -18.3% | TBD |

## Contributing

To add new Layer 3 models:

1. Create `engines/layer3_yourmodel.py`
2. Implement `get_directional_vote(df) -> float` method
3. Add to `SignalService` model selection

## License

Same as parent project.
