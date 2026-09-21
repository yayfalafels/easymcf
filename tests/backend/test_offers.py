"""09.13.CK.08 — offers gate the OFFER stage, their status closes the lead, and a closed lead can re-open."""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta

import pytest

pytestmark = pytest.mark.backend

OFFER = "/api/v1/offer"


def _row(db_path: str, sql: str, *params):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def _offer_for_lead_4(client, **extra):
    return client.post(OFFER, json={"lead_id": 4, "offer_date": "2026-09-19", "amount_sgd": 12500, **extra})


def test_offer_create_moves_the_interview_lead_to_offer_atomically(isolated_client, isolated_db):
    response = _offer_for_lead_4(isolated_client, deadline="2026-10-31")
    assert response.status_code == 201
    offer = response.get_json()
    assert (offer["status"], offer["amount_sgd"], offer["lead_title"] is not None) == ("open", 12500, True)
    lead = isolated_client.get("/api/v1/lead/4").get_json()
    assert (lead["stage"], lead["deadline"], lead["offer_id"], lead["offer_amount_sgd"]) == ("OFFER", "2026-10-31", offer["id"], 12500)
    assert _row(isolated_db, "SELECT event_type, stage_from, stage_to FROM lead_event WHERE lead_id = 4 ORDER BY id DESC LIMIT 1") == [
        ("stage_change", "INTERVIEW", "OFFER")]


def test_offer_deadline_defaults_to_the_lead_deadline(isolated_client, isolated_db):
    deadline = _row(isolated_db, "SELECT deadline FROM lead WHERE id = 4")[0][0]
    assert _offer_for_lead_4(isolated_client).get_json()["deadline"] == deadline


@pytest.mark.parametrize("lead_id", [1, 2, 3, 5, 6])
def test_offer_create_answers_409_unless_the_lead_is_open_at_interview(isolated_client, lead_id):
    response = isolated_client.post(OFFER, json={"lead_id": lead_id, "offer_date": "2026-09-19", "amount_sgd": 1})
    assert response.status_code == 409 and response.get_json()["lead_id"] == lead_id


@pytest.mark.parametrize("body,field", [
    ({"offer_date": "2026-09-19", "amount_sgd": 1}, "lead_id"),
    ({"lead_id": 4, "amount_sgd": 1}, "offer_date"),
    ({"lead_id": 4, "offer_date": "2026-09-19"}, "amount_sgd"),
    ({"lead_id": 4, "offer_date": "2026-09-19", "amount_sgd": 0}, "amount_sgd"),
])
def test_offer_create_validates_its_body(isolated_client, body, field):
    response = isolated_client.post(OFFER, json=body)
    assert response.status_code == 400 and response.get_json()["field"] == field


@pytest.mark.parametrize("status,reason", [("accepted", "offer_accepted"), ("rejected", "rejected"),
                                           ("withdrawn", "withdrawn"), ("expired", "expired")])
def test_each_final_status_closes_the_lead_with_its_mapped_reason(isolated_client, isolated_db, status, reason):
    offer_id = _offer_for_lead_4(isolated_client).get_json()["id"]
    response = isolated_client.put(f"{OFFER}/{offer_id}", json={"status": status})
    assert response.status_code == 200 and response.get_json()["status"] == status
    lead = isolated_client.get("/api/v1/lead/4").get_json()
    assert (lead["status"], lead["stage"], lead["close_reason"]) == ("CLOSED", "CLOSED", reason)
    assert _row(isolated_db, "SELECT stage_from, stage_to FROM lead_event WHERE lead_id = 4 ORDER BY id DESC LIMIT 1") == [("OFFER", "CLOSED")]


def test_an_open_offer_edits_amount_and_deadline_and_a_final_offer_is_read_only(isolated_client, isolated_db):
    offer_id = _offer_for_lead_4(isolated_client).get_json()["id"]
    edited = isolated_client.put(f"{OFFER}/{offer_id}", json={"amount_sgd": 13000, "deadline": "2026-11-15"}).get_json()
    assert (edited["amount_sgd"], edited["deadline"]) == (13000, "2026-11-15")
    assert isolated_client.get("/api/v1/lead/4").get_json()["deadline"] == "2026-11-15"
    isolated_client.put(f"{OFFER}/{offer_id}", json={"status": "withdrawn"})
    assert isolated_client.put(f"{OFFER}/{offer_id}", json={"amount_sgd": 1}).status_code == 409
    assert isolated_client.put(f"{OFFER}/{offer_id}", json={"status": "accepted"}).status_code == 409


def test_an_unknown_status_answers_400(isolated_client):
    offer_id = _offer_for_lead_4(isolated_client).get_json()["id"]
    response = isolated_client.put(f"{OFFER}/{offer_id}", json={"status": "open"})
    assert response.status_code == 400 and response.get_json()["field"] == "status"


def test_offers_are_never_deleted(isolated_client):
    offer_id = _offer_for_lead_4(isolated_client).get_json()["id"]
    assert isolated_client.delete(f"{OFFER}/{offer_id}").status_code == 404


def test_a_lead_at_offer_closes_only_through_its_offer(isolated_client):
    _offer_for_lead_4(isolated_client)
    response = isolated_client.put("/api/v1/lead/4", json={"stage": "CLOSED", "close_reason": "withdrawn"})
    assert response.status_code == 409 and "offer" in response.get_json()["message"]


