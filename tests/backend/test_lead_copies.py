"""13.TC.55 to 13.TC.57 - a lead owns editable copies of its post's display fields, and a post is read-only."""

from __future__ import annotations

import sqlite3

import pytest

pytestmark = pytest.mark.backend


def _q(db, sql, *args):
    conn = sqlite3.connect(db)
    try:
        return conn.execute(sql, args).fetchall()
    finally:
        conn.close()


def _run(db, sql, *args):
    conn = sqlite3.connect(db)
    conn.execute(sql, args)
    conn.commit()
    conn.close()


# 13.TC.56 - promotion copies four values once and later post changes never reach the lead
def test_promotion_copies_title_company_and_url_and_computes_the_deadline(isolated_client, isolated_db, fixed_clock):
    fixed_clock("2026-09-21T07:00:00")
    isolated_client.post("/api/v1/auth/signin", json={"email": "demo.user@example.test", "password": "Seed-Password-1!"})
    post = _q(isolated_db, "SELECT position_title, company_name, url_ref, closing_date FROM post WHERE id = 'synthetic-promote-future'")[0]
    created = isolated_client.post("/api/v1/lead", json={"post_id": "synthetic-promote-future", "track_id": 1})
    assert created.status_code == 201
    lead = _q(isolated_db, "SELECT position_title, company_name, url_ref, deadline, user_id FROM lead WHERE id = ?", created.get_json()["id"])[0]
    assert lead[:3] == post[:3] and lead[3] == post[3] and lead[4] == 1


def test_a_later_change_to_the_post_never_rewrites_the_lead(isolated_client, isolated_db):
    lead_id = isolated_client.post("/api/v1/lead", json={"post_id": "synthetic-promote-nodate", "track_id": 1}).get_json()["id"]
    before = _q(isolated_db, "SELECT position_title, company_name, url_ref, deadline FROM lead WHERE id = ?", lead_id)
    _run(isolated_db, "UPDATE post SET position_title = 'Renamed', company_name = 'Renamed Co', url_ref = 'https://renamed.example', closing_date = '2030-01-01' WHERE id = 'synthetic-promote-nodate'")
    assert isolated_client.get(f"/api/v1/lead/{lead_id}").get_json()["position_title"] == before[0][0]
    assert _q(isolated_db, "SELECT position_title, company_name, url_ref, deadline FROM lead WHERE id = ?", lead_id) == before


def test_two_users_hold_separate_copies_of_the_same_post(isolated_client, isolated_client_b, isolated_db):
    _run(isolated_db, "INSERT INTO post (id, source, position_title, company_name, url_ref, src_method) VALUES ('shared-copy', 's', 'Shared', 'Shared Co', 'https://shared.example', 'scraped')")
    for track_id in (1, 7):
        _run(isolated_db, "INSERT INTO post_track (post_id, track_id, search_match) VALUES ('shared-copy', ?, 1)", track_id)
    a = isolated_client.post("/api/v1/lead", json={"post_id": "shared-copy", "track_id": 1}).get_json()
    b = isolated_client_b.post("/api/v1/lead", json={"post_id": "shared-copy", "track_id": 7}).get_json()
    assert isolated_client.put(f"/api/v1/lead/{a['id']}", json={"position_title": "A's title"}).status_code == 200
    assert _q(isolated_db, "SELECT position_title FROM lead WHERE id = ?", b["id"]) == [("Shared",)]
    assert _q(isolated_db, "SELECT position_title FROM post WHERE id = 'shared-copy'") == [("Shared",)]


# 13.TC.57 - editing the lead's own fields
def test_editing_the_four_display_fields_updates_the_lead_and_logs_events(isolated_client, isolated_db):
    lead_id = 2
    post = _q(isolated_db, "SELECT position_title, company_name, url_ref FROM post WHERE id = (SELECT post_id FROM lead WHERE id = 2)")
    fields = isolated_client.put(f"/api/v1/lead/{lead_id}", json={"position_title": "New title", "company_name": "New Co", "url_ref": "https://new.example/job"})
    deadline = isolated_client.put(f"/api/v1/lead/{lead_id}", json={"deadline": "2026-12-31"})
    assert fields.status_code == deadline.status_code == 200
    body = deadline.get_json()
    assert (body["position_title"], body["company_name"], body["url_ref"], body["deadline"]) == ("New title", "New Co", "https://new.example/job", "2026-12-31")
    assert _q(isolated_db, "SELECT position_title, company_name, url_ref FROM post WHERE id = (SELECT post_id FROM lead WHERE id = 2)") == post
    events = _q(isolated_db, "SELECT event_type, detail FROM lead_event WHERE lead_id = ? AND event_type IN ('field_edited', 'deadline_changed') ORDER BY id", lead_id)
    assert [e[0] for e in events] == ["field_edited", "deadline_changed"] and "position_title" in events[0][1] and "deadline" in events[1][1]


def test_a_request_mixing_fields_and_the_deadline_logs_one_deadline_event(isolated_client, isolated_db):
    isolated_client.put("/api/v1/lead/2", json={"position_title": "Mixed", "deadline": "2026-12-30"})
    kinds = [r[0] for r in _q(isolated_db, "SELECT event_type FROM lead_event WHERE lead_id = 2 AND detail LIKE '%Mixed%'")]
    assert kinds == ["deadline_changed"]


@pytest.mark.parametrize("field, value", [("url_ref", "not a url"), ("url_ref", "ftp://x.example"), ("position_title", ""), ("company_name", "")])
def test_invalid_display_values_are_refused(isolated_client, field, value):
    response = isolated_client.put("/api/v1/lead/2", json={field: value})
    assert response.status_code == 400 and response.get_json()["field"] == field


def test_the_url_can_be_cleared(isolated_client, isolated_db):
    assert isolated_client.put("/api/v1/lead/2", json={"url_ref": None}).status_code == 200
    assert _q(isolated_db, "SELECT url_ref FROM lead WHERE id = 2") == [(None,)]


# 13.TC.55 - a post is read-only through the API
def test_post_write_verbs_are_not_exposed(isolated_client, isolated_db):
    before = _q(isolated_db, "SELECT * FROM post ORDER BY id")
    assert isolated_client.put("/api/v1/post/synthetic-promote-past", json={"url_ref": "https://x.example"}).status_code == 404
    assert isolated_client.post("/api/v1/post", json={"id": "x"}).status_code == 404
    assert isolated_client.post("/api/v1/post/batch", json={"rows": []}).status_code == 404
    assert isolated_client.delete("/api/v1/post/synthetic-promote-past").status_code == 404
    assert _q(isolated_db, "SELECT * FROM post ORDER BY id") == before
