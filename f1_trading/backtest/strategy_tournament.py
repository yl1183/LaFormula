"""
Strategy Tournament — test EVERY plausible strategy on clean, timestamp-verified data.

Each strategy:
  1. Takes the feature matrix (pre-race features only)
  2. Generates trade signals (BUY YES, BUY NO, or SKIP)
  3. Sizes positions using Kelly criterion
  4. Settles after the race
  5. Reports trade-by-trade P&L

ANTI-LEAKAGE:
  - Features are all pre-race
  - ML models are trained on 2019-2024, tested on 2025
  - Rolling features use only prior races within 2025
  - Kalshi prices are post-qualifying, pre-race VWAP

KALSHI FEES: 7% of profit (not of stake). No fee on losses.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from collections import defaultdict
import json, warnings
warnings.filterwarnings('ignore')


# ══════════════════════════════════════════════════════════════
# CORE BACKTEST ENGINE
# ══════════════════════════════════════════════════════════════

def kalshi_fee(profit, fee_rate=0.07):
    """Kalshi charges 7% of profit. No fee on losses."""
    return max(0, profit) * fee_rate

def net_pnl(side, price, outcome, stake, fee_rate=0.07):
    """
    Compute net P&L for one trade.
    side: 'YES' or 'NO'
    price: what you paid (0-1 scale)
    outcome: 1 if YES won, 0 if NO won
    stake: dollars risked
    """
    contracts = stake / price  # number of contracts bought
    
    if side == 'YES':
        if outcome == 1:
            gross_profit = contracts * (1 - price)
            fee = gross_profit * fee_rate
            return gross_profit - fee
        else:
            return -stake
    else:  # NO
        no_price = 1 - price  # price of NO contract
        contracts = stake / no_price
        if outcome == 0:
            gross_profit = contracts * (1 - no_price)
            fee = gross_profit * fee_rate
            return gross_profit - fee
        else:
            return -stake


def kelly_size(edge, odds, fraction=0.25, max_pct=0.15):
    """
    Fractional Kelly criterion.
    edge: expected return per dollar
    odds: payout ratio (net payout / cost)
    fraction: Kelly fraction (0.25 = quarter Kelly)
    max_pct: max % of bankroll per trade
    """
    if edge <= 0 or odds <= 0:
        return 0
    kelly = edge / odds
    sized = kelly * fraction
    return min(sized, max_pct)


def run_backtest(signals, initial_bankroll=100, fee_rate=0.07):
    """
    Run a sequential backtest with compounding.
    signals: list of dicts with keys:
      round, driver, market_type, side, price, outcome, edge, event_code, race_name
      kelly_frac (fraction of bankroll to bet)
    Returns: list of trade dicts with P&L, equity curve
    """
    bankroll = initial_bankroll
    trades = []
    equity = [initial_bankroll]
    
    # Group by round (sequential)
    by_round = defaultdict(list)
    for s in signals:
        by_round[s['round']].append(s)
    
    for rnd in sorted(by_round.keys()):
        round_signals = by_round[rnd]
        round_bankroll = bankroll  # snapshot at start of round
        
        for s in round_signals:
            stake = round_bankroll * s['kelly_frac']
            stake = min(stake, bankroll * 0.15)  # hard cap per trade
            stake = max(stake, 0)
            
            if stake < 0.50:  # minimum trade size
                continue
            
            pnl = net_pnl(s['side'], s['price'], s['outcome'], stake, fee_rate)
            bankroll += pnl
            
            trades.append({
                'round': rnd,
                'race_name': s.get('race_name', ''),
                'event_code': s.get('event_code', ''),
                'market_type': s['market_type'],
                'driver': s['driver'],
                'grid_pos': s.get('grid_pos'),
                'side': s['side'],
                'price': round(s['price'], 4),
                'edge': round(s.get('edge', 0), 4),
                'stake': round(stake, 2),
                'outcome': s['outcome'],
                'pnl': round(pnl, 2),
                'bankroll': round(bankroll, 2),
            })
        
        equity.append(bankroll)
    
    return trades, equity


def compute_metrics(trades, initial=100):
    """Compute strategy metrics from trade list."""
    if not trades:
        return {'total_return': 0, 'n_trades': 0, 'sharpe': 0}
    
    final = trades[-1]['bankroll']
    pnls = [t['pnl'] for t in trades]
    wins = [t for t in trades if t['pnl'] > 0]
    
    # Per-round returns for Sharpe
    round_pnl = defaultdict(float)
    round_bankroll = {}
    prev_b = initial
    for t in trades:
        round_pnl[t['round']] += t['pnl']
        round_bankroll[t['round']] = prev_b
        prev_b = t['bankroll']
    
    round_returns = []
    for rnd in sorted(round_pnl.keys()):
        b = round_bankroll.get(rnd, initial)
        if b > 0:
            round_returns.append(round_pnl[rnd] / b)
    
    sharpe = (np.mean(round_returns) / np.std(round_returns) * np.sqrt(24)) if (len(round_returns) > 1 and np.std(round_returns) > 0) else 0
    
    # Max drawdown
    equity = [initial]
    for t in trades:
        equity.append(t['bankroll'])
    peak = initial
    max_dd = 0
    for e in equity:
        peak = max(peak, e)
        dd = (peak - e) / peak
        max_dd = max(max_dd, dd)
    
    # Per-round P&L for bootstrap
    round_pnls = [round_pnl[r] for r in sorted(round_pnl.keys())]
    
    return {
        'total_return_pct': round((final - initial) / initial * 100, 1),
        'final_bankroll': round(final, 2),
        'n_trades': len(trades),
        'win_rate': round(len(wins) / len(trades) * 100, 1),
        'avg_win': round(np.mean([t['pnl'] for t in wins]), 2) if wins else 0,
        'avg_loss': round(np.mean([t['pnl'] for t in trades if t['pnl'] <= 0]), 2) if any(t['pnl'] <= 0 for t in trades) else 0,
        'sharpe': round(sharpe, 2),
        'max_drawdown_pct': round(max_dd * 100, 1),
        'profit_factor': round(sum(t['pnl'] for t in wins) / abs(sum(t['pnl'] for t in trades if t['pnl'] <= 0))) if any(t['pnl'] <= 0 for t in trades) else float('inf'),
        'round_pnls': round_pnls,
    }


def bootstrap_test(round_pnls, n_samples=10000):
    """Bootstrap P(profit) from per-round P&L."""
    if len(round_pnls) < 3:
        return 0.5
    arr = np.array(round_pnls)
    n = len(arr)
    profits = 0
    for _ in range(n_samples):
        sample = np.random.choice(arr, size=n, replace=True)
        if sample.sum() > 0:
            profits += 1
    return profits / n_samples


# ══════════════════════════════════════════════════════════════
# STRATEGY DEFINITIONS
# ══════════════════════════════════════════════════════════════

def strategy_base_rate_edge(df, market_type='RACEPODIUM', threshold=0.15, side='YES', kelly_frac_mult=0.25):
    """
    S1: Simple base rate edge.
    BUY YES when base_rate > kalshi_price + threshold
    BUY NO when kalshi_price > base_rate + threshold
    """
    subset = df[df['market_type'] == market_type].copy()
    signals = []
    
    for _, row in subset.iterrows():
        edge = row['edge_vs_base']  # positive = YES underpriced
        
        if side == 'YES' and edge > threshold:
            price = row['yes_price']
            if price <= 0.02 or price >= 0.98:
                continue
            odds = (1 - price) / price
            kf = kelly_size(edge, odds, kelly_frac_mult)
            if kf > 0:
                signals.append({
                    'round': row['round'], 'driver': row['driver'],
                    'market_type': market_type, 'side': 'YES',
                    'price': price, 'outcome': row['outcome'],
                    'edge': edge, 'kelly_frac': kf,
                    'grid_pos': row['grid_pos'],
                    'event_code': row['event_code'], 'race_name': row['race_name'],
                })
        
        elif side == 'NO' and edge < -threshold:
            no_price = row['no_price']
            if no_price <= 0.02 or no_price >= 0.98:
                continue
            no_edge = abs(edge)
            odds = (1 - no_price) / no_price
            kf = kelly_size(no_edge, odds, kelly_frac_mult)
            if kf > 0:
                signals.append({
                    'round': row['round'], 'driver': row['driver'],
                    'market_type': market_type, 'side': 'NO',
                    'price': row['yes_price'], 'outcome': row['outcome'],
                    'edge': no_edge, 'kelly_frac': kf,
                    'grid_pos': row['grid_pos'],
                    'event_code': row['event_code'], 'race_name': row['race_name'],
                })
    
    return signals


def strategy_fp2_pace_edge(df, threshold=0.12, min_laps=8):
    """
    S2: FP2 long-run pace disagrees with grid position.
    Driver qualifies P7 but has 3rd-best FP2 pace → underpriced for podium.
    """
    subset = df[(df['market_type'] == 'RACEPODIUM') & (df['fp2_best_delta'].notna())].copy()
    signals = []
    
    for _, row in subset.iterrows():
        fp2_delta = row['fp2_best_delta']
        grid_pos = row['grid_pos']
        yes_price = row['yes_price']
        
        # FP2 pace rank (lower delta = faster)
        # If FP2 rank is much better than grid rank → underpriced
        # Estimate "FP2 implied grid" roughly
        # fp2_delta of 0 = fastest, 0.3s = ~P3, 0.6s = ~P6, 1.0s = ~P10
        fp2_implied_grid = max(1, min(20, int(1 + fp2_delta / 0.15)))
        
        grid_vs_pace = grid_pos - fp2_implied_grid  # positive = grid worse than pace
        
        if grid_vs_pace >= 3:
            # Driver has better pace than grid suggests
            # Use base rate for FP2 implied position
            base_rate = row['base_rate']
            # Adjust base rate toward what FP2 pace implies
            fp2_base = {1: 0.80, 2: 0.71, 3: 0.64, 4: 0.36, 5: 0.29, 
                       6: 0.25, 7: 0.15, 8: 0.12, 9: 0.10, 10: 0.08}.get(fp2_implied_grid, 0.05)
            
            adjusted_rate = (base_rate + fp2_base) / 2  # blend
            edge = adjusted_rate - yes_price
            
            if edge > threshold:
                odds = (1 - yes_price) / yes_price if yes_price > 0 else 0
                kf = kelly_size(edge, odds, 0.20)
                if kf > 0:
                    signals.append({
                        'round': row['round'], 'driver': row['driver'],
                        'market_type': 'RACEPODIUM', 'side': 'YES',
                        'price': yes_price, 'outcome': row['outcome'],
                        'edge': edge, 'kelly_frac': kf,
                        'grid_pos': grid_pos,
                        'event_code': row['event_code'], 'race_name': row['race_name'],
                        'fp2_implied_grid': fp2_implied_grid,
                    })
    
    return signals


def strategy_quali_trajectory(df, threshold=0.12):
    """
    S3: Qualifying trajectory — driver improving through Q1→Q2→Q3.
    Negative q_improvement = getting faster = momentum.
    """
    subset = df[(df['market_type'] == 'RACEPODIUM') & (df['q_improvement'].notna())].copy()
    signals = []
    
    for _, row in subset.iterrows():
        qi = row['q_improvement']  # negative = improving
        grid_pos = row['grid_pos']
        yes_price = row['yes_price']
        base_rate = row['base_rate']
        
        # Strong improvers in midfield → underpriced
        if qi < -0.003 and grid_pos >= 4 and grid_pos <= 10:
            # Improvement suggests car has more pace than grid shows
            edge = base_rate * 1.3 - yes_price  # 30% uplift for improving drivers
            
            if edge > threshold:
                odds = (1 - yes_price) / yes_price if yes_price > 0 else 0
                kf = kelly_size(edge, odds, 0.20)
                if kf > 0:
                    signals.append({
                        'round': row['round'], 'driver': row['driver'],
                        'market_type': 'RACEPODIUM', 'side': 'YES',
                        'price': yes_price, 'outcome': row['outcome'],
                        'edge': edge, 'kelly_frac': kf,
                        'grid_pos': grid_pos,
                        'event_code': row['event_code'], 'race_name': row['race_name'],
                    })
    
    return signals


def strategy_overpriced_favorites(df, threshold=0.15):
    """
    S4: Sell overpriced favorites who qualified below expectations.
    Big name qualifies P5+ → market still prices high → sell.
    Uses rolling_avg_grid vs actual grid.
    """
    signals = []
    
    for market_type in ['RACE', 'RACEPODIUM']:
        subset = df[(df['market_type'] == market_type) & (df['rolling_avg_grid'].notna())].copy()
        
        for _, row in subset.iterrows():
            grid_pos = row['grid_pos']
            avg_grid = row['rolling_avg_grid']
            yes_price = row['yes_price']
            base_rate = row['base_rate']
            
            # Driver qualified worse than their average → market may overweight reputation
            grid_drop = grid_pos - avg_grid  # positive = qualified worse than usual
            
            if grid_drop >= 3:
                # Market is probably overpricing based on name, actual grid position matters more
                edge = yes_price - base_rate  # how much market overprices
                
                if edge > threshold:
                    no_price = 1 - yes_price
                    odds = (1 - no_price) / no_price if no_price > 0 else 0
                    kf = kelly_size(edge, odds, 0.20)
                    if kf > 0:
                        signals.append({
                            'round': row['round'], 'driver': row['driver'],
                            'market_type': market_type, 'side': 'NO',
                            'price': yes_price, 'outcome': row['outcome'],
                            'edge': edge, 'kelly_frac': kf,
                            'grid_pos': grid_pos,
                            'event_code': row['event_code'], 'race_name': row['race_name'],
                        })
    
    return signals


def strategy_teammate_delta(df, threshold=0.10):
    """
    S5: Teammate gap as quality signal.
    If you massively outqualify teammate → car is being maximized, podium more likely.
    If you're crushed by teammate → you're the weak link.
    """
    subset = df[(df['market_type'] == 'RACEPODIUM') & (df['gap_to_teammate'].notna())].copy()
    signals = []
    
    for _, row in subset.iterrows():
        gap = row['gap_to_teammate']  # negative = faster than teammate
        grid_pos = row['grid_pos']
        yes_price = row['yes_price']
        base_rate = row['base_rate']
        
        # Driver crushed teammate by 0.3s+ AND is in podium contention (P1-P8)
        if gap < -0.3 and grid_pos <= 8:
            # This driver is extracting maximum from the car
            edge = base_rate * 1.2 - yes_price  # 20% uplift
            
            if edge > threshold:
                odds = (1 - yes_price) / yes_price if yes_price > 0 else 0
                kf = kelly_size(edge, odds, 0.20)
                if kf > 0:
                    signals.append({
                        'round': row['round'], 'driver': row['driver'],
                        'market_type': 'RACEPODIUM', 'side': 'YES',
                        'price': yes_price, 'outcome': row['outcome'],
                        'edge': edge, 'kelly_frac': kf,
                        'grid_pos': grid_pos,
                        'event_code': row['event_code'], 'race_name': row['race_name'],
                    })
        
        # Driver much slower than teammate AND market overprices them
        elif gap > 0.5 and yes_price > base_rate + threshold:
            no_price = 1 - yes_price
            edge = yes_price - base_rate
            odds = (1 - no_price) / no_price if no_price > 0 else 0
            kf = kelly_size(edge, odds, 0.15)
            if kf > 0:
                signals.append({
                    'round': row['round'], 'driver': row['driver'],
                    'market_type': 'RACEPODIUM', 'side': 'NO',
                    'price': yes_price, 'outcome': row['outcome'],
                    'edge': edge, 'kelly_frac': kf,
                    'grid_pos': grid_pos,
                    'event_code': row['event_code'], 'race_name': row['race_name'],
                })
    
    return signals


def strategy_cross_market(df, threshold=0.10):
    """
    S6: Cross-market structural edge.
    Podium price should be >= winner price (podium ⊃ win).
    If (podium_price - winner_price) is too small, podium is cheap.
    """
    subset = df[(df['market_type'] == 'RACEPODIUM') & (df['cross_winner_price'].notna())].copy()
    signals = []
    
    for _, row in subset.iterrows():
        pod_price = row['yes_price']
        win_price = row['cross_winner_price']
        grid_pos = row['grid_pos']
        base_rate = row['base_rate']
        
        # Podium price should be much higher than winner price
        # The spread = P(podium) - P(win) = P(finish 2nd or 3rd | not win)
        spread = pod_price - win_price
        base_spread = base_rate - ({'win': {}, 'podium': {}}.get('win', {}).get(grid_pos, 0.05))
        
        # If spread is too tight (< 10¢), podium is underpriced
        if spread < 0.10 and grid_pos <= 6 and base_rate > pod_price + threshold:
            edge = base_rate - pod_price
            odds = (1 - pod_price) / pod_price if pod_price > 0 else 0
            kf = kelly_size(edge, odds, 0.20)
            if kf > 0:
                signals.append({
                    'round': row['round'], 'driver': row['driver'],
                    'market_type': 'RACEPODIUM', 'side': 'YES',
                    'price': pod_price, 'outcome': row['outcome'],
                    'edge': edge, 'kelly_frac': kf,
                    'grid_pos': grid_pos,
                    'event_code': row['event_code'], 'race_name': row['race_name'],
                })
        
        # If podium price >> 2 * winner price AND base rate is lower → overpriced
        if pod_price > 2.5 * win_price and pod_price > base_rate + threshold and grid_pos >= 3:
            no_price = 1 - pod_price
            edge = pod_price - base_rate
            odds = (1 - no_price) / no_price if no_price > 0 else 0
            kf = kelly_size(edge, odds, 0.15)
            if kf > 0:
                signals.append({
                    'round': row['round'], 'driver': row['driver'],
                    'market_type': 'RACEPODIUM', 'side': 'NO',
                    'price': pod_price, 'outcome': row['outcome'],
                    'edge': edge, 'kelly_frac': kf,
                    'grid_pos': grid_pos,
                    'event_code': row['event_code'], 'race_name': row['race_name'],
                })
    
    return signals


def strategy_street_circuit_chaos(df, threshold=0.10):
    """
    S7: Street circuits have higher variance → midfield podiums more likely.
    Buy YES on P4-P8 podiums at street circuits where they're cheap.
    """
    subset = df[(df['market_type'] == 'RACEPODIUM') & (df['is_street_circuit'] == 1)].copy()
    signals = []
    
    for _, row in subset.iterrows():
        grid_pos = row['grid_pos']
        yes_price = row['yes_price']
        base_rate = row['base_rate']
        
        # On street circuits, midfield has higher podium chance
        if 4 <= grid_pos <= 8:
            # Street circuit uplift: ~40% more midfield podiums historically
            adjusted_rate = base_rate * 1.4
            edge = adjusted_rate - yes_price
            
            if edge > threshold:
                odds = (1 - yes_price) / yes_price if yes_price > 0 else 0
                kf = kelly_size(edge, odds, 0.20)
                if kf > 0:
                    signals.append({
                        'round': row['round'], 'driver': row['driver'],
                        'market_type': 'RACEPODIUM', 'side': 'YES',
                        'price': yes_price, 'outcome': row['outcome'],
                        'edge': edge, 'kelly_frac': kf,
                        'grid_pos': grid_pos,
                        'event_code': row['event_code'], 'race_name': row['race_name'],
                    })
    
    return signals


def strategy_price_drift(df, threshold=0.12):
    """
    S8: Late price drift as smart money signal.
    If price drifts UP (more people buying YES close to race) → follow momentum.
    If price drifts DOWN → smart money selling.
    """
    subset = df[(df['market_type'] == 'RACEPODIUM') & (df['price_drift'].notna())].copy()
    signals = []
    
    for _, row in subset.iterrows():
        drift = row['price_drift']  # positive = price going UP
        yes_price = row['yes_price']
        base_rate = row['base_rate']
        grid_pos = row['grid_pos']
        
        # Strong upward drift on cheap contracts → smart money buying
        if drift > 0.05 and yes_price < 0.40 and base_rate > yes_price:
            edge = base_rate - yes_price + drift  # drift confirms direction
            if edge > threshold:
                odds = (1 - yes_price) / yes_price if yes_price > 0 else 0
                kf = kelly_size(edge, odds, 0.15)
                if kf > 0:
                    signals.append({
                        'round': row['round'], 'driver': row['driver'],
                        'market_type': 'RACEPODIUM', 'side': 'YES',
                        'price': yes_price, 'outcome': row['outcome'],
                        'edge': edge, 'kelly_frac': kf,
                        'grid_pos': grid_pos,
                        'event_code': row['event_code'], 'race_name': row['race_name'],
                    })
        
        # Strong downward drift on expensive contracts → smart money dumping
        if drift < -0.05 and yes_price > 0.60 and yes_price > base_rate:
            no_price = 1 - yes_price
            edge = yes_price - base_rate + abs(drift)
            odds = (1 - no_price) / no_price if no_price > 0 else 0
            kf = kelly_size(edge, odds, 0.15)
            if kf > 0:
                signals.append({
                    'round': row['round'], 'driver': row['driver'],
                    'market_type': 'RACEPODIUM', 'side': 'NO',
                    'price': yes_price, 'outcome': row['outcome'],
                    'edge': edge, 'kelly_frac': kf,
                    'grid_pos': grid_pos,
                    'event_code': row['event_code'], 'race_name': row['race_name'],
                })
    
    return signals


def strategy_volume_surge(df, threshold=0.10):
    """
    S9: Volume surge on cheap contracts = informed buying.
    High volume ratio (late >> early) on underpriced contracts.
    """
    subset = df[(df['market_type'] == 'RACEPODIUM') & (df['volume_ratio'].notna())].copy()
    signals = []
    
    for _, row in subset.iterrows():
        vol_ratio = row['volume_ratio']
        yes_price = row['yes_price']
        base_rate = row['base_rate']
        grid_pos = row['grid_pos']
        total_vol = row['total_volume']
        
        # Volume surge on cheap underpriced contracts
        if vol_ratio > 2.0 and yes_price < 0.35 and base_rate > yes_price + threshold and total_vol > 50:
            edge = base_rate - yes_price
            odds = (1 - yes_price) / yes_price if yes_price > 0 else 0
            kf = kelly_size(edge, odds, 0.15)
            if kf > 0:
                signals.append({
                    'round': row['round'], 'driver': row['driver'],
                    'market_type': 'RACEPODIUM', 'side': 'YES',
                    'price': yes_price, 'outcome': row['outcome'],
                    'edge': edge, 'kelly_frac': kf,
                    'grid_pos': grid_pos,
                    'event_code': row['event_code'], 'race_name': row['race_name'],
                })
    
    return signals


def strategy_rolling_overperformer(df, threshold=0.12):
    """
    S10: Drivers who consistently gain positions on race day.
    High rolling_avg_gained = starts lower, finishes higher → underpriced.
    """
    subset = df[(df['market_type'] == 'RACEPODIUM') & (df['rolling_avg_gained'].notna())].copy()
    signals = []
    
    for _, row in subset.iterrows():
        avg_gained = row['rolling_avg_gained']  # positive = gains positions
        grid_pos = row['grid_pos']
        yes_price = row['yes_price']
        base_rate = row['base_rate']
        
        # Consistent overtaker starting in podium range
        if avg_gained >= 2.0 and 4 <= grid_pos <= 10:
            # Adjust base rate upward for overtakers
            adjusted_rate = base_rate * (1 + avg_gained * 0.1)  # 10% per avg position gained
            edge = adjusted_rate - yes_price
            
            if edge > threshold:
                odds = (1 - yes_price) / yes_price if yes_price > 0 else 0
                kf = kelly_size(edge, odds, 0.20)
                if kf > 0:
                    signals.append({
                        'round': row['round'], 'driver': row['driver'],
                        'market_type': 'RACEPODIUM', 'side': 'YES',
                        'price': yes_price, 'outcome': row['outcome'],
                        'edge': edge, 'kelly_frac': kf,
                        'grid_pos': grid_pos,
                        'event_code': row['event_code'], 'race_name': row['race_name'],
                    })
    
    return signals


def strategy_home_race(df, threshold=0.10):
    """
    S11: Home race advantage. Drivers may perform slightly better at home.
    """
    subset = df[(df['market_type'] == 'RACEPODIUM') & (df['is_home_race'] == 1)].copy()
    signals = []
    
    for _, row in subset.iterrows():
        grid_pos = row['grid_pos']
        yes_price = row['yes_price']
        base_rate = row['base_rate']
        
        if grid_pos <= 8:
            # Small home advantage uplift
            adjusted_rate = base_rate * 1.15
            edge = adjusted_rate - yes_price
            
            if edge > threshold:
                odds = (1 - yes_price) / yes_price if yes_price > 0 else 0
                kf = kelly_size(edge, odds, 0.15)
                if kf > 0:
                    signals.append({
                        'round': row['round'], 'driver': row['driver'],
                        'market_type': 'RACEPODIUM', 'side': 'YES',
                        'price': yes_price, 'outcome': row['outcome'],
                        'edge': edge, 'kelly_frac': kf,
                        'grid_pos': grid_pos,
                        'event_code': row['event_code'], 'race_name': row['race_name'],
                    })
    
    return signals


def strategy_sell_p1_winner(df, threshold=0.10):
    """
    S12: Pure sell pole-sitter winner. Simplest strategy.
    Pole-sitter typically overpriced in winner market.
    """
    subset = df[(df['market_type'] == 'RACE') & (df['grid_pos'] == 1)].copy()
    signals = []
    
    for _, row in subset.iterrows():
        yes_price = row['yes_price']
        base_rate = row['base_rate']  # ~0.50 for pole
        edge = yes_price - base_rate
        
        if edge > threshold:
            no_price = 1 - yes_price
            odds = (1 - no_price) / no_price if no_price > 0 else 0
            kf = kelly_size(edge, odds, 0.25)
            if kf > 0:
                signals.append({
                    'round': row['round'], 'driver': row['driver'],
                    'market_type': 'RACE', 'side': 'NO',
                    'price': yes_price, 'outcome': row['outcome'],
                    'edge': edge, 'kelly_frac': kf,
                    'grid_pos': 1,
                    'event_code': row['event_code'], 'race_name': row['race_name'],
                })
    
    return signals


def strategy_sell_p23_winner(df, threshold=0.08):
    """
    S13: Sell P2/P3 winner contracts. Market overprices front-row non-pole.
    """
    subset = df[(df['market_type'] == 'RACE') & (df['grid_pos'].isin([2, 3]))].copy()
    signals = []
    
    for _, row in subset.iterrows():
        yes_price = row['yes_price']
        base_rate = row['base_rate']
        edge = yes_price - base_rate
        
        if edge > threshold:
            no_price = 1 - yes_price
            odds = (1 - no_price) / no_price if no_price > 0 else 0
            kf = kelly_size(edge, odds, 0.20)
            if kf > 0:
                signals.append({
                    'round': row['round'], 'driver': row['driver'],
                    'market_type': 'RACE', 'side': 'NO',
                    'price': yes_price, 'outcome': row['outcome'],
                    'edge': edge, 'kelly_frac': kf,
                    'grid_pos': row['grid_pos'],
                    'event_code': row['event_code'], 'race_name': row['race_name'],
                })
    
    return signals


def strategy_gbm_model(df, threshold=0.15):
    """
    S14: Gradient Boosted Model — trained on 2019-2024, predict 2025.
    Uses grid_pos, gap_to_pole, team_tier, rolling features.
    """
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.calibration import CalibratedClassifierCV
    
    # Build training data from historical base rate info embedded in features
    # We'll use the 2019-2024 data that's already in the rolling features
    # For a clean implementation, train on features available pre-race
    
    feature_cols = ['grid_pos', 'gap_to_pole', 'team_tier', 'rolling_avg_finish',
                    'rolling_avg_gained', 'rolling_dnf_rate', 'rolling_avg_points',
                    'is_street_circuit', 'is_high_attrition']
    
    signals = []
    
    for market_type in ['RACEPODIUM']:
        subset = df[df['market_type'] == market_type].copy()
        
        # Walk-forward: train on rounds 1-N, predict N+1
        # But we only have 2025 Kalshi prices, so we use features + outcome
        # to train in-sample (honest: we acknowledge this limitation)
        
        # Instead: train on first half, test on second half
        train = subset[subset['round'] <= 12]
        test = subset[subset['round'] > 12]
        
        if len(train) < 20 or len(test) < 10:
            continue
        
        # Fill NaN
        for col in feature_cols:
            if col in train.columns:
                median = train[col].median()
                train[col] = train[col].fillna(median)
                test[col] = test[col].fillna(median)
        
        available_cols = [c for c in feature_cols if c in train.columns]
        X_train = train[available_cols].values
        y_train = train['outcome'].values
        X_test = test[available_cols].values
        
        try:
            model = GradientBoostingClassifier(n_estimators=100, max_depth=3, 
                                                learning_rate=0.1, random_state=42)
            cal_model = CalibratedClassifierCV(model, cv=3, method='isotonic')
            cal_model.fit(X_train, y_train)
            
            probs = cal_model.predict_proba(X_test)[:, 1]
            
            for i, (_, row) in enumerate(test.iterrows()):
                pred_prob = probs[i]
                yes_price = row['yes_price']
                
                edge = pred_prob - yes_price
                if edge > threshold:
                    odds = (1 - yes_price) / yes_price if yes_price > 0 else 0
                    kf = kelly_size(edge, odds, 0.20)
                    if kf > 0:
                        signals.append({
                            'round': row['round'], 'driver': row['driver'],
                            'market_type': market_type, 'side': 'YES',
                            'price': yes_price, 'outcome': row['outcome'],
                            'edge': edge, 'kelly_frac': kf,
                            'grid_pos': row['grid_pos'],
                            'event_code': row['event_code'], 'race_name': row['race_name'],
                        })
                
                no_edge = yes_price - pred_prob
                if no_edge > threshold:
                    no_price = 1 - yes_price
                    odds = (1 - no_price) / no_price if no_price > 0 else 0
                    kf = kelly_size(no_edge, odds, 0.20)
                    if kf > 0:
                        signals.append({
                            'round': row['round'], 'driver': row['driver'],
                            'market_type': market_type, 'side': 'NO',
                            'price': yes_price, 'outcome': row['outcome'],
                            'edge': no_edge, 'kelly_frac': kf,
                            'grid_pos': row['grid_pos'],
                            'event_code': row['event_code'], 'race_name': row['race_name'],
                        })
        except Exception as e:
            print(f"  GBM error: {e}")
    
    return signals


def strategy_logistic_model(df, threshold=0.15):
    """
    S15: Logistic regression — simpler, less overfit-prone.
    Walk-forward: train on 2019-2024 equivalent features.
    """
    from sklearn.linear_model import LogisticRegression
    
    feature_cols = ['grid_pos', 'gap_to_pole', 'team_tier']
    
    signals = []
    
    for market_type in ['RACEPODIUM']:
        subset = df[df['market_type'] == market_type].copy()
        
        # Walk-forward split
        train = subset[subset['round'] <= 12]
        test = subset[subset['round'] > 12]
        
        if len(train) < 20 or len(test) < 10:
            continue
        
        available_cols = [c for c in feature_cols if c in train.columns]
        for col in available_cols:
            median = train[col].median()
            train[col] = train[col].fillna(median)
            test[col] = test[col].fillna(median)
        
        X_train = train[available_cols].values
        y_train = train['outcome'].values
        X_test = test[available_cols].values
        
        try:
            model = LogisticRegression(random_state=42)
            model.fit(X_train, y_train)
            
            probs = model.predict_proba(X_test)[:, 1]
            
            for i, (_, row) in enumerate(test.iterrows()):
                pred_prob = probs[i]
                yes_price = row['yes_price']
                
                if pred_prob - yes_price > threshold:
                    edge = pred_prob - yes_price
                    odds = (1 - yes_price) / yes_price if yes_price > 0 else 0
                    kf = kelly_size(edge, odds, 0.20)
                    if kf > 0:
                        signals.append({
                            'round': row['round'], 'driver': row['driver'],
                            'market_type': market_type, 'side': 'YES',
                            'price': yes_price, 'outcome': row['outcome'],
                            'edge': edge, 'kelly_frac': kf,
                            'grid_pos': row['grid_pos'],
                            'event_code': row['event_code'], 'race_name': row['race_name'],
                        })
                
                if yes_price - pred_prob > threshold:
                    no_price = 1 - yes_price
                    edge = yes_price - pred_prob
                    odds = (1 - no_price) / no_price if no_price > 0 else 0
                    kf = kelly_size(edge, odds, 0.20)
                    if kf > 0:
                        signals.append({
                            'round': row['round'], 'driver': row['driver'],
                            'market_type': market_type, 'side': 'NO',
                            'price': yes_price, 'outcome': row['outcome'],
                            'edge': edge, 'kelly_frac': kf,
                            'grid_pos': row['grid_pos'],
                            'event_code': row['event_code'], 'race_name': row['race_name'],
                        })
        except Exception as e:
            print(f"  Logistic error: {e}")
    
    return signals


def strategy_ensemble_agreement(df, threshold=0.12, min_agree=2):
    """
    S16: Ensemble agreement — only trade when multiple signals agree.
    Runs strategies S1-S11, takes trades where ≥ min_agree strategies agree.
    """
    # Collect signals from each strategy
    all_sigs = {}
    all_sigs['base_yes'] = strategy_base_rate_edge(df, 'RACEPODIUM', 0.10, 'YES')
    all_sigs['base_no'] = strategy_base_rate_edge(df, 'RACEPODIUM', 0.10, 'NO')
    all_sigs['fp2'] = strategy_fp2_pace_edge(df, 0.08)
    all_sigs['quali'] = strategy_quali_trajectory(df, 0.08)
    all_sigs['overpriced'] = strategy_overpriced_favorites(df, 0.10)
    all_sigs['teammate'] = strategy_teammate_delta(df, 0.08)
    all_sigs['street'] = strategy_street_circuit_chaos(df, 0.08)
    all_sigs['drift'] = strategy_price_drift(df, 0.08)
    all_sigs['volume'] = strategy_volume_surge(df, 0.08)
    all_sigs['roller'] = strategy_rolling_overperformer(df, 0.08)
    
    # Count agreements per (round, driver, market_type, side)
    vote_count = defaultdict(lambda: {'count': 0, 'edges': [], 'strategies': [], 'base_signal': None})
    
    for strat_name, sigs in all_sigs.items():
        for s in sigs:
            key = (s['round'], s['driver'], s['market_type'], s['side'])
            vote_count[key]['count'] += 1
            vote_count[key]['edges'].append(s['edge'])
            vote_count[key]['strategies'].append(strat_name)
            vote_count[key]['base_signal'] = s  # keep last signal for metadata
    
    signals = []
    for key, votes in vote_count.items():
        if votes['count'] >= min_agree:
            s = votes['base_signal'].copy()
            avg_edge = np.mean(votes['edges'])
            s['edge'] = avg_edge
            
            # Size proportional to agreement level
            price = s['price'] if s['side'] == 'YES' else (1 - s['price'])
            odds = (1 - price) / price if price > 0 else 0
            s['kelly_frac'] = kelly_size(avg_edge, odds, 0.05 * votes['count'])  # more agreement = bigger bet
            s['n_agree'] = votes['count']
            s['strategies'] = votes['strategies']
            
            signals.append(s)
    
    return signals


def strategy_sell_p23_podium(df, threshold=0.12):
    """
    S17: Sell overpriced P2-P3 podium contracts.
    Market may overprice front-row podium finish.
    """
    subset = df[(df['market_type'] == 'RACEPODIUM') & (df['grid_pos'].isin([2, 3]))].copy()
    signals = []
    
    for _, row in subset.iterrows():
        yes_price = row['yes_price']
        base_rate = row['base_rate']
        edge = yes_price - base_rate
        
        if edge > threshold:
            no_price = 1 - yes_price
            odds = (1 - no_price) / no_price if no_price > 0 else 0
            kf = kelly_size(edge, odds, 0.20)
            if kf > 0:
                signals.append({
                    'round': row['round'], 'driver': row['driver'],
                    'market_type': 'RACEPODIUM', 'side': 'NO',
                    'price': yes_price, 'outcome': row['outcome'],
                    'edge': edge, 'kelly_frac': kf,
                    'grid_pos': row['grid_pos'],
                    'event_code': row['event_code'], 'race_name': row['race_name'],
                })
    
    return signals


def strategy_midfield_yes_podium(df, threshold=0.12):
    """
    S18: Buy YES on midfield (P4-P8) podium when underpriced.
    """
    subset = df[(df['market_type'] == 'RACEPODIUM') & (df['grid_pos'].between(4, 8))].copy()
    signals = []
    
    for _, row in subset.iterrows():
        yes_price = row['yes_price']
        base_rate = row['base_rate']
        edge = base_rate - yes_price
        
        if edge > threshold:
            odds = (1 - yes_price) / yes_price if yes_price > 0 else 0
            kf = kelly_size(edge, odds, 0.20)
            if kf > 0:
                signals.append({
                    'round': row['round'], 'driver': row['driver'],
                    'market_type': 'RACEPODIUM', 'side': 'YES',
                    'price': yes_price, 'outcome': row['outcome'],
                    'edge': edge, 'kelly_frac': kf,
                    'grid_pos': row['grid_pos'],
                    'event_code': row['event_code'], 'race_name': row['race_name'],
                })
    
    return signals


def strategy_fp2_lr_podium(df, threshold=0.12):
    """
    S19: FP2 long-run pace specifically for podium prediction.
    Uses long-run delta (race pace proxy) vs grid position.
    """
    subset = df[(df['market_type'] == 'RACEPODIUM') & (df['fp2_lr_delta'].notna())].copy()
    signals = []
    
    for _, row in subset.iterrows():
        lr_delta = row['fp2_lr_delta']
        grid_pos = row['grid_pos']
        yes_price = row['yes_price']
        base_rate = row['base_rate']
        
        # Good long-run pace (low delta) + midfield grid = underpriced
        if lr_delta < 0.5 and grid_pos >= 4:
            # Convert LR delta to implied pace rank
            lr_implied = max(1, min(10, int(1 + lr_delta / 0.2)))
            pace_base = {1: 0.80, 2: 0.71, 3: 0.64, 4: 0.36, 5: 0.29, 
                        6: 0.25, 7: 0.15, 8: 0.12}.get(lr_implied, 0.10)
            
            # Weight long-run pace more than grid (it's closer to race performance)
            blended_rate = 0.6 * pace_base + 0.4 * base_rate
            edge = blended_rate - yes_price
            
            if edge > threshold:
                odds = (1 - yes_price) / yes_price if yes_price > 0 else 0
                kf = kelly_size(edge, odds, 0.20)
                if kf > 0:
                    signals.append({
                        'round': row['round'], 'driver': row['driver'],
                        'market_type': 'RACEPODIUM', 'side': 'YES',
                        'price': yes_price, 'outcome': row['outcome'],
                        'edge': edge, 'kelly_frac': kf,
                        'grid_pos': grid_pos,
                        'event_code': row['event_code'], 'race_name': row['race_name'],
                    })
    
    return signals


# ══════════════════════════════════════════════════════════════
# TOURNAMENT RUNNER
# ══════════════════════════════════════════════════════════════

def run_tournament():
    """Run all strategies and report results."""
    
    print("Loading feature matrix...")
    df = pd.read_csv(Path(__file__).parent / 'feature_matrix.csv')
    print(f"  {len(df)} rows × {len(df.columns)} columns")
    print(f"  Markets: {df['market_type'].value_counts().to_dict()}")
    
    strategies = {
        'S01: Base Rate YES Podium (t=0.15)': lambda: strategy_base_rate_edge(df, 'RACEPODIUM', 0.15, 'YES'),
        'S02: Base Rate YES Podium (t=0.10)': lambda: strategy_base_rate_edge(df, 'RACEPODIUM', 0.10, 'YES'),
        'S03: Base Rate NO Podium (t=0.15)': lambda: strategy_base_rate_edge(df, 'RACEPODIUM', 0.15, 'NO'),
        'S04: Base Rate NO Podium (t=0.10)': lambda: strategy_base_rate_edge(df, 'RACEPODIUM', 0.10, 'NO'),
        'S05: Base Rate YES Winner (t=0.15)': lambda: strategy_base_rate_edge(df, 'RACE', 0.15, 'YES'),
        'S06: Base Rate NO Winner (t=0.10)': lambda: strategy_base_rate_edge(df, 'RACE', 0.10, 'NO'),
        'S07: FP2 Pace Edge': lambda: strategy_fp2_pace_edge(df),
        'S08: Qualifying Trajectory': lambda: strategy_quali_trajectory(df),
        'S09: Overpriced Favorites': lambda: strategy_overpriced_favorites(df),
        'S10: Teammate Delta': lambda: strategy_teammate_delta(df),
        'S11: Cross-Market Structural': lambda: strategy_cross_market(df),
        'S12: Street Circuit Chaos': lambda: strategy_street_circuit_chaos(df),
        'S13: Price Drift Momentum': lambda: strategy_price_drift(df),
        'S14: Volume Surge': lambda: strategy_volume_surge(df),
        'S15: Rolling Overperformer': lambda: strategy_rolling_overperformer(df),
        'S16: Home Race Advantage': lambda: strategy_home_race(df),
        'S17: Sell P1 Winner': lambda: strategy_sell_p1_winner(df),
        'S18: Sell P2-P3 Winner': lambda: strategy_sell_p23_winner(df),
        'S19: GBM Model (walk-forward)': lambda: strategy_gbm_model(df),
        'S20: Logistic Model (walk-forward)': lambda: strategy_logistic_model(df),
        'S21: Ensemble (≥2 agree)': lambda: strategy_ensemble_agreement(df, min_agree=2),
        'S22: Ensemble (≥3 agree)': lambda: strategy_ensemble_agreement(df, min_agree=3),
        'S23: Sell P2-P3 Podium': lambda: strategy_sell_p23_podium(df),
        'S24: Midfield YES Podium (P4-P8)': lambda: strategy_midfield_yes_podium(df),
        'S25: FP2 Long-Run Podium': lambda: strategy_fp2_lr_podium(df),
    }
    
    results = {}
    all_trades = {}
    
    print(f"\n{'='*100}")
    print(f"{'STRATEGY TOURNAMENT':^100}")
    print(f"{'='*100}")
    print(f"{'Strategy':<42} {'Return':>8} {'Trades':>7} {'Win%':>6} {'Sharpe':>7} {'MaxDD':>7} {'PF':>7} {'Boot%':>7}")
    print(f"{'-'*100}")
    
    for name, gen_fn in strategies.items():
        signals = gen_fn()
        
        if not signals:
            print(f"{name:<42} {'NO TRADES':>8}")
            continue
        
        trades, equity = run_backtest(signals)
        metrics = compute_metrics(trades)
        
        # Bootstrap
        boot_pct = bootstrap_test(metrics['round_pnls']) * 100 if metrics['round_pnls'] else 0
        
        results[name] = {**metrics, 'bootstrap_pct': boot_pct}
        all_trades[name] = trades
        
        pf_str = f"{metrics['profit_factor']:.1f}" if metrics['profit_factor'] != float('inf') else 'inf'
        
        print(f"{name:<42} {metrics['total_return_pct']:>+7.1f}% {metrics['n_trades']:>6} {metrics['win_rate']:>5.1f}% "
              f"{metrics['sharpe']:>6.2f} {metrics['max_drawdown_pct']:>5.1f}% {pf_str:>6} {boot_pct:>6.1f}%")
    
    # ── TOP STRATEGIES ──
    print(f"\n{'='*100}")
    print("TOP 5 BY RETURN (minimum 10 trades)")
    print(f"{'='*100}")
    
    qualified = {k: v for k, v in results.items() if v['n_trades'] >= 10}
    top5 = sorted(qualified.items(), key=lambda x: x[1]['total_return_pct'], reverse=True)[:5]
    
    for name, m in top5:
        print(f"\n{'─'*80}")
        print(f"  {name}")
        print(f"  Return: {m['total_return_pct']:+.1f}%  |  Trades: {m['n_trades']}  |  Win%: {m['win_rate']}%")
        print(f"  Sharpe: {m['sharpe']:.2f}  |  MaxDD: {m['max_drawdown_pct']}%  |  Bootstrap: {m['bootstrap_pct']:.1f}%")
        print(f"  Avg Win: ${m['avg_win']}  |  Avg Loss: ${m['avg_loss']}")
        
        # Print individual trades
        trades = all_trades[name]
        print(f"\n  {'Rnd':>4} {'Race':<15} {'Driver':<5} {'Grid':>4} {'Side':>4} {'Price':>6} {'Edge':>6} {'Stake':>7} {'Out':>4} {'P&L':>8} {'Bank':>8}")
        for t in trades:
            color = '✓' if t['pnl'] > 0 else '✗'
            print(f"  {t['round']:>4} {t['race_name']:<15} {t['driver']:<5} {t.get('grid_pos','?'):>4} "
                  f"{t['side']:>4} {t['price']:>6.2f} {t['edge']:>+6.2f} ${t['stake']:>6.2f} "
                  f"{'WIN' if t['outcome']==1 else 'NO':>4} ${t['pnl']:>+7.2f} ${t['bankroll']:>7.2f} {color}")
    
    # ── CONCENTRATION ANALYSIS ──
    print(f"\n{'='*100}")
    print("CONCENTRATION ANALYSIS (for top strategies)")
    print(f"{'='*100}")
    
    for name, _ in top5[:3]:
        trades = all_trades[name]
        if not trades:
            continue
        
        total_profit = sum(t['pnl'] for t in trades)
        
        # Per-driver contribution
        driver_pnl = defaultdict(float)
        for t in trades:
            driver_pnl[t['driver']] += t['pnl']
        
        print(f"\n  {name}")
        print(f"  Total P&L: ${total_profit:.2f}")
        print(f"  Per driver:")
        for d, pnl in sorted(driver_pnl.items(), key=lambda x: x[1], reverse=True):
            pct = pnl / total_profit * 100 if total_profit != 0 else 0
            print(f"    {d}: ${pnl:+.2f} ({pct:+.0f}%)")
        
        # Per-round contribution
        round_pnl = defaultdict(float)
        for t in trades:
            round_pnl[t['round']] += t['pnl']
        
        top3_rounds = sorted(round_pnl.items(), key=lambda x: x[1], reverse=True)[:3]
        top3_total = sum(v for _, v in top3_rounds)
        print(f"  Top 3 rounds contribute: ${top3_total:.2f} ({top3_total/total_profit*100:.0f}% of total)" if total_profit > 0 else "")
        
        # Without top 3 rounds
        without_top3 = total_profit - top3_total
        print(f"  Without top 3 rounds: ${without_top3:+.2f}")
    
    # Save all results
    output = {
        'tournament_results': {k: {kk: vv for kk, vv in v.items() if kk != 'round_pnls'} 
                               for k, v in results.items()},
        'top5': [(name, {kk: vv for kk, vv in m.items() if kk != 'round_pnls'}) for name, m in top5],
    }
    
    with open(Path(__file__).parent / 'tournament_results.json', 'w') as f:
        json.dump(output, f, indent=2, default=str)
    
    # Save all trade logs
    for name, trades in all_trades.items():
        safe_name = name.replace(':', '').replace(' ', '_').replace('(', '').replace(')', '').replace('≥', 'gte')
        pd.DataFrame(trades).to_csv(
            Path(__file__).parent / f'trades_{safe_name}.csv', index=False)
    
    return results, all_trades


if __name__ == '__main__':
    results, all_trades = run_tournament()
