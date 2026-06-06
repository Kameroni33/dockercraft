import pytest

from api.clients import mojang
from api.services.players import format_uuid

KAM_UUID_RAW = "069a79f444e94726a5befca90e38aaf5"
KAM_UUID = "069a79f4-44e9-4726-a5be-fca90e38aaf5"


@pytest.fixture
def fake_mojang(monkeypatch):
    lookups: list[str] = []

    def lookup(username, client=None):
        lookups.append(username)
        if username.lower() == "notch":
            return {"id": KAM_UUID_RAW, "name": "Notch"}
        return None

    monkeypatch.setattr(mojang, "lookup_uuid", lookup)
    return lookups


def test_format_uuid():
    assert format_uuid(KAM_UUID_RAW) == KAM_UUID
    assert format_uuid(KAM_UUID) == KAM_UUID  # already dashed → unchanged


def test_cache_and_reuse(client, fake_mojang):
    resp = client.post("/players", json={"username": "notch"})
    assert resp.status_code == 200
    assert resp.json()["username"] == "Notch"  # canonical caps from Mojang
    assert resp.json()["uuid"] == KAM_UUID

    # Second resolve (any casing) must hit the DB, not Mojang.
    client.post("/players", json={"username": "NOTCH"})
    assert fake_mojang == ["notch"]
    assert len(client.get("/players").json()) == 1


def test_unknown_player_404(client, fake_mojang):
    assert client.post("/players", json={"username": "nope"}).status_code == 404


def _server(client):
    return client.post("/servers", json={"name": "wl-test", "mc_version": "1.21.1"}).json()["id"]


def test_whitelist_flow(client, fake_mojang):
    sid = _server(client)
    resp = client.post(f"/servers/{sid}/whitelist", json={"username": "notch"})
    assert resp.json() == [{"uuid": KAM_UUID, "name": "Notch"}]
    # Idempotent add
    resp = client.post(f"/servers/{sid}/whitelist", json={"username": "Notch"})
    assert len(resp.json()) == 1
    # Whitelisting also cached the player globally → visible for future servers
    assert client.get("/players").json()[0]["username"] == "Notch"

    assert client.delete(f"/servers/{sid}/whitelist/notch").status_code == 204
    assert client.get(f"/servers/{sid}/whitelist").json() == []
    assert client.delete(f"/servers/{sid}/whitelist/notch").status_code == 404


def test_ops_flow(client, fake_mojang):
    sid = _server(client)
    resp = client.post(f"/servers/{sid}/ops", json={"username": "notch", "level": 3})
    entry = resp.json()[0]
    assert entry["level"] == 3 and entry["bypassesPlayerLimit"] is False
    # Re-adding with a new level replaces, not duplicates
    resp = client.post(f"/servers/{sid}/ops", json={"username": "notch"})
    assert [e["level"] for e in resp.json()] == [4]
    assert client.delete(f"/servers/{sid}/ops/Notch").status_code == 204
