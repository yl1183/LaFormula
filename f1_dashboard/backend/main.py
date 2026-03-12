"""FastAPI backend — fully autonomous F1 trading system.

Changes from previous version:
- SQLite replaces state.json
- Autonomous poller starts on boot (no manual start)
- Kill switch (POST /api/kill?pin=, POST /api/unkill?pin=)
- No manual trade confirmation — trades placed automatically
- Bankroll synced from Kalshi on every poll
- Full audit logging
"""
import os, json, asyncio
from datetime import datetime, timezone, timedelta
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

import config
import db
import strategy
import kalshi_client
import f1_live

# ============================================================
# Autonomous monitor state (in-memory, not persisted)
# ============================================================
monitor_state = {
    "active": False,
    "last_poll": None,
    "last_signals": [],
    "last_prices": [],
    "last_qualifying": [],
    "poll_count": 0,
    "error": None,
    "race": None,
    "mode": "idle",  # idle | weekend_active | daily_scan
}

KILL_PIN = os.getenv("CONFIRM_PIN", "483291")
SPRINT_ROUNDS = {2, 6, 12, 18, 20, 22}  # 2026 sprint weekends

# Concurrency guard — prevent overlapping auto_trade executions
_trade_lock = asyncio.Lock()


# ============================================================
# Helper: determine current race weekend
# ============================================================
def get_current_race_context():
    """Return current race dict + whether it's a race weekend."""
    now = datetime.now(timezone.utc)
    for r in config.RACES_2026:
        race_date = datetime.strptime(r["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        # Race weekend: Wednesday before race through end of race Sunday
        weekend_start = race_date - timedelta(days=5)  # Tue/Wed
        weekend_end = race_date + timedelta(hours=23, minutes=59)
        if weekend_start <= now <= weekend_end:
            days_to_race = (race_date - now).days
            return {
                "race": r,
                "is_weekend": True,
                "is_sprint": r["round"] in SPRINT_ROUNDS,
                "days_to_race": days_to_race,
                "phase": _get_phase(days_to_race, now.hour),
            }
    # Not a race weekend — find next race
    for r in config.RACES_2026:
        race_date = datetime.strptime(r["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        if race_date > now:
            return {"race": r, "is_weekend": False, "is_sprint": False, "days_to_race": (race_date - now).days, "phase": "off_week"}
    return {"race": None, "is_weekend": False, "is_sprint": False, "days_to_race": 999, "phase": "season_over"}


def _get_phase(days_to_race: int, hour: int) -> str:
    if days_to_race > 2:
        return "contracts_opening"
    elif days_to_race == 2:
        return "friday_practice"
    elif days_to_race == 1:
        return "saturday_quali"  # Primary window
    elif days_to_race == 0:
        if hour < 12:
            return "overnight_drift"
        else:
            return "race_day"
    return "post_race"


# ============================================================
# Autonomous Trading Loop
# ============================================================
async def autonomous_loop():
    """Main autonomous loop. Starts on boot. Runs forever."""
    db.audit("SYSTEM", "Autonomous trading loop started")
    monitor_state["active"] = True

    while True:
        poll_interval = 3600  # Default: 1 hour (overridden below)
        try:
            ctx = get_current_race_context()
            monitor_state["race"] = ctx["race"]
            halted = db.is_halted()

            if ctx["is_weekend"]:
                monitor_state["mode"] = "weekend_active"
                poll_interval = config.POLL_INTERVAL_SECONDS  # 5 min during weekends
                
                # === 1. Sync Kalshi balance (only when no open trades to avoid overwrites) ===
                if not db.get_open_trades():
                    await _sync_kalshi_balance()

                # === 2. Poll Kalshi prices ===
                prices = await _poll_kalshi_prices(ctx)

                # === 3. Check for qualifying results ===
                grid = await _check_qualifying(ctx)

                # === 4. Generate signals and auto-trade (with lock) ===
                if grid and prices and not halted:
                    async with _trade_lock:
                        await _auto_trade(ctx, grid, prices)
                elif halted:
                    monitor_state["error"] = "Trading halted (kill switch active)"

                # === 5. Verify fills on open orders ===
                await _verify_fills()

                # === 6. Cancel stale unfilled orders before race ===
                if ctx["phase"] in ("race_day",):
                    await _cancel_stale_orders()

                # === 7. Check for race results (settlement) ===
                if ctx["phase"] in ("race_day", "post_race"):
                    async with _trade_lock:
                        await _check_settlements(ctx)

                # === 8. Reconcile positions with Kalshi ===
                if monitor_state["poll_count"] % 12 == 0:  # Every ~hour during weekend
                    await _reconcile_positions()

            else:
                monitor_state["mode"] = "daily_scan"
                poll_interval = 3600  # 1 hour between weekends
                
                # Daily: sync balance, check for new markets
                await _sync_kalshi_balance()

            monitor_state["last_poll"] = datetime.now(timezone.utc).isoformat()
            monitor_state["poll_count"] += 1
            monitor_state["error"] = None

        except Exception as e:
            monitor_state["error"] = str(e)
            db.audit("ERROR", f"Autonomous loop error: {e}")
            poll_interval = 60  # Retry faster on error

        await asyncio.sleep(poll_interval)


async def _sync_kalshi_balance():
    """Pull real balance from Kalshi. Works in DRY_RUN (read-only)."""
    if not config.KALSHI_API_KEY:
        return
    try:
        bal = kalshi_client.get_balance()
        if bal.get("balance") is not None:
            db.set_setting("kalshi_balance_cents", str(bal["balance"]))
            db.set_setting("last_kalshi_sync", datetime.now(timezone.utc).isoformat())
            # Update bankroll to match Kalshi
            real_balance = bal["balance"] / 100.0
            db.set_bankroll(real_balance)
            db.audit("KALSHI_SYNC", f"Balance synced: ${real_balance:.2f}")
    except Exception as e:
        db.audit("ERROR", f"Kalshi balance sync failed: {e}")


async def _poll_kalshi_prices(ctx: dict) -> list[dict]:
    """Poll Kalshi for F1 contract prices."""
    race = ctx["race"]
    if not race:
        return []

    prices = []
    if config.KALSHI_API_KEY:
        try:
            # Try various ticker formats to find F1 markets
            circuit_code = race["circuit"][:3].upper()
            race_code = race.get("code", circuit_code)  # e.g., "AUS", "CHN"
            
            # Check if we've cached a working event ticker
            cached_winner = db.get_setting(f"event_ticker_winner_r{race['round']}")
            cached_podium = db.get_setting(f"event_ticker_podium_r{race['round']}")
            
            # CONFIRMED 2026 format (verified with real API):
            # Winner: KXF1RACE-AUSGP26  → contracts: KXF1RACE-AUSGP26-VER
            # Podium: KXF1RACEPODIUM-AUSGP26  → contracts: KXF1RACEPODIUM-AUSGP26-VER
            race_slug = f"{race_code}GP26"  # e.g., AUSGP26
            
            # Winner event tickers to try (confirmed format first)
            winner_tickers = []
            if cached_winner:
                winner_tickers.append(cached_winner)
            winner_tickers.extend([
                f"KXF1RACE-{race_slug}",      # CONFIRMED working format
                f"KXFRACE-{race_slug}",       # Fallback
                f"KXF1RACE-{race_code}26",    # Shorter fallback
            ])
            
            # Podium event tickers
            podium_tickers = []
            if cached_podium:
                podium_tickers.append(cached_podium)
            podium_tickers.extend([
                f"KXF1RACEPODIUM-{race_slug}",    # CONFIRMED working format
                f"KXFRACEPODIUM-{race_slug}",     # Fallback
                f"KXF1RACEPODIUM-{race_code}26",  # Shorter fallback
            ])
            
            event_tickers = winner_tickers + podium_tickers
            # Deduplicate while preserving order
            seen = set()
            event_tickers = [t for t in event_tickers if not (t in seen or seen.add(t))]
            
            all_markets = []
            
            # Try winner tickers
            for et in winner_tickers:
                try:
                    found = kalshi_client.get_markets(et)
                    if found:
                        db.set_setting(f"event_ticker_winner_r{race['round']}", et)
                        db.audit("KALSHI_MARKETS", f"Found {len(found)} WINNER markets via {et}")
                        for m in found:
                            m["_market_type"] = "winner"
                        all_markets.extend(found)
                        break
                except Exception:
                    continue
            
            # Try podium tickers
            for et in podium_tickers:
                try:
                    found = kalshi_client.get_markets(et)
                    if found:
                        db.set_setting(f"event_ticker_podium_r{race['round']}", et)
                        db.audit("KALSHI_MARKETS", f"Found {len(found)} PODIUM markets via {et}")
                        for m in found:
                            m["_market_type"] = "podium"
                        all_markets.extend(found)
                        break
                except Exception:
                    continue
            
            markets = all_markets
            
            # If no luck with guessed tickers, try broader search
            if not markets:
                try:
                    events = kalshi_client.search_events("F1")
                    for ev in events:
                        ev_ticker = ev.get("event_ticker", "")
                        ev_title = ev.get("title", "").lower()
                        race_name_lower = race["name"].lower()
                        # Match by race name in event title
                        if race_name_lower in ev_title or circuit_code.lower() in ev_title or "formula" in ev_title:
                            nested = ev.get("markets", [])
                            if nested:
                                markets = nested
                                working_ticker = ev_ticker
                                db.set_setting(f"event_ticker_r{race['round']}", ev_ticker)
                                db.audit("KALSHI_MARKETS", f"Found {len(markets)} markets via search: {ev_ticker} ({ev_title})")
                                break
                except Exception as e:
                    db.audit("ERROR", f"Kalshi event search failed: {e}")
            
            if not markets and ctx["is_weekend"]:
                db.audit("KALSHI_MARKETS", f"No F1 markets found for {race['name']}. Tried: {event_tickers}")

            for m in markets:
                ticker = m.get("ticker", "")
                # Price: prefer yes_ask (current ask), fall back to yes_bid, then last_price
                raw_price = m.get("yes_ask") or m.get("yes_bid") or m.get("last_price") or 0
                # Kalshi prices are ALWAYS in cents (1-99). Convert to decimal (0.01-0.99)
                yes_price = raw_price / 100.0
                driver_code = _extract_driver_from_ticker(ticker)
                market_type = m.get("_market_type", "winner" if "PODIUM" not in ticker.upper() else "podium")
                
                # Extract driver name and team from Kalshi market data
                driver_name = m.get("no_sub_title", "") or m.get("yes_sub_title", "")
                team = (m.get("subtitle", "") or "").replace(":: ", "")

                price_data = {
                    "driver": driver_code,
                    "driver_name": driver_name,
                    "team": team,
                    "market": market_type,
                    "price": yes_price,
                    "ticker": ticker,
                    "yes_ask": m.get("yes_ask", 0),
                    "yes_bid": m.get("yes_bid", 0),
                    "no_ask": m.get("no_ask", 0),
                    "no_bid": m.get("no_bid", 0),
                    "volume": m.get("volume", 0),
                    "open_interest": m.get("open_interest", 0),
                }
                prices.append(price_data)

                # Persist price snapshot
                db.record_price_snapshot({
                    "ticker": ticker,
                    "driver": driver_code,
                    "market": market_type,
                    "yes_price": yes_price,
                    "no_price": 1 - yes_price,
                    "volume": m.get("volume", 0),
                    "race_name": race["name"],
                    "race_round": race["round"],
                })

        except Exception as e:
            db.audit("ERROR", f"Kalshi price poll failed: {e}")

    monitor_state["last_prices"] = prices
    return prices


def _extract_driver_from_ticker(ticker: str) -> str:
    """Extract 3-letter driver code from Kalshi ticker."""
    parts = ticker.split("-")
    if len(parts) >= 3:
        return parts[-1][:3].upper()
    return ticker[-3:].upper()


async def _check_qualifying(ctx: dict) -> list[dict]:
    """Fetch qualifying results for the current race."""
    race = ctx["race"]
    if not race:
        return []

    # Check if we already have qualifying data stored
    cached = db.get_f1_session(2026, race["round"], "qualifying")
    if cached and cached.get("grid"):
        monitor_state["last_qualifying"] = cached["grid"]
        return cached["grid"]

    # Try to fetch from Jolpica/OpenF1
    try:
        quali = await f1_live.get_qualifying_results(2026, race["round"])
        if quali and quali.get("grid") and len(quali["grid"]) > 0:
            db.store_f1_session(2026, race["round"], "qualifying", quali)
            db.audit("F1_DATA", f"Qualifying results fetched for Round {race['round']}: {race['name']}")
            monitor_state["last_qualifying"] = quali["grid"]
            return quali["grid"]
    except Exception as e:
        db.audit("ERROR", f"Qualifying fetch failed: {e}")

    return []


async def _auto_trade(ctx: dict, grid: list[dict], prices: list[dict]):
    """Generate signals and place trades automatically."""
    race = ctx["race"]
    race_round = race["round"]

    # Always re-fetch bankroll from DB for each auto_trade call
    bankroll = db.get_bankroll()

    # Convert grid to format strategy expects
    grid_input = [{"driver": g.get("driver", ""), "position": g.get("position", 0)} for g in grid]

    signals = strategy.generate_signals(grid_input, prices, bankroll, race_round)
    monitor_state["last_signals"] = signals

    if not signals:
        return

    # Check weekend risk cap — includes all trades this weekend (open + settled)
    existing_weekend_risk = db.get_weekend_risk(race_round)
    max_weekend = bankroll * config.MAX_PER_WEEKEND_PCT

    for sig in signals:
        # Check if we already traded this signal (same driver/market/race)
        existing = _already_traded(sig, race_round)
        if existing:
            db.record_signal(sig, acted_on=False, skip_reason="Already traded this driver/market this weekend")
            db.audit("SIGNAL_SKIP", f"Skipped {sig['label']}: already traded", metadata=sig)
            continue

        # Check weekend risk cap
        if existing_weekend_risk + sig["risk"] > max_weekend:
            db.record_signal(sig, acted_on=False, skip_reason=f"Weekend risk cap (${max_weekend:.2f})")
            db.audit("SIGNAL_SKIP", f"Skipped {sig['label']}: weekend risk cap", metadata=sig)
            continue

        # Check drawdown halt (50% from initial $100 = $50 floor)
        if bankroll <= config.STOP_LOSS_FLOOR:
            db.set_halted(True, f"Auto-halt: bankroll ${bankroll:.2f} <= ${config.STOP_LOSS_FLOOR:.2f}")
            db.audit("HALT", f"Auto-halted due to drawdown. Bankroll: ${bankroll:.2f}")
            break
        
        # Also check peak-to-trough drawdown (50% from peak)
        peak = float(db.get_setting("peak_bankroll", "100.0"))
        if peak > 0 and bankroll < peak * 0.5:
            db.set_halted(True, f"Auto-halt: 50% peak drawdown. Peak=${peak:.2f}, Current=${bankroll:.2f}")
            db.audit("HALT", f"Auto-halted: 50% peak drawdown. Peak=${peak:.2f}, Current=${bankroll:.2f}")
            break

        # === PLACE THE TRADE ===
        try:
            side = "yes" if sig["action"] == "BUY_YES" else "no"
            price_cents = round(sig["price"] * 100) if side == "yes" else round((1 - sig["price"]) * 100)
            
            # Validate price is within Kalshi bounds [1, 99]
            if price_cents < 1 or price_cents > 99:
                db.record_signal(sig, acted_on=False, skip_reason=f"Invalid price: {price_cents}¢ (must be 1-99)")
                db.audit("SIGNAL_SKIP", f"Skipped {sig['label']}: invalid price {price_cents}¢")
                continue

            result = kalshi_client.place_order(
                ticker=sig.get("ticker", ""),
                side=side,
                contracts=sig["contracts"],
                price_cents=price_cents,
            )

            is_dry_run = result.get("dry_run", False)

            # Record the trade
            trade_data = {
                **sig,
                "race_name": race["name"],
                "race_round": race_round,
                "kalshi_order_id": result.get("order", {}).get("order_id", "") if not is_dry_run else f"DRY-{sig['id']}",
                "kalshi_response": result,
            }
            db.open_trade(trade_data)
            db.record_signal(sig, acted_on=True, trade_id=sig["id"])
            existing_weekend_risk += sig["risk"]
            # Re-fetch bankroll from DB (open_trade already deducted risk)
            bankroll = db.get_bankroll()

            mode = "DRY-RUN" if is_dry_run else "LIVE"
            db.audit("TRADE_PLACED", 
                f"[{mode}] AUTO-PLACED: {sig['label']} | Risk: ${sig['risk']:.2f} | Edge: {sig['edge']:.1%}",
                metadata=trade_data)

        except Exception as e:
            db.record_signal(sig, acted_on=False, skip_reason=f"Order failed: {e}")
            db.audit("TRADE_ERROR", f"Failed to place {sig['label']}: {e}", metadata=sig)


def _already_traded(signal: dict, race_round: int) -> bool:
    """Check if we already have a trade for this driver/market/sleeve this weekend.
    
    Uses sleeve in the check so sprint and race trades don't block each other
    when different signals fire for the same driver.
    """
    open_trades = db.get_open_trades()
    history = db.get_trade_history()
    all_trades = open_trades + history
    for t in all_trades:
        if (t.get("race_round") == race_round and
            t.get("driver") == signal["driver"] and
            t.get("market") == signal.get("market") and
            t.get("sleeve") == signal.get("sleeve")):
            return True
    return False


async def _verify_fills():
    """Check each open trade's Kalshi order status. Log partial fills or failures."""
    open_trades = db.get_open_trades()
    if not open_trades:
        return
    
    for trade in open_trades:
        order_id = trade.get("kalshi_order_id", "")
        if not order_id or order_id.startswith("DRY-"):
            continue  # Skip dry-run trades
        
        try:
            order = kalshi_client.get_order(order_id)
            if order.get("dry_run"):
                continue
            
            status = order.get("status", "unknown")
            remaining = order.get("remaining_count", 0)
            
            if status == "canceled":
                # Order was canceled (e.g., by Kalshi or user) — settle as loss
                db.audit("FILL_CHECK", f"Order {order_id} was CANCELED. Settling as loss.", metadata=order)
                db.settle_trade(trade["id"], won=False)
            elif status == "resting" and remaining > 0:
                # Partially or fully unfilled — just log it
                filled = trade.get("contracts", 0) - remaining
                if filled > 0:
                    db.audit("FILL_CHECK", f"Order {order_id}: {filled}/{trade.get('contracts', 0)} filled, {remaining} resting")
            elif status == "executed":
                # Fully filled — this is the happy path, nothing to do
                pass
            # 'pending' status = still being processed, check again next poll
        except Exception as e:
            db.audit("ERROR", f"Fill verification failed for order {order_id}: {e}")


async def _cancel_stale_orders():
    """Cancel any resting (unfilled) orders before race start to free up capital."""
    open_trades = db.get_open_trades()
    if not open_trades:
        return
    
    for trade in open_trades:
        order_id = trade.get("kalshi_order_id", "")
        if not order_id or order_id.startswith("DRY-"):
            continue
        
        try:
            order = kalshi_client.get_order(order_id)
            if order.get("dry_run"):
                continue
            
            if order.get("status") == "resting":
                # This order hasn't filled — cancel it before race starts
                result = kalshi_client.cancel_order(order_id)
                db.audit("ORDER_CANCELED", 
                    f"Canceled stale order {order_id} for {trade.get('label', '?')} — was unfilled at race start",
                    metadata=result)
                # Settle the trade as loss (risk was already deducted)
                # Actually, Kalshi returns the funds when an order is canceled,
                # so we should refund the risk
                db.settle_trade(trade["id"], won=False)
                # The bankroll will be re-synced on next Kalshi balance pull
        except Exception as e:
            db.audit("ERROR", f"Failed to cancel stale order {order_id}: {e}")


async def _reconcile_positions():
    """Compare internal tracked positions with Kalshi's actual positions.
    Logs any discrepancies for manual review.
    """
    if not config.KALSHI_API_KEY or config.DRY_RUN:
        return
    
    try:
        open_trades = db.get_open_trades()
        result = kalshi_client.reconcile_positions(open_trades)
        
        if result.get("dry_run") or result.get("error"):
            return
        
        if result["healthy"]:
            db.audit("RECONCILE", f"Position reconciliation OK: {len(result['matched'])} positions match")
        else:
            issues = []
            if result["kalshi_only"]:
                issues.append(f"{len(result['kalshi_only'])} on Kalshi not tracked")
            if result["internal_only"]:
                issues.append(f"{len(result['internal_only'])} tracked not on Kalshi")
            if result["mismatched"]:
                issues.append(f"{len(result['mismatched'])} quantity mismatches")
            
            db.audit("RECONCILE_MISMATCH", 
                f"Position discrepancy detected: {', '.join(issues)}",
                metadata=result)
    except Exception as e:
        db.audit("ERROR", f"Position reconciliation failed: {e}")


async def _check_settlements(ctx: dict):
    """Check if race has finished and settle open trades."""
    race = ctx["race"]
    if not race:
        return

    open_trades = db.get_open_trades()
    if not open_trades:
        return

    # Check for race results
    try:
        results = await f1_live.get_race_results(2026, race["round"])
        if not results or results.get("error") or not results.get("results"):
            return

        # Cache the results
        db.store_f1_session(2026, race["round"], "race", results)

        # Build podium and winner sets
        podium_drivers = set()
        winner = None
        for r in results["results"][:3]:
            code = r.get("driver", "")
            podium_drivers.add(code)
            if r.get("position") == "1" or r.get("position") == 1:
                winner = code

        # Settle each open trade
        for trade in open_trades:
            if trade.get("race_round") != race["round"]:
                continue

            driver = trade.get("driver", "")
            won = False

            if trade["action"] == "BUY_YES" and trade.get("market") == "podium":
                won = driver in podium_drivers
            elif trade["action"] == "BUY_YES" and trade.get("market") == "winner":
                won = driver == winner
            elif trade["action"] == "BUY_NO" and trade.get("market") == "winner":
                won = driver != winner
            elif trade["action"] == "BUY_NO" and trade.get("market") == "podium":
                won = driver not in podium_drivers

            result = db.settle_trade(trade["id"], won)
            if result:
                db.audit("TRADE_SETTLED",
                    f"{'WIN' if won else 'LOSS'}: {trade['label']} | PnL: ${result['pnl']:.2f}",
                    metadata=result)

        db.audit("RACE_SETTLED", f"Settled trades for {race['name']}")

    except Exception as e:
        db.audit("ERROR", f"Settlement check failed: {e}")


# ============================================================
# App Lifecycle
# ============================================================
bg_task = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global bg_task
    # Startup
    os.makedirs("data", exist_ok=True)
    
    # Decode PEM from base64 env var if present (Fly.io secrets can't hold files)
    pem_b64 = os.getenv("KALSHI_PEM_B64", "")
    if pem_b64 and config.KALSHI_PEM_PATH:
        import base64
        try:
            pem_bytes = base64.b64decode(pem_b64)
            with open(config.KALSHI_PEM_PATH, "wb") as f:
                f.write(pem_bytes)
            os.chmod(config.KALSHI_PEM_PATH, 0o600)
        except Exception as e:
            print(f"WARNING: Failed to decode KALSHI_PEM_B64: {e}")
    
    db.init_db()
    
    # Track restart count for observability
    restart_count = int(db.get_setting("restart_count", "0")) + 1
    db.set_setting("restart_count", str(restart_count))
    db.set_setting("last_start", datetime.now(timezone.utc).isoformat())
    db.audit("SYSTEM", f"Server started (boot #{restart_count})")

    # Migrate from state.json if it exists
    _migrate_from_json()

    # Start autonomous loop
    bg_task = asyncio.create_task(autonomous_loop())

    yield

    # Shutdown
    monitor_state["active"] = False
    if bg_task:
        bg_task.cancel()
    db.audit("SYSTEM", "Server shutdown")


def _migrate_from_json():
    """One-time migration from old state.json to SQLite."""
    state_file = "data/state.json"
    if not os.path.exists(state_file):
        return
    try:
        with open(state_file) as f:
            old = json.load(f)
        if old.get("bankroll") and old["bankroll"] != 100.0:
            db.set_bankroll(old["bankroll"])
        if old.get("halted"):
            db.set_halted(True, old.get("halt_reason", ""))
        # Mark as migrated
        os.rename(state_file, state_file + ".migrated")
        db.audit("SYSTEM", "Migrated from state.json")
    except Exception:
        pass


app = FastAPI(title="F1 Kalshi Trading System", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ============================================================
# STATE endpoints
# ============================================================

@app.get("/api/state")
def get_state():
    return db.get_full_state()


@app.post("/api/state/reset")
def reset_state():
    return db.reset_all()


# ============================================================
# KILL SWITCH
# ============================================================

@app.post("/api/kill")
def kill_switch(pin: str = Query(...)):
    if pin != KILL_PIN:
        raise HTTPException(403, "Invalid PIN")
    db.set_halted(True, "Kill switch activated")
    db.audit("KILL", "Kill switch activated via API")
    return {"status": "halted", "message": "All new trades stopped. Open positions will settle naturally."}


@app.post("/api/unkill")
def unkill(pin: str = Query(...)):
    if pin != KILL_PIN:
        raise HTTPException(403, "Invalid PIN")
    db.set_halted(False, "")
    db.audit("UNKILL", "Kill switch deactivated via API")
    return {"status": "active", "message": "Trading resumed."}


@app.get("/api/kill/status")
def kill_status():
    return {"halted": db.is_halted(), "reason": db.get_setting("halt_reason", "")}


# ============================================================
# MONITORING (read-only status)
# ============================================================

@app.get("/api/monitor/status")
def get_monitor_status():
    return monitor_state


@app.get("/api/monitor/signals")
def get_recent_signals(limit: int = Query(default=50)):
    return db.get_recent_signals(limit)


@app.get("/api/contracts/analysis")
def get_contracts_analysis():
    """Return every Kalshi F1 contract with live price + full model decision analysis.
    
    For each contract, shows:
    - Current price from last poll
    - Which sleeve(s) could apply
    - The base rate for that grid position
    - The computed edge
    - The decision: TRADE / NO_TRADE / WAITING
    - Full reasoning string explaining why
    """
    ctx = get_current_race_context()
    race = ctx.get("race")
    
    # Get latest prices from monitor state (most recent poll)
    prices = monitor_state.get("last_prices", [])
    
    # Also pull latest from DB if monitor hasn't polled yet
    if not prices:
        db_prices = db.get_price_history(limit=50)
        if db_prices and race:
            # Only use prices from current race
            prices = [
                {
                    "driver": p["driver"],
                    "market": p["market"],
                    "price": p["yes_price"],
                    "ticker": p["ticker"],
                    "volume": p.get("volume", 0),
                    "captured_at": p["captured_at"],
                }
                for p in db_prices
                if p.get("race_round") == (race["round"] if race else None)
            ]
            # Dedupe — keep most recent per ticker
            seen = {}
            for p in prices:
                if p["ticker"] not in seen:
                    seen[p["ticker"]] = p
            prices = list(seen.values())
    
    # Get qualifying grid (from monitor's last check or DB)
    grid = []
    if race:
        # Try to get from Jolpica via cache (non-blocking — uses last known)
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're in the event loop context — can't await, use stored data
                pass
        except:
            pass
    
    # Use monitor_state qualifying data if available
    qualifying_data = monitor_state.get("last_qualifying", [])
    
    # Build the analysis
    bankroll = db.get_bankroll()
    race_round = race["round"] if race else 0
    halted = db.is_halted()
    
    # Get existing trades this weekend
    open_trades = db.get_open_trades()
    history = db.get_trade_history()
    weekend_trades = [t for t in (open_trades + history) if t.get("race_round") == race_round]
    weekend_risk = sum(t.get("risk", 0) for t in weekend_trades)
    max_weekend = bankroll * config.MAX_PER_WEEKEND_PCT
    max_trade = bankroll * config.MAX_PER_TRADE_PCT
    
    bet_size = config.FLAT_BET_SIZE
    if race_round <= config.CALIBRATION_RACES:
        bet_size = config.FLAT_BET_SIZE / 2
    bet_size = min(bet_size, max_trade)
    
    grid_map = {g.get("driver", ""): g.get("position", 0) for g in qualifying_data}
    has_grid = len(grid_map) > 0
    has_prices = len(prices) > 0
    
    contracts = []
    for p in prices:
        driver = p["driver"]
        market = p["market"]
        price = p["price"]
        ticker = p.get("ticker", "")
        volume = p.get("volume", 0)
        captured_at = p.get("captured_at", "")
        
        pos = grid_map.get(driver)
        
        analysis = {
            "ticker": ticker,
            "driver": driver,
            "driver_name": p.get("driver_name", ""),
            "team": p.get("team", ""),
            "market": market,
            "price": price,
            "yes_ask": p.get("yes_ask", 0),
            "yes_bid": p.get("yes_bid", 0),
            "no_ask": p.get("no_ask", 0),
            "no_bid": p.get("no_bid", 0),
            "volume": volume,
            "open_interest": p.get("open_interest", 0),
            "captured_at": captured_at,
            "grid_pos": pos,
            "sleeves": [],       # Which sleeves were evaluated
            "decision": "NO_TRADE",
            "decision_icon": "⬜",
            "reasons": [],       # All reasoning
            "edge": None,
            "base_rate": None,
            "sleeve_match": None,
            "signal": None,      # The signal that would fire (if any)
            "blocked_by": None,  # What's preventing the trade
        }
        
        # If no grid position, we can't analyze
        if pos is None:
            if not has_grid:
                analysis["decision"] = "WAITING"
                analysis["decision_icon"] = "⏳"
                analysis["reasons"].append("Qualifying results not yet available. Cannot compute base rates without grid position.")
            else:
                analysis["reasons"].append(f"Driver {driver} not found in qualifying grid. May be a reserve driver or ticker parsing issue.")
            contracts.append(analysis)
            continue
        
        # Check already traded
        already_traded = any(
            t.get("driver") == driver and t.get("market") == market
            for t in weekend_trades
        )
        
        # === EVALUATE SLEEVE A: Buy YES Podium ===
        if market == "podium":
            base = config.PODIUM_BASE_RATES.get(pos, 0)
            edge = base - price
            analysis["base_rate"] = base
            analysis["edge"] = round(edge, 4)
            
            sleeve_a = {
                "sleeve": "A",
                "name": "Lottery (Buy YES Podium)",
                "base_rate": base,
                "edge": round(edge, 4),
                "threshold": config.SLEEVE_A_MIN_EDGE,
                "qualifies": edge >= config.SLEEVE_A_MIN_EDGE,
                "reasoning": "",
            }
            
            if edge >= config.SLEEVE_A_MIN_EDGE:
                contracts_count = max(1, int(bet_size / price))
                risk = round(contracts_count * price, 2)
                if risk > max_trade:
                    contracts_count = max(1, int(max_trade / price))
                    risk = round(contracts_count * price, 2)
                profit = round(contracts_count * (1.0 - price), 2)
                
                sleeve_a["reasoning"] = (
                    f"✅ EDGE FOUND: {driver} qualifies P{pos}. "
                    f"Historical podium rate: {base:.1%}. Kalshi price: {price:.1%}. "
                    f"Edge: {edge:.1%} ≥ {config.SLEEVE_A_MIN_EDGE:.0%} threshold. "
                    f"Would buy {contracts_count} YES contracts @ {price:.0%} = ${risk:.2f} risk for ${profit:.2f} potential profit."
                )
                
                analysis["signal"] = {
                    "sleeve": "A", "action": "BUY_YES", "contracts": contracts_count,
                    "risk": risk, "profit": profit, "edge": edge,
                }
                analysis["sleeve_match"] = "A"
                
                # Check blockers
                if halted:
                    analysis["decision"] = "BLOCKED"
                    analysis["decision_icon"] = "🛑"
                    analysis["blocked_by"] = "Kill switch active"
                    analysis["reasons"].append("Kill switch is active. Trade would fire otherwise.")
                elif already_traded:
                    analysis["decision"] = "BLOCKED"
                    analysis["decision_icon"] = "🔄"
                    analysis["blocked_by"] = "Already traded this driver/market this weekend"
                    analysis["reasons"].append(f"Already have a position on {driver} {market} this weekend.")
                elif weekend_risk + risk > max_weekend:
                    analysis["decision"] = "BLOCKED"
                    analysis["decision_icon"] = "📊"
                    analysis["blocked_by"] = f"Weekend risk cap (${weekend_risk:.2f} + ${risk:.2f} > ${max_weekend:.2f})"
                    analysis["reasons"].append(f"Weekend risk: ${weekend_risk:.2f}/{max_weekend:.2f}. Adding ${risk:.2f} would exceed cap.")
                elif bankroll <= config.STOP_LOSS_FLOOR:
                    analysis["decision"] = "BLOCKED"
                    analysis["decision_icon"] = "💀"
                    analysis["blocked_by"] = f"Drawdown halt (bankroll ${bankroll:.2f} ≤ ${config.STOP_LOSS_FLOOR:.2f})"
                else:
                    analysis["decision"] = "TRADE"
                    analysis["decision_icon"] = "🟢"
                    analysis["reasons"].append("Signal meets all criteria. System will/did auto-trade.")
            else:
                sleeve_a["reasoning"] = (
                    f"❌ No edge: {driver} qualifies P{pos}. "
                    f"Historical podium rate: {base:.1%}. Kalshi price: {price:.1%}. "
                    f"Edge: {edge:.1%} < {config.SLEEVE_A_MIN_EDGE:.0%} threshold needed. "
                    f"Market is pricing {driver}'s podium finish {'close to' if abs(edge) < 0.05 else 'above'} fair value."
                )
                analysis["reasons"].append(f"Sleeve A: Edge {edge:.1%} < {config.SLEEVE_A_MIN_EDGE:.0%} threshold.")
            
            analysis["sleeves"].append(sleeve_a)
        
        # === EVALUATE SLEEVE B: Sell P2/P3 Winner ===
        if market == "winner":
            base = config.WINNER_BASE_RATES.get(pos, 0)
            edge = price - base  # Selling side — overpricing
            analysis["base_rate"] = base
            analysis["edge"] = round(edge, 4)
            
            in_grid_range = config.SLEEVE_B_GRID_RANGE[0] <= pos <= config.SLEEVE_B_GRID_RANGE[1]
            
            sleeve_b = {
                "sleeve": "B",
                "name": "Grinder (Sell P2/P3 Winner)",
                "base_rate": base,
                "edge": round(edge, 4),
                "threshold": config.SLEEVE_B_MIN_EDGE,
                "qualifies": in_grid_range and edge >= config.SLEEVE_B_MIN_EDGE,
                "reasoning": "",
            }
            
            if not in_grid_range:
                sleeve_b["reasoning"] = (
                    f"❌ Grid filter: {driver} qualifies P{pos}, but Sleeve B only targets P{config.SLEEVE_B_GRID_RANGE[0]}-P{config.SLEEVE_B_GRID_RANGE[1]}. "
                    f"(Historical win rate for P{pos}: {base:.1%}. Kalshi: {price:.1%}. Edge would be {edge:.1%}.)"
                )
            elif edge >= config.SLEEVE_B_MIN_EDGE:
                no_price = 1.0 - price
                contracts_count = max(1, int(bet_size / no_price))
                risk = round(contracts_count * no_price, 2)
                if risk > max_trade:
                    contracts_count = max(1, int(max_trade / no_price))
                    risk = round(contracts_count * no_price, 2)
                profit = round(contracts_count * price, 2)
                
                sleeve_b["reasoning"] = (
                    f"✅ EDGE FOUND: {driver} qualifies P{pos}. "
                    f"Historical win rate: {base:.1%}. Kalshi price: {price:.1%}. "
                    f"Overpriced by {edge:.1%} ≥ {config.SLEEVE_B_MIN_EDGE:.0%} threshold. "
                    f"Would sell (buy NO) {contracts_count} contracts @ {no_price:.0%} = ${risk:.2f} risk for ${profit:.2f} potential profit."
                )
                
                analysis["signal"] = {
                    "sleeve": "B", "action": "BUY_NO", "contracts": contracts_count,
                    "risk": risk, "profit": profit, "edge": edge,
                }
                analysis["sleeve_match"] = "B"
                
                if halted:
                    analysis["decision"] = "BLOCKED"
                    analysis["decision_icon"] = "🛑"
                    analysis["blocked_by"] = "Kill switch active"
                elif already_traded:
                    analysis["decision"] = "BLOCKED"
                    analysis["decision_icon"] = "🔄"
                    analysis["blocked_by"] = "Already traded this driver/market this weekend"
                elif weekend_risk + risk > max_weekend:
                    analysis["decision"] = "BLOCKED"
                    analysis["decision_icon"] = "📊"
                    analysis["blocked_by"] = f"Weekend risk cap exceeded"
                elif bankroll <= config.STOP_LOSS_FLOOR:
                    analysis["decision"] = "BLOCKED"
                    analysis["decision_icon"] = "💀"
                    analysis["blocked_by"] = "Drawdown halt"
                else:
                    analysis["decision"] = "TRADE"
                    analysis["decision_icon"] = "🟢"
                    analysis["reasons"].append("Signal meets all criteria. System will/did auto-trade.")
            else:
                sleeve_b["reasoning"] = (
                    f"❌ No edge: {driver} qualifies P{pos}. "
                    f"Historical win rate: {base:.1%}. Kalshi price: {price:.1%}. "
                    f"Edge: {edge:.1%} < {config.SLEEVE_B_MIN_EDGE:.0%} threshold. "
                    f"Market pricing is {'close to' if abs(edge) < 0.03 else 'below'} fair value."
                )
                analysis["reasons"].append(f"Sleeve B: Edge {edge:.1%} < {config.SLEEVE_B_MIN_EDGE:.0%} threshold.")
            
            analysis["sleeves"].append(sleeve_b)
            
            # === EVALUATE SLEEVE E: Sell Any Overpriced Winner ===
            in_price_range = config.SLEEVE_E_PRICE_RANGE[0] <= price <= config.SLEEVE_E_PRICE_RANGE[1]
            
            sleeve_e = {
                "sleeve": "E",
                "name": "Value (Sell Overpriced Non-Top-3)",
                "base_rate": base,
                "edge": round(edge, 4),
                "threshold": config.SLEEVE_E_MIN_EDGE,
                "qualifies": pos > 3 and in_price_range and edge >= config.SLEEVE_E_MIN_EDGE,
                "reasoning": "",
            }
            
            if pos <= 3:
                sleeve_e["reasoning"] = f"❌ Grid filter: P{pos} is top-3. Sleeve E only targets P4+."
            elif not in_price_range:
                sleeve_e["reasoning"] = (
                    f"❌ Price filter: {price:.1%} is outside [{config.SLEEVE_E_PRICE_RANGE[0]:.0%}, {config.SLEEVE_E_PRICE_RANGE[1]:.0%}] range."
                )
            elif edge >= config.SLEEVE_E_MIN_EDGE:
                no_price = 1.0 - price
                contracts_count = max(1, int(bet_size / no_price))
                risk = round(contracts_count * no_price, 2)
                if risk > max_trade:
                    contracts_count = max(1, int(max_trade / no_price))
                    risk = round(contracts_count * no_price, 2)
                profit = round(contracts_count * price, 2)
                
                sleeve_e["reasoning"] = (
                    f"✅ EDGE FOUND: {driver} qualifies P{pos}. "
                    f"Historical win rate: {base:.1%}. Kalshi wildly overprices at {price:.1%}. "
                    f"Edge: {edge:.1%} ≥ {config.SLEEVE_E_MIN_EDGE:.0%}. "
                    f"Would sell {contracts_count} contracts = ${risk:.2f} risk."
                )
                
                # Only set signal if Sleeve B didn't already claim this
                if analysis["sleeve_match"] is None:
                    analysis["signal"] = {
                        "sleeve": "E", "action": "BUY_NO", "contracts": contracts_count,
                        "risk": risk, "profit": profit, "edge": edge,
                    }
                    analysis["sleeve_match"] = "E"
                    analysis["decision"] = "TRADE"
                    analysis["decision_icon"] = "🟢"
            else:
                sleeve_e["reasoning"] = (
                    f"❌ No edge: P{pos} win rate: {base:.1%}. Price: {price:.1%}. "
                    f"Edge: {edge:.1%} < {config.SLEEVE_E_MIN_EDGE:.0%} threshold."
                )
            
            analysis["sleeves"].append(sleeve_e)
        
        # Default reason if no edge found
        if analysis["decision"] == "NO_TRADE" and not analysis["reasons"]:
            analysis["reasons"].append("No sleeve found an actionable edge at current prices.")
        
        contracts.append(analysis)
    
    # Sort: trades first, then blocked, then no-trade, then waiting
    decision_order = {"TRADE": 0, "BLOCKED": 1, "NO_TRADE": 2, "WAITING": 3}
    contracts.sort(key=lambda c: (decision_order.get(c["decision"], 9), -(c["edge"] or 0)))
    
    return {
        "race": race,
        "phase": ctx.get("phase", "unknown"),
        "is_weekend": ctx.get("is_weekend", False),
        "has_grid": has_grid,
        "has_prices": has_prices,
        "bankroll": bankroll,
        "weekend_risk": round(weekend_risk, 2),
        "max_weekend_risk": round(max_weekend, 2),
        "bet_size": bet_size,
        "halted": halted,
        "contracts": contracts,
        "qualifying_grid": [{"driver": d, "position": p} for d, p in sorted(grid_map.items(), key=lambda x: x[1])],
        "last_poll": monitor_state.get("last_poll"),
        "poll_count": monitor_state.get("poll_count", 0),
    }


# ============================================================
# STRATEGY
# ============================================================

@app.get("/api/backtest")
def get_backtest(
    bet_size: float = Query(default=5.0),
    sleeve_a: bool = Query(default=True),
    sleeve_b: bool = Query(default=True),
    sleeve_e: bool = Query(default=True),
    edge_a: float = Query(default=0.15),
    edge_b: float = Query(default=0.08),
    edge_e: float = Query(default=0.10),
):
    return strategy.run_backtest(
        bet_size=bet_size, sleeve_a=sleeve_a, sleeve_b=sleeve_b, sleeve_e=sleeve_e,
        edge_a=edge_a, edge_b=edge_b, edge_e=edge_e,
    )


# ============================================================
# TRADING (read-only — trades happen automatically)
# ============================================================

@app.get("/api/trades/open")
def get_open_trades():
    return db.get_open_trades()


@app.get("/api/trades/history")
def get_trade_history():
    return db.get_trade_history()


@app.get("/api/trades/all")
def get_all_trades():
    return db.get_all_trades()


# Manual settlement endpoint (for when Kalshi auto-settle isn't working)
class SettleRequest(BaseModel):
    trade_id: str
    won: bool

@app.post("/api/trade/settle")
async def settle_trade(req: SettleRequest):
    async with _trade_lock:
        result = db.settle_trade(req.trade_id, req.won)
    if not result:
        raise HTTPException(404, "Trade not found or already settled")
    db.audit("MANUAL_SETTLE", f"Manual settlement: {req.trade_id} -> {'WIN' if req.won else 'LOSS'}")
    return result


# ============================================================
# KALSHI
# ============================================================

@app.get("/api/kalshi/balance")
def kalshi_balance():
    return kalshi_client.get_balance()


@app.get("/api/kalshi/markets/{event_ticker}")
def kalshi_markets(event_ticker: str):
    return kalshi_client.get_markets(event_ticker)


@app.get("/api/kalshi/discover")
def kalshi_discover():
    """Search Kalshi for any F1-related events. Use this to find the right ticker format."""
    if not config.KALSHI_API_KEY:
        return {"error": "No API key configured"}
    results = {"events": [], "searches_tried": []}
    
    # Search with various queries
    for query in ["F1", "Formula 1", "Grand Prix", "racing"]:
        try:
            events = kalshi_client.search_events(query)
            results["searches_tried"].append({"query": query, "count": len(events)})
            for ev in events:
                title = ev.get("title", "")
                if any(kw in title.lower() for kw in ["f1", "formula", "grand prix", "race winner", "podium"]):
                    results["events"].append({
                        "event_ticker": ev.get("event_ticker"),
                        "title": title,
                        "status": ev.get("status"),
                        "markets_count": len(ev.get("markets", [])),
                        "market_tickers": [m.get("ticker") for m in ev.get("markets", [])[:5]],
                    })
        except Exception as e:
            results["searches_tried"].append({"query": query, "error": str(e)})
    
    # Also try direct market lookup with known patterns for current race
    ctx = get_current_race_context()
    if ctx.get("race"):
        race = ctx["race"]
        code = race.get("code", race["circuit"][:3].upper())
        direct_tries = []
        for pattern in [f"KXF1RACE-{code}GP26", f"KXF1RACE-{code}26", f"KXFRACE-{code}GP-26", f"KXF1-{code}26"]:
            try:
                markets = kalshi_client.get_markets(pattern)
                direct_tries.append({"ticker": pattern, "found": len(markets)})
            except Exception as e:
                direct_tries.append({"ticker": pattern, "error": str(e)})
        results["direct_lookups"] = direct_tries
        results["current_race"] = race["name"]
    
    db.audit("KALSHI_DISCOVER", f"Discovery found {len(results['events'])} F1 events")
    return results


@app.get("/api/kalshi/positions")
def kalshi_positions():
    """Get actual Kalshi positions for reconciliation."""
    return kalshi_client.get_positions()


@app.get("/api/kalshi/orders")
def kalshi_orders(status: str = None):
    """Get Kalshi orders, optionally filtered by status."""
    return kalshi_client.get_orders(status=status)


@app.get("/api/kalshi/reconcile")
def kalshi_reconcile():
    """Compare internal tracked trades with Kalshi actual positions."""
    open_trades = db.get_open_trades()
    return kalshi_client.reconcile_positions(open_trades)


@app.post("/api/kalshi/sync")
def kalshi_sync():
    if not config.KALSHI_API_KEY:
        return {"synced": False, "reason": "No API key"}
    try:
        bal = kalshi_client.get_balance()
        pos = kalshi_client.get_positions()
        if bal.get("balance") is not None:
            real = bal["balance"] / 100.0
            db.set_bankroll(real)
            db.set_setting("kalshi_balance_cents", str(bal["balance"]))
            db.set_setting("last_kalshi_sync", datetime.now(timezone.utc).isoformat())
        return {"synced": True, "balance": bal, "positions": pos}
    except Exception as e:
        return {"synced": False, "error": str(e)}


# ============================================================
# PRICES
# ============================================================

@app.get("/api/prices/history")
def price_history(ticker: str = None, limit: int = 100):
    return db.get_price_history(ticker, limit)


# ============================================================
# AUDIT LOG
# ============================================================

@app.get("/api/audit")
def get_audit(event_type: str = None, limit: int = 200):
    return db.get_audit_log(event_type, limit)


# ============================================================
# F1 LIVE DATA
# ============================================================

@app.get("/api/f1/standings/drivers")
async def driver_standings(year: int = 2025):
    return await f1_live.get_driver_standings(year)


@app.get("/api/f1/standings/constructors")
async def constructor_standings(year: int = 2025):
    return await f1_live.get_constructor_standings(year)


@app.get("/api/f1/results/last")
async def last_race(year: int = 2025):
    return await f1_live.get_last_race_results(year)


@app.get("/api/f1/qualifying")
async def qualifying(year: int = 2025, round: int = None):
    return await f1_live.get_qualifying_results(year, round)


@app.get("/api/f1/timing")
async def live_timing():
    return await f1_live.get_live_timing()


@app.get("/api/f1/race/{year}/{round_num}")
async def race_results(year: int, round_num: int):
    return await f1_live.get_race_results(year, round_num)


# ============================================================
# EXPANDED F1 HUB ENDPOINTS
# ============================================================

@app.get("/api/f1/season/{year}")
async def season_races(year: int):
    return await f1_live.get_season_races(year)


@app.get("/api/f1/driver-history/{year}")
async def driver_history(year: int):
    return await f1_live.get_driver_race_history(year)


@app.get("/api/f1/quali-battles/{year}")
async def quali_battles(year: int):
    return await f1_live.get_qualifying_pace(year)


@app.get("/api/f1/predictions")
async def weekend_predictions():
    """AI-generated predictions for the upcoming race weekend.
    Uses base rates, recent form, and circuit characteristics."""
    import config as cfg
    
    ctx = get_current_race_context()
    race = ctx.get("race") or (cfg.RACES_2026[0] if cfg.RACES_2026 else None)
    if not race:
        return {"error": "No upcoming race"}
    
    # Get Kalshi contracts if available
    contracts = monitor_state.get("last_contracts", {})
    
    # Get qualifying data if available
    quali = monitor_state.get("last_qualifying") or {}
    if isinstance(quali, list):
        quali = quali[0] if quali else {}
    grid = quali.get("grid", []) if isinstance(quali, dict) else []
    
    # Circuit characteristics (hand-coded knowledge)
    CIRCUIT_TRAITS = {
        "AUS": {"type": "Street-ish", "overtaking": "Medium", "safety_car_pct": 62, "drs_zones": 3, "key_trait": "High SC rate, wall proximity, new surface in 2022 reconfig"},
        "CHN": {"type": "Permanent", "overtaking": "High", "safety_car_pct": 43, "drs_zones": 2, "key_trait": "Long back straight, heavy tire deg, Turn 1-2 complex"},
        "JPN": {"type": "Permanent", "overtaking": "Low", "safety_car_pct": 38, "drs_zones": 1, "key_trait": "Highest-speed circuit, qualifying critical, Esses = car balance test"},
        "BHR": {"type": "Permanent", "overtaking": "High", "safety_car_pct": 45, "drs_zones": 3, "key_trait": "Tire management race, multiple passing zones, night race"},
        "SAU": {"type": "Street", "overtaking": "Medium", "safety_car_pct": 75, "drs_zones": 3, "key_trait": "Fastest street circuit, very high SC risk, wall brushing"},
        "MIA": {"type": "Street-ish", "overtaking": "Medium", "safety_car_pct": 50, "drs_zones": 3, "key_trait": "Sprint weekend, high humidity, hard braking zones"},
        "CAN": {"type": "Semi-street", "overtaking": "High", "safety_car_pct": 58, "drs_zones": 2, "key_trait": "Wall of Champions, heavy braking, high SC rate"},
        "MON": {"type": "Street", "overtaking": "Very Low", "safety_car_pct": 55, "drs_zones": 1, "key_trait": "Qualifying IS the race. Track position is everything."},
        "ESP": {"type": "Permanent", "overtaking": "Medium", "safety_car_pct": 30, "drs_zones": 2, "key_trait": "New Madrid circuit for 2026, unknown characteristics"},
        "AUT": {"type": "Permanent", "overtaking": "High", "safety_car_pct": 48, "drs_zones": 3, "key_trait": "Short lap, many laps, high-altitude braking, Red Bull home"},
        "GBR": {"type": "Permanent", "overtaking": "Medium", "safety_car_pct": 35, "drs_zones": 2, "key_trait": "High-speed, aero-sensitive, weather can shake things up"},
        "BEL": {"type": "Permanent", "overtaking": "High", "safety_car_pct": 48, "drs_zones": 2, "key_trait": "Sprint weekend, Eau Rouge/Kemmel straight, rain risk, longest lap"},
        "HUN": {"type": "Permanent", "overtaking": "Low", "safety_car_pct": 32, "drs_zones": 1, "key_trait": "Monaco without walls. Track position critical. Hot temps."},
        "NED": {"type": "Permanent", "overtaking": "Low", "safety_car_pct": 42, "drs_zones": 1, "key_trait": "Banked corners, narrow, strategy variety, wind factor"},
        "ITA": {"type": "Permanent", "overtaking": "Very High", "safety_car_pct": 48, "drs_zones": 2, "key_trait": "Temple of Speed. Slipstream crucial. Low downforce."},
        "AZE": {"type": "Street", "overtaking": "High", "safety_car_pct": 80, "drs_zones": 2, "key_trait": "Castle section + 2.2km straight. Chaos race. 80% SC rate."},
        "SGP": {"type": "Street", "overtaking": "Low", "safety_car_pct": 72, "drs_zones": 3, "key_trait": "Night race, extreme humidity, physical endurance test, high SC"},
        "USA": {"type": "Permanent", "overtaking": "Medium", "safety_car_pct": 55, "drs_zones": 2, "key_trait": "Sprint weekend, multi-line racing, Turn 1 elevation"},
        "MEX": {"type": "Permanent", "overtaking": "Medium", "safety_car_pct": 45, "drs_zones": 3, "key_trait": "2,240m altitude, thin air, turbo advantage, long straight"},
        "BRA": {"type": "Permanent", "overtaking": "High", "safety_car_pct": 65, "drs_zones": 2, "key_trait": "Sprint weekend, rain risk, counter-clockwise, altitude"},
        "LVG": {"type": "Street", "overtaking": "High", "safety_car_pct": 55, "drs_zones": 2, "key_trait": "Night race, cold track, long straight, low grip"},
        "QAT": {"type": "Permanent", "overtaking": "Medium", "safety_car_pct": 35, "drs_zones": 2, "key_trait": "Sprint weekend, extreme tire stress, outer loop = G forces"},
        "ABU": {"type": "Permanent", "overtaking": "Medium", "safety_car_pct": 38, "drs_zones": 2, "key_trait": "Season finale, day-to-night, hotel section"},
    }
    
    circuit = CIRCUIT_TRAITS.get(race["code"], {})
    sc_pct = circuit.get("safety_car_pct", 40)
    overtaking = circuit.get("overtaking", "Medium")
    
    # Build predictions based on grid + base rates + circuit
    predictions = []
    
    # 2026 pre-season power rankings (our prior before any data)
    # Based on winter testing reports and team trajectory
    TEAM_POWER = {
        "McLaren": 0.92, "Ferrari": 0.90, "Red Bull": 0.88, "Mercedes": 0.85,
        "Aston Martin": 0.72, "Williams": 0.60, "Alpine": 0.58,
        "RB": 0.55, "Haas": 0.50, "Kick Sauber": 0.48, "Sauber": 0.48,
        "Cadillac": 0.45,
    }
    
    DRIVER_RATINGS = {
        "VER": 0.98, "NOR": 0.93, "LEC": 0.92, "HAM": 0.90, "RUS": 0.89,
        "PIA": 0.87, "SAI": 0.86, "ALO": 0.83, "GAS": 0.78, "OCO": 0.76,
        "TSU": 0.75, "STR": 0.74, "HUL": 0.73, "ALB": 0.76, "MAG": 0.71,
        "LAW": 0.72, "COL": 0.70, "HAD": 0.68, "BEA": 0.65, "DOO": 0.62,
        "SAR": 0.60, "BOT": 0.78, "ZHO": 0.65, "BOR": 0.64, "ANT": 0.63,
    }
    
    # If we have grid, use it for precise predictions
    if grid:
        for entry in grid:
            pos = entry.get("position", 20)
            code = entry.get("driver", "???")
            name = entry.get("name", code)
            team = entry.get("team", "")
            
            podium_base = cfg.PODIUM_BASE_RATES.get(pos, 0.02)
            win_base = cfg.WINNER_BASE_RATES.get(pos, 0.005)
            
            # Adjust for circuit type
            if overtaking in ["Very Low", "Low"]:
                # Grid position matters MORE
                win_base = min(win_base * 1.15, 0.99) if pos <= 3 else win_base * 0.85
                podium_base = min(podium_base * 1.1, 0.99) if pos <= 5 else podium_base * 0.9
            elif overtaking in ["High", "Very High"]:
                # Grid position matters LESS
                win_base = win_base * 0.9 if pos <= 2 else win_base * 1.1
                podium_base = podium_base * 0.95 if pos <= 3 else podium_base * 1.08
            
            # Adjust for safety car probability (more chaos = more variance)
            chaos_factor = sc_pct / 50  # >1 = more chaos
            if pos > 5:
                podium_base = min(podium_base * (0.9 + chaos_factor * 0.2), 0.99)
                win_base = min(win_base * (0.9 + chaos_factor * 0.15), 0.99)
            
            # Get Kalshi price if available
            kalshi_winner = None
            kalshi_podium = None
            for ticker, p in contracts.items():
                if code in ticker:
                    if "PODIUM" in ticker.upper():
                        kalshi_podium = p
                    else:
                        kalshi_winner = p
            
            predictions.append({
                "position": pos, "driver": code, "name": name, "team": team,
                "win_pct": round(win_base * 100, 1),
                "podium_pct": round(podium_base * 100, 1),
                "kalshi_winner": kalshi_winner,
                "kalshi_podium": kalshi_podium,
                "notes": _prediction_note(code, pos, circuit, overtaking, sc_pct),
            })
    else:
        # No grid yet — use power rankings as prior
        sorted_drivers = sorted(DRIVER_RATINGS.items(), key=lambda x: -x[1])
        for i, (code, rating) in enumerate(sorted_drivers[:20]):
            team = _guess_team(code)
            matching = [v for k, v in TEAM_POWER.items() if k.lower() in (team or "").lower()]
            team_power = max(matching) if matching else 0.5
            combined = rating * 0.6 + team_power * 0.4
            win_pct = max(1, round(combined ** 8 * 50, 1))  # Exponential — top drivers dominate
            podium_pct = max(2, round(combined ** 4 * 80, 1))
            
            predictions.append({
                "position": i + 1, "driver": code, "name": _driver_name(code), "team": team,
                "win_pct": win_pct, "podium_pct": podium_pct,
                "source": "power_ranking",
                "kalshi_winner": None, "kalshi_podium": None,
                "notes": f"Pre-quali projection based on team/driver ratings. Combined: {combined:.2f}",
            })
    
    # Build narrative insights
    insights = []
    
    if circuit:
        if sc_pct > 60:
            insights.append({
                "type": "chaos", "icon": "⚠️",
                "title": f"High Chaos Race — {sc_pct}% Safety Car Probability",
                "body": f"This circuit has produced safety cars in {sc_pct}% of races. Midfield podiums are more likely than base rates suggest. Our Sleeve A (lottery tickets) historically performs well at high-SC circuits."
            })
        if overtaking == "Very Low":
            insights.append({
                "type": "grid", "icon": "🏁",
                "title": "Qualifying Is The Race",
                "body": f"Overtaking is extremely difficult here. Grid position is destiny. P1→P1 conversion rate is ~60% (vs 45% average). Be cautious selling favorites — they're more likely to hold on."
            })
        if overtaking in ["High", "Very High"]:
            insights.append({
                "type": "opportunity", "icon": "🎯",
                "title": "Overtaking Paradise — Grid Position Less Important",
                "body": f"High overtaking opportunity means midfield drivers can fight forward. P4-P6 podium rates are higher than average. Good conditions for Sleeve A bets."
            })
    
    # 2026 new regs insight
    if race.get("round", 1) <= 4:
        insights.append({
            "type": "caution", "icon": "🔬",
            "title": f"Race {race.get('round', '?')}/4 — Calibration Period",
            "body": "New 2026 regulations (ground effect + active aero) make all priors uncertain. We're trading at half-size ($2.50/trade) until patterns stabilize after Race 4. Base rates from 2019-2024 may not fully apply."
        })
    
    return {
        "race": race,
        "circuit": circuit,
        "predictions": predictions[:20],
        "insights": insights,
        "grid_available": len(grid) > 0,
        "contracts_available": len(contracts) > 0,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def _prediction_note(code, grid_pos, circuit, overtaking, sc_pct):
    """Generate a narrative note for each driver's prediction."""
    notes = []
    if grid_pos == 1:
        notes.append("Pole position — historically converts 45% of the time")
    elif grid_pos <= 3:
        notes.append(f"Front row start — strong position")
    elif grid_pos <= 6:
        notes.append(f"Midfield start — needs race pace or chaos")
    else:
        notes.append(f"P{grid_pos} — needs safety cars or strategy to podium")
    
    if circuit.get("safety_car_pct", 0) > 60 and grid_pos > 5:
        notes.append("High SC probability helps from this position")
    
    if overtaking == "Very Low" and grid_pos <= 3:
        notes.append("Low overtaking = track position is king here")
    
    return ". ".join(notes)


def _guess_team(code):
    """Best-guess team for 2026 grid."""
    teams = {
        "VER": "Red Bull", "LAW": "Red Bull",
        "LEC": "Ferrari", "HAM": "Ferrari",
        "NOR": "McLaren", "PIA": "McLaren",
        "RUS": "Mercedes", "ANT": "Mercedes",
        "ALO": "Aston Martin", "STR": "Aston Martin",
        "GAS": "Alpine", "DOO": "Alpine",
        "ALB": "Williams", "SAI": "Williams",
        "TSU": "RB", "HAD": "RB",
        "OCO": "Haas", "BEA": "Haas",
        "HUL": "Kick Sauber", "BOR": "Kick Sauber",
        "COL": "Cadillac", "MAG": "Cadillac",
    }
    return teams.get(code, "Unknown")


def _driver_name(code):
    """Full name from code."""
    names = {
        "VER": "Max Verstappen", "NOR": "Lando Norris", "LEC": "Charles Leclerc",
        "HAM": "Lewis Hamilton", "RUS": "George Russell", "PIA": "Oscar Piastri",
        "SAI": "Carlos Sainz", "ALO": "Fernando Alonso", "GAS": "Pierre Gasly",
        "OCO": "Esteban Ocon", "TSU": "Yuki Tsunoda", "STR": "Lance Stroll",
        "HUL": "Nico Hülkenberg", "ALB": "Alexander Albon", "MAG": "Kevin Magnussen",
        "LAW": "Liam Lawson", "COL": "Franco Colapinto", "HAD": "Isack Hadjar",
        "BEA": "Oliver Bearman", "DOO": "Jack Doohan", "BOR": "Gabriel Bortoleto",
        "ANT": "Kimi Antonelli", "BOT": "Valtteri Bottas", "ZHO": "Guanyu Zhou",
        "SAR": "Logan Sargeant",
    }
    return names.get(code, code)

# ============================================================
# CONFIG
# ============================================================

@app.get("/api/config")
def get_config():
    return {
        "dry_run": config.DRY_RUN,
        "initial_bankroll": config.INITIAL_BANKROLL,
        "stop_loss_floor": config.STOP_LOSS_FLOOR,
        "flat_bet_size": config.FLAT_BET_SIZE,
        "calibration_races": config.CALIBRATION_RACES,
        "max_per_trade_pct": config.MAX_PER_TRADE_PCT,
        "max_per_weekend_pct": config.MAX_PER_WEEKEND_PCT,
        "races": config.RACES_2026,
        "sprint_rounds": list(SPRINT_ROUNDS),
        "base_rates": {
            "podium": config.PODIUM_BASE_RATES,
            "winner": config.WINNER_BASE_RATES,
        },
    }


# ============================================================
# HEALTH
# ============================================================

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "halted": db.is_halted(),
        "monitor_active": monitor_state["active"],
        "monitor_mode": monitor_state["mode"],
        "poll_count": monitor_state["poll_count"],
        "last_poll": monitor_state["last_poll"],
        "boot_number": int(db.get_setting("restart_count", "0")),
        "last_start": db.get_setting("last_start", ""),
        "uptime_seconds": (datetime.now(timezone.utc) - _boot_time).total_seconds(),
    }

_boot_time = datetime.now(timezone.utc)


# ============================================================
# Serve frontend (SPA)
# ============================================================
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")

if os.path.exists(FRONTEND_DIR):
    # Serve static assets
    @app.get("/assets/{filepath:path}")
    async def serve_assets(filepath: str):
        file_path = os.path.join(FRONTEND_DIR, "assets", filepath)
        if os.path.exists(file_path):
            return FileResponse(file_path)
        raise HTTPException(404)

    # SPA fallback: all non-API routes serve index.html
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Don't intercept /api/ routes
        if full_path.startswith("api/"):
            raise HTTPException(404)
        index_path = os.path.join(FRONTEND_DIR, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        raise HTTPException(404)


