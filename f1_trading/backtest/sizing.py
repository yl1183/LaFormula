"""
Position sizing module with per-weekend exposure caps.

Key insight: all trades at the same GP are correlated — same weather, same
safety car, same chaos events. A 7-trade weekend with $10 flat stakes puts
$70 at risk, and in the worst case (all lose), that's a 70% drawdown on $100.

This module provides:
1. Flat sizing with weekend caps
2. Kelly sizing with weekend caps
3. Tiered sizing by edge confidence
"""

from collections import defaultdict

# === CONFIG ===
MAX_WEEKEND_EXPOSURE_PCT = 0.30   # max 30% of bankroll at risk per weekend
MAX_SINGLE_TRADE_PCT = 0.15      # max 15% per trade  
MIN_TRADE_SIZE = 0.50            # minimum $0.50 to execute
KELLY_FRACTION = 0.25            # quarter-Kelly
FEE_RATE = 0.07                  # Kalshi 7% profit fee


def kelly_fraction(p_win, b, fraction=KELLY_FRACTION, cap=MAX_SINGLE_TRADE_PCT):
    """Quarter-Kelly sizing. b = net payout / cost."""
    if b <= 0:
        return 0
    edge = p_win * b - (1 - p_win)
    if edge <= 0:
        return 0
    return min(edge / b * fraction, cap)


def size_flat_with_cap(bankroll, trades_this_weekend, flat_amount=10.0):
    """
    Flat sizing with weekend exposure cap.
    
    Args:
        bankroll: current bankroll
        trades_this_weekend: number of trades planned this weekend
        flat_amount: default per-trade amount
    
    Returns:
        per-trade stake (may be reduced to stay under weekend cap)
    """
    max_total = bankroll * MAX_WEEKEND_EXPOSURE_PCT
    if trades_this_weekend * flat_amount > max_total:
        # Reduce per-trade to fit under cap
        per_trade = max_total / trades_this_weekend
    else:
        per_trade = flat_amount
    
    per_trade = min(per_trade, bankroll * MAX_SINGLE_TRADE_PCT)
    return max(per_trade, MIN_TRADE_SIZE) if per_trade >= MIN_TRADE_SIZE else 0


def size_kelly_with_cap(bankroll, signals_this_weekend):
    """
    Kelly sizing with weekend exposure cap.
    
    Args:
        bankroll: current bankroll
        signals_this_weekend: list of dicts with 'edge', 'price', 'side'
    
    Returns:
        list of stakes (same order as signals)
    """
    # First pass: compute raw Kelly sizes
    raw_sizes = []
    for sig in signals_this_weekend:
        edge = sig['edge']
        price = sig['price']
        side = sig['side']
        
        if side == 'YES':
            cost = price
            payout_ratio = (1.0 - price) * (1 - FEE_RATE) / cost
            p_est = min(max(price + edge, 0.01), 0.99)
        else:
            cost = 1.0 - price
            payout_ratio = price * (1 - FEE_RATE) / cost
            p_est = min(max(1 - price + edge, 0.01), 0.99)
        
        k = kelly_fraction(p_est, payout_ratio)
        raw_size = bankroll * k
        raw_sizes.append(raw_size)
    
    # Second pass: enforce weekend cap
    total_raw = sum(raw_sizes)
    max_total = bankroll * MAX_WEEKEND_EXPOSURE_PCT
    
    if total_raw > max_total and total_raw > 0:
        # Scale all positions proportionally
        scale = max_total / total_raw
        stakes = [s * scale for s in raw_sizes]
    else:
        stakes = raw_sizes
    
    # Enforce per-trade cap and minimum
    stakes = [min(s, bankroll * MAX_SINGLE_TRADE_PCT) for s in stakes]
    stakes = [s if s >= MIN_TRADE_SIZE else 0 for s in stakes]
    
    return stakes


