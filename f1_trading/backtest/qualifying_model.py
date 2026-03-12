"""
Model exploration: logistic regression, calibration analysis, and LLM probability estimation.
Train on 2019-2024, evaluate on 2025 against Kalshi prices.
"""
import csv, json, math
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
            r['volume'] = float(r['volume'])
            r['n_trades'] = int(r['n_trades'])
            rows.append(r)
    return rows

def load_hist():
    with open(Path(__file__).parent / 'historical_data.json') as f:
        return json.load(f)

def logistic(x):
    x = np.clip(x, -500, 500)
    return 1 / (1 + np.exp(-x))

def fit_logistic(X, y, lr=0.01, epochs=10000, reg=0.01):
    n, d = X.shape
    w = np.zeros(d)
    b = 0.0
    for _ in range(epochs):
        z = X @ w + b
        p = logistic(z)
        grad_w = X.T @ (p - y) / n + reg * w
        grad_b = np.mean(p - y)
        w -= lr * grad_w
        b -= lr * grad_b
    return w, b

BASE_PODIUM_RATE = {
    1: 0.746, 2: 0.576, 3: 0.508, 4: 0.373, 5: 0.271, 6: 0.186,
    7: 0.153, 8: 0.136, 9: 0.085, 10: 0.085, 11: 0.051, 12: 0.034,
    13: 0.034, 14: 0.034, 15: 0.017, 16: 0.017, 17: 0.0, 18: 0.017, 19: 0.0, 20: 0.0
}
BASE_WIN_RATE = {
    1: 0.381, 2: 0.157, 3: 0.102, 4: 0.085, 5: 0.051, 6: 0.034,
    7: 0.034, 8: 0.034, 9: 0.017, 10: 0.017, 11: 0.017, 12: 0.017,
    13: 0.0, 14: 0.017, 15: 0.0, 16: 0.0, 17: 0.0, 18: 0.017, 19: 0.0, 20: 0.0
}

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

def kelly_frac(p_win, b, frac=0.25, cap=0.10):
    if b <= 0: return 0
    edge = p_win * b - (1 - p_win)
    if edge <= 0: return 0
    return min(edge / b * frac, cap)

