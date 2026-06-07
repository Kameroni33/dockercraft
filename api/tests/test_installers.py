import hashlib
import json

import httpx
import pytest

from api.clients import fabric, mojang
from api.config import settings
from api.models.instance import Loader, ServerInstance
from api.services import provision

JAR_BYTES = b"\x50\x4b\x03\x04 fake server jar"
JAR_SHA1 = hashlib.sha1(JAR_BYTES).hexdigest()

MANIFEST = {
    "versions": [
        {"id": "1.21.1", "type": "release", "url": "https://meta.test/1.21.1.json",
         "releaseTime": "2024-08-08T12:24:45+00:00"},
        {"id": "1.8.9", "type": "release", "url": "https://meta.test/1.8.9.json",
         "releaseTime": "2015-12-09T12:24:45+00:00"},
    ]
}
VERSION_1_21_1 = {
    "id": "1.21.1",
    "javaVersion": {"majorVersion": 21},
    "downloads": {"server": {"url": "https://dl.test/server.jar", "sha1": JAR_SHA1}},
}
VERSION_1_8_9 = {"id": "1.8.9", "downloads": {}}  # no javaVersion, no server dl

FABRIC_LOADERS = [
    {"loader": {"version": "0.16.0", "stable": False}},
    {"loader": {"version": "0.15.11", "stable": True}},
]
FABRIC_INSTALLERS = [{"version": "1.0.1", "stable": True}]


def _handler(request: httpx.Request) -> httpx.Response:
    url = str(request.url)
    routes = {
        mojang.VERSION_MANIFEST_URL: MANIFEST,
        "https://meta.test/1.21.1.json": VERSION_1_21_1,
        "https://meta.test/1.8.9.json": VERSION_1_8_9,
        f"{fabric.FABRIC_META_URL}/versions/loader/1.21.1": FABRIC_LOADERS,
        f"{fabric.FABRIC_META_URL}/versions/installer": FABRIC_INSTALLERS,
    }
    if url in routes:
        return httpx.Response(200, text=json.dumps(routes[url]))
    if url == "https://dl.test/server.jar" or "/server/jar" in url:
        return httpx.Response(200, content=JAR_BYTES)
    return httpx.Response(404)


@pytest.fixture
def http(monkeypatch):
    client = httpx.Client(transport=httpx.MockTransport(_handler))
    monkeypatch.setattr(mojang, "make_client", lambda: client)
    return client


def test_list_and_get_version(http):
    versions = mojang.list_versions(http)
    assert versions[0]["id"] == "1.21.1"
    v = mojang.get_version("1.21.1", http)
    assert mojang.java_major(v) == 21
    assert mojang.java_major(mojang.get_version("1.8.9", http)) == 8  # pre-field default


def test_unknown_version(http):
    with pytest.raises(mojang.VersionNotFoundError):
        mojang.get_version("9.9.9", http)


def test_download_verifies_sha1(http, tmp_path):
    dest = tmp_path / "server.jar"
    mojang.download_server_jar(VERSION_1_21_1, dest, http)
    assert dest.read_bytes() == JAR_BYTES

    bad = {**VERSION_1_21_1, "downloads": {"server": {"url": "https://dl.test/server.jar",
                                                      "sha1": "0" * 40}}}
    with pytest.raises(mojang.ChecksumError):
        mojang.download_server_jar(bad, tmp_path / "bad.jar", http)
    assert not (tmp_path / "bad.jar").exists()


def test_fabric_latest_stable(http):
    assert fabric.latest_stable_loader("1.21.1", http) == "0.15.11"
    assert fabric.latest_stable_installer(http) == "1.0.1"


def _instance(loader=Loader.VANILLA) -> ServerInstance:
    return ServerInstance(
        name="prov-test", mc_version="1.21.1", loader=loader, game_port=1, rcon_port=2
    )


def test_provision_vanilla_and_cache(http, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    inst = _instance()
    provision.provision_instance(inst)
    assert inst.java_major == 21
    assert inst.server_jar == "server.jar"
    assert (tmp_path / "instances/prov-test/server.jar").read_bytes() == JAR_BYTES

    cache = tmp_path / "cache/vanilla/1.21.1.jar"
    assert cache.exists()
    cache.write_bytes(b"CACHED")  # second provision must reuse, not re-download
    inst2 = _instance()
    inst2.name = "prov-test-2"
    provision.provision_instance(inst2)
    assert (tmp_path / "instances/prov-test-2/server.jar").read_bytes() == b"CACHED"


def test_provision_fabric(http, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    inst = _instance(Loader.FABRIC)
    provision.provision_instance(inst)
    assert inst.loader_version == "0.15.11"  # auto-picked latest stable
    assert inst.server_jar == provision.FABRIC_JAR
    assert (tmp_path / "instances/prov-test" / provision.FABRIC_JAR).exists()


def test_eula(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    inst = _instance()
    with pytest.raises(provision.EulaNotAcceptedError):
        provision.write_eula(inst, accepted=False)
    provision.write_eula(inst, accepted=True)
    assert (tmp_path / "instances/prov-test/eula.txt").read_text() == "eula=true\n"
