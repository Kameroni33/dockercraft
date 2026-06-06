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
