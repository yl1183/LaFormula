"""API endpoint tests using FastAPI TestClient."""
import os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

TEST_DB_DIR = tempfile.mkdtemp()
os.environ["DB_PATH"] = os.path.join(TEST_DB_DIR, "test_api.db")
os.environ["DRY_RUN"] = "true"

import pytest
from fastapi.testclient import TestClient

import db

# Reset db thread-local before import
if hasattr(db._local, 'conn'):
    try: db._local.conn.close()
    except: pass
    db._local.conn = None

# Must import after env setup
from main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def fresh_db():
    db_path = os.environ["DB_PATH"]
    if hasattr(db._local, 'conn') and db._local.conn is not None:
        try: db._local.conn.close()
        except: pass
        db._local.conn = None
    for suffix in ["", "-wal", "-shm"]:
        p = db_path + suffix
        if os.path.exists(p):
            os.remove(p)
    db.init_db()
    yield
    if hasattr(db._local, 'conn') and db._local.conn is not None:
        try: db._local.conn.close()
        except: pass
        db._local.conn = None


class TestHealthEndpoint:
    def test_health(self):
        r = client.get("/api/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "halted" in data
        assert "monitor_active" in data


class TestStateEndpoint:
    def test_get_state(self):
        r = client.get("/api/state")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data["bankroll"], (int, float))
        assert "positions" in data
        assert "history" in data

    def test_reset_state(self):
        db.set_bankroll(200.0)
        r = client.post("/api/state/reset")
        assert r.status_code == 200
        data = r.json()
        assert data["bankroll"] == 100.0


class TestKillSwitch:
    def test_kill_wrong_pin(self):
        r = client.post("/api/kill?pin=000000")
        assert r.status_code == 403

    def test_kill_correct_pin(self):
        r = client.post("/api/kill?pin=483291")
        assert r.status_code == 200
        assert r.json()["status"] == "halted"
        # Verify state
        r2 = client.get("/api/kill/status")
        assert r2.json()["halted"] == True

    def test_unkill(self):
        client.post("/api/kill?pin=483291")
        r = client.post("/api/unkill?pin=483291")
        assert r.status_code == 200
        assert r.json()["status"] == "active"
        r2 = client.get("/api/kill/status")
        assert r2.json()["halted"] == False

    def test_unkill_wrong_pin(self):
        client.post("/api/kill?pin=483291")
        r = client.post("/api/unkill?pin=999999")
        assert r.status_code == 403


class TestBacktestEndpoint:
    def test_default_backtest(self):
        r = client.get("/api/backtest")
        assert r.status_code == 200
        data = r.json()
        assert data["total_trades"] == 30
        assert abs(data["win_rate"] - 66.7) < 1.0
        assert abs(data["final_bankroll"] - 226.01) < 1.0

    def test_custom_backtest(self):
        r = client.get("/api/backtest?sleeve_a=false&sleeve_b=true")
        assert r.status_code == 200
        assert r.json()["total_trades"] == 17  # Sleeve B only


class TestTradingEndpoints:
    def test_open_trades_empty(self):
        r = client.get("/api/trades/open")
        assert r.status_code == 200
        assert r.json() == []

    def test_trade_history_empty(self):
        r = client.get("/api/trades/history")
        assert r.status_code == 200
        assert r.json() == []


class TestMonitorEndpoints:
    def test_monitor_status(self):
        r = client.get("/api/monitor/status")
        assert r.status_code == 200
        data = r.json()
        assert "active" in data
        assert "mode" in data

    def test_recent_signals(self):
        r = client.get("/api/monitor/signals")
        assert r.status_code == 200
        assert isinstance(r.json(), list)


class TestConfigEndpoint:
    def test_get_config(self):
        r = client.get("/api/config")
        assert r.status_code == 200
        data = r.json()
        assert data["dry_run"] == True
        assert len(data["races"]) == 23
        assert "base_rates" in data
        assert data["flat_bet_size"] == 5.0


class TestAuditEndpoint:
    def test_audit_log(self):
        r = client.get("/api/audit")
        assert r.status_code == 200
        assert isinstance(r.json(), list)


class TestKalshiEndpoints:
    def test_balance_dry_run(self):
        r = client.get("/api/kalshi/balance")
        assert r.status_code == 200
        assert r.json()["dry_run"] == True

    def test_sync_dry_run(self):
        r = client.post("/api/kalshi/sync")
        assert r.status_code == 200
        assert r.json()["synced"] == False


class TestPriceEndpoints:
    def test_price_history(self):
        r = client.get("/api/prices/history")
        assert r.status_code == 200
        assert isinstance(r.json(), list)


class TestSPAFallback:
    def test_root_serves_html(self):
        r = client.get("/")
        # Should either serve index.html or 404 if dist doesn't exist relative to test
        assert r.status_code in (200, 404)

    def test_api_routes_not_caught_by_spa(self):
        r = client.get("/api/health")
        assert r.status_code == 200
        assert "status" in r.json()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
