"""
Rigorous robustness testing for top strategies.
Tests: leave-one-out, bootstrap, concentration, drawdown paths, walk-forward.
"""
import csv, json, math, random
import numpy as np
from pathlib import Path
from collections import defaultdict

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

BASE_PODIUM_RATE = {
    1: 0.746, 2: 0.576, 3: 0.508, 4: 0.373, 5: 0.271, 6: 0.186,
    7: 0.153, 8: 0.136, 9: 0.085, 10: 0.085, 11: 0.051, 12: 0.034,
    13: 0.034, 14: 0.034, 15: 0.017, 16: 0.017, 17: 0.0, 18: 0.017,
    19: 0.0, 20: 0.0
}

def net_pnl_pct(side, price, outcome, fee=0.07):
    if side == 'YES':
        if outcome == 1:
            profit = 1.0 - price
            return (profit - profit * fee) / price
        return -1.0
    else:  # NO
        cost = 1.0 - price
        if outcome == 0:
            profit = price
            return (profit - profit * fee) / cost
        return -1.0

def kelly_frac(p_win, b, frac=0.25, cap=0.10):
    if b <= 0: return 0
    edge = p_win * b - (1 - p_win)
    if edge <= 0: return 0
    return min(edge / b * frac, cap)

def generate_signals(row, threshold=0.15):
    """The top strategy: BaseRate_RACEPODIUM_BOTH_t15"""
    if row['market_type'] != 'RACEPODIUM':
        return None
    if row['volume'] < 20:
        return None
    gp = row['grid_pos']
    if gp is None or gp > 20:
        return None
    base = BASE_PODIUM_RATE.get(gp, 0)
    p = row['yes_vwap']
    
    if p > base + threshold:
        return ('NO', p - base)
    if p < base - threshold:
        return ('YES', base - p)
    return None

def simulate(trades_by_round, rounds_to_use, bankroll=100.0):
    """Run strategy on specific rounds."""
    b = bankroll
    pnls = []
    for rnd in sorted(rounds_to_use):
        for row in trades_by_round.get(rnd, []):
            sig = generate_signals(row)
            if sig is None:
                continue
            side, edge = sig
            p = row['yes_vwap']
            
            # Kelly sizing
            if side == 'YES':
                cost = p
                payout_ratio = (1.0 - p) * 0.93 / cost
                p_est = min(max(p + edge, 0.01), 0.99)
            else:
                cost = 1.0 - p
                payout_ratio = p * 0.93 / cost
                p_est = min(max(1 - p + edge, 0.01), 0.99)
            
            k = kelly_frac(p_est, payout_ratio, 0.25, 0.10)
            size = b * k
            if size < 0.50:
                continue
            
            ret = net_pnl_pct(side, p, row['outcome'])
            pnl = size * ret
            b += pnl
            pnls.append(pnl)
    
    return b, pnls

