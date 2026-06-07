from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class Player(SQLModel, table=True):
    """Known players (username ↔ UUID), cached so new servers can whitelist
    familiar people without re-hitting the Mojang API."""

    __tablename__ = "player"

    id: int | None = Field(default=None, primary_key=True)
    # Java: canonical capitalization from Mojang. Bedrock: ".GamerTag"
    # (Floodgate's prefixed form — the dot marks platform throughout the app).
    username: str = Field(unique=True, index=True)
    uuid: str = Field(unique=True)  # dashed; Floodgate UUID for bedrock players
    platform: str = "java"  # java | bedrock
    cached_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
