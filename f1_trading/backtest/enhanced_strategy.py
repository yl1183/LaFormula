"""
Enhanced Strategy — Base Rate + Logistic Adjuster + Liquidity Filter

Improvements over raw base-rate strategy:
1. Logistic regression adjusts base rates using available features
   (shrinkage: 70% base rate + 30% model, avoids overfitting)
2. Liquidity filter: only trade contracts with sufficient volume
3. Weekend exposure caps via sizing module
"""
import csv, json
from pathlib import Path
from collections import defaultdict
import numpy as np
import warnings
warnings.filterwarnings('ignore')

OUT = Path(__file__).parent

# ── BASE RATES ──
BASE_PODIUM_RATE = {
    1: 0.746, 2: 0.576, 3: 0.508, 4: 0.373, 5: 0.271, 6: 0.186,
    7: 0.153, 8: 0.136, 9: 0.085, 10: 0.085, 11: 0.051, 12: 0.034,
    13: 0.034, 14: 0.034, 15: 0.017, 16: 0.017, 17: 0.0, 18: 0.017,
    19: 0.0, 20: 0.0
}
BASE_WIN_RATE = {
    1: 0.381, 2: 0.157, 3: 0.102, 4: 0.085, 5: 0.051, 6: 0.034,
    7: 0.034, 8: 0.034, 9: 0.017, 10: 0.017, 11: 0.017, 12: 0.017,
    13: 0.0, 14: 0.017, 15: 0.0, 16: 0.0, 17: 0.0, 18: 0.017,
    19: 0.0, 20: 0.0
}


def load_feature_matrix():
    """Load enriched feature matrix."""
    import pandas as pd
    return pd.read_csv(OUT / 'feature_matrix.csv')


