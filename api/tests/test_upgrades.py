"""Version upgrades: pre-flight compatibility, the upgrade itself, the
post-boot health check, and rollback via the pre_upgrade backup."""

import hashlib
import json

import httpx
import pytest

from api.clients import fabric, modrinth, mojang
from api.services import docker_manager, instances, upgrades

CURRENT = "1.21.1"
TARGET = "1.21.4"

JAR = b"\x50\x4b fake mod jar"
SHA512 = hashlib.sha512(JAR).hexdigest()

VERSION_JSON = {
    CURRENT: {"id": CURRENT, "javaVersion": {"majorVersion": 21}},
    TARGET: {"id": TARGET, "javaVersion": {"majorVersion": 22}},  # Java bump
}


def _file(name):
    return {
        "url": f"https://cdn.test/{name}",
        "filename": name,
        "hashes": {"sha512": SHA512},
        "primary": True,
    }


PROJECTS = {
    "sodium": {"id": "SODIUM1", "slug": "sodium", "title": "Sodium"},
    "oldmod": {"id": "OLD1", "slug": "oldmod", "title": "Stuck Mod"},
    "needsdep": {"id": "NEEDS1", "slug": "needsdep", "title": "Needs Dep"},
    "newdep": {"id": "NEWDEP1", "slug": "newdep", "title": "New Dep"},
}
PROJECTS |= {p["id"]: p for p in list(PROJECTS.values())}

# project id -> mc version -> versions (newest first). Missing = no build.
BUILDS = {
    "SODIUM1": {
        CURRENT: [
            {
                "id": "sv1",
                "version_number": "0.5",
                "files": [_file("sodium-0.5.jar")],
                "dependencies": [],
            }
        ],
        TARGET: [
            {
                "id": "sv2",
                "version_number": "0.6",
                "files": [_file("sodium-0.6.jar")],
                "dependencies": [],
            }
        ],
    },
    # The blocker: nothing built for TARGET yet.
    "OLD1": {
        CURRENT: [
            {
                "id": "ov1",
                "version_number": "1.0",
                "files": [_file("oldmod.jar")],
                "dependencies": [],
            }
        ],
    },
    # Its TARGET build gains a dependency its CURRENT build didn't have.
    "NEEDS1": {
        CURRENT: [
            {
                "id": "nv1",
                "version_number": "1.0",
                "files": [_file("needs-1.0.jar")],
                "dependencies": [],
            }
        ],
        TARGET: [
            {
                "id": "nv2",
                "version_number": "2.0",
                "files": [_file("needs-2.0.jar")],
                "dependencies": [{"project_id": "NEWDEP1", "dependency_type": "required"}],
            }
        ],
    },
    "NEWDEP1": {
        CURRENT: [
            {
                "id": "dv1",
                "version_number": "1.0",
                "files": [_file("newdep.jar")],
                "dependencies": [],
            }
        ],
        TARGET: [
            {
                "id": "dv2",
                "version_number": "2.0",
                "files": [_file("newdep-2.jar")],
                "dependencies": [],
            }
        ],
    },
}


def _handler(request: httpx.Request) -> httpx.Response:
    if request.url.host == "cdn.test":
        return httpx.Response(200, content=JAR)
    parts = request.url.path.split("/")
    key = parts[3] if len(parts) > 3 else ""
    if key not in PROJECTS:
        return httpx.Response(404)
    project = PROJECTS[key]
    if len(parts) == 5 and parts[4] == "version":
        wanted = json.loads(request.url.params["game_versions"])[0]
        return httpx.Response(200, json=BUILDS[project["id"]].get(wanted, []))
    return httpx.Response(200, json=project)


