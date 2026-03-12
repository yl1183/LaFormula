"""
Strategy Laboratory — systematic exploration of every plausible edge.
All strategies use ONLY post-qualifying, pre-race information.
"""
import csv, math, json
from pathlib import Path
from collections import defaultdict
import numpy as np

def load_universe():
    rows = []
    with open(Path(__file__).parent / 'trade_universe.csv') as f:
        for r in csv.DictReader(f):
            r['round'] = int(r['round'])
            r['grid_pos'] = int(r['grid_pos']) if r['grid_pos'] else None
            r['finish_pos'] = int(r['finish_pos']) if r['finish_pos'] else None
            r['outcome'] = int(r['outcome'])
            r['yes_vwap'] = float(r['yes_vwap'])
            r['no_vwap'] = float(r['no_vwap'])
            r['volume'] = float(r['volume'])
            r['n_trades'] = int(r['n_trades'])
            rows.append(r)
    return rows

# ── KALSHI FEE MODEL ──
# Kalshi charges fee on PROFIT only: 7% of profit (capped)
# If you buy YES at 40¢ and win: payout=100¢, profit=60¢, fee=4.2¢, net=55.8¢
# If you buy YES at 40¢ and lose: payout=0, loss=40¢, fee=0
# If you buy NO at 60¢ and win: payout=100¢, profit=40¢, fee=2.8¢, net=37.2¢
def net_pnl_per_contract(side, price, outcome, fee_rate=0.07):
    """PnL per $1 risked, after fees."""
    if side == 'YES':
        cost = price
        if outcome == 1:
            profit = (1.0 - price)
            fee = profit * fee_rate
            return (profit - fee) / cost  # return per dollar risked
        else:
            return -1.0  # lose entire stake
    elif side == 'NO':
        cost = 1.0 - price  # cost to buy NO = 1 - yes_price
        if outcome == 0:
            profit = price  # NO wins, profit = yes_price
            fee = profit * fee_rate
            return (profit - fee) / cost
        else:
            return -1.0
    return 0

def kelly_fraction(p_win, b, fraction=0.25):
    """Quarter-Kelly. b = net payout ratio (profit/risk)."""
    if b <= 0:
        return 0
    edge = p_win * b - (1 - p_win)
    if edge <= 0:
        return 0
    kelly = edge / b
    return max(0, min(kelly * fraction, 0.15))  # cap at 15%

# ── BASE RATES (2019-2024, from our earlier analysis) ──
BASE_WIN_RATE = {
    1: 0.381, 2: 0.157, 3: 0.102, 4: 0.085, 5: 0.051, 6: 0.034,
    7: 0.034, 8: 0.034, 9: 0.017, 10: 0.017, 11: 0.017, 12: 0.017,
    13: 0.0, 14: 0.017, 15: 0.0, 16: 0.0, 17: 0.0, 18: 0.017,
    19: 0.0, 20: 0.0
}
BASE_PODIUM_RATE = {
    1: 0.746, 2: 0.576, 3: 0.508, 4: 0.373, 5: 0.271, 6: 0.186,
    7: 0.153, 8: 0.136, 9: 0.085, 10: 0.085, 11: 0.051, 12: 0.034,
    13: 0.034, 14: 0.034, 15: 0.017, 16: 0.017, 17: 0.0, 18: 0.017,
    19: 0.0, 20: 0.0
}

def run_backtest(universe, signal_fn, sizing_fn, label="Strategy"):
    """
    Generic backtest engine.
    signal_fn(row) -> ('YES', edge) or ('NO', edge) or None
    sizing_fn(bankroll, edge, price, side) -> dollars to risk
    """
    bankroll = 100.0
    trades = []
    equity_curve = [(0, bankroll)]
    
    # Process race by race (chronological)
    by_round = defaultdict(list)
    for r in universe:
        by_round[r['round']].append(r)
    
    for rnd in sorted(by_round.keys()):
        opportunities = by_round[rnd]
        round_trades = []
        
        for row in opportunities:
            signal = signal_fn(row)
            if signal is None:
                continue
            side, edge = signal
            
            size = sizing_fn(bankroll, edge, row['yes_vwap'], side)
            if size < 0.50:  # minimum $0.50 trade
                continue
            
            pnl_pct = net_pnl_per_contract(side, row['yes_vwap'], row['outcome'])
            pnl = size * pnl_pct
            
            bankroll += pnl
            
            round_trades.append({
                'round': rnd,
                'race': row['race_name'],
                'market': row['market_type'],
                'driver': row['driver'],
                'grid': row['grid_pos'],
                'finish': row['finish_pos'],
                'side': side,
                'price': row['yes_vwap'],
                'edge': edge,
                'size': size,
                'outcome': row['outcome'],
                'pnl': pnl,
                'bankroll': bankroll,
            })
        
        trades.extend(round_trades)
        if round_trades:
            equity_curve.append((rnd, bankroll))
    
    # Stats
    if not trades:
        return {'label': label, 'trades': 0, 'final': bankroll, 'ret': 0}
    
    wins = sum(1 for t in trades if t['pnl'] > 0)
    pnls = [t['pnl'] for t in trades]
    returns = [t['pnl'] / max(t['size'], 0.01) for t in trades]
    
    peak = 100
    max_dd = 0
    for t in trades:
        peak = max(peak, t['bankroll'])
        dd = (peak - t['bankroll']) / peak
        max_dd = max(max_dd, dd)
    
    avg_ret = np.mean(returns)
    std_ret = np.std(returns) if len(returns) > 1 else 1
    sharpe = avg_ret / std_ret * np.sqrt(len(set(t['round'] for t in trades))) if std_ret > 0 else 0
    
    return {
        'label': label,
        'trades': len(trades),
        'wins': wins,
        'losses': len(trades) - wins,
        'hit_rate': wins / len(trades),
        'final': bankroll,
        'ret': (bankroll - 100) / 100,
        'max_dd': max_dd,
        'sharpe': sharpe,
        'avg_pnl': np.mean(pnls),
        'total_pnl': sum(pnls),
        'trade_log': trades,
        'equity_curve': equity_curve,
    }


