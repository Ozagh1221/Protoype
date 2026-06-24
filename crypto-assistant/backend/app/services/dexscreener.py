"""DexScreener client - free, keyless source for live market data.

Given a token mint it returns the most-liquid trading pair's price, market
cap / FDV, liquidity, 24h volume and price change.
"""
from typing import Optional

import httpx

from .. import config


async def get_market(client: httpx.AsyncClient, mint: str) -> Optional[dict]:
    url = f"{config.DEXSCREENER_BASE}/latest/dex/tokens/{mint}"
    try:
        resp = await client.get(url)
        resp.raise_for_status()
    except (httpx.HTTPError, httpx.TimeoutException):
        return None

    pairs = (resp.json() or {}).get("pairs") or []
    # Keep only Solana pairs, then pick the deepest liquidity pool.
    sol_pairs = [p for p in pairs if p.get("chainId") == "solana"]
    if not sol_pairs:
        return None
    best = max(sol_pairs, key=lambda p: (p.get("liquidity") or {}).get("usd") or 0)

    return {
        "symbol": (best.get("baseToken") or {}).get("symbol"),
        "name": (best.get("baseToken") or {}).get("name"),
        "price_usd": _to_float(best.get("priceUsd")),
        "market_cap": _to_float(best.get("marketCap")) or _to_float(best.get("fdv")),
        "fdv": _to_float(best.get("fdv")),
        "liquidity_usd": _to_float((best.get("liquidity") or {}).get("usd")),
        "volume_24h": _to_float((best.get("volume") or {}).get("h24")),
        "price_change_24h": _to_float((best.get("priceChange") or {}).get("h24")),
        "price_change_1h": _to_float((best.get("priceChange") or {}).get("h1")),
        "pair_created_at": best.get("pairCreatedAt"),
        "pair_address": best.get("pairAddress"),  # pool address, for OHLCV charts
        "dex_url": best.get("url"),
        "source": "dexscreener",
    }


def _to_float(value) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


async def resolve_query(client: httpx.AsyncClient, query: str) -> Optional[str]:
    """Resolve a free-text query (symbol or name) to a Solana token mint.

    Picks the deepest-liquidity Solana pair, preferring an exact symbol match.
    """
    url = f"{config.DEXSCREENER_BASE}/latest/dex/search"
    try:
        resp = await client.get(url, params={"q": query})
        resp.raise_for_status()
    except (httpx.HTTPError, httpx.TimeoutException):
        return None

    pairs = [p for p in (resp.json() or {}).get("pairs") or [] if p.get("chainId") == "solana"]
    if not pairs:
        return None

    q = query.strip().lower()
    exact = [p for p in pairs if ((p.get("baseToken") or {}).get("symbol") or "").lower() == q]
    pool = exact or pairs
    best = max(pool, key=lambda p: (p.get("liquidity") or {}).get("usd") or 0)
    return (best.get("baseToken") or {}).get("address")
