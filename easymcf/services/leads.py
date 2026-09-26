"""REQ-CRM-01..11 — lead creation, transitions, batch moves, activity log, deadline maintenance, expiry."""

from __future__ import annotations

from datetime import date, timedelta

from .. import clock, tenancy
from ..errors import Conflict, RecordNotFound, ValidationFailed

STAGES = ("TOAPPLY", "APPLIED", "CALLBACK", "INTERVIEW", "OFFER", "CLOSED")
CLOSE_REASONS = ("offer_accepted", "rejected", "withdrawn", "expired", "cancelled", "duplicate", "apply_failed",
                  "dropped", "track_not_matched")
TRANSITIONS = {
    "TOAPPLY": {"APPLIED", "CLOSED"},
    "APPLIED": {"CALLBACK", "CLOSED"},
    "CALLBACK": {"INTERVIEW", "CLOSED"},
    "INTERVIEW": {"OFFER", "CLOSED"},
    "OFFER": {"CLOSED"},
    "CLOSED": {"INTERVIEW"},  # re-open, legal only for a lead closed from OFFER (see _check_gates)
}
ROLLING_STAGES = frozenset({"CALLBACK", "INTERVIEW"})
BATCH_MAX = 200
ROLLING_DAYS = 28
UNDATED_POST_DAYS = 28
PAST_CLOSING_DAYS = 7


def _date(value: str | None) -> date | None:
    return date.fromisoformat(value[:10]) if value else None


def initial_deadline(post, promoted_on: date) -> date:
    closing = _date(post["closing_date"])
    if closing is None:
        posted = _date(post["posted_date"]) or promoted_on
        return posted + timedelta(days=UNDATED_POST_DAYS)
    if closing > promoted_on:
        return closing
    return promoted_on + timedelta(days=PAST_CLOSING_DAYS)


def _load(db, lead_id: int):
    row = db.execute("SELECT * FROM lead WHERE id = ?", (lead_id,)).fetchone()
    if row is None:
        raise RecordNotFound(f"lead {lead_id} not found")
    return row


def _event(db, lead_id: int, event_type: str, detail: str | None, at: str,
           stage_from: str | None, stage_to: str) -> None:
    db.execute(
        "INSERT INTO lead_event (lead_id, event_type, detail, stage_from, stage_to, occurred_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (lead_id, event_type, detail, stage_from, stage_to, at),
    )
    db.execute("UPDATE lead SET updated_at = ? WHERE id = ?", (at, lead_id))


def _write(db, lead_id: int, values: dict) -> None:
    sets = ", ".join(f"{column} = ?" for column in values)
    db.execute(f"UPDATE lead SET {sets} WHERE id = ?", (*values.values(), lead_id))


def _refresh_deadline(db, lead_id: int, at: str) -> None:
    lead = _load(db, lead_id)
    if lead["status"] != "OPEN" or lead["stage"] not in ROLLING_STAGES:
        return
    target = (clock.today() + timedelta(days=ROLLING_DAYS)).isoformat()
    if lead["deadline"] != target:
        _write(db, lead_id, {"deadline": target})
        _event(db, lead_id, "deadline_changed", f"deadline: {lead['deadline']} -> {target}", at,
               lead["stage"], lead["stage"])


def _profile_salary(db, track_id: int) -> int | None:
    row = db.execute("SELECT min_salary FROM search_profile WHERE track_id = ?", (track_id,)).fetchone()
    return row["min_salary"] if row else None


def promote(db, body: dict, *, stage: str = "TOAPPLY", copies: dict | None = None) -> int:
    """Create a lead. The search process calls it at TOAPPLY, manual add at APPLIED (REQ-CRM-01)."""
    post = db.execute(
        "SELECT id, position_title, company_name, url_ref, posted_date, closing_date FROM post WHERE id = ?", (body["post_id"],)).fetchone()
    if post is None:
        raise RecordNotFound(f"post {body['post_id']} not found")
    track = db.execute("SELECT user_id FROM track WHERE id = ?", (body["track_id"],)).fetchone()
    if track is None:
        raise RecordNotFound(f"track {body['track_id']} not found")
    existing = db.execute("SELECT id FROM lead WHERE user_id = ? AND post_id = ?", (track["user_id"], body["post_id"])).fetchone()
    if existing:
        raise Conflict(f"post {body['post_id']} is already promoted", lead_id=existing["id"])
    at = clock.stamp()
    deadline = initial_deadline(post, clock.today()).isoformat()
    salary = body.get("expected_salary_sgd", _profile_salary(db, body["track_id"]))
    values = {"position_title": post["position_title"], "company_name": post["company_name"], "url_ref": post["url_ref"], **(copies or {})}
    lead_id = db.execute(
        "INSERT INTO lead (user_id, post_id, track_id, status, stage, position_title, company_name, url_ref, deadline, "
        "applied_date, expected_salary_sgd, created_at, updated_at) VALUES (?, ?, ?, 'OPEN', ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (track["user_id"], body["post_id"], body["track_id"], stage, values["position_title"], values["company_name"],
         values["url_ref"], deadline, at[:10] if stage == "APPLIED" else None, salary, at, at),
    ).lastrowid
    detail = "promoted to TOAPPLY" if stage == "TOAPPLY" else f"added manually at {stage}"
    _event(db, lead_id, "stage_change", detail, at, None, stage)
    return lead_id


