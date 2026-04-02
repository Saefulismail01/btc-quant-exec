# Quick Reference - Common Commands & Links

Fast lookup for the most common tasks and commands.

---

## Most Important Files (Bookmark These)

| File | What to use it for | Link |
|------|------------------|------|
| **START_HERE.md** | Entry point - choose your path | `../START_HERE.md` |
| **README.md** | Full project overview | `../../README.md` |
| **QUICK_REFERENCE.md** | Common commands (this file) | (you are here) |
| **CRYPTO_RELEVANCE_ANALYSIS_2026.md** | Key research findings | `../research/CRYPTO_RELEVANCE_ANALYSIS_2026.md` |
| **MCP_WITH_OTHER_AI.md** | AI integration setup | `../integration/MCP_WITH_OTHER_AI.md` |

---

## Trading Commands

### Test Connection
```bash
python backend/scripts/test_lighter_connection.py
```

### Run Tests
```bash
pytest backend/tests/ -v
```

### Enable Trading (DANGEROUS - use carefully!)
Edit `.env` and change:
```
LIGHTER_TRADING_ENABLED=true
```

### Disable Trading (Safe)
Edit `.env` and set:
```
LIGHTER_TRADING_ENABLED=false
```

---

## Paper Search Commands

### CLI Search (Direct ArXiv)
```bash
cd learn/arxiv-mcp-server
python arxiv_simple.py search --query "econophysics" --limit 10
python arxiv_simple.py export --query "HMM finance" --format bibtex --output papers.bib
```

### HTTP API (For ChatGPT, Gemini, etc)
```bash
# Terminal 1: Start server
cd learn/paper-search-mcp
python mcp_http_server.py --port 8000

# Terminal 2: Search
curl "http://127.0.0.1:8000/search?query=econophysics&limit=5"
curl "http://127.0.0.1:8000/econophysics?query=power+law"
curl "http://127.0.0.1:8000/finance?query=statistical+arbitrage"
curl "http://127.0.0.1:8000/crypto?query=bitcoin"
```

### Use in Claude Code
```
@arxiv search "topic" limit:10
@paper-search-mcp search papers
```

---

## Paper Search Endpoints

When HTTP server running at `http://127.0.0.1:8000`:

| Endpoint | Purpose | Example |
|----------|---------|---------|
| `/search` | General search | `?query=econophysics&limit=10` |
| `/econophysics` | Econophysics papers | `?query=power+law` |
| `/finance` | Quantitative finance | `?query=machine+learning` |
| `/crypto` | Blockchain/crypto | `?query=bitcoin` |
| `/ai` | AI/ML papers | `?query=neural+networks` |
| `/categories` | List arXiv categories | `GET /categories` |
| `/docs` | API documentation | Swagger UI |
| `/health` | Health check | `GET /health` |

---

## Useful Search Queries (For Your Research)

### HMM & Regime Detection
```bash
# CLI
python arxiv_simple.py search --query "Hidden Markov Models financial markets"

# HTTP
curl "http://127.0.0.1:8000/search?query=Hidden+Markov+Models+financial+markets"
```

### Statistical Arbitrage
```bash
curl "http://127.0.0.1:8000/finance?query=statistical+arbitrage+cointegration"
```

### Kelly Criterion
```bash
curl "http://127.0.0.1:8000/finance?query=Kelly+criterion+position+sizing"
```

### On-Chain Bitcoin Analysis
```bash
curl "http://127.0.0.1:8000/crypto?query=blockchain+analysis+bitcoin+prediction"
```

### Entropy & Portfolio Optimization
```bash
curl "http://127.0.0.1:8000/search?query=entropy+portfolio+optimization"
```

### Econophysics General
```bash
curl "http://127.0.0.1:8000/econophysics?query=power+law+distributions"
```

---

## Environment Variables (Critical)

| Variable | Description | Example |
|----------|-------------|---------|
| `LIGHTER_MAINNET_API_KEY` | Lighter API key | `8e9eaef1...fd536` |
| `LIGHTER_MAINNET_API_SECRET` | Lighter API secret | `39c0ba8a...f610` |
| `LIGHTER_API_KEY_INDEX` | Key index for auth | `3` |
| `LIGHTER_ACCOUNT_INDEX` | Your account | `718591` |
| `LIGHTER_EXECUTION_MODE` | Live/testnet | `mainnet` |
| `LIGHTER_TRADING_ENABLED` | Enable/disable trades | `false` (safe) |

**Location**: `.env` (PRIVATE - not in git)

---

## Key Files Location Quick Map

```
btc-scalping-execution_layer/
├── docs/
│   ├── START_HERE.md ← Entry point
│   ├── README.md ← Master nav (in root too)
│   ├── setup/ ← Installation & setup guides
│   ├── integration/ ← AI platform guides
│   ├── research/ ← Key findings & papers
│   ├── guides/ ← How-to guides
│   ├── reference/ ← Quick lookups
│   └── architecture/ ← System design
│
├── learn/
│   ├── README.md ← Tools guide
│   ├── arxiv-mcp-server/ ← Direct ArXiv search
│   ├── paper-search-mcp/ ← Multi-source search
│   └── riset_renaisance/ ← Research files
│
├── backend/ ← Main code
├── tests/ ← 133 tests
├── scripts/ ← Utilities
│
├── README.md ← Project overview
├── .env ← Credentials (PRIVATE)
├── requirements.txt ← Dependencies
├── Dockerfile ← Container config
└── docker-compose.yml ← Compose config
```

