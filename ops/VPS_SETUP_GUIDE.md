# VPS Setup Guide - Match Local Cleaned Structure

## 🎯 Goal
VPS harus punya struktur yang sama persis dengan local (cleaned):
```
/opt/btc-quant/
├── 🔴 backend/              (Production - 115 items)
├── 🔬 cloud_core/           (Research - 34 items)
├── 📚 docs/                (103 items)
├── 🗄️ archive/             (499 items)
├── 🔌 execution_layer/     (18 items)
├── 🎨 frontend/            (22 items)
├── 📊 backtest/            (176 items)
└── ⚙️ [config files]
```

---

## 🚀 Quick Sync (Run on VPS)

### 1. SSH ke VPS
```bash
ssh user@your-vps-ip
```

### 2. Run Sync Script
```bash
cd /opt/btc-quant
curl -o vps_sync.sh https://raw.githubusercontent.com/Saefulismail01/btc-quant-exec/main/ops/scripts/vps_sync.sh
chmod +x vps_sync.sh
sudo ./vps_sync.sh
```

---

## 📝 Manual Steps (Kalau Script Failed)

### Step 1: Backup Current
```bash
# Create backup
cd /opt
cp -r btc-quant btc-quant-backup-$(date +%Y%m%d)

# Or use tar
tar -czf btc-quant-backup-$(date +%Y%m%d).tar.gz btc-quant/
```

### Step 2: Pull Latest
```bash
cd /opt/btc-quant

# Check what will change
git fetch origin main
git diff --name-only HEAD origin/main

# ⚠️  IMPORTANT: Check if backend/ changes!
# Kalau backend/ ada di list, DON'T auto-pull!
# Manual review required.

# Kalau aman (hanya docs/cloud_core/archive):
git pull origin main
```

### Step 3: Clean Old Folders
```bash
cd /opt/btc-quant

# Remove old scattered folders
rm -rf rtk/ learn/ research/ scripts/ infrastructure/ logs/ wfv_workspace/ artifacts/

# Remove from cloud_core too
rm -rf cloud_core/archive/

# Verify structure
ls -la
```

### Step 4: Verify Structure
```bash
# Check folders
for dir in backend cloud_core docs archive execution_layer frontend backtest; do
    if [ -d "$dir" ]; then
        count=$(find "$dir" -type f | wc -l)
        echo "✅ $dir/ ($count files)"
    else
        echo "❌ $dir/ MISSING!"
    fi
done
```

---

## 🛡️ Safety Measures

### Production Protection
```bash
# Script untuk check sebelum pull
#!/bin/bash
cd /opt/btc-quant

git fetch origin main
CHANGES=$(git diff --name-only HEAD origin/main)

if echo "$CHANGES" | grep -q "^backend/"; then
    echo "🚫 PRODUCTION CHANGES DETECTED!"
    echo "Files:"
    echo "$CHANGES" | grep "^backend/"
    
    # Send Telegram alert
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${TELEGRAM_CHAT_ID}" \
        -d "text=⚠️ Production code changes on VPS - Manual review required"
    exit 1
fi

# Safe to update
git pull origin main
echo "✅ Safe update complete"
```

### Auto-Restart (Non-Production Only)
```bash
# In crontab: check every hour
0 * * * * /opt/btc-quant/ops/scripts/safe_pull.sh >> /var/log/btc-quant-sync.log 2>&1
```

---

## 🔄 Keeping VPS in Sync

### Option 1: Manual Sync (Recommended)
```bash
# Setiap kali Anda push dari local:
ssh user@vps-ip "cd /opt/btc-quant && git pull origin main && ls -la"
```

### Option 2: Auto-Sync (With Safety)
```bash
# Add to crontab
crontab -e

# Add line:
*/30 * * * * /opt/btc-quant/ops/scripts/vps_sync.sh >> /var/log/btc-quant-sync.log 2>&1
```

### Option 3: GitHub Webhook (Advanced)
```bash
# Setup webhook on VPS
# Only sync when YOU push, not random commits
```

---

## 📊 Verification Checklist

Run this on VPS after sync:

```bash
cd /opt/btc-quant

echo "=== FOLDER STRUCTURE ==="
ls -la | grep -E "^d" | awk '{print $9, "(" $3 ")"}'

echo ""
echo "=== FILE COUNTS ==="
for dir in backend cloud_core docs archive; do
    count=$(find "$dir" -type f 2>/dev/null | wc -l)
    echo "$dir: $count files"
done

echo ""
echo "=== PRODUCTION CHECK ==="
if [ -f "backend/app/core/engines/layer3_ai.py" ]; then
    echo "✅ MLP model exists"
else
    echo "❌ MLP model missing!"
fi

echo ""
echo "=== OLD FOLDERS CLEANED ==="
for old in rtk learn research scripts; do
    if [ -d "$old" ]; then
        echo "❌ $old still exists (should be archived)"
    else
        echo "✅ $old removed"
    fi
done
```

---

## 🚨 Troubleshooting

### Problem: `backend/` files missing after sync
**Solution:** Restore from backup
```bash
cp -r /opt/btc-quant-backup-*/backend /opt/btc-quant/
```

### Problem: Permission denied
**Solution:** Fix permissions
```bash
sudo chown -R $(whoami):$(whoami) /opt/btc-quant
chmod -R 755 /opt/btc-quant
```

### Problem: Git conflict
**Solution:** Force sync (careful!)
```bash
cd /opt/btc-quant
git fetch origin main
git reset --hard origin/main  # ⚠️  This will discard local changes!
```

---

## ✅ Final Check

VPS harus sama persis dengan local:
```
Local:  8 main folders + config
VPS:    8 main folders + config (sama)

Diff check:
rsync -avn --dry-run local/btc-quant/ vps:/opt/btc-quant/
```

---

**Last Updated:** April 11, 2026