@pytest.fixture
def fake_upstreams(monkeypatch, tmp_path):
    """Modrinth + Mojang + Fabric + the docker bits upgrades touches."""
    monkeypatch.setattr(
        modrinth, "make_client", lambda: httpx.Client(transport=httpx.MockTransport(_handler))
    )

    def get_version(version_id, client=None):
        if version_id not in VERSION_JSON:
            raise mojang.VersionNotFoundError(f"unknown Minecraft version {version_id!r}")
        return VERSION_JSON[version_id]

    monkeypatch.setattr(mojang, "get_version", get_version)
    monkeypatch.setattr(mojang, "latest_release", lambda client=None: TARGET)
    monkeypatch.setattr(fabric, "latest_stable_loader", lambda v, client=None: f"loader-for-{v}")
    monkeypatch.setattr(fabric, "latest_stable_installer", lambda client=None: "1.0.0")

    def download_launcher(mc, loader, installer, dest, client=None):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"fabric launcher")
        return dest

    monkeypatch.setattr(fabric, "download_server_launcher", download_launcher)
    monkeypatch.setattr(docker_manager, "ensure_image", lambda java_major: f"img:java{java_major}")
    monkeypatch.setattr(upgrades, "_image_present", lambda java_major: True)


def _server(client, name="modded"):
    return client.post(
        "/api/servers", json={"name": name, "mc_version": CURRENT, "loader": "fabric"}
    ).json()["id"]


def _install(client, sid, *slugs):
    for slug in slugs:
        resp = client.post(f"/api/servers/{sid}/mods", json={"project": slug})
        assert resp.status_code == 201, resp.text


# --------------------------------------------------------------------------
# Pre-flight
# --------------------------------------------------------------------------


def test_preflight_reports_java_bump_and_mod_plan(client, fake_upstreams):
    sid = _server(client)
    _install(client, sid, "sodium")
    report = client.post(
        f"/api/servers/{sid}/upgrade/preflight", json={"mc_version": TARGET}
    ).json()

    assert report["ready"] is True
    assert report["current_version"] == CURRENT and report["target_version"] == TARGET
    assert report["java"] == {
        "current": 21,
        "target": 22,
        "changed": True,
        "image_build_required": False,
    }
    assert report["loader_version"]["target"] == f"loader-for-{TARGET}"
    assert report["mods"][0]["status"] == "ok"
    assert report["mods"][0]["available"] == "0.6"


def test_preflight_resolves_latest_and_blocks_on_incompatible_mod(client, fake_upstreams):
    sid = _server(client)
    _install(client, sid, "sodium", "oldmod")
    report = client.post(f"/api/servers/{sid}/upgrade/preflight", json={}).json()

    assert report["target_version"] == TARGET  # "latest" resolved
    assert report["ready"] is False
    assert any("Stuck Mod" in b for b in report["blockers"])
    by_title = {m["title"]: m for m in report["mods"]}
    assert by_title["Stuck Mod"]["status"] == "blocked"
    assert by_title["Sodium"]["status"] == "ok"


def test_disabled_mod_warns_but_does_not_block(client, fake_upstreams):
    sid = _server(client)
    _install(client, sid, "sodium", "oldmod")
    client.patch(f"/api/servers/{sid}/mods/OLD1", json={"enabled": False})

    report = client.post(
        f"/api/servers/{sid}/upgrade/preflight", json={"mc_version": TARGET}
    ).json()
    assert report["ready"] is True
    assert report["blockers"] == []
    assert any("Stuck Mod" in w for w in report["warnings"])


def test_preflight_rejects_unknown_version(client, fake_upstreams):
    sid = _server(client)
    report = client.post(
        f"/api/servers/{sid}/upgrade/preflight", json={"mc_version": "9.9.9"}
    ).json()
    assert report["ready"] is False
    assert "9.9.9" in report["blockers"][0]


# --------------------------------------------------------------------------
# Upgrade
# --------------------------------------------------------------------------


def test_upgrade_blocked_returns_409_with_report(client, fake_upstreams, session):
    sid = _server(client)
    _install(client, sid, "oldmod")
    resp = client.post(f"/api/servers/{sid}/upgrade", json={"mc_version": TARGET})

    assert resp.status_code == 409
    assert resp.json()["detail"]["preflight"]["ready"] is False
    # Nothing moved.
    assert client.get(f"/api/servers/{sid}").json()["mc_version"] == CURRENT
    assert client.get(f"/api/servers/{sid}/backups").json() == []


