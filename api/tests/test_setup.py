import httpx
import pytest

from api import paths
from api.clients import mojang
from api.config import settings
from api.tests.test_installers import _handler  # fake piston-meta/fabric routes


@pytest.fixture
def http(monkeypatch):
    client = httpx.Client(transport=httpx.MockTransport(_handler))
    monkeypatch.setattr(mojang, "make_client", lambda: client)
    monkeypatch.setattr(mojang, "latest_release", lambda client=None: "1.21.1")
    return client


def _setup(client, **overrides):
    body = {
        "name": "wizard",
        "mc_version": "1.21.1",
        "loader": "fabric",
        "accept_eula": True,
        **overrides,
    }
    return client.post("/api/servers/setup", json=body)


def test_eula_required(client, http):
    resp = _setup(client, accept_eula=False)
    assert resp.status_code == 422
    assert "EULA" in resp.json()["detail"]
    assert client.get("/api/servers").json() == []  # nothing left behind


def test_full_setup(client, http, fake_mojang):
    resp = _setup(
        client,
        mc_version="latest",
        properties={"motd": "Brother SMP", "max-players": 8},
        whitelist=["notch"],
        ops=["notch"],
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["mc_version"] == "1.21.1"  # "latest" resolved
    assert data["java_major"] == 21
    assert data["loader_version"] == "0.15.11"  # latest stable from fabric meta

    inst_dir = paths.instance_dir("wizard")
    assert (inst_dir / "fabric-launcher.jar").exists()
    assert (inst_dir / "eula.txt").read_text() == "eula=true\n"

    props = client.get(f"/api/servers/{data['id']}/properties").json()
    assert props["motd"] == "Brother SMP"
    assert props["white-list"] == "true"  # auto-enabled because whitelist given
    assert props["enable-rcon"] == "true"  # managed keys present

    assert client.get(f"/api/servers/{data['id']}/whitelist").json()[0]["name"] == "Notch"
    assert client.get(f"/api/servers/{data['id']}/ops").json()[0]["level"] == 4


def test_setup_with_start(client, http, fake_docker):
    resp = _setup(client, start=True)
    assert resp.status_code == 201
    assert ("start", "wizard") in fake_docker["calls"]


def test_failed_provision_rolls_back(client, http, monkeypatch, fake_docker):
    from api.services import provision

    def boom(instance):
        raise RuntimeError("download exploded")

    monkeypatch.setattr(provision, "provision_instance", boom)
    with pytest.raises(RuntimeError):
        _setup(client)
    assert client.get("/api/servers").json() == []
    assert not paths.instance_dir("wizard").exists()
    assert not (settings.instances_dir / "wizard").exists()


def test_unknown_whitelist_user_rolls_back(client, http, fake_mojang):
    resp = _setup(client, whitelist=["definitely-not-real"])
    assert resp.status_code == 422
    assert client.get("/api/servers").json() == []
