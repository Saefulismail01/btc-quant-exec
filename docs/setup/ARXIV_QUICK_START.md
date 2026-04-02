# ArXiv MCP Server - Quick Start Guide

## 1-MINUTE SETUP

### Windows (Native)
```bash
# Double-click to run:
ARXIV_SETUP.bat
```

### Linux/macOS/WSL2
```bash
# Run setup script
bash ARXIV_SETUP.sh
```

**That's it!** Restart Claude Code and you're done.

---

## VERIFY IT WORKS

After setup:

```bash
# In terminal (inside btc-scalping-execution_layer folder)
cd learn/arxiv-mcp-server
poetry run arxiv-mcp search --query "Hidden Markov Models" --limit 5
```

Expected output: JSON list of 5 papers from arXiv

---

## USAGE IN CLAUDE CODE

### In Chat:
```
Search arXiv for papers on Hidden Markov Models in finance

@arxiv search "Hidden Markov Models trading" limit:20
```

### In Terminal:
```bash
# Navigate to arxiv-mcp-server folder
cd learn/arxiv-mcp-server

# Search
poetry run arxiv-mcp search --query "statistical arbitrage bitcoin" --limit 20

# Analyze paper
poetry run arxiv-mcp analyze --paper-id 2401.12345

# Export to BibTeX
poetry run arxiv-mcp export --format bibtex --query "regime switching" --output papers.bib
```

---

## COMMON COMMANDS

### Search
```bash
poetry run arxiv-mcp search \
  --query "machine learning cryptocurrency" \
  --limit 30 \
  --from 2024-01-01
```

### Export
```bash
# BibTeX
poetry run arxiv-mcp export --format bibtex --query "topic" --output out.bib

# JSON
poetry run arxiv-mcp export --format json --query "topic" --output out.json

# CSV
poetry run arxiv-mcp export --format csv --query "topic" --output out.csv
```

### Analyze
```bash
# Get full paper details
poetry run arxiv-mcp analyze --paper-id 2401.12345

# With citations
poetry run arxiv-mcp analyze --paper-id 2401.12345 --citations
```

---

## ARXIV CATEGORIES (For Better Searches)

**Financial Markets & Crypto**:
- `q-fin.PM` - Portfolio Management
- `q-fin.ST` - Statistical Finance
- `q-fin.TR` - Trading
- `cs.AI` - Machine Learning
- `stat.AP` - Applied Statistics

**Search with category**:
```bash
poetry run arxiv-mcp search --query "HMM" --category "stat.AP" --limit 20
```

---

## RECOMMENDED SAVED SEARCHES

Create file `research_queries.txt`:

```
Hidden Markov Models cryptocurrency
statistical arbitrage bitcoin
regime detection trading
Kelly criterion position sizing
machine learning crypto volatility
on-chain analysis bitcoin
cointegration pairs trading
GARCH volatility models
entropy portfolio optimization
deep learning time series forecasting
```

Then batch search:
```bash
while IFS= read -r query; do
  poetry run arxiv-mcp search --query "$query" --limit 10 --from 2024-01-01
done < research_queries.txt
```

---

## AUTOMATED DAILY RESEARCH

Setup daily paper sync using Claude Code `/schedule` skill:

```
/schedule 0 9 * * * poetry run arxiv-mcp search "bitcoin trading algorithms" --limit 10 --output "research/papers_$(date +%Y%m%d).json"
```

This runs every day at 9 AM and saves results.

---

## TROUBLESHOOTING

### "Command not found: arxiv-mcp"

**Solution**: Make sure you're in the Poetry shell:
```bash
cd learn/arxiv-mcp-server
poetry shell
arxiv-mcp search --query "test" --limit 1
```

### "Failed to download from arXiv"

**Solution**: Check network, try with longer timeout:
```bash
ARXIV_API_TIMEOUT=60 poetry run arxiv-mcp search --query "test" --limit 1
```

### "MCP server not appearing in Claude Code"

**Solution**:
1. Check `~/.claude/settings.json` syntax is valid JSON
2. Restart Claude Code completely
3. Check logs: Output panel → Claude Code

---

## INTEGRATING WITH BTC-QUANT RESEARCH

### 1. Daily Paper Sync
```bash
/schedule 0 8 * * * poetry run arxiv-mcp search "regime switching" --limit 10 --output "research/papers.json"
```

### 2. Export as BibTeX
```bash
poetry run arxiv-mcp export \
  --format bibtex \
  --query "Hidden Markov Models financial markets" \
  --from 2024-01-01 \
  --output btc_quant_research.bib
```

### 3. Create Research Index
```bash
poetry run arxiv-mcp export \
  --format csv \
  --query "bitcoin algorithmic trading" \
  --from 2024-01-01 \
  --output research/btc_algo_papers.csv
```

---

## NEXT: ADVANCED USAGE

See full documentation: `SETUP_ARXIV_MCP_SERVER.md`

Topics:
- Custom MCP resources
- Automated indexing
- Citation analysis
- Trend tracking
- Integration with backtesting

---

**Version**: 1.0  
**Last Updated**: April 2, 2026
