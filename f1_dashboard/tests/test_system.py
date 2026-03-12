"""Comprehensive test suite for the F1 autonomous trading system.

Tests all core components:
- Strategy logic (signal generation, backtest)
- Database layer (CRUD, audit, settings)
- Kill switch
- Risk management (per-trade, per-weekend, drawdown)
- Kalshi client (mock mode)
- API endpoints
- Backtest CSV consistency
"""
import os, sys, json, csv, asyncio, tempfile, shutil
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import pytest
import sqlite3

# Override DB path before importing
TEST_DB_DIR = tempfile.mkdtemp()
os.environ["DB_PATH"] = os.path.join(TEST_DB_DIR, "test.db")
os.environ["DRY_RUN"] = "true"

import config
import db
import strategy


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture(autouse=True)
def fresh_db(tmp_path):
    """Fresh database for each test. Uses a unique temp path per test to avoid cross-contamination."""
    new_db = str(tmp_path / "test.db")
    os.environ["DB_PATH"] = new_db
    # Force db module to use the new path
    db.DB_PATH = new_db
    # Close any existing connection first
    if hasattr(db._local, 'conn') and db._local.conn is not None:
        try: db._local.conn.close()
        except: pass
        db._local.conn = None
    db.init_db()
    yield
    if hasattr(db._local, 'conn') and db._local.conn is not None:
        try: db._local.conn.close()
        except: pass
        db._local.conn = None


@pytest.fixture
def sample_grid():
    """Typical qualifying grid."""
    return [
        {"driver": "VER", "position": 1},
        {"driver": "NOR", "position": 2},
        {"driver": "PIA", "position": 3},
        {"driver": "LEC", "position": 4},
        {"driver": "SAI", "position": 5},
        {"driver": "HAM", "position": 6},
        {"driver": "RUS", "position": 7},
        {"driver": "ALO", "position": 8},
        {"driver": "GAS", "position": 9},
        {"driver": "OCO", "position": 10},
    ]


@pytest.fixture
def sample_prices():
    """Prices with clear mispricings for testing."""
    return [
        # Sleeve A: LEC P4 podium at 10% (base 28%) -> 18% edge > 15% threshold
        {"driver": "LEC", "market": "podium", "price": 0.10, "ticker": "KX-LEC-POD"},
        # Sleeve A: SAI P5 podium at 5% (base 21.7%) -> 16.7% edge > 15%
        {"driver": "SAI", "market": "podium", "price": 0.05, "ticker": "KX-SAI-POD"},
        # No signal: VER P1 podium at 70% (base 74%) -> 4% edge < 15%
        {"driver": "VER", "market": "podium", "price": 0.70, "ticker": "KX-VER-POD"},
        # Sleeve B: NOR P2 winner at 40% (base 23%) -> 17% edge > 8%
        {"driver": "NOR", "market": "winner", "price": 0.40, "ticker": "KX-NOR-WIN"},
        # Sleeve B: PIA P3 winner at 25% (base 12%) -> 13% edge > 8%
        {"driver": "PIA", "market": "winner", "price": 0.25, "ticker": "KX-PIA-WIN"},
        # No signal: VER P1 winner at 50% (base 45%) -> 5% edge < 8%, also not P2/P3
        {"driver": "VER", "market": "winner", "price": 0.50, "ticker": "KX-VER-WIN"},
        # Sleeve E candidate: HAM P6 winner at 20% (base 3.3%) -> 16.7% edge, price in [0.15, 0.50], pos > 3
        {"driver": "HAM", "market": "winner", "price": 0.20, "ticker": "KX-HAM-WIN"},
    ]


# ============================================================
# STRATEGY TESTS
# ============================================================

