# Reusable Library Architecture for Paper Search

**Problem**: Want to use paper search tools across multiple projects, not just BTC-QUANT.  
**Solution**: Extract to standalone library instead of embedding in each project.

---

## Current Problem: Embedded Approach ❌

```
btc-scalping-execution_layer/
├── learn/
│   ├── arxiv-mcp-server/          ← Embedded
│   ├── paper-search-mcp/          ← Embedded

Project 2 (Different Codebase)
├── learn/
│   ├── arxiv-mcp-server/          ← Copy-paste?
│   ├── paper-search-mcp/          ← Copy-paste?

Project 3 (Another Codebase)
├── learn/
│   ├── arxiv-mcp-server/          ← Copy-paste again?
│   └── paper-search-mcp/          ← Copy-paste again?
```

**Issues**:
- Code duplication across projects
- Hard to maintain (bug fix = fix everywhere)
- Version management nightmare
- Not professional/scalable

---

## Better Solution: Standalone Library ✅

### Architecture

```
GitHub Organization:
├── paper-search-lib/                    ← CORE LIBRARY (reusable)
│   ├── src/paper_search/
│   │   ├── __init__.py
│   │   ├── base.py                     # Abstract base
│   │   ├── arxiv_connector.py
│   │   ├── pubmed_connector.py
│   │   ├── semantic_scholar.py
│   │   ├── multi_source_search.py
│   │   ├── robust_search.py            # Error handling + retry
│   │   ├── pdf_downloader.py           # Fallback chain
│   │   └── models.py                   # Data classes
│   │
│   ├── tests/
│   │   ├── test_arxiv.py
│   │   ├── test_pubmed.py
│   │   ├── test_robust_search.py
│   │   └── test_integration.py
│   │
│   ├── docs/
│   │   ├── README.md
│   │   ├── API_REFERENCE.md
│   │   ├── SOURCES.md
│   │   └── EXAMPLES.md
│   │
│   ├── setup.py                        # PyPI package
│   ├── requirements.txt
│   └── LICENSE
│
├── btc-scalping-execution_layer/       ← PROJECT 1
│   ├── backend/
│   ├── requirements.txt
│   │   └── paper-search-lib>=1.0.0
│   └── (import from library)
│
├── cryptocurrency-analysis/             ← PROJECT 2
│   ├── src/
│   ├── requirements.txt
│   │   └── paper-search-lib>=1.0.0
│   └── (import from library)
│
└── research-platform/                   ← PROJECT 3
    ├── api/
    ├── requirements.txt
    │   └── paper-search-lib>=1.0.0
    └── (import from library)
```

---

## Setup.py Example

```python
from setuptools import setup, find_packages

setup(
    name='paper-search-lib',
    version='1.0.0',
    author='Your Name',
    description='Unified paper search across 20+ academic sources',
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    python_requires='>=3.9',
    install_requires=[
        'requests>=2.28.0',
        'pydantic>=2.0.0',
        'httpx>=0.24.0',
        'feedparser>=6.0.0',
    ],
    extras_require={
        'pdf': ['pdf2image>=1.16.0', 'pdfminer>=20221105'],
        'dev': ['pytest>=7.0', 'pytest-cov>=4.0', 'black>=23.0'],
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
    ],
)
```

---

## Clean API Design

### Simple Usage

```python
from paper_search import PaperSearch

# Create searcher
searcher = PaperSearch(sources=['arxiv', 'pubmed'])

# Search
papers = searcher.search("machine learning", limit=10)

# Iterate results
for paper in papers:
    print(f"{paper.title}")
    print(f"Authors: {paper.authors}")
    print(f"URL: {paper.url}")
```

### Robust Search (with error handling)

```python
from paper_search import RobustSearch

# Create robust searcher
robust = RobustSearch(
    sources=['arxiv', 'semantic_scholar', 'pubmed'],
    timeout=90,
    retry_count=3,
    min_delay=10
)

# Search with automatic retries + fallbacks
papers = robust.search("bitcoin prediction", limit=20)
```

### Multi-Source with Fallback

```python
from paper_search import PaperSearch, PDFDownloader

searcher = PaperSearch(sources='all')
papers = searcher.search("AI", limit=50)

downloader = PDFDownloader()
for paper in papers:
    # Tries multiple fallback sources for PDF
    pdf_path = downloader.download_with_fallback(paper)
    if pdf_path:
        print(f"Downloaded: {pdf_path}")
```

---

## Usage in Different Projects

### Project 1: BTC-QUANT

```python
# requirements.txt
paper-search-lib>=1.0.0

# In your code
from paper_search import PaperSearch
searcher = PaperSearch(sources=['arxiv', 'semantic_scholar'])
papers = searcher.search("econophysics regime switching", limit=10)
```

### Project 2: Cryptocurrency Analysis

```python
# requirements.txt
paper-search-lib>=1.0.0

# In your code
from paper_search import RobustSearch
searcher = RobustSearch(sources=['arxiv', 'pubmed', 'SSRN'])
papers = searcher.search("blockchain security", limit=20)
```

### Project 3: Research Platform

```python
# requirements.txt
paper-search-lib[pdf]>=1.0.0  # Include PDF extras

# In your code
from paper_search import PaperSearch, PDFDownloader
searcher = PaperSearch(sources='all')
papers = searcher.search("quantum computing")

downloader = PDFDownloader()
for paper in papers:
    downloader.download_with_fallback(paper)
```

