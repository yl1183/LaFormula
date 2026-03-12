"""SQLite persistence layer. WAL mode. Single source of truth for all state."""
import sqlite3
import json
import os
import threading
from datetime import datetime, timezone
from contextlib import contextmanager

DB_PATH = os.getenv("DB_PATH", "data/f1trading.db")
_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    """Thread-local connection with WAL mode."""
    if not hasattr(_local, "conn") or _local.conn is None:
        os.makedirs(os.path.dirname(DB_PATH) or "data", exist_ok=True)
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.row_factory = sqlite3.Row
        _local.conn = conn
    return _local.conn


@contextmanager
def get_db():
    conn = _get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def init_db():
    """Create all tables if they don't exist."""
    with get_db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS trades (
            id TEXT PRIMARY KEY,
            sleeve TEXT NOT NULL,
            action TEXT NOT NULL,
            driver TEXT NOT NULL,
            market TEXT NOT NULL,
            grid_pos INTEGER,
            price REAL NOT NULL,
            base_rate REAL NOT NULL,
            edge REAL NOT NULL,
            contracts INTEGER NOT NULL,
            risk REAL NOT NULL,
            potential_profit REAL NOT NULL,
            ticker TEXT,
            label TEXT,
            reasoning TEXT,
            race_name TEXT,
            race_round INTEGER,
            status TEXT NOT NULL DEFAULT 'open',
            won INTEGER,
            pnl REAL,
            kalshi_order_id TEXT,
            kalshi_response TEXT,
            opened_at TEXT NOT NULL,
            settled_at TEXT
        );

        CREATE TABLE IF NOT EXISTS signals (
            id TEXT PRIMARY KEY,
            sleeve TEXT NOT NULL,
            action TEXT NOT NULL,
            driver TEXT NOT NULL,
            market TEXT NOT NULL,
            grid_pos INTEGER,
            price REAL NOT NULL,
            base_rate REAL NOT NULL,
            edge REAL NOT NULL,
            contracts INTEGER NOT NULL,
            risk REAL NOT NULL,
            potential_profit REAL NOT NULL,
            ticker TEXT,
            label TEXT,
            reasoning TEXT,
            race_name TEXT,
            race_round INTEGER,
            acted_on INTEGER NOT NULL DEFAULT 0,
            trade_id TEXT,
            skip_reason TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS price_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            driver TEXT,
            market TEXT,
            yes_price REAL,
            no_price REAL,
            volume INTEGER,
            race_name TEXT,
            race_round INTEGER,
            captured_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            detail TEXT,
            metadata TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS f1_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER NOT NULL,
            round INTEGER NOT NULL,
            session_type TEXT NOT NULL,
            data TEXT,
            fetched_at TEXT NOT NULL,
            UNIQUE(year, round, session_type)
        );

        CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
        CREATE INDEX IF NOT EXISTS idx_trades_race ON trades(race_round);
        CREATE INDEX IF NOT EXISTS idx_signals_race ON signals(race_round);
        CREATE INDEX IF NOT EXISTS idx_audit_type ON audit_log(event_type);
        CREATE INDEX IF NOT EXISTS idx_price_ticker ON price_snapshots(ticker, captured_at);
        """)

        # Initialize default settings if not present
        defaults = {
            "bankroll": "100.0",
            "initial_bankroll": "100.0",
            "peak_bankroll": "100.0",
            "halted": "false",
            "halt_reason": "",
            "current_race": "0",
            "kalshi_balance_cents": "",
            "last_kalshi_sync": "",
            "races_completed": "0",
        }
        now = _now()
        for key, value in defaults.items():
            conn.execute(
                "INSERT OR IGNORE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
                (key, value, now),
            )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# === Settings (key-value store) ===

def get_setting(key: str, default: str = "") -> str:
    with get_db() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (key, value, _now()),
        )


def get_bankroll() -> float:
    return float(get_setting("bankroll", "100.0"))


def set_bankroll(amount: float):
    set_setting("bankroll", str(round(amount, 2)))
    peak = float(get_setting("peak_bankroll", "100.0"))
    if amount > peak:
        set_setting("peak_bankroll", str(round(amount, 2)))


def is_halted() -> bool:
    return get_setting("halted", "false") == "true"


def set_halted(halted: bool, reason: str = ""):
    set_setting("halted", "true" if halted else "false")
    set_setting("halt_reason", reason)


# === Trades ===

def open_trade(trade: dict):
    """Record a new open trade."""
    with get_db() as conn:
        conn.execute("""
            INSERT INTO trades (id, sleeve, action, driver, market, grid_pos, price, base_rate,
                edge, contracts, risk, potential_profit, ticker, label, reasoning,
                race_name, race_round, status, kalshi_order_id, kalshi_response, opened_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?, ?)
        """, (
            trade["id"], trade["sleeve"], trade["action"], trade["driver"],
            trade.get("market", ""), trade.get("grid_pos"), trade["price"],
            trade.get("base_rate", 0), trade.get("edge", 0), trade["contracts"],
            trade["risk"], trade["potential_profit"], trade.get("ticker", ""),
            trade.get("label", ""), trade.get("reasoning", ""),
            trade.get("race_name", ""), trade.get("race_round"),
            trade.get("kalshi_order_id", ""),
            json.dumps(trade.get("kalshi_response", {})),
            _now(),
        ))
    # Deduct risk from bankroll
    bankroll = get_bankroll()
    set_bankroll(bankroll - trade["risk"])


def settle_trade(trade_id: str, won: bool) -> dict | None:
    """Settle an open trade."""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM trades WHERE id=? AND status='open'", (trade_id,)).fetchone()
        if not row:
            return None
        trade = dict(row)
        pnl = trade["potential_profit"] if won else -trade["risk"]
        conn.execute(
            "UPDATE trades SET status='settled', won=?, pnl=?, settled_at=? WHERE id=?",
            (1 if won else 0, round(pnl, 2), _now(), trade_id),
        )
    # Update bankroll
    bankroll = get_bankroll()
    if won:
        set_bankroll(bankroll + trade["risk"] + trade["potential_profit"])
    # (if lost, risk was already deducted at open)
    trade["won"] = won
    trade["pnl"] = round(pnl, 2)
    return trade


def get_open_trades() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM trades WHERE status='open' ORDER BY opened_at DESC").fetchall()
        return [dict(r) for r in rows]


def get_trade_history() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM trades WHERE status='settled' ORDER BY settled_at DESC").fetchall()
        return [dict(r) for r in rows]


def get_all_trades() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM trades ORDER BY opened_at DESC").fetchall()
        return [dict(r) for r in rows]


def get_weekend_risk(race_round: int) -> float:
    """Total risk deployed this weekend (open + settled, to prevent re-deploying capital)."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(risk), 0) as total FROM trades WHERE race_round=?",
            (race_round,),
        ).fetchone()
        return row["total"]