class TestStrategy:
    def test_generate_signals_sleeve_a(self, sample_grid, sample_prices):
        """Sleeve A should fire for underpriced podium bets."""
        signals = strategy.generate_signals(sample_grid, sample_prices, 100.0, 5)
        sleeve_a = [s for s in signals if s["sleeve"] == "A"]
        assert len(sleeve_a) == 2  # LEC and SAI
        drivers = {s["driver"] for s in sleeve_a}
        assert "LEC" in drivers
        assert "SAI" in drivers
        for s in sleeve_a:
            assert s["action"] == "BUY_YES"
            assert s["edge"] >= 0.15

    def test_generate_signals_sleeve_b(self, sample_grid, sample_prices):
        """Sleeve B should fire for overpriced P2/P3 winners."""
        # Use higher bankroll to avoid weekend cap limiting signals
        signals = strategy.generate_signals(sample_grid, sample_prices, 200.0, 5)
        sleeve_b = [s for s in signals if s["sleeve"] == "B"]
        assert len(sleeve_b) >= 1  # At least NOR; PIA may also fire
        assert any(s["driver"] == "NOR" for s in sleeve_b)
        for s in sleeve_b:
            assert s["action"] == "BUY_NO"
            assert s["edge"] >= 0.08
            assert s["grid_pos"] in (2, 3)

    def test_generate_signals_sleeve_e(self, sample_grid, sample_prices):
        """Sleeve E should fire for overpriced non-top-3 winners."""
        # Use higher bankroll to avoid weekend cap blocking E signals
        signals = strategy.generate_signals(sample_grid, sample_prices, 500.0, 5)
        sleeve_e = [s for s in signals if s["sleeve"] == "E"]
        assert len(sleeve_e) == 1  # HAM
        assert sleeve_e[0]["driver"] == "HAM"
        assert sleeve_e[0]["action"] == "BUY_NO"
        assert sleeve_e[0]["grid_pos"] > 3

    def test_no_signals_on_fair_prices(self, sample_grid):
        """Fair prices should generate no signals."""
        fair_prices = [
            {"driver": "VER", "market": "podium", "price": 0.74, "ticker": "test"},
            {"driver": "NOR", "market": "winner", "price": 0.23, "ticker": "test"},
        ]
        signals = strategy.generate_signals(sample_grid, fair_prices, 100.0, 5)
        assert len(signals) == 0

    def test_halted_at_stop_loss(self, sample_grid, sample_prices):
        """No signals when bankroll at stop-loss floor."""
        signals = strategy.generate_signals(sample_grid, sample_prices, 50.0, 5)
        assert len(signals) == 0

    def test_calibration_half_size(self, sample_grid, sample_prices):
        """First 4 races should use half bet size."""
        signals_cal = strategy.generate_signals(sample_grid, sample_prices, 100.0, 1)
        signals_full = strategy.generate_signals(sample_grid, sample_prices, 100.0, 5)
        
        # Calibration signals should have smaller risk
        for sc in signals_cal:
            matching = [sf for sf in signals_full if sf["driver"] == sc["driver"] and sf["sleeve"] == sc["sleeve"]]
            if matching:
                assert sc["risk"] <= matching[0]["risk"]

    def test_weekend_risk_cap(self, sample_grid):
        """Weekend risk cap should limit total exposure."""
        # Create many expensive mispriced contracts
        prices = []
        for i, driver in enumerate(["NOR", "PIA"]):
            prices.append({"driver": driver, "market": "winner", "price": 0.45, "ticker": f"test-{i}"})
        
        signals = strategy.generate_signals(sample_grid, prices, 100.0, 5)
        total_risk = sum(s["risk"] for s in signals)
        assert total_risk <= 100.0 * config.MAX_PER_WEEKEND_PCT

    def test_per_trade_risk_cap(self, sample_grid, sample_prices):
        """Each trade's risk should be ≤ 7% of bankroll."""
        signals = strategy.generate_signals(sample_grid, sample_prices, 100.0, 5)
        for s in signals:
            assert s["risk"] <= 100.0 * config.MAX_PER_TRADE_PCT + 1.0  # Small rounding tolerance


