from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class Backup(SQLModel, table=True):
    """One archive of an instance dir + enough metadata to rebuild the instance.

    instance_id is nullable on purpose: backups outlive instance deletion (the
    snapshot fields below are what clone/restore-to-new needs, not the live row).
    """

    __tablename__ = "backup"

    id: int | None = Field(default=None, primary_key=True)
    instance_id: int | None = Field(default=None, foreign_key="server_instance.id", index=True)
    instance_name: str = Field(index=True)

    # Provisioning snapshot at backup time (enables clone without the instance row)
    mc_version: str
    loader: str
    loader_version: str | None = None
    java_major: int
    server_jar: str
    memory: str
    jvm_flags: str

    filename: str  # relative to settings.backups_dir
    size_bytes: int
    kind: str = "manual"  # manual | scheduled | pre_restore
    note: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
