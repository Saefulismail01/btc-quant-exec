#!/bin/bash

# Verify Script: Check Telegram Isolation
# Purpose: Ensure execution telegram is properly isolated from signal telegram
# Run: bash execution_layer/VERIFY_TELEGRAM_ISOLATION.sh

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  Telegram Isolation Verification for Execution Layer          ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Load .env file
if [ ! -f ".env" ]; then
    echo "❌ ERROR: .env file not found in project root"
    exit 1
fi

echo "📋 Reading .env file..."
echo ""

# Extract values using grep
TELEGRAM_BOT_TOKEN=$(grep "^TELEGRAM_BOT_TOKEN=" .env | cut -d'=' -f2 | tr -d ' ')
TELEGRAM_CHAT_ID=$(grep "^TELEGRAM_CHAT_ID=" .env | cut -d'=' -f2 | tr -d ' ')
EXECUTION_TELEGRAM_BOT_TOKEN=$(grep "^EXECUTION_TELEGRAM_BOT_TOKEN=" .env | cut -d'=' -f2 | tr -d ' ')
EXECUTION_TELEGRAM_CHAT_ID=$(grep "^EXECUTION_TELEGRAM_CHAT_ID=" .env | cut -d'=' -f2 | tr -d ' ')

echo "═════════════════════════════════════════════════════════════════"
echo "1️⃣  SIGNAL TELEGRAM (Existing)"
echo "═════════════════════════════════════════════════════════════════"

if [ -z "$TELEGRAM_BOT_TOKEN" ] && [ -z "$TELEGRAM_CHAT_ID" ]; then
    echo "⚠️  Signal telegram not configured (will use execution fallback)"
    SIGNAL_CONFIGURED=0
elif [ -z "$TELEGRAM_BOT_TOKEN" ] || [ -z "$TELEGRAM_CHAT_ID" ]; then
    echo "❌ ERROR: One of TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing"
    SIGNAL_CONFIGURED=0
else
    echo "✅ Signal telegram configured"
    echo "   Token: ${TELEGRAM_BOT_TOKEN:0:10}...${TELEGRAM_BOT_TOKEN: -5}"
    echo "   Chat ID: $TELEGRAM_CHAT_ID"
    SIGNAL_CONFIGURED=1
fi

echo ""
echo "═════════════════════════════════════════════════════════════════"
echo "2️⃣  EXECUTION TELEGRAM (New)"
echo "═════════════════════════════════════════════════════════════════"

if [ -z "$EXECUTION_TELEGRAM_BOT_TOKEN" ] && [ -z "$EXECUTION_TELEGRAM_CHAT_ID" ]; then
    echo "⚠️  Execution telegram not configured"
    EXECUTION_CONFIGURED=0
elif [ -z "$EXECUTION_TELEGRAM_BOT_TOKEN" ] || [ -z "$EXECUTION_TELEGRAM_CHAT_ID" ]; then
    echo "❌ ERROR: One of EXECUTION_TELEGRAM_BOT_TOKEN or EXECUTION_TELEGRAM_CHAT_ID is missing"
    EXECUTION_CONFIGURED=0
else
    echo "✅ Execution telegram configured"
    echo "   Token: ${EXECUTION_TELEGRAM_BOT_TOKEN:0:10}...${EXECUTION_TELEGRAM_BOT_TOKEN: -5}"
    echo "   Chat ID: $EXECUTION_TELEGRAM_CHAT_ID"
    EXECUTION_CONFIGURED=1
fi

echo ""
echo "═════════════════════════════════════════════════════════════════"
echo "3️⃣  ISOLATION CHECK"
echo "═════════════════════════════════════════════════════════════════"

# Check if tokens are different
if [ "$EXECUTION_CONFIGURED" = "1" ] && [ "$SIGNAL_CONFIGURED" = "1" ]; then
    if [ "$TELEGRAM_BOT_TOKEN" = "$EXECUTION_TELEGRAM_BOT_TOKEN" ]; then
        echo "⚠️  WARNING: Using same bot for both signal and execution"
        echo "   This is allowed but not recommended"
        ISOLATED=0
    else
        echo "✅ Tokens are different (properly isolated)"
        ISOLATED=1
    fi

    if [ "$TELEGRAM_CHAT_ID" = "$EXECUTION_TELEGRAM_CHAT_ID" ]; then
        echo "⚠️  WARNING: Using same chat for both signal and execution"
        echo "   Notifications will be mixed"
        ISOLATED=0
    else
        echo "✅ Chat IDs are different (properly isolated)"
        ISOLATED=1
    fi
else
    echo "ℹ️  Isolation check: Not both configured yet"
    ISOLATED=0
fi

echo ""
echo "═════════════════════════════════════════════════════════════════"
echo "4️⃣  RECOMMENDATIONS"
echo "═════════════════════════════════════════════════════════════════"

if [ "$ISOLATED" = "1" ]; then
    echo "✅ Setup is properly isolated!"
    echo "   • Signal and execution notifications will be separate"
    echo "   • Different bots and chat IDs configured"
    echo "   • Ready for testnet"
    EXIT_CODE=0
elif [ "$EXECUTION_CONFIGURED" = "0" ] && [ "$SIGNAL_CONFIGURED" = "1" ]; then
    echo "⚠️  Execution telegram not configured"
    echo "   Options:"
    echo "   1. Configure EXECUTION_TELEGRAM_BOT_TOKEN and EXECUTION_TELEGRAM_CHAT_ID"
    echo "      (Recommended: separate bot for execution)"
    echo "   2. Or leave empty to fallback to signal telegram"
    echo ""
    echo "   → See: execution_layer/TELEGRAM_SETUP.md for setup guide"
    EXIT_CODE=1
elif [ "$SIGNAL_CONFIGURED" = "0" ] && [ "$EXECUTION_CONFIGURED" = "1" ]; then
    echo "✅ Only execution telegram configured (signal can use execution fallback)"
    echo "   This is acceptable for execution-only setup"
    EXIT_CODE=0
elif [ "$SIGNAL_CONFIGURED" = "0" ] && [ "$EXECUTION_CONFIGURED" = "0" ]; then
    echo "⚠️  No telegram configured at all"
    echo "   Options:"
    echo "   1. Configure signal telegram (TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID)"
    echo "   2. Configure execution telegram (EXECUTION_TELEGRAM_BOT_TOKEN + EXECUTION_TELEGRAM_CHAT_ID)"
    echo "   3. Configure both (recommended)"
    echo ""
    echo "   → See: execution_layer/TELEGRAM_SETUP.md for setup guide"
    EXIT_CODE=1
else
    echo "⚠️  Partial configuration detected"
    echo "   Review and complete configuration"
    EXIT_CODE=1
fi

echo ""
echo "═════════════════════════════════════════════════════════════════"
echo "5️⃣  NEXT STEPS"
echo "═════════════════════════════════════════════════════════════════"

if [ "$EXIT_CODE" = "0" ]; then
    echo "✅ Ready for testnet!"
    echo "   1. Start API: python -m uvicorn app.main:app --reload"
    echo "   2. Start daemon: python live_executor.py"
    echo "   3. Check status: curl http://localhost:8000/api/execution/status"
else
    echo "⚠️  Please configure telegram first"
    echo "   See: execution_layer/TELEGRAM_SETUP.md"
fi

echo ""
exit $EXIT_CODE
