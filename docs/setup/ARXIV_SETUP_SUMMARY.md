# ArXiv MCP Server Setup — Complete Summary

## What You're Setting Up

```
┌─────────────────────┐
│   Claude Code       │
│   (Your AI)         │
└──────────┬──────────┘
           │ (asks for research papers)
           ↓
┌─────────────────────┐
│  MCP Protocol       │ (communication bridge)
└──────────┬──────────┘
           ↓
┌─────────────────────┐
│ arXiv-mcp-server    │ (this repository)
│ (local service)     │
└──────────┬──────────┘
           │ (fetches papers)
           ↓
┌─────────────────────┐
│   arXiv.org         │ (journal database)
│   (public API)      │
└─────────────────────┘
```

**Result**: You can ask Claude Code to search arXiv papers directly, without leaving your IDE.

---

## 3-STEP SETUP

### Step 1: Run Setup Script (2 minutes)

**Windows**:
```bash
double-click ARXIV_SETUP.bat
```

**Linux/macOS/WSL2**:
```bash
bash ARXIV_SETUP.sh
```

**What it does**:
- ✅ Checks Python is installed
- ✅ Installs Poetry (dependency manager)
- ✅ Clones repository
- ✅ Installs dependencies
- ✅ Creates cache directory
- ✅ Updates `~/.claude/settings.json`

### Step 2: Restart Claude Code (1 minute)

Close and reopen Claude Code completely.

### Step 3: Verify It Works (1 minute)

Open terminal and run:
```bash
cd learn/arxiv-mcp-server
poetry run arxiv-mcp search --query "bitcoin" --limit 3
```

Expected output:
```json
[
  {
    "id": "2401.12345",
    "title": "Bitcoin Market Microstructure...",
    "authors": ["Author A", "Author B"],
    "published": "2024-01-15",
    "summary": "..."
  },
  ...
]
```

---

## THEN: Use It

### Example 1: Search from Terminal
```bash
cd learn/arxiv-mcp-server
poetry run arxiv-mcp search --query "Hidden Markov Models" --limit 20
```

### Example 2: Export to BibTeX
```bash
poetry run arxiv-mcp export \
  --format bibtex \
  --query "statistical arbitrage" \
  --output my_papers.bib
```

### Example 3: Automated Daily Research
```bash
/schedule 0 9 * * * poetry run arxiv-mcp search "bitcoin trading" --limit 10
```
(Runs every day at 9 AM)

---

## FILES CREATED

| File | Purpose |
|------|---------|
| `ARXIV_SETUP.bat` | Windows automated setup |
| `ARXIV_SETUP.sh` | Linux/WSL2 automated setup |
| `ARXIV_QUICK_START.md` | Quick reference (you are here) |
| `learn/riset_renaisance/SETUP_ARXIV_MCP_SERVER.md` | Full documentation |
| `learn/arxiv-mcp-server/` | Repository clone |

---

## REQUIREMENTS

✅ **Windows 11 with**:
- Python 3.9+ (from python.org)
- Git (from git-scm.com)
- ~500MB disk space

✅ **macOS/Linux with**:
- Python 3.9+
- Git
- ~500MB disk space

✅ **Internet connection** (for arXiv API)

---

## TROUBLESHOOTING

### "Command not found: arxiv-mcp"
```bash
# Solution: Activate Poetry environment first
cd learn/arxiv-mcp-server
poetry shell
arxiv-mcp search --query "test" --limit 1
```

### "MCP server not showing in Claude Code"
```bash
# Solution: Restart Claude Code
# Then check: Cmd+Shift+P → "List MCP Resources"
# arxiv-mcp-server should appear
```

### "Failed to connect to arXiv"
```bash
# Solution: Check internet connection
# Try with longer timeout:
ARXIV_API_TIMEOUT=60 poetry run arxiv-mcp search --query "test" --limit 1
```

---

## FOR BTC-QUANT RESEARCH

**Recommended Searches**:
```bash
# Research papers relevant to your system

# 1. Regime detection
poetry run arxiv-mcp search "regime switching markets" --from 2024-01-01 --limit 30

# 2. HMM applications
poetry run arxiv-mcp search "Hidden Markov Models finance" --from 2023-01-01 --limit 25

# 3. Statistical arbitrage
poetry run arxiv-mcp search "statistical arbitrage cryptocurrency" --from 2024-01-01 --limit 20

# 4. Position sizing
poetry run arxiv-mcp search "Kelly criterion optimal sizing" --from 2020-01-01 --limit 15

# 5. On-chain analysis
poetry run arxiv-mcp search "blockchain analysis bitcoin prediction" --from 2024-01-01 --limit 20

# Export all as bibliography
poetry run arxiv-mcp export \
  --format bibtex \
  --query "HMM OR statistical arbitrage OR regime switching" \
  --from 2023-01-01 \
  --output btc_quant_research.bib
```

---

## NEXT STEPS

1. **Immediate**: Run setup script today
2. **Day 1**: Verify with one search query
3. **Day 2**: Schedule daily paper syncs
4. **Day 3+**: Link papers to strategy components in code

---

## SUPPORT

- **Setup fails?** → Check `SETUP_ARXIV_MCP_SERVER.md` troubleshooting section
- **Need help with commands?** → See `ARXIV_QUICK_START.md`
- **Want advanced features?** → Read `SETUP_ARXIV_MCP_SERVER.md` section 7+

---

**Estimated Time to Setup**: 5 minutes  
**Estimated Time to First Search**: 10 minutes  
**ROI**: Direct access to 2+ million arXiv papers from Claude Code

Let's go! 🚀
