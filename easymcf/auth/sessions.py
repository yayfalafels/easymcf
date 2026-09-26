"""REQ-AUTH-05 - sign-in sessions: signing key, token, cookie, and request-to-user lookup (ARCH-AUTH-02)."""

from __future__ import annotations

import hashlib
import os
import secrets
from datetime import timedelta

from itsdangerous import BadSignature, URLSafeSerializer

from .. import clock

COOKIE = "easymcf_session"


def secret_key(config) -> bytes:
    """SECRET_KEY when set, else 32 random bytes kept in <SECRETS_DIR>/session_key (mode 0600)."""
    if os.environ.get("SECRET_KEY"):
        return os.environ["SECRET_KEY"].encode()
    path = os.path.join(config.secrets_dir, "session_key")
    if not os.path.exists(path):
        os.makedirs(config.secrets_dir, mode=0o700, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(secrets.token_bytes(32))
    with open(path, "rb") as handle:
        return handle.read()


def _signer(config) -> URLSafeSerializer:
    return URLSafeSerializer(secret_key(config), salt="easymcf-session")


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create(db, config, user_id: int) -> str:
    """Insert an auth_session row and return the signed cookie value. The caller commits."""
    now = clock.now()
    db.execute("DELETE FROM auth_session WHERE expires_at <= ?", (clock.stamp(now),))
    token = secrets.token_urlsafe(32)
    db.execute(
        "INSERT INTO auth_session (user_id, token_hash, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (user_id, _digest(token), clock.stamp(now), clock.stamp(now + timedelta(hours=config.session_lifetime_h))),
    )
    return _signer(config).dumps(token)


def resolve(db, config, cookie_value: str | None) -> int | None:
    if not cookie_value:
        return None
    try:
        token = _signer(config).loads(cookie_value)
    except BadSignature:
        return None
    row = db.execute(
        "SELECT s.user_id FROM auth_session s JOIN user u ON u.id = s.user_id "
        "WHERE s.token_hash = ? AND s.expires_at > ? AND u.status = 'active'",
        (_digest(token), clock.stamp()),
    ).fetchone()
    return row["user_id"] if row else None


def destroy(db, config, cookie_value: str | None) -> None:
    if not cookie_value:
        return
    try:
        db.execute("DELETE FROM auth_session WHERE token_hash = ?", (_digest(_signer(config).loads(cookie_value)),))
    except BadSignature:
        pass


def set_cookie(response, config, value: str) -> None:
    response.set_cookie(
        COOKIE, value, max_age=config.session_lifetime_h * 3600, httponly=True,
        samesite="Lax", path="/", secure=config.cookie_secure,
    )


def clear_cookie(response) -> None:
    response.delete_cookie(COOKIE, path="/")
