# Lighter Execution Layer - VPS Deployment Status

**Date:** 2026-03-14
**Status:** ✅ LIVE & OPERATIONAL

---

## Deployment Summary

### Infrastructure
- **VPS Location:** `/home/saeful/vps/projects/btc-quant-lighter`
- **Docker Image:** `btc-quant-lighter-btc-quant-api:latest` (1.33GB)
- **Port:** `8002:8000` (API exposed on port 8002)
- **Network:** `btc-quant-lighter_btc-quant-network` (bridge)

### Service Status
```
Container: btc-quant-api
Status: UP (5+ seconds)
Health: Starting (will be healthy after warmup)
Command: python backend/run.py
```

### API Endpoints
- **Health Check:** `http://localhost:8002/api/health`
  - Response: `{"status":"ok","version":"2.1","timestamp":"2026-03-14T05:14:20Z"}`

---

## Active Components

### Running Services (DO NOT STOP)
- `btc-quant-backend` (port 8000) - Original backend
- `btc-quant-frontend` (port 5173)
- `postgres:15-alpine` (btc-signal-db)
- `redis:7-alpine` (btc-signal-redis)
- `btc-signal-dashboard-backend` (port 8001)
- ✅ **NEW:** `btc-quant-api` (Lighter execution) (port 8002)

### Data Ingestion
- Data daemon initialized and running
- OHLCV pipeline active (500 rows ingested in first cycle)
- Latest BTC price: $71,062

---

## Configuration

### Environment Variables (Active)
```
LIGHTER_EXECUTION_MODE=testnet
LIGHTER_TRADING_ENABLED=false
EXECUTION_GATEWAY=lighter
LIGHTER_TESTNET_API_KEY=8a28d5711521993466e6d59073c555aef6300754fa419a3d5f21c3105631b094a38c4fdecf612f7c
LIGHTER_TESTNET_API_SECRET=d542c367ff83715223f27794e6d741750a9f85f964701100034211117eba8686de952c3e112a0126
LIGHTER_API_KEY_INDEX=3
```

### Safety Flags
- `LIGHTER_TRADING_ENABLED=false` ✅ (Trading disabled for testnet)
- Ready for manual enable after 48-hour validation

---

## Volume Persistence

Volumes mounted for:
- Database: `./backend/app/infrastructure/database:/app/backend/app/infrastructure/database`
- Nonce state: `./backend/app/infrastructure:/app/backend/app/infrastructure`

---

## Next Steps (Testing Phase)

### Phase 1: Verification (In Progress)
1. ✅ Container running and API responding
2. ✅ Data ingestion daemon active
3. ⏳ Monitor logs for 1-2 hours
4. ⏳ Verify Lighter API connection on first trade attempt

### Phase 2: Testnet Trading (48 Hours)
- Enable `LIGHTER_TRADING_ENABLED=true` when ready
- Monitor:
  - Trade execution success
  - SL/TP order placement
  - PnL calculations
  - Nonce synchronization

### Phase 3: Mainnet Migration
- After 48-hour testnet validation:
  - Set `LIGHTER_EXECUTION_MODE=mainnet`
  - Update mainnet credentials
  - Restart container
  - Monitor 24 hours before live trading

---

## Monitoring Commands

### View Logs
```bash
ssh vps-rumah "cd /home/saeful/vps/projects/btc-quant-lighter && docker compose logs -f btc-quant-api"
```

### Check Container Status
```bash
ssh vps-rumah "cd /home/saeful/vps/projects/btc-quant-lighter && docker compose ps"
```

### API Health Check
```bash
curl http://vps-ip:8002/api/health
```

### Docker Stats
```bash
ssh vps-rumah "docker stats btc-quant-api"
```

---

## Troubleshooting

### Port Conflict
If port 8002 is in use:
```bash
ssh vps-rumah "cd /home/saeful/vps/projects/btc-quant-lighter && sed -i 's/\"8002:8000\"/\"8003:8000\"/g' docker-compose.yml && docker compose restart"
```

### Restart Container
```bash
ssh vps-rumah "cd /home/saeful/vps/projects/btc-quant-lighter && docker compose restart btc-quant-api"
```

### View Database
```bash
ssh vps-rumah "cd /home/saeful/vps/projects/btc-quant-lighter && docker compose exec btc-quant-api sqlite3 backend/app/infrastructure/database/btc-quant.db"
```

---

## Important Notes

1. **Testnet Uses Mainnet Endpoint**: Lighter doesn't have separate testnet. Testnet accounts use mainnet endpoint with testnet credentials.

2. **Nonce Management**: Each transaction requires sequential nonce. Managed automatically by `LighterNonceManager`.

3. **Market Metadata**: Refreshed every 24 hours or on demand.

4. **Safety First**: `LIGHTER_TRADING_ENABLED=false` by default. Must explicitly enable for trading.

5. **Database Persistence**: DuckDB database persists across container restarts via volume mount.

---

**Last Updated:** 2026-03-14 12:14 UTC
**Deployment URL:** https://github.com/Saefulismail01/btc-quant-exec
**Repository:** git@github.com:Saefulismail01/btc-quant-exec.git
