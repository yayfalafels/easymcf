from __future__ import annotations

import sqlite3
from datetime import date, timedelta

import pytest

pytestmark = pytest.mark.backend

LEAD_STAGES = {"TOAPPLY", "APPLIED", "CALLBACK", "INTERVIEW", "OFFER", "CLOSED"}
CLOSE_REASONS = {"offer_accepted", "rejected", "withdrawn", "expired", "cancelled", "duplicate", "apply_failed", "dropped"}
APPLICATION_STATUSES = {
    "applied", "questionnaire_required", "cv_selector_error", "unable_to_apply",
    "post_unavailable", "cv_not_found", "post_closed", "invalid_input",
}
RUN_STATUSES = {"running", "success", "partial", "failed"}


@pytest.fixture()
def conn(db_path):
    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")
    yield connection
    connection.close()


def distinct(connection, query):
    return {row[0] for row in connection.execute(query)}


def test_track_and_post_coverage(conn):
    total, archived = conn.execute("SELECT COUNT(*), SUM(1 - is_active) FROM track").fetchone()
    assert total >= 2
    assert archived >= 1
    assert distinct(conn, "SELECT DISTINCT src_method FROM post") == {"scraped", "manual"}
    assert conn.execute("SELECT COUNT(*) FROM (SELECT post_id FROM post_track GROUP BY post_id HAVING COUNT(*) > 1)").fetchone()[0] >= 1


def test_two_users_with_distinct_data(conn):
    assert conn.execute("SELECT COUNT(*) FROM user").fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM track WHERE user_id = 2").fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM lead WHERE user_id = 2").fetchone()[0] == 4
    assert conn.execute("SELECT COUNT(*) FROM cv WHERE user_id = 2").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM lead_note WHERE lead_id IN (SELECT id FROM lead WHERE user_id = 2)").fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM run_log WHERE user_id = 2").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM mcf_session").fetchone()[0] == 2


def test_ownership_columns_are_consistent(conn):
    assert conn.execute("SELECT COUNT(*) FROM lead JOIN track ON track.id = lead.track_id WHERE lead.user_id != track.user_id").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM track JOIN cv ON cv.id = track.default_cv_id WHERE cv.user_id != track.user_id").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM mcf_session WHERE user_id != id").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM lead WHERE position_title = '' OR company_name = ''").fetchone()[0] == 0


def test_seeded_passwords_verify(conn):
    from werkzeug.security import check_password_hash
    rows = dict(conn.execute("SELECT id, password_hash FROM user"))
    assert rows[1].startswith("scrypt:") and check_password_hash(rows[1], "Seed-Password-1!")
    assert check_password_hash(rows[2], "Seed-Password-2!")
    assert rows[1] != rows[2]
    assert conn.execute("SELECT COUNT(*) FROM user WHERE google_sub IS NOT NULL OR photo_ref IS NOT NULL").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM auth_session").fetchone()[0] == 0


def test_shared_posts_and_per_user_leads(conn):
    matched_to_both = conn.execute(
        "SELECT COUNT(*) FROM (SELECT pt.post_id FROM post_track pt JOIN track t ON t.id = pt.track_id "
        "GROUP BY pt.post_id HAVING COUNT(DISTINCT t.user_id) = 2)").fetchone()[0]
    assert matched_to_both >= 1
    only_user_2 = conn.execute(
        "SELECT COUNT(*) FROM (SELECT pt.post_id FROM post_track pt JOIN track t ON t.id = pt.track_id "
        "GROUP BY pt.post_id HAVING MIN(t.user_id) = 2)").fetchone()[0]
    assert only_user_2 == 3
    both_lead = conn.execute("SELECT COUNT(*) FROM (SELECT post_id FROM lead GROUP BY post_id HAVING COUNT(DISTINCT user_id) = 2)").fetchone()[0]
    assert both_lead == 1


def test_match_score_paired_with_post_track(conn):
    unpaired = conn.execute(
        "SELECT COUNT(*) FROM post_track pt LEFT JOIN match_score ms "
        "ON ms.post_id = pt.post_id AND ms.track_id = pt.track_id WHERE ms.post_id IS NULL"
    ).fetchone()[0]
    assert unpaired == 0
    assert conn.execute("SELECT COUNT(*) FROM match_score").fetchone()[0] >= 1


