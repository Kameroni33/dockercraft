from fastapi import APIRouter

from api.db import SessionDep
from api.services import docker_manager, instances, network

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/addresses")
def addresses(session: SessionDep) -> dict:
    """Connection info per instance — what players use on the LAN, and the
    ports to forward on the router for external access."""
    ip = network.lan_ip()
    return {
        "lan_ip": ip,
        "servers": [
            {
                "name": i.name,
                "address": f"{ip}:{i.game_port}",
                "game_port": i.game_port,
                "rcon_port": i.rcon_port,
                "status": docker_manager.status(i),
                "port_forward_hint": f"router: TCP/UDP {i.game_port} -> {ip}:{i.game_port}",
            }
            for i in instances.list_instances(session)
        ],
    }
