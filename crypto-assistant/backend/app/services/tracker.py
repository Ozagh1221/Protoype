"""Orchestration: turn tracked wallets into an analysed portfolio view.

Flow:
  wallet -> SPL holdings -> (per unique mint) market data + on-chain facts
         -> risk analysis -> assembled dashboard payload

Per-mint analysis is cached (SQLite, short TTL) and de-duplicated so that a
coin held by many wallets is only fetched once per refresh.
"""
import asyncio
import json
from typing import Optional

from .. import config, db
from . import analysis, dexscreener
from .solana import SolanaClient, make_http_client


def load_wallets() -> list[dict]:
    with open(config.WALLETS_FILE) as f:
        data = json.load(f)
    return [w for w in data.get("wallets", []) if w.get("address")]


async def _analyze_mint(client, sol: SolanaClient, mint: str, sem: asyncio.Semaphore) -> dict:
    """Fetch + analyse a single coin (cached). Returns a coin payload."""
    cached = db.get_cached_coin(mint)
    if cached:
        return cached

    async with sem:
        market, mint_info, largest = await asyncio.gather(
            dexscreener.get_market(client, mint),
            sol.get_mint_info(mint),
            sol.get_largest_holders(mint),
            return_exceptions=True,
        )

    # Tolerate partial failures from the free endpoints.
    market = market if isinstance(market, dict) else None
    mint_info = mint_info if isinstance(mint_info, dict) else {}
    largest = largest if isinstance(largest, list) else []

    if mint_info.get("supply") is not None:
        decimals = mint_info.get("decimals", 0)
        mint_info["supply_ui"] = mint_info["supply"] / (10 ** decimals)

    risk = analysis.analyze(mint_info, largest, market)

    payload = {
        "mint": mint,
        "symbol": (market or {}).get("symbol") or mint[:4] + "…",
        "name": (market or {}).get("name"),
        "price_usd": (market or {}).get("price_usd"),
        "market_cap": (market or {}).get("market_cap"),
        "liquidity_usd": (market or {}).get("liquidity_usd"),
        "volume_24h": (market or {}).get("volume_24h"),
        "price_change_24h": (market or {}).get("price_change_24h"),
        "price_change_1h": (market or {}).get("price_change_1h"),
        "dex_url": (market or {}).get("dex_url"),
        **risk,
    }
    db.put_cached_coin(mint, payload)
    return payload


async def build_overview() -> dict:
    """Return the full dashboard payload across all tracked wallets."""
    wallets = load_wallets()
    sem = asyncio.Semaphore(config.MAX_CONCURRENCY)

    async with make_http_client() as client:
        sol = SolanaClient(client)

        # 1) Fetch every wallet's holdings concurrently.
        async def holdings_for(w):
            try:
                return w, await sol.get_token_holdings(w["address"])
            except Exception as e:  # keep one bad wallet from sinking the page
                return w, {"error": str(e)}

        results = await asyncio.gather(*(holdings_for(w) for w in wallets))

        # 2) Collect the unique set of non-stablecoin mints to analyse.
        unique_mints: set[str] = set()
        for _w, holds in results:
            if isinstance(holds, dict):  # error sentinel
                continue
            for h in holds:
                if h["mint"] not in config.IGNORED_MINTS:
                    unique_mints.add(h["mint"])

        coin_tasks = {m: _analyze_mint(client, sol, m, sem) for m in unique_mints}
        coins = dict(zip(coin_tasks.keys(), await asyncio.gather(*coin_tasks.values())))

    # 3) Assemble per-wallet views + a cross-wallet coin rollup.
    wallet_views = []
    holders_by_mint: dict[str, list[str]] = {}
    for w, holds in results:
        if isinstance(holds, dict):
            wallet_views.append({"label": w["label"], "address": w["address"],
                                 "notes": w.get("notes"), "error": holds.get("error"),
                                 "coins": []})
            continue
        coin_list = []
        for h in holds:
            if h["mint"] in config.IGNORED_MINTS:
                continue
            coin = coins.get(h["mint"])
            if not coin:
                continue
            value_usd = (coin.get("price_usd") or 0) * h["amount"]
            if value_usd < config.MIN_HOLDING_USD and coin.get("price_usd"):
                continue  # drop dust
            holders_by_mint.setdefault(h["mint"], []).append(w["label"])
            coin_list.append({**coin, "amount": h["amount"], "value_usd": value_usd})
        coin_list.sort(key=lambda c: c.get("value_usd") or 0, reverse=True)
        wallet_views.append({"label": w["label"], "address": w["address"],
                             "notes": w.get("notes"), "coins": coin_list})

    # Coins held by more than one tracked wallet = early "meta" signal.
    rollup = []
    for mint, labels in holders_by_mint.items():
        coin = coins.get(mint, {})
        rollup.append({
            "mint": mint,
            "symbol": coin.get("symbol"),
            "market_cap": coin.get("market_cap"),
            "price_change_24h": coin.get("price_change_24h"),
            "risk_score": coin.get("risk_score"),
            "risk_level": coin.get("risk_level"),
            "held_by": sorted(set(labels)),
            "holder_count": len(set(labels)),
        })
    rollup.sort(key=lambda r: r["holder_count"], reverse=True)

    return {
        "wallets": wallet_views,
        "shared_coins": rollup,
        "wallet_count": len(wallets),
        "coin_count": len(unique_mints),
    }
