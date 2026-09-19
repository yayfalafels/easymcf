"""Resource declarations. Importing this module registers them with generic.register()."""

from __future__ import annotations

import uuid

from flask import jsonify, request

from .. import clock
from ..services import leads
from .db import get_db
from .generic import GENERIC, REGISTRY, Resource, _fetch, _validate, bp, register

READ_ONLY = frozenset({"get", "search"})
_DATE = {"type": ["string", "null"], "pattern": r"^\d{4}-\d{2}-\d{2}$"}
_ANY = {"type": "object"}


def _only_user(db) -> dict:
    row = db.execute("SELECT id FROM user ORDER BY id LIMIT 1").fetchone()
    return {"user_id": row["id"]} if row else {}


_TRACK_PROPS = {
    "role_id": {"type": "integer"},
    "seniority": {"type": "string", "minLength": 1},
    "default_cv_id": {"type": ["integer", "null"]},
    "is_active": {"type": ["boolean", "integer"]},
}
register(Resource(
    "track",
    create_schema={"type": "object", "properties": {**_TRACK_PROPS, "user_id": {"type": "integer"}},
                   "required": ["user_id", "role_id", "seniority"], "additionalProperties": False},
    update_schema={"type": "object", "properties": _TRACK_PROPS, "additionalProperties": False},
    verbs=frozenset({"get", "search", "create", "update"}),
    bool_columns=("is_active",),
    select_sql="SELECT track.*, role.name AS role_name FROM track JOIN role ON role.id = track.role_id",
    defaults=_only_user,
))
register(Resource(
    "role",
    create_schema={"type": "object", "properties": {"name": {"type": "string", "minLength": 1},
                                                   "description": {"type": ["string", "null"]}},
                   "required": ["name"], "additionalProperties": False},
    update_schema=_ANY, verbs=frozenset({"get", "search", "create"}),
))
_CV_PROPS = {"label": {"type": "string", "minLength": 1}}
register(Resource(
    "cv",
    create_schema={"type": "object", "properties": {**_CV_PROPS, "user_id": {"type": "integer"}},
                   "required": ["user_id", "label"], "additionalProperties": False},
    update_schema={"type": "object", "properties": _CV_PROPS, "required": ["label"], "additionalProperties": False},
    verbs=frozenset({"get", "search", "create", "update", "delete"}), defaults=_only_user,
))
_PROFILE_PROPS = {
    "keywords": {"type": "string", "minLength": 1}, "min_salary": {"type": ["integer", "null"]},
    "max_age_weeks": {"type": ["integer", "null"], "minimum": 1},
    "min_match_score": {"type": "number", "minimum": 0, "maximum": 1},
    "employment_type": {"type": "string", "minLength": 1},
}
register(Resource(
    "search_profile",
    create_schema={"type": "object", "properties": {"track_id": {"type": "integer"}, **_PROFILE_PROPS},
                   "required": ["track_id", "keywords", "min_match_score", "employment_type"], "additionalProperties": False},
    update_schema={"type": "object", "properties": _PROFILE_PROPS, "additionalProperties": False},
    verbs=frozenset({"get", "search", "create", "update"}), pk="track_id",
))
_SCHEDULE_PROPS = {
    "schedule_enabled": {"type": ["boolean", "integer"]},
    "schedule_interval_hours": {"type": "integer", "minimum": 1},
    "next_run_at": {"type": ["string", "null"]},
}
register(Resource(
    "search_schedule",
    create_schema={"type": "object", "properties": {"track_id": {"type": "integer"}, **_SCHEDULE_PROPS},
                   "required": ["track_id", "schedule_enabled", "schedule_interval_hours"], "additionalProperties": False},
    update_schema={"type": "object", "properties": _SCHEDULE_PROPS, "additionalProperties": False},
    verbs=frozenset({"get", "search", "create", "update"}), pk="track_id", bool_columns=("schedule_enabled",),
))
_POST_UPDATE_PROPS = {"url_ref": {"type": ["string", "null"]}}
register(Resource(
    "post",
    create_schema=_ANY,
    update_schema={"type": "object", "properties": _POST_UPDATE_PROPS, "required": ["url_ref"], "additionalProperties": False},
    verbs=frozenset({"get", "search", "update"}), bool_columns=("is_open",),
))

register(Resource(
    "lead",
    create_schema={"type": "object", "properties": {"post_id": {"type": "string", "minLength": 1},
                                                   "track_id": {"type": "integer"}},
                   "required": ["post_id", "track_id"], "additionalProperties": False},
    update_schema={"type": "object", "additionalProperties": False, "properties": {
        "stage": {"enum": list(leads.STAGES)},
        "close_reason": {"enum": [*leads.CLOSE_REASONS, None]},
        "title_override": {"type": ["string", "null"]},
        "company_override": {"type": ["string", "null"]},
        "deadline": _DATE, "applied_date": _DATE,
        "first_attempt_date": _DATE, "last_contact_date": _DATE}},
    verbs=frozenset({"get", "search", "create", "update"}),
    select_sql=("SELECT lead.*, post.position_title, post.company_name, post.url_ref "
                "FROM lead JOIN post ON post.id = lead.post_id"),
    create_fn=leads.promote, update_fn=leads.update_lead, before_read=leads.expire_due,
))

_MANUAL_LEAD_SCHEMA = {
    "type": "object",
    "properties": {
        "track_id": {"type": "integer"}, "position_title": {"type": "string", "minLength": 1},
        "company_name": {"type": "string", "minLength": 1}, "url_ref": {"type": ["string", "null"]},
        "salary_high": {"type": ["integer", "null"]}, "posted_date": _DATE,
    },
    "required": ["track_id", "position_title", "company_name"],
    "additionalProperties": False,
}


@bp.post("/lead/manual")
def create_manual_lead():
    body = request.get_json(silent=True)
    _validate(body, _MANUAL_LEAD_SCHEMA)
    db = get_db()
    post_id = f"manual-{uuid.uuid4()}"
    with db:
        db.execute(
            "INSERT INTO post (id, source, position_title, company_name, url_ref, posted_date, salary_high, is_open, src_method) "
            "VALUES (?, 'Manual', ?, ?, ?, ?, ?, 1, 'manual')",
            (post_id, body["position_title"], body["company_name"], body.get("url_ref") or str(uuid.uuid4()),
             body.get("posted_date") or clock.today().isoformat(), body.get("salary_high")),
        )
        lead_id = leads.promote(db, {"post_id": post_id, "track_id": body["track_id"]})
        lead = _fetch(db, REGISTRY["lead"], lead_id)
    return jsonify(lead), 201


register(Resource(
    "lead_note",
    create_schema={"type": "object", "properties": {"lead_id": {"type": "integer"},
                                                   "note": {"type": "string", "minLength": 1}},
                   "required": ["lead_id", "note"], "additionalProperties": False},
    update_schema=_ANY, verbs=frozenset({"get", "search", "create"}), create_fn=leads.add_note,
))
register(Resource("lead_event", create_schema=_ANY, update_schema=_ANY, verbs=READ_ONLY))
register(Resource("application", create_schema=_ANY, update_schema=_ANY, verbs=READ_ONLY))
