from fastapi import APIRouter

from api.db import SessionDep
from api.services import docker_manager, instances, network

router = APIRouter(tags=["system"])  # open: just liveness
protected_router = APIRouter(tags=["system"])  # requires auth (mounted in main)


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@protected_router.get("/addresses")
def addresses(session: SessionDep) -> dict:
    """Connection info per instance: LAN address, shareable public address
    (valid once the router forwards the port), and the forwarding rule."""
    ip = network.lan_ip()
    wan = network.public_ip()
    return {
        "lan_ip": ip,
        "public_ip": wan,
        "servers": [
            {
                "name": i.name,
                "address": f"{ip}:{i.game_port}",
                "public_address": f"{wan}:{i.game_port}" if wan else None,
                "game_port": i.game_port,
                "rcon_port": i.rcon_port,
                "status": docker_manager.status(i),
                "port_forward_hint": f"router: TCP/UDP {i.game_port} -> {ip}:{i.game_port}",
            }
            for i in instances.list_instances(session)
        ],
    }
