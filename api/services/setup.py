"""New-server setup flow: one call from nothing to a ready (or running) server.

Composes: create -> provision (jar/loader download) -> EULA -> properties ->
whitelist/ops -> optional start. Provisioning failures roll the instance back
so a failed setup leaves nothing behind.
"""

from pydantic import BaseModel, Field
from sqlmodel import Session

from api.clients import mojang
from api.models.instance import InstanceCreate, Loader, ServerInstance
from api.services import instances, mc_config, players, provision

LATEST = "latest"


class SetupRequest(BaseModel):
    name: str
    mc_version: str = LATEST  # "latest" -> current release
    loader: Loader = Loader.VANILLA
    loader_version: str | None = None  # fabric: None -> latest stable
    memory: str = "2G"
    jvm_flags: str = ""
    accept_eula: bool = False  # must be explicitly true
    properties: dict = Field(default_factory=dict)
    whitelist: list[str] = Field(default_factory=list)  # usernames; enables white-list
    ops: list[str] = Field(default_factory=list)
    start: bool = False


def setup_server(session: Session, req: SetupRequest) -> ServerInstance:
    # EULA gate comes first — fail before any downloads or DB writes.
    if not req.accept_eula:
        raise provision.EulaNotAcceptedError(
            "accept_eula must be true — running a server requires accepting the Minecraft EULA"
        )

    mc_version = mojang.latest_release() if req.mc_version == LATEST else req.mc_version
    instance = instances.create_instance(
        session,
        InstanceCreate(
            name=req.name,
            mc_version=mc_version,
            loader=req.loader,
            loader_version=req.loader_version,
            memory=req.memory,
            jvm_flags=req.jvm_flags,
        ),
    )
    try:
        provision.provision_instance(instance)
        provision.write_eula(instance, req.accept_eula)

        properties = dict(req.properties)
        if req.whitelist:
            properties.setdefault("white-list", True)
        if properties:
            mc_config.update_properties(instance, properties)
        else:
            mc_config.apply_managed(instance)

        for username in req.whitelist:
            player = players.resolve(session, username)
            mc_config.add_whitelist(instance, player.uuid, player.username)
        for username in req.ops:
            player = players.resolve(session, username)
            mc_config.add_op(instance, player.uuid, player.username)
    except Exception:
        instances.delete_instance(session, instance, delete_data=True)
        raise

    session.add(instance)  # provision mutated java_major/server_jar/loader_version
    session.commit()
    session.refresh(instance)

    if req.start:
        instances.start_instance(instance)
    return instance
