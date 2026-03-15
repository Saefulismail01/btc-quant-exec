#!/bin/bash
# Monitor HFT bot activity on VPS
# Usage: ./hft_bot_monitor.sh

VPS="vps-rumah"
PROJECT_DIR="/home/saeful/vps/projects/btc-quant-lighter"

echo "🚀 Starting HFT Bot Monitor..."
echo "================================"

# SSH to VPS and run bot
ssh $VPS "
  cd $PROJECT_DIR
  source /tmp/hft_venv/bin/activate
  python -u backend/scripts/hft_bot.py
"
