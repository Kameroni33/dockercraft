"""Instance CRUD orchestration: DB records + data dirs + containers."""

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
    session.delete(instance)
    session.commit()


def start_instance(instance: ServerInstance) -> None:
    """Start = re-assert managed properties (RCON config etc.), then start container."""
    mc_config.apply_managed(instance)
    docker_manager.start(instance)
