# Docker Setup Guide for BTC-QUANT Lighter Execution Layer

This guide explains how to deploy BTC-QUANT with Lighter integration on a Linux VPS using Docker.

---

## Prerequisites

- **Linux VPS** (Ubuntu 20.04+ recommended)
- **Docker** installed (v20.10+)
- **Docker Compose** installed (v1.29+)
- **Git** installed
- **Lighter API credentials** (from your Lighter dashboard)

---

## Step 1: Prepare VPS

```bash
# Update system
sudo apt-get update && sudo apt-get upgrade -y

# Install Docker
sudo apt-get install -y docker.io docker-compose git curl

# Add your user to docker group (optional, for non-sudo access)
sudo usermod -aG docker $USER
newgrp docker

# Verify installation
docker --version
docker-compose --version
```

---

## Step 2: Clone Repository

```bash
# Clone the project
git clone <your-repo-url> btc-quant
cd btc-quant

# Or if already cloned, pull latest
cd btc-quant
git pull origin main
```

---

## Step 3: Configure Environment

```bash
# Copy and edit .env
cp .env .env.docker

# Edit with your Lighter credentials
nano .env.docker
```

**Required variables in `.env.docker`:**
```env
# Lighter Testnet Credentials
LIGHTER_TESTNET_API_KEY=your_api_key_from_lighter
LIGHTER_TESTNET_API_SECRET=your_api_secret_from_lighter
LIGHTER_API_KEY_INDEX=3

# Telegram (optional)
EXECUTION_TELEGRAM_BOT_TOKEN=your_bot_token
EXECUTION_TELEGRAM_CHAT_ID=your_chat_id

# Mode
LIGHTER_EXECUTION_MODE=testnet
LIGHTER_TRADING_ENABLED=false
```

---

## Step 4: Build and Run

### Option A: Run API Server

```bash
# Build image
docker-compose build

# Start container
docker-compose up -d

# Check logs
docker-compose logs -f btc-quant-api

# Verify API is running
curl http://localhost:8000/api/health
```

### Option B: Run Lighter Executor Daemon

Edit `docker-compose.yml` to uncomment the `btc-quant-lighter-executor` service, then:

```bash
docker-compose up -d btc-quant-lighter-executor

# Check logs
docker-compose logs -f btc-quant-lighter-executor
```

---

## Step 5: Verify Setup

### Check API Health
```bash
curl http://localhost:8000/api/health
# Expected: {"status": "ok", ...}
```

### Check Logs for Connection
```bash
docker-compose logs btc-quant-api | grep LIGHTER

# Expected to see:
# [LIGHTER] Initialized in testnet mode
# [LIGHTER] Account Balance: $XXXX.XX USDC
# [LIGHTER] Nonce resynced from server
```

### Verify Database
```bash
# Check database persistence
ls -lah backend/app/infrastructure/database/

# Should show btc-quant.db file
```

---

## Step 6: Monitor and Maintain

### Daily Monitoring

```bash
# Check container status
docker-compose ps

# View recent logs
docker-compose logs --tail=100 btc-quant-api

# Check resource usage
docker stats btc-quant-api
```

### Update Credentials

If you need to update API keys:

```bash
# Edit environment file
nano .env.docker

# Restart container
docker-compose restart btc-quant-api

# Verify
docker-compose logs -f btc-quant-api
```

### Restart Services

```bash
# Restart single service
docker-compose restart btc-quant-api

# Restart all services
docker-compose restart

# Full restart (stop + start)
docker-compose down
docker-compose up -d
```

### View Database

```bash
# Access database directly
docker-compose exec btc-quant-api sqlite3 backend/app/infrastructure/database/btc-quant.db

# Example queries:
# SELECT COUNT(*) FROM live_trades;
# SELECT * FROM live_trades ORDER BY created_at DESC LIMIT 5;
```

---

## Step 7: Production Setup (After Testnet Validation)

Once you've validated 48+ hours on testnet:

```bash
# Create backup
cp -r backend/app/infrastructure/database backend/app/infrastructure/database.testnet.backup

# Update .env.docker for mainnet
LIGHTER_EXECUTION_MODE=mainnet
LIGHTER_TRADING_ENABLED=true  # Only after 48h testnet!
LIGHTER_MAINNET_API_KEY=your_mainnet_key
LIGHTER_MAINNET_API_SECRET=your_mainnet_secret

# Restart
docker-compose restart btc-quant-api
```

---

## Troubleshooting

### Container won't start

```bash
# Check detailed logs
docker-compose logs btc-quant-api

# Common issues:
# - Port 8000 already in use: change to "8001:8000" in docker-compose.yml
# - Out of disk space: run `docker system prune -a`
# - Permission denied: run with `sudo docker-compose`
```

### Connection errors to Lighter

