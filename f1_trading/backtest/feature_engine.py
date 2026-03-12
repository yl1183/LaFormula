"""
Feature Engine — extract ALL available pre-race signals from FastF1 + Kalshi.

ANTI-LEAKAGE GUARANTEES:
  - All features derived from sessions BEFORE the race (FP1, FP2, FP3, Qualifying)
  - No race results or in-race data used
  - Historical features (rolling stats) use only prior races
  - Kalshi prices are post-qualifying, pre-race only (timestamp verified)
"""

import fastf1
import pandas as pd
import numpy as np
import json, os, warnings
from datetime import timedelta, timezone, datetime
from pathlib import Path
from collections import defaultdict

warnings.filterwarnings('ignore')
import logging
logging.getLogger('fastf1').setLevel(logging.ERROR)

CACHE_DIR = str(Path(__file__).parent.parent / 'data' / 'raw' / 'fastf1_cache')
fastf1.Cache.enable_cache(CACHE_DIR)


# ── TEAM MAPPING (2025) ──
TEAM_TIERS_2025 = {
    'McLaren': 1, 'Ferrari': 1, 'Red Bull Racing': 1,
    'Mercedes': 2, 'Aston Martin': 2,
    'Alpine': 3, 'Racing Bulls': 3, 'Williams': 3,
    'Haas F1 Team': 3, 'Kick Sauber': 3,
}

# ── TRACK CHARACTERISTICS ──
STREET_CIRCUITS = {1: False, 2: False, 3: False, 4: False, 5: True,  # Jeddah
                   6: True, 7: False, 8: True, 9: False, 10: True,   # Monaco, Montreal
                   11: False, 12: False, 13: False, 14: False, 15: False,
                   16: False, 17: True, 18: True, 19: False, 20: False,  # Baku, Singapore
                   21: False, 22: True, 23: False, 24: False}  # Las Vegas

HIGH_ATTRITION_TRACKS = {1, 5, 6, 8, 10, 17, 18, 22}  # Historically high DNF rates

# ── NATIONALITY → HOME RACE MAPPING ──
DRIVER_NATIONALITY = {
    'VER': 'NL', 'NOR': 'GB', 'PIA': 'AU', 'LEC': 'MC', 'SAI': 'ES',
    'RUS': 'GB', 'HAM': 'GB', 'ALO': 'ES', 'STR': 'CA', 'GAS': 'FR',
    'OCO': 'FR', 'TSU': 'JP', 'HAD': 'FR', 'HUL': 'DE', 'MAG': 'DK',
    'ALB': 'TH', 'BOR': 'BR', 'BEA': 'US', 'LAW': 'GB', 'DOO': 'AU',
    'ANT': 'IT', 'COL': 'AR',
}

HOME_RACE_MAP = {  # round → nationality that's "home"
    1: 'AU',   # Australia
    3: 'JP',   # Japan
    6: 'US',   # Miami
    7: 'IT',   # Emilia Romagna
    8: 'MC',   # Monaco
    9: 'ES',   # Spain
    10: 'CA',  # Canada
    11: 'AT',  # Austria (no Austrian driver in 2025)
    12: 'GB',  # Britain
    13: 'BE',  # Belgium
    14: 'HU',  # Hungary
    15: 'NL',  # Netherlands
    16: 'IT',  # Italy
    17: 'AZ',  # Azerbaijan
    18: 'SG',  # Singapore
    19: 'US',  # United States
    20: 'MX',  # Mexico
    21: 'BR',  # São Paulo
    22: 'US',  # Las Vegas
    23: 'QA',  # Qatar
    24: 'AE',  # Abu Dhabi
}