# ═══════════════════════════════════════════════════════════
# STRATEGY DEFINITIONS
# ═══════════════════════════════════════════════════════════

def make_base_rate_signal(market_type, threshold, side_filter=None):
    """Signal based on base rate vs market price."""
    def signal_fn(row):
        if row['market_type'] != market_type:
            return None
        gp = row['grid_pos']
        if gp is None or gp > 20:
            return None
        
        if market_type == 'RACE':
            base = BASE_WIN_RATE.get(gp, 0)
        elif market_type == 'RACEPODIUM':
            base = BASE_PODIUM_RATE.get(gp, 0)
        else:
            return None
        
        yes_price = row['yes_vwap']
        
        # Overpriced → sell (buy NO)
        if yes_price > base + threshold:
            if side_filter and side_filter != 'NO':
                return None
            edge = yes_price - base
            return ('NO', edge)
        
        # Underpriced → buy YES
        if yes_price < base - threshold:
            if side_filter and side_filter != 'YES':
                return None
            edge = base - yes_price
            return ('YES', edge)
        
        return None
    return signal_fn

def make_kelly_sizing(fraction=0.25, max_pct=0.15):
    """Kelly-based sizing."""
    def sizing_fn(bankroll, edge, price, side):
        if side == 'YES':
            cost = price
            b = (1.0 - price) * 0.93 / cost  # net of fees
            p_est = price + edge  # our estimate of true prob
        else:
            cost = 1.0 - price
            b = price * 0.93 / cost
            p_est = 1.0 - price + edge
        
        p_est = min(max(p_est, 0.01), 0.99)
        k = kelly_fraction(p_est, b, fraction)
        return min(bankroll * k, bankroll * max_pct)
    return sizing_fn

def make_flat_sizing(pct=0.05):
    """Flat percentage of bankroll."""
    def sizing_fn(bankroll, edge, price, side):
        return bankroll * pct
    return sizing_fn

def make_grid_filter_signal(inner_signal_fn, grid_range):
    """Wrap a signal to only fire for specific grid positions."""
    def signal_fn(row):
        gp = row['grid_pos']
        if gp is None or gp < grid_range[0] or gp > grid_range[1]:
            return None
        return inner_signal_fn(row)
    return signal_fn

def make_volume_filter_signal(inner_signal_fn, min_volume=50):
    """Only trade liquid contracts."""
    def signal_fn(row):
        if row['volume'] < min_volume:
            return None
        return inner_signal_fn(row)
    return signal_fn

# ── Market maker / price-only strategies ──
def make_price_range_signal(market_type, buy_below=None, sell_above=None):
    """Pure price-level strategy — buy cheap, sell expensive."""
    def signal_fn(row):
        if row['market_type'] != market_type:
            return None
        p = row['yes_vwap']
        if sell_above and p > sell_above:
            return ('NO', p - sell_above)
        if buy_below and p < buy_below:
            return ('YES', buy_below - p)
        return None
    return signal_fn


