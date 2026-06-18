"""RugCheck enrichment - optional deeper scam analysis.

RugCheck.xyz exposes a free report endpoint per token mint that adds signals
our own on-chain checks don't cheaply cover: LP lock/burn status, a curated
list of named risks, and an overall score. We treat it as an *optional
enricher*: if it's unreachable (rate limit, network policy, downtime) the
coin still gets our native analysis and we simply skip the extra flags.

Parsing is isolated in normalize_report() so it can be unit-tested with a
fixture without any network access.
"""
from typing import Optional

import httpx

from .. import config
from .analysis import SEV_HIGH, SEV_MED, SEV_OK

_LEVEL_TO_SEV = {
    "danger": SEV_HIGH, "high": SEV_HIGH, "critical": SEV_HIGH,
    "warn": SEV_MED, "warning": SEV_MED, "medium": SEV_MED,
    "good": SEV_OK, "none": SEV_OK, "info": SEV_OK,
}

RUGCHECK_BASE = "https://api.rugcheck.xyz/v1"


async def get_report(client: httpx.AsyncClient, mint: str) -> Optional[dict]:
    """Fetch + normalize a RugCheck report, or None if unavailable."""
    url = f"{RUGCHECK_BASE}/tokens/{mint}/report/summary"
    try:
        resp = await client.get(url, timeout=config.HTTP_TIMEOUT)
        if resp.status_code != 200:
            return None
        return normalize_report(resp.json())
    except (httpx.HTTPError, httpx.TimeoutException, ValueError):
        return None


def normalize_report(raw: dict) -> dict:
    """Map a RugCheck summary payload into our flag/shape vocabulary.

    RugCheck's `score_normalised` runs 0-100 where higher = riskier, matching
    our convention. `risks` is a list of {name, level, description}.
    """
    flags: list[dict] = []
    for risk in raw.get("risks") or []:
        level = (risk.get("level") or "").lower()
        sev = _LEVEL_TO_SEV.get(level, SEV_MED)
        name = risk.get("name") or "Risk"
        flags.append({"severity": sev, "message": f"RugCheck: {name}"})

    return {
        "rugcheck_score": raw.get("score_normalised", raw.get("score")),
        "rugcheck_flags": flags,
        "rugged": bool(raw.get("rugged")),
    }


def merge_into_coin(coin: dict, report: Optional[dict]) -> dict:
    """Fold a normalized RugCheck report into a coin payload, bumping risk."""
    if not report:
        return coin
    coin["rugcheck_score"] = report.get("rugcheck_score")
    coin["rugged"] = report.get("rugged")
    if report.get("rugged"):
        coin["risk_score"] = 100
        coin["risk_level"] = "high"
        coin.setdefault("flags", []).append(
            {"severity": SEV_HIGH, "message": "RugCheck: flagged as RUGGED"}
        )
    # Append RugCheck's named risks to our flag list.
    coin.setdefault("flags", []).extend(report.get("rugcheck_flags", []))
    return coin