def test_lead_note_history(conn):
    assert conn.execute("SELECT COUNT(*) FROM lead_note").fetchone()[0] >= 1
    bad = conn.execute(
        "SELECT ln.id FROM lead_note ln LEFT JOIN lead l ON l.id = ln.lead_id WHERE l.id IS NULL"
    ).fetchall()
    assert bad == []


def test_closed_vocabularies_are_complete(conn):
    assert LEAD_STAGES <= distinct(conn, "SELECT DISTINCT stage FROM lead")
    assert CLOSE_REASONS <= distinct(conn, "SELECT DISTINCT close_reason FROM lead WHERE status = 'CLOSED'")
    assert APPLICATION_STATUSES <= distinct(conn, "SELECT DISTINCT status FROM application")
    assert RUN_STATUSES <= distinct(conn, "SELECT DISTINCT status FROM run_log")


def test_retry_pair_and_apply_failed_linkage(conn):
    assert conn.execute("SELECT COUNT(*) FROM (SELECT lead_id FROM application GROUP BY lead_id HAVING COUNT(*) > 1)").fetchone()[0] >= 1
    bad = conn.execute(
        "SELECT a.id FROM application a JOIN lead l ON l.id = a.lead_id "
        "WHERE a.status IN ('post_closed', 'post_unavailable') AND l.close_reason != 'apply_failed'"
    ).fetchall()
    assert bad == []


EVENT_TYPES = {"stage_change", "contact_logged", "note_edited", "deadline_changed", "field_edited"}
SEEDED_ROLES = {"Data Analyst", "Sustainability Consultant", "Data Engineer", "Data Scientist",
                "Software Developer", "Gen AI Developer"}


def test_event_type_enumeration_is_complete(conn):
    assert EVENT_TYPES <= distinct(conn, "SELECT DISTINCT event_type FROM lead_event")


def test_seeded_user_identity(conn):
    assert conn.execute("SELECT name, email FROM user ORDER BY id").fetchall() == [
        ("Taylor Hickem", "yayfalafels@gmail.com"), ("Sam Second", "second.user@example.test")]


def test_seeded_roles_and_tracks(conn):
    assert distinct(conn, "SELECT name FROM role") == SEEDED_ROLES
    rows = conn.execute("SELECT r.name, t.is_active, t.default_cv_id FROM track t JOIN role r ON r.id = t.role_id WHERE t.user_id = 1").fetchall()
    assert {row[0] for row in rows} == SEEDED_ROLES
    new = {row[0]: row for row in rows if row[0] in SEEDED_ROLES - {"Data Analyst", "Sustainability Consultant"}}
    assert len(new) == 4 and all(row[1] == 1 for row in new.values())
    assert all(row[2] == 1 for row in rows)


def test_every_track_has_a_profile_and_a_disabled_schedule(conn):
    tracks = distinct(conn, "SELECT id FROM track")
    assert distinct(conn, "SELECT track_id FROM search_profile") == tracks
    schedules = conn.execute("SELECT track_id, schedule_enabled, schedule_interval_hours, next_run_at FROM search_schedule").fetchall()
    assert {row[0] for row in schedules} == tracks
    assert all(row[1:] == (0, 24, None) for row in schedules)


def test_new_track_profiles_use_the_role_name_as_keywords(conn):
    rows = conn.execute("SELECT r.name, p.keywords FROM search_profile p JOIN track t ON t.id = p.track_id JOIN role r ON r.id = t.role_id").fetchall()
    assert all(name == keywords for name, keywords in rows)


def test_promotable_posts_cover_the_three_deadline_branches(conn):
    rows = conn.execute(
        "SELECT p.id, p.closing_date, p.posted_date FROM post p LEFT JOIN lead l ON l.post_id = p.id "
        "WHERE p.id LIKE 'synthetic-promote-%' AND l.id IS NULL ORDER BY p.id").fetchall()
    assert [row[0] for row in rows] == ["synthetic-promote-future", "synthetic-promote-nodate", "synthetic-promote-past"]
    future, nodate, past = rows
    assert future[1] > future[2] and nodate[1] is None and past[1] is not None
    assert conn.execute("SELECT COUNT(*) FROM post_track WHERE post_id LIKE 'synthetic-promote-%'").fetchone()[0] == 3


