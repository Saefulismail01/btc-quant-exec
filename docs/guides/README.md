# Practical Guides

Step-by-step guides for common tasks and workflows.

---

## Available Guides

### 📖 TRADING_GUIDE.md
**How to run and manage live trading**

- Setup trading environment
- Enable/disable trading safely
- Monitor positions
- Risk management
- Emergency procedures

**Read time**: 15 min  
**When**: Before trading live

---

### 📚 PAPER_SEARCH_GUIDE.md
**How to search for academic papers**

- Using ArXiv MCP directly
- Using Paper Search MCP
- HTTP API access
- Query formulation
- Saving and organizing papers

**Read time**: 10 min  
**When**: Starting paper research

---

### 🔧 AI_INTEGRATION_GUIDE.md
**How to integrate with ChatGPT, Gemini, etc**

- Choosing your AI platform
- Setup instructions per platform
- Running HTTP server
- Testing integration
- Common workflows

**Read time**: 15 min  
**When**: Setting up multi-AI access

---

## Quick Navigation

### I want to start trading
→ TRADING_GUIDE.md

### I want to search papers
→ PAPER_SEARCH_GUIDE.md

### I want to use ChatGPT or Gemini
→ AI_INTEGRATION_GUIDE.md

### I want to understand everything
→ Read all in order above

---

## Related Documentation

- **Setup**: See `../setup/` for technical setup guides
- **Research**: See `../research/` for key findings
- **Integration**: See `../integration/` for platform-specific setup
- **Reference**: See `../reference/` for quick lookup

---

## Quick Commands

### Test Trading Connection
```bash
python ../../backend/scripts/test_lighter_connection.py
```

### Search Papers (CLI)
```bash
cd ../../learn/arxiv-mcp-server
python arxiv_simple.py search --query "bitcoin"
```

### Search Papers (HTTP API)
```bash
cd ../../learn/paper-search-mcp
python mcp_http_server.py --port 8000
# In another terminal:
curl "http://127.0.0.1:8000/search?query=econophysics"
```

### Use with Claude Code
```
In Claude Code chat:
@arxiv search "statistical arbitrage"
```

---

## Learning Paths

### Path 1: Just Trade (5 min)
```
1. Verify .env credentials
2. Run: test_lighter_connection.py
3. Enable LIGHTER_TRADING_ENABLED if ready
4. Monitor trades
```

### Path 2: Research & Trade (45 min)
```
1. PAPER_SEARCH_GUIDE.md (10 min)
2. TRADING_GUIDE.md (15 min)
3. Search relevant papers (10 min)
4. Review findings, adjust strategy
5. Trade with insights (10 min)
```

### Path 3: Multi-AI Setup (30 min)
```
1. AI_INTEGRATION_GUIDE.md (15 min)
2. Setup your preferred platform (15 min)
3. Test integration
4. Use across tools
```

---

## File Organization

```
guides/
├── README.md ← You are here
├── TRADING_GUIDE.md
├── PAPER_SEARCH_GUIDE.md
└── AI_INTEGRATION_GUIDE.md
```

---

## Tips & Best Practices

### Trading Safety
- ✅ Always test connection first
- ✅ Start with small positions
- ✅ Monitor closely in first 24h
- ✅ Use emergency stop if needed
- ✅ Keep `.env` credentials private

### Paper Search Efficiency
- ✅ Start with broad queries
- ✅ Refine based on results
- ✅ Save interesting papers
- ✅ Cross-reference findings
- ✅ Document hypotheses

### AI Integration Success
- ✅ Test HTTP server first
- ✅ Verify API connectivity
- ✅ Start with simple queries
- ✅ Document your setup
- ✅ Combine multiple tools

---

## Troubleshooting Quick Links

### Trading Issues
→ See TRADING_GUIDE.md → "Troubleshooting" section

### Paper Search Issues
→ See PAPER_SEARCH_GUIDE.md → "Troubleshooting" section

### AI Integration Issues
→ See AI_INTEGRATION_GUIDE.md → "Troubleshooting" section

---

## Next Steps

1. Choose your primary task: Trading, Research, or Integration
2. Read the corresponding guide
3. Follow step-by-step instructions
4. Refer back as needed

---

**Status**: ✅ Guides ready  
**Last Updated**: April 2, 2026  
**Note**: Each guide is self-contained and can be read independently
