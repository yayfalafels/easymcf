"""REQ-APPLY-02 — the CV label catalog's remove and re-add rules (11.IS.19).

A label in live use, the default of an active track or the effective CV of a queued (open TOAPPLY) lead, can't be removed: the
409 names those uses in plain words. A label that only history still uses, attempt rows or an archived track's
default, is retired instead: `is_active` goes to 0, pickers stop offering it, and every `application.cv_id` keeps
naming the CV that attempt used. A label nothing references is deleted. Adding a label equal to a retired one
reactivates that row rather than colliding with the (user_id, label) unique key.
"""

from __future__ import annotations

from ..errors import Conflict

_ACTIVE_TRACKS = (
    "SELECT track.id, role.name AS role_name, track.seniority FROM track JOIN role ON role.id = track.role_id "
    "WHERE track.default_cv_id = ? AND track.is_active = 1 ORDER BY track.id"
)
_OPEN_LEADS = (
    "SELECT lead.id FROM lead WHERE lead.status = 'OPEN' AND lead.stage = 'TOAPPLY' AND "
    "COALESCE(lead.cv_id, (SELECT default_cv_id FROM track WHERE track.id = lead.track_id)) = ? ORDER BY lead.id"
)
_HISTORY = (
    "SELECT (SELECT COUNT(*) FROM application WHERE cv_id = :id) + "
    "(SELECT COUNT(*) FROM track WHERE default_cv_id = :id) + (SELECT COUNT(*) FROM lead WHERE cv_id = :id)"
)


def remove(db, cv_id) -> dict | None:
    """Delete, retire, or refuse. Returns the kept row's id marker when retired, None when deleted."""
    cv_id = int(cv_id)  # the URL's text id never equals an INTEGER inside an affinity-free COALESCE (11.IS.19.03)
    label = db.execute("SELECT label FROM cv WHERE id = ?", (cv_id,)).fetchone()["label"]
    tracks = db.execute(_ACTIVE_TRACKS, (cv_id,)).fetchall()
    leads = [row["id"] for row in db.execute(_OPEN_LEADS, (cv_id,)).fetchall()]
    if tracks or leads:
        uses = []
        if tracks:
            names = ", ".join(f"{t['role_name']} ({t['seniority']})" for t in tracks)
            uses.append(f"the default of active track{'s' if len(tracks) > 1 else ''} {names}")
        if leads:
            uses.append(f"{len(leads)} queued lead{'s' if len(leads) > 1 else ''}")
        raise Conflict(f"CV '{label}' is still in use as {' and '.join(uses)}; choose another CV there first",
                       in_use={"track_ids": [t["id"] for t in tracks], "lead_ids": leads})
    if db.execute(_HISTORY, {"id": cv_id}).fetchone()[0]:
        db.execute("UPDATE cv SET is_active = 0 WHERE id = ?", (cv_id,))
        return {"id": cv_id, "retired": True}
    db.execute("DELETE FROM cv WHERE id = ?", (cv_id,))
    return None


def create(db, body: dict) -> int:
    """A new label, or the reactivated retired row of the same label."""
    retired = db.execute("SELECT id FROM cv WHERE user_id = ? AND label = ? AND is_active = 0",
                         (body["user_id"], body["label"])).fetchone()
    if retired:
        db.execute("UPDATE cv SET is_active = 1 WHERE id = ?", (retired["id"],))
        return retired["id"]
    try:
        return db.execute("INSERT INTO cv (user_id, label) VALUES (?, ?)", (body["user_id"], body["label"])).lastrowid
    except db.IntegrityError as exc:
        raise Conflict(f"CV '{body['label']}' already exists") from exc
