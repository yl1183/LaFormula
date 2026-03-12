#!/bin/bash
set -e

###############################################################################
# F1 Kalshi Trading System — Complete Setup & Deploy
# 
# PREREQUISITES:
#   1. Create a FREE Fly.io account: https://fly.io/app/sign-up
#   2. Get an API token: https://fly.io/user/personal_access_tokens
#   3. Export it: export FLY_API_TOKEN="your-token-here"
#   4. Run this script: bash setup_and_deploy.sh
###############################################################################

echo "🏎️  F1 Kalshi Trading System — Full Deployment"
echo "================================================"

if [ -z "$FLY_API_TOKEN" ]; then
    echo ""
    echo "❌ FLY_API_TOKEN not set."
    echo ""
    echo "QUICK START:"
    echo "  1. Go to https://fly.io/app/sign-up (free, no credit card)"
    echo "  2. Go to https://fly.io/user/personal_access_tokens"
    echo "  3. Create token → copy it"
    echo "  4. Run: export FLY_API_TOKEN=\"fly_xxxxxxxxxxxxx\""
    echo "  5. Re-run: bash setup_and_deploy.sh"
    exit 1
fi

# Find or install flyctl
FLYCTL=$(which flyctl 2>/dev/null || echo "")
if [ -z "$FLYCTL" ]; then
    FLYCTL="/workspace/.fly/bin/flyctl"
    if [ ! -f "$FLYCTL" ]; then
        echo "📦 Installing Fly CLI..."
        curl -L https://fly.io/install.sh | sh 2>&1 | tail -3
    fi
fi
echo "Using flyctl: $($FLYCTL version)"

cd /workspace/f1_dashboard

# Step 1: Create app (ignore error if exists)
echo ""
echo "📱 Creating app..."
$FLYCTL apps create f1-kalshi-trading 2>&1 || echo "  (already exists, continuing)"

# Step 2: Create volume (ignore error if exists)
echo ""
echo "💾 Creating persistent volume..."
$FLYCTL volumes create f1_data --size 1 --region iad --yes 2>&1 || echo "  (already exists, continuing)"

# Step 3: Deploy
echo ""
echo "🚀 Deploying (this takes ~60 seconds)..."
$FLYCTL deploy --remote-only --wait-timeout 180

# Step 4: Verify
echo ""
echo "🔍 Verifying deployment..."
sleep 5
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" https://f1-kalshi-trading.fly.dev/api/health 2>/dev/null || echo "000")

if [ "$HTTP_CODE" = "200" ]; then
    echo "✅ Health check passed!"
else
    echo "⏳ Still starting up (HTTP $HTTP_CODE). Give it 30 seconds and check manually."
fi

echo ""
echo "=============================================="
echo "✅ DEPLOYMENT COMPLETE"
echo "=============================================="
echo ""
echo "🌐 Dashboard:  https://f1-kalshi-trading.fly.dev"
echo ""
echo "🔴 Kill switch: curl -X POST https://f1-kalshi-trading.fly.dev/api/kill?pin=483291"
echo "🟢 Unkill:      curl -X POST https://f1-kalshi-trading.fly.dev/api/unkill?pin=483291"  
echo "❤️  Health:      curl https://f1-kalshi-trading.fly.dev/api/health"
echo ""
echo "📋 View logs:   $FLYCTL logs"
echo "🖥️  SSH access:  $FLYCTL ssh console"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "NEXT STEPS (when ready for live trading):"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "1. Upload Kalshi PEM file:"
echo "   $FLYCTL ssh console -C 'cat > /app/data/kalshi.pem' < your_kalshi_key.pem"
echo ""
echo "2. Set Kalshi API key and go live:"
echo "   $FLYCTL secrets set KALSHI_API_KEY=your-key-id KALSHI_PEM_PATH=/app/data/kalshi.pem DRY_RUN=false"
echo ""
echo "3. The system auto-restarts with DRY_RUN=false and begins autonomous trading."
echo "   First 4 races run at HALF SIZE for calibration."
echo ""
