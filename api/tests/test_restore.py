from api import paths


def _server(client, name="rst"):
    return client.post(
        "/servers", json={"name": name, "mc_version": "1.21.1", "loader": "fabric"}
    ).json()["id"]


def _world_file(name):
    d = paths.instance_dir(name)
    (d / "world").mkdir(parents=True, exist_ok=True)
    return d / "world/level.dat"


def test_restore_in_place(client, session):
    sid = _server(client)
    level = _world_file("rst")
    level.write_bytes(b"GOOD STATE")
    bid = client.post(f"/servers/{sid}/backups", json={"note": "good"}).json()["id"]

    level.write_bytes(b"CREEPER GRIEFED EVERYTHING")
    resp = client.post(f"/backups/{bid}/restore")
    assert resp.status_code == 200
    assert resp.json()["kind"] == "pre_restore"  # safety backup returned
    assert level.read_bytes() == b"GOOD STATE"

    # The griefed state is itself recoverable from the safety backup
    safety_id = resp.json()["id"]
    client.post(f"/backups/{safety_id}/restore")
    assert level.read_bytes() == b"CREEPER GRIEFED EVERYTHING"


def test_restore_running_server_stops_and_restarts(client, session, fake_docker, fake_rcon):
    sid = _server(client)
    _world_file("rst").write_bytes(b"x")
    bid = client.post(f"/servers/{sid}/backups", json={}).json()["id"]
    fake_docker["statuses"]["rst"] = "running"
    client.post(f"/backups/{bid}/restore")
    ops = [op for op, name in fake_docker["calls"] if name == "rst"]
    assert ops == ["stop", "remove_container", "start"]


def test_clone_to_new_instance(client, session):
    sid = _server(client)
    _world_file("rst").write_bytes(b"CLONE ME")
    bid = client.post(f"/servers/{sid}/backups", json={}).json()["id"]

    resp = client.post(f"/backups/{bid}/clone", json={"name": "rst-copy"})
    assert resp.status_code == 201
    data = resp.json()
    src = client.get(f"/servers/{sid}").json()
    assert data["name"] == "rst-copy"
    assert data["loader"] == "fabric" and data["mc_version"] == "1.21.1"
    assert data["game_port"] != src["game_port"]  # fresh ports
    assert (paths.instance_dir("rst-copy") / "world/level.dat").read_bytes() == b"CLONE ME"

    assert client.post(f"/backups/{bid}/clone", json={"name": "rst-copy"}).status_code == 409


def test_orphan_backup_restore_409_but_clone_works(client, session):
    sid = _server(client)
    _world_file("rst").write_bytes(b"ORPHANED WORLD")
    bid = client.post(f"/servers/{sid}/backups", json={}).json()["id"]
    client.delete(f"/servers/{sid}?delete_data=true")

    assert client.post(f"/backups/{bid}/restore").status_code == 409
    resp = client.post(f"/backups/{bid}/clone", json={"name": "phoenix"})
    assert resp.status_code == 201
    assert (paths.instance_dir("phoenix") / "world/level.dat").read_bytes() == b"ORPHANED WORLD"
