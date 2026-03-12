"""
Build a unified trade universe from ALL Kalshi market types.
Every row = one potential trade opportunity (post-qualifying, pre-race).
No lookahead. No leakage.
"""
import json, os, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
import csv

sys.path.insert(0, str(Path(__file__).parent))

# ── Race Calendar ──
RACE_CALENDAR = {
    'AGP25':     {'round': 1,  'name': 'Australia',       'qual_start': '2025-03-15T05:00:00Z', 'race_start': '2025-03-16T04:00:00Z'},
    'CGP25':     {'round': 2,  'name': 'China',           'qual_start': '2025-03-22T07:00:00Z', 'race_start': '2025-03-23T07:00:00Z'},
    'JGP25':     {'round': 3,  'name': 'Japan',           'qual_start': '2025-04-05T06:00:00Z', 'race_start': '2025-04-06T05:00:00Z'},
    'BGP25':     {'round': 4,  'name': 'Bahrain',         'qual_start': '2025-04-12T15:00:00Z', 'race_start': '2025-04-13T15:00:00Z'},
    'SAGP25':    {'round': 5,  'name': 'Saudi Arabia',    'qual_start': '2025-04-19T17:00:00Z', 'race_start': '2025-04-20T17:00:00Z'},
    'MGP25':     {'round': 6,  'name': 'Miami',           'qual_start': '2025-05-03T20:00:00Z', 'race_start': '2025-05-04T20:00:00Z'},
    'ERGP25':    {'round': 7,  'name': 'Emilia Romagna',  'qual_start': '2025-05-17T14:00:00Z', 'race_start': '2025-05-18T13:00:00Z'},
    'MCGP25':    {'round': 8,  'name': 'Monaco',          'qual_start': '2025-05-24T14:00:00Z', 'race_start': '2025-05-25T13:00:00Z'},
    'SGP25':     {'round': 9,  'name': 'Spain',           'qual_start': '2025-05-31T14:00:00Z', 'race_start': '2025-06-01T13:00:00Z'},
    'CAGP25':    {'round': 10, 'name': 'Canada',          'qual_start': '2025-06-14T20:00:00Z', 'race_start': '2025-06-15T18:00:00Z'},
    'AUGP25':    {'round': 11, 'name': 'Austria',         'qual_start': '2025-06-28T14:00:00Z', 'race_start': '2025-06-29T13:00:00Z'},
    'BGP25':     {'round': 4,  'name': 'Bahrain',         'qual_start': '2025-04-12T15:00:00Z', 'race_start': '2025-04-13T15:00:00Z'},
    'BRGP25':    {'round': 12, 'name': 'Great Britain',   'qual_start': '2025-07-05T14:00:00Z', 'race_start': '2025-07-06T14:00:00Z'},
    'BELGP25':   {'round': 13, 'name': 'Belgium',         'qual_start': '2025-07-26T14:00:00Z', 'race_start': '2025-07-27T13:00:00Z'},
    'HUNGP25':   {'round': 14, 'name': 'Hungary',         'qual_start': '2025-08-02T14:00:00Z', 'race_start': '2025-08-03T13:00:00Z'},
    'DUTGP25':   {'round': 15, 'name': 'Netherlands',     'qual_start': '2025-08-30T14:00:00Z', 'race_start': '2025-08-31T13:00:00Z'},
    'ITAGP25':   {'round': 16, 'name': 'Italy',           'qual_start': '2025-09-06T14:00:00Z', 'race_start': '2025-09-07T13:00:00Z'},
    'AZEGP25':   {'round': 17, 'name': 'Azerbaijan',      'qual_start': '2025-09-20T12:00:00Z', 'race_start': '2025-09-21T11:00:00Z'},
    'SINGP25':   {'round': 18, 'name': 'Singapore',       'qual_start': '2025-10-04T13:00:00Z', 'race_start': '2025-10-05T12:00:00Z'},
    'UNISGP25':  {'round': 19, 'name': 'United States',   'qual_start': '2025-10-18T22:00:00Z', 'race_start': '2025-10-19T19:00:00Z'},
    'GRAPDM25':  {'round': 20, 'name': 'Mexico',          'qual_start': '2025-10-25T22:00:00Z', 'race_start': '2025-10-26T20:00:00Z'},
    'SAOPGP25':  {'round': 21, 'name': 'São Paulo',       'qual_start': '2025-11-08T18:00:00Z', 'race_start': '2025-11-09T17:00:00Z'},
    'LASVGP25':  {'round': 22, 'name': 'Las Vegas',       'qual_start': '2025-11-22T06:00:00Z', 'race_start': '2025-11-23T06:00:00Z'},
    'QATGP25':   {'round': 23, 'name': 'Qatar',           'qual_start': '2025-11-29T16:00:00Z', 'race_start': '2025-11-30T16:00:00Z'},
    'ABUDGP25':  {'round': 24, 'name': 'Abu Dhabi',       'qual_start': '2025-12-06T14:00:00Z', 'race_start': '2025-12-07T13:00:00Z'},
}

