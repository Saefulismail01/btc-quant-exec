# Alternatif 4: Docker-Based Isolation

## 🎯 Konsep

Production dan Research berjalan di **container terpisah**:
- `prod` container: Minimal, hanya code validated
- `research` container: Full ML stack, Jupyter, heavy deps

```
┌─────────────────────────────────────────────────────────────┐
│                     DOCKER HOST                             │
│                                                             │
│  ┌──────────────────┐      ┌──────────────────────────┐      │
│  │   PROD CONTAINER │      │   RESEARCH CONTAINER     │      │
│  │   (Minimal)        │      │   (Full ML Stack)        │      │
│  │                    │      │                          │      │
│  │  • Python 3.11     │      │  • Python 3.11           │      │
│  │  • Core engine     │      │  • Core engine           │      │
│  │  • Execution       │      │  • Research models       │      │
│  │  • Risk Mgmt       │      │  • Jupyter Lab           │      │
│  │  • Telegram        │      │  • TensorFlow/PyTorch    │      │
│  │  • ~50MB deps      │      │  • ~2GB deps             │      │
│  └──────────────────┘      └──────────────────────────┘      │
│           │                          │                      │
│           └──────────┬───────────────┘                      │
│                      │                                      │
│              ┌───────▼────────┐                             │
│              │  SHARED DATA   │                             │
│              │  • Market data │                             │
│              │  • Logs        │                             │
│              │  • Config      │                             │
│              └────────────────┘                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 Struktur Direktori

```
btc-scalping/
│
├── 📁 prod/                        ← 🚫 PRODUCTION CODE
│   ├── Dockerfile                  # Minimal image
│   ├── requirements.txt            # Minimal deps
│   ├── src/
│   │   ├── engine/
│   │   │   ├── __init__.py
│   │   │   ├── layer1_regime.py
│   │   │   ├── layer2_trend.py
│   │   │   ├── layer3_ml/
│   │   │   │   ├── __init__.py     # Only exports validated models
│   │   │   │   └── logistic.py     # 🏆 Production model
│   │   │   ├── layer4_risk.py
│   │   │   └── spectrum.py
│   │   ├── execution/
│   │   │   ├── __init__.py
│   │   │   ├── binance_gateway.py
│   │   │   ├── lighter_gateway.py
│   │   │   └── order_manager.py
│   │   ├── risk/
│   │   │   ├── position_sizing.py
│   │   │   └── sl_calculator.py
│   │   ├── notify/
│   │   │   ├── telegram_bot.py
│   │   │   └── templates/
│   │   └── main.py                 # Entry point
│   └── tests/
│       └── test_integration.py
│
├── 📁 research/                    ← 🔬 RESEARCH WORKSPACE
│   ├── Dockerfile                  # Full ML image
│   ├── requirements.txt            # Full deps (tensorflow, etc)
│   ├── docker-compose.yml          # Services: Jupyter, MLflow
│   ├── notebooks/
│   │   ├── 01_model_comparison.ipynb
│   │   ├── 02_feature_analysis.ipynb
│   │   └── 03_backtest.ipynb
│   ├── src/
│   │   ├── models/
│   │   │   ├── experiments/        # New model trials
│   │   │   │   ├── lstm_v1.py
│   │   │   │   ├── transformer.py
│   │   │   │   └── attention.py
│   │   │   ├── candidates/         # Validated (ready for prod)
│   │   │   │   └── lightgbm_v2.py
│   │   │   └── evaluator.py
│   │   ├── features/
│   │   │   ├── experiments/
│   │   │   └── selector.py
│   │   ├── backtest/
│   │   │   ├── engine.py
│   │   │   └── strategies/
│   │   └── data/
│   │       └── csv_loader.py
│   └── results/
│       ├── models/                   # Saved model files
│       └── reports/                  # Generated reports
│
├── 📁 shared/                      ← ⚠️ SHARED (mount ke dua container)
│   ├── config/
│   │   ├── settings.yaml
│   │   └── constants.py
│   ├── types/
│   │   └── dataclasses.py
│   └── utils/
│       ├── time.py
│       └── math.py
│
├── 📁 data/                        ← 💾 VOLUME SHARED
│   ├── market/                     # OHLCV cache
│   ├── db/                         # SQLite/Postgres
│   └── logs/                       # Application logs
│
├── 📁 ops/                         ← 🔧 OPERATIONS
│   ├── monitoring/
│   │   ├── prometheus.yml
│   │   └── grafana-dashboards/
│   ├── scripts/
│   │   ├── backup.sh
│   │   └── health_check.py
│   └── deployment/
│       └── docker-compose.prod.yml
│
├── 📁 docs/                        ← 📚 DOCUMENTATION
│   ├── PROD_SETUP.md
│   ├── RESEARCH_WORKFLOW.md
│   └── API.md
│
├── docker-compose.yml              # Main orchestration
├── Makefile                        # Common commands
└── README.md                       # Quick start
```

---

## 🐳 Docker Configuration

### 1. Production Container (`prod/Dockerfile`)

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Minimal dependencies only
COPY prod/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy production code only
COPY shared/ ./shared/
COPY prod/src/ ./src/

# Non-root user for security
RUN useradd -m -u 1000 produser
USER produser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import sys; sys.exit(0)"

CMD ["python", "-m", "src.main"]
```