def main():
    hist = load_hist()
    universe = load_universe()
    
    # Split historical
    train = [r for r in hist if r['year'] <= 2024]
    test_2025 = [r for r in hist if r['year'] == 2025]
    
    # Build feature matrices
    # Features: grid/20, gap_to_pole (normalized), (grid/20)^2
    train_with_gap = [r for r in train if r['gap_to_pole'] is not None and r['grid'] <= 20]
    
    X_train = np.array([[r['grid']/20, r['gap_to_pole'], (r['grid']/20)**2] for r in train_with_gap])
    y_pod_train = np.array([r['podium'] for r in train_with_gap])
    y_win_train = np.array([r['won'] for r in train_with_gap])
    
    gap_mean = X_train[:, 1].mean()
    gap_std = X_train[:, 1].std()
    X_train[:, 1] = (X_train[:, 1] - gap_mean) / gap_std
    
    print(f"Training: {len(train_with_gap)} records (2019-2024)")
    
    # Fit models
    w_pod, b_pod = fit_logistic(X_train, y_pod_train)
    w_win, b_win = fit_logistic(X_train, y_win_train)
    
    # ── Calibration check on 2025 data ──
    test25_with_gap = [r for r in test_2025 if r['gap_to_pole'] is not None and r['grid'] <= 20]
    X_test = np.array([[r['grid']/20, (r['gap_to_pole'] - gap_mean)/gap_std, (r['grid']/20)**2] for r in test25_with_gap])
    
    p_pod_25 = logistic(X_test @ w_pod + b_pod)
    p_win_25 = logistic(X_test @ w_win + b_win)
    y_pod_25 = np.array([r['podium'] for r in test25_with_gap])
    y_win_25 = np.array([r['won'] for r in test25_with_gap])
    
    print(f"\n{'='*70}")
    print("OUT-OF-SAMPLE CALIBRATION (2025)")
    print(f"{'='*70}")
    print(f"\n  {'Grid':>4} {'N':>4} {'ActPod':>7} {'Model':>7} {'Base':>7} | {'ActWin':>7} {'Model':>7} {'Base':>7}")
    for g in range(1, 11):
        mask = np.array([r['grid'] == g for r in test25_with_gap])
        if mask.sum() == 0: continue
        print(f"  {g:>4} {mask.sum():>4} {y_pod_25[mask].mean():>6.1%} {p_pod_25[mask].mean():>6.1%} "
              f"{BASE_PODIUM_RATE.get(g,0):>6.1%} | {y_win_25[mask].mean():>6.1%} {p_win_25[mask].mean():>6.1%} "
              f"{BASE_WIN_RATE.get(g,0):>6.1%}")
    
    # Brier scores
    base_pod_25 = np.array([BASE_PODIUM_RATE.get(r['grid'], 0) for r in test25_with_gap])
    base_win_25 = np.array([BASE_WIN_RATE.get(r['grid'], 0) for r in test25_with_gap])
    
    print(f"\nBrier Scores (lower = better):")
    print(f"  Podium: Model={np.mean((p_pod_25-y_pod_25)**2):.4f}, Base={np.mean((base_pod_25-y_pod_25)**2):.4f}")
    print(f"  Winner: Model={np.mean((p_win_25-y_win_25)**2):.4f}, Base={np.mean((base_win_25-y_win_25)**2):.4f}")
    
    # ── Now compare against Kalshi prices ──
    print(f"\n{'='*70}")
    print("MODEL vs KALSHI PRICES (2025 podium market)")
    print(f"{'='*70}")
    
    # Map 2025 gaps for each (round, driver)
    gap_map = {}
    for r in test25_with_gap:
        gap_map[(r['round'], r['driver'])] = r['gap_to_pole']
    
    podium_trades = [r for r in universe if r['market_type'] == 'RACEPODIUM' and r['volume'] >= 20 and r['grid_pos'] is not None]
    
    kalshi_brier_parts = []
    model_brier_parts = []
    base_brier_parts = []
    
    enriched = []
    for row in podium_trades:
        gp = row['grid_pos']
        if gp > 20: continue
        gap = gap_map.get((row['round'], row['driver']), None)
        if gap is None: gap = 0.0
        
        x = np.array([[gp/20, (gap - gap_mean)/gap_std, (gp/20)**2]])
        model_p = logistic(x @ w_pod + b_pod)[0]
        base_p = BASE_PODIUM_RATE.get(gp, 0)
        kalshi_p = row['yes_vwap']
        
        kalshi_brier_parts.append((kalshi_p - row['outcome'])**2)
        model_brier_parts.append((model_p - row['outcome'])**2)
        base_brier_parts.append((base_p - row['outcome'])**2)
        
        enriched.append({**row, 'model_prob': float(model_p), 'base_prob': base_p})
    
    print(f"\nBrier Score against actual outcomes ({len(enriched)} contracts):")
    print(f"  Kalshi price: {np.mean(kalshi_brier_parts):.4f}")
    print(f"  Base rates:   {np.mean(base_brier_parts):.4f}")
    print(f"  Log model:    {np.mean(model_brier_parts):.4f}")
    
    # ── Backtest: Model-based strategy ──
    print(f"\n{'='*70}")
    print("BACKTEST: MODEL-BASED vs BASE-RATE-BASED")
    print(f"{'='*70}")
    
    for label, prob_key in [("Logistic Model", 'model_prob'), ("Base Rates", 'base_prob')]:
        for thresh in [0.10, 0.15, 0.20, 0.25]:
            bankroll = 100.0
            n_trades = 0; wins = 0
            for rnd in sorted(set(r['round'] for r in enriched)):
                rnd_rows = [r for r in enriched if r['round'] == rnd]
                for r in rnd_rows:
                    my_prob = r[prob_key]
                    kalshi_p = r['yes_vwap']
                    edge = my_prob - kalshi_p
                    
                    if abs(edge) < thresh: continue
                    
                    if edge > 0:
                        side = 'YES'
                        p_est = min(max(my_prob, 0.01), 0.99)
                        cost = kalshi_p
                        b_ratio = (1 - cost) * 0.93 / cost
                    else:
                        side = 'NO'
                        p_est = min(max(1 - my_prob, 0.01), 0.99)
                        cost = 1 - kalshi_p
                        b_ratio = kalshi_p * 0.93 / cost
                    
                    k = kelly_frac(p_est, b_ratio, 0.25, 0.10)
                    size = bankroll * k
                    if size < 0.50: continue
                    
                    pnl = size * net_pnl_pct(side, kalshi_p, r['outcome'])
                    bankroll += pnl
                    n_trades += 1
                    if pnl > 0: wins += 1
            
            wr = wins / n_trades if n_trades else 0
            print(f"  {label:<16} thresh={thresh:.0%}: ${bankroll:>7.2f} ({(bankroll/100-1)*100:>+6.1f}%) "
                  f"{n_trades:>3} trades, {wr:.0%} win")
    
    # ── "Ensemble": average of model + base rate ──
    print(f"\n  --- ENSEMBLE (avg of model + base) ---")
    for thresh in [0.10, 0.15, 0.20]:
        bankroll = 100.0
        n_trades = 0; wins = 0
        for rnd in sorted(set(r['round'] for r in enriched)):
            rnd_rows = [r for r in enriched if r['round'] == rnd]
            for r in rnd_rows:
                my_prob = (r['model_prob'] + r['base_prob']) / 2
                kalshi_p = r['yes_vwap']
                edge = my_prob - kalshi_p
                
                if abs(edge) < thresh: continue
                if edge > 0:
                    side = 'YES'; p_est = min(max(my_prob,0.01),0.99); b_ratio = (1-kalshi_p)*0.93/kalshi_p
                else:
                    side = 'NO'; p_est = min(max(1-my_prob,0.01),0.99); b_ratio = kalshi_p*0.93/(1-kalshi_p)
                
                k = kelly_frac(p_est, b_ratio, 0.25, 0.10)
                size = bankroll * k
                if size < 0.50: continue
                pnl = size * net_pnl_pct(side, kalshi_p, r['outcome'])
                bankroll += pnl
                n_trades += 1
                if pnl > 0: wins += 1
        wr = wins / n_trades if n_trades else 0
        print(f"  Ensemble         thresh={thresh:.0%}: ${bankroll:>7.2f} ({(bankroll/100-1)*100:>+6.1f}%) "
              f"{n_trades:>3} trades, {wr:.0%} win")
    
    # ── Winner market too ──
    print(f"\n{'='*70}")
    print("WINNER MARKET: Model-based")
    print(f"{'='*70}")
    
    winner_trades = [r for r in universe if r['market_type'] == 'RACE' and r['volume'] >= 20 and r['grid_pos'] is not None]
    
    for label, use_model in [("Logistic", True), ("Base Rate", False)]:
        for thresh in [0.05, 0.10, 0.15]:
            bankroll = 100.0
            n_trades = 0; wins = 0
            for rnd in sorted(set(r['round'] for r in winner_trades)):
                rnd_rows = [r for r in winner_trades if r['round'] == rnd]
                for r in rnd_rows:
                    gp = r['grid_pos']
                    if gp > 20: continue
                    gap = gap_map.get((r['round'], r['driver']), 0) or 0
                    
                    if use_model:
                        x = np.array([[gp/20, (gap-gap_mean)/gap_std, (gp/20)**2]])
                        my_prob = float(logistic(x @ w_win + b_win)[0])
                    else:
                        my_prob = BASE_WIN_RATE.get(gp, 0)
                    
                    kalshi_p = r['yes_vwap']
                    edge = my_prob - kalshi_p
                    
                    if abs(edge) < thresh: continue
                    if edge > 0:
                        side = 'YES'; p_est = min(max(my_prob,0.01),0.99); b_ratio = (1-kalshi_p)*0.93/kalshi_p
                    else:
                        side = 'NO'; p_est = min(max(1-my_prob,0.01),0.99); b_ratio = kalshi_p*0.93/(1-kalshi_p)
                    
                    k = kelly_frac(p_est, b_ratio, 0.25, 0.10)
                    size = bankroll * k
                    if size < 0.50: continue
                    pnl = size * net_pnl_pct(side, kalshi_p, r['outcome'])
                    bankroll += pnl
                    n_trades += 1
                    if pnl > 0: wins += 1
            wr = wins / n_trades if n_trades else 0
            print(f"  {label:<12} thresh={thresh:.0%}: ${bankroll:>7.2f} ({(bankroll/100-1)*100:>+6.1f}%) "
                  f"{n_trades:>3} trades, {wr:.0%} win")

    # Save model
    model_params = {
        'w_pod': w_pod.tolist(), 'b_pod': float(b_pod),
        'w_win': w_win.tolist(), 'b_win': float(b_win),
        'gap_mean': float(gap_mean), 'gap_std': float(gap_std),
    }
    with open(Path(__file__).parent / 'model_params.json', 'w') as f:
        json.dump(model_params, f, indent=2)

main()
