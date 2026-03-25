from __future__ import annotations

import sqlite3
import logging
from flask import g, current_app

logger = logging.getLogger(__name__)

SCHEMA = """
-- Raw items as ingested from sources before LLM processing
CREATE TABLE IF NOT EXISTS raw_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    external_id TEXT,
    title TEXT NOT NULL,
    url TEXT,
    raw_content TEXT,
    author TEXT,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_name, external_id)
);

-- Processed items after LLM enrichment
CREATE TABLE IF NOT EXISTS processed_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_item_id INTEGER NOT NULL REFERENCES raw_items(id),
    summary TEXT NOT NULL,
    relevance_score INTEGER NOT NULL,
    hype_score INTEGER NOT NULL,
    teaching_angle TEXT,
    key_stats TEXT,
    tags TEXT,
    verdict TEXT NOT NULL,
    llm_reasoning TEXT,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Ops person and CEO actions
CREATE TABLE IF NOT EXISTS item_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    processed_item_id INTEGER NOT NULL REFERENCES processed_items(id),
    action TEXT NOT NULL,
    acted_by TEXT NOT NULL,
    note TEXT,
    acted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_processed_verdict ON processed_items(verdict);
CREATE INDEX IF NOT EXISTS idx_processed_at ON processed_items(processed_at);
CREATE INDEX IF NOT EXISTS idx_item_actions_pid ON item_actions(processed_item_id);
CREATE INDEX IF NOT EXISTS idx_raw_items_dedup ON raw_items(source_name, external_id);
"""


def get_db_connection(db_path: str) -> sqlite3.Connection:
    """Create a new database connection with row factory enabled."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: str):
    """Initialize the database schema."""
    conn = get_db_connection(db_path)
    conn.executescript(SCHEMA)
    conn.close()
    logger.info(f"Database initialized at {db_path}")


def get_db(close: bool = False) -> sqlite3.Connection | None:
    """Get a database connection for the current Flask request context.

    If close=True, closes the connection and returns None (used in teardown).
    """
    if close:
        db = g.pop("db", None)
        if db is not None:
            db.close()
        return None

    if "db" not in g:
        g.db = get_db_connection(current_app.config["DATABASE_PATH"])
    return g.db