# === Signals ===

def record_signal(signal: dict, acted_on: bool = False, trade_id: str = None, skip_reason: str = None):
    with get_db() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO signals (id, sleeve, action, driver, market, grid_pos, price, base_rate,
                edge, contracts, risk, potential_profit, ticker, label, reasoning,
                race_name, race_round, acted_on, trade_id, skip_reason, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            signal["id"], signal["sleeve"], signal["action"], signal["driver"],
            signal.get("market", ""), signal.get("grid_pos"), signal["price"],
            signal.get("base_rate", 0), signal.get("edge", 0), signal["contracts"],
            signal["risk"], signal["potential_profit"], signal.get("ticker", ""),
            signal.get("label", ""), signal.get("reasoning", ""),
            signal.get("race_name", ""), signal.get("race_round"),
            1 if acted_on else 0, trade_id or "", skip_reason or "",
            _now(),
        ))


def get_recent_signals(limit: int = 50) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM signals ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


# === Price Snapshots ===

def record_price_snapshot(snapshot: dict):
    with get_db() as conn:
        conn.execute("""
            INSERT INTO price_snapshots (ticker, driver, market, yes_price, no_price, volume,
                race_name, race_round, captured_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            snapshot.get("ticker", ""), snapshot.get("driver", ""),
            snapshot.get("market", ""), snapshot.get("yes_price"),
            snapshot.get("no_price"), snapshot.get("volume"),
            snapshot.get("race_name", ""), snapshot.get("race_round"),
            _now(),
        ))


def get_price_history(ticker: str = None, limit: int = 100) -> list[dict]:
    with get_db() as conn:
        if ticker:
            rows = conn.execute(
                "SELECT * FROM price_snapshots WHERE ticker=? ORDER BY captured_at DESC LIMIT ?",
                (ticker, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM price_snapshots ORDER BY captured_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]


# === Audit Log ===

def audit(event_type: str, detail: str = "", metadata: dict = None):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO audit_log (event_type, detail, metadata, created_at) VALUES (?, ?, ?, ?)",
            (event_type, detail, json.dumps(metadata) if metadata else "", _now()),
        )


def get_audit_log(event_type: str = None, limit: int = 200) -> list[dict]:
    with get_db() as conn:
        if event_type:
            rows = conn.execute(
                "SELECT * FROM audit_log WHERE event_type=? ORDER BY created_at DESC LIMIT ?",
                (event_type, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM audit_log ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]


# === F1 Sessions ===

def store_f1_session(year: int, round_num: int, session_type: str, data: dict):
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO f1_sessions (year, round, session_type, data, fetched_at) VALUES (?, ?, ?, ?, ?)",
            (year, round_num, session_type, json.dumps(data), _now()),
        )


def get_f1_session(year: int, round_num: int, session_type: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT data FROM f1_sessions WHERE year=? AND round=? AND session_type=?",
            (year, round_num, session_type),
        ).fetchone()
        return json.loads(row["data"]) if row else None


# === State export (for API compatibility) ===

def get_full_state() -> dict:
    """Export full state as dict for the API. Compatible with old state.json format."""
    bankroll = get_bankroll()
    initial = float(get_setting("initial_bankroll", "100.0"))
    peak = float(get_setting("peak_bankroll", "100.0"))
    halted = is_halted()
    halt_reason = get_setting("halt_reason", "")
    kalshi_balance = get_setting("kalshi_balance_cents", "")
    last_sync = get_setting("last_kalshi_sync", "")

    open_trades = get_open_trades()
    history = get_trade_history()

    # Build PnL curve from trade history
    pnl_curve = [{"date": "2026-03-04", "bankroll": initial}]
    running = initial
    for t in sorted(history, key=lambda x: x.get("settled_at", "")):
        pnl = t.get("pnl", 0) or 0
        running += pnl
        pnl_curve.append({
            "date": (t.get("settled_at") or "")[:10],
            "bankroll": round(running, 2),
        })

    return {
        "bankroll": bankroll,
        "initial_bankroll": initial,
        "peak_bankroll": peak,
        "current_race": int(get_setting("current_race", "0")),
        "positions": open_trades,
        "history": history,
        "pnl_curve": pnl_curve,
        "halted": halted,
        "halt_reason": halt_reason if halted else None,
        "kalshi_balance": int(kalshi_balance) / 100.0 if kalshi_balance else None,
        "kalshi_synced": bool(last_sync),
        "last_kalshi_sync": last_sync or None,
    }


def reset_all():
    """Reset everything to defaults."""
    with get_db() as conn:
        conn.execute("DELETE FROM trades")
        conn.execute("DELETE FROM signals")
        conn.execute("DELETE FROM price_snapshots")
        conn.execute("DELETE FROM audit_log")
        conn.execute("DELETE FROM settings")
    init_db()
    audit("SYSTEM", "Full state reset")
    return get_full_state()
