from fastapi import APIRouter, HTTPException, WebSocket
from pydantic import BaseModel, Field
from sqlmodel import Session

from api.clients.rcon import RconError
from api.db import SessionDep
from api.models.instance import InstanceCreate, InstanceRead, ServerInstance
from api.services import console, docker_manager, instances, mc_config, players, provision, setup

router = APIRouter(prefix="/servers", tags=["servers"])


def _read(instance: ServerInstance) -> InstanceRead:
    return InstanceRead(**instance.model_dump(), status=docker_manager.status(instance))


def _get_or_404(session: Session, instance_id: int) -> ServerInstance:
    instance = instances.get_instance(session, instance_id)
    if instance is None:
        raise HTTPException(404, f"instance {instance_id} not found")
    return instance


@router.get("", response_model=list[InstanceRead])
def list_servers(session: SessionDep):
    return [_read(i) for i in instances.list_instances(session)]


@router.post("", response_model=InstanceRead, status_code=201)
def create_server(data: InstanceCreate, session: SessionDep):
    try:
        instance = instances.create_instance(session, data)
    except instances.InvalidNameError as e:
        raise HTTPException(422, str(e)) from e
    except instances.DuplicateNameError as e:
        raise HTTPException(409, str(e)) from e
    return _read(instance)


@router.post("/setup", response_model=InstanceRead, status_code=201)
def setup_server(req: setup.SetupRequest, session: SessionDep):
    """Full setup wizard: create + provision + EULA + properties + players, optional start."""
    try:
        instance = setup.setup_server(session, req)
    except provision.EulaNotAcceptedError as e:
        raise HTTPException(422, str(e)) from e
    except instances.InvalidNameError as e:
        raise HTTPException(422, str(e)) from e
    except instances.DuplicateNameError as e:
        raise HTTPException(409, str(e)) from e
    except players.UnknownPlayerError as e:
        raise HTTPException(422, str(e)) from e
    return _read(instance)


@router.get("/{instance_id}", response_model=InstanceRead)
def get_server(instance_id: int, session: SessionDep):
    return _read(_get_or_404(session, instance_id))


@router.delete("/{instance_id}", status_code=204)
def delete_server(instance_id: int, session: SessionDep, delete_data: bool = False):
    instances.delete_instance(session, _get_or_404(session, instance_id), delete_data)


@router.post("/{instance_id}/start", response_model=InstanceRead)
def start_server(instance_id: int, session: SessionDep):
    instance = _get_or_404(session, instance_id)
    instances.start_instance(instance)
    return _read(instance)


@router.post("/{instance_id}/stop", response_model=InstanceRead)
def stop_server(instance_id: int, session: SessionDep):
    instance = _get_or_404(session, instance_id)
    docker_manager.stop(instance)
    return _read(instance)


@router.post("/{instance_id}/restart", response_model=InstanceRead)
def restart_server(instance_id: int, session: SessionDep):
    instance = _get_or_404(session, instance_id)
    docker_manager.restart(instance)
    return _read(instance)


@router.get("/{instance_id}/properties")
def get_properties(instance_id: int, session: SessionDep) -> dict[str, str]:
    return mc_config.read_properties(_get_or_404(session, instance_id))


@router.patch("/{instance_id}/properties")
def patch_properties(instance_id: int, updates: dict, session: SessionDep) -> dict:
    instance = _get_or_404(session, instance_id)
    try:
        props = mc_config.update_properties(instance, updates)
    except mc_config.ManagedPropertyError as e:
        raise HTTPException(422, str(e)) from e
    # File changes only apply on (re)start — tell the caller if one is pending.
    return {"properties": props, "restart_required": docker_manager.status(instance) == "running"}


class PlayerBody(BaseModel):
    username: str
    level: int = Field(default=4, ge=1, le=4)  # op permission level, ops only


def _resolve_or_404(session: Session, username: str):
    try:
        return players.resolve(session, username)
    except players.UnknownPlayerError as e:
        raise HTTPException(404, str(e)) from e


@router.get("/{instance_id}/whitelist")
def get_whitelist(instance_id: int, session: SessionDep) -> list[dict]:
    return mc_config.read_whitelist(_get_or_404(session, instance_id))


