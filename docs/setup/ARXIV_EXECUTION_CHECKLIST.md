# ArXiv MCP Setup — Execution Checklist

Use this checklist to complete the setup step-by-step.

---

## PHASE 1: PRE-SETUP VERIFICATION (5 minutes)

- [ ] **Check Python installed**
  ```bash
  python --version
  ```
  Expected: `Python 3.9.x` or higher
  
  If missing: Download from https://www.python.org/downloads/

- [ ] **Check Git installed**
  ```bash
  git --version
  ```
  Expected: `git version 2.x.x`
  
  If missing: Download from https://git-scm.com/download/win

- [ ] **Check disk space**
  - Need ~500MB free space
  - Run: `disk usage` or `dir C:` to check

- [ ] **Read ARXIV_SETUP_SUMMARY.md**
  - Understand what's being installed
  - Know what MCP is

---

## PHASE 2: RUN SETUP SCRIPT (2 minutes)

### Option A: Windows (Easiest)

- [ ] Navigate to folder
  ```bash
  cd C:\Users\ThinkPad\Documents\Windsurf\btc-scalping-execution_layer
  ```

- [ ] Run setup script
  ```bash
  ARXIV_SETUP.bat
  ```
  
  Watch for these messages:
  - ✅ `OK: Python 3.x.x found`
  - ✅ `OK: Poetry already installed` or `Installing Poetry...`
  - ✅ `OK: Repository cloned`
  - ✅ `OK: Dependencies installed`
  - ✅ `OK: Cache directory created`

- [ ] When complete, press any key to close

### Option B: Linux/macOS/WSL2

- [ ] Navigate to folder
  ```bash
  cd ~/Documents/Windsurf/btc-scalping-execution_layer
  ```

- [ ] Run setup script
  ```bash
  bash ARXIV_SETUP.sh
  ```

- [ ] Watch for ✅ marks (same as Windows)

---

## PHASE 3: VERIFY INSTALLATION (3 minutes)

- [ ] Open new terminal window

- [ ] Navigate to arxiv-mcp-server
  ```bash
  cd learn/arxiv-mcp-server
  ```

- [ ] Run test search
  ```bash
  poetry run arxiv-mcp search --query "bitcoin" --limit 3
  ```

- [ ] Verify output
  - [ ] JSON array appears
  - [ ] Contains 3 paper entries
  - [ ] Each has `id`, `title`, `authors`, `published`, `summary`

**Example output**:
```json
[
  {
    "id": "2401.12345",
    "title": "Bitcoin Market Microstructure...",
    "authors": ["Alice", "Bob"],
    "published": "2024-01-15",
    "summary": "..."
  },
  ...
]
```

- [ ] No errors in output

---

## PHASE 4: CLAUDE CODE INTEGRATION (2 minutes)

- [ ] **Close Claude Code completely**
  - Close all windows
  - Kill process if needed

- [ ] **Restart Claude Code**
  - Open application fresh
  - Wait for it to fully load

- [ ] **Verify MCP server is listed**
  - Press `Ctrl+Shift+P` (Command Palette)
  - Type: `MCP Resources`
  - Look for `arxiv-mcp-server` in the list
  
  If found: ✅ Setup successful!
  If NOT found: 
  - [ ] Check `~/.claude/settings.json` manually
  - [ ] Verify JSON syntax is valid
  - [ ] Restart Claude Code again

---

## PHASE 5: FIRST RESEARCH QUERY (3 minutes)

**Option A: From Terminal**

- [ ] Open terminal in btc-scalping-execution_layer folder
  ```bash
  cd learn/arxiv-mcp-server
  ```

- [ ] Search for HMM papers
  ```bash
  poetry run arxiv-mcp search --query "Hidden Markov Models" --limit 10
  ```

- [ ] Verify: You get 10 papers with metadata

**Option B: From Claude Code Chat** (if MCP integrated)

- [ ] Open chat in Claude Code
- [ ] Type:
  ```
  @arxiv search "Hidden Markov Models" limit:10
  ```

- [ ] Verify: Response shows papers found

---

## PHASE 6: TEST EXPORT (2 minutes)