def extract_fp_pace(year, rnd, session_name='FP2'):
    """
    Extract practice pace metrics per driver.
    Returns dict: driver_code → {best_lap, long_run_median, long_run_consistency, n_laps}
    """
    try:
        session = fastf1.get_session(year, rnd, session_name)
        session.load(telemetry=False, weather=False)
        laps = session.laps
    except Exception:
        return {}
    
    if laps is None or laps.empty:
        return {}
    
    # Filter to valid laps (accurate timing, no pit in/out)
    valid = laps[laps['IsAccurate'] == True].copy() if 'IsAccurate' in laps.columns else laps.copy()
    valid = valid.dropna(subset=['LapTime'])
    valid['LapSec'] = valid['LapTime'].dt.total_seconds()
    
    # Remove outlier laps (>107% of session best)
    session_best = valid['LapSec'].min()
    valid = valid[valid['LapSec'] < session_best * 1.07]
    
    results = {}
    for driver, dlaps in valid.groupby('Driver'):
        best = dlaps['LapSec'].min()
        
        # Long runs = stints with 5+ consecutive laps on same compound
        long_run_laps = []
        for (stint, compound), stint_laps in dlaps.groupby(['Stint', 'Compound']):
            if len(stint_laps) >= 5:
                long_run_laps.extend(stint_laps['LapSec'].values)
        
        lr_median = np.median(long_run_laps) if long_run_laps else None
        lr_std = np.std(long_run_laps) if len(long_run_laps) >= 3 else None
        
        results[driver] = {
            'fp_best_lap': best,
            'fp_long_run_median': lr_median,
            'fp_long_run_std': lr_std,
            'fp_n_laps': len(dlaps),
            'fp_n_long_run_laps': len(long_run_laps),
        }
    
    # Normalize to deltas from session best
    best_overall = min(r['fp_best_lap'] for r in results.values())
    best_lr = min((r['fp_long_run_median'] for r in results.values() if r['fp_long_run_median']), default=None)
    
    for driver, r in results.items():
        r['fp_best_delta'] = r['fp_best_lap'] - best_overall
        r['fp_lr_delta'] = (r['fp_long_run_median'] - best_lr) if (r['fp_long_run_median'] and best_lr) else None
    
    return results


def extract_qualifying_detail(year, rnd):
    """
    Extract Q1/Q2/Q3 progression and qualifying gaps.
    Returns dict: driver_code → {q1_sec, q2_sec, q3_sec, q_improvement, gap_to_pole, gap_to_teammate}
    """
    try:
        session = fastf1.get_session(year, rnd, 'Q')
        session.load(telemetry=False, laps=False, weather=False)
        res = session.results
    except Exception:
        return {}
    
    if res is None or res.empty:
        return {}
    
    results = {}
    team_times = defaultdict(list)
    
    for _, row in res.iterrows():
        driver = row['Abbreviation']
        pos = int(row['Position']) if pd.notna(row['Position']) else None
        team = row['TeamName']
        
        q1 = row['Q1'].total_seconds() if pd.notna(row['Q1']) else None
        q2 = row['Q2'].total_seconds() if pd.notna(row['Q2']) else None
        q3 = row['Q3'].total_seconds() if pd.notna(row['Q3']) else None
        
        best_q = q3 or q2 or q1
        
        # Q1→Q2→Q3 improvement (negative = getting faster = good)
        improvement = None
        if q1 and q2:
            improvement = (q2 - q1) / q1  # fraction faster in Q2 vs Q1
            if q3:
                improvement = (q3 - q1) / q1  # overall Q1→Q3
        
        results[driver] = {
            'qual_pos': pos,
            'q1_sec': q1,
            'q2_sec': q2,
            'q3_sec': q3,
            'q_best_sec': best_q,
            'q_improvement': improvement,  # negative = improving through sessions
            'team': team,
        }
        
        if best_q:
            team_times[team].append((driver, best_q))
    
    # Compute gap to pole
    pole_time = min((r['q_best_sec'] for r in results.values() if r['q_best_sec']), default=None)
    if pole_time:
        for r in results.values():
            r['gap_to_pole'] = (r['q_best_sec'] - pole_time) if r['q_best_sec'] else None
    
    # Compute gap to teammate
    for team, drivers in team_times.items():
        if len(drivers) == 2:
            d1, t1 = drivers[0]
            d2, t2 = drivers[1]
            results[d1]['gap_to_teammate'] = t1 - t2  # positive = slower than teammate
            results[d2]['gap_to_teammate'] = t2 - t1
        elif len(drivers) == 1:
            results[drivers[0][0]]['gap_to_teammate'] = None
    
    return results


def extract_race_results(year, rnd):
    """Get race finish positions and status (for building rolling features)."""
    try:
        session = fastf1.get_session(year, rnd, 'R')
        session.load(telemetry=False, laps=False, weather=False)
        res = session.results
    except Exception:
        return {}
    
    results = {}
    for _, row in res.iterrows():
        driver = row['Abbreviation']
        pos = int(row['Position']) if pd.notna(row['Position']) else None
        grid = int(row['GridPosition']) if pd.notna(row['GridPosition']) else None
        status = row['Status']
        dnf = 0 if status == 'Finished' or status.startswith('+') else 1
        points = float(row['Points']) if pd.notna(row['Points']) else 0
        
        results[driver] = {
            'finish_pos': pos,
            'grid_pos': grid,
            'dnf': dnf,
            'points': points,
            'status': status,
            'positions_gained': (grid - pos) if (grid and pos) else None,
        }
    
    return results


