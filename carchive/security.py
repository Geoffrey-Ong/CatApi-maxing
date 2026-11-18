"""Password hashing (argon2) and login tokens (JWT). No database access here."""
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

log = logging.getLogger("carchive.security")

TOKEN_LIFETIME = timedelta(days=7)

_hasher = PasswordHasher()
# Verified against when the account doesn't exist, so a failed login takes the same time
# whether or not the username/email is registered.
_DUMMY_HASH = _hasher.hash("this-is-not-a-real-password")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def check_password(stored_hash: Optional[str], password: str) -> bool:
    try:
        _hasher.verify(stored_hash or _DUMMY_HASH, password)
        return stored_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def _secret() -> str:
    secret = os.environ.get("JWT_SECRET", "")
    if len(secret) < 32:
        log.error("JWT_SECRET is missing or shorter than 32 characters")
        raise RuntimeError("Token signing is not configured.")
    return secret


def create_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "iat": now, "exp": now + TOKEN_LIFETIME}
    return jwt.encode(payload, _secret(), algorithm="HS256")


def read_token(token: str) -> Optional[int]:
    """Return the user id inside a valid, unexpired token, or None for anything else."""
    try:
        claims = jwt.decode(token, _secret(), algorithms=["HS256"], options={"require": ["exp", "sub"]})
        return int(claims["sub"])
    except (jwt.PyJWTError, ValueError, KeyError):
        return None