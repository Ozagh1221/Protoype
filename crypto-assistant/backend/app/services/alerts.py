"""Consolidated alerts: the 'what needs my attention now' surface.

Scans the analysed wallet views and lifts the things an owner most wants
flagged to the top of the dashboard: any tracked wallet currently holding a
high-risk / rugged coin. Kept separate so it can feed both the dashboard and
(later) push notifications.
"""


def build_alerts(wallet_views: list[dict]) -> list[dict]:
    alerts: list[dict] = []
    for w in wallet_views:
        for coin in w.get("coins", []):
            reasons = []
            if coin.get("rugged"):
                reasons.append("flagged RUGGED by RugCheck")
            elif coin.get("risk_level") == "high":
                reasons.append(f"high risk score {coin.get('risk_score')}")
            if not reasons:
                continue
            alerts.append({
                "wallet_label": w.get("label"),
                "wallet_address": w.get("address"),
                "symbol": coin.get("symbol"),
                "mint": coin.get("mint"),
                "risk_score": coin.get("risk_score"),
                "value_usd": coin.get("value_usd"),
                "reason": "; ".join(reasons),
            })
    # Biggest exposure first.
    alerts.sort(key=lambda a: a.get("value_usd") or 0, reverse=True)
    return alerts