DRIVER_CODE_MAP = {
    'VER': 'VER', 'NOR': 'NOR', 'PIA': 'PIA', 'LEC': 'LEC', 'SAI': 'SAI',
    'RUS': 'RUS', 'HAM': 'HAM', 'ALO': 'ALO', 'STR': 'STR', 'GAS': 'GAS',
    'OCO': 'OCO', 'TSU': 'TSU', 'RIC': 'RIC', 'HUL': 'HUL', 'MAG': 'MAG',
    'ALB': 'ALB', 'SAR': 'SAR', 'BOT': 'BOT', 'ZHO': 'ZHO', 'BEA': 'BEA',
    'LAW': 'LAW', 'COL': 'COL', 'DOO': 'DOO', 'ANT': 'ANT', 'HAD': 'HAD',
    'BOR': 'BOR', 'IWA': 'IWA',
}

QUAL_DURATION_MIN = 80  # Conservative: Q1+Q2+Q3+breaks

def parse_ts(s):
    s = s.rstrip('Z')
    for fmt in ['%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S']:
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None

def get_post_qual_vwap(trades, qual_end, race_start):
    """VWAP of trades in [qual_end, race_start) — the clean window."""
    volume = 0
    value = 0
    count = 0
    for t in trades:
        ts = parse_ts(t['created_time'])
        if ts is None:
            continue
        if qual_end <= ts < race_start:
            n = float(t.get('count', t.get('count_fp', 1)))
            yes_p = int(t['yes_price']) / 100.0
            volume += n
            value += yes_p * n
            count += 1
    if volume == 0:
        return None, 0, 0
    return value / volume, volume, count

def load_qualifying_results():
    """Load 2025 qualifying results from FastF1 cache."""
    try:
        import fastf1
        fastf1.Cache.enable_cache('/workspace/f1_trading/data/fastf1_cache')
    except:
        pass
    
    results = {}
    for event_code, info in RACE_CALENDAR.items():
        rnd = info['round']
        try:
            import fastf1
            session = fastf1.get_session(2025, rnd, 'Q')
            session.load(telemetry=False, laps=False, weather=False)
            grid = {}
            for _, row in session.results.iterrows():
                pos = int(row['Position']) if not (hasattr(row['Position'], '__float__') and row['Position'] != row['Position']) else None
                if pos and pos <= 20:
                    abbr = row['Abbreviation']
                    grid[abbr] = pos
            results[event_code] = grid
        except Exception as e:
            pass
    return results

def load_race_results():
    """Load 2025 race results from FastF1."""
    try:
        import fastf1
        fastf1.Cache.enable_cache('/workspace/f1_trading/data/fastf1_cache')
    except:
        pass
    
    results = {}
    for event_code, info in RACE_CALENDAR.items():
        rnd = info['round']
        try:
            import fastf1
            session = fastf1.get_session(2025, rnd, 'R')
            session.load(telemetry=False, laps=False, weather=False)
            finish = {}
            for _, row in session.results.iterrows():
                pos = int(row['Position']) if not (hasattr(row['Position'], '__float__') and row['Position'] != row['Position']) else None
                if pos:
                    abbr = row['Abbreviation']
                    finish[abbr] = pos
            results[event_code] = finish
        except Exception as e:
            pass
    return results

