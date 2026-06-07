import tarfile
from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import select

from api import paths
from api.config import settings
from api.models.backup import Backup
from api.services import backups, instances


def _server(client, name="bk"):
    return client.post("/api/servers", json={"name": name, "mc_version": "1.21.1"}).json()["id"]


def _populate(name: str) -> None:
    d = paths.instance_dir(name)
    (d / "world").mkdir(parents=True, exist_ok=True)
    (d / "world/level.dat").write_bytes(b"WORLDDATA")
    (d / "server.properties").write_text("motd=backup me\n")
    (d / "logs").mkdir(exist_ok=True)
    (d / "logs/latest.log").write_text("noise")


def test_cold_backup_roundtrip(client, session):
    sid = _server(client)
    _populate("bk")
    resp = client.post(f"/api/servers/{sid}/backups", json={"note": "before the creeper"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["kind"] == "manual" and data["note"] == "before the creeper"
    assert data["mc_version"] == "1.21.1"  # provisioning snapshot captured
    assert data["size_bytes"] > 0

    archive = settings.backups_dir / data["filename"]
    with tarfile.open(archive) as tar:
        names = tar.getnames()
    assert "world/level.dat" in names and "server.properties" in names
    assert not any(n.startswith("logs") for n in names)  # logs excluded

    assert len(client.get(f"/api/servers/{sid}/backups").json()) == 1
    assert client.delete(f"/api/backups/{data['id']}").status_code == 204
    assert not archive.exists()


def test_hot_backup_rcon_choreography(client, session, fake_docker, fake_rcon):
    sid = _server(client)
    _populate("bk")
    fake_docker["statuses"]["bk"] = "running"
    assert client.post(f"/api/servers/{sid}/backups", json={}).status_code == 201
    assert fake_rcon == ["save-off", "save-all flush", "save-on"]


def test_save_on_even_if_archive_fails(client, session, fake_docker, fake_rcon, monkeypatch):
    sid = _server(client)
    instance = instances.get_instance(session, sid)
    fake_docker["statuses"]["bk"] = "running"
    monkeypatch.setattr(backups, "_archive", lambda i, k: 1 / 0)
    with pytest.raises(ZeroDivisionError):
        backups.create_backup(session, instance)
    assert fake_rcon[-1] == "save-on"  # autosave always restored


def test_prune_policy(client, session):
    sid = _server(client)
    _populate("bk")
    for _ in range(4):
        client.post(f"/api/servers/{sid}/backups", json={})  # manual — exempt
    inst = instances.get_instance(session, sid)
    for _ in range(5):
        backups.create_backup(session, inst, kind="scheduled")
    old = backups.create_backup(session, inst, kind="scheduled")
    old.created_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=30)
    session.add(old)
    session.commit()

    resp = client.put(
        f"/api/servers/{sid}/backup-policy",
        json={"enabled": True, "interval_hours": 6, "keep_count": 3, "keep_days": 7},
    )
    assert resp.status_code == 200
    assert resp.json()["pruned"] == 3  # 5+1 scheduled -> keep 3 newest, old one age-pruned

    remaining = session.exec(select(Backup)).all()
    kinds = [b.kind for b in remaining]
    assert kinds.count("manual") == 4  # manual untouched
    assert kinds.count("scheduled") == 3
    # pruned files actually gone from disk
    for b in remaining:
        assert backups.backup_path(b).exists()


def test_backup_survives_instance_deletion(client, session):
    sid = _server(client)
    _populate("bk")
    bid = client.post(f"/api/servers/{sid}/backups", json={}).json()["id"]
    client.delete(f"/api/servers/{sid}?delete_data=true")
    all_backups = client.get("/api/backups").json()
    assert [b["id"] for b in all_backups] == [bid]
    assert all_backups[0]["instance_name"] == "bk"
    assert backups.backup_path(session.get(Backup, bid)).exists()


def test_backup_response_includes_host_path(client, monkeypatch):
    from pathlib import Path

    monkeypatch.setattr(settings, "host_data_dir", Path("/srv/dockercraft/data"))
    sid = _server(client, "pathy")
    _populate("pathy")
    data = client.post(f"/api/servers/{sid}/backups", json={}).json()
    # Path is the HOST view (what a human can open), not the manager's view
    assert data["path"] == f"/srv/dockercraft/data/backups/{data['filename']}"
    assert client.get(f"/api/servers/{sid}/backups").json()[0]["path"] == data["path"]