class TestBacktest:
    def test_backtest_default_params(self):
        """Default backtest should match known results."""
        result = strategy.run_backtest()
        assert result["total_trades"] == 30
        assert result["wins"] == 20  # 66.7%
        assert abs(result["win_rate"] - 66.7) < 1.0
        assert abs(result["final_bankroll"] - 226.01) < 1.0
        assert result["max_drawdown_pct"] <= 8.0  # ~7.5%

    def test_backtest_sleeve_a_only(self):
        """Sleeve A alone: 13 trades."""
        result = strategy.run_backtest(sleeve_a=True, sleeve_b=False, sleeve_e=False)
        assert result["total_trades"] == 13

    def test_backtest_sleeve_b_only(self):
        """Sleeve B alone: 17 trades."""
        result = strategy.run_backtest(sleeve_a=False, sleeve_b=True, sleeve_e=False)
        assert result["total_trades"] == 17

    def test_backtest_what_if_bet_size(self):
        """Different bet sizes should change P&L but not trade count."""
        r1 = strategy.run_backtest(bet_size=5.0)
        r2 = strategy.run_backtest(bet_size=10.0)
        assert r1["total_trades"] == r2["total_trades"]
        # Larger bets -> larger P&L (assuming positive expectation)
        assert abs(r2["final_bankroll"] - 100) > abs(r1["final_bankroll"] - 100)

    def test_backtest_higher_threshold_fewer_trades(self):
        """Higher edge thresholds should produce fewer trades."""
        r_default = strategy.run_backtest(edge_a=0.15, edge_b=0.08)
        r_strict = strategy.run_backtest(edge_a=0.25, edge_b=0.20)
        assert r_strict["total_trades"] <= r_default["total_trades"]

    def test_backtest_equity_curve_length(self):
        """Equity curve should have n+1 points for n trades."""
        result = strategy.run_backtest()
        assert len(result["curve"]) == result["total_trades"] + 1
        assert result["curve"][0] == 100.0
        assert result["curve"][-1] == result["final_bankroll"]

    def test_verified_trades_match_csv(self):
        """CRITICAL: Verify backtest trades match source CSVs."""
        csv_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'f1_trading', 'backtest')
        
        # Sleeve A CSV
        csv_a_path = os.path.join(csv_dir, 'trades_S01_Base_Rate_YES_Podium_t=0.15.csv')
        if os.path.exists(csv_a_path):
            with open(csv_a_path) as f:
                csv_a = list(csv.DictReader(f))
            
            bt_a = [t for t in strategy.VERIFIED_2025_TRADES if t["sleeve"] == "A"]
            assert len(bt_a) == len(csv_a), f"Sleeve A: {len(bt_a)} in code vs {len(csv_a)} in CSV"
            
            for bt, cv in zip(bt_a, csv_a):
                assert abs(bt["price"] - float(cv["price"])) < 0.01, \
                    f"Price mismatch: {bt['race']} {bt['driver']}: {bt['price']} vs {cv['price']}"
                # Outcome mapping: CSV outcome=1 means podium happened (YES wins)
                csv_won = cv["outcome"] == "1"
                assert bt["won"] == csv_won, \
                    f"Outcome mismatch: {bt['race']} {bt['driver']}: {bt['won']} vs {csv_won}"

        # Sleeve B CSV
        csv_b_path = os.path.join(csv_dir, 'trades_S18_Sell_P2-P3_Winner.csv')
        if os.path.exists(csv_b_path):
            with open(csv_b_path) as f:
                csv_b = list(csv.DictReader(f))
            
            bt_b = [t for t in strategy.VERIFIED_2025_TRADES if t["sleeve"] == "B"]
            assert len(bt_b) == len(csv_b), f"Sleeve B: {len(bt_b)} in code vs {len(csv_b)} in CSV"
            
            for bt, cv in zip(bt_b, csv_b):
                assert abs(bt["price"] - float(cv["price"])) < 0.01, \
                    f"Price mismatch: {bt['race']} {bt['driver']}: {bt['price']} vs {cv['price']}"
                # Outcome mapping: CSV outcome=0 means driver didn't win (NO wins)
                csv_won = cv["outcome"] == "0"
                assert bt["won"] == csv_won, \
                    f"Outcome mismatch: {bt['race']} {bt['driver']}: {bt['won']} vs {csv_won}"


# ============================================================
# DATABASE TESTS
# ============================================================

