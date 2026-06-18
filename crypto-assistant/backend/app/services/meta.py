"""Meta radar: classify coins into narratives and rank what the tracked
group is rotating into.

On Solana, "metas" are the rotating narratives memecoins cluster around
(AI agents, dogs, cats, frogs/Pepe, politics, ...). We tag each held coin by
keyword-matching its symbol/name, then aggregate across all tracked wallets
so the owner can see — at a glance — which narrative the group is most
exposed to and how it's performing.

This is intentionally a transparent keyword classifier so it's easy to tune;
add or edit entries in NARRATIVES.
"""
import re

# narrative -> (emoji, [keywords]). Matched against lowercased symbol+name.
NARRATIVES: dict[str, tuple[str, list[str]]] = {
    "AI / Agents":   ("🤖", ["ai", "gpt", "agent", "neural", "llm", "bot", "goat", "machine", "robot"]),
    "Dogs":          ("🐕", ["dog", "doge", "shib", "inu", "bonk", "wif", "floki", "puppy", "woof"]),
    "Cats":          ("🐈", ["cat", "popcat", "mew", "meow", "kitty", "paw"]),
    "Frogs / Pepe":  ("🐸", ["pepe", "frog", "pep", "kek"]),
    "Politics":      ("🏛️", ["trump", "maga", "boden", "biden", "election", "potus", "kamala"]),
    "Animals":       ("🦛", ["hippo", "moo", "bull", "bear", "monkey", "ape", "penguin", "elon"]),
    "Food":          ("🍔", ["burger", "pizza", "milk", "egg", "banana", "peanut", "wojak"]),
}


def classify_coin(symbol: str | None, name: str | None) -> list[str]:
    """Return the narratives a coin matches (may be several, or none)."""
    text = f"{symbol or ''} {name or ''}".lower()
    tokens = set(re.findall(r"[a-z]+", text))
    hits = []
    for narrative, (_emoji, keywords) in NARRATIVES.items():
        # Whole-token match avoids 'cat' matching 'category' etc.
        if any(kw in tokens for kw in keywords):
            hits.append(narrative)
    return hits


def build_radar(wallet_views: list[dict]) -> list[dict]:
    """Aggregate tagged holdings across wallets into a ranked narrative list."""
    agg: dict[str, dict] = {}
    for w in wallet_views:
        label = w.get("label")
        for coin in w.get("coins", []):
            for narrative in classify_coin(coin.get("symbol"), coin.get("name")):
                emoji = NARRATIVES[narrative][0]
                bucket = agg.setdefault(narrative, {
                    "narrative": narrative, "emoji": emoji,
                    "wallets": set(), "coins": {}, "total_value": 0.0,
                    "changes": [],
                })
                bucket["wallets"].add(label)
                bucket["total_value"] += coin.get("value_usd") or 0
                sym = coin.get("symbol")
                if sym:
                    bucket["coins"][sym] = coin.get("risk_level")
                if coin.get("price_change_24h") is not None:
                    bucket["changes"].append(coin["price_change_24h"])

    radar = []
    for b in agg.values():
        changes = b["changes"]
        radar.append({
            "narrative": b["narrative"],
            "emoji": b["emoji"],
            "wallet_count": len(b["wallets"]),
            "held_by": sorted(b["wallets"]),
            "coins": sorted(b["coins"].keys()),
            "coin_count": len(b["coins"]),
            "total_value": round(b["total_value"], 2),
            "avg_change_24h": round(sum(changes) / len(changes), 1) if changes else None,
        })
    # Rank by how many wallets are in the narrative, then by capital committed.
    radar.sort(key=lambda r: (r["wallet_count"], r["total_value"]), reverse=True)
    return radar
