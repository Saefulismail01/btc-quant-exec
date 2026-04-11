# Learn - Research & Paper Search Tools

Folder untuk research, learning materials, dan academic paper discovery tools.

---

## Folder Structure

```
learn/
├── README.md ← You are here
│
├── arxiv-mcp-server/
│   ├── arxiv_simple.py              Direct ArXiv search CLI
│   ├── econophysics_search.py        Econophysics-focused search
│   ├── test_export.bib               Sample BibTeX export
│   └── ... (other MCP files)
│
├── paper-search-mcp/
│   ├── mcp_http_server.py            REST API bridge for all AI tools
│   ├── econophysics_search.py        Specialized econophysics search
│   └── ... (other paper-search files)
│
├── riset_renaisance/
│   ├── CRYPTO_RELEVANCE_ANALYSIS_2026.md   Renaissance algo in crypto
│   ├── base_algo.md                         Algorithm synthesis
│   ├── SETUP_ARXIV_MCP_SERVER.md            Full technical docs
│   └── riset_jim_smons.md                   Team roster & pipeline
│
└── MCP_WITH_OTHER_AI.md          Panduan menggunakan MCP dengan ChatGPT, Gemini, dll
```

---

## Tools Available

### 1. ArXiv-MCP-Server (Direct API)
**Purpose**: Direct search arXiv papers  
**Best for**: Quick terminal searches  
**Status**: ✅ Ready

```bash
cd arxiv-mcp-server
python arxiv_simple.py search --query "econophysics" --limit 10
```

---

### 2. Paper-Search-MCP (Multi-source)
**Purpose**: Search multiple paper sources  
**Best for**: Comprehensive research  
**Status**: ✅ Ready

```bash
# Via HTTP API (for all AI tools)
cd paper-search-mcp
python mcp_http_server.py --port 8000

# Then access from ChatGPT, Gemini, etc
curl "http://127.0.0.1:8000/search?query=econophysics&limit=5"
```

---

### 3. Renaissance Algorithm Research
**Purpose**: Understand Renaissance Technologies methods  
**Files**: 
- `riset_renaisance/CRYPTO_RELEVANCE_ANALYSIS_2026.md` — Current relevance analysis
- `riset_renaisance/base_algo.md` — Algorithm synthesis
- `riset_renaisance/riset_jim_smons.md` — Team composition

**Status**: ✅ Complete analysis

---

## Quick Start

### For Claude Users (VSCode)
```bash
# No setup needed! MCP already configured
# In Claude Code chat:
@arxiv search "econophysics" limit:10

# Or read papers directly:
cat riset_renaisance/CRYPTO_RELEVANCE_ANALYSIS_2026.md
```

### For ChatGPT Users
```bash
# Terminal: Start HTTP bridge
cd paper-search-mcp
python mcp_http_server.py --port 8000

# Then: Create Custom GPT at https://chatgpt.com/gpts/editor
# Add action pointing to http://127.0.0.1:8000
```

### For Any AI Tool via HTTP
```bash
# Start server
cd paper-search-mcp
python mcp_http_server.py --port 8000

# Access from any HTTP client
# curl, Postman, ChatGPT, Gemini, etc
```

---

## How to Use Each Tool

### Search for Papers

**ArXiv Direct**:
```bash
cd arxiv-mcp-server
python arxiv_simple.py search --query "econophysics" --limit 10
python arxiv_simple.py export --query "HMM finance" --format bibtex --output papers.bib
```

**Paper Search (Recommended)**:
```bash
cd paper-search-mcp
python mcp_http_server.py --port 8000

# In another terminal or your AI tool:
curl "http://127.0.0.1:8000/search?query=econophysics&limit=5"
curl "http://127.0.0.1:8000/econophysics?query=power+law"
curl "http://127.0.0.1:8000/finance?query=trading"
```

---

## Paper Search Endpoints

When HTTP server is running:

| Endpoint | Purpose | Example |
|----------|---------|---------|
| `/search` | General search | `?query=econophysics&limit=10` |
| `/econophysics` | Finance papers | `?query=power+law` |
| `/finance` | Quantitative finance | `?query=machine+learning` |
| `/crypto` | Blockchain/crypto | `?query=bitcoin` |
| `/ai` | AI/ML papers | `?query=neural+networks` |
| `/categories` | List arXiv categories | `GET /categories` |
| `/docs` | API documentation | Swagger UI |
| `/health` | Health check | `GET /health` |

