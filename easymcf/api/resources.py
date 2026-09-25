"""Resource declarations. Importing this module registers them with generic.register()."""

from __future__ import annotations

import uuid

from flask import current_app, g, jsonify, request

from .. import clock
from .. import tenancy
from ..errors import ValidationFailed
from ..services import leads, mcf_connection, offers, search
from .db import get_db
from .generic import GENERIC, REGISTRY, Resource, _fetch, _guarded, _insert, _scope_sql, _select, _serialize, _validate, bp, register

READ_ONLY = frozenset({"get", "search"})
_DATE = {"type": ["string", "null"], "pattern": r"^\d{4}-\d{2}-\d{2}$"}
_ANY = {"type": "object"}


def _owner(db, uid: int) -> dict:
    """The server-set owner of a new row (ARCH-AUTH-04). A client body can never carry user_id."""
    return {"user_id": uid}


_TRACK_PROPS = {
    "role_id": {"type": "integer"},
    "seniority": {"type": "string", "minLength": 1},
    "default_cv_id": {"type": ["integer", "null"]},
    "is_active": {"type": ["boolean", "integer"]},
}


def _create_track(db, body: dict) -> int:
    """Workflow 1 — a new track also gets its default search_profile/search_schedule
    rows, in the same transaction, so the data model's exactly-one-per-track holds from
    the first moment (10.EL.08)."""
    track_id = _guarded(_insert, db, REGISTRY["track"], body)
    role_name = db.execute("SELECT name FROM role WHERE id = ?", (body["role_id"],)).fetchone()["name"]
    db.execute(
        "INSERT INTO search_profile (track_id, keywords, min_match_score, employment_type) "
        "VALUES (?, ?, 0.3, 'Full Time')",
        (track_id, role_name),
    )
    db.execute(
        "INSERT INTO search_schedule (track_id, schedule_enabled, schedule_interval_hours) VALUES (?, 0, 24)",
        (track_id,),
    )
    return track_id


register(Resource(
    "track",
    create_schema={"type": "object", "properties": _TRACK_PROPS,
                   "required": ["role_id", "seniority"], "additionalProperties": False},
    update_schema={"type": "object", "properties": _TRACK_PROPS, "additionalProperties": False},
    verbs=frozenset({"get", "search", "create", "update"}),
    bool_columns=("is_active",),
    select_sql="SELECT track.*, role.name AS role_name FROM track JOIN role ON role.id = track.role_id",
    owned=_owner, parents=(("default_cv_id", "cv"),), create_fn=_create_track,
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
    create_schema={"type": "object", "properties": _CV_PROPS, "required": ["label"], "additionalProperties": False},
    update_schema={"type": "object", "properties": _CV_PROPS, "required": ["label"], "additionalProperties": False},
    verbs=frozenset({"get", "search", "create", "update", "delete"}), owned=_owner,
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
    verbs=frozenset({"get", "search", "create", "update"}), pk="track_id", parents=(("track_id", "track"),),
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
    parents=(("track_id", "track"),),
))
# A post is shared and read-only to every user (REQ-AUTH-06). Only the search run and the manual entry endpoints
# write it. Its `search` verb is hook-backed (10.EL.13/search_fn, api design row 06): a bare column filter on the
# `post` table alone cannot express "this track's posts with this pairing's match_score/search_match/lead_id",
# since those columns live in post_track/match_score/lead, not on post itself.
def _post_search(db, uid: int, args) -> list[dict]:
    """With a track_id (api design row 06): the per-track joined read the Posts page needs.
    Without one: the same plain tenancy-scoped listing the generic search() produced for
    `post` before this hook existed (10.IS.08) — test_tenancy.py's own oracle cases call
    GET /api/v1/post/search with no track_id and expect that bare shape back."""
    track_id = args.get("track_id", type=int)
    if track_id is not None:
        return search.posts_for_track(db, uid, track_id, args.get("max_age_weeks", type=int))
    resource = REGISTRY["post"]
    sql = f"{_select(resource)} WHERE {_scope_sql(resource)} ORDER BY {resource.table}.{resource.pk}"
    return [_serialize(resource, row) for row in db.execute(sql, {"uid": uid}).fetchall()]


