"""Demo data provider.

When DEMO_MODE is enabled (or live RPC/market endpoints are unreachable),
the dashboard is driven by realistic fixture data run through the *real*
analysis engine. This lets you verify the full UI + risk-scoring pipeline
offline, and serves as a test fixture. The shape mirrors what the live
Solana RPC + DexScreener services return.
"""
from . import analysis, meta

# (mint_info, largest_holders, market) per coin — chosen to exercise the
# full range of the risk engine.
_COINS = {
    "BONKmintXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX1": (
        {"mint_authority": None, "freeze_authority": None, "supply": 1e14, "decimals": 5, "supply_ui": 1e9},
        [1.2e8, 9e7, 7e7],
        {"symbol": "BONK", "name": "Bonk", "price_usd": 0.000023, "market_cap": 1_600_000_000,
         "liquidity_usd": 4_200_000, "volume_24h": 90_000_000, "price_change_24h": 8.4,
         "price_change_1h": 1.2, "pair_created_at": None, "dex_url": "https://dexscreener.com"},
    ),
    "WIFmintXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX2": (
        {"mint_authority": None, "freeze_authority": None, "supply": 1e9, "decimals": 6, "supply_ui": 1e9},
        [2.1e8, 1.1e8, 6e7],
        {"symbol": "WIF", "name": "dogwifhat", "price_usd": 1.85, "market_cap": 1_850_000_000,
         "liquidity_usd": 8_500_000, "volume_24h": 120_000_000, "price_change_24h": -3.1,
         "price_change_1h": -0.6, "pair_created_at": None, "dex_url": "https://dexscreener.com"},
    ),
    "RUGmintXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX3": (
        {"mint_authority": "Scammer11111111111111111111111111111111111", "freeze_authority": "Scammer11111111111111111111111111111111111",
         "supply": 1e9, "decimals": 6, "supply_ui": 1e9},
        [9.3e8, 4e7],
        {"symbol": "SAFEMOON2", "name": "Totally Safe Inu", "price_usd": 0.00000004, "market_cap": 40_000,
         "liquidity_usd": 1_800, "volume_24h": 12_000, "price_change_24h": -71.0,
         "price_change_1h": -22.0, "pair_created_at": None, "dex_url": "https://dexscreener.com"},
    ),
    "AImintXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX4": (
        {"mint_authority": None, "freeze_authority": None, "supply": 1e9, "decimals": 6, "supply_ui": 1e9},
        [5.5e8, 1e8, 5e7],
        {"symbol": "GOAT", "name": "Goatseus Maximus", "price_usd": 0.42, "market_cap": 420_000_000,
         "liquidity_usd": 3_100_000, "volume_24h": 45_000_000, "price_change_24h": 24.7,
         "price_change_1h": 5.5, "pair_created_at": None, "dex_url": "https://dexscreener.com"},
    ),
}

# Which coins each demo wallet holds, and the held amount (ui).
_WALLETS = [
    {"label": "Whale Alice", "address": "Aiice1111111111111111111111111111111111111",
     "notes": "Demo target", "holdings": [
        ("BONKmintXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX1", 50_000_000),
        ("AImintXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX4", 200_000),
        ("WIFmintXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX2", 30_000)]},
    {"label": "Degen Bob", "address": "Bob2222222222222222222222222222222222222222",
     "notes": "Demo target", "holdings": [
        ("AImintXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX4", 90_000),
        ("RUGmintXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX3", 500_000_000)]},
    {"label": "Smart Money Carol", "address": "Caro3333333333333333333333333333333333333",
     "notes": "Demo target", "holdings": [
        ("BONKmintXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX1", 120_000_000),
        ("AImintXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX4", 350_000)]},
    {"label": "Quiet Dave", "address": "Dave4444444444444444444444444444444444444",
     "notes": "Demo target", "holdings": []},
]


def _coin_payload(mint: str) -> dict:
    mint_info, largest, market = _COINS[mint]
    risk = analysis.analyze(mint_info, largest, market)
    return {
        "mint": mint, "symbol": market["symbol"], "name": market["name"],
        "price_usd": market["price_usd"], "market_cap": market["market_cap"],
        "liquidity_usd": market["liquidity_usd"], "volume_24h": market["volume_24h"],
        "price_change_24h": market["price_change_24h"], "price_change_1h": market["price_change_1h"],
        "dex_url": market["dex_url"], **risk,
    }


def build_activity() -> list[dict]:
    """Synthetic activity feed so the live panel is viewable offline."""
    import time
    now = time.time()
    raw = [
        (2,    "Smart Money Carol", "AImintXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX4", "GOAT", "NEW", "alert", "risk 12"),
        (9,    "Whale Alice",       "AImintXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX4", "GOAT", "ADD", "info", "risk 12"),
        (24,   "Degen Bob",         "RUGmintXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX3", "SAFEMOON2", "NEW", "alert", "risk 100 - HIGH RISK"),
        (51,   "Whale Alice",       "WIFmintXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX2", "WIF", "REDUCE", "info", None),
        (140,  "Smart Money Carol", "BONKmintXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX1", "BONK", "NEW", "alert", "risk 0"),
        (210,  "Degen Bob",         "WIFmintXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX2", "WIF", "EXIT", "alert", None),
    ]
    return [{
        "ts": now - mins * 60, "wallet_label": label, "mint": mint, "symbol": sym,
        "event_type": etype, "level": level, "note": note,
        "delta": 1 if etype in ("NEW", "ADD") else -1,
    } for mins, label, mint, sym, etype, level, note in raw]


def build_overview() -> dict:
    coins = {m: _coin_payload(m) for m in _COINS}
    wallet_views = []
    holders_by_mint: dict[str, list[str]] = {}
    for w in _WALLETS:
        coin_list = []
        for mint, amount in w["holdings"]:
            coin = coins[mint]
            holders_by_mint.setdefault(mint, []).append(w["label"])
            coin_list.append({**coin, "amount": amount,
                              "value_usd": (coin["price_usd"] or 0) * amount})
        coin_list.sort(key=lambda c: c["value_usd"], reverse=True)
        wallet_views.append({"label": w["label"], "address": w["address"],
                             "notes": w["notes"], "coins": coin_list})

    rollup = []
    for mint, labels in holders_by_mint.items():
        if len(set(labels)) < 2:
            continue
        coin = coins[mint]
        rollup.append({"mint": mint, "symbol": coin["symbol"], "market_cap": coin["market_cap"],
                       "price_change_24h": coin["price_change_24h"], "risk_score": coin["risk_score"],
                       "risk_level": coin["risk_level"], "held_by": sorted(set(labels)),
                       "holder_count": len(set(labels))})
    rollup.sort(key=lambda r: r["holder_count"], reverse=True)
    return {"wallets": wallet_views, "shared_coins": rollup,
            "metas": meta.build_radar(wallet_views),
            "wallet_count": len(_WALLETS), "coin_count": len(_COINS), "demo": True}
