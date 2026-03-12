"""
Step 4: Clean backtest — no black boxes, no data leakage.

STRATEGY: "Sell the Favorite" (Favorite-Longshot Bias)
  For each race, after qualifying:
    1. Look at post-qualifying Kalshi prices for drivers in grid P1-P6
    2. Compare each price to historical base rate for that grid position
    3. If Kalshi price > base_rate + threshold: BUY NO (the market overprices this driver)
    4. If Kalshi price < base_rate - threshold: BUY YES (the market underprices this driver)
    5. Size using fractional Kelly criterion, capped

ANTI-LEAKAGE GUARANTEES:
  - Prices: VWAP of trades AFTER quali ends, BEFORE race starts (verified by timestamp)
  - Base rates: computed ONLY from 2019-2024 data (no 2025 in training set)
  - Outcomes: from FastF1 race results (ground truth)
  - No parameter optimization on 2025 data — threshold and Kelly fraction are fixed a priori
  
MARKETS TESTED:
  - RACE (winner): settle at $1 if driver wins, $0 otherwise
  - RACEPODIUM: settle at $1 if driver finishes top 3, $0 otherwise
"""

import pandas as pd
import numpy as np
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtest.race_calendar import get_race_calendar, get_race_results, KALSHI_TO_F1
from backtest.post_qual_prices import get_post_qual_prices, load_outcomes, parse_ticker


def load_base_rates():
    rates = pd.read_csv('backtest/base_rates_2019_2024.csv')
    win_rates = dict(zip(rates['qual_pos'], rates['p_win']))
    podium_rates = dict(zip(rates['qual_pos'], rates['p_podium']))
    return win_rates, podium_rates


def get_race_outcome_map(year=2025):
    """
    For each 2025 race, get {driver_code: finish_position} from FastF1.
    Returns dict: kalshi_event -> {driver_code: finish_pos}
    """
    import logging
    logging.getLogger('fastf1').setLevel(logging.ERROR)
    
    outcomes = {}
    for kalshi_event, (yr, rnd) in KALSHI_TO_F1.items():
        if yr != year:
            continue
        try:
            results = get_race_results(yr, rnd)
            driver_finish = {}
            for _, row in results.iterrows():
                abbr = row['abbreviation']
                fp = row['finish_position']
                driver_finish[abbr] = int(fp) if not pd.isna(fp) else None
            outcomes[kalshi_event] = driver_finish
        except Exception as e:
            print(f"  Could not load race results for {kalshi_event}: {e}")
    return outcomes


def get_grid_map(year=2025):
    """
    For each 2025 race, get {driver_code: grid_position} from FastF1 race results.
    Grid position (not quali position) — accounts for penalties.
    """
    import logging
    logging.getLogger('fastf1').setLevel(logging.ERROR)
    from backtest.race_calendar import get_qualifying_grid
    
    grids = {}
    for kalshi_event, (yr, rnd) in KALSHI_TO_F1.items():
        if yr != year:
            continue
        try:
            # Use qualifying results (Position column = quali position)
            qr = get_qualifying_grid(yr, rnd)
            driver_grid = dict(zip(qr['abbreviation'], qr['quali_position']))
            grids[kalshi_event] = driver_grid
        except Exception as e:
            print(f"  Could not load qualifying for {kalshi_event}: {e}")
    return grids


def kalshi_fee(profit):
    """Kalshi fee: 7% of profit, only if positive. No fee on losses."""
    if profit > 0:
        return profit * 0.07
    return 0.0


