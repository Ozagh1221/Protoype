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
        # Latest known balance per wallet+mint, used to diff between polls.
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS holdings_snapshot (
                wallet_address TEXT NOT NULL,
                mint           TEXT NOT NULL,
                amount         REAL NOT NULL,
                updated_at     REAL NOT NULL,
                PRIMARY KEY (wallet_address, mint)
            )
            """
        )
        # Append-only feed of detected position changes.
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS activity (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                ts             REAL NOT NULL,
                wallet_label   TEXT,
                wallet_address TEXT,
                mint           TEXT,
                symbol         TEXT,
                event_type     TEXT,
                delta          REAL,
                level          TEXT,
                note           TEXT
            )
            """
        )
        c.execute("CREATE INDEX IF NOT EXISTS idx_activity_ts ON activity(ts DESC)")
        c.commit()


# --- Holdings snapshots / diffing --------------------------------------

def get_wallet_snapshot(address: str) -> dict[str, float]:
    """Return {mint: amount} of the last stored snapshot for a wallet."""
    with _conn() as c:
        rows = c.execute(
            "SELECT mint, amount FROM holdings_snapshot WHERE wallet_address = ?",
            (address,),
        ).fetchall()
    return {r["mint"]: r["amount"] for r in rows}


def replace_wallet_snapshot(address: str, holdings: dict[str, float]) -> None:
    """Overwrite the stored snapshot for a wallet with the current holdings."""
    now = time.time()
    with _conn() as c:
        c.execute("DELETE FROM holdings_snapshot WHERE wallet_address = ?", (address,))
        c.executemany(
            "INSERT INTO holdings_snapshot (wallet_address, mint, amount, updated_at) "
            "VALUES (?, ?, ?, ?)",
            [(address, mint, amt, now) for mint, amt in holdings.items()],
        )
        c.commit()


def wallet_has_snapshot(address: str) -> bool:
    with _conn() as c:
        row = c.execute(
            "SELECT 1 FROM holdings_snapshot WHERE wallet_address = ? LIMIT 1",
            (address,),
        ).fetchone()
    return row is not None


# --- Activity feed ------------------------------------------------------

def record_activity(event: dict) -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO activity (ts, wallet_label, wallet_address, mint, symbol, "
            "event_type, delta, level, note) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                event.get("ts", time.time()),
                event.get("wallet_label"),
                event.get("wallet_address"),
                event.get("mint"),
                event.get("symbol"),
                event.get("event_type"),
                event.get("delta"),
                event.get("level", "info"),
                event.get("note"),
            ),
        )
        c.commit()


def get_recent_activity(limit: int = 100) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM activity ORDER BY ts DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


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
