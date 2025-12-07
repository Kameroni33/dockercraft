from fastapi import APIRouter, HTTPException
from typing import List
import httpx
import logging

from models import ModInfo, ModInstall

router = APIRouter()
logger = logging.getLogger(__name__)

MODRINTH_API = "https://api.modrinth.com/v2"

@router.get("/search", response_model=List[ModInfo])
async def search_mods(query: str, limit: int = 10):
    """Search mods on Modrinth"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{MODRINTH_API}/search",
                params={
                    "query": query,
                    "facets": '[["project_type:mod"]]',
                    "limit": limit
                }
            )
            response.raise_for_status()
            data = response.json()
            
            mods = []
            for hit in data.get("hits", []):
                mods.append(ModInfo(
                    slug=hit["slug"],
                    title=hit["title"],
                    description=hit["description"],
                    downloads=hit["downloads"],
                    icon_url=hit.get("icon_url"),
                    versions=[]  # Will be fetched separately
                ))
            
            return mods
    except Exception as e:
        logger.error(f"Failed to search mods: {e}")
        raise HTTPException(status_code=500, detail="Failed to search mods")

@router.get("/{mod_slug}/versions")
async def get_mod_versions(mod_slug: str):
    """Get available versions for a mod"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{MODRINTH_API}/project/{mod_slug}/version")
            response.raise_for_status()
            versions = response.json()
            
            return [{
                "id": v["id"],
                "version_number": v["version_number"],
                "name": v["name"],
                "game_versions": v["game_versions"],
                "loaders": v["loaders"]
            } for v in versions]
    except Exception as e:
        logger.error(f"Failed to get mod versions: {e}")
        raise HTTPException(status_code=500, detail="Failed to get mod versions")

@router.post("/install")
async def install_mod(mod: ModInstall):
    """Install mod to server"""
    # TODO: Implement mod installation
    return {"message": "Mod installation not yet implemented"}