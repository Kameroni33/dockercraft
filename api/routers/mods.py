from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.clients import modrinth
from api.db import SessionDep
from api.models.mod import InstalledMod
from api.services import docker_manager, instances, mods

router = APIRouter(tags=["mods"])


class ModInstall(BaseModel):
    project: str  # Modrinth slug or id
    version_id: str | None = None  # None -> newest compatible


class ModPatch(BaseModel):
    enabled: bool | None = None
    auto_update: bool | None = None


def _instance_or_404(session, instance_id: int):
    instance = instances.get_instance(session, instance_id)
    if instance is None:
        raise HTTPException(404, f"instance {instance_id} not found")
    return instance


def _mod_or_404(session, instance, project_id: str) -> InstalledMod:
    mod = mods.get_mod(session, instance, project_id)
    if mod is None:
        raise HTTPException(404, f"mod {project_id!r} is not installed on {instance.name!r}")
    return mod


@router.get("/mods/search")
def search_mods(
    query: str, mc_version: str | None = None, loader: str = "fabric", limit: int = 20
) -> list[dict]:
    """Modrinth search, pre-filtered to compatible mods. For the UI/browse flow."""
    hits = modrinth.search(query, loader=loader, mc_version=mc_version, limit=limit)
    return [
        {
            "project_id": h["project_id"],
            "slug": h["slug"],
            "title": h["title"],
            "description": h["description"],
            "downloads": h["downloads"],
            "icon_url": h.get("icon_url"),
        }
        for h in hits
    ]


@router.get("/servers/{instance_id}/mods", response_model=list[InstalledMod])
def list_mods(instance_id: int, session: SessionDep):
    return mods.list_mods(session, _instance_or_404(session, instance_id))


@router.post("/servers/{instance_id}/mods", status_code=201)
def install_mod(instance_id: int, body: ModInstall, session: SessionDep) -> dict:
    instance = _instance_or_404(session, instance_id)
    try:
        installed = mods.install_mod(session, instance, body.project, body.version_id)
    except modrinth.ProjectNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except mods.LoaderUnsupportedError as e:
        raise HTTPException(409, str(e)) from e
    except mods.IncompatibleModError as e:
        raise HTTPException(422, str(e)) from e
    for m in installed:
        session.refresh(m)  # later commits expire earlier rows; un-expire before dump
    return {
        "installed": [m.model_dump() for m in installed],  # mod + any pulled-in deps
        "restart_required": docker_manager.status(instance) == "running",
    }


@router.delete("/servers/{instance_id}/mods/{project_id}", status_code=204)
def uninstall_mod(
    instance_id: int, project_id: str, session: SessionDep, force: bool = False
):
    instance = _instance_or_404(session, instance_id)
    mod = _mod_or_404(session, instance, project_id)
    try:
        mods.uninstall_mod(session, instance, mod, force=force)
    except mods.DependencyError as e:
        raise HTTPException(409, str(e)) from e


@router.patch("/servers/{instance_id}/mods/{project_id}", response_model=InstalledMod)
def patch_mod(instance_id: int, project_id: str, body: ModPatch, session: SessionDep):
    instance = _instance_or_404(session, instance_id)
    mod = _mod_or_404(session, instance, project_id)
    if body.enabled is not None:
        mods.set_enabled(instance, mod, body.enabled)
    if body.auto_update is not None:
        mod.auto_update = body.auto_update
    session.add(mod)
    session.commit()
    session.refresh(mod)
    return mod


@router.post("/servers/{instance_id}/mods/check-updates")
def check_updates(instance_id: int, session: SessionDep) -> list[dict]:
    return mods.check_updates(session, _instance_or_404(session, instance_id))


@router.post("/servers/{instance_id}/mods/{project_id}/update")
def update_mod(instance_id: int, project_id: str, session: SessionDep) -> dict:
    instance = _instance_or_404(session, instance_id)
    mod = _mod_or_404(session, instance, project_id)
    changed = mods.update_mod(session, instance, mod)
    return {
        "updated": changed,
        "version": mod.version_number,
        "restart_required": changed and docker_manager.status(instance) == "running",
    }