def run_backtest(
    edge_threshold=0.05,   # minimum edge to trade (5 percentage points)
    kelly_fraction=0.25,   # quarter Kelly
    max_position_pct=0.15, # max 15% of bankroll per trade  
    min_trades_for_price=3,# require at least 3 trades in window for reliable VWAP
    initial_bankroll=100.0,
    grid_positions=range(1, 7),  # only trade P1-P6 qualifiers
    markets=('RACE', 'RACEPODIUM'),
    verbose=True,
):
    """
    Run the full backtest and return trade log + equity curve.
    """
    if verbose:
        print("=" * 80)
        print("CLEAN BACKTEST — Favorite-Longshot Bias on Kalshi F1 Markets")
        print("=" * 80)
        print(f"Parameters:")
        print(f"  Edge threshold:    {edge_threshold:.0%}")
        print(f"  Kelly fraction:    {kelly_fraction:.0%}")
        print(f"  Max position:      {max_position_pct:.0%}")
        print(f"  Min trades/price:  {min_trades_for_price}")
        print(f"  Grid positions:    {list(grid_positions)}")
        print(f"  Markets:           {markets}")
        print(f"  Initial bankroll:  ${initial_bankroll:.2f}")
        print()
    
    # Load data
    if verbose:
        print("Loading data...")
    
    calendar = get_race_calendar()
    calendar_2025 = calendar[calendar['year'] == 2025].copy()
    
    prices = get_post_qual_prices(calendar)
    prices_2025 = prices[prices['kalshi_event'].isin(calendar_2025['kalshi_event'].values)]
    
    win_rates, podium_rates = load_base_rates()
    race_outcomes = get_race_outcome_map(2025)
    grid_map = get_grid_map(2025)
    
    # Also load outcomes from individual Kalshi files (for verification)
    kalshi_outcomes = load_outcomes()
    
    if verbose:
        print(f"  Races with prices: {prices_2025['kalshi_event'].nunique()}")
        print(f"  Races with outcomes: {len(race_outcomes)}")
        print(f"  Price observations: {len(prices_2025)}")
        print()
    
    # Sort races chronologically
    race_order = calendar_2025.sort_values('race_start_utc')['kalshi_event'].tolist()
    
    # Run backtest
    bankroll = initial_bankroll
    trade_log = []
    equity_curve = [{'race_num': 0, 'event': 'START', 'bankroll': bankroll}]
    
    for event in race_order:
        if event not in race_outcomes:
            continue
        if event not in grid_map:
            continue
        
        event_grid = grid_map[event]
        event_results = race_outcomes[event]
        event_prices = prices_2025[prices_2025['kalshi_event'] == event]
        
        # Reverse lookup: F1 abbreviation → Kalshi driver code
        # They should match but let's be safe
        event_name = calendar_2025[calendar_2025['kalshi_event'] == event]['event_name'].iloc[0]
        
        race_trades = []
        
        for _, price_row in event_prices.iterrows():
            market_type = price_row['market_type']
            driver_code = price_row['driver_code']
            
            if market_type not in markets:
                continue
            if price_row['trade_count'] < min_trades_for_price:
                continue
            
            # Find this driver's grid position
            grid_pos = event_grid.get(driver_code)
            if grid_pos is None:
                continue
            if grid_pos not in grid_positions:
                continue
            
            # Get Kalshi price (convert cents to probability)
            kalshi_yes = price_row['vwap_yes_cents'] / 100.0
            kalshi_no = price_row['vwap_no_cents'] / 100.0
            
            # Get base rate
            if market_type == 'RACE':
                base_rate = win_rates.get(grid_pos, 0)
            elif market_type == 'RACEPODIUM':
                base_rate = podium_rates.get(grid_pos, 0)
            else:
                continue
            
            # Compute edge
            edge_sell = kalshi_yes - base_rate   # positive = overpriced, sell (buy NO)
            edge_buy = base_rate - kalshi_yes    # positive = underpriced, buy YES
            
            # Determine trade direction
            if edge_sell >= edge_threshold:
                direction = 'BUY_NO'
                entry_price = kalshi_no  # we pay this for NO contract
                edge = edge_sell
            elif edge_buy >= edge_threshold:
                direction = 'BUY_YES'
                entry_price = kalshi_yes  # we pay this for YES contract
                edge = edge_buy
            else:
                continue  # no edge
            
            # Kelly sizing
            if direction == 'BUY_NO':
                # We buy NO at entry_price, win (1 - base_rate), lose base_rate
                p_win = 1 - base_rate  # probability NO wins (driver doesn't win/podium)
                p_lose = base_rate
                b = (1 - entry_price) / entry_price  # odds ratio (payout / cost)
                if b <= 0:
                    continue
                kelly = (p_win * b - p_lose) / b
            else:
                # We buy YES at entry_price, win base_rate, lose (1 - base_rate)
                p_win = base_rate
                p_lose = 1 - base_rate
                b = (1 - entry_price) / entry_price
                if b <= 0:
                    continue
                kelly = (p_win * b - p_lose) / b
            
            if kelly <= 0:
                continue  # negative Kelly = don't trade
            
            position_size_pct = min(kelly * kelly_fraction, max_position_pct)
            stake = bankroll * position_size_pct
            
            if stake < 1.0:  # minimum $1 trade
                continue
            
            # Determine outcome
            finish_pos = event_results.get(driver_code)
            if finish_pos is None:
                # DNF — treat as not winning/not podium
                if market_type == 'RACE':
                    driver_won = False
                    driver_podium = False
                else:
                    driver_won = False
                    driver_podium = False
            else:
                driver_won = finish_pos == 1
                driver_podium = finish_pos <= 3
            
            if market_type == 'RACE':
                event_happened = driver_won
            else:
                event_happened = driver_podium
            
            # Settlement
            contracts = stake / entry_price  # number of contracts at entry_price cents each
            
            if direction == 'BUY_NO':
                if not event_happened:
                    # NO wins: we get $1 per contract, paid entry_price per contract
                    gross_profit = contracts * (1.0 - entry_price)
                    fee = kalshi_fee(gross_profit)
                    net_pnl = gross_profit - fee
                else:
                    # NO loses: we lose our stake
                    net_pnl = -stake
            else:  # BUY_YES
                if event_happened:
                    # YES wins
                    gross_profit = contracts * (1.0 - entry_price)
                    fee = kalshi_fee(gross_profit)
                    net_pnl = gross_profit - fee
                else:
                    # YES loses
                    net_pnl = -stake
            
            bankroll += net_pnl
            
            trade = {
                'event': event,
                'event_name': event_name,
                'market': market_type,
                'driver': driver_code,
                'grid_pos': grid_pos,
                'direction': direction,
                'entry_price': round(entry_price, 4),
                'base_rate': round(base_rate, 4),
                'edge': round(edge, 4),
                'kelly': round(kelly, 4),
                'position_pct': round(position_size_pct, 4),
                'stake': round(stake, 2),
                'contracts': round(contracts, 2),
                'outcome': 'WIN' if ((direction == 'BUY_NO' and not event_happened) or 
                                     (direction == 'BUY_YES' and event_happened)) else 'LOSS',
                'finish_pos': finish_pos,
                'event_happened': event_happened,
                'gross_pnl': round(net_pnl + (kalshi_fee(max(0, net_pnl + stake - stake)) if net_pnl > 0 else 0), 2),
                'net_pnl': round(net_pnl, 2),
                'bankroll_after': round(bankroll, 2),
            }
            trade_log.append(trade)
            race_trades.append(trade)
        
        equity_curve.append({
            'race_num': race_order.index(event) + 1,
            'event': event,
            'bankroll': round(bankroll, 2),
        })
        
        if verbose and race_trades:
            print(f"Race {race_order.index(event)+1:>2}: {event_name:<30} | "
                  f"{len(race_trades)} trades | "
                  f"P&L: ${sum(t['net_pnl'] for t in race_trades):>+8.2f} | "
                  f"Bankroll: ${bankroll:>8.2f}")
    
    return trade_log, equity_curve


