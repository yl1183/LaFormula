PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;
CREATE TABLE settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
INSERT INTO settings VALUES('bankroll','100.0','2026-03-04T07:12:34.413718+00:00');
INSERT INTO settings VALUES('initial_bankroll','100.0','2026-03-04T07:12:34.413718+00:00');
INSERT INTO settings VALUES('peak_bankroll','100.0','2026-03-04T07:12:34.413718+00:00');
INSERT INTO settings VALUES('halted','false','2026-03-04T07:12:34.413718+00:00');
INSERT INTO settings VALUES('halt_reason','','2026-03-04T07:12:34.413718+00:00');
INSERT INTO settings VALUES('current_race','0','2026-03-04T07:12:34.413718+00:00');
INSERT INTO settings VALUES('kalshi_balance_cents','','2026-03-04T07:12:34.413718+00:00');
INSERT INTO settings VALUES('last_kalshi_sync','','2026-03-04T07:12:34.413718+00:00');
INSERT INTO settings VALUES('races_completed','0','2026-03-04T07:12:34.413718+00:00');
CREATE TABLE trades (
            id TEXT PRIMARY KEY,
            sleeve TEXT NOT NULL,
            action TEXT NOT NULL,
            driver TEXT NOT NULL,
            market TEXT NOT NULL,
            grid_pos INTEGER,
            price REAL NOT NULL,
            base_rate REAL NOT NULL,
            edge REAL NOT NULL,
            contracts INTEGER NOT NULL,
            risk REAL NOT NULL,
            potential_profit REAL NOT NULL,
            ticker TEXT,
            label TEXT,
            reasoning TEXT,
            race_name TEXT,
            race_round INTEGER,
            status TEXT NOT NULL DEFAULT 'open',
            won INTEGER,
            pnl REAL,
            kalshi_order_id TEXT,
            kalshi_response TEXT,
            opened_at TEXT NOT NULL,
            settled_at TEXT
        );
CREATE TABLE signals (
            id TEXT PRIMARY KEY,
            sleeve TEXT NOT NULL,
            action TEXT NOT NULL,
            driver TEXT NOT NULL,
            market TEXT NOT NULL,
            grid_pos INTEGER,
            price REAL NOT NULL,
            base_rate REAL NOT NULL,
            edge REAL NOT NULL,
            contracts INTEGER NOT NULL,
            risk REAL NOT NULL,
            potential_profit REAL NOT NULL,
            ticker TEXT,
            label TEXT,
            reasoning TEXT,
            race_name TEXT,
            race_round INTEGER,
            acted_on INTEGER NOT NULL DEFAULT 0,
            trade_id TEXT,
            skip_reason TEXT,
            created_at TEXT NOT NULL
        );
CREATE TABLE price_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            driver TEXT,
            market TEXT,
            yes_price REAL,
            no_price REAL,
            volume INTEGER,
            race_name TEXT,
            race_round INTEGER,
            captured_at TEXT NOT NULL
        );
CREATE TABLE audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            detail TEXT,
            metadata TEXT,
            created_at TEXT NOT NULL
        );
INSERT INTO audit_log VALUES(1,'SYSTEM','Server started','','2026-03-04T07:12:34.416401+00:00');
INSERT INTO audit_log VALUES(2,'SYSTEM','Autonomous trading loop started','','2026-03-04T07:12:34.420091+00:00');
INSERT INTO audit_log VALUES(3,'SYSTEM','Server shutdown','','2026-03-05T04:19:19.484151+00:00');
CREATE TABLE f1_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER NOT NULL,
            round INTEGER NOT NULL,
            session_type TEXT NOT NULL,
            data TEXT,
            fetched_at TEXT NOT NULL,
            UNIQUE(year, round, session_type)
        );
DELETE FROM sqlite_sequence;
INSERT INTO sqlite_sequence VALUES('audit_log',3);
CREATE INDEX idx_trades_status ON trades(status);
CREATE INDEX idx_trades_race ON trades(race_round);
CREATE INDEX idx_signals_race ON signals(race_round);
CREATE INDEX idx_audit_type ON audit_log(event_type);
CREATE INDEX idx_price_ticker ON price_snapshots(ticker, captured_at);
COMMIT;
