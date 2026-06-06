"""Provisioning: turn an empty instance dir into a launchable server.

Jars are cached under data/cache/ so N instances of one version download once.
Mutates the instance (java_major, server_jar, loader_version) — caller commits.
"""

import shutil
from pathlib import Path

from api.clients import fabric, mojang
from api.config import settings
from api.models.instance import Loader, ServerInstance
from api.services import docker_manager

FABRIC_JAR = "fabric-launcher.jar"


class EulaNotAcceptedError(Exception):
    pass


def _cache(*parts: str) -> Path:
    return settings.data_dir / "cache" / Path(*parts)


def write_eula(instance: ServerInstance, accepted: bool) -> None:
    if not accepted:
        raise EulaNotAcceptedError("the Minecraft EULA must be accepted to run a server")
    path = docker_manager.instance_dir(instance) / "eula.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("eula=true\n")


def provision_instance(instance: ServerInstance) -> None:
    version_json = mojang.get_version(instance.mc_version)
    instance.java_major = mojang.java_major(version_json)

    if instance.loader == Loader.VANILLA:
        _provision_vanilla(instance, version_json)
    elif instance.loader == Loader.FABRIC:
        _provision_fabric(instance)
    else:  # future loaders (forge/neoforge/paper) plug in here
        raise NotImplementedError(f"loader {instance.loader} not supported yet")


def _provision_vanilla(instance: ServerInstance, version_json: dict) -> None:
    cached = _cache("vanilla", f"{instance.mc_version}.jar")
    if not cached.exists():
        mojang.download_server_jar(version_json, cached)
    _install(instance, cached, "server.jar")


def _provision_fabric(instance: ServerInstance) -> None:
    if not instance.loader_version:
        instance.loader_version = fabric.latest_stable_loader(instance.mc_version)
    installer = fabric.latest_stable_installer()
    cached = _cache(
        "fabric", f"{instance.mc_version}-{instance.loader_version}-{installer}.jar"
    )
    if not cached.exists():
        fabric.download_server_launcher(
            instance.mc_version, instance.loader_version, installer, cached
        )
    _install(instance, cached, FABRIC_JAR)
    # The launcher fetches the vanilla jar itself on first boot.


def _install(instance: ServerInstance, cached: Path, jar_name: str) -> None:
    dest_dir = docker_manager.instance_dir(instance)
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(cached, dest_dir / jar_name)
    instance.server_jar = jar_name