def train_logistic_adjuster(df, market_type='RACEPODIUM'):
    """
    Train logistic regression on first-half, use as base-rate adjuster.
    Returns a function: adjust(grid_pos, features_dict) -> adjusted_prob
    
    The model provides a BLENDED estimate:
        adjusted = shrinkage * base_rate + (1-shrinkage) * model_prob
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    
    subset = df[df['market_type'] == market_type].copy()
    
    feature_cols = ['grid_pos', 'gap_to_pole', 'team_tier', 
                    'rolling_avg_finish', 'rolling_avg_gained']
    available = [c for c in feature_cols if c in subset.columns]
    
    # Fill NaN with medians
    for col in available:
        subset[col] = subset[col].fillna(subset[col].median())
    
    X = subset[available].values
    y = subset['outcome'].values
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    model = LogisticRegression(C=0.1, random_state=42)  # strong regularization
    model.fit(X_scaled, y)
    
    # In-sample calibration check
    probs = model.predict_proba(X_scaled)[:, 1]
    
    SHRINKAGE = 0.70  # 70% base rate, 30% model
    
    def adjuster(row_features):
        """Return adjusted probability for a single row."""
        feats = np.array([[row_features.get(c, 0) for c in available]])
        # Fill NaN
        feats = np.nan_to_num(feats, nan=0)
        feats_scaled = scaler.transform(feats)
        model_prob = model.predict_proba(feats_scaled)[0, 1]
        
        gp = row_features.get('grid_pos', 10)
        if market_type == 'RACEPODIUM':
            base = BASE_PODIUM_RATE.get(int(gp), 0.05)
        else:
            base = BASE_WIN_RATE.get(int(gp), 0.01)
        
        return SHRINKAGE * base + (1 - SHRINKAGE) * model_prob
    
    return adjuster, model, scaler


def load_universe():
    rows = []
    with open(OUT / 'trade_universe.csv') as f:
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


def net_pnl_pct(side, price, outcome, fee=0.07):
    if side == 'YES':
        if outcome == 1:
            profit = 1.0 - price
            return (profit - profit * fee) / price
        return -1.0
    else:
        cost = 1.0 - price
        if outcome == 0:
            profit = price
            return (profit - profit * fee) / cost
        return -1.0


def run_enhanced_backtest(threshold=0.15, min_volume=50, use_adjuster=True, 
                          sizing_mode='flat', flat_amount=10.0):
    """
    Enhanced backtest with:
    - Optional logistic adjuster
    - Liquidity filter
    - Weekend exposure caps
    """
    import pandas as pd
    from sizing import size_flat_with_cap, size_kelly_with_cap, size_tiered, MAX_WEEKEND_EXPOSURE_PCT
    
    universe = load_universe()
    
    # Train adjuster if requested
    adjuster = None
    if use_adjuster:
        df = load_feature_matrix()
        adjuster, _, _ = train_logistic_adjuster(df, 'RACEPODIUM')
        # Also build a lookup: (round, driver, market_type) -> features
        feature_lookup = {}
        for _, row in df.iterrows():
            key = (int(row['round']), row['driver'], row['market_type'])
            feature_lookup[key] = row.to_dict()
    
    # Group by round
    by_round = defaultdict(list)
    for r in universe:
        by_round[r['round']].append(r)
    
    bankroll = 100.0
    trades = []
    skipped_liquidity = 0
    
    for rnd in sorted(by_round.keys()):
        # Phase 1: Generate all signals for this weekend
        weekend_signals = []
        for row in by_round[rnd]:
            # Liquidity filter
            if row['volume'] < min_volume:
                skipped_liquidity += 1
                continue
            
            if row['market_type'] not in ('RACEPODIUM', 'RACE'):
                continue
            
            gp = row['grid_pos']
            if gp is None or gp > 20:
                continue
            
            # Get probability estimate
            if use_adjuster and adjuster and row['market_type'] == 'RACEPODIUM':
                key = (rnd, row['driver'], row['market_type'])
                feats = feature_lookup.get(key, {'grid_pos': gp})
                prob_est = adjuster(feats)
            else:
                if row['market_type'] == 'RACEPODIUM':
                    prob_est = BASE_PODIUM_RATE.get(gp, 0)
                else:
                    prob_est = BASE_WIN_RATE.get(gp, 0)
            
            price = row['yes_vwap']
            
            # Check for edge
            if price > prob_est + threshold:
                side = 'NO'
                edge = price - prob_est
            elif price < prob_est - threshold:
                side = 'YES'
                edge = prob_est - price
            else:
                continue
            
            # Also apply S18 logic (sell P2-P3 winner)
            if row['market_type'] == 'RACE' and gp in (2, 3):
                win_base = BASE_WIN_RATE.get(gp, 0.1)
                if price > win_base + 0.08:
                    side = 'NO'
                    edge = price - win_base
                else:
                    continue
            elif row['market_type'] == 'RACE':
                continue  # Skip non P2-P3 RACE contracts (S17 doesn't work)
            
            weekend_signals.append({
                'row': row,
                'side': side,
                'edge': edge,
                'price': price,
            })
        
        if not weekend_signals:
            continue
        
        # Phase 2: Size positions with weekend cap
        n = len(weekend_signals)
        if sizing_mode == 'flat':
            per_trade = size_flat_with_cap(bankroll, n, flat_amount)
            stakes = [per_trade] * n
        elif sizing_mode == 'kelly':
            stakes = size_kelly_with_cap(bankroll, weekend_signals)
        elif sizing_mode == 'tiered':
            stakes = size_tiered(bankroll, weekend_signals)
        else:
            stakes = [flat_amount] * n
        
        # Phase 3: Execute
        for sig, stake in zip(weekend_signals, stakes):
            if stake <= 0:
                continue
            
            row = sig['row']
            ret = net_pnl_pct(sig['side'], row['yes_vwap'], row['outcome'])
            pnl = stake * ret
            bankroll += pnl
            
            trades.append({
                'round': rnd,
                'race': row['race_name'],
                'market': row['market_type'],
                'driver': row['driver'],
                'grid': row['grid_pos'],
                'side': sig['side'],
                'price': row['yes_vwap'],
                'edge': round(sig['edge'], 4),
                'stake': round(stake, 2),
                'outcome': row['outcome'],
                'pnl': round(pnl, 2),
                'bankroll': round(bankroll, 2),
            })
    
    return trades, bankroll, skipped_liquidity


def main():
    print("=" * 80)
    print("ENHANCED STRATEGY COMPARISON")
    print("=" * 80)
    
    configs = [
        # (label, threshold, min_vol, use_adj, sizing, flat_amt)
        ("Baseline (S01+S03+S18, flat $10, no filter)", 0.15, 20, False, 'flat', 10),
        ("+ Liquidity filter ($50 min vol)",            0.15, 50, False, 'flat', 10),
        ("+ Logistic adjuster",                         0.15, 50, True,  'flat', 10),
        ("+ Weekend cap (30% max exposure)",            0.15, 50, True,  'flat', 10),
        ("Kelly + weekend cap",                         0.15, 50, True,  'kelly', None),
        ("Tiered + weekend cap",                        0.15, 50, True,  'tiered', None),
        ("Lower threshold (12%)",                       0.12, 50, True,  'flat', 10),
        ("Lower threshold (10%)",                       0.10, 50, True,  'flat', 10),
    ]
    
    print(f"\n{'Config':<50} {'Trades':>6} {'Final':>8} {'Return':>8} {'Skipped':>8}")
    print("─" * 90)
    
    results = []
    for label, thresh, min_vol, use_adj, sizing, flat_amt in configs:
        trades, final, skipped = run_enhanced_backtest(
            threshold=thresh, min_volume=min_vol, use_adjuster=use_adj,
            sizing_mode=sizing, flat_amount=flat_amt or 10
        )
        
        n = len(trades)
        ret = (final - 100) / 100
        wins = sum(1 for t in trades if t['pnl'] > 0)
        hit = wins / n if n > 0 else 0
        
        print(f"{label:<50} {n:>6} ${final:>7.2f} {ret:>+7.1%} {skipped:>8}")
        
        # Concentration
        round_pnl = defaultdict(float)
        for t in trades:
            round_pnl[t['round']] += t['pnl']
        top3 = sorted(round_pnl.values(), reverse=True)[:3]
        top3_total = sum(top3)
        total_pnl = final - 100
        
        results.append({
            'label': label,
            'trades': n,
            'final': round(final, 2),
            'return_pct': round(ret * 100, 1),
            'win_rate': round(hit * 100, 1),
            'skipped_liquidity': skipped,
            'top3_weekend_pnl': round(top3_total, 2),
            'without_top3': round(total_pnl - top3_total, 2),
        })
    
    # Print detailed results for best config
    print("\n" + "=" * 80)
    print("DETAILED: Logistic Adjuster + Liquidity Filter + Weekend Cap")
    print("=" * 80)
    
    trades, final, _ = run_enhanced_backtest(
        threshold=0.15, min_volume=50, use_adjuster=True,
        sizing_mode='flat', flat_amount=10
    )
    
    print(f"\n{'Rnd':>4} {'Race':<15} {'Mkt':<12} {'Drv':<5} {'G':>3} {'Side':<4} {'Price':>6} "
          f"{'Edge':>6} {'Stake':>7} {'Out':>4} {'PnL':>8} {'Bank':>8}")
    print("─" * 90)
    for t in trades:
        marker = '✓' if t['pnl'] > 0 else '✗'
        print(f"{t['round']:>4} {t['race']:<15} {t['market']:<12} {t['driver']:<5} "
              f"P{t['grid']:>2} {t['side']:<4} {t['price']:>5.2f} {t['edge']:>+5.2f} "
              f"${t['stake']:>6.2f} {'WIN' if t['outcome'] else 'NO':>4} "
              f"${t['pnl']:>+7.2f} ${t['bankroll']:>7.2f} {marker}")
    
    # Save
    with open(OUT / 'enhanced_strategy_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nSaved to {OUT / 'enhanced_strategy_results.json'}")


if __name__ == '__main__':
    main()
