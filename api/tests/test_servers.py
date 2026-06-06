from api.config import settings
from api.services import ports
from api.services.ports import PortsExhaustedError


def _create(client, name="test-server", **overrides):
    body = {"name": name, "mc_version": "1.21.1", **overrides}
    return client.post("/servers", json=body)


def test_create_and_get(client):
    resp = _create(client)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "test-server"
    assert data["game_port"] == settings.game_port_range[0]
    assert data["rcon_port"] == settings.rcon_port_range[0]
    assert data["status"] == "not_created"
    assert "rcon_password" not in data  # secret stays out of API responses

    assert client.get(f"/servers/{data['id']}").json()["name"] == "test-server"
    assert (settings.instances_dir / "test-server").is_dir()


def test_port_allocation_skips_used(client):
    a = _create(client, "alpha").json()
    b = _create(client, "beta").json()
    assert b["game_port"] == a["game_port"] + 1
    assert b["rcon_port"] == a["rcon_port"] + 1


def test_duplicate_name_409(client):
    assert _create(client, "dup").status_code == 201
    assert _create(client, "dup").status_code == 409


def test_invalid_name_422(client):
    for bad in ("Has Caps", "-leading-dash", "under_score", ""):
        assert _create(client, bad).status_code == 422, bad


def test_lifecycle_endpoints(client, fake_docker):
    sid = _create(client).json()["id"]
    for op in ("start", "stop", "restart"):
        assert client.post(f"/servers/{sid}/{op}").status_code == 200
    assert fake_docker["calls"] == [
        ("start", "test-server"),
        ("stop", "test-server"),
        ("restart", "test-server"),
    ]


def test_status_reflected(client, fake_docker):
    sid = _create(client).json()["id"]
    fake_docker["statuses"]["test-server"] = "running"
    assert client.get(f"/servers/{sid}").json()["status"] == "running"


def test_delete(client, fake_docker):
    sid = _create(client).json()["id"]
    assert client.delete(f"/servers/{sid}?delete_data=true").status_code == 204
    assert ("remove_container", "test-server") in fake_docker["calls"]
    assert client.get(f"/servers/{sid}").status_code == 404
    assert not (settings.instances_dir / "test-server").exists()


def test_missing_instance_404(client):
    assert client.get("/servers/999").status_code == 404
    assert client.post("/servers/999/start").status_code == 404


def test_ports_exhausted(client, session, monkeypatch):
    monkeypatch.setattr(
        settings, "game_port_range", (25565, 25565)
    )
    assert _create(client, "only").status_code == 201
    try:
        ports.allocate_ports(session)
        raise AssertionError("expected PortsExhaustedError")
    except PortsExhaustedError:
        pass