def test_open_leads_start_inside_their_deadline(conn):
    assert conn.execute(
        "SELECT COUNT(*) FROM lead WHERE status = 'OPEN' AND deadline <= date(created_at)").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM lead WHERE status = 'OPEN' AND deadline IS NULL").fetchone()[0] == 0


@pytest.mark.parametrize("post,offset_days", [
    ("synthetic-promote-future", None),
    ("synthetic-promote-nodate", "posted_plus_28"),
    ("synthetic-promote-past", 7),
])
def test_initial_deadline_branches(isolated_client, isolated_db, fixed_clock, post, offset_days):
    posted, closing = sqlite3.connect(isolated_db).execute(
        "SELECT posted_date, closing_date FROM post WHERE id = ?", (post,)).fetchone()
    promoted_on = date.fromisoformat(posted) + timedelta(days=3)
    fixed_clock(f"{promoted_on}T07:00:00")
    lead = isolated_client.post("/api/v1/lead", json={"post_id": post, "track_id": 1}).get_json()
    expected = {None: closing,
                "posted_plus_28": (date.fromisoformat(posted) + timedelta(days=28)).isoformat(),
                7: (promoted_on + timedelta(days=7)).isoformat()}[offset_days]
    assert lead["deadline"] == expected


def test_rolling_deadline_27_and_29_days(isolated_client, isolated_db, fixed_clock):
    conn = sqlite3.connect(isolated_db)
    conn.execute("UPDATE lead SET stage = 'CALLBACK', deadline = '2026-10-12' WHERE id = 1")
    conn.execute("UPDATE lead SET stage = 'CALLBACK', deadline = '2026-10-10' WHERE id = 2")
    conn.commit()
    fixed_clock("2026-10-11T07:00:00")
    leads = {l["id"]: l for l in isolated_client.get("/api/v1/lead/search").get_json()}
    assert leads[1]["status"] == "OPEN"
    assert leads[2]["status"] == "CLOSED" and leads[2]["close_reason"] == "expired"


def test_open_stages_expire_and_closed_leads_keep_state(isolated_client, isolated_db, fixed_clock):
    conn = sqlite3.connect(isolated_db)
    conn.execute("UPDATE lead SET deadline = '2026-01-01'")
    conn.commit()
    closed_before = conn.execute("SELECT * FROM lead WHERE user_id = 1 AND status = 'CLOSED' ORDER BY id").fetchall()
    fixed_clock("2026-09-15T07:00:00")
    leads = isolated_client.get("/api/v1/lead/search").get_json()
    assert all(l["close_reason"] == "expired" for l in leads if l["id"] <= 5)
    assert conn.execute("SELECT * FROM lead WHERE user_id = 1 AND status = 'CLOSED' AND id >= 6 ORDER BY id").fetchall() == closed_before


def _pin_after_anchor(isolated_db, fixed_clock, days: int) -> date:
    anchor = sqlite3.connect(isolated_db).execute("SELECT substr(created_at, 1, 10) FROM lead WHERE id = 1").fetchone()[0]
    day = date.fromisoformat(anchor) + timedelta(days=days)
    fixed_clock(f"{day}T07:00:00")
    return day


def _events(isolated_db, lead_id: int) -> list[str]:
    rows = sqlite3.connect(isolated_db).execute("SELECT event_type FROM lead_event WHERE lead_id = ? ORDER BY id", (lead_id,))
    return [row[0] for row in rows]


def test_callback_transition_moves_deadline_and_logs_it(isolated_client, isolated_db, fixed_clock):
    day = _pin_after_anchor(isolated_db, fixed_clock, 5)
    response = isolated_client.put("/api/v1/lead/2", json={"stage": "CALLBACK"})
    assert response.status_code == 200
    assert response.get_json()["deadline"] == (day + timedelta(days=28)).isoformat()
    assert _events(isolated_db, 2)[-2:] == ["stage_change", "deadline_changed"]


