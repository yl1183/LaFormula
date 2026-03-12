#!/bin/bash
# Quick deploy script for La Formula
# Usage: bash deploy.sh

set -e

# Load Fly.io token
if [ -f /workspace/.credentials/flyio.env ]; then
    source /workspace/.credentials/flyio.env
    export FLY_API_TOKEN
fi

if [ -z "$FLY_API_TOKEN" ]; then
    echo "ERROR: FLY_API_TOKEN not set. Either:"
    echo "  1. source /workspace/.credentials/flyio.env"
    echo "  2. export FLY_API_TOKEN=your_token"
    exit 1
fi

export PATH="/workspace/.fly/bin:$PATH"
APP="f1-kalshi-trading"

echo "🏎️  Deploying La Formula..."

# Build frontend if needed
if [ "$1" = "--rebuild-frontend" ]; then
    echo "📦 Rebuilding frontend..."
    cd /workspace/f1_dashboard/frontend
    npm run build
    cd /workspace/f1_dashboard
fi

# Deploy to Fly.io
cd /workspace/f1_dashboard
flyctl deploy --now -a "$APP" -t "$FLY_API_TOKEN"

echo ""
echo "✅ Deployed! Dashboard: https://${APP}.fly.dev"
echo ""
echo "Useful commands:"
echo "  flyctl status -a $APP      # Check app status"
echo "  flyctl logs -a $APP        # View logs (add --no-tail for snapshot)"
echo "  flyctl ssh console -a $APP # SSH into container"
