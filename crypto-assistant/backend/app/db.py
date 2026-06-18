"""Tiny SQLite layer used as a cache for coin analysis.

Mint authorities and holder distributions change rarely, and prices change
constantly, so we cache the *whole* analysis blob with a short TTL
(config.COIN_CACHE_TTL) to stay friendly to free rate limits.
"""
import json
import sqlite3
import time
from contextlib import contextmanager
from typing import Optional

from . import config


def init_db() -> None:
    with _conn() as c:
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS coin_cache (
                mint        TEXT PRIMARY KEY,
                payload     TEXT NOT NULL,
                updated_at  REAL NOT NULL
            )
            """
        )
        c.commit()


@contextmanager
def _conn():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def get_cached_coin(mint: str) -> Optional[dict]:
    """Return cached analysis dict if present and still fresh, else None."""
    with _conn() as c:
        row = c.execute(
            "SELECT payload, updated_at FROM coin_cache WHERE mint = ?", (mint,)
        ).fetchone()
    if not row:
        return None
    if time.time() - row["updated_at"] > config.COIN_CACHE_TTL:
        return None
    return json.loads(row["payload"])


def put_cached_coin(mint: str, payload: dict) -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO coin_cache (mint, payload, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(mint) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at",
            (mint, json.dumps(payload), time.time()),
        )
        c.commit()
