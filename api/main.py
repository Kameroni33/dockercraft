from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.staticfiles import StaticFiles

from api.db import init_db
from api.routers import backups, mods, players, servers, system, versions
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
    api.include_router(system.router)
    api.include_router(servers.router)
    api.include_router(versions.router)
    api.include_router(players.router)
    api.include_router(backups.router)
    api.include_router(mods.router)
    app.include_router(api)
    # Built Vue app (hash routing, so plain static serving suffices). In dev the
    # vite server proxies /api here instead.
    if WEB_DIST.is_dir():
        app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="ui")
    return app


app = create_app()
