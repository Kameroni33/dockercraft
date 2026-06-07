"""Player cache: resolve names to UUIDs via DB first, then the platform API.

Java names go through Mojang. Names prefixed with "." are Bedrock gamertags
(Floodgate's convention): resolved via the GeyserMC API to an XUID, stored
with the Floodgate UUID that MC sees them as.
"""

from sqlmodel import Session, func, select

from api.clients import geysermc, mojang
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
    """Cached lookup; case-insensitive (MC usernames are). ".GamerTag" form
    resolves as a Bedrock player."""
    player = session.exec(
        select(Player).where(func.lower(Player.username) == username.lower())
    ).first()
    if player is not None:
        return player

    player = _resolve_bedrock(username[1:]) if username.startswith(".") else _resolve_java(username)
    session.add(player)
    session.commit()
    session.refresh(player)
    return player


def _resolve_java(username: str) -> Player:
    profile = mojang.lookup_uuid(username)
    if profile is None:
        raise UnknownPlayerError(f"no Minecraft (Java) account named {username!r}")
    return Player(username=profile["name"], uuid=format_uuid(profile["id"]), platform="java")


def _resolve_bedrock(gamertag: str) -> Player:
    # Escape hatch: ".2535416061927855" whitelists by raw XUID directly
    # (gamertags must start with a letter, so all-digits is unambiguous).
    if gamertag.isdigit():
        xuid = int(gamertag)
    else:
        xuid = geysermc.lookup_xuid(gamertag)
        if xuid is None:
            raise UnknownPlayerError(
                f"GeyserMC doesn't know the gamertag {gamertag!r} yet (its cache only "
                "covers players who have used a Geyser server before). Have them "
                "attempt to join once and retry — or whitelist by XUID: .<digits> "
                "(find it at e.g. cxkes.me/xbox/xuid)"
            )
    return Player(
        username=f".{gamertag}", uuid=geysermc.floodgate_uuid(xuid), platform="bedrock"
    )
