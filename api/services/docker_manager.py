"""Thin service layer over the docker SDK — every docker call in the app lives here.

Containers are named dockercraft-mc-<instance.name> and labeled so we can always
re-discover them. The DB stores declared config; Docker is the source of truth
for live status.
"""

import json
from pathlib import Path

import docker
from docker.errors import ImageNotFound, NotFound
from docker.models.containers import Container

from api import paths
from api.config import settings
from api.models.instance import ServerInstance

LABEL = "dockercraft.instance"
PHANTOM_LABEL = "dockercraft.phantom"
STOP_TIMEOUT = 60  # seconds for SIGTERM → world save before SIGKILL
MEM_OVERHEAD = 1.5  # container limit = JVM heap × this (metaspace, native, etc.)
BEDROCK_PORT = 19132  # Bedrock default port; also the LAN discovery broadcast port


def heap_bytes(memory: str) -> int:
    """Parse a JVM size string ("2G", "2048M") to bytes."""
    import re

    m = re.fullmatch(r"(\d+)\s*([GgMm])", memory.strip())
    if not m:
        raise ValueError(f"invalid memory size {memory!r} (use e.g. 2G or 2048M)")
    n, unit = int(m.group(1)), m.group(2).lower()
    return n * (1024**3 if unit == "g" else 1024**2)

_client: docker.DockerClient | None = None


def get_client() -> docker.DockerClient:
    global _client
    if _client is None:
        _client = docker.from_env()
    return _client


def container_name(instance: ServerInstance) -> str:
    return f"dockercraft-mc-{instance.name}"


def image_tag(java_major: int) -> str:
    return f"{settings.mc_image_repo}:java{java_major}"


def ensure_image(java_major: int) -> str:
    """Return the MC image tag for this Java major, building it if absent."""
    tag = image_tag(java_major)
    client = get_client()
    try:
        client.images.get(tag)
    except ImageNotFound:
        context = Path(__file__).resolve().parents[2] / "images" / "minecraft"
        client.images.build(
            path=str(context), buildargs={"JAVA_VERSION": str(java_major)}, tag=tag
        )
    return tag


def container_config(instance: ServerInstance) -> dict:
    """Build the kwargs for containers.create() for this instance."""
    ports = {
        "25565/tcp": instance.game_port,
        "25565/udp": instance.game_port,
        # RCON is password-protected but plaintext — never expose beyond the host.
        "25575/tcp": ("127.0.0.1", instance.rcon_port),
    }
    for extra in json.loads(instance.extra_ports_json):
        ports[f"{extra['container']}/{extra.get('proto', 'tcp')}"] = extra["host"]
    limits: dict = {"mem_limit": int(heap_bytes(instance.memory) * MEM_OVERHEAD)}
    if instance.cpus > 0:
        limits["nano_cpus"] = int(instance.cpus * 1e9)
    return {
        **limits,
        "image": image_tag(instance.java_major),
        "name": container_name(instance),
        "detach": True,
        "stdin_open": True,  # console commands go to the server's stdin
        "environment": {
            "SERVER_JAR": instance.server_jar,
            "MEMORY": instance.memory,
            "JVM_FLAGS": instance.jvm_flags,
        },
        "volumes": {
            str(paths.instance_host_dir(instance.name)): {"bind": "/data", "mode": "rw"}
        },
        "ports": ports,
        "restart_policy": {"Name": "unless-stopped"},  # crash → restart; API stop sticks
        "labels": {LABEL: instance.name},
    }


def get_container(instance: ServerInstance) -> Container | None:
    try:
        return get_client().containers.get(container_name(instance))
    except NotFound:
        return None


def status(instance: ServerInstance) -> str:
    """Docker container status, or "not_created" if no container exists yet."""
    container = get_container(instance)
    return container.status if container else "not_created"


