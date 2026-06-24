"""GeckoTerminal client - free, keyless source used for three things:

  1. Price history (OHLCV) for sparkline charts
  2. Market-wide discovery: trending pools + new launches on Solana
  3. A backup market-data source when DexScreener has no pair for a mint

All parsing is isolated in normalize_* helpers so it can be unit-tested with
fixtures without network access.

API docs: https://www.geckoterminal.com/dex-api  (v2, network id = "solana")
"""
from typing import Optional

import httpx

from .. import config

GT_BASE = "https://api.geckoterminal.com/api/v2"
NETWORK = "solana"
_HEADERS = {"accept": "application/json;version=20230302"}


def _f(v) -> Optional[float]:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


async def _get(client: httpx.AsyncClient, path: str, params: dict | None = None):
    try:
        resp = await client.get(f"{GT_BASE}{path}", params=params, headers=_HEADERS,
                                timeout=config.HTTP_TIMEOUT)
        if resp.status_code != 200:
            return None
        return resp.json()
    except (httpx.HTTPError, httpx.TimeoutException, ValueError):
        return None


# --- 1. OHLCV history (sparkline) --------------------------------------

async def get_ohlcv(client, pool_address: str, timeframe: str = "hour",
                    limit: int = 24) -> Optional[list[dict]]:
    if not pool_address:
        return None
    raw = await _get(client, f"/networks/{NETWORK}/pools/{pool_address}/ohlcv/{timeframe}",
                     {"limit": limit, "aggregate": 1})
    return normalize_ohlcv(raw)


def normalize_ohlcv(raw: Optional[dict]) -> Optional[list[dict]]:
    if not raw:
        return None
    lst = (((raw.get("data") or {}).get("attributes") or {}).get("ohlcv_list")) or []
    # Each entry: [timestamp, open, high, low, close, volume]; API returns newest first.
    out = [{"ts": e[0], "close": _f(e[4])} for e in lst if len(e) >= 5]
    out.sort(key=lambda x: x["ts"])
    return out or None


# --- 2. Market-wide discovery ------------------------------------------

async def trending_pools(client, limit: int = 10) -> list[dict]:
    raw = await _get(client, f"/networks/{NETWORK}/trending_pools", {"limit": limit})
    return normalize_pools(raw)[:limit]


async def new_pools(client, limit: int = 10) -> list[dict]:
    raw = await _get(client, f"/networks/{NETWORK}/new_pools", {"limit": limit})
    return normalize_pools(raw)[:limit]


def normalize_pools(raw: Optional[dict]) -> list[dict]:
    out = []
    for item in (raw or {}).get("data") or []:
        a = item.get("attributes") or {}
        base_id = (((item.get("relationships") or {}).get("base_token") or {})
                   .get("data") or {}).get("id") or ""
        mint = base_id.split("_", 1)[1] if "_" in base_id else None
        name = a.get("name") or ""
        out.append({
            "name": name,
            "symbol": name.split(" / ")[0] if " / " in name else name,
            "mint": mint,
            "price_usd": _f(a.get("base_token_price_usd")),
            "market_cap": _f(a.get("market_cap_usd")) or _f(a.get("fdv_usd")),
            "liquidity_usd": _f(a.get("reserve_in_usd")),
            "volume_24h": _f((a.get("volume_usd") or {}).get("h24")),
            "price_change_24h": _f((a.get("price_change_percentage") or {}).get("h24")),
            "pool_address": a.get("address"),
        })
    return out


# --- 3. Backup market-data source --------------------------------------

async def get_market(client, mint: str) -> Optional[dict]:
    """DexScreener-compatible market dict from GeckoTerminal token + top pool."""
    raw = await _get(client, f"/networks/{NETWORK}/tokens/{mint}",
                     {"include": "top_pools"})
    if not raw:
        return None
    a = (raw.get("data") or {}).get("attributes") or {}
    if not a:
        return None
    # Pull the top pool (first included) for the pool address used by charts.
    pool_addr = None
    for inc in raw.get("included") or []:
        if inc.get("type") == "pool":
            pool_addr = (inc.get("attributes") or {}).get("address")
            break
    return {
        "symbol": a.get("symbol"),
        "name": a.get("name"),
        "price_usd": _f(a.get("price_usd")),
        "market_cap": _f(a.get("market_cap_usd")) or _f(a.get("fdv_usd")),
        "fdv": _f(a.get("fdv_usd")),
        "liquidity_usd": _f(a.get("total_reserve_in_usd")),
        "volume_24h": _f((a.get("volume_usd") or {}).get("h24")),
        "price_change_24h": None,  # not provided at token level
        "price_change_1h": None,
        "pair_created_at": None,
        "pair_address": pool_addr,
        "dex_url": f"https://www.geckoterminal.com/{NETWORK}/pools/{pool_addr}" if pool_addr else None,
        "source": "geckoterminal",
    }