def build_universe():
    print("Loading qualifying results...")
    qual_results = load_qualifying_results()
    print(f"  Got qualifying for {len(qual_results)} races")
    
    print("Loading race results...")
    race_results = load_race_results()
    print(f"  Got race results for {len(race_results)} races")
    
    trades_dir = Path('/workspace/f1_trading/data/raw/kalshi_trades')
    universe = []
    
    for event_code, info in sorted(RACE_CALENDAR.items(), key=lambda x: x[1]['round']):
        qual_start = parse_ts(info['qual_start'])
        qual_end = qual_start + timedelta(minutes=QUAL_DURATION_MIN)
        race_start = parse_ts(info['race_start'])
        
        grid = qual_results.get(event_code, {})
        finish = race_results.get(event_code, {})
        
        if not grid or not finish:
            continue
        
        # Process all market types for this race
        for market_type in ['RACE', 'RACEPODIUM', 'FASTESTLAP']:
            prefix = f'KXF1{market_type}-{event_code}-'
            
            for fname in os.listdir(trades_dir):
                if not fname.startswith(prefix) or not fname.endswith('.json'):
                    continue
                
                driver_code = fname.replace(prefix, '').replace('.json', '')
                
                with open(trades_dir / fname) as f:
                    data = json.load(f)
                
                raw_trades = data.get('trades', [])
                result = data.get('result', '')
                
                vwap, vol, n_trades = get_post_qual_vwap(raw_trades, qual_end, race_start)
                
                if vwap is None or n_trades < 3:
                    continue
                
                grid_pos = grid.get(driver_code)
                finish_pos = finish.get(driver_code)
                
                # Determine actual outcome
                if market_type == 'RACE':
                    outcome = 1 if finish_pos == 1 else 0
                elif market_type == 'RACEPODIUM':
                    outcome = 1 if finish_pos is not None and finish_pos <= 3 else 0
                elif market_type == 'FASTESTLAP':
                    outcome = 1 if result == 'yes' else 0
                
                # Cross-check with Kalshi result field
                kalshi_outcome = 1 if result == 'yes' else 0
                if outcome != kalshi_outcome and result in ('yes', 'no'):
                    # Trust Kalshi's result field for settlement
                    outcome = kalshi_outcome
                
                universe.append({
                    'round': info['round'],
                    'event_code': event_code,
                    'race_name': info['name'],
                    'market_type': market_type,
                    'driver': driver_code,
                    'grid_pos': grid_pos,
                    'finish_pos': finish_pos,
                    'outcome': outcome,
                    'yes_vwap': round(vwap, 4),
                    'no_vwap': round(1 - vwap, 4),
                    'volume': vol,
                    'n_trades': n_trades,
                    'qual_end_utc': qual_end.isoformat(),
                    'race_start_utc': race_start.isoformat(),
                })
    
    return universe

if __name__ == '__main__':
    universe = build_universe()
    
    # Save
    outpath = Path('/workspace/f1_trading/backtest/trade_universe.csv')
    if universe:
        keys = universe[0].keys()
        with open(outpath, 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(universe)
    
    print(f"\n{'='*60}")
    print(f"TRADE UNIVERSE: {len(universe)} opportunities")
    
    # Summary
    from collections import Counter
    by_type = Counter(r['market_type'] for r in universe)
    by_race = Counter(r['event_code'] for r in universe)
    print(f"\nBy market type:")
    for k, v in by_type.most_common():
        print(f"  {k}: {v}")
    print(f"\nRaces covered: {len(by_race)}")
    print(f"Avg opportunities per race: {len(universe) / max(len(by_race),1):.1f}")
    
    # Price sanity
    race_winners = [r for r in universe if r['market_type'] == 'RACE']
    print(f"\nRACE winner contracts: {len(race_winners)}")
    print(f"  Mean yes_vwap: {sum(r['yes_vwap'] for r in race_winners)/len(race_winners):.3f}")
    print(f"  Win rate: {sum(r['outcome'] for r in race_winners)/len(race_winners):.3f}")
    
    podium = [r for r in universe if r['market_type'] == 'RACEPODIUM']
    if podium:
        print(f"\nRACEPODIUM contracts: {len(podium)}")
        print(f"  Mean yes_vwap: {sum(r['yes_vwap'] for r in podium)/len(podium):.3f}")
        print(f"  Podium rate: {sum(r['outcome'] for r in podium)/len(podium):.3f}")

    print(f"\nSaved to {outpath}")
