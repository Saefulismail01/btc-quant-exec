# Phase 2: Publishing to PyPI - Quick Guide

**Estimated Time**: 2-3 hours  
**Status**: Ready to start  
**Location**: `/c/Users/ThinkPad/Documents/paper-search-lib/`

---

## What Needs to Happen

### 1. Add More Connectors (1.5-2 hours)

Currently only ArXiv is implemented. Add these key sources:

#### PubMed Connector
- Source: `learn/paper-search-mcp/paper_search_mcp/academic_platforms/pubmed.py`
- Create: `src/paper_search/connectors/pubmed.py`
- Time: 20 minutes

#### Semantic Scholar
- Source: `learn/paper-search-mcp/paper_search_mcp/academic_platforms/semantic.py`
- Create: `src/paper_search/connectors/semantic_scholar.py`
- Time: 20 minutes

#### Google Scholar (Optional)
- Source: `learn/paper-search-mcp/paper_search_mcp/academic_platforms/google_scholar.py`
- Create: `src/paper_search/connectors/google_scholar.py`
- Time: 15 minutes

### 2. Write Tests (30 mins - 1 hour)

Each connector needs:
- `tests/test_pubmed.py`
- `tests/test_semantic_scholar.py`
- Basic: Does it return papers? Do they have required fields?

### 3. Documentation (30 mins)

Create in `/docs/`:
- `API_REFERENCE.md` - Class documentation
- `SOURCES.md` - List of sources and their features
- `EXAMPLES.md` - More usage examples
- `TROUBLESHOOTING.md` - Common issues

### 4. Publish to PyPI (30 mins)

```bash
# Install build tools
pip install build twine

# Build distribution
cd /c/Users/ThinkPad/Documents/paper-search-lib
python -m build

# Upload to PyPI (requires account)
python -m twine upload dist/*
```

---

## How to Add a Connector

### Step 1: Extract from paper-search-mcp

```bash
# Copy the connector implementation
cp learn/paper-search-mcp/paper_search_mcp/academic_platforms/pubmed.py \
   /c/Users/ThinkPad/Documents/paper-search-lib/src/paper_search/connectors/pubmed.py
```

### Step 2: Update Imports

Change from:
```python
from ..paper import Paper
from .base import PaperSource
```

To:
```python
from ..models import Paper
from ..base import PaperConnector
```

### Step 3: Update Class

Change from:
```python
class PubmedSearcher(PaperSource):
```

To:
```python
class PubmedConnector(PaperConnector):
```

### Step 4: Implement get_source_name()

Add method:
```python
def get_source_name(self) -> str:
    return 'pubmed'
```

### Step 5: Register in __init__.py

In `src/paper_search/connectors/__init__.py`:
```python
from .arxiv import ArxivConnector
from .pubmed import PubmedConnector
from .semantic_scholar import SemanticScholarConnector

__all__ = ['ArxivConnector', 'PubmedConnector', 'SemanticScholarConnector']
```

### Step 6: Test It

```python
from paper_search import PaperSearch
from paper_search.connectors import PubmedConnector

searcher = PaperSearch(connectors=[PubmedConnector()])
papers = searcher.search("machine learning", max_results=5)
print(f"Found {len(papers)} papers")
```

---

## Publishing to PyPI

### Before Publishing

```bash
# Build distribution
python -m build

# Check build output
ls -la dist/

# Should have:
# - paper-search-lib-1.0.0.tar.gz
# - paper-search-lib-1.0.0-py3-none-any.whl
```

### Creating PyPI Account

1. Go to https://pypi.org/account/register/
2. Create account
3. Create API token (Settings → API tokens)
4. Create `~/.pypirc`:

```ini
[distutils]
index-servers =
    pypi

[pypi]
repository = https://upload.pypi.org/legacy/
username = __token__
password = pypi_YOUR_TOKEN_HERE
```

### Upload to PyPI

```bash
# Check configuration
twine check dist/*

# Upload
twine upload dist/*

# Verify (should be available in ~5 minutes)
pip install paper-search-lib==1.0.0
```

---

## Using in BTC-QUANT After Publishing

Once published, update `btc-scalping-execution_layer`:

### 1. Update requirements.txt

```
# Remove old
# -e ../paper-search-lib/

# Add new
paper-search-lib>=1.0.0
```

### 2. Update imports

In code where `learn/arxiv-mcp-server/` or `learn/paper-search-mcp/` are used:

```python
# OLD
from arxiv_mcp.api import search_papers

# NEW
from paper_search import PaperSearch, RobustSearch
from paper_search.connectors import ArxivConnector, PubmedConnector

# OLD
results = search_papers("query")

# NEW
searcher = RobustSearch(connectors=[ArxivConnector()])
results = searcher.search("query", max_results=20)
```

### 3. Remove embedded code

```bash
rm -rf learn/arxiv-mcp-server/
rm -rf learn/paper-search-mcp/
```

---

## Minimal Version for Phase 2

If short on time, minimum viable:

1. **Publish ArXiv-only version** (just add documentation)
   - Time: 30 minutes
   - Version: 1.0.0-arxiv
   - Can add more sources later

2. **Later: Add connectors in v1.1.0, v1.2.0, etc**
   - Each source in separate minor version
   - Users can upgrade gradually

---

## Quick Checklist for Phase 2

- [ ] Add 2-3 connectors (or skip for v1.0.0)
- [ ] Write unit tests for each connector
- [ ] Test with `pip install -e .` locally
- [ ] Create documentation files
- [ ] Update version in setup.py to 1.0.0
- [ ] Create GitHub account and repo (optional)
- [ ] Create PyPI account
- [ ] Build distribution
- [ ] Upload to PyPI
- [ ] Test: `pip install paper-search-lib`
- [ ] Verify import works: `from paper_search import PaperSearch`

---

## Timeline Options

### Fast Track (45 mins - publish immediately)
- Use ArXiv only
- Publish as v1.0.0
- Add more sources in later releases

### Standard Track (2-3 hours - complete Phase 2)
- Add 2-3 connectors
- Write tests
- Create documentation
- Publish as v1.0.0

### Complete Track (4-5 hours - full Phase 2)
- Add 5-6 connectors
- Comprehensive tests
- Complete documentation
- GitHub repo setup
- Publish as v1.0.0

---

## Key Files Locations

**Library**: `/c/Users/ThinkPad/Documents/paper-search-lib/`
- Source code: `src/paper_search/`
- Tests: `tests/`
- Examples: `examples/`
- Config: `setup.py`, `README.md`

**Current Project**: `c:\Users\ThinkPad\Documents\Windsurf\btc-scalping-execution_layer\`
- Will import from: `pip install paper-search-lib`

**Paper-Search-MCP** (reference for more connectors):
- `learn/paper-search-mcp/paper_search_mcp/academic_platforms/`

---

## Recommendation

### Option A: Fast Track (Recommended for now)
- Publish v1.0.0 with ArXiv connector today
- Use it in BTC-QUANT immediately
- Add more sources in v1.1.0 next week

### Option B: Complete Track
- Spend 3 hours adding more connectors
- Publish comprehensive v1.0.0
- All sources ready from day 1

I recommend **Option A**: Get v1.0.0 out quickly, then iterate.

---

**Status**: Phase 1 Complete, Ready for Phase 2 ✅  
**Next Action**: Choose Option A or B above
