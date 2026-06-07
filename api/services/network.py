"""LAN + public address discovery for the sharing/port-forwarding views."""

import socket
import time

import httpx

from api.config import settings

PUBLIC_IP_SERVICES = ["https://checkip.amazonaws.com", "https://api.ipify.org"]
PUBLIC_IP_TTL = 3600  # WAN IPs rarely change
PUBLIC_IP_FAIL_TTL = 60  # don't hang every /addresses call while offline

_public_ip_cache: tuple[float, str | None] | None = None


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


def detect_public_ip() -> str | None:
    """The WAN IP as seen from outside, via plain-text echo services."""
    for url in PUBLIC_IP_SERVICES:
        try:
            resp = httpx.get(url, timeout=3)
            resp.raise_for_status()
            ip = resp.text.strip()
            if ip:
                return ip
        except httpx.HTTPError:
            continue
    return None


def public_ip() -> str | None:
    """Cached public IP (or the DOCKERCRAFT_PUBLIC_IP override). None if
    detection fails — e.g. no internet — and the UI just hides the row."""
    global _public_ip_cache
    if settings.public_ip:
        return settings.public_ip
    now = time.time()
    if _public_ip_cache is not None:
        fetched_at, cached = _public_ip_cache
        ttl = PUBLIC_IP_TTL if cached else PUBLIC_IP_FAIL_TTL
        if now - fetched_at < ttl:
            return cached
    ip = detect_public_ip()
    _public_ip_cache = (now, ip)
    return ip
