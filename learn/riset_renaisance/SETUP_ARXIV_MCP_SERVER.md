# Setup ArXiv MCP Server untuk Claude Code

**Tujuan**: Menghubungkan Claude Code dengan arXiv journal untuk research otomatis langsung dari AI

**Platform**: Windows 11 (WSL2 recommended atau native Python)  
**Date**: April 2, 2026

---

## 1. PERSIAPAN AWAL

### Opsi A: Menggunakan WSL2 + Linux (RECOMMENDED)

**Kenapa recommended?**
- arXiv-mcp-server dioptimalkan untuk Linux/macOS
- Windows support masih experimental
- WSL2 memberikan environment Linux native di Windows 11

**Persyaratan**:
- Windows 11 Pro/Enterprise (WSL2 support)
- 10GB disk space untuk arXiv data cache
- 4GB RAM minimum

### Opsi B: Native Windows (Lebih Sederhana)

**Persyaratan**:
- Python 3.9+
- Git
- pip (Python package manager)

Kami akan gunakan **Opsi B (Native Windows)** karena lebih straightforward.

---

## 2. INSTALASI STEP-BY-STEP

### Step 1: Install Python (Jika Belum Ada)

Cek apakah Python sudah terinstall:

```bash
python --version
```

Jika belum, download dari https://www.python.org/downloads/ dan install.

**Penting**: Centang "Add Python to PATH" saat install.

---

### Step 2: Clone Repository

```bash
cd C:\Users\ThinkPad\Documents\Windsurf\btc-scalping-execution_layer
git clone https://github.com/1Dark134/arxiv-mcp-server.git
cd arxiv-mcp-server
```

---

### Step 3: Setup Poetry (Dependency Manager)

arXiv-mcp-server menggunakan Poetry untuk manage dependencies.

```bash
# Install Poetry
pip install poetry

# Navigate ke folder arxiv-mcp-server
cd arxiv-mcp-server

# Install dependencies
poetry install
```

**Output yang diharapkan**:
```
Installing dependencies from lock file
Creating virtualenv arxiv-mcp-server-xxxxx in C:\...\.venv
Installing collected packages: ...
Successfully installed arxiv-mcp-server
```

---

### Step 4: Konfigurasi MCP Server

**File yang perlu diedit**: `~/.claude/settings.json` atau create if doesn't exist

**Lokasi Windows**: `C:\Users\ThinkPad\.claude\settings.json`

**Tambahkan konfigurasi berikut**:

```json
{
  "mcpServers": {
    "arxiv-mcp-server": {
      "command": "python",
      "args": [
        "-m",
        "arxiv_mcp_server"
      ],
      "env": {
        "ARXIV_CACHE_DIR": "C:\\Users\\ThinkPad\\.arxiv-cache",
        "ARXIV_API_TIMEOUT": "30",
        "ARXIV_MAX_RESULTS": "100"
      }
    }
  }
}
```

**Penjelasan parameter**:
- `ARXIV_CACHE_DIR`: Folder untuk cache papers (akan dibuat otomatis)
- `ARXIV_API_TIMEOUT`: Timeout API call dalam detik
- `ARXIV_MAX_RESULTS`: Max hasil per query

---

### Step 5: Verifikasi Instalasi

Test apakah server berjalan:

```bash
# Test dari dalam virtual environment Poetry
poetry run python -m arxiv_mcp_server --version

# Atau jika ada CLI command
poetry run arxiv-mcp --help
```

**Expected output**: Versi server dan list available commands

---

## 3. INTEGRASI DENGAN CLAUDE CODE

### A. Via Settings.json (Automatic)

Jika sudah add ke `~/.claude/settings.json`, Claude Code akan auto-load MCP server saat startup.

**Verify dalam Claude Code**:
1. Buka Command Palette (`Ctrl+Shift+P`)
2. Search "MCP Resources" atau "List MCP"
3. Cek apakah `arxiv-mcp-server` listed

---

### B. Via Claude Code Desktop App (GUI)

Jika menggunakan Claude Code desktop:

1. **Settings** → **MCP Servers**
2. Click **+ Add MCP Server**
3. **Name**: `arxiv-mcp-server`
4. **Command**: `python`
5. **Arguments**: 
   ```
   -m
   arxiv_mcp_server
   ```
6. **Environment Variables**:
   ```
   ARXIV_CACHE_DIR=C:\Users\ThinkPad\.arxiv-cache
   ARXIV_API_TIMEOUT=30
   ```
7. Click **Save** → Server akan auto-start

---

### C. Via Web Interface (Optional)

Jika server mendukung web interface (verify di README):

```bash
poetry run arxiv-mcp-server --web --port 8080
```

Kemudian akses di `http://localhost:8080`

---

## 4. USAGE EXAMPLES

### Setelah Setup, Gunakan Commands Berikut:

**Dalam Claude Code terminal atau chat**:

#### Search untuk Papers

```bash
# Search papers tentang "Bitcoin trading algorithms"
arxiv-mcp search --query "Bitcoin trading algorithms" --limit 20

# Search dengan date filter
arxiv-mcp search --query "cryptocurrency" --from 2024-01-01 --limit 50

# Search dengan category filter
arxiv-mcp search --query "HMM" --category "cs.AI" --limit 30
```

#### Analyze Single Paper

```bash
# Analyze paper by arXiv ID
arxiv-mcp analyze --paper-id 2401.12345

# Get citations
arxiv-mcp analyze --paper-id 2401.12345 --citations
```

#### Export Results

