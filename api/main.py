from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.db import init_db
from api.routers import backups, mods, players, servers, system, versions
from api.services import scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    scheduler.start()
    yield
    scheduler.shutdown()


def create_app() -> FastAPI:
    app = FastAPI(title="dockercraft", lifespan=lifespan)
    app.include_router(system.router)
    app.include_router(servers.router)
    app.include_router(versions.router)
    app.include_router(players.router)
    app.include_router(backups.router)
    app.include_router(mods.router)
    return app


app = create_app()
