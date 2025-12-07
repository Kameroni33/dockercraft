from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import logging

from routers import servers, backups, mods, console
from config import settings, setup_logging


setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    logger.info("Starting Dockercraft API...")
    yield
    logger.info("Shutting down Dockercraft API...")

app = FastAPI(
    title="Dockercraft API",
    description="Minecraft Server Management API",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(servers.router, prefix="/api/servers", tags=["servers"])
app.include_router(backups.router, prefix="/api/backups", tags=["backups"])
app.include_router(mods.router, prefix="/api/mods", tags=["mods"])
app.include_router(console.router, prefix="/ws", tags=["console"])

@app.get("/")
async def root():
    return {
        "message": "Dockercraft API",
        "version": "2.0.0",
        "docs": "/docs"
    }

@app.get("/api/health")
async def health():
    return {"status": "healthy"}
