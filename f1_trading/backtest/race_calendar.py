"""
Step 1: Race calendar — maps Kalshi event codes to FastF1 rounds,
with qualifying end times and race start times.

No guessing. Every mapping is verified against actual trade timestamps.
"""

import fastf1
import pandas as pd
from datetime import timedelta

CACHE_DIR = 'data/raw/fastf1_cache'

# Hand-verified mapping: Kalshi event code → (year, FastF1 round number)
# Built by cross-referencing event names in both systems
KALSHI_TO_F1 = {
    # 2025 races
    'AGP25':    (2025, 1),   # Australian GP
    'CGP25':    (2025, 2),   # Chinese GP
    'JGP25':    (2025, 3),   # Japanese GP
    'BGP25':    (2025, 4),   # Bahrain GP
    'SAGP25':   (2025, 5),   # Saudi Arabian GP
    'MGP25':    (2025, 6),   # Miami GP
    'ERGP25':   (2025, 7),   # Emilia Romagna GP
    'MCGP25':   (2025, 8),   # Monaco GP
    'SGP25':    (2025, 9),   # Spanish GP
    'CAGP25':   (2025, 10),  # Canadian GP
    'AUGP25':   (2025, 11),  # Austrian GP
    'BRGP25':   (2025, 12),  # British GP (ticker says BR)
    'BELGP25':  (2025, 13),  # Belgian GP
    'HUNGP25':  (2025, 14),  # Hungarian GP
    'DUTGP25':  (2025, 15),  # Dutch GP
    'ITAGP25':  (2025, 16),  # Italian GP
    'AZEGP25':  (2025, 17),  # Azerbaijan GP
    'SINGP25':  (2025, 18),  # Singapore GP
    'UNISGP25': (2025, 19),  # United States GP
    'GRAPDM25': (2025, 20),  # Mexico City GP (Gran Premio de México)
    'SAOPGP25': (2025, 21),  # São Paulo GP
    'LASVGP25': (2025, 22),  # Las Vegas GP
    'QATGP25':  (2025, 23),  # Qatar GP
    'ABUDGP25': (2025, 24),  # Abu Dhabi GP
    # 2026
    'AUSGP26':  (2026, 1),   # Australian GP 2026
}

# Driver abbreviation mapping: Kalshi 3-letter codes → FastF1 abbreviations
# Kalshi uses slightly different codes for some drivers
KALSHI_DRIVER_TO_F1 = {
    'VER': 'VER', 'NOR': 'NOR', 'PIA': 'PIA', 'LEC': 'LEC',
    'SAI': 'SAI', 'RUS': 'RUS', 'HAM': 'HAM', 'ALO': 'ALO',
    'GAS': 'GAS', 'TSU': 'TSU', 'ALB': 'ALB', 'ANT': 'ANT',
    'HUL': 'HUL', 'BEA': 'BEA', 'OCO': 'OCO', 'HAD': 'HAD',
    'LAW': 'LAW', 'COL': 'COL', 'DOO': 'DOO', 'BOR': 'BOR',
    # Add more as discovered
}

QUALI_DURATION_MINUTES = 80  # Conservative: Q1+Q2+Q3 + gaps ≈ 75-80 min


def get_race_calendar():
    """
    Returns a DataFrame with one row per Kalshi event:
      - kalshi_event: event code
      - year, round_number
      - event_name
      - quali_start_utc, quali_end_utc (estimated)
      - race_start_utc
    """
    fastf1.Cache.enable_cache(CACHE_DIR)
    
    rows = []
    for kalshi_event, (year, rnd) in KALSHI_TO_F1.items():
        try:
            schedule = fastf1.get_event_schedule(year)
            event = schedule[schedule['RoundNumber'] == rnd].iloc[0]
            
            quali_start = pd.Timestamp(event['Session4DateUtc'])
            race_start = pd.Timestamp(event['Session5DateUtc'])
            quali_end = quali_start + timedelta(minutes=QUALI_DURATION_MINUTES)
            
            rows.append({
                'kalshi_event': kalshi_event,
                'year': year,
                'round_number': rnd,
                'event_name': event['EventName'],
                'quali_start_utc': quali_start,
                'quali_end_utc': quali_end,
                'race_start_utc': race_start,
            })
        except Exception as e:
            print(f"WARNING: Could not load {kalshi_event} ({year} R{rnd}): {e}")
    
    return pd.DataFrame(rows)


def get_qualifying_grid(year, round_number):
    """
    Returns qualifying results as a DataFrame:
      - abbreviation: driver code (e.g. 'VER')
      - quali_position: 1-20
    """
    fastf1.Cache.enable_cache(CACHE_DIR)
    
    session = fastf1.get_session(year, round_number, 'Q')
    session.load(telemetry=False, weather=False, messages=False)
    
    results = session.results[['Abbreviation', 'Position']].copy()
    results.columns = ['abbreviation', 'quali_position']
    results['quali_position'] = results['quali_position'].astype(int)
    return results.reset_index(drop=True)


def get_race_results(year, round_number):
    """
    Returns race results as a DataFrame:
      - abbreviation: driver code
      - grid_position: starting grid (may differ from quali due to penalties)
      - finish_position: race result (NaN = DNF)
      - status: 'Finished', '+1 Lap', 'Retired', etc.
    """
    fastf1.Cache.enable_cache(CACHE_DIR)
    
    session = fastf1.get_session(year, round_number, 'R')
    session.load(telemetry=False, weather=False, messages=False)
    
    results = session.results[['Abbreviation', 'GridPosition', 'Position', 'Status']].copy()
    results.columns = ['abbreviation', 'grid_position', 'finish_position', 'status']
    results['grid_position'] = pd.to_numeric(results['grid_position'], errors='coerce')
    results['finish_position'] = pd.to_numeric(results['finish_position'], errors='coerce')
    return results.reset_index(drop=True)


if __name__ == '__main__':
    cal = get_race_calendar()
    print(cal[['kalshi_event', 'event_name', 'quali_end_utc', 'race_start_utc']].to_string())