```txt
# prod/requirements.txt (Minimal ~50MB)
pandas==2.1.4
numpy==1.26.3
pandas-ta==0.3.14b0
scikit-learn==1.3.2
lightweight-charts==2.0
python-telegram-bot==20.7
ccxt==4.2.18
pydantic==2.5.3
python-dotenv==1.0.0
```

### 2. Research Container (`research/Dockerfile`)

```dockerfile
FROM python:3.11

WORKDIR /workspace

# System deps for ML
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Full ML dependencies
COPY research/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all code (prod + research)
COPY shared/ ./shared/
COPY prod/src/ ./prod_src/        # Prod code as reference
COPY research/src/ ./research_src/
COPY research/notebooks/ ./notebooks/

# Jupyter extensions
RUN jupyter labextension install @jupyter-widgets/jupyterlab-manager

EXPOSE 8888

CMD ["jupyter", "lab", "--ip=0.0.0.0", "--allow-root", "--no-browser"]
```

```txt
# research/requirements.txt (Full ~2GB)
# Include all prod deps
-r ../prod/requirements.txt

# Additional ML deps
tensorflow==2.15.0
torch==2.1.2
xgboost==2.0.3
lightgbm==4.1.0
catboost==1.2.2
optuna==3.5.0
mlflow==2.9.2
jupyterlab==4.0.10
matplotlib==3.8.2
seaborn==0.13.1
plotly==5.18.0
shap==0.44.0
```

### 3. Docker Compose (Root `docker-compose.yml`)

```yaml
version: '3.8'

services:
  # Production Service
  prod:
    build:
      context: .
      dockerfile: prod/Dockerfile
    container_name: btc-prod
    restart: unless-stopped
    environment:
      - ENV=production
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - BINANCE_API_KEY=${BINANCE_API_KEY}
      - BINANCE_SECRET=${BINANCE_SECRET}
    volumes:
      - ./data:/data
      - ./shared:/shared:ro
    networks:
      - btc-network
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  # Research Service (Jupyter)
  research:
    build:
      context: .
      dockerfile: research/Dockerfile
    container_name: btc-research
    ports:
      - "8888:8888"
    environment:
      - ENV=research
      - JUPYTER_TOKEN=${JUPYTER_TOKEN}
    volumes:
      - ./data:/data
      - ./shared:/shared
      - ./research/notebooks:/workspace/notebooks
      - ./research/results:/workspace/results
    networks:
      - btc-network
    profiles:
      - research  # Only start with: docker-compose --profile research up

  # Monitoring (Prometheus + Grafana)
  monitoring:
    image: prom/prometheus:latest
    container_name: btc-monitoring
    volumes:
      - ./ops/monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"
    networks:
      - btc-network
    profiles:
      - monitoring

networks:
  btc-network:
    driver: bridge
```

---

## 🚀 Workflow Penggunaan

