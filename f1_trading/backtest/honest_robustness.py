"""
Honest Robustness Analysis — Block Bootstrap & Concentration Tests

Key insight: trades within the same weekend are correlated (same weather,
same safety cars, same chaos). The proper resampling unit is the WEEKEND,
not the individual trade. This gives honest confidence intervals.
"""
import csv, json
from collections import defaultdict
import numpy as np
from pathlib import Path

OUT = Path(__file__).parent

def load_flat_trades():
    trades = []
    with open(OUT / 'VERIFIED_flat_trades.csv') as f:
        for r in csv.DictReader(f):
            r['round'] = int(r['round'])
            r['pnl'] = float(r['pnl'])
            trades.append(r)
    return trades

def load_compounded_trades():
    trades = []
    with open(OUT / 'VERIFIED_combined_trades.csv') as f:
        for r in csv.DictReader(f):
            r['round'] = int(r['round'])
            r['pnl'] = float(r['pnl'])
            r['stake'] = float(r['stake'])
            trades.append(r)
    return trades


def block_bootstrap_flat(trades, n_boot=50000, seed=42):
    """Block bootstrap: resample weekends, sum P&L."""
    np.random.seed(seed)
    round_pnl = defaultdict(float)
    for t in trades:
        round_pnl[t['round']] += t['pnl']
    
    # Include all 24 weekends (some may have 0 trades = $0 P&L)
    all_pnls = np.array([round_pnl.get(r, 0.0) for r in range(1, 25)])
    n = len(all_pnls)
    
    boot_totals = np.zeros(n_boot)
    for i in range(n_boot):
        idx = np.random.randint(0, n, size=n)
        boot_totals[i] = all_pnls[idx].sum()
    
    return boot_totals, all_pnls


def block_bootstrap_compounded(trades, n_boot=50000, seed=42):
    """Block bootstrap with compounding: resample weekends, replay Kelly."""
    np.random.seed(seed)
    
    round_trade_data = defaultdict(list)
    for t in trades:
        ret = t['pnl'] / t['stake'] if t['stake'] > 0 else 0
        round_trade_data[t['round']].append({
            'stake_frac': t['stake'],  # original stake (based on $100 start)
            'return': ret,
        })
    
    round_keys = sorted(round_trade_data.keys())
    # Include empty weekends
    all_keys = list(range(1, 25))
    
    boot_finals = np.zeros(n_boot)
    for i in range(n_boot):
        bankroll = 100.0
        sampled = np.random.choice(all_keys, size=24, replace=True)
        for rnd in sampled:
            if rnd not in round_trade_data:
                continue
            for td in round_trade_data[rnd]:
                scale = bankroll / 100.0
                stake = td['stake_frac'] * scale
                stake = min(stake, bankroll * 0.15)
                if stake < 0.50:
                    continue
                pnl = stake * td['return']
                bankroll += pnl
                if bankroll <= 0:
                    bankroll = 0
                    break
            if bankroll <= 0:
                break
        boot_finals[i] = bankroll
    
    return boot_finals


def concentration_analysis(trades):
    """Analyze profit concentration by weekend, driver, and strategy."""
    total_pnl = sum(t['pnl'] for t in trades)
    
    # By weekend
    round_pnl = defaultdict(float)
    round_trades = defaultdict(int)
    for t in trades:
        round_pnl[t['round']] += t['pnl']
        round_trades[t['round']] += 1
    
    sorted_rounds = sorted(round_pnl.items(), key=lambda x: x[1], reverse=True)
    top3_pnl = sum(v for _, v in sorted_rounds[:3])
    
    # By driver
    driver_pnl = defaultdict(float)
    for t in trades:
        driver_pnl[t['driver']] += t['pnl']
    sorted_drivers = sorted(driver_pnl.items(), key=lambda x: x[1], reverse=True)
    top3_driver_pnl = sum(v for _, v in sorted_drivers[:3])
    
    # Winning weekends vs losing weekends
    win_weekends = sum(1 for v in round_pnl.values() if v > 0)
    loss_weekends = sum(1 for v in round_pnl.values() if v < 0)
    
    return {
        'total_pnl': total_pnl,
        'n_weekends_with_trades': len(round_pnl),
        'winning_weekends': win_weekends,
        'losing_weekends': loss_weekends,
        'top3_weekend_pnl': top3_pnl,
        'top3_weekend_pct': top3_pnl / total_pnl * 100 if total_pnl > 0 else 0,
        'without_top3_weekends': total_pnl - top3_pnl,
        'top3_rounds': sorted_rounds[:3],
        'top3_drivers': sorted_drivers[:3],
        'top3_driver_pnl': top3_driver_pnl,
        'top3_driver_pct': top3_driver_pnl / total_pnl * 100 if total_pnl > 0 else 0,
    }


def weekend_exposure_analysis(trades):
    """Analyze per-weekend exposure for correlated risk."""
    round_exposure = defaultdict(lambda: {'n_trades': 0, 'total_stake': 0, 
                                           'total_risk': 0, 'strategies': set()})
    for t in trades:
        re = round_exposure[t['round']]
        re['n_trades'] += 1
        stake = float(t.get('stake', 10))
        re['total_stake'] += stake
        re['total_risk'] += stake  # max loss = full stake
        re['strategies'].add(t['strategy'])
    
    return {rnd: {**v, 'strategies': list(v['strategies'])} 
            for rnd, v in sorted(round_exposure.items())}


