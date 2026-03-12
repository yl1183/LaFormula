# La Formula — F1 Prediction Trading System

Autonomous F1 event contract trading on [Kalshi](https://kalshi.com), built around the **favorite-longshot bias** in prediction markets. The system identifies mispriced F1 race-winner and podium contracts by comparing Kalshi post-qualifying prices against historical base rates (2019–2024), then executes trades with fractional Kelly sizing.

> **Status (Mar 2026):** Strategy backtested on full 2025 season (24 races). Live app deployed to Fly.io in DRY_RUN mode for 2026 Round 1 (Australia). No real money traded yet. Fly.io trial has since expired — app needs redeployment (see [Deployment](#deployment)).

---

## Repo Map

```
LaFormula/
├── f1_dashboard/                  # THE APP — full-stack trading dashboard
│   ├── backend/                   #   FastAPI backend
│   │   ├── main.py                #     API server + autonomous poller
│   │   ├── strategy.py            #     Live signal generation (3 sleeves)
│   │   ├── config.py              #     All params, base rates, 2026 calendar
│   │   ├── kalshi_client.py       #     Kalshi API v2 client (RSA auth)
│   │   ├── f1_live.py             #     FastF1 live data integration
│   │   ├── db.py                  #     SQLite persistence (trades, audit, settings)
│   │   ├── requirements.txt       #     Python deps (FastAPI, uvicorn, httpx, cryptography)
│   │   └── data/
│   │       └── f1trading_dump.sql #     DB schema + default settings (importable)
│   ├── frontend/src/              #   React frontend
│   │   └── pages/
│   │       ├── Dashboard.jsx      #     Main dashboard — equity curve, status, kill switch
│   │       ├── Trading.jsx        #     Active signals + trade execution view
│   │       ├── Backtest.jsx       #     Historical backtest results viewer
│   │       ├── Predictions.jsx    #     Pre-race prediction display
│   │       ├── F1Hub.jsx          #     Live F1 session data
│   │       └── Config.jsx         #     Runtime config editor
│   ├── Dockerfile                 #     Single-stage Docker build (backend serves frontend)
│   └── fly.toml                   #     Fly.io deployment config (easily adaptable)
│
├── f1_trading/                    # RESEARCH — strategy development + data
│   ├── backtest/                  #   Strategy backtesting lab (the core IP)
│   │   ├── strategy_tournament.py #     ★ 25-strategy tournament (S01–S25)
│   │   ├── strategy_lab.py        #     Strategy exploration framework
│   │   ├── clean_backtest.py      #     Final clean backtest (favorite-longshot bias)
│   │   ├── enhanced_strategy.py   #     Multi-sleeve combo strategies
│   │   ├── honest_robustness.py   #     Block bootstrap + concentration tests
│   │   ├── feature_engine.py      #     Feature extraction from FastF1 (anti-leakage)
│   │   ├── qualifying_model.py    #     Logistic regression model (walk-forward)
│   │   ├── build_trade_universe.py#     Builds verified trade universe from raw data
│   │   ├── post_qual_prices.py    #     Extracts post-quali VWAP prices from Kalshi data
│   │   ├── base_rates.py          #     Historical base rate computation (2019–2024)
│   │   ├── sizing.py              #     Kelly criterion + position sizing
│   │   ├── robustness.py          #     Earlier robustness tests
│   │   ├── race_calendar.py       #     Kalshi↔F1 event mapping
│   │   └── [results]              #     CSVs + JSONs (see "Key Results" below)
│   │
│   └── data/
│       ├── raw/
│       │   └── kalshi_all.json    #     ★ 259K trade records, 935 tickers (Git LFS, 74 MB)
│       └── processed/
│           ├── master_dataset.csv #     Merged features: grid, prices, practice, history
│           ├── features.csv       #     Cleaned feature matrix
│           ├── base_rates.json    #     Win/podium rates by grid position (2019–2024)
│           └── kalshi_vs_reality.csv #  Price vs outcome calibration data
│
└── .cache/fastf1/                 # FastF1 telemetry cache (2019–2026, 768 files)
```

---

## The Strategy

### Core Thesis: Favorite-Longshot Bias

Kalshi F1 markets systematically **overprice favorites and underprice longshots** relative to historical grid-position base rates. This is a well-documented behavioral bias in prediction markets.

### How It Works (Post-Qualifying, Pre-Race)

1. **After qualifying**, pull Kalshi VWAP prices for each driver's winner and podium contracts
2. **Compare** each price to the historical base rate for that driver's grid position (computed from 2019–2024, ~2500 race results)
3. **If edge > threshold**, generate a trade signal:
   - **Sleeve A** — BUY YES podium when `base_rate - price ≥ 15%` (underpriced podium finishers)
   - **Sleeve B** — BUY NO winner when `price - base_rate ≥ 8%` for P2/P3 qualifiers (overpriced near-favorites)
   - **Sleeve E** — BUY NO winner when `price - base_rate ≥ 10%` for any driver priced 15–50¢
4. **Size** using quarter-Kelly criterion, capped at 7% bankroll per trade, 15% per weekend
5. **Halt** if bankroll drops below $50 (stop-loss floor)

### Anti-Leakage Guarantees

Every backtest enforces strict temporal separation:
- **Prices**: VWAP of trades *after* qualifying ends, *before* race starts (timestamp-verified)
- **Base rates**: computed ONLY from 2019–2024 data (zero 2025 data in training)
- **Outcomes**: from FastF1 official race results (ground truth)
- **ML models** (S19/S20): walk-forward only — trained on prior races within 2025, never future data
- **Rolling features**: use only prior-race data within season

---

## Key Results (2025 Season Backtest)

### Strategy Tournament — 25 Strategies Tested

Top performers (out of 25, ranked by return + statistical robustness):

| # | Strategy | Return | Trades | Win Rate | Sharpe | Bootstrap p(profit) |
|---|----------|--------|--------|----------|--------|---------------------|
| S03 | Base Rate NO Podium (t=0.15) | **+94.8%** | 35 | 51.4% | 1.98 | 96.2% |
| S09 | Overpriced Favorites | **+43.9%** | 9 | 77.8% | 3.36 | 95.8% |
| S01 | Base Rate YES Podium (t=0.15) | **+34.3%** | 13 | 53.8% | 3.13 | 98.3% |
| S02 | Base Rate YES Podium (t=0.10) | +29.9% | 21 | 47.6% | 1.88 | 93.5% |
| S20 | Logistic Model (walk-forward) | +25.7% | — | — | — | 83.8% |
| S11 | Cross-Market Structural | +24.2% | — | — | — | 81.7% |
| S22 | Ensemble (≥3 agree) | +19.4% | — | — | — | 86.9% |
| S18 | Sell P2-P3 Winner | +19.0% | 17 | — | — | 86.3% |

**Strategies that failed:** FP2 Pace (S07: −9.7%), Sell P1 Winner (S17: −10.5%), FP2 Long-Run Podium (S25: −8.2%), Price Drift Momentum (S13: −2.7%).

### Combined Strategy (Enhanced)

The production strategy combines S01 + S03 + S18 with logistic probability adjustments:

| Variant | Return | Trades | Bootstrap p |
|---------|--------|--------|-------------|
| Baseline (flat $10, no filter) | +70.4% | 83 | — |
| + Logistic adjuster | +86.2% | 76 | — |
| + Kelly sizing | **+171.2%** | 76 | — |

### ⚠️ Honest Caveats (from `honest_robustness.py`)

- **Concentration risk is real**: Top 3 weekends account for ~96% of flat P&L. Without the best 3 weekends, profit drops to +$13 (from +$357).
- **Block bootstrap** (resampling whole weekends, not individual trades) gives p(profit) = **96.9%** flat, **89.9%** compounded — strong but not bulletproof.
- **Small sample**: 24 race weekends is inherently limited. The edge is real but noisy.

---

## Data Inventory

### Kalshi Market Data (`f1_trading/data/raw/kalshi_all.json`)
- **259,128 trade records** across **935 unique tickers**
- Coverage: Feb 2025 → Mar 2026
- Markets: Race winner, Podium, Pole position, Sprint, Season championship (drivers + constructors)
- Stored via **Git LFS** (74 MB)

### FastF1 Telemetry Cache (`.cache/fastf1/`)
- Full seasons 2019–2025 (all races) + 2026 Round 1–2
- 768 `.ff1pkl` files — session results, lap times, telemetry
- Used for: base rate computation, practice pace features, qualifying analysis

### Processed Datasets (`f1_trading/data/processed/`)
- `master_dataset.csv` — merged features per driver per race (grid, prices, practice, rolling stats)
- `features.csv` — cleaned feature matrix for ML models
- `base_rates.json` — win/podium probabilities by grid position
- `kalshi_vs_reality.csv` — calibration: Kalshi prices vs actual outcomes

### Backtest Results (`f1_trading/backtest/`)
- `tournament_results.json` — all 25 strategies, full metrics
- `clean_results.json` — clean backtest of core strategy
- `honest_robustness_results.json` — block bootstrap confidence intervals
- `enhanced_strategy_results.json` — combined strategy variants
- `final_strategy_comparison.json` — final strategy ranking
- `VERIFIED_combined_trades.csv` / `VERIFIED_flat_trades.csv` — verified trade logs
- `trades_S01_*.csv` through `trades_S25_*.csv` — per-strategy trade logs
- `feature_matrix.csv` / `master_features.csv` — feature matrices used in tournament

---

## The App (`f1_dashboard/`)

### Architecture
- **Backend**: FastAPI (Python 3.11), SQLite for persistence, async poller for autonomous operation
- **Frontend**: React (Vite), TailwindCSS
- **Deployment**: Single Docker container, backend serves built frontend static files on port 8000

### Key Endpoints
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/status` | GET | System status, mode, last poll |
| `/api/signals` | GET | Current trade signals |
| `/api/trades` | GET | Trade history |
| `/api/equity` | GET | Equity curve |
| `/api/backtest` | GET | Backtest results (serves embedded CSVs) |
| `/api/kill?pin=PIN` | POST | Kill switch — halt all trading |
| `/api/unkill?pin=PIN` | POST | Resume trading |
| `/api/settings` | GET/PUT | Runtime config (DRY_RUN, sizing, thresholds) |

### Autonomous Operation
On boot, the backend starts an async poller that:
1. Checks if it's a race weekend (Wed–Sun window around each GP)
2. If yes: polls Kalshi for current prices, runs `strategy.generate_signals()`, places trades (or logs them in DRY_RUN)
3. Syncs bankroll from Kalshi API
4. Full audit trail in SQLite

### Environment Variables
```bash
KALSHI_API_KEY=...          # Kalshi API key ID
KALSHI_PEM_PATH=...         # Path to RSA private key (.pem)
DRY_RUN=true                # Set to "false" to enable real trades
CONFIRM_PIN=483291          # 6-digit kill switch PIN
```

---

## Running Locally

### Backend only
```bash
cd f1_dashboard/backend
pip install -r requirements.txt
DRY_RUN=true uvicorn main:app --reload --port 8000
```

### Frontend dev server
```bash
cd f1_dashboard/frontend
npm install
npm run dev  # Vite dev server on :5173, proxies API to :8000
```

### Docker (production-like)
```bash
cd f1_dashboard
docker build -t la-formula .
docker run -p 8000:8000 -e DRY_RUN=true -v $(pwd)/data:/app/data la-formula
```

---

## Deployment

The app was originally on **Fly.io** (free trial, now expired). For redeployment, the best options are:

1. **Railway** (~$5/mo) — `railway.app`, connect GitHub repo, set root to `f1_dashboard`, add a volume at `/app/data`
2. **Render** ($7/mo for always-on) — add persistent disk at `/app/data`
3. **DigitalOcean Droplet** ($6/mo) — full SSH access, docker-compose, GitHub Actions for CI/CD

The only requirement is **persistent storage** for the SQLite DB (mounted at `/app/data`).

---

## For the Next Agent

### What's working
- Strategy logic is solid and well-tested. `strategy.py` implements the production version.
- `config.py` has the full 2026 calendar (23 confirmed races) and all tunable parameters.
- The app is fully functional — dashboard, trading view, backtest viewer, kill switch all work.
- Kalshi API client handles RSA authentication and order placement.

### What needs attention
1. **No real money has been traded yet.** The system ran DRY_RUN for 2026 Round 1 only.
2. **Concentration risk** — the strategy's P&L is dominated by a few big weekends. Consider diversifying across more markets or adding intra-race hedging.
3. **The 2026 calendar has 23 confirmed races** — Round 24 was TBC at time of development.
4. **Kalshi ticker format** — confirmed as `KXF1RACE-{code}GP26-{DRIVER}` (e.g., `KXF1RACE-AUSGP26-VER`). The code verified this against live API data for 2026 Round 1.
5. **FastF1 cache** will rebuild on first run (~20 min download). No action needed.
6. **The Kalshi PEM key** (`kalshi.pem`) is gitignored — you'll need to provide your own.

### Key files to read first
1. `f1_dashboard/backend/config.py` — all parameters and base rates
2. `f1_dashboard/backend/strategy.py` — live signal generation logic
3. `f1_trading/backtest/strategy_tournament.py` — the full 25-strategy evaluation
4. `f1_trading/backtest/honest_robustness.py` — statistical robustness analysis
5. `f1_trading/backtest/tournament_results.json` — results summary

### Potential improvements
- **Live price streaming** instead of polling (Kalshi websocket API)
- **In-play hedging** — exit or reduce positions during the race based on live timing
- **Polymarket integration** — cross-exchange arbitrage (raw Polymarket data exists in `data/`)
- **More granular base rates** — condition on driver + team tier, not just grid position
- **Automated backtesting on new season data** — the framework is all there, just needs 2026 results fed in
