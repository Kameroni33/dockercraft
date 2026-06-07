import pytest
from fastapi.testclient import TestClient

from api.config import settings
from api.db import get_session
from api.main import create_app
from api.services import auth


@pytest.fixture
def raw_client(session, tmp_path, monkeypatch):
    """TestClient WITHOUT the auth override — exercises the real guard."""
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(auth, "_secret", None)  # fresh secret.key per test
    monkeypatch.setattr(auth, "COOKIE_NAME", auth.COOKIE_NAME)  # no-op, clarity
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app)


CREDS = {"username": "kameron", "password": "correct-horse-battery"}


def test_first_run_setup_and_protection(raw_client):
    # Fresh install: setup required, everything protected
    status = raw_client.get("/api/auth/status").json()
    assert status == {"setup_required": True, "authenticated": False}
    assert raw_client.get("/api/servers").status_code == 401
    assert raw_client.get("/api/addresses").status_code == 401
    assert raw_client.get("/api/health").status_code == 200  # liveness stays open

    # Create admin -> auto-logged-in via cookie
    assert raw_client.post("/api/auth/setup", json=CREDS).status_code == 200
    assert raw_client.get("/api/auth/status").json() == {
        "setup_required": False,
        "authenticated": True,
    }
    assert raw_client.get("/api/servers").status_code == 200

    # Setup endpoint is one-shot
    assert raw_client.post("/api/auth/setup", json=CREDS).status_code == 409


def test_login_logout_cycle(raw_client):
    raw_client.post("/api/auth/setup", json=CREDS)
    raw_client.post("/api/auth/logout")
    assert raw_client.get("/api/servers").status_code == 401

    bad = raw_client.post("/api/auth/login", json={**CREDS, "password": "wrong-password"})
    assert bad.status_code == 401
    assert raw_client.post("/api/auth/login", json=CREDS).status_code == 200
    assert raw_client.get("/api/servers").status_code == 200


def test_short_password_rejected(raw_client):
    resp = raw_client.post("/api/auth/setup", json={"username": "k", "password": "short"})
    assert resp.status_code == 422


def test_tampered_and_expired_tokens(raw_client, tmp_path):
    raw_client.post("/api/auth/setup", json=CREDS)
    good = auth.make_token("kameron")
    assert auth.verify_token(good) == "kameron"
    assert auth.verify_token(good[:-2] + "ff") is None  # tampered signature
    assert auth.verify_token("kameron:123:deadbeef") is None  # forged
    assert auth.verify_token(auth.make_token("kameron", ttl=-10)) is None  # expired
    assert auth.verify_token(None) is None


def test_password_hash_roundtrip():
    stored = auth.hash_password("hunter2hunter2")
    assert auth.verify_password("hunter2hunter2", stored)
    assert not auth.verify_password("hunter3hunter3", stored)
    assert not auth.verify_password("x", "garbage")
