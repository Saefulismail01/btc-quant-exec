@echo off
REM SIMPLE CLEANUP - Just archive scattered files
REM Run this to clean up the clutter

echo [32m🧹 Simple Cleanup Starting...[0m

REM 1. Create archive folder
if not exist archive\old_stuff mkdir archive\old_stuff

REM 2. Archive large unused folders
echo [33m📦 Archiving big unused folders...[0m
if exist rtk (
    move rtk archive\old_stuff\
    echo   [32m✓ rtk/ archived[0m
)
if exist learn (
    move learn archive\old_stuff\
    echo   [32m✓ learn/ archived[0m
)
if exist research (
    move research archive\old_stuff\
    echo   [32m✓ research/ archived[0m
)
if exist backtest\v4 (
    move backtest\v4 archive\old_stuff\
    echo   [32m✓ backtest/v4/ archived[0m
)

REM 3. Archive scattered check scripts
echo [33m📦 Archiving scattered check scripts...[0m
if not exist archive\scripts mkdir archive\scripts
move check_*.py archive\scripts\ 2>nul
if exist query_trades.py move query_trades.py archive\scripts\
echo   [32m✓ check_*.py moved[0m

REM 4. Keep only recent documentation
echo [33m📦 Archiving old docs...[0m
if not exist archive\docs mkdir archive\docs
if exist PHASE1_COMPLETE_SUMMARY.txt move PHASE1_COMPLETE_SUMMARY.txt archive\docs\
if exist PROJECT_LEDGER.md move PROJECT_LEDGER.md archive\docs\

REM 5. Clean up root level (keep only essentials)
echo [33m🧹 Root level cleanup...[0m
if not exist archive\configs mkdir archive\configs
if exist arxiv-cli move arxiv-cli archive\configs\

REM 6. Done
echo.
echo [32m✅ Cleanup Complete![0m
echo.
echo 📁 Structure sekarang:
echo   🔴 backend/       (production - unchanged)
echo   🔬 cloud_core/    (research - unchanged)
echo   🗄️ archive/      (old stuff archived)
echo   📚 [docs]         (cleaned up)
echo.
echo 💾 Database tetap di root: btc-quant.db
echo 🔧 Config tetap di root: docker-compose.yml, .env, dll

pause