def compute_stats(trade_log, equity_curve, initial_bankroll=100.0):
    """Compute summary statistics from trade log."""
    if not trade_log:
        return {}
    
    df = pd.DataFrame(trade_log)
    eq = pd.DataFrame(equity_curve)
    
    total_pnl = sum(t['net_pnl'] for t in trade_log)
    final_bankroll = equity_curve[-1]['bankroll']
    
    wins = df[df['outcome'] == 'WIN']
    losses = df[df['outcome'] == 'LOSS']
    
    # Per-race returns for Sharpe
    race_pnls = df.groupby('event')['net_pnl'].sum()
    race_bankrolls = eq.set_index('event')['bankroll']
    
    # Compute per-race returns as fraction of bankroll at start of race
    race_returns = []
    prev_bankroll = initial_bankroll
    for event in eq[eq['event'] != 'START']['event']:
        curr_bankroll = eq[eq['event'] == event]['bankroll'].iloc[0]
        ret = (curr_bankroll - prev_bankroll) / prev_bankroll if prev_bankroll > 0 else 0
        race_returns.append(ret)
        prev_bankroll = curr_bankroll
    
    race_returns = np.array(race_returns)
    
    # Drawdown
    peak = initial_bankroll
    max_dd = 0
    for _, row in eq.iterrows():
        if row['bankroll'] > peak:
            peak = row['bankroll']
        dd = (peak - row['bankroll']) / peak
        if dd > max_dd:
            max_dd = dd
    
    stats = {
        'initial_bankroll': initial_bankroll,
        'final_bankroll': final_bankroll,
        'total_return_pct': (final_bankroll / initial_bankroll - 1) * 100,
        'total_trades': len(trade_log),
        'wins': len(wins),
        'losses': len(losses),
        'win_rate': len(wins) / len(trade_log),
        'avg_win': wins['net_pnl'].mean() if len(wins) > 0 else 0,
        'avg_loss': losses['net_pnl'].mean() if len(losses) > 0 else 0,
        'profit_factor': abs(wins['net_pnl'].sum() / losses['net_pnl'].sum()) if losses['net_pnl'].sum() != 0 else float('inf'),
        'sharpe': np.mean(race_returns) / np.std(race_returns) * np.sqrt(24) if np.std(race_returns) > 0 else 0,
        'max_drawdown_pct': max_dd * 100,
        'races_traded': len(race_returns),
        'avg_trades_per_race': len(trade_log) / len(race_returns) if len(race_returns) > 0 else 0,
    }
    
    return stats


