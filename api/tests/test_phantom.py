"""LAN discovery (phantom sidecar) toggle + docker_manager phantom plumbing."""

import json

import pytest

from api.config import settings
from api.models.instance import ServerInstance
from api.services import docker_manager, instances, ports


def _create(client, name="test-server"):
    resp = client.post("/api/servers", json={"name": name, "mc_version": "1.21.1"})
    assert resp.status_code == 201
    return resp.json()["id"]


def _add_bedrock(client, sid, host=19132):
    resp = client.put(
        f"/api/servers/{sid}/extra-ports",
        json=[{"host": host, "container": 19132, "proto": "udp"}],
    )
    assert resp.status_code == 200


def _bedrock_host(client, sid) -> int | None:
    extras = json.loads(client.get(f"/api/servers/{sid}").json()["extra_ports_json"])
    return next(
        (e["host"] for e in extras if e["proto"] == "udp" and e["container"] == 19132),
        None,
    )


# --- toggle endpoint ---------------------------------------------------------


def test_defaults_off_and_in_read(client):
    sid = _create(client)
    assert client.get(f"/api/servers/{sid}").json()["lan_discovery"] is False


def test_enable_without_bedrock_port_409(client):
    sid = _create(client)
    resp = client.put(f"/api/servers/{sid}/lan-discovery", json={"enabled": True})
    assert resp.status_code == 409
    assert "Geyser" in resp.json()["detail"]


def test_enable_remaps_19132(client, fake_docker):
    sid = _create(client)
    _add_bedrock(client, sid, host=19132)
    fake_docker["calls"].clear()

    resp = client.put(f"/api/servers/{sid}/lan-discovery", json={"enabled": True})
    assert resp.status_code == 200
    assert resp.json()["lan_discovery"] is True
    # 19132 belongs to phantom now; the direct Bedrock port moved into the remap range.
    assert _bedrock_host(client, sid) == settings.bedrock_remap_range[0]
    assert ("recreate_container", "test-server") in fake_docker["calls"]


def test_enable_with_custom_port_skips_remap(client, fake_docker):
    sid = _create(client)
    _add_bedrock(client, sid, host=19140)
    fake_docker["calls"].clear()

    resp = client.put(f"/api/servers/{sid}/lan-discovery", json={"enabled": True})
    assert resp.status_code == 200
    assert _bedrock_host(client, sid) == 19140
    assert ("recreate_container", "test-server") not in fake_docker["calls"]


def test_enable_starts_phantom_only_when_running(client, fake_docker):
    sid = _create(client)
    _add_bedrock(client, sid)
    client.put(f"/api/servers/{sid}/lan-discovery", json={"enabled": True})
    assert ("start_phantom", "test-server") not in fake_docker["calls"]  # stopped

    client.put(f"/api/servers/{sid}/lan-discovery", json={"enabled": False})
    fake_docker["statuses"]["test-server"] = "running"
    client.put(f"/api/servers/{sid}/lan-discovery", json={"enabled": True})
    assert ("start_phantom", "test-server") in fake_docker["calls"]


def test_second_instance_409(client, fake_docker):
    first = _create(client, "first")
    _add_bedrock(client, first)
    second = _create(client, "second")
    _add_bedrock(client, second, host=19140)

    assert (
        client.put(f"/api/servers/{first}/lan-discovery", json={"enabled": True}).status_code
        == 200
    )
    resp = client.put(f"/api/servers/{second}/lan-discovery", json={"enabled": True})
    assert resp.status_code == 409
    assert "first" in resp.json()["detail"]


def test_disable_removes_phantom_keeps_port(client, fake_docker):
    sid = _create(client)
    _add_bedrock(client, sid)
    client.put(f"/api/servers/{sid}/lan-discovery", json={"enabled": True})

    resp = client.put(f"/api/servers/{sid}/lan-discovery", json={"enabled": False})
    assert resp.status_code == 200
    assert resp.json()["lan_discovery"] is False
    assert ("remove_phantom", "test-server") in fake_docker["calls"]
    # Remap is deliberately not reverted (avoids another recreate / re-conflict).
    assert _bedrock_host(client, sid) == settings.bedrock_remap_range[0]


