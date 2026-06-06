from datetime import UTC, datetime, timedelta

from api import paths
from api.services import instances, scheduler

NOW = datetime.now(UTC).replace(tzinfo=None)


def _enabled_server(client, session, name, running=True, fake_docker=None):
    sid = client.post("/api/servers", json={"name": name, "mc_version": "1.21.1"}).json()["id"]
    client.put(
        f"/api/servers/{sid}/backup-policy",
        json={"enabled": True, "interval_hours": 6, "keep_count": 3, "keep_days": 0},
    )
    (paths.instance_dir(name) / "world").mkdir(parents=True, exist_ok=True)
    (paths.instance_dir(name) / "world/level.dat").write_bytes(b"x")
    if running and fake_docker is not None:
        fake_docker["statuses"][name] = "running"
    return instances.get_instance(session, sid)


def test_first_sweep_backs_up(client, session, fake_docker, fake_rcon):
    _enabled_server(client, session, "sched", fake_docker=fake_docker)
    created = scheduler.run_due_backups(session, now=NOW)
    assert [b.instance_name for b in created] == ["sched"]
    # Immediately due again? No — interval not elapsed.
    assert scheduler.run_due_backups(session, now=NOW + timedelta(hours=1)) == []
    # After the interval: due.
    assert len(scheduler.run_due_backups(session, now=NOW + timedelta(hours=7))) == 1


def test_stopped_and_disabled_skipped(client, session, fake_docker):
    _enabled_server(client, session, "stopped", running=False, fake_docker=fake_docker)
    resp = client.post("/api/servers", json={"name": "nopolicy", "mc_version": "1.21.1"})
    sid = resp.json()["id"]
    fake_docker["statuses"]["nopolicy"] = "running"
    assert scheduler.run_due_backups(session, now=NOW) == []
    assert client.get(f"/api/servers/{sid}/backups").json() == []


def test_sweep_prunes(client, session, fake_docker, fake_rcon):
    inst = _enabled_server(client, session, "prune-me", fake_docker=fake_docker)
    from api.services import backups

    for _ in range(5):
        backups.create_backup(session, inst, kind="scheduled")
    # Make them look old so the next sweep is due
    for b in backups.list_backups(session, inst.id):
        b.created_at = NOW - timedelta(hours=10)
        session.add(b)
    session.commit()

    scheduler.run_due_backups(session, now=NOW)
    remaining = backups.list_backups(session, inst.id)
    assert len(remaining) == 3  # keep_count enforced after the new backup