def test_upgrade_happy_path(client, fake_upstreams, session, fake_docker):
    sid = _server(client)
    _install(client, sid, "sodium")
    resp = client.post(f"/api/servers/{sid}/upgrade", json={"mc_version": TARGET, "memory": "6G"})
    assert resp.status_code == 200, resp.text
    result = resp.json()

    assert result["from_version"] == CURRENT and result["to_version"] == TARGET
    assert result["java_major"] == 22
    assert result["loader_version"] == f"loader-for-{TARGET}"
    assert result["memory"] == "6G"
    assert result["mods"]["updated"] == [{"title": "Sodium", "version": "0.6"}]

    server = client.get(f"/api/servers/{sid}").json()
    assert server["mc_version"] == TARGET and server["java_major"] == 22
    assert server["memory"] == "6G"

    # Mandatory backup, taken on the OLD version so it's a real rollback point.
    backups = client.get(f"/api/servers/{sid}/backups").json()
    assert len(backups) == 1
    assert backups[0]["kind"] == "pre_upgrade" and backups[0]["mc_version"] == CURRENT

    # New jar on disk, old mod jar gone.
    inst = instances.get_instance(session, sid)
    from api.services.mods import mods_dir

    assert (mods_dir(inst) / "sodium-0.6.jar").exists()
    assert not (mods_dir(inst) / "sodium-0.5.jar").exists()
    # Container torn down so the new image/env apply on next start.
    assert ("remove_container", inst.name) in fake_docker["calls"]


def test_upgrade_installs_newly_required_dependency(client, fake_upstreams, session):
    sid = _server(client)
    _install(client, sid, "needsdep")
    assert len(client.get(f"/api/servers/{sid}/mods").json()) == 1

    result = client.post(f"/api/servers/{sid}/upgrade", json={"mc_version": TARGET}).json()
    assert result["mods"]["added"] == ["New Dep"]
    assert {m["title"] for m in client.get(f"/api/servers/{sid}/mods").json()} == {
        "Needs Dep",
        "New Dep",
    }


def test_force_disables_incompatible_mods(client, fake_upstreams, session):
    sid = _server(client)
    _install(client, sid, "sodium", "oldmod")
    result = client.post(
        f"/api/servers/{sid}/upgrade",
        json={"mc_version": TARGET, "disable_incompatible": True},
    ).json()

    assert result["mods"]["disabled"] == ["Stuck Mod"]
    by_id = {m["project_id"]: m for m in client.get(f"/api/servers/{sid}/mods").json()}
    assert by_id["OLD1"]["enabled"] is False
    assert by_id["SODIUM1"]["enabled"] is True

    inst = instances.get_instance(session, sid)
    from api.services.mods import mods_dir

    assert (mods_dir(inst) / "oldmod.jar.disabled").exists()


def test_failed_provision_rolls_the_row_back(client, fake_upstreams, session, monkeypatch):
    sid = _server(client)
    _install(client, sid, "sodium")

    def boom(mc, loader, installer, dest, client=None):
        raise OSError("fabric meta unreachable")

    monkeypatch.setattr(fabric, "download_server_launcher", boom)
    resp = client.post(f"/api/servers/{sid}/upgrade", json={"mc_version": TARGET})
    assert resp.status_code == 500
    assert "rolled back" in resp.json()["detail"]

    server = client.get(f"/api/servers/{sid}").json()
    assert server["mc_version"] == CURRENT and server["java_major"] == 21
    # The safety backup still exists to restore from.
    assert client.get(f"/api/servers/{sid}/backups").json()[0]["kind"] == "pre_upgrade"


