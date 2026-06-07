"""Host port allocation for instances: lowest free port in the configured ranges."""

import json

from sqlmodel import Session, select

from api.config import settings
from api.models.instance import ServerInstance


class PortsExhaustedError(Exception):
    pass


def _allocate(used: set[int], port_range: tuple[int, int]) -> int:
    lo, hi = port_range
    for port in range(lo, hi + 1):
        if port not in used:
            return port
    raise PortsExhaustedError(f"no free ports in {lo}-{hi}")


def allocate_ports(session: Session) -> tuple[int, int]:
    """Return (game_port, rcon_port) not used by any existing instance."""
    instances = session.exec(select(ServerInstance)).all()
    used = {i.game_port for i in instances} | {i.rcon_port for i in instances}
    game = _allocate(used, settings.game_port_range)
    rcon = _allocate(used | {game}, settings.rcon_port_range)
    return game, rcon


def allocate_bedrock_remap_port(session: Session) -> int:
    """Lowest free port in the Bedrock remap range (used when LAN discovery
    moves an instance's Bedrock host port out of phantom-owned 19132)."""
    instances = session.exec(select(ServerInstance)).all()
    used = {i.game_port for i in instances} | {i.rcon_port for i in instances}
    for i in instances:
        used |= {extra["host"] for extra in json.loads(i.extra_ports_json)}
    return _allocate(used, settings.bedrock_remap_range)
