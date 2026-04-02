# Setup & Installation Guide

Complete setup instructions for BTC-QUANT execution layer and tools.

---

## Quick Start

### Path 1: Just Trade (5 min)
```bash
# Verify credentials in .env
# Test connection
python backend/scripts/test_lighter_connection.py
```

### Path 2: Full Setup (30 min)
```bash
# Windows
ARXIV_SETUP.bat

# Linux/WSL
bash ARXIV_SETUP.sh
```

---

## Files in This Folder

| File | Purpose | When to Use |
|------|---------|-----------|
| **ARXIV_SETUP_SUMMARY.md** | Architecture overview | Understanding the system |
| **ARXIV_EXECUTION_CHECKLIST.md** | Step-by-step verification | After running setup script |
| **ARXIV_QUICK_START.md** | Common commands | Daily usage |
| **ARXIV_README.md** | ArXiv integration overview | Getting started with papers |
| **SETUP_COMPLETE.md** | Setup status & quick reference | Troubleshooting |

---

## Setup Order

1. **Check Prerequisites**
   - Python 3.9+ installed
   - pip available
   - Internet connection

2. **Run Setup Script**
   - Windows: `ARXIV_SETUP.bat`
   - Linux: `bash ARXIV_SETUP.sh`

3. **Verify Installation**
   - Follow `ARXIV_EXECUTION_CHECKLIST.md`
   - Run test commands in `ARXIV_QUICK_START.md`

4. **Troubleshoot if Needed**
   - Check `SETUP_COMPLETE.md`
   - Read relevant section in `ARXIV_README.md`

---

## System Architecture

The setup installs:

```
Paper Search Tools
├── ArXiv MCP Server (direct API access)
├── Paper Search MCP (multi-source)
└── HTTP API (for ChatGPT, Gemini, etc)

AI Integration
├── Claude/MCP (auto-configured)
├── ChatGPT (via Custom GPT)
└── Google Gemini (via Custom Integration)
```

See `ARXIV_SETUP_SUMMARY.md` for technical details.

---

## Common Issues & Solutions

### "Command not found: python"
→ Check Python installation or use `python3`

### "Connection refused"
→ Ensure HTTP server running: `python ../paper-search-mcp/mcp_http_server.py`

### "No papers found"
→ Check internet, try simpler query, wait 3s between requests

See `SETUP_COMPLETE.md` for more troubleshooting.

---

## Next Steps

1. ✅ Run appropriate setup script for your OS
2. ✅ Verify with ARXIV_EXECUTION_CHECKLIST.md
3. ✅ Try first search: `arxiv_simple.py search --query "bitcoin"`
4. ✅ Integrate with your AI tool via `../integration/MCP_WITH_OTHER_AI.md`

---

**Status**: ✅ Setup complete and tested  
**Last Updated**: April 2, 2026
