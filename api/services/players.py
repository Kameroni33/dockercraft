"""Player cache: resolve usernames to UUIDs via DB first, Mojang API second."""

from sqlmodel import Session, func, select

from api.clients import mojang
from api.models.player import Player


class UnknownPlayerError(Exception):
    pass


def format_uuid(raw: str) -> str:
    """Mojang returns undashed UUIDs; MC json files want dashed."""
    raw = raw.replace("-", "")
    return f"{raw[0:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:32]}"


def list_players(session: Session) -> list[Player]:
    return list(session.exec(select(Player).order_by(Player.username)).all())


def resolve(session: Session, username: str) -> Player:
    """Cached lookup; case-insensitive (MC usernames are)."""
    player = session.exec(
        select(Player).where(func.lower(Player.username) == username.lower())
    ).first()
    if player is not None:
        return player

    profile = mojang.lookup_uuid(username)
    if profile is None:
        raise UnknownPlayerError(f"no Minecraft account named {username!r}")
    player = Player(username=profile["name"], uuid=format_uuid(profile["id"]))
    session.add(player)
    session.commit()
    session.refresh(player)
    return player
