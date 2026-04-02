# System Architecture

Technical system design and architecture documentation.

---

## Overview

BTC-QUANT is a live trading bot execution layer for Bitcoin on the Lighter mainnet with a comprehensive research framework based on Renaissance Technologies methods.

**Status**: Phase 3 Mainnet - First live order placed ✅

---

## System Components

```
┌─────────────────────────────────────────┐
│  User Interface / Monitoring Layer      │
│  (Telegram notifications, CLI tools)    │
└──────────────────┬──────────────────────┘
                   │
┌──────────────────▼──────────────────────┐
│  Data Pipeline & Strategy Layer         │
│  (Position Manager, Data Ingestion)     │
│  (FixedStrategy, HestonStrategy)        │
└──────────────────┬──────────────────────┘
                   │
┌──────────────────▼──────────────────────┐
│  Execution Layer (SDK Gateway)          │
│  (LighterExecutionGateway)              │
│  (Lighter Mainnet SDK)                  │
└──────────────────┬──────────────────────┘
                   │
┌──────────────────▼──────────────────────┐
│  External Services                      │
│  (Lighter Mainnet, ArXiv, Paper DB)    │
└─────────────────────────────────────────┘
```

---

## Key Design Patterns

### 1. Gateway Pattern (Execution)
- **BaseExchangeExecutionGateway**: Abstract interface
- **LighterExecutionGateway**: Concrete implementation for Lighter mainnet
- **Enables**: Easy swapping of exchanges, testing with mocks

### 2. Strategy Pattern (Trading)
- **FixedStrategy**: Fixed margin/leverage ($99, 5x)
- **HestonStrategy**: ATR-based SL/TP dynamic sizing
- **Enables**: Easy addition of new strategies

### 3. Repository Pattern (Data)
- **LiveTradeRepository**: Abstracts trade storage
- **PositionManager**: Manages open positions
- **Enables**: Easy switching between storage backends

---

## API Integration

### Lighter Mainnet Connection

**Endpoint**: `https://mainnet.zklighter.elliot.ai`

**Key Parameters**:
- Market: BTC Perpetual (ID=1)
- Min Base Amount: 0.00020 BTC (~$14)
- Min Quote Amount: $10 USDC
- Supported Size Decimals: 5 (scale by 1e5)
- Supported Price Decimals: 1 (scale by 10)

**Authentication**:
- API Key: `LIGHTER_MAINNET_API_KEY`
- API Secret: `LIGHTER_MAINNET_API_SECRET`
- Account Index: 718591 (derived from L1 address)

---

## Data Flow

### Order Placement Flow
```
Strategy Decision
    ↓
PositionManager.open_position()
    ↓
LighterExecutionGateway._submit_order()
    ↓
lighter.SignerClient.create_market_order()
    ↓
Lighter Mainnet API
    ↓
Exchange Confirmation
    ↓
LiveTradeRepository.save_trade()
    ↓
ExecutionNotifier.notify() (Telegram)
```

### Position Monitoring Flow
```
DataIngestion.fetch_positions()
    ↓
PositionManager.update_state()
    ↓
Calculate current P&L
    ↓
Evaluate exit signals (SL/TP)
    ↓
If exit triggered → close position
    ↓
Execute closing trade
    ↓
Update state & notify
```

---

## Directory Structure

```
backend/
├── app/
│   ├── adapters/
│   │   ├── gateways/
│   │   │   ├── base_exchange_execution_gateway.py
│   │   │   └── lighter_execution_gateway.py ← SDK integration
│   │   └── repositories/
│   │       └── live_trade_repository.py
│   │
│   ├── domain/
│   │   ├── models/
│   │   │   ├── trade.py
│   │   │   └── position.py
│   │   └── interfaces/
│   │       └── (abstract definitions)
│   │
│   ├── use_cases/
│   │   ├── data_ingestion_use_case.py
│   │   ├── position_manager.py
│   │   └── strategies/
│   │       ├── fixed_strategy.py
│   │       └── heston_strategy.py
│   │
│   ├── handlers/
│   │   ├── execution_notifier.py (Telegram)
│   │   └── emergency_stop_handler.py
│   │
│   └── main.py
│
├── scripts/
│   └── test_lighter_connection.py
│
├── tests/
│   └── (133 test files - all passing)
│
└── config/
    └── (environment configuration)
```

---

## Technology Stack

