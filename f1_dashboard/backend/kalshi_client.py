"""Kalshi API client with RSA-PSS auth. Thin wrapper.

Includes:
- Balance, markets, positions (read-only)
- Order placement (respects DRY_RUN)
- Order status checking (fill verification)
- Order cancellation
- Portfolio reconciliation
"""
import os, time, json, base64, httpx
from datetime import datetime, timezone
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from config import KALSHI_API_KEY, KALSHI_PEM_PATH, KALSHI_BASE_URL, DRY_RUN


def _load_key():
    if not KALSHI_PEM_PATH or not os.path.exists(KALSHI_PEM_PATH):
        return None
    with open(KALSHI_PEM_PATH, "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None)


def _sign(method: str, path: str, timestamp_ms: int) -> str:
    key = _load_key()
    if not key:
        return ""
    # Strip query parameters for signing (Kalshi docs requirement)
    sign_path = path.split("?")[0]
    # Message format: timestamp + method + full_path (with /trade-api/v2 prefix)
    message = f"{timestamp_ms}{method}/trade-api/v2{sign_path}".encode()
    sig = key.sign(message, padding.PSS(
        mgf=padding.MGF1(hashes.SHA256()),
        salt_length=32  # SHA256 digest length; Kalshi requires this, not MAX_LENGTH
    ), hashes.SHA256())
    return base64.b64encode(sig).decode()


def _headers(method: str, path: str) -> dict:
    ts = int(datetime.now(timezone.utc).timestamp() * 1000)
    return {
        "KALSHI-ACCESS-KEY": KALSHI_API_KEY,
        "KALSHI-ACCESS-SIGNATURE": _sign(method, path, ts),
        "KALSHI-ACCESS-TIMESTAMP": str(ts),
        "Content-Type": "application/json",
    }


def get_balance() -> dict:
    """Get account balance. Works even in DRY_RUN (read-only)."""
    if not KALSHI_API_KEY:
        return {"balance": None, "dry_run": True}
    path = "/portfolio/balance"
    url = KALSHI_BASE_URL + path
    r = httpx.get(url, headers=_headers("GET", path), timeout=10)
    r.raise_for_status()
    return r.json()


def get_markets(event_ticker: str) -> list[dict]:
    """Get all markets for an event. Works even in DRY_RUN (read-only)."""
    if not KALSHI_API_KEY:
        return []
    path = f"/markets?event_ticker={event_ticker}&limit=100"
    url = KALSHI_BASE_URL + path
    r = httpx.get(url, headers=_headers("GET", path), timeout=10)
    r.raise_for_status()
    return r.json().get("markets", [])


def get_event(event_ticker: str) -> dict:
    """Get event details."""
    if not KALSHI_API_KEY:
        return {}
    path = f"/events/{event_ticker}"
    url = KALSHI_BASE_URL + path
    r = httpx.get(url, headers=_headers("GET", path), timeout=10)
    r.raise_for_status()
    return r.json()


def search_events(query: str) -> list[dict]:
    """Search for events by keyword."""
    if not KALSHI_API_KEY:
        return []
    path = f"/events?status=open&with_nested_markets=true&limit=50"
    url = KALSHI_BASE_URL + path
    r = httpx.get(url, headers=_headers("GET", path), timeout=10)
    r.raise_for_status()
    return r.json().get("events", [])


def get_orderbook(ticker: str) -> dict:
    """Get orderbook for a specific market ticker. Works even in DRY_RUN (read-only)."""
    if not KALSHI_API_KEY:
        return {}
    path = f"/markets/{ticker}/orderbook"
    url = KALSHI_BASE_URL + path
    r = httpx.get(url, headers=_headers("GET", path), timeout=10)
    r.raise_for_status()
    return r.json()


def get_market(ticker: str) -> dict:
    """Get a single market's details."""
    if not KALSHI_API_KEY:
        return {}
    path = f"/markets/{ticker}"
    url = KALSHI_BASE_URL + path
    r = httpx.get(url, headers=_headers("GET", path), timeout=10)
    r.raise_for_status()
    return r.json()


def place_order(ticker: str, side: str, contracts: int, price_cents: int) -> dict:
    """
    Place a limit order.
    side: "yes" or "no"
    price_cents: price in cents (1-99)
    """
    if DRY_RUN:
        return {
            "dry_run": True,
            "ticker": ticker,
            "side": side,
            "contracts": contracts,
            "price_cents": price_cents,
        }
    path = "/portfolio/orders"
    url = KALSHI_BASE_URL + path
    body = {
        "ticker": ticker,
        "action": "buy",
        "side": side,
        "count": contracts,
        "type": "limit",
        "yes_price": price_cents if side == "yes" else None,
        "no_price": price_cents if side == "no" else None,
    }
    body = {k: v for k, v in body.items() if v is not None}
    r = httpx.post(url, headers=_headers("POST", path), json=body, timeout=10)
    r.raise_for_status()
    return r.json()


# ============================================================
# ORDER STATUS / FILL VERIFICATION
# ============================================================

def get_order(order_id: str) -> dict:
    """Get a specific order's status. Used for fill verification.
    
    Returns order dict with status: 'resting', 'canceled', 'executed', 'pending'.
    Key fields:
    - status: order status
    - remaining_count: unfilled contracts
    - action, side, ticker, etc.
    """
    if DRY_RUN or not KALSHI_API_KEY:
        return {"dry_run": True, "order_id": order_id, "status": "executed", "remaining_count": 0}
    path = f"/portfolio/orders/{order_id}"
    url = KALSHI_BASE_URL + path
    r = httpx.get(url, headers=_headers("GET", path), timeout=10)
    r.raise_for_status()
    return r.json().get("order", r.json())


def get_orders(ticker: str = None, status: str = None) -> list[dict]:
    """Get all orders, optionally filtered by ticker and/or status.
    
    status: 'resting' | 'canceled' | 'executed' | 'pending'
    """
    if DRY_RUN or not KALSHI_API_KEY:
        return []
    params = []
    if ticker:
        params.append(f"ticker={ticker}")
    if status:
        params.append(f"status={status}")
    query = "&".join(params)
    path = f"/portfolio/orders{'?' + query if query else ''}"
    url = KALSHI_BASE_URL + path
    r = httpx.get(url, headers=_headers("GET", path), timeout=10)
    r.raise_for_status()
    return r.json().get("orders", [])


def cancel_order(order_id: str) -> dict:
    """Cancel a resting (unfilled) order.
    
    Returns the canceled order dict or raises on failure.
    Only works for orders with status='resting'.
    """
    if DRY_RUN:
        return {"dry_run": True, "order_id": order_id, "status": "canceled"}
    if not KALSHI_API_KEY:
        return {"error": "No API key"}
    path = f"/portfolio/orders/{order_id}"
    url = KALSHI_BASE_URL + path
    r = httpx.delete(url, headers=_headers("DELETE", path), timeout=10)
    r.raise_for_status()
    return r.json()


def get_fills(ticker: str = None, limit: int = 100) -> list[dict]:
    """Get recent fills (executed trades).
    
    Returns list of fill objects with:
    - ticker, side, action, count, price, created_time, etc.
    """
    if DRY_RUN or not KALSHI_API_KEY:
        return []
    params = [f"limit={limit}"]
    if ticker:
        params.append(f"ticker={ticker}")
    query = "&".join(params)
    path = f"/portfolio/fills?{query}"
    url = KALSHI_BASE_URL + path
    r = httpx.get(url, headers=_headers("GET", path), timeout=10)
    r.raise_for_status()
    return r.json().get("fills", [])


# ============================================================
# POSITION RECONCILIATION
# ============================================================

def get_positions() -> list[dict]:
    """Get current open positions. Works even in DRY_RUN (read-only)."""
    if not KALSHI_API_KEY:
        return []
    path = "/portfolio/positions"
    url = KALSHI_BASE_URL + path
    r = httpx.get(url, headers=_headers("GET", path), timeout=10)
    r.raise_for_status()
    return r.json().get("market_positions", [])


def reconcile_positions(internal_trades: list[dict]) -> dict:
    """Compare internal tracked positions with Kalshi's actual positions.
    
    Returns:
    {
        "matched": [...],      # Positions that agree
        "kalshi_only": [...],  # On Kalshi but not tracked internally
        "internal_only": [...],# Tracked internally but not on Kalshi
        "mismatched": [...],   # Different quantities
        "healthy": bool,
    }
    """
    if DRY_RUN or not KALSHI_API_KEY:
        return {
            "matched": [], "kalshi_only": [], "internal_only": [],
            "mismatched": [], "healthy": True, "dry_run": True,
        }
    
    try:
        kalshi_positions = get_positions()
    except Exception as e:
        return {"error": str(e), "healthy": False}
    
    # Build lookup: ticker -> position data
    kalshi_map = {}
    for pos in kalshi_positions:
        ticker = pos.get("ticker", "")
        kalshi_map[ticker] = pos
    
    internal_map = {}
    for trade in internal_trades:
        ticker = trade.get("ticker", "")
        if ticker:
            internal_map[ticker] = trade
    
    matched = []
    mismatched = []
    kalshi_only = []
    internal_only = []
    
    # Check kalshi positions against internal
    for ticker, kpos in kalshi_map.items():
        if ticker in internal_map:
            # Both exist — compare
            k_count = abs(kpos.get("total_traded", 0))
            i_trade = internal_map[ticker]
            i_count = i_trade.get("contracts", 0)
            if k_count == i_count:
                matched.append({"ticker": ticker, "contracts": k_count})
            else:
                mismatched.append({
                    "ticker": ticker,
                    "kalshi_contracts": k_count,
                    "internal_contracts": i_count,
                })
        else:
            kalshi_only.append({"ticker": ticker, "position": kpos})
    
    # Check internal trades not on Kalshi
    for ticker, itrade in internal_map.items():
        if ticker not in kalshi_map:
            internal_only.append({"ticker": ticker, "trade": itrade})
    
    healthy = len(mismatched) == 0 and len(kalshi_only) == 0 and len(internal_only) == 0
    
    return {
        "matched": matched,
        "kalshi_only": kalshi_only,
        "internal_only": internal_only,
        "mismatched": mismatched,
        "healthy": healthy,
    }
