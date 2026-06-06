from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.db import init_db
from api.routers import backups, players, servers, system, versions


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="dockercraft", lifespan=lifespan)
    app.include_router(system.router)
    app.include_router(servers.router)
    app.include_router(versions.router)
    app.include_router(players.router)
    app.include_router(backups.router)
    return app


app = create_app()
