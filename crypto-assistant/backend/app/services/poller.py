"""Background poller: turns periodic holdings snapshots into a live feed.

On each run it fetches every tracked wallet's current SPL holdings, diffs
them against the previously stored snapshot, and records position changes
(new buys, adds, reduces, exits) into the activity feed. The first time it
sees a wallet it records a baseline only (no events) so the feed isn't
flooded on startup.
"""
import asyncio
import logging
import time

from .. import config, db
from . import dexscreener
from .solana import SolanaClient, make_http_client
from .tracker import load_wallets

log = logging.getLogger("poller")

# Ignore position changes smaller than this fraction of the prior balance.
_REL_THRESHOLD = 0.05


def _classify(old_amt: float, new_amt: float) -> tuple[str, str] | None:
    """Return (event_type, level) for a balance change, or None if trivial."""
    if old_amt == 0 and new_amt > 0:
        return "NEW", "alert"          # entering a position is notable
    if new_amt == 0 and old_amt > 0:
        return "EXIT", "alert"         # so is fully leaving one
    if old_amt > 0:
        change = (new_amt - old_amt) / old_amt
        if change >= _REL_THRESHOLD:
            return "ADD", "info"
        if change <= -_REL_THRESHOLD:
            return "REDUCE", "info"
    return None


async def _poll_wallet(sol: SolanaClient, wallet: dict) -> list[dict]:
    address = wallet["address"]
    try:
        holdings = await sol.get_token_holdings(address)
    except Exception as e:
        log.warning("poll failed for %s: %s", wallet.get("label"), e)
        return []

    current = {
        h["mint"]: h["amount"]
        for h in holdings
        if h["mint"] not in config.IGNORED_MINTS
    }

    # First sighting: store baseline, emit nothing.
    if not db.wallet_has_snapshot(address):
        db.replace_wallet_snapshot(address, current)
        return []

    old = db.get_wallet_snapshot(address)
    events: list[dict] = []
    now = time.time()
    for mint in set(old) | set(current):
        verdict = _classify(old.get(mint, 0.0), current.get(mint, 0.0))
        if not verdict:
            continue
        event_type, level = verdict
        cached = db.get_cached_coin(mint) or {}
        # Buying a high-risk coin is always worth an alert.
        if cached.get("risk_level") == "high" and event_type in ("NEW", "ADD"):
            level = "alert"
        events.append({
            "ts": now,
            "wallet_label": wallet.get("label"),
            "wallet_address": address,
            "mint": mint,
            "symbol": cached.get("symbol") or mint[:4] + "…",
            "event_type": event_type,
            "delta": current.get(mint, 0.0) - old.get(mint, 0.0),
            "level": level,
            "note": cached.get("risk_level") and f"risk {cached.get('risk_score')}",
        })

    db.replace_wallet_snapshot(address, current)
    return events


async def poll_once() -> int:
    """Run one polling cycle across all wallets. Returns #events recorded."""
    wallets = load_wallets()
    async with make_http_client() as client:
        sol = SolanaClient(client)
        results = await asyncio.gather(*(_poll_wallet(sol, w) for w in wallets))
    recorded = 0
    for events in results:
        for ev in events:
            db.record_activity(ev)
            recorded += 1
    if recorded:
        log.info("poll recorded %d activity events", recorded)
    return recorded
