"""
Step 2: Extract post-qualifying, pre-race Kalshi prices.

ANTI-LEAKAGE DESIGN:
  - Only uses trades with timestamps AFTER qualifying ends AND BEFORE race starts
  - qualifying_end = Session4DateUtc + 80 minutes (conservative)
  - race_start = Session5DateUtc
  - Returns VWAP (volume-weighted average price) in that window
  - Also returns trade count so we can see liquidity

This is the entry price a real trader would get Saturday evening.
"""

import json
import os
import pandas as pd
from datetime import datetime
from collections import defaultdict

from backtest.race_calendar import get_race_calendar, KALSHI_TO_F1


def load_all_trades(data_dir='data/raw'):
    """
    Load all trades from kalshi_all.json + individual trade files.
    Individual files may have trades not in the aggregate file.
    Returns list of dicts with: ticker, created_time, yes_price, no_price, count
    """
    all_trades = []
    
    # Load aggregate file
    agg_path = os.path.join(data_dir, 'kalshi_all.json')
    with open(agg_path) as f:
        agg = json.load(f)
    
    # Index by trade_id to deduplicate
    seen_ids = set()
    for t in agg:
        tid = t.get('trade_id', '')
        if tid:
            seen_ids.add(tid)
        all_trades.append({
            'ticker': t['ticker'],
            'created_time': t['created_time'],
            'yes_price_cents': int(t['yes_price']),
            'no_price_cents': int(t['no_price']),
            'count': int(t.get('count', 1)),
        })
    
    # Load individual files for any additional trades
    trade_dir = os.path.join(data_dir, 'kalshi_trades')
    if os.path.exists(trade_dir):
        for fname in os.listdir(trade_dir):
            if not fname.endswith('.json'):
                continue
            fpath = os.path.join(trade_dir, fname)
            with open(fpath) as f:
                data = json.load(f)
            
            # Individual files have structure: {ticker, trades: [...], result, ...}
            if isinstance(data, dict) and 'trades' in data:
                for t in data['trades']:
                    tid = t.get('trade_id', '')
                    if tid and tid in seen_ids:
                        continue
                    if tid:
                        seen_ids.add(tid)
                    all_trades.append({
                        'ticker': t['ticker'],
                        'created_time': t['created_time'],
                        'yes_price_cents': int(t['yes_price']),
                        'no_price_cents': int(t['no_price']),
                        'count': int(t.get('count', 1)),
                    })
    
    return all_trades


def load_outcomes(data_dir='data/raw'):
    """
    Load market outcomes (yes/no) from individual trade files.
    Returns dict: ticker -> 'yes' or 'no'
    """
    outcomes = {}
    trade_dir = os.path.join(data_dir, 'kalshi_trades')
    if not os.path.exists(trade_dir):
        return outcomes
    
    for fname in os.listdir(trade_dir):
        if not fname.endswith('.json'):
            continue
        fpath = os.path.join(trade_dir, fname)
        with open(fpath) as f:
            data = json.load(f)
        if isinstance(data, dict) and 'result' in data:
            outcomes[data['ticker']] = data['result']
    
    return outcomes


def parse_ticker(ticker):
    """
    Parse ticker like 'KXF1RACE-SAGP25-VER' into (market_type, event_code, driver_code).
    market_type: 'RACE' or 'RACEPODIUM'
    """
    parts = ticker.split('-')
    if len(parts) != 3:
        return None, None, None
    
    prefix = parts[0]
    if prefix == 'KXF1RACE':
        market_type = 'RACE'
    elif prefix == 'KXF1RACEPODIUM':
        market_type = 'RACEPODIUM'
    else:
        return None, None, None
    
    return market_type, parts[1], parts[2]


def get_post_qual_prices(calendar_df=None, data_dir='data/raw'):
    """
    For each race, extract VWAP prices in the post-qualifying, pre-race window.
    
    Returns DataFrame with columns:
      - kalshi_event, market_type, driver_code
      - vwap_yes_cents: volume-weighted avg yes price (cents)
      - vwap_no_cents: volume-weighted avg no price (cents)
      - trade_count: number of trades in window
      - total_volume: total contracts traded in window
      - window_start, window_end: the time window used
    """
    if calendar_df is None:
        calendar_df = get_race_calendar()
    
    all_trades = load_all_trades(data_dir)
    
    # Build calendar lookup: event_code -> (quali_end, race_start)
    cal_lookup = {}
    for _, row in calendar_df.iterrows():
        cal_lookup[row['kalshi_event']] = (
            row['quali_end_utc'],
            row['race_start_utc'],
        )
    
    # Group trades by event+market+driver
    grouped = defaultdict(list)
    for t in all_trades:
        market_type, event_code, driver_code = parse_ticker(t['ticker'])
        if market_type is None:
            continue
        if event_code not in cal_lookup:
            continue
        grouped[(event_code, market_type, driver_code)].append(t)
    
    rows = []
    for (event_code, market_type, driver_code), trades in grouped.items():
        quali_end, race_start = cal_lookup[event_code]
        
        # Filter to post-qualifying, pre-race window
        window_trades = []
        for t in trades:
            ts_str = t['created_time']
            # Parse ISO timestamp
            ts = pd.Timestamp(ts_str.rstrip('Z')).tz_localize(None)
            if quali_end <= ts < race_start:
                window_trades.append(t)
        
        if not window_trades:
            continue
        
        # Compute VWAP
        total_vol = sum(t['count'] for t in window_trades)
        vwap_yes = sum(t['yes_price_cents'] * t['count'] for t in window_trades) / total_vol
        vwap_no = sum(t['no_price_cents'] * t['count'] for t in window_trades) / total_vol
        
        rows.append({
            'kalshi_event': event_code,
            'market_type': market_type,
            'driver_code': driver_code,
            'vwap_yes_cents': round(vwap_yes, 2),
            'vwap_no_cents': round(vwap_no, 2),
            'trade_count': len(window_trades),
            'total_volume': total_vol,
            'window_start': str(quali_end),
            'window_end': str(race_start),
        })
    
    return pd.DataFrame(rows)


if __name__ == '__main__':
    print("Loading calendar...")
    cal = get_race_calendar()
    
    print("Extracting post-qualifying prices...")
    prices = get_post_qual_prices(cal)
    
    print(f"\nTotal price observations: {len(prices)}")
    print(f"Events with data: {prices['kalshi_event'].nunique()}")
    print(f"Market types: {prices['market_type'].value_counts().to_dict()}")
    
    # Show sample
    print("\nSample (Saudi Arabia RACE):")
    sample = prices[(prices['kalshi_event'] == 'SAGP25') & (prices['market_type'] == 'RACE')]
    print(sample.sort_values('vwap_yes_cents', ascending=False).to_string(index=False))
    
    # Show events with low liquidity
    event_stats = prices.groupby('kalshi_event').agg(
        drivers=('driver_code', 'count'),
        total_trades=('trade_count', 'sum'),
        avg_trades_per_driver=('trade_count', 'mean'),
    ).sort_values('total_trades')
    print("\nLiquidity by event:")
    print(event_stats.to_string())
