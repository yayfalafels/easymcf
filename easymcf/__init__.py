"""Flask application factory (ARCH-RUN-01/07/09).

`easymcf/` (repo root) -> `easymcf/easymcf/` (this package) -> `create_app()`.
One process serves both the JSON API (`/api/v1/*`) and the AngularJS
frontend's static files (`frontend/`, everything else) — no reverse proxy,
no second server.
"""

from __future__ import annotations

import os

from flask import Flask, abort, jsonify, send_from_directory
from werkzeug.exceptions import NotFound

from .config import Config
from .api import init_api
from .api import mcf_attempt_routes, mcf_session_routes
from .auth import google as auth_google, routes as auth_routes, sessions
from .db.connection import get_connection, schema_version
from .services import mcf_connection, search

SCHEMA_VERSION = 9  # bump alongside easymcf/db/schema.sql (ARCH-STO-03)

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FRONTEND_DIR = os.path.join(_REPO_ROOT, "frontend")
_ASSETS_DIR = os.path.join(_REPO_ROOT, "assets")


def create_app(config: Config | None = None) -> Flask:
    config = config or Config()

    on_disk_version = schema_version(config.db_path)
    if on_disk_version is not None and on_disk_version != SCHEMA_VERSION:
        raise RuntimeError(
            f"database is version {on_disk_version}, code expects {SCHEMA_VERSION} "
            "— run scripts/resetdb.py"
        )
    mcf_connection.reconcile_local_sessions(config)
    # Interrupted runs (Workflow, "Interrupted runs" note): before the server accepts
    # requests and before the scheduler starts, every `running` run_log row of every user
    # becomes `failed`, or ARCH-RUN-03's partial unique index would refuse every later
    # search by a user whose previous process died mid-run.
    _startup_db = get_connection(config.db_path)
    try:
        search.reconcile_orphaned_runs(_startup_db)
    finally:
        _startup_db.close()

    # No Flask-managed static folder: the catch-all route below does that job
    # itself (ARCH-RUN-09), so /api/v1/* routes can't ever be shadowed by it.
    app = Flask(__name__, static_folder=None)
    app.config["EASYMCF_CONFIG"] = config
    app.secret_key = sessions.secret_key(config)
    app.config.update(
        SESSION_COOKIE_NAME="easymcf_oauth", SESSION_COOKIE_SAMESITE="Lax", SESSION_COOKIE_HTTPONLY=True,
        PERMANENT_SESSION_LIFETIME=600, MAX_CONTENT_LENGTH=config.photo_max_bytes + 1024 * 1024,
    )
    auth_routes.install_guard(app)
    auth_google.init(app, config)
    app.register_blueprint(auth_routes.bp)
    app.register_blueprint(mcf_attempt_routes.bp)
    app.register_blueprint(mcf_session_routes.bp)
    init_api(app)

    @app.errorhandler(413)
    def too_large(_error):
        return jsonify(error="payload_too_large", message="The image is larger than the upload limit."), 413

    @app.get("/api/v1/health")
    def health():
        # API-EP-07 — no body, no db touch; readiness probe only, application
        # code never calls this itself.
        return jsonify(status="ok")

    @app.get("/assets/<path:path>")
    def assets(path: str):
        return send_from_directory(_ASSETS_DIR, path)

    @app.get("/")
    @app.get("/<path:path>")
    def spa(path: str = "index.html"):
        # ARCH-RUN-09: unmatched non-/api paths get frontend/index.html, so
        # AngularJS's client-side html5Mode routing can resolve them (a direct
        # navigation/refresh on a client-side route has no matching file on
        # disk). A path that IS a real static asset (index.html itself, a
        # vendored/app script, a template) is served as-is first.
        # send_from_directory raises werkzeug's NotFound, not a plain
        # FileNotFoundError, when the path doesn't resolve — the original
        # `except FileNotFoundError` here never actually caught anything.
        if path == "api" or path.startswith("api/"):
            return jsonify(error="not_found", message=f"no such API path: /{path}"), 404
        try:
            return send_from_directory(_FRONTEND_DIR, path)
        except NotFound:
            try:
                return send_from_directory(_FRONTEND_DIR, "index.html")
            except NotFound:
                abort(404)

    return app
