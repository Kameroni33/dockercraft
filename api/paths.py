"""Filesystem layout helpers. Two views of the same data:
manager view (file IO) vs docker-host view (bind mounts for sibling containers)."""

from pathlib import Path

from api.config import settings


def instance_dir(name: str) -> Path:
    return settings.instances_dir / name


def instance_host_dir(name: str) -> Path:
    return settings.resolved_host_data_dir / "instances" / name
