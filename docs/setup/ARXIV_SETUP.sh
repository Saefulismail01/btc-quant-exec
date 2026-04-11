#!/bin/bash
# ArXiv MCP Server Setup Script for Windows (WSL2 or Git Bash)
# Run: bash ARXIV_SETUP.sh

set -e  # Exit on error

echo "=========================================="
echo "ArXiv MCP Server Setup for Claude Code"
echo "=========================================="
echo ""

# Check Python
echo "[1/6] Checking Python installation..."
if ! command -v python &> /dev/null; then
    echo "❌ Python not found. Please install Python 3.9+ from https://www.python.org/downloads/"
    exit 1
fi
PYTHON_VERSION=$(python --version)
echo "✅ $PYTHON_VERSION found"
echo ""

# Check/Install Poetry
echo "[2/6] Setting up Poetry..."
if ! command -v poetry &> /dev/null; then
    echo "Installing Poetry..."
    pip install poetry --quiet
else
    echo "✅ Poetry already installed"
fi
echo ""

# Clone Repository
echo "[3/6] Cloning arxiv-mcp-server repository..."
REPO_PATH="./learn/arxiv-mcp-server"
if [ -d "$REPO_PATH" ]; then
    echo "⚠️  Repository already exists at $REPO_PATH"
    read -p "Overwrite? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$REPO_PATH"
        git clone https://github.com/1Dark134/arxiv-mcp-server.git "$REPO_PATH"
    fi
else
    git clone https://github.com/1Dark134/arxiv-mcp-server.git "$REPO_PATH"
fi
echo "✅ Repository cloned"
echo ""

# Install Dependencies
echo "[4/6] Installing dependencies with Poetry..."
cd "$REPO_PATH"
poetry install --quiet
echo "✅ Dependencies installed"
echo ""

# Create Cache Directory
echo "[5/6] Creating cache directory..."
CACHE_DIR="$HOME/.arxiv-cache"
mkdir -p "$CACHE_DIR"
echo "✅ Cache directory created at $CACHE_DIR"
echo ""

# Update Claude Code Settings
echo "[6/6] Updating Claude Code settings..."
SETTINGS_FILE="$HOME/.claude/settings.json"
mkdir -p "$HOME/.claude"

# Create settings.json if doesn't exist
if [ ! -f "$SETTINGS_FILE" ]; then
    cat > "$SETTINGS_FILE" << 'EOF'
{
  "mcpServers": {
    "arxiv-mcp-server": {
      "command": "python",
      "args": [
        "-m",
        "arxiv_mcp_server"
      ],
      "env": {
        "ARXIV_CACHE_DIR": "~/.arxiv-cache",
        "ARXIV_API_TIMEOUT": "30",
        "ARXIV_MAX_RESULTS": "100"
      }
    }
  }
}
EOF
    echo "✅ Created new settings.json"
else
    # Check if arxiv-mcp-server already exists
    if grep -q "arxiv-mcp-server" "$SETTINGS_FILE"; then
        echo "⚠️  arxiv-mcp-server already configured in settings.json"
    else
        echo "⚠️  settings.json exists but needs manual update"
        echo "Add this to your ~/.claude/settings.json under 'mcpServers':"
        echo ""
        cat << 'EOF'
    "arxiv-mcp-server": {
      "command": "python",
      "args": ["-m", "arxiv_mcp_server"],
      "env": {
        "ARXIV_CACHE_DIR": "~/.arxiv-cache",
        "ARXIV_API_TIMEOUT": "30",
        "ARXIV_MAX_RESULTS": "100"
      }
    }
EOF
    fi
fi
echo ""

# Verify Installation
echo "=========================================="
echo "Verification..."
echo "=========================================="
cd "$(git rev-parse --show-toplevel)/learn/arxiv-mcp-server"
poetry run python -m arxiv_mcp_server --help > /dev/null 2>&1 && echo "✅ MCP server executable verified" || echo "⚠️  Could not verify MCP server"
echo ""

echo "=========================================="
echo "Setup Complete! ✅"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Restart Claude Code (Cmd+Shift+P → Reload)"
echo "2. Check Settings → MCP Servers to verify arxiv-mcp-server is listed"
echo "3. Test with: poetry run arxiv-mcp search --query 'bitcoin' --limit 5"
echo ""
echo "Documentation: learn/riset_renaisance/SETUP_ARXIV_MCP_SERVER.md"