### Production Mode
```bash
# Start production only
docker-compose up prod

# View logs
docker-compose logs -f prod

# Restart after config change
docker-compose restart prod
```

### Research Mode
```bash
# Start research (Jupyter)
docker-compose --profile research up

# Access Jupyter
open http://localhost:8888

# Run experiments di notebook
# Save results ke ./research/results/
```

### Development Mode
```bash
# Start both
docker-compose --profile research up

# Prod runs live trading
# Research runs Jupyter
# Kedua container bisa akses shared data
```

---

## 📊 Perbandingan Container

| Aspek | Prod Container | Research Container |
|-------|----------------|-------------------|
| **Size** | ~150MB | ~3GB |
| **Start time** | 2 detik | 30 detik |
| **Security** | Non-root, minimal | Root, full access |
| **Persistence** | Must be stateless | Can save state |
| **Restart** | Auto on crash | Manual only |
| **Network** | Isolated | Exposed port 8888 |
| **Monitoring** | Health checks | None |

---

## 🔄 Alur Integrasi Research → Prod

### Step 1: Eksperimen di Research
```python
# research/notebooks/01_lstm_test.ipynb

from research_src.models.experiments import LSTMModel

model = LSTMModel()
model.train(df)
accuracy = model.evaluate(test_df)

# Kalau bagus (accuracy > 60%):
# Save to research_src/models/candidates/
```

### Step 2: Validasi Kandidat
```bash
# Backtest kandidat
docker-compose --profile research run research python \
  -m research_src.backtest.validate_candidate lstm_v2

# Kalau profit > 20% annual:
# Promote ke prod
```

### Step 3: Copy ke Production
```bash
# Copy dari research candidates ke prod
$ cp research/src/models/candidates/lstm_v2.py \
     prod/src/engine/layer3_ml/

# Update prod __init__.py
# Add test di prod/tests/
# Build dan deploy
$ docker-compose build prod
$ docker-compose up -d prod
```

### Step 4: Monitoring
```bash
# Monitor new model performance
$ docker-compose logs -f prod | grep "LSTM"

# Kalau 1 bulan profit → success
# Kalau drawdown > 10% → rollback
```

---

## 🛡️ Security Benefits

### Production Container:
- ✅ Non-root user
- ✅ Minimal attack surface (no build tools)
- ✅ Read-only shared mount
- ✅ No dev dependencies
- ✅ Resource limits

### Research Container:
- ⚠️ Root access (diperlukan untuk ML tools)
- ⚠️ Exposed ports (Jupyter)
- ✅ Isolated from production
- ✅ Can be destroyed anytime

---

## 📁 File Mapping Detail

| Host Path | Prod Container | Research Container | Mode |
|-----------|----------------|-------------------|------|
| `./shared/` | `/shared` (ro) | `/shared` (rw) | ro/rw |
| `./data/market/` | `/data/market` | `/data/market` | rw |
| `./data/db/` | `/data/db` | `/data/db` | rw |
| `./data/logs/` | `/data/logs` | Not mounted | rw |
| `./prod/src/` | `/src` | `/prod_src` (ro) | ro |
| `./research/` | Not mounted | `/workspace` | rw |

---

## 🎯 Summary Keuntungan

| Keuntungan | Penjelasan |
|------------|------------|
| **Isolation sempurna** | Research gabisa break production |
| **Security** | Prod minimal, Research isolated |
| **Scalability** | Prod bisa scale horizontal |
| **Reproducibility** | Research 100% reproducible |
| **Resource efficiency** | Prod kecil, Research besar tapi optional |
| **Easy deployment** | Single command deploy prod |
| **Clean boundaries** | Physically separated by container |

---

## ❓ FAQ

**Q: Kenapa tidak pakai VM/server terpisah?**  
A: Container lebih ringan, lebih cepat deploy, lebih mudah maintain.

**Q: Bisa running bare metal?**  
A: Bisa, tapi lewatkan keuntungan isolation. Sarankan tetap pakai container.

**Q: Data persistence gimana?**  
A: Shared volume `./data/` di-mount ke kedua container.

**Q: Backup strategy?**  
A: Backup `./data/` dan `./prod/src/` saja. Research bisa rebuild.
