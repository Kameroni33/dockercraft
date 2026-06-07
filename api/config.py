"""Application settings, overridable via environment variables (DOCKERCRAFT_ prefix)."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DOCKERCRAFT_", env_file=".env", extra="ignore")

    # Where the manager reads/writes instance data (its own view of the filesystem).
    data_dir: Path = Path("data")

    # The same directory as seen by the Docker HOST. When the manager runs in a
    # container and creates sibling MC containers via the host docker socket,
    # volume binds must use host paths, not container paths. Defaults to
    # data_dir (correct when running directly on the host).
    host_data_dir: Path | None = None

    # Host port ranges allocated to instances.
    game_port_range: tuple[int, int] = (25565, 25664)
    rcon_port_range: tuple[int, int] = (25665, 25764)

    # Custom MC server image (tagged per Java major, e.g. dockercraft/minecraft:java21).
    mc_image_repo: str = "dockercraft/minecraft"

    # phantom sidecar (console LAN discovery for Bedrock/Geyser instances).
    phantom_image: str = "dockercraft/phantom:latest"
    phantom_version: str = "0.5.4"  # must match the sha256 pin in images/phantom/Dockerfile
    # When LAN discovery is enabled, an instance's Bedrock host port is moved out
    # of 19132 (phantom needs it for discovery broadcasts) into this range.
    bedrock_remap_range: tuple[int, int] = (19133, 19232)

    # LAN IP players connect to. Auto-detected when unset; must be set explicitly
    # when the manager runs in a container (detection would find the bridge IP).
    lan_ip: str | None = None

    # Public (WAN) IP for sharing with non-LAN players. Auto-detected via
    # external echo services when unset; set explicitly if you have a static IP
    # or want to use a dynamic-DNS hostname instead.
    public_ip: str | None = None

    database_url: str = ""  # derived from data_dir when empty

    @property
    def resolved_host_data_dir(self) -> Path:
        return (self.host_data_dir or self.data_dir).resolve()

    @property
    def instances_dir(self) -> Path:
        return self.data_dir / "instances"

    @property
    def backups_dir(self) -> Path:
        return self.data_dir / "backups"

    @property
    def resolved_database_url(self) -> str:
        return self.database_url or f"sqlite:///{self.data_dir / 'dockercraft.db'}"


settings = Settings()
