"""FastAPI entrypoint: REST API + serves the dashboard frontend."""
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import config, db
from .services import demo, poller, tracker, xtrack

app = FastAPI(title="Crypto Investment Assistant", version="0.1.0")
_scheduler = None

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = config.REPO_DIR / "frontend"


@app.on_event("startup")
def _startup() -> None:
    db.init_db()
    # Start the background poller for the live activity feed (live mode only).
    global _scheduler
    if config.POLL_ENABLED and not config.DEMO_MODE:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler

        _scheduler = AsyncIOScheduler()
        _scheduler.add_job(
            poller.poll_once,
            "interval",
            seconds=config.POLL_INTERVAL_SECONDS,
            next_run_time=None,  # first run after one interval; avoids startup spike
            id="poll_wallets",
            max_instances=1,
        )
        _scheduler.start()


@app.on_event("shutdown")
def _shutdown() -> None:
    if _scheduler:
        _scheduler.shutdown(wait=False)


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "rpc": config.SOLANA_RPC_URL, "demo_mode": config.DEMO_MODE}


@app.get("/api/wallets")
async def list_wallets() -> dict:
    return {"wallets": tracker.load_wallets()}


@app.get("/api/overview")
async def overview() -> dict:
    """Full dashboard payload: wallets, their analysed coins, shared-coin rollup."""
    if config.DEMO_MODE:
        return demo.build_overview()
    try:
        return await tracker.build_overview()
    except Exception as e:  # surface a clean error to the dashboard
        raise HTTPException(status_code=502, detail=f"Failed to build overview: {e}")


@app.get("/api/activity")
async def activity(limit: int = 100) -> dict:
    """Recent position changes across all tracked wallets (live feed)."""
    if config.DEMO_MODE:
        return {"activity": demo.build_activity()}
    return {"activity": db.get_recent_activity(limit)}


@app.get("/api/coin")
async def coin_lookup(q: str) -> dict:
    """On-demand market data + risk analysis for any coin by mint or symbol."""
    result = demo.lookup_coin(q) if config.DEMO_MODE else await tracker.lookup_coin(q)
    if not result:
        raise HTTPException(status_code=404, detail=f"No Solana coin found for '{q}'")
    return result


@app.get("/api/accounts")
async def accounts() -> dict:
    """Tracked X accounts with recent posts + sentiment (provider-dependent)."""
    return await xtrack.build_accounts_view()


@app.post("/api/poll")
async def trigger_poll() -> dict:
    """Manually run a polling cycle now (useful between scheduled runs)."""
    if config.DEMO_MODE:
        return {"recorded": 0, "demo": True}
    recorded = await poller.poll_once()
    return {"recorded": recorded}


# --- Serve the dashboard ------------------------------------------------
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(FRONTEND_DIR / "index.html")