def main():
    universe = load_universe()
    
    by_round = defaultdict(list)
    for r in universe:
        by_round[r['round']].append(r)
    
    all_rounds = sorted(by_round.keys())
    print(f"Rounds: {all_rounds}\n")
    
    # ── Full run ──
    full_final, full_pnls = simulate(by_round, all_rounds)
    print(f"FULL BACKTEST: $100 → ${full_final:.2f} ({(full_final/100-1)*100:+.1f}%)")
    print(f"  Trades: {len(full_pnls)}, Win rate: {sum(1 for p in full_pnls if p>0)/len(full_pnls):.1%}")
    
    # ── Leave-one-out ──
    print(f"\n{'='*60}")
    print("LEAVE-ONE-OUT (remove each race)")
    print(f"{'='*60}")
    loo_results = []
    for skip_rnd in all_rounds:
        rounds = [r for r in all_rounds if r != skip_rnd]
        final, _ = simulate(by_round, rounds)
        ret = (final / 100 - 1) * 100
        loo_results.append((skip_rnd, final, ret))
        race_name = by_round[skip_rnd][0]['race_name'] if by_round[skip_rnd] else '?'
        marker = " *** LOSS" if final < 100 else ""
        print(f"  Skip R{skip_rnd:>2} ({race_name:<15}): ${final:>7.2f} ({ret:>+6.1f}%){marker}")
    
    profitable_loo = sum(1 for _, f, _ in loo_results if f > 100)
    print(f"\n  Profitable without any single race: {profitable_loo}/{len(loo_results)}")
    print(f"  Min: ${min(f for _, f, _ in loo_results):.2f}, Max: ${max(f for _, f, _ in loo_results):.2f}")
    
    # ── Leave-three-out (remove top 3 contributing races) ──
    print(f"\n{'='*60}")
    print("LEAVE-THREE-OUT (remove 3 best races)")
    print(f"{'='*60}")
    # Find 3 races that contribute most
    contributions = []
    for rnd in all_rounds:
        without = [r for r in all_rounds if r != rnd]
        f_without, _ = simulate(by_round, without)
        contribution = full_final - f_without
        race_name = by_round[rnd][0]['race_name'] if by_round[rnd] else '?'
        contributions.append((rnd, race_name, contribution))
    
    contributions.sort(key=lambda x: x[2], reverse=True)
    print("Top contributing races:")
    for rnd, name, contrib in contributions[:5]:
        print(f"  R{rnd:>2} {name:<15}: ${contrib:>+7.2f}")
    
    top3_rounds = {c[0] for c in contributions[:3]}
    rounds_no_top3 = [r for r in all_rounds if r not in top3_rounds]
    f_no_top3, _ = simulate(by_round, rounds_no_top3)
    print(f"\nWithout top 3 races: ${f_no_top3:.2f} ({(f_no_top3/100-1)*100:+.1f}%)")
    
    # ── Bootstrap ──
    print(f"\n{'='*60}")
    print("BOOTSTRAP (10,000 resampled seasons)")
    print(f"{'='*60}")
    random.seed(42)
    np.random.seed(42)
    
    boot_finals = []
    for _ in range(10000):
        sampled_rounds = [random.choice(all_rounds) for _ in range(len(all_rounds))]
        final, _ = simulate(by_round, sampled_rounds)
        boot_finals.append(final)
    
    boot_finals = np.array(boot_finals)
    p_profit = np.mean(boot_finals > 100)
    print(f"  P(profit): {p_profit:.1%}")
    print(f"  Median: ${np.median(boot_finals):.2f}")
    print(f"  Mean: ${np.mean(boot_finals):.2f}")
    print(f"  5th percentile: ${np.percentile(boot_finals, 5):.2f}")
    print(f"  25th percentile: ${np.percentile(boot_finals, 25):.2f}")
    print(f"  75th percentile: ${np.percentile(boot_finals, 75):.2f}")
    print(f"  95th percentile: ${np.percentile(boot_finals, 95):.2f}")
    print(f"  P(>50% return): {np.mean(boot_finals > 150):.1%}")
    print(f"  P(lose >25%): {np.mean(boot_finals < 75):.1%}")
    
    # ── Walk-Forward ──
    print(f"\n{'='*60}")
    print("WALK-FORWARD (train on first N races, test on next)")
    print(f"{'='*60}")
    # Can we learn the threshold from early races?
    for train_size in [6, 8, 12]:
        train_rounds = all_rounds[:train_size]
        test_rounds = all_rounds[train_size:]
        
        # Train: find if strategy is profitable on training set
        f_train, pnls_train = simulate(by_round, train_rounds)
        f_test, pnls_test = simulate(by_round, test_rounds)
        
        print(f"\n  Train on R1-R{train_rounds[-1]} ({train_size} races):")
        print(f"    Train: ${f_train:.2f} ({(f_train/100-1)*100:+.1f}%), {len(pnls_train)} trades")
        print(f"    Test:  ${f_test:.2f} ({(f_test/100-1)*100:+.1f}%), {len(pnls_test)} trades")
    
    # ── Concentration analysis ──
    print(f"\n{'='*60}")
    print("CONCENTRATION ANALYSIS")
    print(f"{'='*60}")
    
    # Run full and track by driver
    driver_pnl = defaultdict(float)
    driver_trades = defaultdict(int)
    b = 100.0
    for rnd in sorted(all_rounds):
        for row in by_round.get(rnd, []):
            sig = generate_signals(row)
            if sig is None: continue
            side, edge = sig
            p = row['yes_vwap']
            if side == 'YES':
                cost = p; pr = (1-p)*0.93/cost; p_est = min(max(p+edge,0.01),0.99)
            else:
                cost = 1-p; pr = p*0.93/cost; p_est = min(max(1-p+edge,0.01),0.99)
            k = kelly_frac(p_est, pr, 0.25, 0.10)
            size = b * k
            if size < 0.50: continue
            ret = net_pnl_pct(side, p, row['outcome'])
            pnl = size * ret
            b += pnl
            driver_pnl[row['driver']] += pnl
            driver_trades[row['driver']] += 1
    
    total_abs_pnl = sum(abs(v) for v in driver_pnl.values())
    sorted_drivers = sorted(driver_pnl.items(), key=lambda x: x[1], reverse=True)
    print(f"\n  {'Driver':<6} {'PnL':>8} {'Trades':>7} {'% of total':>10}")
    for drv, pnl in sorted_drivers:
        pct = pnl / (full_final - 100) * 100 if full_final != 100 else 0
        print(f"  {drv:<6} ${pnl:>+7.2f} {driver_trades[drv]:>7} {pct:>+9.1f}%")
    
    # ── Fee sensitivity ──
    print(f"\n{'='*60}")
    print("FEE SENSITIVITY")
    print(f"{'='*60}")
    for fee in [0.0, 0.05, 0.07, 0.10, 0.15]:
        b = 100.0
        for rnd in sorted(all_rounds):
            for row in by_round.get(rnd, []):
                sig = generate_signals(row)
                if sig is None: continue
                side, edge = sig
                p = row['yes_vwap']
                if side == 'YES':
                    cost = p; pr = (1-p)*(1-fee)/cost; p_est = min(max(p+edge,0.01),0.99)
                else:
                    cost = 1-p; pr = p*(1-fee)/cost; p_est = min(max(1-p+edge,0.01),0.99)
                k = kelly_frac(p_est, pr, 0.25, 0.10)
                size = b * k
                if size < 0.50: continue
                pnl = size * net_pnl_pct(side, p, row['outcome'], fee)
                b += pnl
        print(f"  Fee {fee:.0%}: ${b:.2f} ({(b/100-1)*100:+.1f}%)")

    # ── Threshold sensitivity ──
    print(f"\n{'='*60}")
    print("THRESHOLD SENSITIVITY")
    print(f"{'='*60}")
    for thresh in [0.05, 0.08, 0.10, 0.12, 0.15, 0.18, 0.20, 0.25]:
        b = 100.0
        n = 0
        for rnd in sorted(all_rounds):
            for row in by_round.get(rnd, []):
                if row['market_type'] != 'RACEPODIUM' or row['volume'] < 20:
                    continue
                gp = row['grid_pos']
                if gp is None or gp > 20: continue
                base = BASE_PODIUM_RATE.get(gp, 0)
                p = row['yes_vwap']
                if p > base + thresh:
                    side, edge = 'NO', p - base
                elif p < base - thresh:
                    side, edge = 'YES', base - p
                else:
                    continue
                
                if side == 'YES':
                    cost = p; pr = (1-p)*0.93/cost; p_est = min(max(p+edge,0.01),0.99)
                else:
                    cost = 1-p; pr = p*0.93/cost; p_est = min(max(1-p+edge,0.01),0.99)
                k = kelly_frac(p_est, pr, 0.25, 0.10)
                size = b * k
                if size < 0.50: continue
                pnl = size * net_pnl_pct(side, p, row['outcome'])
                b += pnl
                n += 1
        print(f"  Threshold {thresh:.0%}: ${b:.2f} ({(b/100-1)*100:+.1f}%), {n} trades")

main()
