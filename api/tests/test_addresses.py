from api.config import settings
from api.services import network


def test_addresses(client, fake_docker, monkeypatch):
    monkeypatch.setattr(settings, "lan_ip", None)  # a repo-root .env may set this
    monkeypatch.setattr(settings, "public_ip", None)
    monkeypatch.setattr(network, "detect_lan_ip", lambda: "192.168.1.50")
    monkeypatch.setattr(network, "public_ip", lambda: "203.0.113.7")
    client.post("/api/servers", json={"name": "one", "mc_version": "1.21.1"})
    client.post("/api/servers", json={"name": "two", "mc_version": "1.21.1"})
    fake_docker["statuses"]["one"] = "running"

    body = client.get("/api/addresses").json()
    assert body["lan_ip"] == "192.168.1.50"
    assert body["public_ip"] == "203.0.113.7"
    one, two = body["servers"]
    assert one["address"] == f"192.168.1.50:{settings.game_port_range[0]}"
    assert one["public_address"] == f"203.0.113.7:{settings.game_port_range[0]}"
    assert one["status"] == "running" and two["status"] == "not_created"
    assert str(two["game_port"]) in two["port_forward_hint"]


def test_addresses_without_internet(client, monkeypatch):
    monkeypatch.setattr(settings, "public_ip", None)
    monkeypatch.setattr(network, "public_ip", lambda: None)
    client.post("/api/servers", json={"name": "off", "mc_version": "1.21.1"})
    body = client.get("/api/addresses").json()
    assert body["public_ip"] is None
    assert body["servers"][0]["public_address"] is None


def test_ip_overrides(client, monkeypatch):
    monkeypatch.setattr(settings, "lan_ip", "10.0.0.99")
    monkeypatch.setattr(settings, "public_ip", "play.example.com")  # ddns hostname works too
    body = client.get("/api/addresses").json()
    assert body["lan_ip"] == "10.0.0.99"
    assert body["public_ip"] == "play.example.com"


def test_public_ip_caching(monkeypatch):
    calls = []
    monkeypatch.setattr(settings, "public_ip", None)
    monkeypatch.setattr(network, "_public_ip_cache", None)
    monkeypatch.setattr(network, "detect_public_ip", lambda: calls.append(1) or "1.2.3.4")
    assert network.public_ip() == "1.2.3.4"
    assert network.public_ip() == "1.2.3.4"
    assert len(calls) == 1  # second hit served from cache
