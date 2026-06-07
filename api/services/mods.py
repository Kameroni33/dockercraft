"""Mod management: install (with recursive required-dependency resolution),
toggle, uninstall, and update checks against Modrinth."""

import json
from pathlib import Path

from sqlmodel import Session, select

from api import paths
from api.clients import modrinth
from api.models.instance import Loader, ServerInstance
from api.models.mod import InstalledMod


class ModError(Exception):
    pass


class LoaderUnsupportedError(ModError):
    pass


class IncompatibleModError(ModError):
    pass


class DependencyError(ModError):
    pass


def mods_dir(instance: ServerInstance) -> Path:
    return paths.instance_dir(instance.name) / "mods"


def mod_file(instance: ServerInstance, mod: InstalledMod) -> Path:
    name = mod.filename if mod.enabled else f"{mod.filename}.disabled"
    return mods_dir(instance) / name


def list_mods(session: Session, instance: ServerInstance) -> list[InstalledMod]:
    return list(
        session.exec(
            select(InstalledMod)
            .where(InstalledMod.instance_id == instance.id)
            .order_by(InstalledMod.title)
        ).all()
    )


def get_mod(session: Session, instance: ServerInstance, project_id: str) -> InstalledMod | None:
    return session.exec(
        select(InstalledMod).where(
            InstalledMod.instance_id == instance.id, InstalledMod.project_id == project_id
        )
    ).first()


def install_mod(
    session: Session,
    instance: ServerInstance,
    id_or_slug: str,
    version_id: str | None = None,
    _dependency_of: str | None = None,
) -> list[InstalledMod]:
    """Install a mod (newest compatible version unless pinned) plus its required
    dependencies. Returns everything newly installed."""
    if instance.loader != Loader.FABRIC:
        raise LoaderUnsupportedError(
            f"mods require a fabric instance; {instance.name!r} is {instance.loader}"
        )

    project = modrinth.get_project(id_or_slug)
    if (existing := get_mod(session, instance, project["id"])) is not None:
        if _dependency_of and existing.dependency_of is None:
            return []  # already explicitly installed; nothing to do
        return []

    versions = modrinth.get_versions(project["id"], "fabric", instance.mc_version)
    if not versions:
        raise IncompatibleModError(
            f"{project['title']!r} has no fabric build for MC {instance.mc_version}"
        )
    version = versions[0]
    if version_id is not None:
        version = next((v for v in versions if v["id"] == version_id), None)
        if version is None:
            raise IncompatibleModError(
                f"version {version_id!r} of {project['title']!r} is not compatible "
                f"with fabric/{instance.mc_version}"
            )

    required = [
        dep["project_id"]
        for dep in version.get("dependencies", [])
        if dep.get("dependency_type") == "required" and dep.get("project_id")
    ]
    installed: list[InstalledMod] = []
    # Required deps first, so a failed dep aborts before we write the mod itself.
    for dep_id in required:
        installed += install_mod(session, instance, dep_id, _dependency_of=project["id"])

    file_info = modrinth.primary_file(version)
    modrinth.download_file(file_info, mods_dir(instance) / file_info["filename"])

    mod = InstalledMod(
        instance_id=instance.id,
        project_id=project["id"],
        slug=project["slug"],
        title=project["title"],
        version_id=version["id"],
        version_number=version["version_number"],
        filename=file_info["filename"],
        dependency_of=_dependency_of,
        requires_json=json.dumps(required),
    )
    session.add(mod)
    session.commit()
    session.refresh(mod)
    installed.append(mod)
    return installed


def uninstall_mod(
    session: Session, instance: ServerInstance, mod: InstalledMod, force: bool = False
) -> None:
    """Remove a mod's file + record. Refuses (without force) to remove a mod that
    another installed mod requires."""
    dependents = [
        m
        for m in list_mods(session, instance)
        if m.id != mod.id and mod.project_id in json.loads(m.requires_json)
    ]
    if dependents and not force:
        names = ", ".join(m.title for m in dependents)
        raise DependencyError(
            f"{mod.title!r} is a required dependency of: {names}. "
            "Remove those first or pass force=true"
        )
    mod_file(instance, mod).unlink(missing_ok=True)
    session.delete(mod)
    session.commit()


def set_enabled(instance: ServerInstance, mod: InstalledMod, enabled: bool) -> None:
    if mod.enabled == enabled:
        return
    current = mod_file(instance, mod)
    mod.enabled = enabled
    current.rename(mod_file(instance, mod))


def check_updates(session: Session, instance: ServerInstance) -> list[dict]:
    """Newer compatible versions for installed mods (all of them, not just auto)."""
    updates = []
    for mod in list_mods(session, instance):
        versions = modrinth.get_versions(mod.project_id, "fabric", instance.mc_version)
        if versions and versions[0]["id"] != mod.version_id:
            updates.append(
                {
                    "project_id": mod.project_id,
                    "title": mod.title,
                    "installed": mod.version_number,
                    "available": versions[0]["version_number"],
                    "available_version_id": versions[0]["id"],
                    "auto_update": mod.auto_update,
                }
            )
    return updates


def update_mod(session: Session, instance: ServerInstance, mod: InstalledMod) -> bool:
    """Move a mod to the newest compatible version. True if anything changed."""
    versions = modrinth.get_versions(mod.project_id, "fabric", instance.mc_version)
    if not versions or versions[0]["id"] == mod.version_id:
        return False
    version = versions[0]
    file_info = modrinth.primary_file(version)
    was_enabled = mod.enabled
    old_file = mod_file(instance, mod)
    modrinth.download_file(file_info, mods_dir(instance) / file_info["filename"])
    old_file.unlink(missing_ok=True)
    mod.version_id = version["id"]
    mod.version_number = version["version_number"]
    mod.filename = file_info["filename"]
    mod.requires_json = json.dumps(
        [
            d["project_id"]
            for d in version.get("dependencies", [])
            if d.get("dependency_type") == "required" and d.get("project_id")
        ]
    )
    mod.enabled = True
    if not was_enabled:  # preserve disabled state with the new filename
        set_enabled(instance, mod, False)
    session.add(mod)
    session.commit()
    return True
