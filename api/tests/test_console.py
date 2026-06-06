import socket
import struct
import threading

import pytest

from api.clients.rcon import AUTH, EXEC, RconAuthError, RconClient
from api.services.console import demux_docker_stream

PASSWORD = "hunter2"


def _read_packet(conn):
    (length,) = struct.unpack("<i", conn.recv(4))
    data = b""
    while len(data) < length:
        data += conn.recv(length - len(data))
    pid, ptype = struct.unpack("<ii", data[:8])
    return pid, ptype, data[8:-2].decode()


def _send_packet(conn, pid, ptype, body=""):
    payload = struct.pack("<ii", pid, ptype) + body.encode() + b"\x00\x00"
    conn.sendall(struct.pack("<i", len(payload)) + payload)


@pytest.fixture
def rcon_server():
    """A real TCP server speaking just enough RCON for the client to talk to."""
    server = socket.create_server(("127.0.0.1", 0))
    port = server.getsockname()[1]

    def serve():
        conn, _ = server.accept()
        with conn:
            pid, ptype, body = _read_packet(conn)
            assert ptype == AUTH
            if body != PASSWORD:
                _send_packet(conn, -1, 2)
                return
            _send_packet(conn, pid, 2)  # auth ok
            while True:
                try:
                    pid, ptype, body = _read_packet(conn)
                except (struct.error, ConnectionError):
                    return
                assert ptype == EXEC
                _send_packet(conn, pid, 0, f"echo: {body}")

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    yield port
    server.close()


def test_rcon_roundtrip(rcon_server):
    with RconClient("127.0.0.1", rcon_server, PASSWORD) as rcon:
        assert rcon.command("list") == "echo: list"
        assert rcon.command("say hi") == "echo: say hi"


def test_rcon_bad_password(rcon_server):
    with pytest.raises(RconAuthError):
        RconClient("127.0.0.1", rcon_server, "wrong")


def _frame(payload: bytes, stream=1) -> bytes:
    return bytes([stream, 0, 0, 0]) + len(payload).to_bytes(4, "big") + payload


def test_demux_complete_frames():
    buf = _frame(b"line one\n") + _frame(b"line two\n", stream=2)
    frames, rest = demux_docker_stream(buf)
    assert frames == [b"line one\n", b"line two\n"]
    assert rest == b""


def test_demux_partial_frame():
    full = _frame(b"hello world")
    frames, rest = demux_docker_stream(full[:10])  # header + 2 bytes only
    assert frames == [] and rest == full[:10]
    frames, rest = demux_docker_stream(rest + full[10:])
    assert frames == [b"hello world"] and rest == b""


def test_command_endpoint_not_running(client):
    sid = client.post("/api/servers", json={"name": "cmd", "mc_version": "1.21.1"}).json()["id"]
    resp = client.post(f"/api/servers/{sid}/command", json={"command": "list"})
    assert resp.status_code == 409
