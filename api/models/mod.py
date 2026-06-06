from datetime import UTC, datetime

from sqlmodel import Field, SQLModel, UniqueConstraint


class InstalledMod(SQLModel, table=True):
    """A Modrinth mod installed on one instance (file lives in <instance>/mods/)."""

    __tablename__ = "installed_mod"
    __table_args__ = (UniqueConstraint("instance_id", "project_id"),)

    id: int | None = Field(default=None, primary_key=True)
    instance_id: int = Field(foreign_key="server_instance.id", index=True)

    project_id: str  # Modrinth project id
    slug: str
    title: str
    version_id: str
    version_number: str
    filename: str  # within mods/, without the .disabled suffix

    enabled: bool = True  # disabled = file renamed to <filename>.disabled
    auto_update: bool = False
    dependency_of: str | None = None  # project_id that pulled this in, if any
    requires_json: str = "[]"  # project_ids this mod's installed version requires

    installed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
