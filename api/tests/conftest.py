import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import api.models  # noqa: F401 — register tables
from api.config import settings
from api.db import get_session
from api.main import create_app
from api.services import docker_manager


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture
def fake_docker(monkeypatch):
    """Stub out every docker_manager call; record what was invoked."""
    calls: list[tuple] = []
    statuses: dict[str, str] = {}  # instance name -> status

    monkeypatch.setattr(
        docker_manager, "status", lambda i: statuses.get(i.name, "not_created")
    )
    for op in ("start", "stop", "restart", "remove_container", "recreate_container"):
        monkeypatch.setattr(
            docker_manager, op, lambda i, _op=op: calls.append((_op, i.name))
        )
    return {"calls": calls, "statuses": statuses}


@pytest.fixture
def fake_mojang(monkeypatch):
    """Stub Mojang profile lookups: only 'notch' exists. Records queries."""
    from api.clients import mojang

    lookups: list[str] = []

    def lookup(username, client=None):
        lookups.append(username)
        if username.lower() == "notch":
            return {"id": "069a79f444e94726a5befca90e38aaf5", "name": "Notch"}
        return None

    monkeypatch.setattr(mojang, "lookup_uuid", lookup)
    return lookups


@pytest.fixture
def client(session, tmp_path, monkeypatch, fake_docker):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(settings, "host_data_dir", None)
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    # No lifespan: init_db would touch the real engine; tests use the override.
    return TestClient(app)
