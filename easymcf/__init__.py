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
from .db.connection import schema_version

SCHEMA_VERSION = 4  # bump alongside easymcf/db/schema.sql (ARCH-STO-03)

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FRONTEND_DIR = os.path.join(_REPO_ROOT, "frontend")


def create_app(config: Config | None = None) -> Flask:
    config = config or Config()

    on_disk_version = schema_version(config.db_path)
    if on_disk_version is not None and on_disk_version != SCHEMA_VERSION:
        raise RuntimeError(
            f"database is version {on_disk_version}, code expects {SCHEMA_VERSION} "
            "— run scripts/resetdb.py"
        )

    # No Flask-managed static folder: the catch-all route below does that job
    # itself (ARCH-RUN-09), so /api/v1/* routes can't ever be shadowed by it.
    app = Flask(__name__, static_folder=None)
    app.config["EASYMCF_CONFIG"] = config
    init_api(app)

    @app.get("/api/v1/health")
    def health():
        # API-EP-07 — no body, no db touch; readiness probe only, application
        # code never calls this itself.
        return jsonify(status="ok")

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
