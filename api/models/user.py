from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    """Manager account. Single admin for now; table leaves room for more."""

    __tablename__ = "user"

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    password_hash: str  # "scrypt$<n>$<r>$<p>$<salt hex>$<hash hex>"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