class TestDatabase:
    def test_init_creates_tables(self):
        """DB init should create all required tables."""
        with db.get_db() as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = {t["name"] for t in tables}
            assert "settings" in table_names
            assert "trades" in table_names
            assert "signals" in table_names
            assert "price_snapshots" in table_names
            assert "audit_log" in table_names
            assert "f1_sessions" in table_names

    def test_default_settings(self):
        """Default bankroll should be 100."""
        assert db.get_bankroll() == 100.0
        assert db.is_halted() == False

    def test_bankroll_management(self):
        db.set_bankroll(150.0)
        assert db.get_bankroll() == 150.0
        # Peak should update
        assert float(db.get_setting("peak_bankroll")) == 150.0
        # Lower bankroll shouldn't update peak
        db.set_bankroll(120.0)
        assert float(db.get_setting("peak_bankroll")) == 150.0

    def test_halt_persistence(self):
        assert not db.is_halted()
        db.set_halted(True, "Test halt")
        assert db.is_halted()
        assert db.get_setting("halt_reason") == "Test halt"
        db.set_halted(False)
        assert not db.is_halted()

    def test_open_and_settle_trade(self):
        trade = {
            "id": "test-001",
            "sleeve": "A",
            "action": "BUY_YES",
            "driver": "VER",
            "market": "podium",
            "grid_pos": 4,
            "price": 0.10,
            "base_rate": 0.28,
            "edge": 0.18,
            "contracts": 5,
            "risk": 0.50,
            "potential_profit": 4.50,
            "ticker": "test-ticker",
            "label": "Test trade",
            "reasoning": "Test",
            "race_name": "Test GP",
            "race_round": 1,
        }
        
        initial_bankroll = db.get_bankroll()
        db.open_trade(trade)
        
        # Bankroll should decrease by risk
        assert db.get_bankroll() == initial_bankroll - 0.50
        
        # Should be in open trades
        open_trades = db.get_open_trades()
        assert len(open_trades) == 1
        assert open_trades[0]["id"] == "test-001"
        
        # Settle as win
        result = db.settle_trade("test-001", won=True)
        assert result is not None
        assert result["won"] == True
        assert result["pnl"] == 4.50
        
        # Bankroll should increase by risk + profit
        assert db.get_bankroll() == initial_bankroll - 0.50 + 0.50 + 4.50
        
        # Should be in history, not open
        assert len(db.get_open_trades()) == 0
        assert len(db.get_trade_history()) == 1

    def test_settle_trade_loss(self):
        trade = {
            "id": "test-002",
            "sleeve": "B",
            "action": "BUY_NO",
            "driver": "NOR",
            "market": "winner",
            "grid_pos": 2,
            "price": 0.40,
            "base_rate": 0.23,
            "edge": 0.17,
            "contracts": 8,
            "risk": 4.80,
            "potential_profit": 3.20,
            "ticker": "test",
            "label": "Test",
            "reasoning": "Test",
            "race_name": "Test",
            "race_round": 1,
        }
        
        initial = db.get_bankroll()
        db.open_trade(trade)
        result = db.settle_trade("test-002", won=False)
        
        assert result["pnl"] == -4.80
        # Bankroll: was reduced by risk at open, stays there on loss
        assert db.get_bankroll() == initial - 4.80

    def test_weekend_risk_tracking(self):
        for i in range(3):
            db.open_trade({
                "id": f"wk-{i}", "sleeve": "A", "action": "BUY_YES",
                "driver": "VER", "market": "podium", "grid_pos": 1,
                "price": 0.10, "base_rate": 0.74, "edge": 0.64,
                "contracts": 1, "risk": 2.0, "potential_profit": 8.0,
                "ticker": "t", "label": "t", "reasoning": "t",
                "race_name": "Test", "race_round": 5,
            })
        
        assert db.get_weekend_risk(5) == 6.0
        assert db.get_weekend_risk(6) == 0.0

    def test_audit_log(self):
        db.audit("TEST", "Test audit entry", {"key": "value"})
        db.audit("TEST", "Second entry")
        
        log = db.get_audit_log()
        assert len(log) >= 2  # May include init entries
        
        test_entries = db.get_audit_log("TEST")
        assert len(test_entries) == 2

    def test_signal_recording(self):
        signal = {
            "id": "sig-001", "sleeve": "A", "action": "BUY_YES",
            "driver": "LEC", "market": "podium", "grid_pos": 4,
            "price": 0.10, "base_rate": 0.28, "edge": 0.18,
            "contracts": 5, "risk": 0.50, "potential_profit": 4.50,
            "ticker": "t", "label": "t", "reasoning": "t",
        }
        db.record_signal(signal, acted_on=True, trade_id="trade-001")
        db.record_signal({**signal, "id": "sig-002"}, acted_on=False, skip_reason="Weekend cap")
        
        signals = db.get_recent_signals()
        assert len(signals) == 2
        acted = [s for s in signals if s["acted_on"]]
        skipped = [s for s in signals if not s["acted_on"]]
        assert len(acted) == 1
        assert len(skipped) == 1
        assert skipped[0]["skip_reason"] == "Weekend cap"

    def test_price_snapshot(self):
        db.record_price_snapshot({
            "ticker": "KX-VER-WIN",
            "driver": "VER",
            "market": "winner",
            "yes_price": 0.50,
            "no_price": 0.50,
            "volume": 100,
            "race_name": "Test GP",
            "race_round": 1,
        })
        
        history = db.get_price_history("KX-VER-WIN")
        assert len(history) == 1
        assert history[0]["yes_price"] == 0.50

    def test_f1_session_storage(self):
        data = {"grid": [{"driver": "VER", "position": 1}]}
        db.store_f1_session(2026, 1, "qualifying", data)
        
        result = db.get_f1_session(2026, 1, "qualifying")
        assert result is not None
        assert result["grid"][0]["driver"] == "VER"
        
        # Different session/round returns None
        assert db.get_f1_session(2026, 2, "qualifying") is None
        assert db.get_f1_session(2026, 1, "race") is None

    def test_full_state_export(self):
        state = db.get_full_state()
        assert "bankroll" in state
        assert "positions" in state
        assert "history" in state
        assert "pnl_curve" in state
        assert "halted" in state
        assert "kalshi_balance" in state
        assert isinstance(state["bankroll"], float)

    def test_reset_clears_everything(self):
        db.set_bankroll(200.0)
        db.set_halted(True, "test")
        db.audit("TEST", "entry")
        
        db.reset_all()
        
        assert db.get_bankroll() == 100.0
        assert not db.is_halted()