def test_rollback_restores_version_and_mod_rows(client, fake_upstreams, session):
    sid = _server(client)
    _install(client, sid, "sodium")
    upgrade = client.post(f"/api/servers/{sid}/upgrade", json={"mc_version": TARGET}).json()
    assert client.get(f"/api/servers/{sid}/mods").json()[0]["version_number"] == "0.6"

    resp = client.post(f"/api/backups/{upgrade['backup_id']}/restore")
    assert resp.status_code == 200

    server = client.get(f"/api/servers/{sid}").json()
    assert server["mc_version"] == CURRENT and server["java_major"] == 21
    # The mod DB is back in sync with the jars inside the restored archive.
    mods_now = client.get(f"/api/servers/{sid}/mods").json()
    assert [(m["title"], m["version_number"]) for m in mods_now] == [("Sodium", "0.5")]


# --------------------------------------------------------------------------
# Health check
# --------------------------------------------------------------------------


@pytest.fixture
def fake_boot(monkeypatch):
    """Drive docker_manager.state/logs from a scripted sequence of ticks."""
    monkeypatch.setattr(upgrades, "POLL_INTERVAL", 0)
    monkeypatch.setattr(instances, "start_instance", lambda i: None)
    script: list[tuple[dict, str]] = []

    def state(instance):
        return script[min(len(script) - 1, state.tick)][0]

    def logs(instance, tail=200):
        entry = script[min(len(script) - 1, state.tick)][1]
        state.tick += 1
        return entry

    state.tick = 0
    monkeypatch.setattr(docker_manager, "state", state)
    monkeypatch.setattr(docker_manager, "logs", logs)
    return script


RUNNING = {
    "status": "running",
    "exit_code": 0,
    "restarting": False,
    "restart_count": 0,
    "oom_killed": False,
}


def test_health_check_healthy(client, fake_upstreams, fake_boot):
    sid = _server(client)
    fake_boot += [
        (RUNNING, "Starting minecraft server version 1.21.4"),
        (RUNNING, 'Done (12.345s)! For help, type "help"'),
    ]
    result = client.post(f"/api/servers/{sid}/health-check", json={"timeout": 30}).json()

    assert result["verdict"] == "healthy" and result["healthy"] is True
    assert result["findings"] == []
    assert "came up on MC" in result["summary"]


def test_health_check_crash_loop_diagnoses_and_stops(
    client, fake_upstreams, fake_boot, fake_docker, session
):
    sid = _server(client)
    crash = "Mixin apply failed: sodium.mixins.json\njava.lang.NoSuchMethodError: foo"
    fake_boot += [
        (RUNNING, "Starting minecraft server"),
        ({**RUNNING, "restart_count": 1, "exit_code": 1}, crash),
    ]
    result = client.post(
        f"/api/servers/{sid}/health-check", json={"timeout": 30, "rollback_backup_id": 7}
    ).json()

    assert result["verdict"] == "crash_loop" and result["healthy"] is False
    reasons = " ".join(f["reason"] for f in result["findings"])
    assert "mixins" in reasons and "game code that changed" in reasons
    assert result["rollback"]["backup_id"] == 7
    # A crash loop keeps restarting — we stop it so the operator can read this.
    inst = instances.get_instance(session, sid)
    assert ("stop", inst.name) in fake_docker["calls"]


def test_health_check_out_of_memory_recommends_more_heap(client, fake_upstreams, fake_boot):
    sid = _server(client)
    fake_boot += [
        (
            {**RUNNING, "status": "exited", "exit_code": 1, "oom_killed": True},
            "java.lang.OutOfMemoryError: Java heap space",
        ),
    ]
    result = client.post(f"/api/servers/{sid}/health-check", json={"timeout": 30}).json()

    assert result["healthy"] is False
    recs = " ".join(f["recommendation"] for f in result["findings"])
    assert "memory limit" in recs


def test_health_check_timeout_is_inconclusive(client, fake_upstreams, fake_boot):
    sid = _server(client)
    fake_boot.append((RUNNING, "Preparing spawn area: 42%"))
    result = client.post(f"/api/servers/{sid}/health-check", json={"timeout": 10}).json()

    assert result["verdict"] == "timeout" and result["healthy"] is False
    assert "hadn't finished starting" in result["summary"]
    assert result["findings"]  # falls back to "read the console"