def build_rolling_features(year=2025, lookback=5):
    """
    Build rolling driver-level features from prior races (NO LEAKAGE).
    For each race N, uses only races 1..N-1.
    Also pulls from prior year for early-season races.
    """
    # Load all 2024 results for prior-year features
    prior_results = {}  # driver → list of {finish_pos, grid_pos, dnf, points, positions_gained}
    for rnd in range(1, 25):
        try:
            race = extract_race_results(2024, rnd)
            for driver, res in race.items():
                if driver not in prior_results:
                    prior_results[driver] = []
                prior_results[driver].append(res)
        except:
            pass
    
    # Build rolling features for each 2025 race
    current_results = defaultdict(list)  # driver → list of results so far in 2025
    rolling = {}  # (round, driver) → features
    
    for rnd in range(1, 25):
        race = extract_race_results(year, rnd)
        
        for driver in race:
            # Combine prior year + current year (up to but NOT including this race)
            history = prior_results.get(driver, []) + current_results.get(driver, [])
            recent = history[-lookback:] if history else []
            
            if recent:
                avg_finish = np.mean([r['finish_pos'] for r in recent if r['finish_pos']])
                avg_grid = np.mean([r['grid_pos'] for r in recent if r['grid_pos']])
                avg_gained = np.mean([r['positions_gained'] for r in recent if r['positions_gained'] is not None])
                dnf_rate = np.mean([r['dnf'] for r in recent])
                avg_points = np.mean([r['points'] for r in recent])
                consistency = np.std([r['finish_pos'] for r in recent if r['finish_pos']]) if len(recent) >= 2 else None
            else:
                avg_finish = avg_grid = avg_gained = dnf_rate = avg_points = consistency = None
            
            rolling[(rnd, driver)] = {
                'rolling_avg_finish': avg_finish,
                'rolling_avg_grid': avg_grid,
                'rolling_avg_gained': avg_gained,
                'rolling_dnf_rate': dnf_rate,
                'rolling_avg_points': avg_points,
                'rolling_consistency': consistency,
                'n_prior_races': len(history),
            }
        
        # NOW add this race to history (after computing features for it)
        for driver, res in race.items():
            current_results[driver].append(res)
    
    return rolling


def extract_kalshi_volume_features(trades_dir, event_code, qual_end, race_start):
    """
    Extract volume/momentum features from Kalshi trade flow.
    Timestamp-verified: only uses post-quali, pre-race data.
    """
    from backtest.build_trade_universe import parse_ts  # already on path
    
    features = {}  # (market_type, driver) → features
    
    for market_type in ['RACE', 'RACEPODIUM', 'FASTESTLAP']:
        prefix = f'KXF1{market_type}-{event_code}-'
        
        for fname in os.listdir(trades_dir):
            if not fname.startswith(prefix) or not fname.endswith('.json'):
                continue
            
            driver = fname.replace(prefix, '').replace('.json', '')
            
            with open(os.path.join(trades_dir, fname)) as f:
                data = json.load(f)
            
            raw_trades = data.get('trades', [])
            
            # Split post-qualifying window into halves
            midpoint = qual_end + (race_start - qual_end) / 2
            
            early_prices, late_prices = [], []
            early_vol, late_vol = 0, 0
            
            for t in raw_trades:
                ts = parse_ts(t['created_time'])
                if ts is None:
                    continue
                if qual_end <= ts < race_start:
                    p = int(t['yes_price']) / 100.0
                    n = float(t.get('count', 1))
                    if ts < midpoint:
                        early_prices.append(p)
                        early_vol += n
                    else:
                        late_prices.append(p)
                        late_vol += n
            
            if not early_prices and not late_prices:
                continue
            
            early_vwap = np.mean(early_prices) if early_prices else None
            late_vwap = np.mean(late_prices) if late_prices else None
            
            # Price drift: are people buying more/less as race approaches?
            drift = (late_vwap - early_vwap) if (early_vwap and late_vwap) else None
            
            # Volume acceleration
            vol_ratio = (late_vol / early_vol) if early_vol > 0 else None
            
            features[(market_type, driver)] = {
                'early_vwap': early_vwap,
                'late_vwap': late_vwap,
                'price_drift': drift,  # positive = market moving YES
                'total_volume': early_vol + late_vol,
                'volume_ratio': vol_ratio,  # >1 = late volume surge
            }
    
    return features