register(Resource(
    "post", create_schema=_ANY, update_schema=_ANY, verbs=READ_ONLY, bool_columns=("is_open",), search_fn=_post_search,
))
# run_log is written only by search.start_run/_run_search (and, later, the apply pipeline); this registers the
# generic-shaped, tenancy-scoped GET /api/v1/run_log/{id}|search poll a triggered run's client uses (REQ-PLAT-03).
register(Resource("run_log", create_schema=_ANY, update_schema=_ANY, verbs=READ_ONLY))

_MANUAL_POST_SCHEMA = {
    "type": "object",
    "properties": {
        "track_id": {"type": "integer"}, "position_title": {"type": "string", "minLength": 1},
        "company_name": {"type": "string", "minLength": 1}, "url_ref": {"type": ["string", "null"]},
        "salary_high": {"type": ["integer", "null"]}, "posted_date": _DATE,
    },
    "required": ["track_id", "position_title", "company_name"],
    "additionalProperties": False,
}


@bp.post("/runs/search")
def trigger_search_run():
    body = request.get_json(silent=True) or {}
    if not isinstance(body.get("track_id"), int):
        raise ValidationFailed("track_id is required", field="track_id")
    db, uid = get_db(), g.user_id
    tenancy.require_visible(db, uid, "track", body["track_id"])
    run = search.start_run(db, uid, body["track_id"], trigger_source="manual")
    return jsonify(dict(run)), 201


@bp.post("/posts/manual")
def create_manual_post():
    body = request.get_json(silent=True)
    _validate(body, _MANUAL_POST_SCHEMA)
    db, uid = get_db(), g.user_id
    result = search.add_manual_post(db, uid, body["track_id"], body)
    return jsonify(result), 201

# mcf_attempt is written only through its own named endpoints (mcf_attempt_routes.py); this registers the
# generic-shaped, tenancy-scoped GET /api/v1/mcf_attempt/search poll, run_log's own trigger-plus-generic-read split.
register(Resource("mcf_attempt", create_schema=_ANY, update_schema=_ANY, verbs=READ_ONLY))
# mcf_session itself had no read endpoint before this feature (17.IS.03): signup (auth/accounts.py,
# auth/google.py) and mcf_connection.confirm()/cancel() are its only writers, and the frontend status
# page/badge need to read it the same generic-shaped, tenancy-scoped way.
def _reconcile_mcf_session_read(db) -> None:
    mcf_connection.reconcile_local_sessions(current_app.config["EASYMCF_CONFIG"], db=db)


register(Resource(
    "mcf_session", create_schema=_ANY, update_schema=_ANY, verbs=READ_ONLY,
    before_read=_reconcile_mcf_session_read,
))

_LEAD_SELECT = (
    "SELECT lead.*, "
    "(SELECT note FROM lead_note WHERE lead_note.lead_id = lead.id ORDER BY lead_note.id DESC LIMIT 1) AS latest_note, "
    "offer.id AS offer_id, offer.amount_sgd AS offer_amount_sgd, offer.offer_date AS offer_date, "
    "offer.deadline AS offer_deadline, offer.status AS offer_status, "
    "(SELECT stage_from FROM lead_event WHERE lead_event.lead_id = lead.id AND lead_event.stage_to = 'CLOSED' "
    "ORDER BY lead_event.id DESC LIMIT 1) AS closed_from "
    "FROM lead "
    "LEFT JOIN offer ON offer.lead_id = lead.id AND offer.status = 'open'"
)
_SALARY = {"type": ["integer", "null"], "minimum": 0}
register(Resource(
    "lead",
    create_schema={"type": "object", "properties": {"post_id": {"type": "string", "minLength": 1},
                                                   "track_id": {"type": "integer"}},
                   "required": ["post_id", "track_id"], "additionalProperties": False},
    update_schema={"type": "object", "additionalProperties": False, "properties": {
        "stage": {"enum": list(leads.STAGES)},
        "close_reason": {"enum": [*leads.CLOSE_REASONS, None]},
        "position_title": {"type": "string", "minLength": 1},
        "company_name": {"type": "string", "minLength": 1},
        "url_ref": {"type": ["string", "null"], "pattern": r"^https?://\S+$"},
        "deadline": _DATE, "applied_date": _DATE,
        "first_attempt_date": _DATE, "last_contact_date": _DATE,
        "expected_salary_sgd": _SALARY, "track_id": {"type": "integer"}}},
    verbs=frozenset({"get", "search", "create", "update", "batch"}),
    select_sql=_LEAD_SELECT,
    create_fn=leads.promote, update_fn=leads.update_lead, before_read=leads.expire_due,
    batch_schema={"type": "object", "additionalProperties": False, "required": ["id", "stage"], "properties": {
        "id": {"type": "integer"}, "stage": {"enum": list(leads.STAGES)},
        "close_reason": {"enum": [*leads.CLOSE_REASONS, None]}}},
    batch_fn=leads.batch_update,
    parents=(("track_id", "track"), ("post_id", "post")),
))

