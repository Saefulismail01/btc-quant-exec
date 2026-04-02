# Paper Search MCP - Panduan Menggunakan dengan AI Lain

**Date**: April 2, 2026  
**Status**: Panduan lengkap untuk integrasi MCP dengan berbagai AI tools

---

## Daftar Isi
1. [Cara Kerja MCP](#cara-kerja-mcp)
2. [Claude (Semua Platform)](#claude-semua-platform)
3. [ChatGPT / OpenAI](#chatgpt--openai)
4. [Google Gemini](#google-gemini)
5. [Anthropic API](#anthropic-api)
6. [HTTP Server Bridge](#http-server-bridge)
7. [Troubleshooting](#troubleshooting)

---

## Cara Kerja MCP

```
┌─────────────────────┐
│   AI Tool           │  (ChatGPT, Gemini, Claude, etc)
│  (User Interface)   │
└──────────┬──────────┘
           │ MCP Protocol
           ↓
┌─────────────────────────────────────┐
│  MCP Server (di device Anda)        │
│  - paper-search-mcp                 │
│  - arxiv_mcp_server                 │
└──────────┬──────────────────────────┘
           │ HTTP API
           ↓
┌─────────────────────┐
│   Data Source       │
│   (arXiv, etc)      │
└─────────────────────┘
```

**Status di device Anda**: ✅ MCP servers sudah installed

---

## Claude (Semua Platform)

### Status: ✅ SUDAH BERJALAN

MCP configuration di `~/.claude/settings.json` berlaku untuk:

#### 1. Claude Code (VSCode Extension) ✅
```bash
# Sudah connected otomatis
# Coba di Claude Code chat:
@arxiv search "econophysics" limit:10
```

#### 2. Claude Web (claude.ai) ✅
```
Langsung available melalui MCP protocol
(Automatic dari browser)
```

#### 3. Claude Desktop App ✅
```
Settings → MCP Servers
arxiv-mcp-server sudah listed
```

#### 4. Anthropic API ✅
```python
from anthropic import Anthropic

client = Anthropic()

# MCP resource accessible via API
# (Jika configured di settings.json)
```

**Tidak perlu setup lagi untuk Claude!**

---

## ChatGPT / OpenAI

### Opsi 1: Custom GPT (Recommended)

**Step 1: Setup HTTP Bridge**
```bash
# 1. Install dependencies
pip install fastapi uvicorn

# 2. Run HTTP server
python mcp_http_server.py --port 8000

# Server akan berjalan di: http://127.0.0.1:8000
```

**Step 2: Create Custom GPT**
1. Go to https://chatgpt.com/gpts/editor
2. Click "Create new GPT"
3. Name: "Paper Search"
4. Instructions:
```
You have access to a paper search API at http://127.0.0.1:8000
Use these endpoints:
- /search?query=QUERY&limit=NUM
- /econophysics?query=QUERY&limit=NUM
- /finance?query=QUERY&limit=NUM
- /crypto?query=QUERY&limit=NUM

Always provide links to papers.
```
5. Scroll to "Actions"
6. Create new action
7. OpenAPI schema:
```json
{
  "openapi": "3.1.0",
  "info": {
    "title": "Paper Search API",
    "version": "1.0.0"
  },
  "servers": [
    {
      "url": "http://127.0.0.1:8000"
    }
  ],
  "paths": {
    "/search": {
      "get": {
        "operationId": "search_papers",
        "parameters": [
          {
            "name": "query",
            "in": "query",
            "required": true,
            "schema": {
              "type": "string"
            }
          },
          {
            "name": "limit",
            "in": "query",
            "schema": {
              "type": "integer",
              "default": 10
            }
          }
        ],
        "responses": {
          "200": {
            "description": "Papers found"
          }
        }
      }
    }
  }
}
```
8. Save → Done

**Step 3: Use in ChatGPT**
```
You: "Find papers on econophysics"
→ ChatGPT calls /search endpoint
→ Results displayed
```

---

### Opsi 2: ChatGPT with Plugin

1. Ensure HTTP server running (Step 1 above)
2. In ChatGPT: "Install plugin"
3. Use Zapier or Make.com to bridge:
   - Trigger: ChatGPT message
   - Action: Call http://127.0.0.1:8000/search

---

## Google Gemini

### Setup (Similar to ChatGPT)

**Step 1: HTTP Server**
```bash
python mcp_http_server.py --port 8000
```

**Step 2: Create Custom Tool**
1. Go to: https://makersuite.google.com/app/apikeys
2. Create new API Key
3. Use with Gemini API:

```python
import google.generativeai as genai

genai.configure(api_key="YOUR_API_KEY")

# Define custom tool
tool_definition = {
    "function_declarations": [
        {
            "name": "search_papers",
            "description": "Search academic papers",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of results"
                    }
                },
                "required": ["query"]
            }
        }
    ]
}

model = genai.GenerativeModel(
    model_name="gemini-pro",
    tools=[tool_definition]
)

response = model.generate_content(
    "Find papers on econophysics",
    tool_config=tool_definition
)
```

---

## Anthropic API

### Direct Integration

```python
from anthropic import Anthropic

client = Anthropic()

# If MCP configured in ~/.claude/settings.json
# MCP resources are accessible via API

response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1024,
    messages=[
        {
            "role": "user",
            "content": "Search for econophysics papers using paper search"
        }
    ]
    # MCP tools automatically available
)

print(response.content)
```

---

## HTTP Server Bridge

### Setup & Run

**Installation:**
```bash
cd learn/paper-search-mcp
pip install fastapi uvicorn requests feedparser
```

**Run Server:**
```bash
# Terminal 1: Start server
python mcp_http_server.py --port 8000

# Terminal 2: Test it
curl "http://127.0.0.1:8000/search?query=econophysics&limit=5"
```

**Available Endpoints:**

| Endpoint | Description | Example |
|----------|-------------|---------|
| `/` | API info | `http://localhost:8000/` |
| `/health` | Health check | `http://localhost:8000/health` |
| `/search` | General search | `/search?query=bitcoin&limit=10` |
| `/econophysics` | Econ papers | `/econophysics?query=power+law&limit=5` |
| `/finance` | Finance papers | `/finance?query=trading&limit=10` |
| `/crypto` | Crypto papers | `/crypto?query=smart+contracts&limit=5` |
| `/ai` | AI/ML papers | `/ai?query=neural+networks&limit=10` |
| `/categories` | List categories | `http://localhost:8000/categories` |
| `/batch-search` | Multiple queries | POST request |
| `/docs` | API documentation | `http://localhost:8000/docs` |

**Example Requests:**

```bash
# Basic search
curl "http://127.0.0.1:8000/search?query=machine%20learning&limit=5"

# With category
curl "http://127.0.0.1:8000/search?query=volatility&category=q-fin&limit=10"

# Batch search
curl -X POST http://127.0.0.1:8000/batch-search \
  -H "Content-Type: application/json" \
  -d '[
    {"query": "econophysics", "limit": 5},
    {"query": "bitcoin trading", "limit": 3}
  ]'
```

---

## Panduan Per AI Tool

### 1. ChatGPT (Free / Plus)
**Cara**: Custom GPT dengan HTTP bridge
**Difficulty**: ⭐⭐⭐ (Medium)
**Setup time**: 10-15 minutes
**Best for**: General paper search queries

**Steps**:
1. Run HTTP server: `python mcp_http_server.py --port 8000`
2. Create Custom GPT (lihat section ChatGPT di atas)
3. Add OpenAPI schema
4. Test dengan: "Find econophysics papers"

---

### 2. Claude (Web / Desktop / API)
**Cara**: Native MCP (sudah setup)
**Difficulty**: ⭐ (Easy)
**Setup time**: 0 minutes
**Best for**: Best integration, fastest

**Steps**:
```bash
# Just use Claude normally
# In chat: @arxiv search "econophysics"
# Or: @paper-search-mcp search papers
```

---

### 3. Google Gemini
**Cara**: Custom tools + HTTP bridge
**Difficulty**: ⭐⭐⭐⭐ (Hard)
**Setup time**: 20-30 minutes
**Best for**: Multi-modal research

**Steps**:
1. Run HTTP server
2. Create Gemini API key
3. Define custom tools (lihat code di atas)
4. Use in Gemini interface

---

### 4. Open-source (Llama, Mistral, etc)
**Cara**: Local MCP server + HTTP bridge
**Difficulty**: ⭐⭐⭐⭐⭐ (Very Hard)
**Setup time**: 1-2 hours
**Best for**: Full control, privacy

**Basic setup**:
```bash
# 1. Run MCP server
python mcp_http_server.py --port 8000

# 2. Run local LLM (e.g., Ollama)
ollama run mistral

# 3. Create wrapper script to call HTTP server
# (Custom integration needed)
```

---

## Rekomendasi Setup Optimal

### Untuk Berbagai Use Case:

**Use Case 1: Cepat & Mudah**
```
→ Claude Code (VSCode) + built-in MCP
✅ No setup needed, works immediately
```

**Use Case 2: ChatGPT Power User**
```
→ ChatGPT Custom GPT + HTTP bridge
1. python mcp_http_server.py --port 8000
2. Create Custom GPT (5 minutes)
```

**Use Case 3: Multi-AI Access**
```
→ HTTP Bridge + multiple tools
1. python mcp_http_server.py --port 8000
2. Use from ChatGPT, Gemini, Postman, curl, etc
```

**Use Case 4: Maximum Privacy/Control**
```
→ Local LLM + local MCP
1. Run Ollama locally
2. Run HTTP server
3. Create local integration (custom)
```

---

## Troubleshooting

### "Connection refused" / "localhost:8000"
**Solution**: 
```bash
# Ensure HTTP server is running
python mcp_http_server.py --port 8000

# In another terminal, test:
curl http://127.0.0.1:8000/health
```

### ChatGPT says "API not found"
**Solution**:
1. Ensure `http://127.0.0.1:8000` is correct
2. Test in browser: `http://127.0.0.1:8000/docs`
3. Firewall: Ensure port 8000 is not blocked

### "No papers found"
**Solution**:
1. Check arXiv is accessible: `curl http://export.arxiv.org/api/query?search_query=test`
2. Try simpler query: "bitcoin" instead of "quantum econophysics"
3. Wait 3 seconds between requests (rate limiting)

### Gemini integration not working
**Solution**:
1. Verify API key: `export GOOGLE_API_KEY=your_key`
2. Test endpoint separately
3. Check network connectivity

---

## File Structure

```
learn/
├── arxiv-mcp-server/
│   ├── arxiv_simple.py          (Direct ArXiv search)
│   └── econophysics_search.py    (Specialized search)
│
├── paper-search-mcp/
│   ├── mcp_http_server.py        (HTTP bridge for all AI)
│   ├── econophysics_search.py    (Econophysics focus)
│   └── ... (other MCP files)
│
└── MCP_WITH_OTHER_AI.md          (This file)
```

---

## Quick Reference

### Commands to Remember

```bash
# Terminal 1: Start HTTP server
cd learn/paper-search-mcp
python mcp_http_server.py --port 8000

# Terminal 2: Test it
curl "http://127.0.0.1:8000/search?query=econophysics&limit=5"

# Or use in any AI tool
# ChatGPT: Add custom action pointing to http://127.0.0.1:8000
# Gemini: Use tools with endpoint
# Claude: Use native MCP (no setup needed)
```

### Endpoints Quick List

```
Health:       GET  /health
Search:       GET  /search?query=...&limit=10
Econophysics: GET  /econophysics?query=...
Finance:      GET  /finance?query=...
Crypto:       GET  /crypto?query=...
AI/ML:        GET  /ai?query=...
Categories:   GET  /categories
Batch:        POST /batch-search
Docs:         GET  /docs (OpenAPI)
```

---

## Next Steps

1. **For Claude users**: Already setup, just use it
2. **For ChatGPT users**: Run HTTP server + create Custom GPT
3. **For Gemini users**: Run HTTP server + setup tools
4. **For others**: Use HTTP bridge endpoint directly

---

**All tools ready to use!** 🚀

Choose your AI, follow the setup, and start searching papers!
