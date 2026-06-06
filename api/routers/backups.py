from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.db import SessionDep
from api.models.backup import Backup
from api.models.instance import InstanceRead
from api.services import backups, docker_manager, instances

router = APIRouter(tags=["backups"])


class BackupCreate(BaseModel):
    note: str = ""


class BackupPolicy(BaseModel):
    enabled: bool
    interval_hours: int = Field(default=6, ge=1)
    keep_count: int = Field(default=10, ge=0)  # 0 = unlimited
    keep_days: int = Field(default=0, ge=0)


def _instance_or_404(session, instance_id: int):
    instance = instances.get_instance(session, instance_id)
    if instance is None:
        raise HTTPException(404, f"instance {instance_id} not found")
    return instance


def _backup_or_404(session, backup_id: int) -> Backup:
    backup = session.get(Backup, backup_id)
    if backup is None:
        raise HTTPException(404, f"backup {backup_id} not found")
    return backup


@router.get("/servers/{instance_id}/backups", response_model=list[Backup])
def list_for_instance(instance_id: int, session: SessionDep):
    _instance_or_404(session, instance_id)
    return backups.list_backups(session, instance_id)


@router.post("/servers/{instance_id}/backups", response_model=Backup, status_code=201)
def create_backup(instance_id: int, body: BackupCreate, session: SessionDep):
    instance = _instance_or_404(session, instance_id)
    return backups.create_backup(session, instance, kind="manual", note=body.note)


@router.put("/servers/{instance_id}/backup-policy")
def set_policy(instance_id: int, policy: BackupPolicy, session: SessionDep) -> dict:
    instance = _instance_or_404(session, instance_id)
    instance.backup_enabled = policy.enabled
    instance.backup_interval_hours = policy.interval_hours
    instance.backup_keep_count = policy.keep_count
    instance.backup_keep_days = policy.keep_days
    session.add(instance)
    session.commit()
    pruned = backups.prune(session, instance)  # apply tighter policy immediately
    return {"policy": policy.model_dump(), "pruned": len(pruned)}


@router.get("/backups", response_model=list[Backup])
def list_all(session: SessionDep):
    """Every backup, including those whose instance no longer exists."""
    return backups.list_backups(session)


@router.delete("/backups/{backup_id}", status_code=204)
def delete_backup(backup_id: int, session: SessionDep):
    backups.delete_backup(session, _backup_or_404(session, backup_id))


class CloneBody(BaseModel):
    name: str


@router.post("/backups/{backup_id}/restore", response_model=Backup)
def restore_backup(backup_id: int, session: SessionDep):
    """Restore in place. Returns the automatic pre_restore safety backup."""
    backup = _backup_or_404(session, backup_id)
    if backup.instance_id is None:
        raise HTTPException(
            409, "backup's instance no longer exists — use /clone to make a new one"
        )
    instance = _instance_or_404(session, backup.instance_id)
    return backups.restore_backup(session, backup, instance)


@router.post("/backups/{backup_id}/clone", response_model=InstanceRead, status_code=201)
def clone_backup(backup_id: int, body: CloneBody, session: SessionDep):
    """Create a brand-new instance (fresh ports) from this backup."""
    backup = _backup_or_404(session, backup_id)
    try:
        instance = backups.clone_backup(session, backup, body.name)
    except instances.InvalidNameError as e:
        raise HTTPException(422, str(e)) from e
    except instances.DuplicateNameError as e:
        raise HTTPException(409, str(e)) from e
    return InstanceRead(**instance.model_dump(), status=docker_manager.status(instance))
