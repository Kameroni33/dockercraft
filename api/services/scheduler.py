"""Background jobs. One periodic sweep derives due work from the DB, so there is
no per-instance job state to lose across manager restarts."""

import logging
from datetime import UTC, datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from sqlmodel import Session, select

from api.db import get_engine
from api.models.backup import Backup
from api.models.instance import ServerInstance
from api.services import backups, docker_manager

logger = logging.getLogger("dockercraft.scheduler")

SWEEP_MINUTES = 5
MOD_UPDATE_SWEEP_HOURS = 6

_scheduler: BackgroundScheduler | None = None


def run_due_backups(session: Session, now: datetime | None = None) -> list[Backup]:
    """Back up every enabled+running instance whose interval has elapsed."""
    now = now or datetime.now(UTC).replace(tzinfo=None)
    created = []
    enabled = session.exec(
        select(ServerInstance).where(ServerInstance.backup_enabled)
    ).all()
    for instance in enabled:
        if docker_manager.status(instance) != "running":
            continue  # nothing changes while stopped; manual backups still work
        last = session.exec(
            select(Backup)
            .where(Backup.instance_id == instance.id, Backup.kind == "scheduled")
            .order_by(Backup.created_at.desc())  # type: ignore[attr-defined]
        ).first()
        due = last is None or now - last.created_at >= timedelta(
            hours=instance.backup_interval_hours
        )
        if not due:
            continue
        try:
            created.append(backups.create_backup(session, instance, kind="scheduled"))
            pruned = backups.prune(session, instance)
            logger.info(
                "scheduled backup of %r done (%d pruned)", instance.name, len(pruned)
            )
        except Exception:
            logger.exception("scheduled backup of %r failed", instance.name)
    return created


def run_mod_updates(session: Session) -> list[str]:
    """Update every auto_update mod to its newest compatible version. Updated
    files take effect on the next restart — we never bounce servers ourselves."""
    from sqlmodel import col

    from api.models.mod import InstalledMod
    from api.services import mods

    updated = []
    auto_mods = session.exec(
        select(InstalledMod).where(col(InstalledMod.auto_update))
    ).all()
    for mod in auto_mods:
        instance = session.get(ServerInstance, mod.instance_id)
        if instance is None:
            continue
        try:
            if mods.update_mod(session, instance, mod):
                updated.append(f"{instance.name}:{mod.slug}@{mod.version_number}")
                logger.info("auto-updated %s on %r to %s",
                            mod.slug, instance.name, mod.version_number)
        except Exception:
            logger.exception("auto-update of %s on %r failed", mod.slug, instance.name)
    return updated


def _sweep() -> None:
    with Session(get_engine()) as session:
        run_due_backups(session)


def _mod_sweep() -> None:
    with Session(get_engine()) as session:
        run_mod_updates(session)


def start() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(_sweep, "interval", minutes=SWEEP_MINUTES, id="backup-sweep")
    _scheduler.add_job(
        _mod_sweep, "interval", hours=MOD_UPDATE_SWEEP_HOURS, id="mod-update-sweep"
    )
    _scheduler.start()


def shutdown() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
