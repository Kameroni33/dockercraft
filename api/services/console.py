"""Console access: RCON for one-shot commands, attach-socket bridge for the
full interactive console over a WebSocket."""

import asyncio
import threading

from fastapi import WebSocket, WebSocketDisconnect

from api.clients.rcon import RconClient
from api.models.instance import ServerInstance
from api.services import docker_manager

LOG_TAIL = 100  # lines of history sent on console connect


class NotRunningError(Exception):
    pass


def _rcon_target(instance: ServerInstance) -> tuple[str, int]:
    """Prefer the container's bridge IP (works from host and sibling containers);
    fall back to the host-mapped port."""
    container = docker_manager.get_container(instance)
    if container is not None and container.status == "running":
        networks = container.attrs["NetworkSettings"]["Networks"]
        ip = next(iter(networks.values()), {}).get("IPAddress")
        if ip:
            return ip, 25575
    return "127.0.0.1", instance.rcon_port


def run_command(instance: ServerInstance, timeout: float = 10) -> RconClient:
    """Open an authenticated RCON session for this instance."""
    if docker_manager.status(instance) != "running":
        raise NotRunningError(f"instance {instance.name!r} is not running")
    host, port = _rcon_target(instance)
    return RconClient(host, port, instance.rcon_password, timeout=timeout)


def demux_docker_stream(buf: bytes) -> tuple[list[bytes], bytes]:
    """Split docker's multiplexed attach stream (8-byte header: type, pad×3,
    big-endian length) into payload frames + unconsumed remainder."""
    frames = []
    while len(buf) >= 8:
        length = int.from_bytes(buf[4:8], "big")
        if len(buf) < 8 + length:
            break
        frames.append(buf[8 : 8 + length])
        buf = buf[8 + length :]
    return frames, buf


async def bridge_console(
    websocket: WebSocket, instance: ServerInstance, tail: int = LOG_TAIL
) -> None:
    """Bidirectional bridge: container stdout/stderr -> WS, WS text -> stdin."""
    container = docker_manager.get_container(instance)
    sock = container.attach_socket(
        params={"stdin": 1, "stdout": 1, "stderr": 1, "stream": 1, "logs": 0}
    )
    raw = getattr(sock, "_sock", sock)

    if tail > 0:
        history = container.logs(tail=tail)
        if history:
            await websocket.send_text(history.decode(errors="replace"))

    queue: asyncio.Queue[bytes | None] = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def reader() -> None:
        buf = b""
        try:
            while True:
                chunk = raw.recv(4096)
                if not chunk:
                    break
                frames, buf = demux_docker_stream(buf + chunk)
                for frame in frames:
                    loop.call_soon_threadsafe(queue.put_nowait, frame)
        except OSError:
            pass
        loop.call_soon_threadsafe(queue.put_nowait, None)

    thread = threading.Thread(target=reader, daemon=True, name=f"console-{instance.name}")
    thread.start()

    async def container_to_ws() -> None:
        while (frame := await queue.get()) is not None:
            await websocket.send_text(frame.decode(errors="replace"))

    async def ws_to_stdin() -> None:
        while True:
            text = await websocket.receive_text()
            raw.sendall((text.rstrip("\n") + "\n").encode())

    out_task = asyncio.create_task(container_to_ws())
    in_task = asyncio.create_task(ws_to_stdin())
    try:
        done, pending = await asyncio.wait(
            {out_task, in_task}, return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
        for task in done:  # surface unexpected errors (disconnects are normal)
            if not task.cancelled() and task.exception():
                exc = task.exception()
                if not isinstance(exc, WebSocketDisconnect):
                    raise exc
    finally:
        raw.close()  # unblocks the reader thread's recv
