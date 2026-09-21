"""09.13.CK.12 — a lead re-assigns to another active track, and the change is logged."""

from __future__ import annotations

import sqlite3

import pytest

pytestmark = pytest.mark.backend


def _events(db_path: str, lead_id: int) -> list[tuple]:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(
            "SELECT event_type, detail, stage_from, stage_to FROM lead_event WHERE lead_id = ? ORDER BY id DESC LIMIT 1", (lead_id,)).fetchall()
    finally:
        conn.close()


def test_a_lead_reassigns_to_another_active_track_and_logs_a_field_edit(isolated_client, isolated_db):
    response = isolated_client.put("/api/v1/lead/1", json={"track_id": 3})
    assert response.status_code == 200 and response.get_json()["track_id"] == 3
    assert _events(isolated_db, 1) == [("field_edited", "track_id: 1 -> 3", "TOAPPLY", "TOAPPLY")]


def test_reassigning_leaves_the_expected_salary_and_the_stage_alone(isolated_client):
    before = isolated_client.get("/api/v1/lead/2").get_json()
    after = isolated_client.put("/api/v1/lead/2", json={"track_id": 4}).get_json()
    assert (after["stage"], after["expected_salary_sgd"], after["deadline"]) == (
        before["stage"], before["expected_salary_sgd"], before["deadline"])


@pytest.mark.parametrize("track_id,message", [(999, "not found"), (2, "archived")])
def test_an_unknown_or_archived_track_answers_400_on_track_id(isolated_client, track_id, message):
    response = isolated_client.put("/api/v1/lead/3", json={"track_id": track_id})
    assert response.status_code == 400 and response.get_json()["field"] == "track_id"
    assert message in response.get_json()["message"]
    assert isolated_client.get("/api/v1/lead/3").get_json()["track_id"] == 1


def test_a_batch_row_carries_no_track(isolated_client):
    response = isolated_client.post("/api/v1/lead/batch", json={"rows": [{"id": 1, "stage": "APPLIED", "track_id": 3}]})
    assert response.status_code == 400 and response.get_json()["field"] == "rows"
