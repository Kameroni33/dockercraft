from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI
from fastapi.staticfiles import StaticFiles

from api.db import init_db
from api.routers import auth, backups, mods, players, servers, system, versions
from api.routers.auth import require_auth
from api.services import scheduler

WEB_DIST = Path(__file__).resolve().parents[1] / "web" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    scheduler.start()
    yield
    scheduler.shutdown()


def create_app() -> FastAPI:
    app = FastAPI(title="dockercraft", lifespan=lifespan)
    api = APIRouter(prefix="/api")
    api.include_router(auth.router)  # login/setup/status stay reachable unauthenticated
    api.include_router(system.router)  # /health open for monitoring
    protected = APIRouter(dependencies=[Depends(require_auth)])
    protected.include_router(system.protected_router)  # /addresses
    protected.include_router(servers.router)
    protected.include_router(versions.router)
    protected.include_router(players.router)
    protected.include_router(backups.router)
    protected.include_router(mods.router)
    api.include_router(protected)
    app.include_router(api)
    # Built Vue app (hash routing, so plain static serving suffices). In dev the
    # vite server proxies /api here instead.
    if WEB_DIST.is_dir():
        app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="ui")
    return app


app = create_app()
