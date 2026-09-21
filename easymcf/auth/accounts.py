"""REQ-AUTH-01..03 - sign-up, sign-in, and the user object (Workflow 10)."""

from __future__ import annotations

import re

from .. import clock
from ..errors import Conflict, InvalidCredentials, ValidationFailed
from . import passwords, ratelimit, sessions

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def user_json(row) -> dict:
    """The user object every account endpoint returns. Never carries the hash, the subject, or a digest."""
    methods = [m for m, present in (("password", row["password_hash"]), ("google", row["google_sub"])) if present]
    photo = row["photo_ref"]
    version = photo.rsplit("-", 1)[-1].split(".")[0] if photo else None
    return {
        "id": row["id"], "name": row["name"], "email": row["email"], "auth_methods": methods,
        "photo_url": f"/api/v1/users/{row['id']}/photo?v={version}" if photo else None,
    }


def signup(db, config, body: dict) -> tuple[dict, str]:
    name, email = body["name"].strip(), body["email"].strip().lower()
    if not 1 <= len(name) <= 80:
        raise ValidationFailed("name must be 1 to 80 characters", field="name")
    if len(email) > 254 or not EMAIL.match(email):
        raise ValidationFailed("email is not a valid address", field="email")
    unmet = passwords.unmet_rules(body["password"], email, name, config.password_min_length)
    if unmet:
        raise ValidationFailed("Password does not meet the requirements.", field="password", rules=unmet)
    if db.execute("SELECT 1 FROM user WHERE email = ?", (email,)).fetchone():
        raise Conflict("An account with this email already exists.", field="email")
    at = clock.stamp()
    with db:
        user_id = db.execute(
            "INSERT INTO user (name, email, status, password_hash, created_at) VALUES (?, ?, 'active', ?, ?)",
            (name, email, passwords.hash_password(body["password"]), at),
        ).lastrowid
        db.execute("INSERT INTO mcf_session (user_id, status) VALUES (?, 'missing')", (user_id,))
        cookie = sessions.create(db, config, user_id)
    return user_json(db.execute("SELECT * FROM user WHERE id = ?", (user_id,)).fetchone()), cookie


def signin(db, config, body: dict) -> tuple[dict, str]:
    email = body["email"].strip().lower()
    ratelimit.check(email, config)
    row = db.execute("SELECT * FROM user WHERE email = ?", (email,)).fetchone()
    active = row is not None and row["status"] == "active"
    if not passwords.verify(row["password_hash"] if active else None, body["password"]):
        ratelimit.record_failure(email, config)
        raise InvalidCredentials("Email or password is incorrect.")
    ratelimit.clear(email)
    with db:
        cookie = sessions.create(db, config, row["id"])
    return user_json(row), cookie
