"""GeyserMC global API client: Xbox gamertag -> XUID lookups for Floodgate.

Bedrock players have no Mojang account. Floodgate gives them a synthetic Java
profile: UUID = UUID(0, xuid) and username = prefix + gamertag (prefix "." by
default) — that's what whitelist.json/ops.json must contain for them.
"""

import uuid as uuidlib
from urllib.parse import quote

import httpx

from api.clients.mojang import make_client

GEYSER_API_URL = "https://api.geysermc.org/v2"


def lookup_xuid(gamertag: str, client: httpx.Client | None = None) -> int | None:
    """Resolve an Xbox gamertag to its XUID, or None if unknown.

    Quirk: the API answers 503 (with an "Unable to find user in our cache"
    body) for gamertags it doesn't know — its cache covers players who have
    connected through a Geyser server before, not all of Xbox Live.
    """
    c = client or make_client()
    resp = c.get(f"{GEYSER_API_URL}/xbox/xuid/{quote(gamertag)}")
    if resp.status_code in (400, 404):
        return None
    if resp.status_code == 503 and "find user" in resp.text.lower():
        return None
    resp.raise_for_status()
    xuid = resp.json().get("xuid")
    return int(xuid) if xuid else None


def floodgate_uuid(xuid: int) -> str:
    """Floodgate UUIDs are UUID(0, xuid) — the XUID in the low 64 bits."""
    return str(uuidlib.UUID(int=xuid))