def test_reopen_returns_to_interview_and_a_new_offer_moves_the_lead_back_to_offer(isolated_client, isolated_db):
    first = _offer_for_lead_4(isolated_client).get_json()["id"]
    isolated_client.put(f"{OFFER}/{first}", json={"status": "rejected"})
    assert isolated_client.get("/api/v1/lead/4").get_json()["closed_from"] == "OFFER"
    reopened = isolated_client.put("/api/v1/lead/4", json={"stage": "INTERVIEW"})
    assert reopened.status_code == 200
    lead = reopened.get_json()
    assert (lead["status"], lead["stage"], lead["close_reason"], lead["closed_from"]) == ("OPEN", "INTERVIEW", None, "OFFER")
    second = _offer_for_lead_4(isolated_client)
    assert second.status_code == 201
    assert isolated_client.get("/api/v1/lead/4").get_json()["stage"] == "OFFER"
    assert _row(isolated_db, "SELECT status FROM offer WHERE lead_id = 4 ORDER BY id") == [("rejected",), ("open",)]


def test_search_filters_offers_and_joins_the_lead(isolated_client):
    rows = isolated_client.get("/api/v1/offer/search?lead_id=5").get_json()
    assert [(r["status"], r["lead_title"] is not None, r["track_id"]) for r in rows] == [("rejected", True, 1), ("open", True, 1)]
    assert [r["status"] for r in isolated_client.get("/api/v1/offer/search?status=accepted").get_json()] == ["accepted"]


def test_lead_responses_carry_the_derived_fields(isolated_client):
    isolated_client.post("/api/v1/lead_note", json={"lead_id": 3, "note": "first"})
    isolated_client.post("/api/v1/lead_note", json={"lead_id": 3, "note": "second"})
    assert isolated_client.get("/api/v1/lead/3").get_json()["latest_note"] == "second"
    assert isolated_client.get("/api/v1/lead/1").get_json()["latest_note"] is None
    lead = isolated_client.get("/api/v1/lead/5").get_json()
    assert (lead["offer_status"], lead["offer_amount_sgd"], lead["offer_date"], lead["closed_from"]) == ("open", 12000, lead["offer_date"], "OFFER")
    assert lead["offer_date"] and lead["offer_deadline"]


def test_the_deadline_at_offer_follows_the_offer_and_ignores_activity(isolated_client, isolated_db, fixed_clock):
    _offer_for_lead_4(isolated_client, deadline="2026-12-01")
    fixed_clock("2026-09-25T07:00:00")
    isolated_client.post("/api/v1/lead_note", json={"lead_id": 4, "note": "waiting"})
    isolated_client.put("/api/v1/lead/4", json={"last_contact_date": "2026-09-25"})
    assert isolated_client.get("/api/v1/lead/4").get_json()["deadline"] == "2026-12-01"


def test_expiry_at_offer_closes_the_lead_and_expires_its_offer(isolated_client, isolated_db, fixed_clock):
    offer_id = _offer_for_lead_4(isolated_client, deadline="2026-09-20").get_json()["id"]
    fixed_clock("2026-09-22T07:00:00")
    lead = next(l for l in isolated_client.get("/api/v1/lead/search").get_json() if l["id"] == 4)
    assert (lead["status"], lead["close_reason"]) == ("CLOSED", "expired")
    assert _row(isolated_db, "SELECT status FROM offer WHERE id = ?", offer_id) == [("expired",)]


@pytest.mark.parametrize("sql", [
    "INSERT INTO offer (lead_id, offer_date, amount_sgd, status, created_at, updated_at) VALUES (5, '2026-09-19', 1, 'open', 'x', 'x')",
    "INSERT INTO offer (lead_id, offer_date, amount_sgd, status, created_at, updated_at) VALUES (1, '2026-09-19', 0, 'open', 'x', 'x')",
    "INSERT INTO offer (lead_id, offer_date, amount_sgd, status, created_at, updated_at) VALUES (1, '2026-09-19', 1, 'nope', 'x', 'x')",
    "UPDATE lead SET expected_salary_sgd = -1 WHERE id = 1",
    "UPDATE lead SET stage = 'PROSPECT' WHERE id = 1",
])
def test_schema_constraints(isolated_db, sql):
    conn = sqlite3.connect(isolated_db)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(sql)
    conn.close()


def test_dropped_is_an_accepted_close_reason(isolated_client):
    response = isolated_client.put("/api/v1/lead/1", json={"stage": "CLOSED", "close_reason": "dropped"})
    assert response.status_code == 200 and response.get_json()["close_reason"] == "dropped"


def test_expected_salary_is_copied_at_creation_and_editable(isolated_client, isolated_db):
    isolated_client.put("/api/v1/search_profile/1", json={"min_salary": 15000})
    created = isolated_client.post("/api/v1/lead", json={"post_id": "synthetic-promote-future", "track_id": 1}).get_json()
    assert created["expected_salary_sgd"] == 15000
    isolated_client.put("/api/v1/search_profile/1", json={"min_salary": 9000})
    assert isolated_client.get(f"/api/v1/lead/{created['id']}").get_json()["expected_salary_sgd"] == 15000
    edited = isolated_client.put(f"/api/v1/lead/{created['id']}", json={"expected_salary_sgd": 11000}).get_json()
    assert edited["expected_salary_sgd"] == 11000
    assert isolated_client.put(f"/api/v1/lead/{created['id']}", json={"expected_salary_sgd": -5}).status_code == 400
    assert isolated_client.put(f"/api/v1/lead/{created['id']}", json={"expected_salary_sgd": None}).status_code == 200


def test_a_profile_without_min_salary_gives_a_null_expected_salary(isolated_client):
    isolated_client.put("/api/v1/search_profile/1", json={"min_salary": None})
    created = isolated_client.post("/api/v1/lead", json={"post_id": "synthetic-promote-past", "track_id": 1}).get_json()
    assert created["expected_salary_sgd"] is None
