"""Authentication: scrypt password hashing + HMAC-signed expiring session
tokens in an HttpOnly cookie. Stdlib only — no crypto dependencies.

The signing secret is generated once and kept in data/secret.key; rotating it
(deleting the file) invalidates every session.
"""

import hashlib
import hmac
import secrets
import time

from sqlmodel import Session, select

from api.config import settings
from api.models.user import User

COOKIE_NAME = "dockercraft_session"
SESSION_TTL = 7 * 86400  # seconds
_SCRYPT = {"n": 2**14, "r": 8, "p": 1}

_secret: bytes | None = None


def get_secret() -> bytes:
    global _secret
    if _secret is None:
        path = settings.data_dir / "secret.key"
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(secrets.token_bytes(32))
            path.chmod(0o600)
        _secret = path.read_bytes()
    return _secret


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT)
    return f"scrypt${_SCRYPT['n']}${_SCRYPT['r']}${_SCRYPT['p']}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, n, r, p, salt_hex, hash_hex = stored.split("$")
        digest = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt_hex), n=int(n), r=int(r), p=int(p)
        )
        return hmac.compare_digest(digest.hex(), hash_hex)
    except (ValueError, KeyError):
        return False


def make_token(username: str, ttl: int = SESSION_TTL) -> str:
    expires = int(time.time()) + ttl
    payload = f"{username}:{expires}"
    sig = hmac.new(get_secret(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"


def verify_token(token: str | None) -> str | None:
    """Return the username for a valid, unexpired token; None otherwise."""
    if not token or token.count(":") != 2:
        return None
    username, expires, sig = token.rsplit(":", 2)
    expected = hmac.new(get_secret(), f"{username}:{expires}".encode(), hashlib.sha256)
    if not hmac.compare_digest(expected.hexdigest(), sig):
        return None
    try:
        if int(expires) < time.time():
            return None
    except ValueError:
        return None
    return username


def any_user_exists(session: Session) -> bool:
    return session.exec(select(User)).first() is not None


def get_user(session: Session, username: str) -> User | None:
    return session.exec(select(User).where(User.username == username)).first()


def create_user(session: Session, username: str, password: str) -> User:
    user = User(username=username, password_hash=hash_password(password))
    session.add(user)
    session.commit()
    session.refresh(user)
    return user