---

## Troubleshooting Quick Links

| Problem | Solution |
|---------|----------|
| "Connection refused" | Check internet, verify `.env` API keys |
| "No papers found" | Try simpler query, wait 3s, check rate limiting |
| "Module not found" | Run: `pip install -r learn/paper-search-mcp/requirements.txt` |
| "ArXiv timeout" | Wait 30s, check internet, try again |
| "Trading not working" | Check LIGHTER_TRADING_ENABLED=false in .env |
| "Can't find a file" | Use `docs/reference/INDEX.md` |
| "Forgot a command" | Check this file or `docs/reference/QUICK_REFERENCE.md` |

---

## Reading Order by Goal

### Goal: Just Trade
```
1. START_HERE.md (5 min)
2. Test connection (1 min)
3. Check LIGHTER_TRADING_ENABLED in .env (1 min)
4. Trade (watch monitor)
```

### Goal: Understand Strategy
```
1. README.md (5 min)
2. ECONOPHYSICS_PAPERS.md (10 min)
3. CRYPTO_RELEVANCE_ANALYSIS_2026.md (45 min)
4. Review backend/app/use_cases/ code (30 min)
```

### Goal: Setup Paper Search with ChatGPT
```
1. MCP_WITH_OTHER_AI.md → ChatGPT section (15 min)
2. Start HTTP server (1 min)
3. Create Custom GPT (10 min)
4. Test search (2 min)
```

### Goal: Full Understanding
```
1. START_HERE.md (5 min)
2. README.md (5 min)
3. FOLDER_STRUCTURE.md (5 min)
4. CRYPTO_RELEVANCE_ANALYSIS_2026.md (45 min)
5. learn/README.md (10 min)
6. MCP_WITH_OTHER_AI.md (15 min)
→ Total: ~85 min
```

---

## Port Numbers to Remember

| Service | Port | Command |
|---------|------|---------|
| **Paper Search HTTP API** | 8000 | `python learn/paper-search-mcp/mcp_http_server.py --port 8000` |
| **Custom (if needed)** | 8001+ | Change `--port` argument |

---

## Test Commands

```bash
# Test Lighter connection
python backend/scripts/test_lighter_connection.py

# Run all backend tests
pytest backend/tests/ -v

# Run specific test
pytest backend/tests/test_lighter_execution_gateway.py -v

# Run with coverage
pytest backend/tests/ --cov=backend/app

# Health check on paper search API
curl http://127.0.0.1:8000/health

# Get API docs
curl http://127.0.0.1:8000/docs
```

---

## Key Statistics

- 📖 **Documentation**: 100+ pages
- 🧪 **Tests**: 133 passing
- 💻 **Code**: 3000+ lines
- 📚 **Research**: 45+ pages analysis
- 📄 **Papers**: 5 econophysics papers
- 🛠️ **Tools**: 2 MCP servers + HTTP API
- 📊 **Time to understand**: ~80-90 min

---

## Things to NEVER Do

- ❌ Commit `.env` with credentials
- ❌ Run trades with `LIGHTER_TRADING_ENABLED=true` without testing
- ❌ Modify private key format without understanding SDK
- ❌ Share `LIGHTER_MAINNET_API_SECRET` with anyone
- ❌ Delete `.env` without backup
- ❌ Edit Lighter SDK integration without understanding SDK version

---

## Things to ALWAYS Do

- ✅ Test connection before trading: `test_lighter_connection.py`
- ✅ Keep `.env` credentials secure
- ✅ Start with small positions first
- ✅ Monitor trades closely in first 24h
- ✅ Review new strategy code before deploying
- ✅ Run tests: `pytest backend/tests/ -v`
- ✅ Use `LIGHTER_TRADING_ENABLED=false` by default

---

## Keyboard Shortcuts (In This Docs)

- **Ctrl+F**: Search within current file
- **Ctrl+K Ctrl+O**: Open file by name (VSCode)
- **Ctrl+Shift+O**: Go to symbol (VSCode)

---

## Quick Help

| Question | Answer |
|----------|--------|
| Where do I start? | `START_HERE.md` |
| What is this project? | `README.md` |
| How do I trade? | `../guides/TRADING_GUIDE.md` |
| How do I search papers? | `../guides/PAPER_SEARCH_GUIDE.md` |
| Where is my file? | `INDEX.md` (this folder) |
| What is the system design? | `../architecture/README.md` |
| How is it organized? | `FOLDER_STRUCTURE.md` |
| What's the research? | `../research/CRYPTO_RELEVANCE_ANALYSIS_2026.md` |
| How do I use ChatGPT? | `../integration/MCP_WITH_OTHER_AI.md` |

---

## Updates & Changes

**Last Updated**: April 2, 2026  
**Keep Bookmarked**: Yes ⭐  
**Print/Download**: Recommended for offline reference

---

**Print this or bookmark it — you'll use it frequently!** 📌