@router.post("/{instance_id}/whitelist")
def add_to_whitelist(instance_id: int, body: PlayerBody, session: SessionDep) -> list[dict]:
    instance = _get_or_404(session, instance_id)
    player = _resolve_or_404(session, body.username)
    return mc_config.add_whitelist(instance, player.uuid, player.username)


@router.delete("/{instance_id}/whitelist/{username}", status_code=204)
def remove_from_whitelist(instance_id: int, username: str, session: SessionDep):
    if not mc_config.remove_whitelist(_get_or_404(session, instance_id), username):
        raise HTTPException(404, f"{username!r} is not on the whitelist")


@router.get("/{instance_id}/ops")
def get_ops(instance_id: int, session: SessionDep) -> list[dict]:
    return mc_config.read_ops(_get_or_404(session, instance_id))


@router.post("/{instance_id}/ops")
def add_to_ops(instance_id: int, body: PlayerBody, session: SessionDep) -> list[dict]:
    instance = _get_or_404(session, instance_id)
    player = _resolve_or_404(session, body.username)
    return mc_config.add_op(instance, player.uuid, player.username, body.level)


@router.delete("/{instance_id}/ops/{username}", status_code=204)
def remove_from_ops(instance_id: int, username: str, session: SessionDep):
    if not mc_config.remove_op(_get_or_404(session, instance_id), username):
        raise HTTPException(404, f"{username!r} is not an op")


class ResourcePatch(BaseModel):
    memory: str | None = None
    cpus: float | None = Field(default=None, ge=0)
    jvm_flags: str | None = None


@router.patch("/{instance_id}", response_model=InstanceRead)
def patch_server(instance_id: int, body: ResourcePatch, session: SessionDep):
    """Update runtime resources; the container is recreated to apply (and
    restarted if it was running)."""
    instance = _get_or_404(session, instance_id)
    if body.memory is not None:
        try:
            docker_manager.heap_bytes(body.memory)  # validate format
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
        instance.memory = body.memory
    if body.cpus is not None:
        instance.cpus = body.cpus
    if body.jvm_flags is not None:
        instance.jvm_flags = body.jvm_flags
    session.add(instance)
    session.commit()
    session.refresh(instance)
    docker_manager.recreate_container(instance)
    return _read(instance)


class ExtraPort(BaseModel):
    host: int = Field(ge=1, le=65535)
    container: int = Field(ge=1, le=65535)
    proto: str = Field(default="tcp", pattern="^(tcp|udp)$")


@router.put("/{instance_id}/extra-ports")
def set_extra_ports(instance_id: int, ports: list[ExtraPort], session: SessionDep) -> dict:
    """Extra host->container port mappings (e.g. Geyser Bedrock UDP 19132).
    Applied when the container is next (re)created."""
    import json

    instance = _get_or_404(session, instance_id)
    instance.extra_ports_json = json.dumps([p.model_dump() for p in ports])
    session.add(instance)
    session.commit()
    docker_manager.recreate_container(instance)  # applies live; restarts if running
    return {"extra_ports": [p.model_dump() for p in ports]}


class CommandBody(BaseModel):
    command: str


@router.post("/{instance_id}/command")
def run_command(instance_id: int, body: CommandBody, session: SessionDep) -> dict:
    """One-shot server command via RCON; returns the server's response."""
    instance = _get_or_404(session, instance_id)
    try:
        with console.run_command(instance) as rcon:
            return {"response": rcon.command(body.command)}
    except console.NotRunningError as e:
        raise HTTPException(409, str(e)) from e
    except (RconError, OSError) as e:
        raise HTTPException(502, f"RCON failed: {e}") from e


@router.websocket("/{instance_id}/console")
async def console_ws(websocket: WebSocket, instance_id: int, session: SessionDep):
    """Interactive console: streams stdout/stderr, sends typed lines to stdin."""
    await websocket.accept()
    instance = instances.get_instance(session, instance_id)
    if instance is None:
        await websocket.close(code=4404, reason=f"instance {instance_id} not found")
        return
    if docker_manager.status(instance) != "running":
        await websocket.close(code=4409, reason=f"instance {instance.name!r} is not running")
        return
    await console.bridge_console(websocket, instance)
