# AI Integration Guide

How to use MCP (Model Context Protocol) paper search tools with different AI platforms.

---

## Supported Platforms

| Platform | Status | Setup Time | Setup Complexity |
|----------|--------|-----------|------------------|
| **Claude / Claude Code** | ✅ Auto-configured | 0 min | Easy |
| **ChatGPT / OpenAI** | ✅ Ready | 15 min | Medium |
| **Google Gemini** | ✅ Ready | 15 min | Medium |
| **Anthropic API** | ✅ Ready | 5 min | Easy |
| **Any HTTP Client** | ✅ Ready | 5 min | Easy |

---

## Quick Links by Platform

### I use Claude / Claude Code
→ Already setup! No additional configuration needed.

### I use ChatGPT
→ See `MCP_WITH_OTHER_AI.md` → Section "ChatGPT / OpenAI"

### I use Google Gemini
→ See `MCP_WITH_OTHER_AI.md` → Section "Google Gemini"

### I use Anthropic API (Node.js, Python)
→ See `MCP_WITH_OTHER_AI.md` → Section "Anthropic API"

### I want HTTP API (curl, Postman, custom tools)
→ See `MCP_WITH_OTHER_AI.md` → Section "HTTP API"

---

## Files in This Folder

| File | Content |
|------|---------|
| **MCP_WITH_OTHER_AI.md** | Complete integration guide for all platforms |

---

## Setup Overview

### Option 1: Claude (Already Working)
```
✅ No setup needed
✅ Use @arxiv or @paper-search commands
✅ Full integration ready
```

### Option 2: ChatGPT Custom GPT
```
1. Read: MCP_WITH_OTHER_AI.md (ChatGPT section)
2. Create Custom GPT at: https://chatgpt.com/gpts/editor
3. Add Action → HTTP endpoint
4. Point to: http://127.0.0.1:8000 (your HTTP server)
5. Use: Access paper search in ChatGPT
```

### Option 3: HTTP API (Any Tool)
```
1. Start server: python ../paper-search-mcp/mcp_http_server.py
2. Access: curl http://127.0.0.1:8000/search?query=bitcoin
3. Use: In any HTTP client (Postman, curl, JavaScript, Python)
```

---

## Common Workflows

### Search Papers from Claude
```
In Claude Code chat:
@arxiv search "econophysics" limit:10
```

### Search Papers from ChatGPT
```
1. Setup Custom GPT (see MCP_WITH_OTHER_AI.md)
2. Ask: "Search for papers on bitcoin halving"
3. ChatGPT uses your paper search API
```

### Search Papers Programmatically
```bash
# Via HTTP API
curl "http://127.0.0.1:8000/search?query=statistical+arbitrage&limit=5"
curl "http://127.0.0.1:8000/econophysics?query=power+law"
```

---

## Choosing the Right Integration

| Use Case | Platform | How |
|----------|----------|-----|
| **Daily research** | Claude | Built-in, no setup |
| **Multi-AI access** | HTTP API | 1 command, any tool |
| **ChatGPT workflows** | Custom GPT | 15 min setup |
| **Gemini workflows** | Gemini API | 15 min setup |
| **Custom automation** | HTTP API | Programmatic access |

---

## Troubleshooting

### "Connection refused" with ChatGPT/Gemini
→ HTTP server not running
→ Start: `python ../paper-search-mcp/mcp_http_server.py --port 8000`

### "Invalid OpenAPI schema"
→ Check `MCP_WITH_OTHER_AI.md` → Copy exact schema format

### "Timeout when searching"
→ Internet connectivity issue or arXiv rate limiting
→ Try: Simpler query, wait 3s between searches

---

## Full Documentation

See **MCP_WITH_OTHER_AI.md** for:
- Complete setup guides for each platform
- OpenAPI schema examples
- Troubleshooting by platform
- Advanced configurations
- HTTP endpoints reference

---

## Next Steps

1. Choose your AI platform
2. Follow setup in `MCP_WITH_OTHER_AI.md`
3. Test integration: search for a paper
4. Start researching!

---

**Status**: ✅ All platforms ready  
**Last Updated**: April 2, 2026
