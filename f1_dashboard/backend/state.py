"""JSON-file state persistence. All money tracking lives here."""
import json, os, copy
from datetime import datetime, timezone

STATE_FILE = os.getenv("STATE_FILE", "data/state.json")

DEFAULT_STATE = {
    "bankroll": 100.0,
    "initial_bankroll": 100.0,
    "peak_bankroll": 100.0,
    "current_race": 0,
    "positions": [],      # open trades
    "history": [],        # settled trades
    "pnl_curve": [{"date": "2026-03-04", "bankroll": 100.0}],
    "halted": False,
    "halt_reason": None,
}

def _ensure_dir():
    os.makedirs(os.path.dirname(STATE_FILE) or "data", exist_ok=True)

def load() -> dict:
    _ensure_dir()
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return copy.deepcopy(DEFAULT_STATE)

def save(state: dict):
    _ensure_dir()
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def reset():
    save(copy.deepcopy(DEFAULT_STATE))
    return load()

def record_trade(state, trade: dict):
    """Add an open position."""
    trade["opened_at"] = datetime.now(timezone.utc).isoformat()
    state["positions"].append(trade)
    state["bankroll"] -= trade["risk"]
    save(state)

def settle_trade(state, trade_id: str, won: bool):
    """Settle a position."""
    pos = None
    for i, p in enumerate(state["positions"]):
        if p["id"] == trade_id:
            pos = state["positions"].pop(i)
            break
    if not pos:
        return None
    
    pos["settled_at"] = datetime.now(timezone.utc).isoformat()
    pos["won"] = won
    if won:
        pos["pnl"] = pos["potential_profit"]
        state["bankroll"] += pos["risk"] + pos["potential_profit"]
    else:
        pos["pnl"] = -pos["risk"]
    
    state["history"].append(pos)
    state["peak_bankroll"] = max(state["peak_bankroll"], state["bankroll"])
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    state["pnl_curve"].append({"date": now, "bankroll": round(state["bankroll"], 2)})
    save(state)
    return pos