def main():
    flat_trades = load_flat_trades()
    comp_trades = load_compounded_trades()
    
    print("=" * 70)
    print("HONEST ROBUSTNESS ANALYSIS — BLOCK BOOTSTRAP BY WEEKEND")
    print("=" * 70)
    
    # --- FLAT $10/TRADE ---
    print("\n" + "─" * 70)
    print("FLAT $10/TRADE")
    print("─" * 70)
    
    boot_flat, round_pnls = block_bootstrap_flat(flat_trades)
    conc = concentration_analysis(flat_trades)
    
    print(f"\nBlock Bootstrap (resample 24 weekends, 50K iterations):")
    print(f"  P(profit):        {np.mean(boot_flat > 0):.1%}")
    print(f"  Median P&L:       ${np.median(boot_flat):.2f}")
    print(f"  Mean P&L:         ${np.mean(boot_flat):.2f}")
    print(f"  5th percentile:   ${np.percentile(boot_flat, 5):.2f}")
    print(f"  25th percentile:  ${np.percentile(boot_flat, 25):.2f}")
    print(f"  75th percentile:  ${np.percentile(boot_flat, 75):.2f}")
    print(f"  95th percentile:  ${np.percentile(boot_flat, 95):.2f}")
    
    print(f"\nConcentration:")
    print(f"  Winning weekends: {conc['winning_weekends']}/{conc['n_weekends_with_trades']}")
    print(f"  Top 3 weekends: ${conc['top3_weekend_pnl']:.2f} ({conc['top3_weekend_pct']:.0f}% of total)")
    print(f"  Without top 3:  ${conc['without_top3_weekends']:.2f}")
    for rnd, pnl in conc['top3_rounds']:
        print(f"    R{rnd}: ${pnl:+.2f}")
    
    print(f"\n  Top 3 drivers: ${conc['top3_driver_pnl']:.2f} ({conc['top3_driver_pct']:.0f}% of total)")
    for drv, pnl in conc['top3_drivers']:
        print(f"    {drv}: ${pnl:+.2f}")
    
    # --- COMPOUNDED KELLY ---
    print("\n" + "─" * 70)
    print("COMPOUNDED QUARTER-KELLY")
    print("─" * 70)
    
    boot_comp = block_bootstrap_compounded(comp_trades)
    
    print(f"\nBlock Bootstrap (resample 24 weekends, 50K iterations):")
    print(f"  P(profit):        {np.mean(boot_comp > 100):.1%}")
    print(f"  Median final:     ${np.median(boot_comp):.2f}")
    print(f"  Mean final:       ${np.mean(boot_comp):.2f}")
    print(f"  5th percentile:   ${np.percentile(boot_comp, 5):.2f}")
    print(f"  25th percentile:  ${np.percentile(boot_comp, 25):.2f}")
    print(f"  75th percentile:  ${np.percentile(boot_comp, 75):.2f}")
    print(f"  95th percentile:  ${np.percentile(boot_comp, 95):.2f}")
    print(f"  P(>2x):           {np.mean(boot_comp > 200):.1%}")
    print(f"  P(ruin <$10):     {np.mean(boot_comp < 10):.1%}")
    
    # --- COMPARISON ---
    print("\n" + "─" * 70)
    print("BOOTSTRAP METHOD COMPARISON")
    print("─" * 70)
    
    # Individual trade bootstrap (naive)
    np.random.seed(42)
    trade_pnls = np.array([t['pnl'] for t in flat_trades])
    n = len(trade_pnls)
    naive_boots = np.array([np.random.choice(trade_pnls, size=n, replace=True).sum() for _ in range(50000)])
    
    print(f"  Individual trade bootstrap P(profit): {np.mean(naive_boots > 0):.1%}  ← OVERCONFIDENT")
    print(f"  Block bootstrap (by weekend) P(profit): {np.mean(boot_flat > 0):.1%}  ← HONEST")
    print(f"  Difference: {np.mean(naive_boots > 0) - np.mean(boot_flat > 0):.1%} overstatement")
    
    # --- EXPOSURE ANALYSIS ---
    print("\n" + "─" * 70)
    print("PER-WEEKEND EXPOSURE (flat $10)")
    print("─" * 70)
    exp = weekend_exposure_analysis(flat_trades)
    high_exp = []
    for rnd, e in exp.items():
        if e['n_trades'] >= 4:
            high_exp.append((rnd, e))
            print(f"  R{rnd:>2}: {e['n_trades']} trades, ${e['total_stake']:.0f} at risk, strategies: {e['strategies']}")
    
    if high_exp:
        print(f"\n  ⚠ {len(high_exp)} weekends with 4+ trades = high correlated risk")
        print(f"  Recommendation: cap per-weekend exposure at 30% of bankroll")
    
    # --- SAVE RESULTS ---
    results = {
        'flat': {
            'block_bootstrap_p_profit': float(np.mean(boot_flat > 0)),
            'block_bootstrap_median': float(np.median(boot_flat)),
            'block_bootstrap_5pct': float(np.percentile(boot_flat, 5)),
            'block_bootstrap_95pct': float(np.percentile(boot_flat, 95)),
            'naive_bootstrap_p_profit': float(np.mean(naive_boots > 0)),
            'overstatement': float(np.mean(naive_boots > 0) - np.mean(boot_flat > 0)),
            'concentration': {
                'top3_weekend_pnl': conc['top3_weekend_pnl'],
                'top3_weekend_pct': conc['top3_weekend_pct'],
                'without_top3': conc['without_top3_weekends'],
            }
        },
        'compounded': {
            'block_bootstrap_p_profit': float(np.mean(boot_comp > 100)),
            'block_bootstrap_median': float(np.median(boot_comp)),
            'block_bootstrap_5pct': float(np.percentile(boot_comp, 5)),
            'block_bootstrap_95pct': float(np.percentile(boot_comp, 95)),
        }
    }
    
    with open(OUT / 'honest_robustness_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n\nSaved to {OUT / 'honest_robustness_results.json'}")


if __name__ == '__main__':
    main()
