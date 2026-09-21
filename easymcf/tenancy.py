"""REQ-AUTH-06 - the single declaration of who owns what (ARCH-AUTH-04).

One SQL predicate per table, bound to the named parameter :uid. The generic CRUD blueprint appends the predicate to
every read, update, and delete, and services call require_visible(), so no route writes its own filter. A row
outside the predicate is indistinguishable from a missing row.
"""

from __future__ import annotations

from .errors import RecordNotFound

_OWN_TRACKS = "SELECT id FROM track WHERE user_id = :uid"
_OWN_LEADS = "SELECT id FROM lead WHERE user_id = :uid"

SCOPES = {
    "track": "track.user_id = :uid",
    "cv": "cv.user_id = :uid",
    "mcf_session": "mcf_session.user_id = :uid",
    "run_log": "run_log.user_id = :uid",
    "lead": "lead.user_id = :uid",
    "search_profile": f"search_profile.track_id IN ({_OWN_TRACKS})",
    "search_schedule": f"search_schedule.track_id IN ({_OWN_TRACKS})",
    "post_track": f"post_track.track_id IN ({_OWN_TRACKS})",
    "match_score": f"match_score.track_id IN ({_OWN_TRACKS})",
    "lead_note": f"lead_note.lead_id IN ({_OWN_LEADS})",
    "lead_event": f"lead_event.lead_id IN ({_OWN_LEADS})",
    "offer": f"offer.lead_id IN ({_OWN_LEADS})",
    "application": f"application.lead_id IN ({_OWN_LEADS})",
    "post": (
        f"(post.id IN (SELECT post_id FROM post_track WHERE track_id IN ({_OWN_TRACKS})) "
        f"OR post.id IN (SELECT post_id FROM lead WHERE user_id = :uid))"
    ),
}
UNSCOPED = frozenset({"role"})  # a shared catalog


def require_visible(db, uid: int, table: str, row_id, pk: str = "id") -> None:
    """Raise RecordNotFound unless the row exists and is visible to the user."""
    row = db.execute(
        f"SELECT 1 FROM {table} WHERE {table}.{pk} = :id AND {SCOPES[table]}", {"id": row_id, "uid": uid}
    ).fetchone()
    if row is None:
        raise RecordNotFound(f"{table} {row_id} not found")
