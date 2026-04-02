# Quick References

Fast lookup documentation for common tasks and questions.

---

## Files in This Folder

### 📋 INDEX.md
**Master file index - Find anything quickly**

- Complete file listing
- Purpose of each file
- Quick links by use case
- Search tips

**Use when**: "Where is that file?"

---

### 📁 FOLDER_STRUCTURE.md
**Complete project organization**

- Root level structure
- Subfolder contents
- File categories and purposes
- Navigation guide

**Use when**: "How is this organized?"

---

### ⚡ QUICK_REFERENCE.md
**Most common commands and links**

- Trading commands
- Paper search queries
- AI integration commands
- Testing procedures

**Use when**: "What's the command for X?"

---

## One-Page Quick Lookup

### Most Important Files

| File | What it is | Read time |
|------|-----------|-----------|
| **README.md** | Project overview | 5 min |
| **START_HERE.md** | Entry point | 5 min |
| **CRYPTO_RELEVANCE_ANALYSIS_2026.md** | Key research | 45 min |
| **ECONOPHYSICS_PAPERS.md** | 5 papers found | 10 min |
| **MCP_WITH_OTHER_AI.md** | AI integration | 15 min |

**Total time to understand everything**: ~80 min

---

### Most Used Commands

```bash
# Test connection
python backend/scripts/test_lighter_connection.py

# Run tests
pytest backend/tests/ -v

# Search papers (CLI)
cd learn/arxiv-mcp-server
python arxiv_simple.py search --query "bitcoin" --limit 10

# Search papers (HTTP)
cd learn/paper-search-mcp
python mcp_http_server.py --port 8000
# curl "http://127.0.0.1:8000/search?query=econophysics"

# Use in Claude
@arxiv search "topic"
@paper-search-mcp search papers
```

---

### By Role

**I'm a Trader**
→ READ: README.md, TRADING_GUIDE.md  
→ DO: Test connection, trade with safety checks

**I'm a Researcher**
→ READ: CRYPTO_RELEVANCE_ANALYSIS_2026.md, ECONOPHYSICS_PAPERS.md  
→ DO: Search papers, analyze findings

**I'm a Developer**
→ READ: FOLDER_STRUCTURE.md, backend/ code  
→ DO: Review implementation, run tests

**I'm New Here**
→ READ: START_HERE.md, README.md, FOLDER_STRUCTURE.md  
→ DO: Understand the project first

---

## Search Tips

### Finding a Specific File
1. Use **INDEX.md** - complete file listing
2. Use **FOLDER_STRUCTURE.md** - organized by category
3. Use **Ctrl+F** - search within markdown

### Finding Information About a Topic
1. Check **START_HERE.md** - quick navigation
2. Read appropriate guide in `../guides/`
3. Search **INDEX.md** for keywords

### Finding How to Do Something
1. Check **QUICK_REFERENCE.md** - commands
2. Read **TRADING_GUIDE.md**, **PAPER_SEARCH_GUIDE.md**, etc
3. See **FOLDER_STRUCTURE.md** - "How to Navigate" section

---

## Navigation Matrix

| I want to... | Read this | Time |
|--------------|-----------|------|
| Understand the project | README.md | 5 min |
| Get started quickly | START_HERE.md | 10 min |
| Learn file organization | FOLDER_STRUCTURE.md | 5 min |
| Find a specific file | INDEX.md | 2 min |
| Find a command | QUICK_REFERENCE.md | 1 min |
| Research crypto methods | CRYPTO_RELEVANCE_ANALYSIS_2026.md | 45 min |
| Find econophysics papers | ECONOPHYSICS_PAPERS.md | 10 min |
| Setup paper search | ../setup/ARXIV_SETUP_SUMMARY.md | 15 min |
| Use ChatGPT/Gemini | ../integration/MCP_WITH_OTHER_AI.md | 15 min |
| Start trading | ../guides/TRADING_GUIDE.md | 15 min |
| Search papers | ../guides/PAPER_SEARCH_GUIDE.md | 10 min |

---

## File Organization

```
reference/
├── README.md ← You are here
├── INDEX.md ← Master file index
├── FOLDER_STRUCTURE.md ← Project organization
└── QUICK_REFERENCE.md ← Common commands
```

---

## Bookmarks to Keep

Add these to your browser/editor bookmarks for fast access:

- **Project Start**: `docs/START_HERE.md`
- **Quick Commands**: `docs/reference/QUICK_REFERENCE.md`
- **Paper Research**: `docs/research/CRYPTO_RELEVANCE_ANALYSIS_2026.md`
- **File Finding**: `docs/reference/INDEX.md`
- **AI Integration**: `docs/integration/MCP_WITH_OTHER_AI.md`

---

## Common Questions Answered

**Q: Where do I start?**  
A: → `START_HERE.md` (this folder's parent)

**Q: How do I trade?**  
A: → `../guides/TRADING_GUIDE.md`

**Q: How do I search papers?**  
A: → `../guides/PAPER_SEARCH_GUIDE.md`

**Q: What are the key findings?**  
A: → `../research/CRYPTO_RELEVANCE_ANALYSIS_2026.md`

**Q: Where is [specific file]?**  
A: → `INDEX.md` (this folder)

**Q: How is everything organized?**  
A: → `FOLDER_STRUCTURE.md` (this folder)

---

## Key Stats

- 📄 **Files**: 15+ documentation files
- 📚 **Research**: 45+ pages analysis
- 🧪 **Tests**: 133 passing tests
- 💻 **Code**: 3000+ lines backend
- 📄 **Papers**: 5 econophysics papers found
- 🛠️ **Tools**: 2 MCP servers + HTTP API

---

## Next Steps

1. **Bookmark** `QUICK_REFERENCE.md`
2. **Keep** `INDEX.md` open when exploring
3. **Refer to** `FOLDER_STRUCTURE.md` when lost
4. **Navigate** using appropriate guides

---

**Status**: ✅ Reference complete  
**Last Updated**: April 2, 2026  
**Purpose**: Fast lookup for common questions
