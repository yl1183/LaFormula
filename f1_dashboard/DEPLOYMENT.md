# F1 Kalshi Trading System — Deployment Guide

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    FastAPI Server                         │
│                                                          │
│  ┌────────────┐  ┌──────────────┐  ┌──────────────────┐ │
│  │ Autonomous │  │   Strategy   │  │  Kalshi Client   │ │
│  │   Loop     │──│ generate_    │──│  (RSA-PSS auth)  │ │
│  │ (24/7)     │  │ signals()    │  │  place_order()   │ │
│  └────────────┘  └──────────────┘  └──────────────────┘ │
│         │                                    │           │
│  ┌──────┴──────┐                    ┌────────┴────────┐  │
│  │   SQLite    │                    │  F1 Live APIs   │  │
│  │  (WAL mode) │                    │ Jolpica+OpenF1  │  │
│  └─────────────┘                    └─────────────────┘  │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │              React Dashboard (SPA)                 │  │
│  │  Dashboard | Trading | Backtest | F1 Hub | Config  │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

## Quick Start (Local)

```bash
cd f1_dashboard/backend
cp ../.env.example .env
# Edit .env with your Kalshi credentials

# Start server
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000

# Dashboard: http://localhost:8000
# API: http://localhost:8000/api/health
```

## Deploy to Railway (Recommended — Free Tier)

1. Push this repo to GitHub
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub
3. Select this repo, Railway detects the Dockerfile
4. Add environment variables:
   - `KALSHI_API_KEY` = your key
   - `KALSHI_PEM_PATH` = /app/data/kalshi_key.pem
   - `DRY_RUN` = false (when ready for live trading)
   - `CONFIRM_PIN` = 483291 (or change it)
5. Add a persistent volume mounted at `/app/data`
6. Deploy — Railway gives you a public URL

## Deploy to Fly.io (Free Tier)

```bash
fly launch  # Creates app from fly.toml
fly volumes create f1_data --size 1 --region iad
fly secrets set KALSHI_API_KEY=your_key
fly secrets set DRY_RUN=false
fly deploy
```

## Deploy to Render

1. Push repo to GitHub
2. New Web Service → Connect repo
3. Render detects `render.yaml`
4. Add a 1GB persistent disk at `/app/data`
5. Set env vars: KALSHI_API_KEY, DRY_RUN=false

## Cloudflare Tunnel (This VM)

```bash
# Quick tunnel (random URL, resets on restart)
cloudflared tunnel --url http://localhost:8000

# Named tunnel (persistent URL)
cloudflared tunnel create f1-trading
cloudflared tunnel route dns f1-trading your-domain.com
cloudflared tunnel run f1-trading
```

## Kill Switch

```bash
# Stop all new trades (open positions settle naturally)
curl -X POST https://YOUR-URL/api/kill?pin=483291

# Resume trading
curl -X POST https://YOUR-URL/api/unkill?pin=483291

# Check status
curl https://YOUR-URL/api/kill/status
```

Dashboard also has a kill button on the Trading page.

## Going Live

1. Set `DRY_RUN=false` in environment
2. Upload your Kalshi PEM key to the persistent volume
3. Restart the server
4. The system will:
   - Auto-detect race weekends from the 2026 calendar
   - Poll Kalshi every 5 minutes during weekends
   - Auto-detect when qualifying results are available
   - Generate signals when edges exceed thresholds
   - Place limit orders automatically (no confirmation)
   - Settle trades when race results come in
   - Log everything to SQLite audit trail

## Safety Rails

| Feature | Value |
|---------|-------|
| Per-trade max | 7% of bankroll |
| Per-weekend max | 15% of bankroll |
| Auto-halt | $50 floor OR 50% peak drawdown |
| First 4 races | Half-size ($2.50/trade) |
| Kill switch | PIN-protected, persists across restarts |
| Dry-run | Default ON, must explicitly set DRY_RUN=false |

## Monitoring

- **Dashboard**: Real-time view of portfolio, signals, audit log
- **Health endpoint**: `GET /api/health` — returns system status
- **Audit log**: `GET /api/audit` — every signal, trade, settlement logged
- **Monitor status**: `GET /api/monitor/status` — current polling state

## File Structure

```
f1_dashboard/
├── backend/
│   ├── main.py          # FastAPI server + autonomous loop
│   ├── strategy.py      # Pure strategy logic + verified backtest
│   ├── config.py        # All settings
│   ├── db.py            # SQLite persistence (WAL mode)
│   ├── kalshi_client.py # Kalshi API with RSA-PSS auth
│   ├── f1_live.py       # Jolpica + OpenF1 wrappers
│   └── state.py         # Legacy JSON state (deprecated, use SQLite)
├── frontend/
│   ├── src/             # React + Tailwind source
│   └── dist/            # Pre-built production bundle
├── tests/
│   ├── test_system.py   # 49 unit tests
│   ├── test_api.py      # 20 API tests
│   └── llm_review.py    # 4-model LLM code review
├── Dockerfile
├── railway.json
├── fly.toml
├── render.yaml
└── .env.example
```
