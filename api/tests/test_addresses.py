from api.config import settings
from api.services import network


def test_addresses(client, fake_docker, monkeypatch):
    monkeypatch.setattr(settings, "lan_ip", None)  # a repo-root .env may set this
    monkeypatch.setattr(network, "detect_lan_ip", lambda: "192.168.1.50")
    client.post("/api/servers", json={"name": "one", "mc_version": "1.21.1"})
    client.post("/api/servers", json={"name": "two", "mc_version": "1.21.1"})
    fake_docker["statuses"]["one"] = "running"

    body = client.get("/api/addresses").json()
    assert body["lan_ip"] == "192.168.1.50"
    one, two = body["servers"]
    assert one["address"] == f"192.168.1.50:{settings.game_port_range[0]}"
    assert one["status"] == "running" and two["status"] == "not_created"
    assert str(two["game_port"]) in two["port_forward_hint"]


def test_lan_ip_override(client, monkeypatch):
    monkeypatch.setattr(settings, "lan_ip", "10.0.0.99")
    assert client.get("/api/addresses").json()["lan_ip"] == "10.0.0.99"