if __name__ == '__main__':
    universe = load_universe()
    print(f"Trade universe: {len(universe)} opportunities across {len(set(r['round'] for r in universe))} races\n")
    
    strategies = []
    
    # ── 1. Base rate strategies (various thresholds) ──
    for thresh in [0.0, 0.03, 0.05, 0.08, 0.10, 0.15]:
        for mkt in ['RACE', 'RACEPODIUM']:
            for side in [None, 'YES', 'NO']:
                side_label = side or 'BOTH'
                label = f"BaseRate_{mkt}_{side_label}_t{int(thresh*100)}"
                sig = make_base_rate_signal(mkt, thresh, side)
                sig = make_volume_filter_signal(sig, min_volume=20)
                strategies.append((label, sig, make_kelly_sizing(0.25, 0.10)))
    
    # ── 2. Grid-filtered base rate ──
    for grid_lo, grid_hi, glabel in [(1,3,'P1-3'), (4,6,'P4-6'), (7,10,'P7-10'), (1,1,'P1'), (2,3,'P2-3')]:
        for mkt in ['RACE', 'RACEPODIUM']:
            for side in [None, 'NO', 'YES']:
                side_label = side or 'BOTH'
                inner = make_base_rate_signal(mkt, 0.05, side)
                inner = make_volume_filter_signal(inner, 20)
                sig = make_grid_filter_signal(inner, (grid_lo, grid_hi))
                label = f"Grid_{glabel}_{mkt}_{side_label}_t5"
                strategies.append((label, sig, make_kelly_sizing(0.25, 0.10)))
    
    # ── 3. Price-level strategies ──
    for sell_thresh in [0.30, 0.40, 0.50]:
        sig = make_volume_filter_signal(
            make_price_range_signal('RACE', sell_above=sell_thresh), 20)
        strategies.append((f"SellExpensive_RACE_{int(sell_thresh*100)}",
                          sig, make_kelly_sizing(0.25, 0.10)))
    
    for buy_thresh in [0.05, 0.08, 0.10]:
        sig = make_volume_filter_signal(
            make_price_range_signal('RACEPODIUM', buy_below=buy_thresh), 20)
        strategies.append((f"BuyCheap_PODIUM_{int(buy_thresh*100)}",
                          sig, make_kelly_sizing(0.25, 0.10)))
    
    # ── 4. Flat sizing variants of best candidates ──
    for mkt in ['RACE', 'RACEPODIUM']:
        for side in ['NO', 'YES']:
            for flat_pct in [0.03, 0.05]:
                sig = make_volume_filter_signal(
                    make_base_rate_signal(mkt, 0.05, side), 20)
                label = f"Flat{int(flat_pct*100)}_{mkt}_{side}_t5"
                strategies.append((label, sig, make_flat_sizing(flat_pct)))
    
    # ── RUN ALL ──
    results = []
    for label, sig_fn, size_fn in strategies:
        res = run_backtest(universe, sig_fn, size_fn, label)
        results.append(res)
    
    # Sort by return
    results.sort(key=lambda x: x['ret'], reverse=True)
    
    # Print top 30
    print(f"{'Strategy':<45} {'Trades':>6} {'Win%':>6} {'Return':>8} {'Final$':>8} {'MaxDD':>7} {'Sharpe':>7}")
    print("=" * 95)
    for r in results[:40]:
        if r['trades'] == 0:
            continue
        print(f"{r['label']:<45} {r['trades']:>6} {r.get('hit_rate',0):>5.1%} {r['ret']:>+7.1%} "
              f"${r['final']:>7.2f} {r.get('max_dd',0):>6.1%} {r.get('sharpe',0):>+6.2f}")
    
    print(f"\n{'─'*95}")
    print("WORST 10:")
    for r in results[-10:]:
        if r['trades'] == 0:
            continue
        print(f"{r['label']:<45} {r['trades']:>6} {r.get('hit_rate',0):>5.1%} {r['ret']:>+7.1%} "
              f"${r['final']:>7.2f} {r.get('max_dd',0):>6.1%} {r.get('sharpe',0):>+6.2f}")
    
    # ── Detailed trade log for top 3 ──
    print(f"\n{'='*95}")
    print("DETAILED TRADE LOGS — TOP 3 STRATEGIES")
    print(f"{'='*95}")
    
    for r in results[:3]:
        if r['trades'] == 0:
            continue
        print(f"\n▶ {r['label']} — {r['trades']} trades, {r['ret']:+.1%}, ${r['final']:.2f}")
        print(f"  {'Rd':>3} {'Race':<15} {'Mkt':<12} {'Driver':<5} {'G':>2}→{'F':>2} {'Side':<4} {'Price':>6} {'Size':>6} {'PnL':>7} {'Bank':>8}")
        for t in r['trade_log']:
            print(f"  {t['round']:>3} {t['race']:<15} {t['market']:<12} {t['driver']:<5} "
                  f"{t['grid'] or '?':>2}→{t['finish'] or '?':>2} {t['side']:<4} "
                  f"{t['price']:>5.2f}¢ ${t['size']:>5.2f} {t['pnl']:>+6.2f} ${t['bankroll']:>7.2f}")

    # Save full results
    summary = []
    for r in results:
        s = {k: v for k, v in r.items() if k != 'trade_log' and k != 'equity_curve'}
        summary.append(s)
    
    with open(Path(__file__).parent / 'strategy_results.json', 'w') as f:
        json.dump(summary, f, indent=2, default=str)
    
    print(f"\n\nSaved {len(results)} strategy results to strategy_results.json")