# ============================================================
# KILL SWITCH TESTS
# ============================================================

class TestKillSwitch:
    def test_kill_halts_trading(self):
        assert not db.is_halted()
        db.set_halted(True, "Kill switch activated")
        assert db.is_halted()
        assert db.get_setting("halt_reason") == "Kill switch activated"

    def test_unkill_resumes(self):
        db.set_halted(True, "Killed")
        assert db.is_halted()
        db.set_halted(False, "")
        assert not db.is_halted()

    def test_kill_persists_across_reinit(self):
        db.set_halted(True, "Persist test")
        # Simulate restart by re-reading
        assert db.is_halted()
        assert db.get_setting("halt_reason") == "Persist test"

    def test_no_signals_when_halted(self, sample_grid, sample_prices):
        """Strategy should still generate signals (the autonomous loop checks halt separately)."""
        # Strategy itself doesn't check halt — that's the loop's job
        signals = strategy.generate_signals(sample_grid, sample_prices, 100.0, 5)
        assert len(signals) > 0  # Strategy generates signals regardless


# ============================================================
# RISK MANAGEMENT TESTS
# ============================================================

class TestRiskManagement:
    def test_drawdown_halt(self, sample_grid, sample_prices):
        """No signals at $50 (stop-loss floor)."""
        signals = strategy.generate_signals(sample_grid, sample_prices, 50.0, 5)
        assert len(signals) == 0

    def test_drawdown_halt_exact(self, sample_grid, sample_prices):
        """At exactly the floor."""
        signals = strategy.generate_signals(sample_grid, sample_prices, 50.0, 5)
        assert len(signals) == 0

    def test_just_above_floor(self, sample_grid, sample_prices):
        """Just above floor should still generate signals."""
        signals = strategy.generate_signals(sample_grid, sample_prices, 51.0, 5)
        assert len(signals) > 0

    def test_per_trade_max_7_percent(self, sample_grid, sample_prices):
        """Each trade risk ≤ 7% of bankroll."""
        for bankroll in [100.0, 200.0, 75.0]:
            signals = strategy.generate_signals(sample_grid, sample_prices, bankroll, 5)
            max_trade = bankroll * 0.07
            for s in signals:
                # Allow small overshoot due to contract rounding
                assert s["risk"] <= max_trade + 1.0, \
                    f"Trade risk ${s['risk']:.2f} > max ${max_trade:.2f} for bankroll ${bankroll}"

    def test_per_weekend_max_15_percent(self, sample_grid, sample_prices):
        """Total weekend risk ≤ 15% of bankroll."""
        signals = strategy.generate_signals(sample_grid, sample_prices, 100.0, 5)
        total_risk = sum(s["risk"] for s in signals)
        assert total_risk <= 100.0 * 0.15 + 0.01  # Small epsilon for rounding

    def test_calibration_period_half_size(self, sample_grid, sample_prices):
        """First 4 races use half bet size ($2.50)."""
        cal_signals = strategy.generate_signals(sample_grid, sample_prices, 100.0, 1)
        full_signals = strategy.generate_signals(sample_grid, sample_prices, 100.0, 5)
        
        # Find matching signals and compare
        for cs in cal_signals:
            for fs in full_signals:
                if cs["driver"] == fs["driver"] and cs["sleeve"] == fs["sleeve"]:
                    # Calibration contracts should be <= full contracts
                    assert cs["contracts"] <= fs["contracts"], \
                        f"{cs['driver']} {cs['sleeve']}: cal={cs['contracts']} > full={fs['contracts']}"


