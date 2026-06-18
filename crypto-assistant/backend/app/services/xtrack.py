"""X / Twitter account tracking with a pluggable provider interface.

The hard constraint: X's free API tier is effectively write-only, so reading
tracked accounts' posts requires a paid provider (official Basic tier, or a
third party like twitterapi.io / Apify). To avoid coupling the app to any one
paid choice, post-fetching goes through a small provider interface. Today we
ship:

  * "none" - no posts (default). The account list + per-person linking still
             work, so the dashboard shows who is tracked.
  * "demo" - fixture posts, so the UI is viewable offline.

Adding a real provider later = implement fetch_posts() and register it in
PROVIDERS; no other code changes.
"""
import json
import re
from typing import Optional

import httpx

from .. import config

# Cheap keyword sentiment so posts carry a signal even without an LLM.
_BULLISH = {"buy", "bullish", "moon", "pump", "long", "send", "ape", "gem", "lfg", "up"}
_BEARISH = {"sell", "bearish", "dump", "short", "rug", "scam", "down", "exit", "dead", "avoid"}


def load_accounts() -> list[dict]:
    try:
        with open(config.X_ACCOUNTS_FILE) as f:
            data = json.load(f)
    except FileNotFoundError:
        return []
    return [a for a in data.get("accounts", []) if a.get("handle")]


def simple_sentiment(text: str) -> str:
    tokens = set(re.findall(r"[a-z$]+", (text or "").lower()))
    b = len(tokens & _BULLISH)
    s = len(tokens & _BEARISH)
    if b > s:
        return "bullish"
    if s > b:
        return "bearish"
    return "neutral"


# --- Providers ----------------------------------------------------------

async def _provider_none(client, handle: str) -> list[dict]:
    return []


async def _provider_demo(client, handle: str) -> list[dict]:
    import time
    now = time.time()
    samples = {
        "example_trader_a": [
            ("Aping $GOAT here, AI meta is just getting started 🐐🤖", 12),
            ("Trimmed some $WIF into strength", 90),
        ],
        "example_trader_b": [
            ("This new $SAFEMOON2 looks like an obvious rug, avoid", 30),
            ("Still bullish $BONK long term", 200),
        ],
    }
    posts = samples.get(handle, [("gm", 60)])
    return [
        {"text": text, "ts": now - mins * 60, "sentiment": simple_sentiment(text)}
        for text, mins in posts
    ]


PROVIDERS = {
    "none": _provider_none,
    "demo": _provider_demo,
}


_DEMO_ACCOUNTS = [
    {"person": "Whale Alice", "handle": "example_trader_a"},
    {"person": "Degen Bob", "handle": "example_trader_b"},
]


async def fetch_posts(client: httpx.AsyncClient, handle: str) -> list[dict]:
    # In demo mode always use the demo provider regardless of X_PROVIDER.
    name = "demo" if config.DEMO_MODE else config.X_PROVIDER
    provider = PROVIDERS.get(name, _provider_none)
    try:
        return await provider(client, handle)
    except Exception:
        return []


async def build_accounts_view() -> dict:
    """Return tracked X accounts with their recent posts + sentiment."""
    accounts = _DEMO_ACCOUNTS if config.DEMO_MODE else load_accounts()
    out = []
    async with httpx.AsyncClient(timeout=config.HTTP_TIMEOUT) as client:
        for acc in accounts:
            posts = await fetch_posts(client, acc["handle"])
            bull = sum(1 for p in posts if p["sentiment"] == "bullish")
            bear = sum(1 for p in posts if p["sentiment"] == "bearish")
            out.append({
                "person": acc.get("person"),
                "handle": acc["handle"],
                "url": f"https://x.com/{acc['handle']}",
                "posts": posts,
                "lean": "bullish" if bull > bear else "bearish" if bear > bull else "neutral",
            })
    provider = "demo" if config.DEMO_MODE else config.X_PROVIDER
    return {"accounts": out, "provider": provider}
