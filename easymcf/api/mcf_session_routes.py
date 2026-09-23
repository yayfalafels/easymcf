"""Named MCF session actions that are not generic table writes."""

from __future__ import annotations

from flask import Blueprint, current_app, g, jsonify, request

from ..services import mcf_connection
from .db import get_db

bp = Blueprint("mcf_session", __name__, url_prefix="/api/v1/mcf_session")


@bp.post("/open")
def open_session():
    body = request.get_json(silent=True) or {}
    result = mcf_connection.open_interactive_session(
        get_db(), current_app.config["EASYMCF_CONFIG"], g.user_id, str(body.get("url", ""))
    )
    return jsonify(result), 202 if result["mode"] == "authenticated" else 200