# 🔗 ArXiv Integration Setup — Complete Package

## What's in This Package?

You now have everything needed to connect Claude Code to arXiv journal for live research.

### 📄 Documentation Files

| File | Purpose | Read Time |
|------|---------|-----------|
| **ARXIV_SETUP_SUMMARY.md** | High-level overview & architecture | 3 min |
| **ARXIV_QUICK_START.md** | Quick reference for commands | 2 min |
| **ARXIV_EXECUTION_CHECKLIST.md** | Step-by-step verification | 5 min |
| **SETUP_ARXIV_MCP_SERVER.md** (in learn/riset_renaisance/) | Full detailed documentation | 15 min |

### 🚀 Setup Scripts

| Script | OS | Usage |
|--------|----|----|
| **ARXIV_SETUP.bat** | Windows | Double-click to run |
| **ARXIV_SETUP.sh** | Linux/macOS/WSL2 | `bash ARXIV_SETUP.sh` |

### 📦 What Gets Installed

- Python MCP server for arXiv integration
- Poetry dependency management
- 500MB cache directory for papers
- CLI tools for searching, analyzing, exporting papers

---

## ⚡ 5-MINUTE QUICK START

### Step 1: Run Setup
**Windows**: Double-click `ARXIV_SETUP.bat`  
**Linux/WSL**: Run `bash ARXIV_SETUP.sh`

### Step 2: Restart Claude Code
Close and reopen Claude Code completely.

### Step 3: Test It Works
```bash
cd learn/arxiv-mcp-server
poetry run arxiv-mcp search --query "bitcoin" --limit 3
```

**Done!** You now have access to 2+ million arXiv papers.

---

## 📖 First-Time Users

1. **Start here**: Read `ARXIV_SETUP_SUMMARY.md` (3 minutes)
2. **Then do**: Follow `ARXIV_EXECUTION_CHECKLIST.md` (20 minutes)
3. **Quick reference**: Bookmark `ARXIV_QUICK_START.md`
4. **Need help**: See `SETUP_ARXIV_MCP_SERVER.md` → Troubleshooting

---

## 🎯 Common Tasks

### Search for papers
```bash
cd learn/arxiv-mcp-server
poetry run arxiv-mcp search --query "Hidden Markov Models" --limit 20
```

### Export as bibliography
```bash
poetry run arxiv-mcp export --format bibtex --query "statistical arbitrage" --output papers.bib
```

### Run daily research automation
```bash
/schedule 0 9 * * * poetry run arxiv-mcp search "bitcoin trading" --limit 10
```

More commands: See `ARXIV_QUICK_START.md`

---

## 🔬 For BTC-QUANT Research

Recommended research queries:

```bash
# Regime detection & HMM
poetry run arxiv-mcp search "Hidden Markov Models financial markets" --limit 25

# Statistical arbitrage
poetry run arxiv-mcp search "statistical arbitrage cryptocurrency cointegration" --limit 20

# On-chain analysis
poetry run arxiv-mcp search "blockchain analysis bitcoin prediction" --limit 20

# Position sizing & Kelly
poetry run arxiv-mcp search "Kelly criterion optimal position sizing" --limit 15

# Machine learning trading
poetry run arxiv-mcp search "machine learning cryptocurrency trading" --limit 25

# Export everything to BibTeX
poetry run arxiv-mcp export \
  --format bibtex \
  --query "HMM OR statistical arbitrage OR regime switching OR Kelly criterion" \
  --from 2023-01-01 \
  --output btc_quant_research.bib
```

---

## ✅ Verification

After setup, you should be able to:

- [ ] Run `poetry run arxiv-mcp --help` without errors
- [ ] Get JSON response from `arxiv-mcp search` command
- [ ] Export papers to BibTeX/CSV/JSON
- [ ] See `arxiv-mcp-server` in Claude Code's MCP Resources
- [ ] Schedule searches using `/schedule` skill

If all work: Setup successful! 🎉

---

## 🆘 Troubleshooting

**Issue**: Command not found  
**Fix**: `cd learn/arxiv-mcp-server && poetry shell`

**Issue**: MCP server not showing  
**Fix**: Restart Claude Code completely, check `~/.claude/settings.json`

**Issue**: Failed to download papers  
**Fix**: Check internet, try with longer timeout: `ARXIV_API_TIMEOUT=60 poetry run ...`

More help: `SETUP_ARXIV_MCP_SERVER.md` → Section 6

---

## 📋 Next Steps

1. ✅ Run setup script today
2. ✅ Verify with test query
3. ✅ Schedule daily paper syncs
4. ✅ Export papers to bibliography
5. ✅ Integrate papers with BTC-QUANT research

---

## 📚 Related Research

You also have:
- **CRYPTO_RELEVANCE_ANALYSIS_2026.md** — Renaissance algo relevance in crypto
- **base_algo.md** — Renaissance Technologies algorithm synthesis
- **riset_jim_simons.md** — Team composition & methods

These can all be enhanced with fresh arXiv papers!

---

## 💡 Pro Tips

1. **Create saved searches**: Add common queries to `research_queries.txt`
2. **Automate exports**: Schedule weekly BibTeX exports for backup
3. **Link to code**: Comment in code which papers justify which algorithms
4. **Track papers**: Store papers.csv to track what you've reviewed
5. **Set reminders**: Use `/schedule` to run searches during your research hours

---

## 📊 What You Can Now Do

```
You (Claude Code) 
    ↓
ArXiv-MCP Server (local)
    ↓
ArXiv API (2.3M papers)
    ↓
Search results → JSON, BibTeX, CSV
    ↓
Your research pipeline

All from within Claude Code!
```

---

## 🔗 Resources

- **Repository**: https://github.com/1Dark134/arxiv-mcp-server
- **arXiv**: https://arxiv.org/
- **arXiv API Docs**: https://arxiv.org/help/api/

---

## 📞 Support

- **Setup fails?** → See `SETUP_ARXIV_MCP_SERVER.md` → Troubleshooting (Section 6)
- **Need commands?** → See `ARXIV_QUICK_START.md`
- **Want advanced?** → See `SETUP_ARXIV_MCP_SERVER.md` → Sections 7-9

---

## 🎯 Success Metrics

You'll know everything works when:

✅ `poetry run arxiv-mcp search --query "bitcoin" --limit 1` returns JSON  
✅ Papers have `id`, `title`, `authors`, `published`, `summary`  
✅ No errors in output  
✅ Files can be exported to BibTeX  
✅ Claude Code shows `arxiv-mcp-server` in MCP Resources  

**When all ✅**: You're good to go! 🚀

---

**Version**: 1.0  
**Created**: April 2, 2026  
**Status**: Ready for setup

Happy researching! 📚
