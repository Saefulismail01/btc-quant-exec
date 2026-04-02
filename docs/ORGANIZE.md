# Documentation Organization Plan

Reorganisasi file dokumentasi untuk struktur yang lebih clean.

---

## Current State
- **Root**: 10 markdown files (terlalu banyak)
- **learn/**: 2 README files di root (harusnya di parent docs)
- **No clear hierarchy** - Sulit navigasi

---

## Target Structure

```
btc-scalping-execution_layer/
├── docs/ (All documentation here!)
│   ├── README.md ← Navigation hub
│   │
│   ├── START_HERE.md ← Entry point (pindah dari root)
│   ├── OVERVIEW.md ← Project overview (dari README.md digabung)
│   │
│   ├── setup/ ← Setup & Installation
│   │   ├── README.md
│   │   ├── ARXIV_SETUP_SUMMARY.md
│   │   ├── ARXIV_EXECUTION_CHECKLIST.md
│   │   ├── ARXIV_QUICK_START.md
│   │   ├── ARXIV_README.md
│   │   ├── SETUP_COMPLETE.md
│   │   └── (scripts di learn/)
│   │
│   ├── integration/ ← AI Integration
│   │   ├── README.md
│   │   └── MCP_WITH_OTHER_AI.md
│   │
│   ├── research/ ← Research & Papers
│   │   ├── README.md
│   │   ├── CRYPTO_RELEVANCE_ANALYSIS_2026.md
│   │   └── ECONOPHYSICS_PAPERS.md
│   │
│   ├── guides/ ← Practical Guides
│   │   ├── README.md
│   │   ├── TRADING_GUIDE.md
│   │   ├── PAPER_SEARCH_GUIDE.md
│   │   └── AI_INTEGRATION_GUIDE.md
│   │
│   ├── reference/ ← Quick References
│   │   ├── README.md
│   │   ├── FOLDER_STRUCTURE.md
│   │   ├── INDEX.md
│   │   └── QUICK_REFERENCE.md
│   │
│   └── architecture/ ← System Design
│       ├── README.md
│       └── (future: detailed architecture docs)
│
├── learn/
│   ├── README.md ← Tools & Research guide
│   ├── MCP_WITH_OTHER_AI.md (→ docs/integration/)
│   ├── arxiv-mcp-server/
│   ├── paper-search-mcp/
│   └── riset_renaisance/
│
└── Root (CLEAN - hanya essentials!)
    ├── README.md (link to docs/)
    ├── .env
    ├── Dockerfile
    ├── requirements.txt
    └── (code folders)
```

---

## Migration Plan

### Phase 1: Create docs/ structure (Sekarang)
- ✓ Create subfolders
- ✓ Create README files per subfolder

### Phase 2: Move & Organize Files
Files to move ke docs/:
- START_HERE.md → docs/START_HERE.md
- ARXIV_* → docs/setup/
- ECONOPHYSICS_PAPERS.md → docs/research/
- CRYPTO_RELEVANCE_ANALYSIS_2026.md → docs/research/
- MCP_WITH_OTHER_AI.md → docs/integration/
- FOLDER_STRUCTURE.md → docs/reference/
- INDEX.md → docs/reference/
- SETUP_COMPLETE.md → docs/setup/
- ARXIV_QUICK_START.md → docs/setup/

Files to keep at root (only):
- README.md (simplified, link to docs/)
- .env
- Dockerfile
- requirements.txt
- Makefile (optional)

### Phase 3: Update Links
- Update all cross-references
- Update links in docs/README.md

---

## Benefits

✅ **Clear Organization**: Documentation grouped by purpose
✅ **Easy Navigation**: Subfolders with own README
✅ **Clean Root**: Only essentials at root level
✅ **Scalable**: Easy to add new docs in future
✅ **Professional**: Matches industry standards

---

## Execution Steps

1. Create folder structure ✓ (already done)
2. Create README per folder (next)
3. Copy/move files (next)
4. Update cross-references (after)
5. Update root README (after)
6. Delete old files from root (last)

---

Ready to proceed?
