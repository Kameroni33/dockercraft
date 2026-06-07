"""Modrinth API v2 client: mod search, versions, compatibility-filtered downloads."""

import hashlib
import json
from pathlib import Path

import httpx

MODRINTH_URL = "https://api.modrinth.com/v2"
USER_AGENT = "dockercraft/0.1.0 (self-hosted Minecraft server manager)"


class ProjectNotFoundError(Exception):
    pass


class ChecksumError(Exception):
    pass


def make_client() -> httpx.Client:
    return httpx.Client(
        timeout=30, follow_redirects=True, headers={"User-Agent": USER_AGENT}
    )


def search(
    query: str,
    loader: str | None = None,
    mc_version: str | None = None,
    limit: int = 20,
    client: httpx.Client | None = None,
) -> list[dict]:
    """Project search, filtered to compatible loader/MC version via facets."""
    c = client or make_client()
    facets = [["project_type:mod"]]
    if loader:
        facets.append([f"categories:{loader}"])
    if mc_version:
        facets.append([f"versions:{mc_version}"])
    resp = c.get(
        f"{MODRINTH_URL}/search",
        params={"query": query, "facets": json.dumps(facets), "limit": limit},
    )
    resp.raise_for_status()
    return resp.json()["hits"]


def get_project(id_or_slug: str, client: httpx.Client | None = None) -> dict:
    c = client or make_client()
    resp = c.get(f"{MODRINTH_URL}/project/{id_or_slug}")
    if resp.status_code == 404:
        raise ProjectNotFoundError(f"no Modrinth project {id_or_slug!r}")
    resp.raise_for_status()
    return resp.json()


def get_versions(
    id_or_slug: str,
    loader: str,
    mc_version: str,
    client: httpx.Client | None = None,
) -> list[dict]:
    """Compatible versions, newest first (Modrinth's ordering)."""
    c = client or make_client()
    resp = c.get(
        f"{MODRINTH_URL}/project/{id_or_slug}/version",
        params={
            "loaders": json.dumps([loader]),
            "game_versions": json.dumps([mc_version]),
        },
    )
    if resp.status_code == 404:
        raise ProjectNotFoundError(f"no Modrinth project {id_or_slug!r}")
    resp.raise_for_status()
    return resp.json()


def primary_file(version: dict) -> dict:
    files = version["files"]
    return next((f for f in files if f.get("primary")), files[0])


def download_file(file_info: dict, dest: Path, client: httpx.Client | None = None) -> Path:
    """Stream a version file to dest, verifying Modrinth's sha512."""
    c = client or make_client()
    expected = file_info.get("hashes", {}).get("sha512")
    sha512 = hashlib.sha512()
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    with c.stream("GET", file_info["url"]) as resp:
        resp.raise_for_status()
        with tmp.open("wb") as f:
            for chunk in resp.iter_bytes():
                sha512.update(chunk)
                f.write(chunk)
    if expected and sha512.hexdigest() != expected:
        tmp.unlink(missing_ok=True)
        raise ChecksumError(f"sha512 mismatch for {dest.name}")
    tmp.replace(dest)
    return dest