def build_full_feature_matrix(year=2025):
    """
    Build the complete feature matrix for all tradeable opportunities.
    Every feature is pre-race only. No leakage.
    """
    import sys; sys.path.insert(0, str(Path(__file__).parent.parent))
    from backtest.build_trade_universe import RACE_CALENDAR, parse_ts, QUAL_DURATION_MIN
    trades_dir = str(Path(__file__).parent.parent / 'data' / 'raw' / 'kalshi_trades')
    
    print("Building rolling features from 2024+2025 race history...")
    rolling = build_rolling_features(year)
    
    print("Computing base rates from 2019-2024...")
    base_rates = compute_base_rates()
    
    rows = []
    
    for event_code, info in sorted(RACE_CALENDAR.items(), key=lambda x: x[1]['round']):
        rnd = info['round']
        name = info['name']
        print(f"  Processing Round {rnd}: {name}...")
        
        qual_start = parse_ts(info['qual_start'])
        qual_end = qual_start + timedelta(minutes=QUAL_DURATION_MIN)
        race_start = parse_ts(info['race_start'])
        
        # Extract features
        qual_detail = extract_qualifying_detail(year, rnd)
        fp2_pace = extract_fp_pace(year, rnd, 'FP2')
        fp3_pace = extract_fp_pace(year, rnd, 'FP3')
        vol_features = extract_kalshi_volume_features(trades_dir, event_code, qual_end, race_start)
        race_results = extract_race_results(year, rnd)
        
        is_street = STREET_CIRCUITS.get(rnd, False)
        is_high_attrition = rnd in HIGH_ATTRITION_TRACKS
        home_nationality = HOME_RACE_MAP.get(rnd)
        
        # For each driver who has qualifying data AND Kalshi prices
        for driver, qd in qual_detail.items():
            grid_pos = qd['qual_pos']
            if grid_pos is None or grid_pos > 20:
                continue
            
            team = qd.get('team', '')
            team_tier = TEAM_TIERS_2025.get(team, 3)
            
            # Rolling features (no leakage — uses only prior races)
            roll = rolling.get((rnd, driver), {})
            
            # FP2 and FP3 pace
            fp2 = fp2_pace.get(driver, {})
            fp3 = fp3_pace.get(driver, {})
            
            # Driver nationality features
            driver_nat = DRIVER_NATIONALITY.get(driver, '')
            is_home = 1 if (driver_nat == home_nationality) else 0
            
            # Race outcome (for target variable — NOT used as feature)
            race_res = race_results.get(driver, {})
            finish_pos = race_res.get('finish_pos')
            dnf = race_res.get('dnf', 0)
            
            # Base rates
            br_win = base_rates['win'].get(grid_pos, 0.05)
            br_podium = base_rates['podium'].get(grid_pos, 0.15)
            
            # For each market type this driver has Kalshi prices for
            for market_type in ['RACE', 'RACEPODIUM', 'FASTESTLAP']:
                vol = vol_features.get((market_type, driver), {})
                
                if not vol:
                    continue
                
                # Determine outcome
                if market_type == 'RACE':
                    outcome = 1 if finish_pos == 1 else 0
                    base_rate = br_win
                elif market_type == 'RACEPODIUM':
                    outcome = 1 if (finish_pos and finish_pos <= 3) else 0
                    base_rate = br_podium
                elif market_type == 'FASTESTLAP':
                    # Check Kalshi settlement
                    fname = f'KXF1{market_type}-{event_code}-{driver}.json'
                    fpath = os.path.join(trades_dir, fname)
                    if os.path.exists(fpath):
                        with open(fpath) as f:
                            d = json.load(f)
                        outcome = 1 if d.get('result') == 'yes' else 0
                    else:
                        continue
                    base_rate = 1.0 / 20  # crude: 1/20 drivers
                
                # Cross-market features
                cross_winner_price = None
                cross_podium_price = None
                if market_type == 'RACEPODIUM':
                    w_vol = vol_features.get(('RACE', driver), {})
                    if w_vol:
                        cross_winner_price = w_vol.get('late_vwap') or w_vol.get('early_vwap')
                
                yes_price = vol.get('late_vwap') or vol.get('early_vwap')
                if yes_price is None:
                    continue
                
                row = {
                    # Identifiers
                    'round': rnd,
                    'event_code': event_code,
                    'race_name': name,
                    'market_type': market_type,
                    'driver': driver,
                    'team': team,
                    
                    # Target (NOT a feature)
                    'outcome': outcome,
                    'finish_pos': finish_pos,
                    
                    # ── PRICE FEATURES ──
                    'yes_price': round(yes_price, 4),
                    'no_price': round(1 - yes_price, 4),
                    'base_rate': round(base_rate, 4),
                    'edge_vs_base': round(base_rate - yes_price, 4),  # positive = YES underpriced
                    'cross_winner_price': cross_winner_price,
                    
                    # ── QUALIFYING FEATURES ──
                    'grid_pos': grid_pos,
                    'gap_to_pole': qd.get('gap_to_pole'),
                    'gap_to_teammate': qd.get('gap_to_teammate'),
                    'q_improvement': qd.get('q_improvement'),
                    'q1_sec': qd.get('q1_sec'),
                    'q3_sec': qd.get('q3_sec'),
                    
                    # ── PRACTICE PACE FEATURES ──
                    'fp2_best_delta': fp2.get('fp_best_delta'),
                    'fp2_lr_delta': fp2.get('fp_lr_delta'),
                    'fp2_lr_std': fp2.get('fp_long_run_std'),
                    'fp2_n_laps': fp2.get('fp_n_laps'),
                    'fp3_best_delta': fp3.get('fp_best_delta'),
                    
                    # ── ROLLING FEATURES (no leakage) ──
                    'rolling_avg_finish': roll.get('rolling_avg_finish'),
                    'rolling_avg_grid': roll.get('rolling_avg_grid'),
                    'rolling_avg_gained': roll.get('rolling_avg_gained'),
                    'rolling_dnf_rate': roll.get('rolling_dnf_rate'),
                    'rolling_avg_points': roll.get('rolling_avg_points'),
                    'rolling_consistency': roll.get('rolling_consistency'),
                    'n_prior_races': roll.get('n_prior_races', 0),
                    
                    # ── CONTEXTUAL FEATURES ──
                    'team_tier': team_tier,
                    'is_street_circuit': int(is_street),
                    'is_high_attrition': int(is_high_attrition),
                    'is_home_race': is_home,
                    
                    # ── VOLUME/MOMENTUM FEATURES ──
                    'price_drift': vol.get('price_drift'),
                    'total_volume': vol.get('total_volume', 0),
                    'volume_ratio': vol.get('volume_ratio'),
                }
                
                rows.append(row)
    
    return pd.DataFrame(rows)


