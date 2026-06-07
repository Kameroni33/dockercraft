from api.services.players import format_uuid

KAM_UUID_RAW = "069a79f444e94726a5befca90e38aaf5"
KAM_UUID = "069a79f4-44e9-4726-a5be-fca90e38aaf5"


def test_format_uuid():
    assert format_uuid(KAM_UUID_RAW) == KAM_UUID
    assert format_uuid(KAM_UUID) == KAM_UUID  # already dashed → unchanged


def test_cache_and_reuse(client, fake_mojang):
    resp = client.post("/api/players", json={"username": "notch"})
    assert resp.status_code == 200
    assert resp.json()["username"] == "Notch"  # canonical caps from Mojang
    assert resp.json()["uuid"] == KAM_UUID

    # Second resolve (any casing) must hit the DB, not Mojang.
    client.post("/api/players", json={"username": "NOTCH"})
    assert fake_mojang == ["notch"]
    assert len(client.get("/api/players").json()) == 1


def test_unknown_player_404(client, fake_mojang):
    assert client.post("/api/players", json={"username": "nope"}).status_code == 404


def _server(client):
    resp = client.post("/api/servers", json={"name": "wl-test", "mc_version": "1.21.1"})
    return resp.json()["id"]


def test_whitelist_flow(client, fake_mojang):
    sid = _server(client)
    resp = client.post(f"/api/servers/{sid}/whitelist", json={"username": "notch"})
    assert resp.json() == [{"uuid": KAM_UUID, "name": "Notch"}]
    # Idempotent add
    resp = client.post(f"/api/servers/{sid}/whitelist", json={"username": "Notch"})
    assert len(resp.json()) == 1
    # Whitelisting also cached the player globally → visible for future servers
    assert client.get("/api/players").json()[0]["username"] == "Notch"

    assert client.delete(f"/api/servers/{sid}/whitelist/notch").status_code == 204
    assert client.get(f"/api/servers/{sid}/whitelist").json() == []
    assert client.delete(f"/api/servers/{sid}/whitelist/notch").status_code == 404


def test_ops_flow(client, fake_mojang):
    sid = _server(client)
    resp = client.post(f"/api/servers/{sid}/ops", json={"username": "notch", "level": 3})
    entry = resp.json()[0]
    assert entry["level"] == 3 and entry["bypassesPlayerLimit"] is False
    # Re-adding with a new level replaces, not duplicates
    resp = client.post(f"/api/servers/{sid}/ops", json={"username": "notch"})
    assert [e["level"] for e in resp.json()] == [4]
    assert client.delete(f"/api/servers/{sid}/ops/Notch").status_code == 204


BEDROCK_XUID = 2535416061927855


def test_floodgate_uuid_format():
    from api.clients.geysermc import floodgate_uuid

    fg = floodgate_uuid(BEDROCK_XUID)
    assert fg.startswith("00000000-0000-0000-")  # high 64 bits are zero
    assert int(fg.replace("-", ""), 16) == BEDROCK_XUID  # low bits ARE the xuid


def test_bedrock_whitelist_flow(client, monkeypatch):
    from api.clients import geysermc

    lookups = []

    def fake_xuid(gamertag, client=None):
        lookups.append(gamertag)
        return BEDROCK_XUID if gamertag == "CoolKid123" else None

    monkeypatch.setattr(geysermc, "lookup_xuid", fake_xuid)

    resp = client.post("/api/players", json={"username": ".CoolKid123"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["username"] == ".CoolKid123"
    assert body["platform"] == "bedrock"
    assert int(body["uuid"].replace("-", ""), 16) == BEDROCK_XUID

    # Cached on second resolve — no second API hit
    client.post("/api/players", json={"username": ".coolkid123"})
    assert lookups == ["CoolKid123"]

    # Whitelisting via the same dot-prefix path writes the floodgate identity
    resp = client.post("/api/servers", json={"name": "bedrock-wl", "mc_version": "1.21.1"})
    sid = resp.json()["id"]
    entries = client.post(f"/api/servers/{sid}/whitelist", json={"username": ".CoolKid123"}).json()
    assert entries == [{"uuid": body["uuid"], "name": ".CoolKid123"}]

    # Unknown gamertag -> 404
    assert client.post("/api/players", json={"username": ".NoSuchTag"}).status_code == 404


def test_bedrock_xuid_escape_hatch(client):
    resp = client.post("/api/players", json={"username": f".{BEDROCK_XUID}"})
    assert resp.status_code == 200  # no API needed — digits = raw XUID
    assert int(resp.json()["uuid"].replace("-", ""), 16) == BEDROCK_XUID


def test_bedrock_not_in_cache_message(client, monkeypatch):
    from api.clients import geysermc

    monkeypatch.setattr(geysermc, "lookup_xuid", lambda g, client=None: None)
    resp = client.post("/api/players", json={"username": ".BrandNewPlayer"})
    assert resp.status_code == 404
    assert "XUID" in resp.json()["detail"]  # error guides toward the workaround


def test_whitelist_change_reloads_running_server(client, fake_mojang, fake_docker, fake_rcon):
    resp = client.post("/api/servers", json={"name": "live-wl", "mc_version": "1.21.1"})
    sid = resp.json()["id"]

    # Stopped server: no RCON traffic
    client.post(f"/api/servers/{sid}/whitelist", json={"username": "notch"})
    assert fake_rcon == []

    # Running server: every whitelist mutation triggers a reload
    fake_docker["statuses"]["live-wl"] = "running"
    client.delete(f"/api/servers/{sid}/whitelist/notch")
    client.post(f"/api/servers/{sid}/whitelist", json={"username": "notch"})
    assert fake_rcon == ["whitelist reload", "whitelist reload"]
