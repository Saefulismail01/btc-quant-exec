# Paper Search Library - Phase 1 Execution Plan

**Date Started**: April 2, 2026  
**Target Completion**: April 4-5, 2026  
**Estimated Time**: 3-4 hours

---

## Phase 1: Extract to Library

### Step 1: Create Paper-Search-Lib Repository Structure ✅ IN PROGRESS

Create directory structure for standalone library:

```
paper-search-lib/
├── src/
│   └── paper_search/
│       ├── __init__.py              # Public API
│       ├── models.py                # Data classes (Paper, SearchResult)
│       ├── base.py                  # Abstract base connector
│       ├── connectors/
│       │   ├── __init__.py
│       │   ├── arxiv.py
│       │   ├── pubmed.py
│       │   ├── semantic_scholar.py
│       │   ├── google_scholar.py
│       │   └── base_search.py       # Common utilities
│       ├── search.py                # PaperSearch class
│       ├── robust_search.py         # RobustSearch with retry logic
│       ├── pdf_downloader.py        # Multi-source PDF download
│       └── utils.py                 # Helpers
│
├── tests/
│   ├── __init__.py
│   ├── test_arxiv.py
│   ├── test_pubmed.py
│   ├── test_robust_search.py
│   └── test_integration.py
│
├── examples/
│   ├── single_query.py
│   ├── multi_query.py
│   ├── with_pdf_download.py
│   └── custom_sources.py
│
├── docs/
│   ├── README.md                   # Main documentation
│   ├── API_REFERENCE.md
│   ├── SOURCES.md                  # Supported sources
│   ├── EXAMPLES.md
│   └── TROUBLESHOOTING.md
│
├── setup.py                         # PyPI package config
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
├── LICENSE
└── .gitignore
```

### Step 2: Extract Core Code from Existing Implementations

**Source 1: paper-search-mcp/**
- Extract `paper_search_mcp/academic_platforms/` → `src/paper_search/connectors/`
- Extract `paper_search_mcp/paper.py` → `src/paper_search/models.py`
- Extract `paper_search_mcp/utils.py` → `src/paper_search/utils.py`

**Source 2: arxiv-mcp-server/learn/**
- Extract `robust_arxiv_search.py` → `src/paper_search/robust_search.py`
- Use as reference for error handling patterns

**Source 3: Paper-search-mcp tests**
- Move tests to `tests/` folder
- Update imports to match new structure

### Step 3: Create Public API

**File: src/paper_search/__init__.py**

```python
from .search import PaperSearch
from .robust_search import RobustSearch
from .models import Paper, SearchResult

__all__ = ['PaperSearch', 'RobustSearch', 'Paper', 'SearchResult']
__version__ = '0.1.0'
```

### Step 4: Setup.py Configuration

**File: setup.py**

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
        'beautifulsoup4>=4.12.0',
        'lxml>=4.9.0',
    ],
    extras_require={
        'pdf': ['pdf2image>=1.16.0', 'pdfminer>=20221105'],
        'dev': ['pytest>=7.0', 'pytest-cov>=4.0', 'black>=23.0'],
    },
)
```

### Step 5: Documentation

**File: docs/README.md**
- Overview of library
- Quick start guide
- Feature list

**File: docs/API_REFERENCE.md**
- PaperSearch class
- RobustSearch class
- Available sources
- Error handling

**File: docs/EXAMPLES.md**
- Single query search
- Multiple query search
- PDF download with fallback
- Custom source configuration

### Step 6: Initial Testing

1. Import from library in test script
2. Run basic searches
3. Verify all connectors working
4. Check error handling

---

## Completion Criteria

- [ ] Directory structure created
- [ ] Core code extracted from paper-search-mcp
- [ ] Robust search code extracted from arxiv-mcp-server
- [ ] Public API defined in __init__.py
- [ ] setup.py configured
- [ ] Documentation written
- [ ] Tests passing
- [ ] Ready for Week 2 (publish to PyPI)

---

## Next Step

Once Phase 1 complete → Begin **Phase 2: Polish & Publish to PyPI**
- Add comprehensive unit tests
- Publish version 1.0.0
- Update current project to use library

**Estimated Start Date**: April 5, 2026
