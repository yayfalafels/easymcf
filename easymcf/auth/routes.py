"""Auth endpoints API-EP-08..17 and the request guard (ARCH-AUTH-03)."""

from __future__ import annotations

from flask import Blueprint, current_app, g, jsonify, request, send_file

from ..api.db import get_db
from ..api.generic import _validate
from ..errors import Forbidden, GoogleNotConfigured, PayloadTooLarge, RecordNotFound, Unauthenticated, ValidationFailed
from . import accounts, google, photo, sessions

bp = Blueprint("auth", __name__, url_prefix="/api/v1")

SIGNUP_SCHEMA = {
    "type": "object", "required": ["name", "email", "password"], "additionalProperties": False,
    "properties": {"name": {"type": "string"}, "email": {"type": "string"}, "password": {"type": "string"}},
}
SIGNIN_SCHEMA = {
    "type": "object", "required": ["email", "password"], "additionalProperties": False,
    "properties": {"email": {"type": "string"}, "password": {"type": "string", "minLength": 1, "maxLength": 128}},
}
PUBLIC = {
    "health", "spa", "auth.signup", "auth.signin", "auth.signout", "auth.config",
    "auth.google_start", "auth.google_callback",
}


def _config():
    return current_app.config["EASYMCF_CONFIG"]


def install_guard(app) -> None:
    @app.before_request
    def guard():
        if request.method in ("POST", "PUT", "DELETE"):
            origin = request.headers.get("Origin")
            if origin and origin.split("://", 1)[-1] != request.host:
                raise Forbidden("cross-site request refused")
        g.user_id = sessions.resolve(get_db(), _config(), request.cookies.get(sessions.COOKIE))
        is_api = request.path == "/api" or request.path.startswith("/api/")
        public = request.endpoint in PUBLIC and not (request.endpoint == "spa" and is_api)  # an unknown API path is not public
        if is_api and not public and g.user_id is None:
            raise Unauthenticated("Sign in to continue.")


@bp.post("/auth/signup")
def signup():
    body = request.get_json(silent=True)
    _validate(body, SIGNUP_SCHEMA)
    user, cookie = accounts.signup(get_db(), _config(), body)
    response = jsonify(user)
    response.status_code = 201
    sessions.set_cookie(response, _config(), cookie)
    return response


@bp.post("/auth/signin")
def signin():
    body = request.get_json(silent=True)
    _validate(body, SIGNIN_SCHEMA)
    user, cookie = accounts.signin(get_db(), _config(), body)
    response = jsonify(user)
    sessions.set_cookie(response, _config(), cookie)
    return response


@bp.post("/auth/signout")
def signout():
    db = get_db()
    with db:
        sessions.destroy(db, _config(), request.cookies.get(sessions.COOKIE))
    response = current_app.response_class(status=204)
    sessions.clear_cookie(response)
    return response


@bp.get("/auth/me")
def me():
    row = get_db().execute("SELECT * FROM user WHERE id = ?", (g.user_id,)).fetchone()
    return jsonify(accounts.user_json(row))


@bp.get("/auth/config")
def config():
    return jsonify(google_enabled=_config().google_enabled)


@bp.get("/auth/google/start")
def google_start():
    if not _config().google_enabled:
        raise GoogleNotConfigured("Google sign-in is not configured.")
    return google.start(_config())


@bp.get("/auth/google/callback")
def google_callback():
    if not _config().google_enabled:
        raise GoogleNotConfigured("Google sign-in is not configured.")
    return google.callback(get_db(), _config())


def _own(user_id: int) -> None:
    """A photo is served only to its owner, so any other id looks like a missing user."""
    if user_id != g.user_id:
        raise RecordNotFound("user not found")


def _user_body(db, user_id: int):
    return jsonify(accounts.user_json(db.execute("SELECT * FROM user WHERE id = ?", (user_id,)).fetchone()))


@bp.put("/users/<int:user_id>/photo")
def put_photo(user_id):
    _own(user_id)
    part = request.files.get("photo")
    if part is None:
        raise ValidationFailed("photo part is required", field="photo")
    limit = _config().photo_max_bytes
    data = part.stream.read(limit + 1)
    if len(data) > limit:
        raise PayloadTooLarge("The image is larger than the upload limit.")
    db = get_db()
    photo.replace(db, _config(), user_id, photo.to_avatar(data, part.mimetype))
    return _user_body(db, user_id)


@bp.delete("/users/<int:user_id>/photo")
def delete_photo(user_id):
    _own(user_id)
    db = get_db()
    photo.remove(db, _config(), user_id)
    return _user_body(db, user_id)


@bp.get("/users/<int:user_id>/photo")
def get_photo(user_id):
    _own(user_id)
    ref = get_db().execute("SELECT photo_ref FROM user WHERE id = ?", (user_id,)).fetchone()["photo_ref"]
    if not ref:
        raise RecordNotFound("no photo")
    response = send_file(photo.path_of(_config(), ref), mimetype="image/png")
    response.headers["Cache-Control"] = "private, max-age=31536000, immutable"
    return response