```bash
# Verify network connectivity from container
docker-compose exec btc-quant-api curl -v https://mainnet.zklighter.elliot.ai/api/v1/account

# Check if credentials are correct
docker-compose logs btc-quant-api | grep "invalid auth"
```

### Database locked

```bash
# DuckDB may be locked if multiple processes access it
# Restart container
docker-compose restart btc-quant-api

# Or remove lock file
docker-compose exec btc-quant-api rm backend/app/infrastructure/database/.duckdb.lock
docker-compose restart btc-quant-api
```

### High memory usage

```bash
# Check memory usage
docker stats btc-quant-api

# If over 500MB, restart to clear caches
docker-compose restart btc-quant-api

# Limit memory in docker-compose.yml:
# mem_limit: '512m'
```

---

## Useful Commands

```bash
# View all logs with timestamps
docker-compose logs --timestamps btc-quant-api

# Follow logs in real-time
docker-compose logs -f btc-quant-api

# Export logs to file
docker-compose logs btc-quant-api > logs.txt

# SSH into container
docker-compose exec btc-quant-api bash

# Run one-off command
docker-compose exec btc-quant-api python -c "import app; print(app.__version__)"

# Rebuild without cache (after code changes)
docker-compose build --no-cache

# Stop all containers
docker-compose down

# Stop and remove volumes (wipe everything)
docker-compose down -v
```

---

## Performance Tips

1. **Use SSD storage** — Better database performance
2. **Place VPS near server** — Lower latency to Lighter API
3. **Set appropriate resources** — 2 CPU cores, 2GB RAM minimum
4. **Enable cgroup memory limits** — Prevent runaway processes
5. **Monitor nonce state** — Ensure `/app/backend/app/infrastructure/lighter_nonce_state.json` is persistent

---

## Deploying Paper Pullback Executor (Forward Test)

Service ini menjalankan simulasi pullback entry 0.30% + daily freeze rule secara paralel dengan sistem live — menggunakan uang virtual. Tidak menyentuh apapun di production.

### Step 1: Pull kode terbaru

```bash
cd btc-quant
git pull origin main
```

### Step 2: Buat folder output di host VPS

```bash
mkdir -p data/paper_pullback
mkdir -p logs
```

### Step 3: Build image (hanya paper-pullback)

```bash
docker-compose build paper-pullback
```

### Step 4: Jalankan service (tanpa restart yang lain)

```bash
docker-compose up -d paper-pullback
```

### Step 5: Verifikasi berjalan

```bash
# Cek status container
docker-compose ps paper-pullback

# Lihat log real-time
docker-compose logs -f btc-quant-paper-pullback

# Output yang diharapkan di log:
# ====================================================================
#   PULLBACK PAPER EXECUTOR — v1.0
#   Pullback : 0.30%  |  Max wait: 2x4H = 8h
#   Notional : $15,000  |  Fee: $12.00  |  SL: 1.333%  |  TP: 0.710%
# ====================================================================
```

### Step 6: Monitor hasil trades

```bash
# Lihat semua trade
cat data/paper_pullback/paper_pullback_trades.csv

# Lihat state terkini (PnL, WR, freeze status)
cat data/paper_pullback/paper_pullback_state.json

# Lihat log hari ini
tail -100 data/paper_pullback/paper_pullback.log
```

### Config opsional via `.env`

Tambahkan baris berikut ke `.env` jika ingin override default:

```env
PB_PCT=0.003        # pullback 0.30% (default)
PB_WAIT=2           # max wait 2 candle 4H (default)
PB_CYCLE=60         # polling setiap 60 detik (default)
PB_NOTIONAL=15000   # notional $15,000 (default)
```

### Stop service

```bash
docker-compose stop paper-pullback
# atau permanen:
docker-compose rm -sf paper-pullback
```

### Catatan penting

- Output tersimpan di `./data/paper_pullback/` di host VPS — **persistent** meski container di-restart
- State JSON otomatis di-resume saat container restart (tidak kehilangan progress)
- Service ini **tidak** mempengaruhi live trading, paper_executor baseline, maupun DuckDB production
- Jalankan minimum **30 hari** untuk hasil yang valid secara statistik

---

## Next Steps

1. ✅ Setup Docker on VPS
2. ✅ Deploy and test API connectivity
3. ✅ Run 24 hours on testnet
4. ✅ Verify trades are executing correctly
5. ✅ Run 48 hours total before switching to mainnet
6. ✅ Deploy mainnet with `LIGHTER_TRADING_ENABLED=true`
7. ⏳ Deploy `paper-pullback` service untuk forward test Proposal D (30 hari)

---

## Support

For issues:
- Check logs: `docker-compose logs btc-quant-api`
- Check Lighter status: https://status.lighter.xyz
- Review environment variables: `docker-compose config`

---

**Last Updated:** March 2026
**Docker Version:** Tested with 25.0+
**Python Version:** 3.12