- [ ] Export to BibTeX format
  ```bash
  cd learn/arxiv-mcp-server
  poetry run arxiv-mcp export \
    --format bibtex \
    --query "regime switching" \
    --limit 5 \
    --output test_papers.bib
  ```

- [ ] Verify file created
  ```bash
  ls test_papers.bib    # Linux/macOS
  dir test_papers.bib   # Windows
  ```

- [ ] Check file contains BibTeX entries
  ```bash
  cat test_papers.bib   # View contents
  ```

---

## PHASE 7: SETUP FOR DAILY USE (5 minutes)

### Create research directory
```bash
mkdir research
cd research
```

### Save research queries file
Create `research_queries.txt`:
```
Hidden Markov Models cryptocurrency
statistical arbitrage bitcoin
regime detection trading
Kelly criterion position sizing
on-chain analysis bitcoin
machine learning crypto
```

### Schedule daily paper sync
```bash
# Option 1: Using Claude Code /schedule skill
/schedule 0 9 * * * poetry run arxiv-mcp search "bitcoin trading" --limit 10

# Option 2: Or manually run periodically
poetry run arxiv-mcp search "bitcoin trading" --limit 10 --output "research/papers_$(date +%Y%m%d).json"
```

---

## FINAL CHECKLIST ✅

Before considering setup complete, verify ALL of these:

- [ ] Python 3.9+ installed and working
- [ ] Repository cloned to `learn/arxiv-mcp-server`
- [ ] Dependencies installed (Poetry)
- [ ] Cache directory created at `~/.arxiv-cache`
- [ ] `~/.claude/settings.json` updated with MCP config
- [ ] Claude Code restarted
- [ ] `arxiv-mcp-server` appears in MCP Resources
- [ ] Test search returns JSON papers
- [ ] Export to BibTeX works
- [ ] File created with paper references
- [ ] Research directory created
- [ ] First query executed successfully

**If all checked**: ✅ Setup complete and ready for daily use!

---

## TROUBLESHOOTING REFERENCE

| Problem | Solution | Check |
|---------|----------|-------|
| "Command not found: arxiv-mcp" | Run `poetry shell` first | Terminal |
| MCP server not in Claude Code | Restart Claude Code completely | Settings |
| "Failed to download from arXiv" | Check internet, increase timeout | Network |
| JSON parsing error | Ensure arXiv API is accessible | Connection |

For detailed help, see: `SETUP_ARXIV_MCP_SERVER.md` → Section 6 (Troubleshooting)

---

## TOTAL TIME ESTIMATE

| Phase | Time | Cumulative |
|-------|------|-----------|
| Pre-setup verification | 5 min | 5 min |
| Run setup script | 2 min | 7 min |
| Verify installation | 3 min | 10 min |
| Claude Code integration | 2 min | 12 min |
| First research query | 3 min | 15 min |
| Test export | 2 min | 17 min |
| Setup for daily use | 5 min | 22 min |

**Total: ~20 minutes** (assuming no issues)

---

## NEXT: DAILY RESEARCH WORKFLOW

Once setup complete, use these commands regularly:

```bash
cd learn/arxiv-mcp-server

# Daily search
poetry run arxiv-mcp search "bitcoin trading" --from 2024-01-01 --limit 20

# Weekly export
poetry run arxiv-mcp export \
  --format bibtex \
  --query "HMM OR regime switching" \
  --from 2024-01-01 \
  --output research_bibliography.bib

# Monthly full index
poetry run arxiv-mcp export \
  --format csv \
  --query "cryptocurrency" \
  --from 2024-01-01 \
  --output research_index_2026_q2.csv
```

---

## SUCCESS INDICATOR

You'll know setup worked when:

✅ Run this command:
```bash
poetry run arxiv-mcp search --query "test" --limit 1
```

✅ Get this output:
```json
[
  {
    "id": "2401.xxxxx",
    "title": "...",
    "authors": [...],
    "published": "2024-...",
    "summary": "..."
  }
]
```

✅ No errors, just clean JSON with papers

**When you see this: You're done!** 🎉

---

**Document**: Execution Checklist v1.0  
**Created**: April 2, 2026  
**Purpose**: Step-by-step verification of arXiv MCP setup
