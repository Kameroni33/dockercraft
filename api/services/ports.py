"""Host port allocation for instances: lowest free port in the configured ranges."""

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
