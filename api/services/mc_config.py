"""server.properties management per instance.

The manager owns container-side networking + RCON keys ("managed properties") —
they are enforced on every write and before every start, and user updates to
them are rejected. Everything else is the user's to customize.
"""

from api import paths
from api.models.instance import ServerInstance

PROPERTIES_FILE = "server.properties"


class ManagedPropertyError(ValueError):
    pass


def managed_properties(instance: ServerInstance) -> dict[str, str]:
    # Container-side ports are fixed; the host side is what varies per instance.
    return {
        "server-port": "25565",
        "query.port": "25565",
        "enable-rcon": "true",
        "rcon.port": "25575",
        "rcon.password": instance.rcon_password,
    }


def _path(instance: ServerInstance):
    return paths.instance_dir(instance.name) / PROPERTIES_FILE


def read_properties(instance: ServerInstance) -> dict[str, str]:
    path = _path(instance)
    props: dict[str, str] = {}
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith(("#", "!")) or "=" not in line:
                continue
            key, _, value = line.partition("=")
            props[key.strip()] = value.strip()
    return props


def write_properties(instance: ServerInstance, props: dict[str, str]) -> None:
    path = _path(instance)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{k}={v}\n" for k, v in sorted(props.items())))


def update_properties(instance: ServerInstance, updates: dict) -> dict[str, str]:
    """Merge user updates into the file; managed keys are off-limits."""
    clashes = set(updates) & set(managed_properties(instance))
    if clashes:
        raise ManagedPropertyError(f"managed by dockercraft, cannot edit: {sorted(clashes)}")
    normalized = {k: _to_prop(v) for k, v in updates.items()}
    props = read_properties(instance) | normalized | managed_properties(instance)
    write_properties(instance, props)
    return props


def apply_managed(instance: ServerInstance) -> None:
    """Re-assert managed keys (run before every start; survives MC rewriting the file)."""
    write_properties(instance, read_properties(instance) | managed_properties(instance))


def _to_prop(value) -> str:
    if isinstance(value, bool):  # JSON true/false -> "true"/"false"
        return "true" if value else "false"
    return str(value)
