"""Minimal async Solana JSON-RPC client.

Only the handful of methods the assistant needs, built on httpx so we can
run wallet/coin lookups concurrently. Works against the free public RPC and
any drop-in replacement (Helius, QuickNode, ...) via config.SOLANA_RPC_URL.
"""
from typing import Any, Optional

import httpx

from .. import config

SPL_TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"


class SolanaClient:
    def __init__(self, client: httpx.AsyncClient):
        self._client = client
        self._id = 0

    async def _rpc(self, method: str, params: list) -> Any:
        self._id += 1
        resp = await self._client.post(
            config.SOLANA_RPC_URL,
            json={"jsonrpc": "2.0", "id": self._id, "method": method, "params": params},
        )
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"RPC {method} error: {data['error']}")
        return data.get("result")

    async def get_token_holdings(self, owner: str) -> list[dict]:
        """Return SPL token balances for a wallet as
        [{mint, amount (ui), decimals}], filtering zero balances."""
        result = await self._rpc(
            "getTokenAccountsByOwner",
            [owner, {"programId": SPL_TOKEN_PROGRAM}, {"encoding": "jsonParsed"}],
        )
        holdings: list[dict] = []
        for acct in (result or {}).get("value", []):
            try:
                info = acct["account"]["data"]["parsed"]["info"]
                amt = info["tokenAmount"]
                ui = amt.get("uiAmount")
                if not ui:  # skip zero / dust-less balances
                    continue
                holdings.append(
                    {
                        "mint": info["mint"],
                        "amount": float(ui),
                        "decimals": int(amt.get("decimals", 0)),
                    }
                )
            except (KeyError, TypeError):
                continue
        return holdings

    async def get_mint_info(self, mint: str) -> dict:
        """Return {mint_authority, freeze_authority, supply, decimals}."""
        result = await self._rpc(
            "getAccountInfo", [mint, {"encoding": "jsonParsed"}]
        )
        value = (result or {}).get("value")
        if not value:
            return {}
        try:
            info = value["data"]["parsed"]["info"]
        except (KeyError, TypeError):
            return {}
        return {
            "mint_authority": info.get("mintAuthority"),
            "freeze_authority": info.get("freezeAuthority"),
            "supply": float(info.get("supply", 0)),
            "decimals": int(info.get("decimals", 0)),
        }

    async def get_largest_holders(self, mint: str) -> list[float]:
        """Return the largest holder balances (ui amounts), used to gauge
        ownership concentration."""
        result = await self._rpc("getTokenLargestAccounts", [mint])
        out: list[float] = []
        for entry in (result or {}).get("value", []):
            ui = entry.get("uiAmount")
            if ui:
                out.append(float(ui))
        return out


def make_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=config.HTTP_TIMEOUT,
        headers={"content-type": "application/json"},
    )
