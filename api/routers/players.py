"""Global player cache endpoints (per-server whitelist/ops live under /servers)."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.db import SessionDep
from api.models.player import Player
from api.services import players

router = APIRouter(prefix="/players", tags=["players"])


class PlayerLookup(BaseModel):
    username: str


@router.get("", response_model=list[Player])
def list_players(session: SessionDep):
    return players.list_players(session)


@router.post("", response_model=Player)
def cache_player(body: PlayerLookup, session: SessionDep):
    """Resolve + cache a username (used by UI to validate before whitelisting)."""
    try:
        return players.resolve(session, body.username)
    except players.UnknownPlayerError as e:
        raise HTTPException(404, str(e)) from e