def start(instance: ServerInstance) -> None:
    """Start the instance, (re)creating its container from current config."""
    container = get_container(instance)
    if container is None:
        ensure_image(instance.java_major)
        container = get_client().containers.create(**container_config(instance))
    container.start()
    if instance.lan_discovery and bedrock_host_port(instance) is not None:
        start_phantom(instance)


def stop(instance: ServerInstance) -> None:
    stop_phantom(instance)  # a stopped server must not keep advertising a LAN game
    container = get_container(instance)
    if container is not None:
        container.stop(timeout=STOP_TIMEOUT)


def restart(instance: ServerInstance) -> None:
    container = get_container(instance)
    if container is None:
        start(instance)
    else:
        container.restart(timeout=STOP_TIMEOUT)


def remove_container(instance: ServerInstance) -> None:
    """Stop and remove the container. Instance data on disk is untouched."""
    remove_phantom(instance)
    container = get_container(instance)
    if container is not None:
        container.stop(timeout=STOP_TIMEOUT)
        container.remove()


def recreate_container(instance: ServerInstance) -> None:
    """Apply config changes (ports/memory/flags) by replacing the container."""
    was_running = status(instance) == "running"
    remove_container(instance)
    if was_running:
        start(instance)


# --- phantom sidecar (console LAN discovery) --------------------------------
#
# Bedrock consoles find servers by broadcasting a ping to UDP 19132, which never
# traverses Docker's bridge NAT — so a Geyser port published the normal way is
# invisible to them. phantom (github.com/jhead/phantom) answers those broadcasts
# and proxies game traffic to the real server. It must run host-networked and
# own UDP 19132, hence at most one phantom per host.


def phantom_container_name(instance: ServerInstance) -> str:
    return f"dockercraft-phantom-{instance.name}"


def ensure_phantom_image() -> str:
    """Return the phantom image tag, building it if absent."""
    tag = settings.phantom_image
    client = get_client()
    try:
        client.images.get(tag)
    except ImageNotFound:
        context = Path(__file__).resolve().parents[2] / "images" / "phantom"
        client.images.build(
            path=str(context),
            buildargs={"PHANTOM_VERSION": settings.phantom_version},
            tag=tag,
        )
    return tag


def bedrock_host_port(instance: ServerInstance) -> int | None:
    """Host port of the instance's Bedrock (Geyser) mapping, if any."""
    for extra in json.loads(instance.extra_ports_json):
        if extra.get("proto") == "udp" and extra["container"] == BEDROCK_PORT:
            return extra["host"]
    return None


def phantom_config(instance: ServerInstance) -> dict:
    """Build the kwargs for containers.create() for the phantom sidecar."""
    port = bedrock_host_port(instance)
    if port is None:
        raise ValueError(f"instance {instance.name!r} has no Bedrock port mapping")
    return {
        "image": settings.phantom_image,
        "name": phantom_container_name(instance),
        "detach": True,
        # Host networking: LAN discovery broadcasts can't reach a bridge-published
        # port. The proxy port stays random — consoles auto-discover it.
        "network_mode": "host",
        "command": ["-server", f"127.0.0.1:{port}"],
        "restart_policy": {"Name": "unless-stopped"},
        "labels": {PHANTOM_LABEL: instance.name},
    }


def get_phantom(instance: ServerInstance) -> Container | None:
    try:
        return get_client().containers.get(phantom_container_name(instance))
    except NotFound:
        return None


def start_phantom(instance: ServerInstance) -> None:
    container = get_phantom(instance)
    if container is None:
        ensure_phantom_image()
        container = get_client().containers.create(**phantom_config(instance))
    container.start()


def stop_phantom(instance: ServerInstance) -> None:
    container = get_phantom(instance)
    if container is not None:
        container.stop(timeout=10)  # nothing to save; don't wait the MC 60s


def remove_phantom(instance: ServerInstance) -> None:
    container = get_phantom(instance)
    if container is not None:
        container.stop(timeout=10)
        container.remove()