---

## Distribution Options

### Option A: PyPI (Recommended) ⭐

```bash
# Publish
python setup.py sdist bdist_wheel
twine upload dist/*

# Usage in any project
pip install paper-search-lib
```

**Advantages**:
- Professional versioning
- Easy updates
- Works with any Python project
- Can be private or public

### Option B: GitHub Package Registry

```bash
# For private/internal use
pip install git+https://github.com/yourusername/paper-search-lib.git
```

### Option C: Git Submodule

```bash
# For monorepo or tight coupling
git submodule add https://github.com/yourusername/paper-search-lib.git
pip install -e ./paper-search-lib/
```

---

## Semantic Versioning

### Version Format: X.Y.Z

- **X (Major)**: Breaking changes
  - New connector interface
  - Removing sources
  - Example: 1.0.0 → 2.0.0

- **Y (Minor)**: New features (backward compatible)
  - New source connector
  - New error handling
  - Example: 1.0.0 → 1.1.0

- **Z (Patch)**: Bug fixes
  - Fix timeout issue
  - Fix parsing bug
  - Example: 1.0.0 → 1.0.1

### Requirements.txt Examples

```
# Specific version
paper-search-lib==1.0.0

# Minimum version
paper-search-lib>=1.0.0

# Compatible releases (recommended)
paper-search-lib~=1.0

# Latest
paper-search-lib
```

---

## Implementation Timeline

### Week 1: Extract to Library (2-3 hours)

1. Create new repo: `paper-search-lib`
2. Extract `src/paper_search/` module
3. Create `setup.py` for PyPI
4. Add comprehensive documentation
5. Write unit tests
6. Prepare for PyPI publishing

### Week 2: Deploy to PyPI (1-2 hours)

1. Publish first version (1.0.0)
2. Test in current project
3. Document usage patterns
4. Create quickstart guide

### Week 3: Refactor Projects (2-3 hours)

1. Update btc-scalping:
   - Remove `learn/arxiv-mcp-server/`
   - Remove `learn/paper-search-mcp/`
   - Add to `requirements.txt`
   - Update imports
   - Update documentation

2. Prepare for Project 2/3:
   - Have stable library ready
   - Clear documentation
   - Working examples

---

## Comparison: Embedded vs Library

| Aspect | Embedded | Library |
|--------|----------|---------|
| Code Reuse | Copy-paste ❌ | Import ✅ |
| Bug Fixes | Fix everywhere ❌ | One place ✅ |
| Version Control | Complex ❌ | Semantic ✅ |
| Maintenance | Nightmare ❌ | Easy ✅ |
| Scalability | Poor ❌ | Excellent ✅ |
| Professionalism | Amateur ❌ | Professional ✅ |
| Team Sharing | Hard ❌ | Easy ✅ |
| CI/CD Integration | Complex ❌ | Simple ✅ |

---

## Benefits of Library Approach

### 1. DRY (Don't Repeat Yourself)
- Write once, use everywhere
- No copy-paste duplication
- Single implementation

### 2. Maintainability
- Single source of truth
- Bug fixes apply everywhere
- Centralized updates
- Easier to test

### 3. Professional
- Industry standard approach
- Shows architectural maturity
- Easy for other developers
- Follows best practices

### 4. Scalability
- Works for 2 projects or 20
- Can add features without affecting projects
- Clear separation of concerns
- Independent development

### 5. Versioning
- Control which version each project uses
- Backward compatibility possible
- Gradual upgrades
- Rollback capability

### 6. Team Collaboration
- Easy for team members to use
- Shared improvements benefit all
- Clear documentation
- Single responsibility

---

## Recommendation

### Short Term (This Month)

1. **Extract to library now** (before Project 2/3)
   - Easier to refactor early
   - Better design from start
   - More professional

2. **Publish to PyPI**
   - Can be private if needed
   - Professional versioning
   - Easy to share with team

3. **Document thoroughly**
   - API reference
   - Usage examples
   - Troubleshooting guide
   - Architecture docs

### Medium Term (Next 1-2 Months)

1. **Version as 1.0.0**
   - Signal stability
   - Allow future semantic versioning
   - Professional milestone

2. **Use in current project first**
   - Test library quality
   - Find missing features
   - Refine before other projects

3. **Start Project 2/3**
   - Just import library
   - No code duplication
   - Professional setup

### Long Term

1. **Maintain version compatibility**
   - Semantic versioning
   - Backward compatibility
   - Clear changelog

2. **Add features**
   - New sources
   - Better error handling
   - Performance improvements

3. **Community**
   - Open source (if appropriate)
   - Accept contributions
   - Grow ecosystem

---

## Quick Implementation Checklist

- [ ] Create `paper-search-lib` repository
- [ ] Extract core code from embedded projects
- [ ] Write `setup.py` and `pyproject.toml`
- [ ] Create comprehensive documentation
- [ ] Write unit tests (>80% coverage)
- [ ] Create examples directory
- [ ] Test locally with current project
- [ ] Publish to PyPI (version 1.0.0)
- [ ] Update btc-scalping-execution_layer
- [ ] Remove embedded code from project
- [ ] Document usage in README
- [ ] Ready for Project 2/3

---

**Status**: Architecture designed ✅  
**Next Step**: Start extraction (2-3 hours of work)  
**Benefit**: Professional, scalable, maintainable solution for all current and future projects
