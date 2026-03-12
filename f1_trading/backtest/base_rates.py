"""
Step 3: Historical base rates — P(win|grid_position) and P(podium|grid_position)
from 2019-2024 FastF1 data.

ANTI-LEAKAGE: Only uses 2019-2024 seasons. No 2025 data touches these rates.
"""

import fastf1
import pandas as pd
from collections import defaultdict

CACHE_DIR = 'data/raw/fastf1_cache'
HISTORICAL_YEARS = [2019, 2020, 2021, 2022, 2023, 2024]


def build_base_rates(years=None):
    """
    Compute P(win|grid) and P(podium|grid) from historical race results.
    
    Returns DataFrame with columns:
      - grid_position (1-20)
      - n_starts: how many times a driver started from this position
      - n_wins: how many times they won from this position
      - n_podiums: how many times they finished top 3 from this position
      - p_win: n_wins / n_starts
      - p_podium: n_podiums / n_starts
    """
    if years is None:
        years = HISTORICAL_YEARS
    
    fastf1.Cache.enable_cache(CACHE_DIR)
    
    records = []
    
    for year in years:
        schedule = fastf1.get_event_schedule(year)
        rounds = schedule[schedule['RoundNumber'] > 0]['RoundNumber'].tolist()
        
        for rnd in rounds:
            try:
                session = fastf1.get_session(year, rnd, 'R')
                session.load(telemetry=False, weather=False, messages=False)
                results = session.results
                
                for _, row in results.iterrows():
                    grid = pd.to_numeric(row.get('GridPosition'), errors='coerce')
                    finish = pd.to_numeric(row.get('Position'), errors='coerce')
                    
                    if pd.isna(grid) or pd.isna(finish) or grid == 0:
                        continue
                    
                    records.append({
                        'year': year,
                        'round': rnd,
                        'driver': row.get('Abbreviation', ''),
                        'grid_position': int(grid),
                        'finish_position': int(finish),
                        'won': int(finish) == 1,
                        'podium': int(finish) <= 3,
                    })
            except Exception as e:
                print(f"  Skipping {year} R{rnd}: {e}")
    
    df = pd.DataFrame(records)
    
    # Aggregate by grid position
    rates = df.groupby('grid_position').agg(
        n_starts=('won', 'count'),
        n_wins=('won', 'sum'),
        n_podiums=('podium', 'sum'),
    ).reset_index()
    
    rates['p_win'] = rates['n_wins'] / rates['n_starts']
    rates['p_podium'] = rates['n_podiums'] / rates['n_starts']
    
    return rates, df


if __name__ == '__main__':
    print("Building base rates from 2019-2024...")
    rates, raw = build_base_rates()
    
    print(f"\nTotal race starts: {len(raw)}")
    print(f"Races covered: {raw.groupby(['year', 'round']).ngroup().nunique()}")
    print(f"\nBase rates (grid positions 1-10):")
    print(rates[rates['grid_position'] <= 10].to_string(index=False))
    
    print(f"\nBase rates (grid positions 11-20):")
    print(rates[(rates['grid_position'] >= 11) & (rates['grid_position'] <= 20)].to_string(index=False))
    
    # Save for reference
    rates.to_csv('backtest/base_rates_2019_2024.csv', index=False)
    print("\nSaved to backtest/base_rates_2019_2024.csv")
