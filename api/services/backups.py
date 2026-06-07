"""Backup engine: RCON-coordinated tar.gz archives + retention pruning.

Hot backups pause autosave (save-off), force a flush (save-all flush), archive,
then always re-enable autosave. Archives live under data/backups/<instance>/ and
exclude logs/. Retention pruning only ever deletes scheduled/pre_restore backups.
"""

import shutil
import tarfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlmodel import Session, select

from api import paths
from api.config import settings
from api.models.backup import Backup
from api.models.instance import InstanceCreate, Loader, ServerInstance
from api.services import console, docker_manager, instances

EXCLUDE = {"logs"}  # top-level instance-dir entries left out of archives
SAVE_TIMEOUT = 120  # save-all flush can take a while on big worlds
PRUNABLE_KINDS = ("scheduled", "pre_restore")


def backup_path(backup: Backup) -> Path:
    return settings.backups_dir / backup.filename


def host_backup_path(backup: Backup) -> Path:
    """The archive's path as the HOST sees it (for humans inspecting files —
    a containerized manager's own view would be /app/data/...)."""
    return settings.resolved_host_data_dir / "backups" / backup.filename


def list_backups(session: Session, instance_id: int | None = None) -> list[Backup]:
    query = select(Backup).order_by(Backup.created_at.desc())  # type: ignore[attr-defined]
    if instance_id is not None:
        query = query.where(Backup.instance_id == instance_id)
    return list(session.exec(query).all())


def create_backup(
    session: Session, instance: ServerInstance, kind: str = "manual", note: str = ""
) -> Backup:
    if docker_manager.status(instance) == "running":
        with console.run_command(instance, timeout=SAVE_TIMEOUT) as rcon:
            rcon.command("save-off")
            try:
                rcon.command("save-all flush")
                archive = _archive(instance, kind)
            finally:
                rcon.command("save-on")
    else:
        archive = _archive(instance, kind)

    backup = Backup(
        instance_id=instance.id,
        instance_name=instance.name,
        mc_version=instance.mc_version,
        loader=instance.loader,
        loader_version=instance.loader_version,
        java_major=instance.java_major,
        server_jar=instance.server_jar,
        memory=instance.memory,
        jvm_flags=instance.jvm_flags,
        filename=str(archive.relative_to(settings.backups_dir)),
        size_bytes=archive.stat().st_size,
        kind=kind,
        note=note,
    )
    session.add(backup)
    session.commit()
    session.refresh(backup)
    return backup


def delete_backup(session: Session, backup: Backup) -> None:
    backup_path(backup).unlink(missing_ok=True)
    session.delete(backup)
    session.commit()


def prune(session: Session, instance: ServerInstance) -> list[Backup]:
    """Apply the instance's retention policy. Manual backups are never pruned."""
    prunable = [
        b
        for b in list_backups(session, instance.id)  # newest first
        if b.kind in PRUNABLE_KINDS
    ]
    doomed: dict[int, Backup] = {}
    if instance.backup_keep_count > 0:
        for b in prunable[instance.backup_keep_count :]:
            doomed[b.id] = b
    if instance.backup_keep_days > 0:
        cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(
            days=instance.backup_keep_days
        )
        for b in prunable:
            if b.created_at < cutoff:
                doomed[b.id] = b
    for b in doomed.values():
        delete_backup(session, b)
    return list(doomed.values())


def extract_backup(backup: Backup, dest: Path) -> None:
    """Extract an archive into a (cleared-by-caller or fresh) instance dir."""
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(backup_path(backup), "r:gz") as tar:
        tar.extractall(dest, filter="data")  # "data" filter blocks path escapes


def restore_backup(session: Session, backup: Backup, instance: ServerInstance) -> Backup:
    """Restore an archive over its instance. Stops the server first (restarting
    after if it was running) and takes a pre_restore safety backup. Returns the
    safety backup. Instance provisioning fields are synced to the snapshot so
    the row matches the restored jar/world."""
    was_running = docker_manager.status(instance) == "running"
    if was_running:
        docker_manager.stop(instance)
    safety = create_backup(
        session, instance, kind="pre_restore", note=f"auto, before restoring backup {backup.id}"
    )

    target = paths.instance_dir(instance.name)
    shutil.rmtree(target, ignore_errors=True)
    extract_backup(backup, target)

    instance.mc_version = backup.mc_version
    instance.loader = Loader(backup.loader)
    instance.loader_version = backup.loader_version
    instance.java_major = backup.java_major
    instance.server_jar = backup.server_jar
    session.add(instance)
    session.commit()

    # Config (image/env) may have changed with the snapshot — rebuild container.
    docker_manager.remove_container(instance)
    if was_running:
        instances.start_instance(instance)
    session.refresh(safety)  # un-expire after the instance-sync commit (else {} serialized)
    return safety


def clone_backup(session: Session, backup: Backup, name: str) -> ServerInstance:
    """Spin up a NEW instance (fresh ports/RCON password) from a backup. Works
    for orphaned backups too. Not started automatically."""
    instance = instances.create_instance(
        session,
        InstanceCreate(
            name=name,
            mc_version=backup.mc_version,
            loader=Loader(backup.loader),
            loader_version=backup.loader_version,
            memory=backup.memory,
            jvm_flags=backup.jvm_flags,
        ),
    )
    instance.java_major = backup.java_major
    instance.server_jar = backup.server_jar
    session.add(instance)
    session.commit()
    session.refresh(instance)
    extract_backup(backup, paths.instance_dir(instance.name))
    # Old rcon.password sits in the extracted server.properties; apply_managed
    # re-asserts the new instance's secrets before every start.
    return instance


def _archive(instance: ServerInstance, kind: str) -> Path:
    src = paths.instance_dir(instance.name)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    dest = settings.backups_dir / instance.name / f"{stamp}-{kind}.tar.gz"
    dest.parent.mkdir(parents=True, exist_ok=True)
    n = 2
    while dest.exists():  # same-second collision
        dest = dest.with_name(f"{stamp}-{kind}-{n}.tar.gz")
        n += 1
    tmp = dest.with_suffix(".part")
    with tarfile.open(tmp, "w:gz") as tar:
        for entry in sorted(src.iterdir()):
            if entry.name in EXCLUDE:
                continue
            tar.add(entry, arcname=entry.name)
    tmp.replace(dest)
    return dest
