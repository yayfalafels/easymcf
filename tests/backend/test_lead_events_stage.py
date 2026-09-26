"""09.CK.10 — lead_event stage context written by the API paths, read directly from SQLite."""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta

import pytest

pytestmark = pytest.mark.backend


def _events(db_path: str, lead_id: int) -> list[tuple]:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(
            "SELECT event_type, stage_from, stage_to FROM lead_event WHERE lead_id = ? ORDER BY id", (lead_id,)).fetchall()
    finally:
        conn.close()


def _pin_after_anchor(db_path: str, fixed_clock, days: int = 5) -> None:
    anchor = sqlite3.connect(db_path).execute("SELECT substr(created_at, 1, 10) FROM lead WHERE id = 1").fetchone()[0]
    fixed_clock(f"{date.fromisoformat(anchor) + timedelta(days=days)}T07:00:00")


def _connected(events: list[tuple]) -> bool:
    return events[0][1] is None and all(events[i][1] == events[i - 1][2] for i in range(1, len(events)))


def test_system_promotion_runs_from_no_stage_to_toapply(isolated_client, isolated_db):
    lead_id = isolated_client.post("/api/v1/lead", json={"post_id": "synthetic-promote-future", "track_id": 1}).get_json()["id"]
    assert _events(isolated_db, lead_id) == [("stage_change", None, "TOAPPLY")]


def test_manual_add_runs_from_no_stage_to_applied(isolated_client, isolated_db):
    body = {"track_id": 1, "position_title": "Manual role", "company_name": "Manual Co"}
    lead = isolated_client.post("/api/v1/lead/manual", json=body).get_json()
    assert lead["stage"] == "APPLIED" and lead["applied_date"] is not None
    assert _events(isolated_db, lead["id"]) == [("stage_change", None, "APPLIED")]


def test_transition_and_close_events_record_both_stages(isolated_client, isolated_db):
    isolated_client.put("/api/v1/lead/1", json={"stage": "APPLIED"})
    assert _events(isolated_db, 1)[-1] == ("stage_change", "TOAPPLY", "APPLIED")
    isolated_client.put("/api/v1/lead/2", json={"stage": "CLOSED", "close_reason": "rejected"})
    assert _events(isolated_db, 2)[-1] == ("stage_change", "APPLIED", "CLOSED")


def test_note_contact_and_field_events_hold_the_stage(isolated_client, isolated_db, fixed_clock):
    _pin_after_anchor(isolated_db, fixed_clock, days=0)
    isolated_client.post("/api/v1/lead_note", json={"lead_id": 3, "note": "chased"})
    assert _events(isolated_db, 3)[-1] == ("note_edited", "CALLBACK", "CALLBACK")
    isolated_client.put("/api/v1/lead/4", json={"last_contact_date": "2026-09-19"})
    isolated_client.put("/api/v1/lead/4", json={"position_title": "Renamed"})
    isolated_client.put("/api/v1/lead/4", json={"deadline": "2031-01-01"})
    assert _events(isolated_db, 4)[-3:] == [
        ("contact_logged", "INTERVIEW", "INTERVIEW"), ("field_edited", "INTERVIEW", "INTERVIEW"),
        ("deadline_changed", "INTERVIEW", "INTERVIEW")]


def test_callback_transition_writes_the_transition_then_the_refresh(isolated_client, isolated_db, fixed_clock):
    _pin_after_anchor(isolated_db, fixed_clock)
    isolated_client.put("/api/v1/lead/2", json={"stage": "CALLBACK"})
    assert _events(isolated_db, 2)[-2:] == [("stage_change", "APPLIED", "CALLBACK"), ("deadline_changed", "CALLBACK", "CALLBACK")]


def test_auto_expiry_event_runs_from_the_stage_at_expiry(isolated_client, isolated_db, fixed_clock):
    conn = sqlite3.connect(isolated_db)
    conn.execute("UPDATE lead SET deadline = '2026-01-01' WHERE id IN (1, 2)")
    conn.commit()
    _pin_after_anchor(isolated_db, fixed_clock)
    isolated_client.get("/api/v1/lead/search")
    assert _events(isolated_db, 1)[-1] == ("stage_change", "TOAPPLY", "CLOSED")
    assert _events(isolated_db, 2)[-1] == ("stage_change", "APPLIED", "CLOSED")


def test_events_stay_a_connected_chain_after_a_write_sequence(isolated_client, isolated_db, fixed_clock):
    _pin_after_anchor(isolated_db, fixed_clock)
    isolated_client.put("/api/v1/lead/2", json={"stage": "CALLBACK"})
    isolated_client.post("/api/v1/lead_note", json={"lead_id": 2, "note": "hello"})
    isolated_client.put("/api/v1/lead/2", json={"stage": "INTERVIEW"})
    isolated_client.put("/api/v1/lead/2", json={"stage": "CLOSED", "close_reason": "withdrawn"})
    events = _events(isolated_db, 2)
    assert _connected(events)
    assert events[-1][2] == "CLOSED"


def test_search_returns_and_filters_the_stage_fields(isolated_client):
    rows = isolated_client.get("/api/v1/lead_event/search?stage_to=CLOSED").get_json()
    assert rows and all(row["stage_to"] == "CLOSED" and "stage_from" in row for row in rows)


@pytest.mark.parametrize("event_type,stage_from,stage_to", [
    ("stage_change", "APPLIED", "APPLIED"),
    ("note_edited", None, "APPLIED"),
    ("note_edited", "APPLIED", "CALLBACK"),
    ("stage_change", "APPLIED", "NOPE"),
    ("stage_change", "APPLIED", None),
    ("stage_change", "PROSPECT", "APPLIED"),
    ("stage_change", None, "PROSPECT"),
])
def test_schema_rejects_inconsistent_stage_pairs(isolated_db, event_type, stage_from, stage_to):
    conn = sqlite3.connect(isolated_db)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO lead_event (lead_id, event_type, stage_from, stage_to, occurred_at) VALUES (1, ?, ?, ?, '2026-09-19 07:00:00')",
            (event_type, stage_from, stage_to))
    conn.close()
