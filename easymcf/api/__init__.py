"""REQ-PLAT-01 — the generic CRUD API mounted under /api/v1 (ARCH-RUN-10)."""

from __future__ import annotations

from flask import Flask, jsonify

from ..errors import ApiError
from . import resources  # noqa: F401  (registers every Resource)
from .db import close_db
from .generic import bp


def init_api(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def _api_error(exc: ApiError):
        body = {"error": exc.error, "message": exc.message}
        if exc.field:
            body["field"] = exc.field
        body.update(exc.extra)
        return jsonify(body), exc.status

    app.register_blueprint(bp)
    app.teardown_appcontext(close_db)