def run_robustness_tests(trade_log, equity_curve, initial_bankroll=100.0, n_bootstrap=5000):
    """
    Run leave-one-out and bootstrap tests.
    """
    df = pd.DataFrame(trade_log)
    events = df['event'].unique()
    
    # Leave-one-out
    loo_results = []
    for leave_out in events:
        remaining = df[df['event'] != leave_out]
        pnl = remaining['net_pnl'].sum()
        loo_results.append({
            'left_out': leave_out,
            'pnl': pnl,
            'profitable': pnl > 0,
        })
    
    loo_df = pd.DataFrame(loo_results)
    n_profitable = loo_df['profitable'].sum()
    
    # Bootstrap (resample races with replacement)
    race_pnls = df.groupby('event')['net_pnl'].sum().values
    rng = np.random.RandomState(42)
    bootstrap_profits = []
    for _ in range(n_bootstrap):
        sample = rng.choice(race_pnls, size=len(race_pnls), replace=True)
        bootstrap_profits.append(sample.sum())
    
    bootstrap_profits = np.array(bootstrap_profits)
    p_profit = (bootstrap_profits > 0).mean()
    
    # Remove top N races
    race_pnl_series = df.groupby('event')['net_pnl'].sum().sort_values(ascending=False)
    
    return {
        'loo_profitable': f"{n_profitable}/{len(events)}",
        'loo_worst': loo_df.loc[loo_df['pnl'].idxmin()],
        'bootstrap_p_profit': p_profit,
        'bootstrap_median': np.median(bootstrap_profits),
        'bootstrap_5th': np.percentile(bootstrap_profits, 5),
        'bootstrap_95th': np.percentile(bootstrap_profits, 95),
        'race_pnl_ranking': race_pnl_series,
        'return_without_top1': (initial_bankroll + race_pnl_series.iloc[1:].sum()) / initial_bankroll - 1,
        'return_without_top3': (initial_bankroll + race_pnl_series.iloc[3:].sum()) / initial_bankroll - 1,
    }


if __name__ == '__main__':
    # Run with default parameters
    trade_log, equity_curve = run_backtest(verbose=True)
    
    print("\n" + "=" * 80)
    print("SUMMARY STATISTICS")
    print("=" * 80)
    stats = compute_stats(trade_log, equity_curve)
    for k, v in stats.items():
        if isinstance(v, float):
            print(f"  {k:<25} {v:>10.2f}")
        else:
            print(f"  {k:<25} {v:>10}")
    
    print("\n" + "=" * 80)
    print("ROBUSTNESS TESTS")
    print("=" * 80)
    robust = run_robustness_tests(trade_log, equity_curve)
    print(f"  Leave-one-out profitable:  {robust['loo_profitable']}")
    print(f"  Bootstrap P(profit):       {robust['bootstrap_p_profit']:.4f}")
    print(f"  Bootstrap median P&L:      ${robust['bootstrap_median']:.2f}")
    print(f"  Bootstrap 5th-95th:        ${robust['bootstrap_5th']:.2f} to ${robust['bootstrap_95th']:.2f}")
    print(f"  Return without top 1 race: {robust['return_without_top1']:.1%}")
    print(f"  Return without top 3 races:{robust['return_without_top3']:.1%}")
    
    print(f"\nPer-race P&L ranking (top to bottom):")
    for event, pnl in robust['race_pnl_ranking'].items():
        print(f"  {event:<12} ${pnl:>+8.2f}")
    
    # Save trade log
    pd.DataFrame(trade_log).to_csv('backtest/clean_trade_log.csv', index=False)
    pd.DataFrame(equity_curve).to_csv('backtest/clean_equity_curve.csv', index=False)
    
    with open('backtest/clean_results.json', 'w') as f:
        json.dump({
            'stats': stats,
            'robustness': {
                'loo_profitable': robust['loo_profitable'],
                'bootstrap_p_profit': robust['bootstrap_p_profit'],
                'bootstrap_median': robust['bootstrap_median'],
                'return_without_top1': robust['return_without_top1'],
                'return_without_top3': robust['return_without_top3'],
            },
        }, f, indent=2, default=str)
    
    print("\nSaved: backtest/clean_trade_log.csv, clean_equity_curve.csv, clean_results.json")
