"""Coin risk / scam analysis.

Combines on-chain facts (mint & freeze authority, holder concentration,
supply) with market data (liquidity, price movement, age) into a single
0-100 risk score plus human-readable flags. Higher score = riskier.

This is intentionally transparent and rule-based so the owner can trust and
tune it. Each contributing rule adds points and a flag.
"""
import time
from typing import Optional

# A flag: (severity, message). Severity drives the colour in the UI.
SEV_HIGH = "high"
SEV_MED = "med"
SEV_LOW = "low"
SEV_OK = "ok"


def top_holder_concentration(largest: list[float], supply_ui: Optional[float]) -> Optional[float]:
    """Percent of supply held by the top-10 accounts (0-100).

    Note: on Solana the largest accounts often include the liquidity pool /
    locked supply, so treat very high values as a *flag to investigate*,
    not absolute proof of a rug.
    """
    if not largest or not supply_ui:
        return None
    top10 = sum(sorted(largest, reverse=True)[:10])
    if supply_ui <= 0:
        return None
    return min(100.0, round(top10 / supply_ui * 100, 2))


def analyze(mint_info: dict, largest: list[float], market: Optional[dict]) -> dict:
    """Return a structured risk assessment dict."""
    flags: list[dict] = []
    score = 0

    # --- Authorities (the classic rug levers) --------------------------
    mint_auth = mint_info.get("mint_authority")
    freeze_auth = mint_info.get("freeze_authority")

    if mint_auth:
        score += 30
        flags.append({"severity": SEV_HIGH, "message": "Mint authority active - supply can be inflated"})
    else:
        flags.append({"severity": SEV_OK, "message": "Mint authority revoked"})

    if freeze_auth:
        score += 25
        flags.append({"severity": SEV_HIGH, "message": "Freeze authority active - your tokens can be frozen"})
    else:
        flags.append({"severity": SEV_OK, "message": "Freeze authority revoked"})

    # --- Ownership concentration --------------------------------------
    concentration = top_holder_concentration(largest, mint_info.get("supply_ui"))
    if concentration is not None:
        if concentration >= 80:
            score += 25
            flags.append({"severity": SEV_HIGH, "message": f"Top-10 holders own {concentration:.0f}% of supply"})
        elif concentration >= 50:
            score += 12
            flags.append({"severity": SEV_MED, "message": f"Top-10 holders own {concentration:.0f}% of supply"})
        else:
            flags.append({"severity": SEV_OK, "message": f"Top-10 holders own {concentration:.0f}% of supply"})

    # --- Liquidity -----------------------------------------------------
    liq = (market or {}).get("liquidity_usd")
    if liq is not None:
        if liq < 5_000:
            score += 20
            flags.append({"severity": SEV_HIGH, "message": f"Very thin liquidity (${liq:,.0f})"})
        elif liq < 25_000:
            score += 10
            flags.append({"severity": SEV_MED, "message": f"Low liquidity (${liq:,.0f})"})
        else:
            flags.append({"severity": SEV_OK, "message": f"Liquidity ${liq:,.0f}"})
    else:
        score += 10
        flags.append({"severity": SEV_MED, "message": "No DEX liquidity found"})

    # --- Age (very new = higher risk) ---------------------------------
    created = (market or {}).get("pair_created_at")
    if created:
        age_hours = (time.time() * 1000 - created) / 3_600_000
        if age_hours < 24:
            score += 10
            flags.append({"severity": SEV_MED, "message": f"Launched {age_hours:.0f}h ago"})

    # --- Price movement (informational, mild signal) ------------------
    chg = (market or {}).get("price_change_24h")
    if chg is not None and chg < -50:
        score += 5
        flags.append({"severity": SEV_MED, "message": f"Down {chg:.0f}% in 24h"})

    score = min(100, score)
    return {
        "risk_score": score,
        "risk_level": _level(score),
        "concentration_pct": concentration,
        "mint_authority_active": bool(mint_auth),
        "freeze_authority_active": bool(freeze_auth),
        "flags": flags,
    }


def _level(score: int) -> str:
    if score >= 60:
        return "high"
    if score >= 30:
        return "medium"
    return "low"
