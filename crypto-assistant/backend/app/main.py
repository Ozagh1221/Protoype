"""FastAPI entrypoint: REST API + serves the dashboard frontend."""
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import config, db
from .services import demo, tracker

app = FastAPI(title="Crypto Investment Assistant", version="0.1.0")

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


# --- Serve the dashboard ------------------------------------------------
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(FRONTEND_DIR / "index.html")