| Component | Technology |
|-----------|-----------|
| **Language** | Python 3.9+ |
| **Exchange SDK** | Lighter SDK |
| **Testing** | pytest |
| **API Server** | FastAPI (for MCP HTTP bridge) |
| **Task Scheduling** | APScheduler (background daemon) |
| **Notifications** | Telegram Bot API |
| **Paper Search** | arXiv API, FastAPI |

---

## Deployment Architecture

### Local Development
```
Development Machine
├── Backend service (Python)
├── Tests (pytest)
├── Paper search HTTP API
└── Claude MCP integration
```

### VPS/Production
```
VPS Server (Docker)
├── Docker Container: btc-quant-backend
├── Volume: Trade logs & data
├── Env: Injected via docker-compose
└── Network: Access to Lighter mainnet
```

### Environment Configuration
- `.env`: Local credentials (not committed)
- `.env.template`: Template for reference
- VPS `.env`: `/home/saeful/vps/projects/btc-quant-lighter/.env`

---

## Key Metrics & Performance

| Metric | Value |
|--------|-------|
| **Code Quality** | 133 tests - all passing ✅ |
| **API Response Time** | <500ms (typical) |
| **Order Execution** | Real SDK, live mainnet |
| **Notification Latency** | <5s (Telegram) |
| **System Uptime Target** | 99%+ |

---

## Safety & Risk Management

### Emergency Controls
- `LIGHTER_TRADING_ENABLED`: Toggle to disable all trades
- Emergency stop handler with manual kill switch
- Position limits: Min $10, Max $99 per trade
- Slippage protection: 5% buffer on SL/TP
- Rate limiting: Max 1 order per 5 seconds

### Order Validation
- Minimum position size checks
- Account balance verification
- Margin requirement validation
- Price sanity checks (not 10x usual)

### Monitoring
- Real-time position tracking
- Automated P&L calculation
- Telegram notifications on all trades
- Configurable alert thresholds

---

## Future Architecture Plans

### Planned Components
- Database persistence layer (SQLAlchemy)
- Advanced ML-based strategy models
- Multi-exchange support
- Advanced portfolio optimization
- Real-time risk analytics dashboard

### Scalability Considerations
- Async/await for concurrent operations
- Horizontal scaling via container orchestration
- Event-driven architecture for real-time updates
- Redis caching for market data

---

## Integration Points

### Lighter Mainnet SDK
- Account creation & key management
- Market order placement
- Position queries
- P&L calculations

### Paper Search Tools
- ArXiv API integration
- FastAPI HTTP bridge
- MCP server integration with Claude

### Notification System
- Telegram Bot API
- Custom alerting thresholds
- Trade execution notifications

---

## Testing Strategy

### Test Coverage
- **Unit Tests**: Business logic (80%+ coverage)
- **Integration Tests**: SDK interactions
- **E2E Tests**: Full trade workflow

### Test Execution
```bash
# Run all tests
pytest backend/tests/ -v

# Run specific test file
pytest backend/tests/test_lighter_execution_gateway.py -v

# Run with coverage
pytest backend/tests/ --cov=backend/app
```

---

## Documentation by Component

- **Execution Layer**: See `lighter_execution_gateway.py` code comments
- **Strategy Logic**: See `fixed_strategy.py`, `heston_strategy.py`
- **Data Pipeline**: See `data_ingestion_use_case.py`, `position_manager.py`
- **Research**: See `../research/CRYPTO_RELEVANCE_ANALYSIS_2026.md`

---

## Troubleshooting Architecture

### Connection Issues
→ See `../setup/SETUP_COMPLETE.md`

### Order Execution Issues
→ Check `LighterExecutionGateway` logs

### Data Pipeline Issues
→ Check `DataIngestion` error handling

### Notification Issues
→ Verify Telegram credentials in `.env`

---

## Performance Optimization Tips

1. **Reduce API Calls**: Cache position data where possible
2. **Async Operations**: Use async/await for I/O
3. **Connection Pooling**: Reuse SDK connections
4. **Rate Limiting**: Implement backoff strategies

---

## Version History

| Version | Date | Key Changes |
|---------|------|-----------|
| **v4.4** | Apr 2, 2026 | Live mainnet trading, MCP integration |
| **v4.3** | Mar 15, 2026 | First market order placed |
| **v4.2** | Mar 1, 2026 | FixedStrategy with 5x leverage |
| **v4.1** | Feb 15, 2026 | Core execution layer |

---

## Next Steps

1. Review key files above
2. Read implementation details in code
3. Review test coverage in `backend/tests/`
4. Follow deployment guide for production

---

**Status**: ✅ Architecture documented  
**Last Updated**: April 2, 2026  
**Maintainer**: Claude Code
