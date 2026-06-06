"""Mojang piston-meta client: MC version listing + server jar downloads.

All functions accept an optional httpx.Client so tests can inject a MockTransport.
"""

import hashlib
from pathlib import Path

import httpx

VERSION_MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
PROFILE_API_URL = "https://api.minecraftservices.com/minecraft/profile/lookup/name"


class VersionNotFoundError(Exception):
    pass


class ChecksumError(Exception):
    pass


def make_client() -> httpx.Client:
    return httpx.Client(timeout=30, follow_redirects=True)


def list_versions(client: httpx.Client | None = None) -> list[dict]:
    """All known versions, newest first: [{id, type, url, releaseTime, ...}]."""
    c = client or make_client()
    resp = c.get(VERSION_MANIFEST_URL)
    resp.raise_for_status()
    return resp.json()["versions"]


def get_version(version_id: str, client: httpx.Client | None = None) -> dict:
    """Full version JSON (downloads, javaVersion, ...) for one version id."""
    c = client or make_client()
    entry = next((v for v in list_versions(c) if v["id"] == version_id), None)
    if entry is None:
        raise VersionNotFoundError(f"unknown Minecraft version {version_id!r}")
    resp = c.get(entry["url"])
    resp.raise_for_status()
    return resp.json()


def java_major(version_json: dict) -> int:
    # Very old versions predate the javaVersion field; they all run on Java 8.
    return version_json.get("javaVersion", {}).get("majorVersion", 8)


def download_server_jar(
    version_json: dict, dest: Path, client: httpx.Client | None = None
) -> Path:
    """Stream the server jar to dest, verifying Mojang's sha1."""
    server = version_json.get("downloads", {}).get("server")
    if server is None:
        raise VersionNotFoundError(
            f"version {version_json.get('id')!r} has no server download"
        )
    c = client or make_client()
    sha1 = hashlib.sha1()
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    with c.stream("GET", server["url"]) as resp:
        resp.raise_for_status()
        with tmp.open("wb") as f:
            for chunk in resp.iter_bytes():
                sha1.update(chunk)
                f.write(chunk)
    if sha1.hexdigest() != server["sha1"]:
        tmp.unlink(missing_ok=True)
        raise ChecksumError(f"sha1 mismatch for {dest.name}")
    tmp.replace(dest)
    return dest


def lookup_uuid(username: str, client: httpx.Client | None = None) -> dict | None:
    """Resolve username -> {'id': uuid, 'name': canonical_name}, or None if unknown."""
    c = client or make_client()
    resp = c.get(f"{PROFILE_API_URL}/{username}")
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()
