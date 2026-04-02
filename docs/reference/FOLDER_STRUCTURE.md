# BTC-QUANT Execution Layer - Folder Structure

**Complete project organization guide**

---

## Project Root Structure

```
btc-scalping-execution_layer/
│
├── 📚 DOCUMENTATION (Start here!)
│   ├── README.md ← Project overview
│   ├── INDEX.md ← Master file index
│   ├── FOLDER_STRUCTURE.md ← This file
│   └── MCP_WITH_OTHER_AI.md ← AI integration guide
│
├── 🔧 SETUP & TOOLS
│   ├── SETUP_COMPLETE.md ← Setup status & quick reference
│   ├── ARXIV_README.md ← ArXiv integration overview
│   ├── ARXIV_SETUP.bat ← Windows setup script
│   ├── ARXIV_SETUP.sh ← Linux/WSL setup script
│   ├── ARXIV_SETUP_SUMMARY.md ← Setup architecture
│   ├── ARXIV_QUICK_START.md ← Common commands
│   ├── ARXIV_EXECUTION_CHECKLIST.md ← Step-by-step verification
│   └── arxiv-cli ← Bash wrapper for searches
│
├── 🔬 RESEARCH
│   ├── ECONOPHYSICS_PAPERS.md ← 5 key papers (Feb-Oct 2025)
│   └── learn/ ← All learning materials (see below)
│
├── 💻 BACKEND CODE
│   ├── backend/ ← Main execution layer code
│   ├── scripts/ ← Testing & utility scripts
│   ├── tests/ ← Test suite (133 tests)
│   └── docker-compose.yml ← Docker configuration
│
├── ⚙️ CONFIGURATION
│   ├── .env ← Environment variables (PRIVATE)
│   ├── .env.template ← Template
│   ├── Dockerfile ← Docker build
│   ├── pyrightconfig.json ← Type checking config
│   ├── requirements.txt ← Python dependencies
│   ├── .gitignore ← Git ignore rules
│   └── .dockerignore ← Docker ignore rules
│
└── 📂 learn/ ← Learning & Research (See below)
```

---

## `learn/` Subfolder Structure

```
learn/
│
├── 📖 MASTER GUIDE
│   ├── README.md ← Start here! Overview of all tools
│   └── MCP_WITH_OTHER_AI.md ← Integration with ChatGPT, Gemini, etc
│
├── 🔍 PAPER SEARCH TOOLS
│   │
│   ├── arxiv-mcp-server/ ← Direct ArXiv integration
│   │   ├── arxiv_simple.py ← CLI tool (main)
│   │   ├── arxiv_cli.py ← Alternative CLI
│   │   ├── run_server.py ← Server runner
│   │   ├── README.md ← Original docs
│   │   ├── poetry.lock ← Dependencies
│   │   └── ... (other files)
│   │
│   └── paper-search-mcp/ ← Multi-source search
│       ├── mcp_http_server.py ← HTTP bridge (for ChatGPT, Gemini)
│       ├── econophysics_search.py ← Specialized search
│       ├── README.md ← Original docs
│       ├── pyproject.toml ← Project config
│       └── ... (other files)
│
└── 📚 RESEARCH FILES
    │
    └── riset_renaisance/ ← Renaissance Technologies research
        ├── CRYPTO_RELEVANCE_ANALYSIS_2026.md ← ⭐ KEY FILE
        │   └── Analysis of Renaissance methods in crypto 2026
        │
        ├── base_algo.md ← Algorithm synthesis
        │   └── FAKTA/PUBLIKASI/SINTESIS framework
        │
        ├── SETUP_ARXIV_MCP_SERVER.md ← Full technical docs
        │   └── Complete setup instructions & troubleshooting
        │
        ├── riset_jim_smons.md ← Team composition
        │   └── 37+ scientist roster & pipeline analysis
        │
        └── riset_jim_simons_id.qmd ← Indonesian version
            └── Quarto format (PDF/HTML exportable)
```

---

## File Categories & Purpose

### 📖 DOCUMENTATION (Start Here)

| File | Purpose | Read Time |
|------|---------|-----------|
| **README.md** | Project overview & status | 5 min |
| **INDEX.md** | Master file navigation | 3 min |
| **FOLDER_STRUCTURE.md** | This file - structure guide | 5 min |
| **MCP_WITH_OTHER_AI.md** | AI integration guide | 15 min |

**Start with**: README.md, then MCP_WITH_OTHER_AI.md

---

### 🔧 SETUP & TOOLS (ArXiv Integration)

| File | Purpose | When to Use |
|------|---------|-----------|
| **SETUP_COMPLETE.md** | Setup status & quick reference | After setup |
| **ARXIV_README.md** | Overview of ArXiv integration | Getting started |
| **ARXIV_SETUP.bat** | Windows automated setup | Windows users |
| **ARXIV_SETUP.sh** | Linux/WSL setup | Linux/WSL users |
| **ARXIV_SETUP_SUMMARY.md** | Architecture explanation | Understanding how it works |
| **ARXIV_QUICK_START.md** | Common commands | Daily usage |
| **ARXIV_EXECUTION_CHECKLIST.md** | Step-by-step verification | Verifying setup |

**Workflow**: 
1. Run setup script (ARXIV_SETUP.bat or .sh)
2. Read ARXIV_QUICK_START.md
3. Keep SETUP_COMPLETE.md bookmarked

---

### 🔬 RESEARCH

