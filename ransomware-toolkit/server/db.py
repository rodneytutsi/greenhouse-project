"""SQLite storage. Chosen over a full database server because the target
deployment is a single small office with a handful of endpoints — SQLite
needs no separate process, license, or ongoing admin, which keeps the
whole toolkit free to run."""
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent / "rwt.sqlite3"

SCHEMA = """
CREATE TABLE IF NOT EXISTS agents (
    agent_id TEXT PRIMARY KEY,
    first_seen REAL NOT NULL,
    last_seen REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    severity TEXT NOT NULL,
    type TEXT NOT NULL,
    details TEXT NOT NULL,
    timestamp REAL NOT NULL,
    acknowledged INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts(timestamp);
"""


@contextmanager
def get_db(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path=DB_PATH):
    with get_db(db_path) as conn:
        conn.executescript(SCHEMA)


def upsert_heartbeat(agent_id: str, timestamp: float, db_path=DB_PATH):
    with get_db(db_path) as conn:
        conn.execute(
            """INSERT INTO agents (agent_id, first_seen, last_seen)
               VALUES (?, ?, ?)
               ON CONFLICT(agent_id) DO UPDATE SET last_seen = excluded.last_seen""",
            (agent_id, timestamp, timestamp),
        )


def insert_alert(agent_id: str, severity: str, alert_type: str, details: str, timestamp: float, db_path=DB_PATH):
    with get_db(db_path) as conn:
        conn.execute(
            """INSERT INTO alerts (agent_id, severity, type, details, timestamp)
               VALUES (?, ?, ?, ?, ?)""",
            (agent_id, severity, alert_type, details, timestamp),
        )
        conn.execute(
            """INSERT INTO agents (agent_id, first_seen, last_seen)
               VALUES (?, ?, ?)
               ON CONFLICT(agent_id) DO UPDATE SET last_seen = excluded.last_seen""",
            (agent_id, timestamp, timestamp),
        )


def list_agents(offline_after_seconds: int = 180, db_path=DB_PATH):
    now = time.time()
    with get_db(db_path) as conn:
        rows = conn.execute("SELECT * FROM agents ORDER BY agent_id").fetchall()
    result = []
    for row in rows:
        status = "online" if (now - row["last_seen"]) <= offline_after_seconds else "offline"
        result.append({**dict(row), "status": status})
    return result


def list_alerts(limit: int = 100, db_path=DB_PATH):
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM alerts ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(row) for row in rows]


def acknowledge_alert(alert_id: int, db_path=DB_PATH):
    with get_db(db_path) as conn:
        conn.execute("UPDATE alerts SET acknowledged = 1 WHERE id = ?", (alert_id,))
