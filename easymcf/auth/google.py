"""REQ-AUTH-04 - Google sign-in: the authorization code flow with PKCE and the linking rules (ARCH-AUTH-05)."""

from __future__ import annotations

import requests
from authlib.integrations.flask_client import OAuth, OAuthError
from flask import redirect, request, session
from joserfc.errors import JoseError

from .. import clock
from . import photo, sessions

oauth = OAuth()


def init(app, config) -> None:
    if not config.google_enabled:
        return
    oauth.init_app(app)
    oauth.register(
        "google", server_metadata_url=config.google_discovery_url,
        client_id=config.gcp_client_id, client_secret=config.google_client_secret(),
        client_kwargs={"scope": "openid email profile", "code_challenge_method": "S256"},
    )


def safe_next(value: str | None) -> str:
    """A same-origin path only: one leading slash, never a protocol-relative or absolute URL."""
    return value if value and value.startswith("/") and not value.startswith("//") else "/"


def start(config):
    session.permanent = True
    session["next"] = safe_next(request.args.get("next"))
    return oauth.google.authorize_redirect(config.google_redirect_uri, prompt="select_account")


def _to_signin(code: str):
    session.clear()
    return redirect(f"/signin?error={code}")


def callback(db, config):
    if request.args.get("error"):
        return _to_signin("google_denied")
    try:
        claims = oauth.google.authorize_access_token()["userinfo"]
    except (OAuthError, JoseError):
        return _to_signin("google_invalid")
    except requests.RequestException:
        return _to_signin("google_unavailable")
    if not claims.get("email") or claims.get("email_verified") is not True:
        return _to_signin("google_email_unverified")
    with db:
        user_id, needs_photo = link_or_create(db, claims)
        cookie = sessions.create(db, config, user_id)
    if needs_photo and claims.get("picture"):
        photo.import_from_url(db, config, user_id, claims["picture"])
    target = safe_next(session.pop("next", None))
    session.clear()
    response = redirect(target)
    sessions.set_cookie(response, config, cookie)
    return response


def link_or_create(db, claims) -> tuple[int, bool]:
    """Apply the three linking rules in order. Returns (user id, whether the user still needs a photo)."""
    sub, email = claims["sub"], claims["email"].lower()
    row = db.execute("SELECT * FROM user WHERE google_sub = ?", (sub,)).fetchone()
    if row:                                                                   # rule 01
        return row["id"], False
    row = db.execute("SELECT * FROM user WHERE email = ?", (email,)).fetchone()
    if row:                                                                   # rule 02, the identity is verified
        db.execute("UPDATE user SET google_sub = ? WHERE id = ?", (sub, row["id"]))
        return row["id"], row["photo_ref"] is None
    name = claims.get("name") or email.split("@")[0]                          # rule 03
    user_id = db.execute(
        "INSERT INTO user (name, email, status, google_sub, created_at) VALUES (?, ?, 'active', ?, ?)",
        (name, email, sub, clock.stamp()),
    ).lastrowid
    db.execute("INSERT INTO mcf_session (user_id, status) VALUES (?, 'missing')", (user_id,))
    return user_id, True