```bash
# Export ke BibTeX
arxiv-mcp export --format bibtex --query "statistical arbitrage" --output papers.bib

# Export ke JSON
arxiv-mcp export --format json --ids 2401.12345,2401.54321 --output papers.json

# Export ke CSV
arxiv-mcp export --format csv --query "regime detection" --output papers.csv
```

---

## 5. INTEGRASI DENGAN RESEARCH WORKFLOW

### Opsi 1: Direct Query dari Claude Chat

**Dalam Claude Code chat, gunakan syntax**:

```
@arxiv search "Hidden Markov Models cryptocurrency" limit:20

@arxiv analyze paper:2401.12345 citations:true

@arxiv export format:bibtex query:"Kelly criterion" output:kelly_papers.bib
```

(Exact syntax tergantung implementasi server)

---

### Opsi 2: Scheduled Research Updates

**Menggunakan Claude Code `/loop` skill** untuk update papers harian:

```bash
/loop 1d @arxiv search "Bitcoin trading" limit:10 format:summary
```

Ini akan jalankan search setiap hari dan collect papers baru.

---

### Opsi 3: Automated Paper Indexing untuk BTC-QUANT

**Create script** `scripts/sync_arxiv_papers.py`:

```python
#!/usr/bin/env python3
"""
Sync latest arXiv papers relevant to BTC-QUANT
Run daily via Claude Code loop
"""

import subprocess
import json
from datetime import datetime

RESEARCH_TOPICS = [
    "Hidden Markov Models cryptocurrency",
    "statistical arbitrage bitcoin", 
    "regime detection trading",
    "machine learning crypto markets",
    "on-chain analysis BTC",
    "Kelly criterion position sizing"
]

def fetch_and_index_papers():
    for topic in RESEARCH_TOPICS:
        print(f"\n[{datetime.now().isoformat()}] Searching: {topic}")
        
        cmd = [
            "arxiv-mcp", "search",
            "--query", topic,
            "--limit", "10",
            "--from", "2024-01-01"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            papers = json.loads(result.stdout)
            print(f"Found {len(papers)} papers")
            
            # Save to local index
            with open(f"research/papers_{topic.replace(' ', '_')}.json", "w") as f:
                json.dump(papers, f, indent=2)
        else:
            print(f"Error: {result.stderr}")

if __name__ == "__main__":
    fetch_and_index_papers()
```

**Run dengan**:
```bash
/loop 1d python scripts/sync_arxiv_papers.py
```

---

## 6. TROUBLESHOOTING

### Issue 1: "arxiv-mcp command not found"

**Solution**:
```bash
# Make sure you're in Poetry virtualenv
poetry shell

# Then try command
arxiv-mcp --help
```

---

### Issue 2: "Failed to download arXiv metadata"

**Possible causes**:
- Network timeout (arXiv server slow)
- Cache directory not writable

**Solution**:
```bash
# Create cache directory manually
mkdir -p C:\Users\ThinkPad\.arxiv-cache

# Set environment variable
$env:ARXIV_CACHE_DIR = "C:\Users\ThinkPad\.arxiv-cache"
```

---

### Issue 3: "MCP Server not appearing in Claude Code"

**Solution**:
1. Check `~/.claude/settings.json` syntax (valid JSON)
2. Restart Claude Code completely
3. Check logs: View → Output → Claude Code logs

---

### Issue 4: "Port already in use" (if using web interface)

**Solution**:
```bash
# Use different port
poetry run arxiv-mcp-server --web --port 8081
```

---

## 7. ADVANCED: CUSTOM MCP RESOURCE

Jika ingin membuat custom resource untuk frequently searched topics:

**Create file** `~/.claude/mcp_resources.json`:

```json
{
  "arxiv_searches": {
    "btc_algo_trading": {
      "query": "bitcoin algorithmic trading machine learning",
      "limit": 20,
      "from": "2024-01-01",
      "refresh": "weekly"
    },
    "regime_switching": {
      "query": "regime switching models cryptocurrency",
      "limit": 15,
      "from": "2023-01-01",
      "refresh": "monthly"
    },
    "statistical_arbitrage": {
      "query": "statistical arbitrage cointegration crypto",
      "limit": 25,
      "from": "2024-01-01",
      "refresh": "weekly"
    }
  }
}
```

Kemudian di Claude Code, dapat directly reference:

```
@arxiv/btc_algo_trading

@arxiv/regime_switching
```

---

## 8. FINAL CHECKLIST

- [ ] Python 3.9+ installed and in PATH
- [ ] Repository cloned to `btc-scalping-execution_layer/arxiv-mcp-server`
- [ ] Poetry installed (`pip install poetry`)
- [ ] Dependencies installed (`poetry install`)
- [ ] `~/.claude/settings.json` updated with MCP config
- [ ] Cache directory created: `C:\Users\ThinkPad\.arxiv-cache`
- [ ] Test command runs: `poetry run arxiv-mcp --help`
- [ ] Claude Code shows arxiv-mcp-server in MCP Resources
- [ ] Sample search works: `arxiv-mcp search --query "test" --limit 5`

---

## 9. NEXT STEPS

Once setup complete:

1. **Start researching** your Renaissance algo relevance papers
   ```bash
   arxiv-mcp search "Hidden Markov Models financial markets" --limit 30
   ```

2. **Automate daily updates** of relevant papers
   ```bash
   /loop 1d arxiv-mcp search "machine learning crypto" --limit 10
   ```

3. **Build research index** for future reference
   ```bash
   arxiv-mcp export --format bibtex --query "regime detection" --output research.bib
   ```

4. **Integrate with backtesting** — Link papers to specific strategy components in code

---

**Setup Version**: 1.0  
**Last Updated**: April 2, 2026  
**Support**: github.com/1Dark134/arxiv-mcp-server/issues
