#!/bin/bash
# VPS Sync Script - Synchronize VPS with GitHub repository
# Run this on VPS to get the cleaned structure

set -e  # Exit on error

REPO_URL="https://github.com/Saefulismail01/btc-quant-exec.git"
PROJECT_DIR="/opt/btc-quant"  # Adjust to your VPS path
BACKUP_DIR="/opt/btc-quant-backup-$(date +%Y%m%d-%H%M%S)"

echo "🚀 BTC-QUANT VPS Sync Starting..."
echo "=================================="

# 1. Backup current production
echo "📦 Creating backup..."
if [ -d "$PROJECT_DIR" ]; then
    sudo mkdir -p "$BACKUP_DIR"
    sudo cp -r "$PROJECT_DIR" "$BACKUP_DIR/"
    echo "✅ Backup created at: $BACKUP_DIR"
fi

# 2. Check if directory exists
if [ ! -d "$PROJECT_DIR" ]; then
    echo "📁 Project directory not found. Cloning fresh..."
    sudo mkdir -p "$PROJECT_DIR"
    sudo git clone "$REPO_URL" "$PROJECT_DIR"
    echo "✅ Fresh clone completed"
else
    # 3. Check what will change
    echo "🔍 Checking changes..."
    cd "$PROJECT_DIR"
    
    # Fetch latest
    sudo git fetch origin main
    
    # Check if production files will change
    CHANGES=$(sudo git diff --name-only HEAD origin/main)
    
    if echo "$CHANGES" | grep -q "^backend/"; then
        echo "🚫 WARNING: Production changes detected!"
        echo "Files that will change in backend/:"
        echo "$CHANGES" | grep "^backend/" || true
        echo ""
        echo "⚠️  Manual review required before updating!"
        echo "Options:"
        echo "1. Review changes: git diff HEAD origin/main -- backend/"
        echo "2. Skip this update: exit 0"
        echo "3. Proceed anyway: git pull origin main"
        exit 0
    fi
    
    # Safe to pull
    echo "✅ No production changes. Safe to update."
    sudo git pull origin main
    echo "✅ Repository updated"
fi

# 4. Verify structure
echo ""
echo "📂 Verifying directory structure..."
cd "$PROJECT_DIR"

# Check essential folders
for folder in backend cloud_core docs archive; do
    if [ -d "$folder" ]; then
        count=$(find "$folder" -type f 2>/dev/null | wc -l)
        echo "  ✅ $folder/ ($count items)"
    else
        echo "  ❌ $folder/ missing!"
    fi
done

# 5. Clean up old folders (if any)
echo ""
echo "🧹 Cleaning up old folders..."
for old_folder in rtk learn research scripts infrastructure logs wfv_workspace artifacts; do
    if [ -d "$old_folder" ]; then
        echo "  🗑️  Removing old folder: $old_folder/"
        sudo rm -rf "$old_folder"
    fi
done

# 6. Set permissions
echo ""
echo "🔒 Setting permissions..."
sudo chown -R $(whoami):$(whoami) "$PROJECT_DIR" 2>/dev/null || true
sudo chmod -R 755 "$PROJECT_DIR"

echo ""
echo "=================================="
echo "✅ VPS Sync Complete!"
echo "=================================="
echo ""
echo "📁 Structure on VPS:"
ls -la "$PROJECT_DIR" | grep -E "^d" | awk '{print "  " $9 " (" $3 ")"}'
echo ""
echo "🔄 Next steps:"
echo "1. Review changes: cd $PROJECT_DIR && git log --oneline -5"
echo "2. Restart services if needed: docker-compose restart"
echo "3. Check production: python backend/scripts/test_lighter_connection.py"
echo ""
echo "💾 Backup location: $BACKUP_DIR"