_MANUAL_LEAD_SCHEMA = {
    "type": "object",
    "properties": {
        "track_id": {"type": "integer"}, "position_title": {"type": "string", "minLength": 1},
        "company_name": {"type": "string", "minLength": 1}, "url_ref": {"type": ["string", "null"]},
        "salary_high": {"type": ["integer", "null"]}, "posted_date": _DATE, "expected_salary_sgd": _SALARY,
    },
    "required": ["track_id", "position_title", "company_name"],
    "additionalProperties": False,
}


@bp.post("/lead/manual")
def create_manual_lead():
    body = request.get_json(silent=True)
    _validate(body, _MANUAL_LEAD_SCHEMA)
    db, uid = get_db(), g.user_id
    tenancy.require_visible(db, uid, "track", body["track_id"])
    post_id = f"manual-{uuid.uuid4()}"
    with db:
        db.execute(
            "INSERT INTO post (id, source, position_title, company_name, url_ref, posted_date, salary_high, is_open, src_method) "
            "VALUES (?, 'Manual', ?, ?, ?, ?, ?, 1, 'manual')",
            (post_id, body["position_title"], body["company_name"], body.get("url_ref") or str(uuid.uuid4()),
             body.get("posted_date") or clock.today().isoformat(), body.get("salary_high")),
        )
        lead_body = {"post_id": post_id, "track_id": body["track_id"]}
        if "expected_salary_sgd" in body:
            lead_body["expected_salary_sgd"] = body["expected_salary_sgd"]
        copies = {"position_title": body["position_title"], "company_name": body["company_name"], "url_ref": body.get("url_ref")}
        lead_id = leads.promote(db, lead_body, stage="APPLIED", copies=copies)
        lead = _fetch(db, REGISTRY["lead"], lead_id, uid)
    return jsonify(lead), 201


register(Resource(
    "lead_note",
    create_schema={"type": "object", "properties": {"lead_id": {"type": "integer"},
                                                   "note": {"type": "string", "minLength": 1}},
                   "required": ["lead_id", "note"], "additionalProperties": False},
    update_schema=_ANY, verbs=frozenset({"get", "search", "create"}), create_fn=leads.add_note,
    parents=(("lead_id", "lead"),),
))
register(Resource("lead_event", create_schema=_ANY, update_schema=_ANY, verbs=READ_ONLY))
register(Resource("application", create_schema=_ANY, update_schema=_ANY, verbs=READ_ONLY))

_OFFER_PROPS = {"amount_sgd": {"type": "integer", "minimum": 1}, "deadline": _DATE}
register(Resource(
    "offer",
    create_schema={"type": "object", "properties": {"lead_id": {"type": "integer"}, "offer_date": {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"}, **_OFFER_PROPS},
                   "required": ["lead_id", "offer_date", "amount_sgd"], "additionalProperties": False},
    update_schema={"type": "object", "properties": {**_OFFER_PROPS, "status": {"type": "string"}}, "additionalProperties": False},
    verbs=frozenset({"get", "search", "create", "update"}),
    select_sql=("SELECT offer.*, lead.position_title AS lead_title, lead.company_name AS lead_company, lead.track_id "
                "FROM offer JOIN lead ON lead.id = offer.lead_id"),
    create_fn=offers.create_offer, update_fn=offers.update_offer, parents=(("lead_id", "lead"),),
))