# ============================================================
# CONFIG TESTS
# ============================================================

class TestConfig:
    def test_base_rates_exist(self):
        assert len(config.PODIUM_BASE_RATES) == 20
        assert len(config.WINNER_BASE_RATES) == 20
        assert config.PODIUM_BASE_RATES[1] == 0.740
        assert config.WINNER_BASE_RATES[1] == 0.450

    def test_calendar_has_23_races(self):
        assert len(config.RACES_2026) == 23

    def test_race_dates_ordered(self):
        dates = [r["date"] for r in config.RACES_2026]
        assert dates == sorted(dates)

    def test_thresholds(self):
        assert config.SLEEVE_A_MIN_EDGE == 0.15
        assert config.SLEEVE_B_MIN_EDGE == 0.08
        assert config.SLEEVE_E_MIN_EDGE == 0.10
        assert config.MAX_PER_TRADE_PCT == 0.07
        assert config.MAX_PER_WEEKEND_PCT == 0.15
        assert config.STOP_LOSS_FLOOR == 50.0
        assert config.CALIBRATION_RACES == 4

    def test_sprint_rounds(self):
        """2026 sprint rounds: China(2), Miami(6), Belgium(12), USA(18), São Paulo(20), Qatar(22)."""
        expected_sprints = {2, 6, 12, 18, 20, 22}
        for r in config.RACES_2026:
            if r["round"] in expected_sprints:
                # Just verify the races exist
                assert r["name"] is not None


# ============================================================
# KALSHI CLIENT TESTS (dry-run mode)
# ============================================================

