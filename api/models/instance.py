import secrets
from datetime import UTC, datetime
from enum import StrEnum

from sqlmodel import Field, SQLModel


class Loader(StrEnum):
    VANILLA = "vanilla"
    FABRIC = "fabric"


class ServerInstance(SQLModel, table=True):
    """Declared configuration of one MC server. Live status comes from Docker,
    never from the DB — query docker_manager.status() for it."""

    __tablename__ = "server_instance"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)  # docker-safe slug, e.g. "brothers-smp"
    mc_version: str
    loader: Loader = Loader.VANILLA
    loader_version: str | None = None
    java_major: int = 21  # from piston-meta's javaVersion at provision time
    server_jar: str = "server.jar"

    game_port: int = Field(unique=True)
    rcon_port: int = Field(unique=True)
    rcon_password: str = Field(default_factory=lambda: secrets.token_urlsafe(16))
    # Extra host->container mappings, e.g. Geyser's Bedrock UDP 19132:
    # [{"host": 19132, "container": 19132, "proto": "udp"}]
    extra_ports_json: str = "[]"

    memory: str = "2G"
    cpus: float = 0  # CPU cores cap; 0 = unlimited
    jvm_flags: str = ""

    # Run a phantom sidecar so consoles (Switch/Xbox/PS) discover this server as
    # a LAN game. At most one instance per host (phantom owns UDP 19132).
    lan_discovery: bool = False

    # Backup policy (0 = unlimited for keep_*; pruning never touches manual backups)
    backup_enabled: bool = False
    backup_interval_hours: int = 6
    backup_keep_count: int = 10
    backup_keep_days: int = 0

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class InstanceCreate(SQLModel):
    name: str
    mc_version: str
    loader: Loader = Loader.VANILLA
    loader_version: str | None = None
    memory: str = "2G"
    jvm_flags: str = ""


class InstanceRead(SQLModel):
    id: int
    name: str
    mc_version: str
    loader: Loader
    loader_version: str | None
    java_major: int
    game_port: int
    rcon_port: int
    extra_ports_json: str
    memory: str
    cpus: float
    jvm_flags: str
    lan_discovery: bool
    created_at: datetime
    status: str  # computed from docker, attached by the router
