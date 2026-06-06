import hashlib
import json

import httpx
import pytest

from api.clients import modrinth
from api.services import mods as mods_service
from api.services.mods import mods_dir

JAR = b"\x50\x4b fake mod jar"
SHA512 = hashlib.sha512(JAR).hexdigest()


def _file(name):
    return {"url": f"https://cdn.test/{name}", "filename": name,
            "hashes": {"sha512": SHA512}, "primary": True}


PROJECTS = {
    "geyser": {"id": "GEYSER1", "slug": "geyser", "title": "Geyser"},
    "floodgate": {"id": "FLOOD1", "slug": "floodgate", "title": "Floodgate"},
    "sodium": {"id": "SODIUM1", "slug": "sodium", "title": "Sodium"},
    "forge-only": {"id": "FORGE1", "slug": "forge-only", "title": "Forge Only"},
}
PROJECTS |= {p["id"]: p for p in list(PROJECTS.values())}

VERSIONS = {
    "GEYSER1": [{"id": "gv2", "version_number": "2.0", "files": [_file("geyser.jar")],
                 "dependencies": [{"project_id": "FLOOD1", "dependency_type": "required"}]}],
    "FLOOD1": [{"id": "fv1", "version_number": "1.0", "files": [_file("floodgate.jar")],
                "dependencies": []}],
    "SODIUM1": [
        {"id": "sv2", "version_number": "0.6", "files": [_file("sodium-0.6.jar")],
         "dependencies": []},
        {"id": "sv1", "version_number": "0.5", "files": [_file("sodium-0.5.jar")],
         "dependencies": []},
    ],
    "FORGE1": [],
}


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/v2/search":
        return httpx.Response(200, json={"hits": [
            {"project_id": "GEYSER1", "slug": "geyser", "title": "Geyser",
             "description": "bedrock bridge", "downloads": 9999, "icon_url": None}]})
    if path.startswith("/v2/project/"):
        parts = path.split("/")
        key = parts[3]
        if key not in PROJECTS:
            return httpx.Response(404)
        project = PROJECTS[key]
        if len(parts) == 5 and parts[4] == "version":
            return httpx.Response(200, json=VERSIONS[project["id"]])
        return httpx.Response(200, json=project)
    if request.url.host == "cdn.test":
        return httpx.Response(200, content=JAR)
    return httpx.Response(404)


@pytest.fixture
def fake_modrinth(monkeypatch):
    client = httpx.Client(transport=httpx.MockTransport(_handler))
    monkeypatch.setattr(modrinth, "make_client", lambda: client)
    return client


def _server(client, loader="fabric", name="modded"):
    return client.post(
        "/servers", json={"name": name, "mc_version": "1.21.1", "loader": loader}
    ).json()["id"]


def test_install_resolves_dependencies(client, session, fake_modrinth):
    sid = _server(client)
    resp = client.post(f"/servers/{sid}/mods", json={"project": "geyser"})
    assert resp.status_code == 201
    titles = [m["title"] for m in resp.json()["installed"]]
    assert titles == ["Floodgate", "Geyser"]  # dep installed first

    inst_mods = {m["slug"]: m for m in client.get(f"/servers/{sid}/mods").json()}
    assert inst_mods["floodgate"]["dependency_of"] == "GEYSER1"
    assert json.loads(inst_mods["geyser"]["requires_json"]) == ["FLOOD1"]
    from api.services.instances import get_instance

    d = mods_dir(get_instance(session, sid))
    assert (d / "geyser.jar").read_bytes() == JAR and (d / "floodgate.jar").exists()

    # Re-install is a no-op
    assert client.post(f"/servers/{sid}/mods", json={"project": "geyser"}).json()["installed"] == []


def test_uninstall_dependency_protection(client, session, fake_modrinth):
    sid = _server(client)
    client.post(f"/servers/{sid}/mods", json={"project": "geyser"})
    resp = client.delete(f"/servers/{sid}/mods/FLOOD1")
    assert resp.status_code == 409 and "Geyser" in resp.json()["detail"]
    assert client.delete(f"/servers/{sid}/mods/FLOOD1?force=true").status_code == 204
    # Geyser itself uninstalls freely
    assert client.delete(f"/servers/{sid}/mods/GEYSER1").status_code == 204
    assert client.get(f"/servers/{sid}/mods").json() == []


def test_incompatible_and_wrong_loader(client, fake_modrinth):
    sid = _server(client)
    assert client.post(f"/servers/{sid}/mods", json={"project": "forge-only"}).status_code == 422
    assert client.post(f"/servers/{sid}/mods", json={"project": "nope"}).status_code == 404
    vanilla = _server(client, loader="vanilla", name="plain")
    assert client.post(f"/servers/{vanilla}/mods", json={"project": "geyser"}).status_code == 409


def test_toggle_enabled(client, session, fake_modrinth):
    sid = _server(client)
    client.post(f"/servers/{sid}/mods", json={"project": "sodium"})
    from api.services.instances import get_instance

    d = mods_dir(get_instance(session, sid))
    assert (d / "sodium-0.6.jar").exists()

    client.patch(f"/servers/{sid}/mods/SODIUM1", json={"enabled": False})
    assert not (d / "sodium-0.6.jar").exists()
    assert (d / "sodium-0.6.jar.disabled").exists()
    client.patch(f"/servers/{sid}/mods/SODIUM1", json={"enabled": True})
    assert (d / "sodium-0.6.jar").exists()


def test_update_flow(client, session, fake_modrinth):
    sid = _server(client)
    client.post(f"/servers/{sid}/mods", json={"project": "sodium", "version_id": "sv1"})
    updates = client.post(f"/servers/{sid}/mods/check-updates").json()
    assert updates == [{
        "project_id": "SODIUM1", "title": "Sodium", "installed": "0.5",
        "available": "0.6", "available_version_id": "sv2", "auto_update": False,
    }]

    resp = client.post(f"/servers/{sid}/mods/SODIUM1/update").json()
    assert resp["updated"] is True and resp["version"] == "0.6"
    from api.services.instances import get_instance

    d = mods_dir(get_instance(session, sid))
    assert (d / "sodium-0.6.jar").exists() and not (d / "sodium-0.5.jar").exists()
    assert client.post(f"/servers/{sid}/mods/check-updates").json() == []
    # Already current: no-op
    assert client.post(f"/servers/{sid}/mods/SODIUM1/update").json()["updated"] is False


def test_auto_update_flag(client, fake_modrinth):
    sid = _server(client)
    client.post(f"/servers/{sid}/mods", json={"project": "sodium", "version_id": "sv1"})
    mod = client.patch(f"/servers/{sid}/mods/SODIUM1", json={"auto_update": True}).json()
    assert mod["auto_update"] is True
    assert mods_service  # imported for completeness; service tested via endpoints


def test_auto_update_sweep(client, session, fake_modrinth):
    from api.services import scheduler

    sid = _server(client)
    client.post(f"/servers/{sid}/mods", json={"project": "sodium", "version_id": "sv1"})
    client.post(f"/servers/{sid}/mods", json={"project": "geyser"})  # current; no auto

    assert scheduler.run_mod_updates(session) == []  # nothing flagged yet
    client.patch(f"/servers/{sid}/mods/SODIUM1", json={"auto_update": True})
    assert scheduler.run_mod_updates(session) == ["modded:sodium@0.6"]
    assert scheduler.run_mod_updates(session) == []  # already current