def size_tiered(bankroll, signals_this_weekend):
    """
    Tiered sizing: larger bets on higher-edge signals.
    
    Tiers:
        Edge > 0.25: "Strong" — 10% of bankroll
        Edge 0.15-0.25: "Medium" — 6% of bankroll 
        Edge 0.10-0.15: "Weak" — 3% of bankroll
    
    Still subject to weekend cap.
    """
    tier_pcts = {
        'strong': 0.10,  # edge > 0.25
        'medium': 0.06,  # 0.15 < edge <= 0.25
        'weak': 0.03,    # 0.10 < edge <= 0.15
    }
    
    raw_sizes = []
    for sig in signals_this_weekend:
        edge = sig['edge']
        if edge > 0.25:
            pct = tier_pcts['strong']
        elif edge > 0.15:
            pct = tier_pcts['medium']
        elif edge > 0.10:
            pct = tier_pcts['weak']
        else:
            raw_sizes.append(0)
            continue
        raw_sizes.append(bankroll * pct)
    
    # Enforce weekend cap
    total = sum(raw_sizes)
    max_total = bankroll * MAX_WEEKEND_EXPOSURE_PCT
    
    if total > max_total and total > 0:
        scale = max_total / total
        stakes = [s * scale for s in raw_sizes]
    else:
        stakes = raw_sizes
    
    stakes = [min(s, bankroll * MAX_SINGLE_TRADE_PCT) for s in stakes]
    stakes = [s if s >= MIN_TRADE_SIZE else 0 for s in stakes]
    
    return stakes


# === BACKTEST HELPER ===
def backtest_with_weekend_caps(universe, signal_fn, sizing_mode='kelly', bankroll_init=100.0):
    """
    Run backtest with proper weekend exposure management.
    
    sizing_mode: 'kelly', 'flat', or 'tiered'
    """
    from collections import defaultdict
    import numpy as np
    
    bankroll = bankroll_init
    trades = []
    
    # Group by round
    by_round = defaultdict(list)
    for r in universe:
        by_round[r['round']].append(r)
    
    for rnd in sorted(by_round.keys()):
        # First pass: identify all signals this weekend
        weekend_signals = []
        for row in by_round[rnd]:
            sig = signal_fn(row)
            if sig is None:
                continue
            side, edge = sig
            weekend_signals.append({
                'row': row,
                'side': side,
                'edge': edge,
                'price': row['yes_vwap'],
            })
        
        if not weekend_signals:
            continue
        
        # Size all positions together (respecting weekend cap)
        if sizing_mode == 'kelly':
            stakes = size_kelly_with_cap(bankroll, weekend_signals)
        elif sizing_mode == 'flat':
            flat_amt = size_flat_with_cap(bankroll, len(weekend_signals))
            stakes = [flat_amt] * len(weekend_signals)
        elif sizing_mode == 'tiered':
            stakes = size_tiered(bankroll, weekend_signals)
        else:
            raise ValueError(f"Unknown sizing mode: {sizing_mode}")
        
        # Execute trades
        for sig, stake in zip(weekend_signals, stakes):
            if stake <= 0:
                continue
            
            row = sig['row']
            side = sig['side']
            price = row['yes_vwap']
            outcome = row['outcome']
            
            # Compute P&L
            if side == 'YES':
                if outcome == 1:
                    profit = (1.0 - price)
                    fee = profit * FEE_RATE
                    pnl = stake * ((profit - fee) / price)
                else:
                    pnl = -stake
            else:  # NO
                cost = 1.0 - price
                if outcome == 0:
                    profit = price
                    fee = profit * FEE_RATE
                    pnl = stake * ((profit - fee) / cost)
                else:
                    pnl = -stake
            
            bankroll += pnl
            
            trades.append({
                'round': rnd,
                'race': row['race_name'],
                'market': row['market_type'],
                'driver': row['driver'],
                'grid': row['grid_pos'],
                'side': side,
                'price': price,
                'edge': sig['edge'],
                'stake': round(stake, 2),
                'outcome': outcome,
                'pnl': round(pnl, 2),
                'bankroll': round(bankroll, 2),
            })
    
    return trades, bankroll