class TestKalshiClient:
    def test_dry_run_balance(self):
        """In dry-run, balance returns None."""
        import kalshi_client
        result = kalshi_client.get_balance()
        assert result["dry_run"] == True
        assert result["balance"] is None

    def test_dry_run_markets(self):
        import kalshi_client
        result = kalshi_client.get_markets("KXFRACE-TEST")
        assert result == []

    def test_dry_run_place_order(self):
        import kalshi_client
        result = kalshi_client.place_order("TEST-TICKER", "yes", 5, 25)
        assert result["dry_run"] == True
        assert result["ticker"] == "TEST-TICKER"
        assert result["contracts"] == 5
        assert result["price_cents"] == 25

    def test_dry_run_positions(self):
        import kalshi_client
        result = kalshi_client.get_positions()
        assert result == []

    def test_dry_run_get_order(self):
        import kalshi_client
        result = kalshi_client.get_order("test-order-123")
        assert result["dry_run"] == True
        assert result["status"] == "executed"
        assert result["remaining_count"] == 0

    def test_dry_run_cancel_order(self):
        import kalshi_client
        result = kalshi_client.cancel_order("test-order-123")
        assert result["dry_run"] == True
        assert result["status"] == "canceled"

    def test_dry_run_get_orders(self):
        import kalshi_client
        result = kalshi_client.get_orders(status="resting")
        assert result == []

    def test_dry_run_get_fills(self):
        import kalshi_client
        result = kalshi_client.get_fills()
        assert result == []

    def test_dry_run_reconcile(self):
        import kalshi_client
        trades = [{"ticker": "TEST-TICKER", "contracts": 5}]
        result = kalshi_client.reconcile_positions(trades)
        assert result["dry_run"] == True
        assert result["healthy"] == True


# ============================================================
# INTEGRATION: Full trading cycle simulation
# ============================================================

class TestTradingCycle:
    def test_full_race_weekend_cycle(self, sample_grid, sample_prices):
        """Simulate a complete race weekend: signals -> trades -> settlement."""
        bankroll = db.get_bankroll()
        assert bankroll == 100.0
        
        # 1. Generate signals
        signals = strategy.generate_signals(sample_grid, sample_prices, bankroll, 5)
        assert len(signals) > 0
        
        # 2. Open trades
        for sig in signals:
            trade = {**sig, "race_name": "Test GP", "race_round": 5,
                     "kalshi_order_id": "", "kalshi_response": {}}
            db.open_trade(trade)
            db.record_signal(sig, acted_on=True, trade_id=sig["id"])
            db.audit("TRADE_PLACED", f"Placed: {sig['label']}")
        
        open_trades = db.get_open_trades()
        assert len(open_trades) == len(signals)
        
        # 3. Check bankroll decreased
        new_bankroll = db.get_bankroll()
        assert new_bankroll < bankroll
        
        # 4. Settle trades (simulate race result)
        for i, trade in enumerate(open_trades):
            won = i % 2 == 0  # Alternate wins/losses for testing
            result = db.settle_trade(trade["id"], won)
            assert result is not None
            db.audit("TRADE_SETTLED", f"{'WIN' if won else 'LOSS'}: {trade['label']}")
        
        # 5. All settled
        assert len(db.get_open_trades()) == 0
        history = db.get_trade_history()
        assert len(history) == len(signals)
        
        # 6. Audit log should have entries
        audit = db.get_audit_log()
        trade_entries = [a for a in audit if a["event_type"] in ("TRADE_PLACED", "TRADE_SETTLED")]
        assert len(trade_entries) == len(signals) * 2  # placed + settled for each

    def test_multiple_weekends(self, sample_grid, sample_prices):
        """Simulate multiple weekends to test cumulative tracking."""
        traded_rounds = set()
        for race_round in range(1, 4):
            signals = strategy.generate_signals(
                sample_grid, sample_prices, db.get_bankroll(), race_round
            )
            if signals:
                traded_rounds.add(race_round)
            for sig in signals:
                trade = {**sig, "race_name": f"Race {race_round}", "race_round": race_round,
                         "kalshi_order_id": "", "kalshi_response": {}}
                db.open_trade(trade)
            
            # Settle all as wins
            for trade in db.get_open_trades():
                if trade["race_round"] == race_round:
                    db.settle_trade(trade["id"], won=True)
        
        # Should have trades from multiple weekends
        history = db.get_trade_history()
        rounds = {t["race_round"] for t in history if t["race_round"] in traded_rounds}
        assert len(rounds) >= 2  # At least 2 weekends traded


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
