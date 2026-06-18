"""Central configuration for the crypto assistant backend.

All settings are environment-overridable so you can start on free public
infrastructure and later upgrade to paid RPC/data providers without code
changes (just set the env vars).
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # .../backend
REPO_DIR = BASE_DIR.parent                          # .../crypto-assistant

# --- Solana RPC ---------------------------------------------------------
# Defaults to the free public mainnet endpoint. Swap to a (free) Helius or
# other provider URL later for higher rate limits:
#   export SOLANA_RPC_URL="https://mainnet.helius-rpc.com/?api-key=YOUR_KEY"
SOLANA_RPC_URL = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")

# --- DexScreener (free, no key) ----------------------------------------
DEXSCREENER_BASE = os.getenv("DEXSCREENER_BASE", "https://api.dexscreener.com")

# --- Files / storage ----------------------------------------------------
WALLETS_FILE = Path(os.getenv("WALLETS_FILE", BASE_DIR / "wallets.json"))
DB_PATH = Path(os.getenv("DB_PATH", BASE_DIR / "data.sqlite3"))

# --- Demo / offline mode ------------------------------------------------
# When 1, the dashboard is driven by fixture data run through the real
# analysis engine. Useful for offline/testing or when the host network
# blocks egress to Solana RPC / DexScreener.  export DEMO_MODE=1
DEMO_MODE = os.getenv("DEMO_MODE", "0") in ("1", "true", "True")

# --- Background polling (live activity feed) ----------------------------
# When enabled (and not in DEMO_MODE), a scheduler snapshots wallet holdings
# every POLL_INTERVAL_SECONDS and records new buys/adds/exits to the feed.
POLL_ENABLED = os.getenv("POLL_ENABLED", "1") in ("1", "true", "True")
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "300"))

# --- Behaviour tuning ---------------------------------------------------
# How long (seconds) cached coin analysis stays fresh before re-fetching.
COIN_CACHE_TTL = int(os.getenv("COIN_CACHE_TTL", "120"))
# Ignore token balances below this USD value to cut noise/dust.
MIN_HOLDING_USD = float(os.getenv("MIN_HOLDING_USD", "5"))
# Max concurrent outbound requests to avoid tripping free rate limits.
MAX_CONCURRENCY = int(os.getenv("MAX_CONCURRENCY", "5"))
# Per-request HTTP timeout (seconds).
HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "20"))

# Well-known mints we never treat as "tracked coins" (stables / SOL).
IGNORED_MINTS = {
    "So11111111111111111111111111111111111111112",  # wrapped SOL
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",  # USDT
}
