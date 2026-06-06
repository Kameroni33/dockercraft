from api import paths


def _create(client, name="props-test"):
    return client.post("/servers", json={"name": name, "mc_version": "1.21.1"}).json()


def test_properties_roundtrip(client):
    sid = _create(client)["id"]
    resp = client.patch(
        f"/servers/{sid}/properties",
        json={"motd": "Brother SMP", "max-players": 12, "white-list": True},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["restart_required"] is False  # not running (fake docker)
    props = body["properties"]
    assert props["motd"] == "Brother SMP"
    assert props["max-players"] == "12"
    assert props["white-list"] == "true"  # JSON bool -> properties format
    # Managed keys enforced on every write:
    assert props["server-port"] == "25565"
    assert props["enable-rcon"] == "true"

    assert client.get(f"/servers/{sid}/properties").json()["motd"] == "Brother SMP"


def test_managed_keys_rejected(client):
    sid = _create(client)["id"]
    resp = client.patch(f"/servers/{sid}/properties", json={"server-port": 1234})
    assert resp.status_code == 422
    assert "managed by dockercraft" in resp.json()["detail"]


def test_survives_mc_style_rewrite(client):
    """MC rewrites server.properties with comments; our parser must cope."""
    sid = _create(client)["id"]
    client.patch(f"/servers/{sid}/properties", json={"motd": "hi"})
    path = paths.instance_dir("props-test") / "server.properties"
    path.write_text("#Minecraft server properties\n#Sat Jun 06\nmotd=hi\nlevel-seed=\n")
    props = client.get(f"/servers/{sid}/properties").json()
    assert props == {"motd": "hi", "level-seed": ""}


def test_start_reasserts_managed(client, fake_docker):
    sid = _create(client)["id"]
    path = paths.instance_dir("props-test") / "server.properties"
    path.write_text("enable-rcon=false\nmotd=keep me\n")  # simulate manual tampering
    client.post(f"/servers/{sid}/start")
    text = path.read_text()
    assert "enable-rcon=true" in text and "motd=keep me" in text
    assert ("start", "props-test") in fake_docker["calls"]
