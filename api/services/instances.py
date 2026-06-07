"""Instance CRUD orchestration: DB records + data dirs + containers."""

import json
import re
import shutil

from sqlmodel import Session, select

from api import paths
from api.models.instance import InstanceCreate, ServerInstance
from api.services import docker_manager, mc_config, ports

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")


class InvalidNameError(ValueError):
    pass


class DuplicateNameError(ValueError):
    pass


class NoBedrockPortError(ValueError):
    pass


class LanDiscoveryConflictError(ValueError):
    pass


def get_instance(session: Session, instance_id: int) -> ServerInstance | None:
    return session.get(ServerInstance, instance_id)


def list_instances(session: Session) -> list[ServerInstance]:
    return list(session.exec(select(ServerInstance).order_by(ServerInstance.id)).all())


def create_instance(session: Session, data: InstanceCreate) -> ServerInstance:
    """Create the DB record + data dir. Provisioning (jar/loader install) is a
    separate step — see the setup flow."""
    if not NAME_RE.match(data.name):
        raise InvalidNameError(
            "name must be a lowercase slug: [a-z0-9-], starting alphanumeric, max 41 chars"
        )
    existing = session.exec(select(ServerInstance).where(ServerInstance.name == data.name)).first()
    if existing is not None:
        raise DuplicateNameError(f"instance {data.name!r} already exists")

    game_port, rcon_port = ports.allocate_ports(session)
    instance = ServerInstance(
        **data.model_dump(),
        game_port=game_port,
        rcon_port=rcon_port,
    )
    session.add(instance)
    session.commit()
    session.refresh(instance)
    paths.instance_dir(instance.name).mkdir(parents=True, exist_ok=True)
    return instance


def delete_instance(session: Session, instance: ServerInstance, delete_data: bool = False) -> None:
    docker_manager.remove_container(instance)
    if delete_data:
        shutil.rmtree(paths.instance_dir(instance.name), ignore_errors=True)
    # Backups outlive the instance — orphan them instead of cascading.
    from api.models.backup import Backup
    from api.models.mod import InstalledMod

    for backup in session.exec(select(Backup).where(Backup.instance_id == instance.id)).all():
        backup.instance_id = None
        session.add(backup)
    for mod in session.exec(
        select(InstalledMod).where(InstalledMod.instance_id == instance.id)
    ).all():
        session.delete(mod)
    session.delete(instance)
    session.commit()


def start_instance(instance: ServerInstance) -> None:
    """Start = re-assert managed properties (RCON config etc.), then start container."""
    mc_config.apply_managed(instance)
    docker_manager.start(instance)


def set_lan_discovery(session: Session, instance: ServerInstance, enabled: bool) -> None:
    """Toggle the phantom sidecar (console LAN discovery) for this instance.

    Enabling moves the instance's Bedrock host port out of 19132 if needed —
    phantom must own UDP 19132 to hear console discovery broadcasts. Disabling
    keeps the remapped port (harmless, and reverting would force another
    container recreate that could re-conflict)."""
    if not enabled:
        instance.lan_discovery = False
        session.add(instance)
        session.commit()
        docker_manager.remove_phantom(instance)
        return

    if docker_manager.bedrock_host_port(instance) is None:
        raise NoBedrockPortError(
            "instance has no Bedrock port mapping — set up Geyser (cross-platform) first"
        )
    other = session.exec(
        select(ServerInstance).where(
            ServerInstance.lan_discovery == True,  # noqa: E712 — SQL expression
            ServerInstance.id != instance.id,
        )
    ).first()
    if other is not None:
        raise LanDiscoveryConflictError(
            f"LAN discovery is already enabled on {other.name!r} — "
            "only one server per host can own discovery port 19132"
        )

    if docker_manager.bedrock_host_port(instance) == docker_manager.BEDROCK_PORT:
        new_port = ports.allocate_bedrock_remap_port(session)
        extras = json.loads(instance.extra_ports_json)
        for extra in extras:
            if extra.get("proto") == "udp" and extra["container"] == docker_manager.BEDROCK_PORT:
                extra["host"] = new_port
        instance.extra_ports_json = json.dumps(extras)
        session.add(instance)
        session.commit()
        # Replace the MC container so docker releases host 19132 for phantom.
        docker_manager.recreate_container(instance)

    instance.lan_discovery = True
    session.add(instance)
    session.commit()
    if docker_manager.status(instance) == "running":
        try:
            docker_manager.start_phantom(instance)
        except Exception:
            instance.lan_discovery = False  # don't claim a sidecar that isn't there
            session.add(instance)
            session.commit()
            raise