| File | Purpose | Priority |
|------|---------|----------|
| **ECONOPHYSICS_PAPERS.md** | 5 key papers found (2025-2026) | ⭐⭐⭐ HIGH |
| **learn/riset_renaisance/** | All Renaissance research | ⭐⭐⭐ HIGH |
| **learn/README.md** | Learn folder guide | ⭐⭐ MEDIUM |

**Key Research Files** (in learn/riset_renaisance/):
1. **CRYPTO_RELEVANCE_ANALYSIS_2026.md** ← Most important
2. **base_algo.md** ← Algorithm details
3. **riset_jim_smons.md** ← Team background

---

### 💻 CODE

| Folder | Purpose |
|--------|---------|
| **backend/** | Main execution layer |
| **scripts/** | Testing & utilities |
| **tests/** | Test suite (133 tests) |

---

### ⚙️ CONFIGURATION

| File | Purpose | Edit? |
|------|---------|-------|
| **.env** | Live credentials | ⚠️ PRIVATE - Don't edit |
| **.env.template** | Template | ✅ Reference only |
| **Dockerfile** | Docker build | ⚠️ Experts only |
| **requirements.txt** | Dependencies | ⚠️ For pip install |
| **pyproject.toml** | Project config | ⚠️ For Poetry |

---

## How to Navigate

### If you want to...

**Search papers**
→ `learn/README.md` → Pick your tool (ArXiv, Paper Search, or HTTP API)

**Use with ChatGPT**
→ `MCP_WITH_OTHER_AI.md` → Section "ChatGPT / OpenAI"

**Use with Gemini**
→ `MCP_WITH_OTHER_AI.md` → Section "Google Gemini"

**Understand Renaissance methods**
→ `learn/riset_renaisance/CRYPTO_RELEVANCE_ANALYSIS_2026.md`

**Find econophysics papers**
→ `ECONOPHYSICS_PAPERS.md`

**Troubleshoot setup**
→ `ARXIV_EXECUTION_CHECKLIST.md` or `SETUP_COMPLETE.md`

**Get quick commands**
→ `ARXIV_QUICK_START.md`

---

## File Organization by Use Case

### For Trading Strategy Development
```
1. Read: README.md (overview)
2. Read: ECONOPHYSICS_PAPERS.md (5 key papers)
3. Deep: learn/riset_renaisance/CRYPTO_RELEVANCE_ANALYSIS_2026.md
4. Implement: Apply findings to backend code
```

### For Paper Research
```
1. Start: learn/README.md
2. Choose: Your AI tool (Claude, ChatGPT, etc)
3. Setup: Follow MCP_WITH_OTHER_AI.md if needed
4. Search: Use ARXIV_QUICK_START.md commands
```

### For System Setup
```
1. Run: ARXIV_SETUP.bat (Windows) or ARXIV_SETUP.sh (Linux)
2. Verify: ARXIV_EXECUTION_CHECKLIST.md
3. Reference: SETUP_COMPLETE.md for troubleshooting
```

---

## File Maintenance

### Essential Files (Keep Updated)
- ✅ `learn/riset_renaisance/CRYPTO_RELEVANCE_ANALYSIS_2026.md` - Key research
- ✅ `ECONOPHYSICS_PAPERS.md` - Important findings
- ✅ `README.md` - Project status

### Setup Reference (Read-Only)
- 📖 `ARXIV_QUICK_START.md` - Commands don't change
- 📖 `SETUP_COMPLETE.md` - Status report
- 📖 `ARXIV_EXECUTION_CHECKLIST.md` - Verification steps

### Configuration (Private)
- 🔐 `.env` - NEVER commit, NEVER modify without knowing
- 🔐 `backend/.env` - VPS configuration

---

## Quick Reference

### Most Important Files (Read These)
1. **README.md** ← Start here
2. **learn/riset_renaisance/CRYPTO_RELEVANCE_ANALYSIS_2026.md** ← Key findings
3. **ECONOPHYSICS_PAPERS.md** ← Research papers
4. **learn/README.md** ← Tools guide
5. **MCP_WITH_OTHER_AI.md** ← AI integration

### Most Used Files (Keep Bookmarked)
- `ARXIV_QUICK_START.md` - Daily commands
- `learn/README.md` - Tool reference
- `SETUP_COMPLETE.md` - Quick troubleshooting

### Never Edit (Reference Only)
- `setup scripts` - Just run, don't edit
- `.env` - Only if you know what you're doing
- Configuration files - Expert use only

---

## Folder Size & Organization

```
btc-scalping-execution_layer/
├── Documentation: ~100KB
│   └── 15+ markdown files with guides
│
├── Code (backend/): ~500KB
│   └── Python execution layer
│
├── Research (learn/): ~2MB
│   ├── arxiv-mcp-server/: ~600KB
│   ├── paper-search-mcp/: ~1.2MB
│   └── riset_renaisance/: ~200KB
│
└── Config & Scripts: ~50KB
    └── Docker, env, requirements
```

---

## Version Control

**Tracked in git** ✅
- All code files
- All documentation
- Configuration templates

**NOT tracked** ⚠️
- `.env` (credentials) - Use .gitignore
- `paper cache` - Local only
- `.claude/` folder - Local config

---

## Setup Status

| Component | Status | Files |
|-----------|--------|-------|
| Backend | ✅ Live | `backend/` |
| ArXiv Integration | ✅ Working | `arxiv-*` files |
| Paper Search | ✅ Ready | `learn/paper-search-mcp/` |
| Research | ✅ Complete | `learn/riset_renaisance/` |
| Documentation | ✅ Complete | `*_*.md` files |

---

## Next Steps

1. **Read**: This file you're reading
2. **Then**: README.md (project overview)
3. **Then**: Choose your use case above
4. **Go**: Follow the appropriate file path

**Everything is organized and ready!** 🚀

---

**Last Updated**: April 2, 2026  
**Maintained By**: Claude Code  
**Status**: ✅ Complete
