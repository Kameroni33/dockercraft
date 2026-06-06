from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class Player(SQLModel, table=True):
    """Known players (username ↔ UUID), cached so new servers can whitelist
    familiar people without re-hitting the Mojang API."""

    __tablename__ = "player"

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)  # canonical capitalization from Mojang
    uuid: str = Field(unique=True)  # dashed format, as MC json files expect
    cached_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
