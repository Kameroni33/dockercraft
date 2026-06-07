"""LAN address discovery for the port-forwarding view."""

import socket

from api.config import settings


def detect_lan_ip() -> str:
    """The host's outbound-facing IP. UDP connect sends no packets — it just
    forces the kernel to pick the route + source address."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def lan_ip() -> str:
    # Containerized managers detect their bridge IP, which is useless to players —
    # set DOCKERCRAFT_LAN_IP explicitly in that case (compose does this).
    return settings.lan_ip or detect_lan_ip()
