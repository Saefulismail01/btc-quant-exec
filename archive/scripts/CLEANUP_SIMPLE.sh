#!/bin/bash
# SIMPLE CLEANUP - Just archive scattered files
# Run this to clean up the clutter

echo "🧹 Simple Cleanup Starting..."

# 1. Create archive folder
mkdir -p archive/old_stuff

# 2. Archive large unused folders
echo "📦 Archiving big unused folders..."
[ -d rtk ] && mv rtk archive/old_stuff/ && echo "  ✓ rtk/ archived"
[ -d learn ] && mv learn archive/old_stuff/ && echo "  ✓ learn/ archived"
[ -d research ] && mv research archive/old_stuff/ && echo "  ✓ research/ archived"
[ -d backtest/v4 ] && mv backtest/v4 archive/old_stuff/ && echo "  ✓ backtest/v4/ archived"

# 3. Archive scattered check scripts
echo "📦 Archiving scattered check scripts..."
mkdir -p archive/scripts
mv check_*.py archive/scripts/ 2>/dev/null && echo "  ✓ check_*.py moved"
mv query_trades.py archive/scripts/ 2>/dev/null && echo "  ✓ query_trades.py moved"

# 4. Keep only recent documentation
echo "📦 Archiving old docs..."
mkdir -p archive/docs
mv PHASE1_COMPLETE_SUMMARY.txt archive/docs/ 2>/dev/null
mv PROJECT_LEDGER.md archive/docs/ 2>/dev/null

# 5. Clean up root level (keep only essentials)
echo "🧹 Root level cleanup..."
mkdir -p archive/configs
mv arxiv-cli archive/configs/ 2>/dev/null

# 6. Done
echo ""
echo "✅ Cleanup Complete!"
echo ""
echo "📁 Structure sekarang:"
echo "  🔴 backend/       (production - unchanged)"
echo "  🔬 cloud_core/    (research - unchanged)"
echo "  🗄️ archive/      (old stuff archived)"
echo "  📚 [docs]         (cleaned up)"
echo ""
echo "💾 Database tetap di root: btc-quant.db"
echo "🔧 Config tetap di root: docker-compose.yml, .env, dll"
