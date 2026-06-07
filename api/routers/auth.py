import time

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field
from starlette.requests import HTTPConnection

from api.db import SessionDep
from api.services import auth

router = APIRouter(prefix="/auth", tags=["auth"])


class Credentials(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8, max_length=256)


def require_auth(conn: HTTPConnection) -> str:
    """Dependency guarding every non-auth API route. Returns the username.
    HTTPConnection covers both HTTP requests and WebSocket handshakes."""
    username = auth.verify_token(conn.cookies.get(auth.COOKIE_NAME))
    if username is None:
        raise HTTPException(401, "not authenticated")
    return username


def _set_session(response: Response, username: str) -> None:
    response.set_cookie(
        auth.COOKIE_NAME,
        auth.make_token(username),
        max_age=auth.SESSION_TTL,
        httponly=True,
        samesite="lax",
        # secure=False: LAN HTTP deployment. Set True when serving over TLS.
    )


@router.get("/status")
def status(request: Request, session: SessionDep) -> dict:
    return {
        "setup_required": not auth.any_user_exists(session),
        "authenticated": auth.verify_token(request.cookies.get(auth.COOKIE_NAME)) is not None,
    }


@router.post("/setup")
def first_run_setup(body: Credentials, response: Response, session: SessionDep) -> dict:
    """Create the admin account. Only available until one exists."""
    if auth.any_user_exists(session):
        raise HTTPException(409, "an admin account already exists")
    user = auth.create_user(session, body.username, body.password)
    _set_session(response, user.username)
    return {"username": user.username}


@router.post("/login")
def login(body: Credentials, response: Response, session: SessionDep) -> dict:
    user = auth.get_user(session, body.username)
    if user is None or not auth.verify_password(body.password, user.password_hash):
        time.sleep(0.5)  # blunt brute-force damper
        raise HTTPException(401, "invalid username or password")
    _set_session(response, user.username)
    return {"username": user.username}


@router.post("/logout", status_code=204)
def logout(response: Response) -> None:
    response.delete_cookie(auth.COOKIE_NAME)
