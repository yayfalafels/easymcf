"""REQ-CRM-01..08 — lead promotion, transitions, activity log, deadline maintenance, expiry."""

from __future__ import annotations

from datetime import date, timedelta

from .. import clock
from ..errors import Conflict, RecordNotFound, ValidationFailed

STAGES = ("TOAPPLY", "APPLIED", "CALLBACK", "INTERVIEW", "OFFER", "CLOSED")
CLOSE_REASONS = ("offer_accepted", "rejected", "withdrawn", "expired", "cancelled", "duplicate", "apply_failed", "dropped")
TRANSITIONS = {
    "TOAPPLY": {"APPLIED", "CLOSED"},
    "APPLIED": {"CALLBACK", "CLOSED"},
    "CALLBACK": {"INTERVIEW", "CLOSED"},
    "INTERVIEW": {"OFFER", "CLOSED"},
    "OFFER": {"CLOSED"},
    "CLOSED": set(),
}
ROLLING_STAGES = frozenset({"CALLBACK", "INTERVIEW", "OFFER"})
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


def promote(db, body: dict) -> int:
    post = db.execute("SELECT id, posted_date, closing_date FROM post WHERE id = ?", (body["post_id"],)).fetchone()
    if post is None:
        raise RecordNotFound(f"post {body['post_id']} not found")
    if db.execute("SELECT 1 FROM track WHERE id = ?", (body["track_id"],)).fetchone() is None:
        raise RecordNotFound(f"track {body['track_id']} not found")
    existing = db.execute("SELECT id FROM lead WHERE post_id = ?", (body["post_id"],)).fetchone()
    if existing:
        raise Conflict(f"post {body['post_id']} is already promoted", lead_id=existing["id"])
    at = clock.stamp()
    deadline = initial_deadline(post, clock.today()).isoformat()
    lead_id = db.execute(
        "INSERT INTO lead (post_id, track_id, status, stage, deadline, created_at, updated_at) "
        "VALUES (?, ?, 'OPEN', 'TOAPPLY', ?, ?, ?)",
        (body["post_id"], body["track_id"], deadline, at, at),
    ).lastrowid
    _event(db, lead_id, "stage_change", "promoted to TOAPPLY", at, None, "TOAPPLY")
    return lead_id


def _event_type(changed: dict) -> str:
    if "stage" in changed or "close_reason" in changed:
        return "stage_change"
    if "deadline" in changed:
        return "deadline_changed"
    if "last_contact_date" in changed:
        return "contact_logged"
    return "field_edited"


def update_lead(db, lead_id: int, body: dict) -> None:
    lead = _load(db, lead_id)
    changed = {k: v for k, v in body.items() if lead[k] != v}
    if not changed:
        return
    closing = changed.get("stage") == "CLOSED"
    if "stage" in changed and changed["stage"] not in TRANSITIONS[lead["stage"]]:
        raise Conflict(f"illegal transition {lead['stage']} -> {changed['stage']}")
    if closing and not body.get("close_reason"):
        raise ValidationFailed("close_reason is required when closing", field="close_reason")
    if body.get("close_reason") and not closing:
        raise ValidationFailed("close_reason applies only when closing", field="close_reason")
    values = {**changed, **({"status": "CLOSED"} if closing else {})}
    at = clock.stamp()
    _write(db, lead_id, values)
    detail = "; ".join(f"{k}: {lead[k]} -> {v}" for k, v in changed.items() if k != "stage") or None
    _event(db, lead_id, _event_type(changed), detail, at, lead["stage"], changed.get("stage", lead["stage"]))
    if "deadline" not in changed:
        _refresh_deadline(db, lead_id, at)


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
