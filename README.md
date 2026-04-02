# BTC-QUANT Execution Layer

Live trading bot execution layer for Bitcoin on Lighter mainnet with Renaissance Technologies research framework.

**Status**: ✅ Phase 3 Mainnet - First live order placed

---

## 📚 Quick Start

**New to this project?** → Start here:
1. Read [`docs/START_HERE.md`](docs/START_HERE.md) (5 min)
2. Read [`docs/README.md`](docs/README.md) (10 min)
3. Choose your path below

**Returning user?** → Direct access:
- Trading: [`docs/guides/TRADING_GUIDE.md`](docs/guides/TRADING_GUIDE.md)
- Research: [`docs/research/CRYPTO_RELEVANCE_ANALYSIS_2026.md`](docs/research/CRYPTO_RELEVANCE_ANALYSIS_2026.md)
- Paper Search: [`docs/guides/PAPER_SEARCH_GUIDE.md`](docs/guides/PAPER_SEARCH_GUIDE.md)
- AI Integration: [`docs/integration/MCP_WITH_OTHER_AI.md`](docs/integration/MCP_WITH_OTHER_AI.md)

---

## 🎯 What Is This?

BTC-QUANT is a **live trading bot** that executes orders on Lighter mainnet for Bitcoin perpetuals, powered by:
- ✅ Renaissance Technologies algorithmic methods
- ✅ Econophysics research framework
- ✅ Academic paper search (ArXiv integration)
- ✅ Multi-AI integration (Claude, ChatGPT, Gemini)

---

## 📂 Documentation Structure

All documentation is organized in `docs/` folder:

```
docs/
├── START_HERE.md ← Entry point
├── README.md ← Navigation hub
├── setup/ ← Installation & setup guides
├── integration/ ← AI platform setup
├── research/ ← Key findings & papers
├── guides/ ← How-to guides
├── reference/ ← Quick lookup
└── architecture/ ← System design
```

**Find what you need**: [`docs/reference/INDEX.md`](docs/reference/INDEX.md)

**Quick commands**: [`docs/reference/QUICK_REFERENCE.md`](docs/reference/QUICK_REFERENCE.md)

---

## 🚀 Key Features

| Feature | Status | Details |
|---------|--------|---------|
| **Live Trading** | ✅ | Mainnet execution on Lighter |
| **Strategy** | ✅ | FixedStrategy ($99 margin, 5x leverage) |
| **Research** | ✅ | 45+ pages Renaissance analysis |
| **Paper Search** | ✅ | ArXiv + Multi-source tools |
| **AI Integration** | ✅ | Claude, ChatGPT, Gemini ready |
| **Tests** | ✅ | 133 passing tests |

---

## 📖 Documentation by Goal

### I want to trade
→ [`docs/guides/TRADING_GUIDE.md`](docs/guides/TRADING_GUIDE.md)

### I want to research papers
→ [`docs/guides/PAPER_SEARCH_GUIDE.md`](docs/guides/PAPER_SEARCH_GUIDE.md)

### I want to understand the strategy
→ [`docs/research/CRYPTO_RELEVANCE_ANALYSIS_2026.md`](docs/research/CRYPTO_RELEVANCE_ANALYSIS_2026.md)

### I want to use with ChatGPT/Gemini
→ [`docs/integration/MCP_WITH_OTHER_AI.md`](docs/integration/MCP_WITH_OTHER_AI.md)

### I want to understand everything
→ Read [`docs/START_HERE.md`](docs/START_HERE.md) → Follow suggested path

---

## 🛠️ Quick Setup

### Test Trading Connection
```bash
python backend/scripts/test_lighter_connection.py
```

### Run Tests
```bash
pytest backend/tests/ -v
```

### Search Papers (CLI)
```bash
cd learn/arxiv-mcp-server
python arxiv_simple.py search --query "bitcoin"
```

### Search Papers (HTTP API)
```bash
cd learn/paper-search-mcp
python mcp_http_server.py --port 8000
# In another terminal:
curl "http://127.0.0.1:8000/search?query=econophysics"
```

---

## 📊 Project Statistics

- 📖 **Documentation**: 100+ pages
- 🧪 **Tests**: 133 passing
- 💻 **Code**: 3000+ lines (backend)
- 📚 **Research**: 45+ pages analysis
- 📄 **Papers**: 5 econophysics papers found
- 🛠️ **Tools**: 2 MCP servers + HTTP API

---

## 🔧 Core Components

- **`backend/`** – Execution layer (Lighter mainnet integration)
- **`learn/`** – Research tools and paper search
  - `arxiv-mcp-server/` – Direct ArXiv API access
  - `paper-search-mcp/` – Multi-source paper search
  - `riset_renaisance/` – Renaissance research files
- **`tests/`** – Test suite (133 tests)
- **`docs/`** – Complete documentation

---

## ⚙️ Configuration

Required: `.env` file (template: `.env.template`)

**Key variables**:
```
LIGHTER_MAINNET_API_KEY=...
LIGHTER_MAINNET_API_SECRET=...
LIGHTER_ACCOUNT_INDEX=718591
LIGHTER_TRADING_ENABLED=false  # false by default (safe)
```

---

## 📞 Need Help?

- **Getting started?** → [`docs/START_HERE.md`](docs/START_HERE.md)
- **Finding a file?** → [`docs/reference/INDEX.md`](docs/reference/INDEX.md)
- **Need quick command?** → [`docs/reference/QUICK_REFERENCE.md`](docs/reference/QUICK_REFERENCE.md)
- **Confused about structure?** → [`docs/reference/FOLDER_STRUCTURE.md`](docs/reference/FOLDER_STRUCTURE.md)

---

**Status**: ✅ Production Ready — Phase 3 Mainnet  
**Last Updated**: April 2, 2026