def _event_type(changed: dict) -> str:
    if "stage" in changed or "close_reason" in changed:
        return "stage_change"
    if "deadline" in changed:
        return "deadline_changed"
    if "last_contact_date" in changed:
        return "contact_logged"
    return "field_edited"


def _closed_from(db, lead_id: int) -> str | None:
    row = db.execute(
        "SELECT stage_from FROM lead_event WHERE lead_id = ? AND stage_to = 'CLOSED' ORDER BY id DESC LIMIT 1", (lead_id,)
    ).fetchone()
    return row["stage_from"] if row else None


def _check_gates(db, lead, new_stage: str) -> None:
    """Stage moves that only the offer routes (or the re-open rule) may perform (REQ-CRM-10)."""
    if new_stage == "OFFER":
        raise Conflict("an offer is required to reach OFFER: create it with POST /api/v1/offer", lead_id=lead["id"])
    if lead["stage"] == "OFFER" and new_stage == "CLOSED":
        raise Conflict("close the lead through its offer: PUT /api/v1/offer/{id}", lead_id=lead["id"])
    if lead["stage"] == "CLOSED" and _closed_from(db, lead["id"]) != "OFFER":
        raise Conflict("only a lead closed from OFFER can be re-opened", lead_id=lead["id"])


def _check_track(db, track_id: int, owner_id: int) -> None:
    """A lead can move only to an existing, active track (REQ-CRM-12)."""
    track = db.execute("SELECT is_active, user_id FROM track WHERE id = ?", (track_id,)).fetchone()
    if track is None:
        raise ValidationFailed(f"track {track_id} not found", field="track_id")
    if not track["is_active"]:
        raise ValidationFailed(f"track {track_id} is archived", field="track_id")
    if track["user_id"] != owner_id:
        raise ValidationFailed(f"track {track_id} belongs to another user", field="track_id")


def update_lead(db, lead_id: int, body: dict, *, internal: bool = False, detail: str | None = None) -> None:
    """The single lead write path. `internal` lets the offer service perform its own stage moves."""
    lead = _load(db, lead_id)
    changed = {k: v for k, v in body.items() if lead[k] != v}
    if not changed:
        return
    if "track_id" in changed:
        _check_track(db, changed["track_id"], lead["user_id"])
    new_stage = changed.get("stage")
    closing = new_stage == "CLOSED"
    reopening = new_stage == "INTERVIEW" and lead["stage"] == "CLOSED"
    if new_stage is not None:
        if new_stage not in TRANSITIONS[lead["stage"]]:
            raise Conflict(f"illegal transition {lead['stage']} -> {new_stage}", lead_id=lead_id)
        if not internal:
            _check_gates(db, lead, new_stage)
    if closing and not body.get("close_reason"):
        raise ValidationFailed("close_reason is required when closing", field="close_reason", lead_id=lead_id)
    if body.get("close_reason") and not closing:
        raise ValidationFailed("close_reason applies only when closing", field="close_reason", lead_id=lead_id)
    values = dict(changed)
    if closing:
        values["status"] = "CLOSED"
    if reopening:
        values.update(status="OPEN", close_reason=None)
    at = clock.stamp()
    _write(db, lead_id, values)
    if detail is None:
        detail = "re-opened from an offer" if reopening else (
            "; ".join(f"{k}: {lead[k]} -> {v}" for k, v in changed.items() if k != "stage") or None)
    _event(db, lead_id, _event_type(changed), detail, at, lead["stage"], new_stage or lead["stage"])
    if "deadline" not in changed:
        _refresh_deadline(db, lead_id, at)


def batch_update(db, rows: list, uid: int | None = None) -> list[int]:
    """POST /lead/batch: stage moves for many leads, atomic under the caller's transaction (REQ-CRM-11)."""
    if not 1 <= len(rows) <= BATCH_MAX:
        raise ValidationFailed(f"rows must hold 1 to {BATCH_MAX} entries", field="rows")
    ids = [row.get("id") for row in rows]
    if len(set(ids)) != len(ids):
        raise ValidationFailed("rows must not repeat an id", field="rows")
    for row in rows:
        if uid is not None:
            tenancy.require_visible(db, uid, "lead", row["id"])   # another user's lead answers 404 and rolls the batch back
        update_lead(db, row["id"], {k: v for k, v in row.items() if k != "id"})
    return ids


def add_note(db, body: dict) -> int:
    lead = _load(db, body["lead_id"])
    at = clock.stamp()
    note_id = db.execute(
        "INSERT INTO lead_note (lead_id, note, created_at) VALUES (?, ?, ?)", (lead["id"], body["note"], at)
    ).lastrowid
    _event(db, lead["id"], "note_edited", body["note"][:80], at, lead["stage"], lead["stage"])
    _refresh_deadline(db, lead["id"], at)
    return note_id


def expire_due(db) -> None:
    today = clock.today().isoformat()
    for row in db.execute("SELECT id, stage FROM lead WHERE status = 'OPEN' AND deadline < ?", (today,)).fetchall():
        with db:
            at = clock.stamp()
            _write(db, row["id"], {"stage": "CLOSED", "status": "CLOSED", "close_reason": "expired"})
            _event(db, row["id"], "stage_change", "auto-closed: deadline passed", at, row["stage"], "CLOSED")
            db.execute("UPDATE offer SET status = 'expired', updated_at = ? WHERE lead_id = ? AND status = 'open'", (at, row["id"]))
