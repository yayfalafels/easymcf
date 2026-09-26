"""API-HOOK-0x — the mcf_attempt named endpoints (run_log's trigger-plus-generic-read split, closure item 17.CK.08)."""

from __future__ import annotations

from flask import Blueprint, Response, current_app, g, jsonify, request

from .. import tenancy
from ..services import mcf_connection
from .db import get_db

bp = Blueprint("mcf_attempt", __name__, url_prefix="/api/v1/mcf_attempt")


def _config():
    return current_app.config["EASYMCF_CONFIG"]


@bp.post("/start")
def start():
    row = mcf_connection.start_attempt(get_db(), _config(), g.user_id)
    return jsonify(row), 201


@bp.get("/<int:attempt_id>/qr")
def qr(attempt_id: int):
    tenancy.require_visible(get_db(), g.user_id, "mcf_attempt", attempt_id)
    image_bytes = mcf_connection.get_qr_bytes(attempt_id)
    if image_bytes is None:
        return jsonify(error="not_found", message="no QR available for this attempt"), 404
    response = Response(image_bytes, mimetype="image/png")
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.get("/<int:attempt_id>/qr_link")
def qr_link(attempt_id: int):
    tenancy.require_visible(get_db(), g.user_id, "mcf_attempt", attempt_id)
    link = mcf_connection.get_qr_link(attempt_id)
    return jsonify(link=link)


@bp.post("/<int:attempt_id>/confirm")
def confirm(attempt_id: int):
    body = request.get_json(silent=True) or {}
    row = mcf_connection.confirm(get_db(), _config(), g.user_id, attempt_id, accept=bool(body.get("accept", False)))
    return jsonify(row)


@bp.delete("/<int:attempt_id>")
def cancel(attempt_id: int):
    row = mcf_connection.cancel(get_db(), _config(), g.user_id, attempt_id)
    return jsonify(row)
