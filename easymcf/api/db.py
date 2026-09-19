from __future__ import annotations

from flask import current_app, g

from ..db.connection import get_connection


def get_db():
    if "db" not in g:
        g.db = get_connection(current_app.config["EASYMCF_CONFIG"].db_path)
    return g.db


def close_db(_exc=None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()
