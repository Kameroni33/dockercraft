"""Version discovery for the setup wizard/UI."""

from fastapi import APIRouter, HTTPException

from api.clients import fabric, mojang

router = APIRouter(prefix="/versions", tags=["versions"])


@router.get("/minecraft")
def minecraft_versions(type: str | None = "release") -> list[dict]:
    """Available MC versions, newest first. type=release|snapshot|None for all."""
    versions = mojang.list_versions()
    if type:
        versions = [v for v in versions if v["type"] == type]
    return [{"id": v["id"], "type": v["type"], "releaseTime": v["releaseTime"]} for v in versions]


@router.get("/fabric/{mc_version}")
def fabric_loaders(mc_version: str) -> list[dict]:
    loaders = fabric.loader_versions(mc_version)
    if not loaders:
        raise HTTPException(404, f"no Fabric loaders for MC {mc_version}")
    return loaders