def test_activity_at_callback_or_later_keeps_the_window_rolling(isolated_client, isolated_db, fixed_clock):
    day = _pin_after_anchor(isolated_db, fixed_clock, 5)
    isolated_client.post("/api/v1/lead_note", json={"lead_id": 3, "note": "chased"})
    assert isolated_client.get("/api/v1/lead/3").get_json()["deadline"] == (day + timedelta(days=28)).isoformat()
    assert _events(isolated_db, 3)[-2:] == ["note_edited", "deadline_changed"]
    later = _pin_after_anchor(isolated_db, fixed_clock, 12)
    isolated_client.put("/api/v1/lead/3", json={"last_contact_date": later.isoformat()})
    assert isolated_client.get("/api/v1/lead/3").get_json()["deadline"] == (later + timedelta(days=28)).isoformat()
    assert _events(isolated_db, 3)[-2:] == ["contact_logged", "deadline_changed"]


def test_activity_before_callback_leaves_the_deadline(isolated_client, isolated_db, fixed_clock):
    _pin_after_anchor(isolated_db, fixed_clock, 5)
    before = isolated_client.get("/api/v1/lead/1").get_json()["deadline"]
    isolated_client.put("/api/v1/lead/1", json={"company_name": "Seed Co"})
    assert isolated_client.get("/api/v1/lead/1").get_json()["deadline"] == before
    assert "deadline_changed" not in _events(isolated_db, 1)[-2:]


def test_a_deadline_set_in_the_request_takes_precedence(isolated_client, isolated_db, fixed_clock):
    _pin_after_anchor(isolated_db, fixed_clock, 5)
    response = isolated_client.put("/api/v1/lead/3", json={"stage": "INTERVIEW", "deadline": "2031-01-01"})
    assert response.get_json()["deadline"] == "2031-01-01"
    assert _events(isolated_db, 3)[-1] == "stage_change"


TRANSITIONS = {
    "TOAPPLY": {"APPLIED", "CLOSED"}, "APPLIED": {"CALLBACK", "CLOSED"}, "CALLBACK": {"INTERVIEW", "CLOSED"},
    "INTERVIEW": {"OFFER", "CLOSED"}, "OFFER": {"CLOSED"}, "CLOSED": {"INTERVIEW"},
}


def test_every_lead_history_is_a_connected_stage_chain(conn):
    for lead_id, stage, post_id in conn.execute("SELECT id, stage, post_id FROM lead ORDER BY id").fetchall():
        rows = conn.execute("SELECT stage_from, stage_to FROM lead_event WHERE lead_id = ? ORDER BY id", (lead_id,)).fetchall()
        first = (None, "APPLIED") if post_id.startswith("manual-") else (None, "TOAPPLY")
        assert rows[0] == first, lead_id
        assert all(rows[i][0] == rows[i - 1][1] for i in range(1, len(rows))), lead_id
        assert rows[-1][1] == stage, lead_id


def test_seeded_stage_changes_follow_the_transition_table(conn):
    rows = conn.execute(
        "SELECT stage_from, stage_to FROM lead_event WHERE event_type = 'stage_change' AND stage_from IS NOT NULL").fetchall()
    assert rows and all(to in TRANSITIONS[frm] for frm, to in rows)


def test_other_events_hold_the_stage(conn):
    rows = conn.execute("SELECT stage_from, stage_to FROM lead_event WHERE event_type <> 'stage_change'").fetchall()
    assert rows and all(frm is not None and frm == to for frm, to in rows)


def test_no_seeded_row_holds_the_dropped_prospect_stage(conn):
    for column in ("lead.stage", "lead_event.stage_from", "lead_event.stage_to"):
        table = column.split(".")[0]
        assert conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {column.split('.')[1]} = 'PROSPECT'").fetchone()[0] == 0


def test_manual_lead_and_salary_defaults(conn):
    assert conn.execute("SELECT stage FROM lead WHERE post_id LIKE 'manual-%'").fetchall() == [("APPLIED",)]
    assert conn.execute(
        "SELECT COUNT(*) FROM lead l JOIN search_profile p ON p.track_id = l.track_id "
        "WHERE l.expected_salary_sgd IS NOT p.min_salary").fetchone()[0] == 0


def test_offer_history_and_the_one_open_offer_invariant(conn):
    assert conn.execute("SELECT lead_id, status FROM offer ORDER BY id").fetchall() == [(5, "rejected"), (5, "open"), (6, "accepted")]
    assert conn.execute("SELECT COUNT(*) FROM lead l WHERE l.stage = 'OFFER' AND "
                        "(SELECT COUNT(*) FROM offer o WHERE o.lead_id = l.id AND o.status = 'open') != 1").fetchone()[0] == 0
