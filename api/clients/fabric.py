"""Fabric Meta client: loader/installer versions + server launcher download.

The Fabric "server launcher" jar bundles the loader and fetches the matching
vanilla server jar on first boot, so it is the only file a Fabric instance needs.
"""

from pathlib import Path

import httpx

from api.clients import mojang

FABRIC_META_URL = "https://meta.fabricmc.net/v2"


class NoLoaderError(Exception):
    pass


def loader_versions(mc_version: str, client: httpx.Client | None = None) -> list[dict]:
    """Loaders available for an MC version, newest first: [{version, stable}]."""
    c = client or mojang.make_client()
    resp = c.get(f"{FABRIC_META_URL}/versions/loader/{mc_version}")
    resp.raise_for_status()
    return [{**e["loader"]} for e in resp.json()]


def latest_stable_loader(mc_version: str, client: httpx.Client | None = None) -> str:
    versions = loader_versions(mc_version, client)
    stable = [v for v in versions if v.get("stable")]
    if not stable and not versions:
        raise NoLoaderError(f"no Fabric loader available for MC {mc_version}")
    return (stable or versions)[0]["version"]


def latest_stable_installer(client: httpx.Client | None = None) -> str:
    c = client or mojang.make_client()
    resp = c.get(f"{FABRIC_META_URL}/versions/installer")
    resp.raise_for_status()
    versions = resp.json()
    stable = [v for v in versions if v.get("stable")]
    return (stable or versions)[0]["version"]


def download_server_launcher(
    mc_version: str,
    loader_version: str,
    installer_version: str,
    dest: Path,
    client: httpx.Client | None = None,
) -> Path:
    c = client or mojang.make_client()
    url = (
        f"{FABRIC_META_URL}/versions/loader/{mc_version}/{loader_version}"
        f"/{installer_version}/server/jar"
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    with c.stream("GET", url) as resp:
        resp.raise_for_status()
        with tmp.open("wb") as f:
            for chunk in resp.iter_bytes():
                f.write(chunk)
    tmp.replace(dest)
    return dest
