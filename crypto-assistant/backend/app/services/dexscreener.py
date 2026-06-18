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
        "dex_url": best.get("url"),
    }


def _to_float(value) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
