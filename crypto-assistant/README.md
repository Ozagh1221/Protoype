# Crypto Investment Assistant (Solana)

A web dashboard that gives an owner a full view over a set of tracked Solana
wallets: what coins each person holds, live market data for those coins, a
transparent **risk/scam score** per coin, and a cross-wallet **"shared coins"**
rollup that surfaces which narratives ("metas") the group is rotating into.

This is **Phase 1** of a larger roadmap (see below). It is built to run on
**free, keyless data sources** and to upgrade to paid providers later with
only environment-variable changes.

---

## What it does today

- **Wallet tracking** — reads a configurable list of wallets (`backend/wallets.json`)
  and fetches each one's SPL token holdings via Solana RPC.
- **Live coin data** — for every held coin, pulls price, market cap, liquidity,
  24h volume and price change from DexScreener (free, no key).
- **On-demand coin lookup** — search box (and `/api/coin?q=`) to analyse ANY
  Solana coin by mint or symbol, not just ones held by tracked wallets:
  resolves the symbol via DexScreener, then runs the full risk pipeline.
- **Risk / scam analysis** — a transparent, rule-based engine scores each coin
  0–100 from on-chain + market facts:
  - mint authority active? (supply can be inflated)
  - freeze authority active? (your tokens can be frozen)
  - top-10 holder concentration %
  - liquidity depth, token age, sharp price drops
  Each rule contributes points and a human-readable flag (🟢 ok / 🟡 / 🔴).
- **Shared-coins meta signal** — highlights coins held by more than one tracked
  wallet, an early indicator of the narrative the group is following.
- **Meta radar** — classifies each held coin into a narrative (AI/Agents, Dogs,
  Cats, Frogs/Pepe, Politics, …) via a transparent keyword classifier, then
  ranks which narratives the group is rotating into by wallet adoption, capital
  committed and 24h performance — your "which meta is hot right now" view.
- **Deeper scam scan (RugCheck)** — each coin is optionally enriched with a
  RugCheck report (LP lock/burn, named risks, rugged flag). It's a best-effort
  enricher: if unreachable, the coin still gets full native analysis.
- **Consolidated alerts** — a top-of-dashboard panel lifting every tracked
  wallet that currently holds a high-risk or rugged coin, biggest exposure first.
- **Live activity feed** — a background poller snapshots holdings on a schedule,
  diffs each snapshot against the last, and records position changes
  (🟢 new buy, ➕ add, ➖ reduce, 🔴 exit) into a feed. Entering/exiting a
  position — and any buy of a high-risk coin — is flagged as an **alert**.
- **X account tracking (scaffold)** — tracks an X handle per person (linked to
  their wallet) and shows recent posts with keyword sentiment, via a pluggable
  provider. See the note below: reading X requires a paid provider, so the
  default provider is `none` and a `demo` provider previews the UI.

---

## Architecture

```
Frontend (vanilla JS dashboard)
   │  GET /api/overview
Backend (FastAPI)
   ├─ services/tracker.py    orchestrates wallets → holdings → coin analysis
   ├─ services/solana.py     Solana JSON-RPC client (holdings, authorities, holders)
   ├─ services/dexscreener.py live price / market cap / liquidity
   ├─ services/analysis.py   rule-based risk/scam scoring
   ├─ services/poller.py     background snapshot + diff -> activity feed
   ├─ services/demo.py       offline fixture data (DEMO_MODE)
   └─ db.py                  SQLite: coin cache + holdings snapshots + activity
   (APScheduler runs poller.poll_once every POLL_INTERVAL_SECONDS in live mode)
```

---

## Quick start

```bash
cd crypto-assistant/backend
pip install -r requirements.txt

# Option A: offline demo (no network needed) — great for trying the UI
DEMO_MODE=1 uvicorn app.main:app --port 8000

# Option B: live data (requires outbound access to Solana RPC + DexScreener)
uvicorn app.main:app --port 8000
```

Then open <http://127.0.0.1:8000>.

### Configure tracked wallets

Edit `backend/wallets.json`:

```json
{
  "wallets": [
    { "label": "Person Name", "address": "<solana-wallet-address>", "notes": "" }
  ]
}
```

Add your 20–50 targets here. `label` is the person/owner shown in the dashboard.

### Environment variables

| Var | Default | Purpose |
|-----|---------|---------|
| `DEMO_MODE` | `0` | `1` = serve fixture data through the real analysis engine |
| `SOLANA_RPC_URL` | public mainnet | Swap to a free Helius/QuickNode URL for higher rate limits |
| `DEXSCREENER_BASE` | dexscreener.com | Market-data base URL |
| `WALLETS_FILE` | `backend/wallets.json` | Path to tracked-wallet config |
| `COIN_CACHE_TTL` | `120` | Seconds before cached coin analysis is refreshed |
| `MIN_HOLDING_USD` | `5` | Hide holdings below this USD value (dust) |
| `MAX_CONCURRENCY` | `5` | Cap concurrent outbound requests (free rate limits) |
| `POLL_ENABLED` | `1` | Run the background poller that builds the live activity feed |
| `POLL_INTERVAL_SECONDS` | `300` | How often to snapshot holdings and diff for changes |
| `X_PROVIDER` | `none` | X post source: `none`, `demo`, or a paid provider you add |
| `X_ACCOUNTS_FILE` | `backend/x_accounts.json` | Tracked X handles, linked to people |

### API endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/overview` | Wallets, analysed coins, alerts, meta radar, shared coins |
| `GET /api/coin?q=<mint or symbol>` | On-demand market data + risk analysis for any coin |
| `GET /api/activity?limit=100` | Recent position changes (live feed) |
| `GET /api/accounts` | Tracked X accounts + recent posts/sentiment |
| `POST /api/poll` | Trigger a polling cycle immediately (live mode) |
| `GET /api/health` | Status + whether demo mode is on |

---

## Note on data access / network policy

The public Solana RPC (`api.mainnet-beta.solana.com`) and DexScreener may be
unreachable from restricted environments (e.g. a Claude Code web session whose
network policy only allows package registries — both return `403` there). Run
the app **locally** or in an environment that permits egress to those hosts for
live data. `DEMO_MODE=1` works anywhere and exercises the full UI + scoring
pipeline offline. For production, point `SOLANA_RPC_URL` at a (free-tier) Helius
key to avoid public-RPC rate limits.

---

## Roadmap

1. **Wallet tracking + coin analysis** ✅
2. **Live activity feed + scheduled polling** ✅ — snapshots holdings and diffs
   them into a feed of new buys / adds / reduces / exits, with alerts.
   *(Next within this phase: push notifications to phone/Telegram.)*
3. **Deeper scam detection + alerts** ✅ — RugCheck enrichment (LP lock, named
   risks, rugged flag) and a consolidated alerts panel. *(Next: bundler/sniper
   detection and holder-graph analysis for bot clusters.)*
4. **Meta radar** ✅ — classifies holdings into named narratives and ranks what
   the group is rotating into. *(Next: trend metas over time using activity.)*
5. **X / Twitter account tracking** 🟡 *scaffold done* — per-person account
   tracking, posts + sentiment, pluggable provider. **Blocked on a data source:**
   X's free tier can't read posts, so live X needs a paid provider (official
   Basic, twitterapi.io, Apify, …). Wire one into `services/xtrack.py`.

---

*Risk scoring is heuristic and informational — not financial advice.*