---

## For BTC-QUANT Research

### Recommended Reading Order

1. **Start Here**:
   - `ECONOPHYSICS_PAPERS.md` (in project root)
   - Read: Bouchaud's Mandelbrot paper

2. **Deep Dive**:
   - `riset_renaisance/CRYPTO_RELEVANCE_ANALYSIS_2026.md`
   - Understand: HMM, Kelly Criterion, Entropy methods

3. **Implementation**:
   - Map papers to your algorithms
   - Apply econophysics principles

### Search Queries for Your Work

```bash
# Regime detection & HMM
/search?query=Hidden+Markov+Models+financial+markets

# Statistical arbitrage
/finance?query=statistical+arbitrage+cointegration

# Kelly Criterion
/finance?query=Kelly+criterion+position+sizing

# On-chain analysis
/crypto?query=blockchain+analysis+bitcoin+prediction

# Entropy & optimization
/search?query=entropy+portfolio+optimization
```

---

## Research Status

| Topic | Status | Files |
|-------|--------|-------|
| Renaissance Algorithm Analysis | ✅ Complete | `riset_renaisance/` |
| Crypto Relevance (2026) | ✅ Complete | `CRYPTO_RELEVANCE_ANALYSIS_2026.md` |
| Econophysics Papers | ✅ Found 5 | `ECONOPHYSICS_PAPERS.md` |
| MCP Setup | ✅ Complete | `arxiv-mcp-server/`, `paper-search-mcp/` |
| Multi-AI Integration | ✅ Complete | `MCP_WITH_OTHER_AI.md` |

---

## File Descriptions

### arxiv-mcp-server/
- **arxiv_simple.py**: Command-line tool for direct arXiv searches
- **econophysics_search.py**: Specialized econophysics paper finder
- **run_server.py**: MCP server entry point
- **poetry.lock**: Dependency lock file

### paper-search-mcp/
- **mcp_http_server.py**: REST API bridge (use with ChatGPT, Gemini, etc)
- **main.py**: Original MCP server
- **paper_search_mcp/**: Package source code
- **pyproject.toml**: Project configuration

### riset_renaisance/
- **CRYPTO_RELEVANCE_ANALYSIS_2026.md**: ⭐ Renaissance methods in crypto 2026
- **base_algo.md**: Algorithm synthesis with FAKTA/PUBLIKASI/SINTESIS
- **SETUP_ARXIV_MCP_SERVER.md**: Full technical documentation
- **riset_jim_smons.md**: 37+ scientist roster
- **riset_jim_simons_id.qmd**: Indonesian version (Quarto format)

---

## Integration Guide

### With Claude (Already Setup)
No additional setup needed. Use in Claude Code:
```
@arxiv search "topic"
@paper-search-mcp search papers
```

### With ChatGPT / Gemini / Others
See: **MCP_WITH_OTHER_AI.md**

### Via HTTP API
1. Run: `python paper-search-mcp/mcp_http_server.py --port 8000`
2. Access: `http://127.0.0.1:8000/docs`
3. Use endpoint in any HTTP client

---

## Troubleshooting

### "ModuleNotFoundError"
```bash
pip install -r paper-search-mcp/requirements.txt
# or
pip install mcp httpx requests feedparser fastapi uvicorn
```

### "Connection refused"
```bash
# Ensure HTTP server running in another terminal
python paper-search-mcp/mcp_http_server.py --port 8000

# Test:
curl http://127.0.0.1:8000/health
```

### "No papers found"
- Check internet connection
- Try simpler query (e.g., "bitcoin" vs "quantum econophysics")
- Wait 3 seconds between requests (rate limiting)

---

## Next Steps

1. ✅ Read: `ECONOPHYSICS_PAPERS.md` (5 key papers identified)
2. ✅ Explore: `riset_renaisance/CRYPTO_RELEVANCE_ANALYSIS_2026.md`
3. ✅ Implement: Apply findings to BTC-QUANT strategies
4. ✅ Automate: Schedule daily paper searches via `/schedule` skill

---

**Everything is ready!** Start researching! 🚀

For detailed guides:
- Paper search: See `MCP_WITH_OTHER_AI.md`
- Renaissance algo: See `riset_renaisance/README.md` (or read files directly)
- Setup details: See individual tool READMEs
