"""SQLite engine + session dependency."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from sqlmodel import Session, SQLModel, create_engine

from api.config import settings

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(
            settings.resolved_database_url,
            connect_args={"check_same_thread": False},
        )
    return _engine


def init_db() -> None:
    # Import models so SQLModel.metadata knows every table before create_all.
    import api.models  # noqa: F401

    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    _auto_add_columns(engine)


def _auto_add_columns(engine) -> None:
    """Poor-man's migration: ADD COLUMN for model fields missing from existing
    tables. Additive-only — enough until the schema stabilizes and a real
    migration tool (alembic) earns its keep."""
    import sqlalchemy as sa

    inspector = sa.inspect(engine)
    with engine.connect() as conn:
        for table in SQLModel.metadata.tables.values():
            existing = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing:
                    continue
                ddl = (
                    f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" '
                    f"{column.type.compile(engine.dialect)}"
                )
                default = getattr(column.default, "arg", None)
                if default is not None and not callable(default):
                    if isinstance(default, bool):
                        literal = "1" if default else "0"
                    elif isinstance(default, int | float):
                        literal = str(default)
                    else:
                        literal = "'{}'".format(str(default).replace("'", "''"))
                    ddl += f" DEFAULT {literal}"
                    if not column.nullable:
                        ddl += " NOT NULL"
                conn.execute(sa.text(ddl))
        conn.commit()


def get_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