def test_start_phantom_failure_rolls_back_flag(client, session, fake_docker, monkeypatch):
    sid = _create(client)
    _add_bedrock(client, sid)
    fake_docker["statuses"]["test-server"] = "running"

    def boom(instance):
        raise RuntimeError("image build failed")

    monkeypatch.setattr(docker_manager, "start_phantom", boom)
    instance = instances.get_instance(session, sid)
    with pytest.raises(RuntimeError):
        instances.set_lan_discovery(session, instance, True)
    assert instances.get_instance(session, sid).lan_discovery is False


# --- docker_manager plumbing -------------------------------------------------


def _instance(**overrides) -> ServerInstance:
    defaults = dict(name="unit", mc_version="1.21.1", game_port=25565, rcon_port=25665)
    return ServerInstance(**{**defaults, **overrides})


def test_bedrock_host_port_parsing():
    extras = json.dumps(
        [
            {"host": 8123, "container": 8123, "proto": "tcp"},
            {"host": 19133, "container": 19132, "proto": "udp"},
        ]
    )
    assert docker_manager.bedrock_host_port(_instance(extra_ports_json=extras)) == 19133
    assert docker_manager.bedrock_host_port(_instance()) is None
    # TCP on 19132 is not a Bedrock mapping
    tcp_only = json.dumps([{"host": 19132, "container": 19132, "proto": "tcp"}])
    assert docker_manager.bedrock_host_port(_instance(extra_ports_json=tcp_only)) is None


def test_phantom_config_shape():
    extras = json.dumps([{"host": 19133, "container": 19132, "proto": "udp"}])
    cfg = docker_manager.phantom_config(_instance(extra_ports_json=extras))
    assert cfg["network_mode"] == "host"
    assert cfg["command"] == ["-server", "127.0.0.1:19133"]
    assert cfg["name"] == "dockercraft-phantom-unit"
    assert cfg["restart_policy"] == {"Name": "unless-stopped"}
    assert cfg["labels"] == {docker_manager.PHANTOM_LABEL: "unit"}


def test_phantom_config_requires_bedrock_port():
    with pytest.raises(ValueError):
        docker_manager.phantom_config(_instance())


def test_allocate_bedrock_remap_port_skips_used(client, session):
    sid = _create(client)
    _add_bedrock(client, sid, host=settings.bedrock_remap_range[0])  # occupy 19133
    port = ports.allocate_bedrock_remap_port(session)
    assert port == settings.bedrock_remap_range[0] + 1


def test_lifecycle_hooks_touch_phantom(monkeypatch):
    """start()/stop()/remove_container() drive the sidecar alongside the MC container."""
    extras = json.dumps([{"host": 19133, "container": 19132, "proto": "udp"}])
    instance = _instance(extra_ports_json=extras, lan_discovery=True)
    calls: list[str] = []

    class FakeContainer:
        def start(self):
            calls.append("mc_start")

        def stop(self, timeout=None):
            calls.append("mc_stop")

        def remove(self):
            calls.append("mc_remove")

    monkeypatch.setattr(docker_manager, "get_container", lambda i: FakeContainer())
    monkeypatch.setattr(docker_manager, "start_phantom", lambda i: calls.append("phantom_start"))
    monkeypatch.setattr(docker_manager, "stop_phantom", lambda i: calls.append("phantom_stop"))
    monkeypatch.setattr(
        docker_manager, "remove_phantom", lambda i: calls.append("phantom_remove")
    )

    docker_manager.start(instance)
    assert calls == ["mc_start", "phantom_start"]

    calls.clear()
    docker_manager.stop(instance)
    assert calls == ["phantom_stop", "mc_stop"]

    calls.clear()
    docker_manager.remove_container(instance)
    assert calls == ["phantom_remove", "mc_stop", "mc_remove"]

    # without the flag, start() leaves phantom alone
    calls.clear()
    docker_manager.start(_instance(extra_ports_json=extras, lan_discovery=False))
    assert calls == ["mc_start"]
