"""Thin service layer over the docker SDK — every docker call in the app lives here.

Containers are named dockercraft-mc-<instance.name> and labeled so we can always
re-discover them. The DB stores declared config; Docker is the source of truth
for live status.
"""

from pathlib import Path

import docker
from docker.errors import ImageNotFound, NotFound
from docker.models.containers import Container

from api import paths
from api.config import settings
from api.models.instance import ServerInstance

LABEL = "dockercraft.instance"
STOP_TIMEOUT = 60  # seconds for SIGTERM → world save before SIGKILL

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
    return {
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
        "ports": {
            "25565/tcp": instance.game_port,
            "25565/udp": instance.game_port,
            "25575/tcp": instance.rcon_port,
        },
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


def stop(instance: ServerInstance) -> None:
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
