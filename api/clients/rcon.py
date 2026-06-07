"""Minimal Source-RCON client (the protocol MC servers speak on rcon.port).

Packet: int32 LE length, then int32 id + int32 type + body + b"\\x00\\x00".
"""

import socket
import struct

AUTH = 3
EXEC = 2
RESPONSE = 0


class RconError(Exception):
    pass


class RconAuthError(RconError):
    pass


class RconClient:
    def __init__(self, host: str, port: int, password: str, timeout: float = 10):
        self._sock = socket.create_connection((host, port), timeout=timeout)
        self._id = 0
        self._auth(password)

    def __enter__(self) -> "RconClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        self._sock.close()

    def command(self, cmd: str) -> str:
        self._send(EXEC, cmd)
        _, _, body = self._recv()
        return body

    def _auth(self, password: str) -> None:
        sent_id = self._send(AUTH, password)
        pid, ptype, _ = self._recv()
        if ptype == RESPONSE:  # some servers send an empty RESPONSE first
            pid, ptype, _ = self._recv()
        if pid == -1 or pid != sent_id:
            raise RconAuthError("RCON authentication failed (bad password?)")

    def _send(self, ptype: int, body: str) -> int:
        self._id += 1
        payload = struct.pack("<ii", self._id, ptype) + body.encode() + b"\x00\x00"
        self._sock.sendall(struct.pack("<i", len(payload)) + payload)
        return self._id

    def _recv(self) -> tuple[int, int, str]:
        (length,) = struct.unpack("<i", self._read_exact(4))
        data = self._read_exact(length)
        pid, ptype = struct.unpack("<ii", data[:8])
        return pid, ptype, data[8:-2].decode(errors="replace")

    def _read_exact(self, n: int) -> bytes:
        buf = b""
        while len(buf) < n:
            chunk = self._sock.recv(n - len(buf))
            if not chunk:
                raise RconError("RCON connection closed by server")
            buf += chunk
        return buf