def compute_base_rates(years=range(2019, 2025)):
    """
    Compute P(win|grid_pos) and P(podium|grid_pos) from historical data.
    Uses ONLY years specified (default: 2019-2024, NO 2025).
    """
    records = []
    
    for year in years:
        for rnd in range(1, 25):
            try:
                session = fastf1.get_session(year, rnd, 'R')
                session.load(telemetry=False, laps=False, weather=False)
                res = session.results
                
                for _, row in res.iterrows():
                    pos = int(row['Position']) if pd.notna(row['Position']) else None
                    grid = int(row['GridPosition']) if pd.notna(row['GridPosition']) else None
                    
                    if pos and grid and grid <= 20:
                        records.append({
                            'year': year,
                            'round': rnd,
                            'grid_pos': grid,
                            'finish_pos': pos,
                            'won': 1 if pos == 1 else 0,
                            'podium': 1 if pos <= 3 else 0,
                        })
            except:
                pass
    
    df = pd.DataFrame(records)
    
    win_rates = df.groupby('grid_pos')['won'].mean().to_dict()
    podium_rates = df.groupby('grid_pos')['podium'].mean().to_dict()
    
    return {'win': win_rates, 'podium': podium_rates, 'n_races': len(df)}


if __name__ == '__main__':
    import sys; sys.path.insert(0, str(Path(__file__).parent.parent))
    print("Building full feature matrix...")
    df = build_full_feature_matrix(2025)
    
    outpath = Path(__file__).parent / 'feature_matrix.csv'
    df.to_csv(outpath, index=False)
    
    print(f"\n{'='*60}")
    print(f"Feature matrix: {len(df)} rows × {len(df.columns)} columns")
    print(f"\nMarket types: {df['market_type'].value_counts().to_dict()}")
    print(f"Rounds covered: {sorted(df['round'].unique())}")
    print(f"\nFeature completeness:")
    for col in df.columns:
        pct = df[col].notna().mean() * 100
        if pct < 100:
            print(f"  {col}: {pct:.0f}%")
    print(f"\nSaved to {outpath}")
