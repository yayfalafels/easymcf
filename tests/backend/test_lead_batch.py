"""09.13.CK.03 — POST /api/v1/lead/batch: atomic stage moves for many leads."""

from __future__ import annotations

import sqlite3

import pytest

pytestmark = pytest.mark.backend

BATCH = "/api/v1/lead/batch"


def _stages(db_path: str) -> dict[int, str]:
    conn = sqlite3.connect(db_path)
    try:
        return dict(conn.execute("SELECT id, stage FROM lead"))
    finally:
        conn.close()


def _events(db_path: str, lead_id: int) -> list[tuple]:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("SELECT stage_from, stage_to FROM lead_event WHERE lead_id = ? ORDER BY id", (lead_id,)).fetchall()
    finally:
        conn.close()


def _promote_two(isolated_client) -> list[int]:
    ids = [1]
    ids.append(isolated_client.post("/api/v1/lead", json={"post_id": "synthetic-promote-nodate", "track_id": 1}).get_json()["id"])
    return ids


def test_batch_apply_moves_every_row_in_request_order(isolated_client, isolated_db):
    ids = _promote_two(isolated_client)
    response = isolated_client.post(BATCH, json={"rows": [{"id": i, "stage": "APPLIED"} for i in reversed(ids)]})
    assert response.status_code == 200
    assert [lead["id"] for lead in response.get_json()] == list(reversed(ids))
    assert all(lead["stage"] == "APPLIED" for lead in response.get_json())
    assert all(_events(isolated_db, i)[-1] == ("TOAPPLY", "APPLIED") for i in ids)


def test_batch_drop_closes_every_row_as_dropped(isolated_client):
    ids = _promote_two(isolated_client)
    response = isolated_client.post(BATCH, json={"rows": [{"id": i, "stage": "CLOSED", "close_reason": "dropped"} for i in ids]})
    assert response.status_code == 200
    assert all((l["status"], l["close_reason"]) == ("CLOSED", "dropped") for l in response.get_json())


def test_one_illegal_row_rejects_the_whole_batch(isolated_client, isolated_db):
    before, events = _stages(isolated_db), _events(isolated_db, 1)
    response = isolated_client.post(BATCH, json={"rows": [{"id": 1, "stage": "APPLIED"}, {"id": 6, "stage": "APPLIED"}]})
    assert response.status_code == 409 and response.get_json()["lead_id"] == 6
    assert _stages(isolated_db) == before
    assert _events(isolated_db, 1) == events


@pytest.mark.parametrize("rows", [
    [], [{"id": 1, "stage": "APPLIED"}, {"id": 1, "stage": "APPLIED"}],
    [{"id": i, "stage": "APPLIED"} for i in range(1, 202)],
    [{"id": 1, "stage": "APPLIED", "position_title": "x"}], [{"stage": "APPLIED"}],
    [{"id": 1, "stage": "PROSPECT"}], "not a list",
])
def test_batch_bodies_outside_the_shape_answer_400_on_rows(isolated_client, isolated_db, rows):
    before = _stages(isolated_db)
    response = isolated_client.post(BATCH, json={"rows": rows})
    assert response.status_code == 400 and response.get_json()["field"] == "rows"
    assert _stages(isolated_db) == before


def test_batch_applies_the_offer_gates(isolated_client):
    response = isolated_client.post(BATCH, json={"rows": [{"id": 4, "stage": "OFFER"}]})
    assert response.status_code == 409 and response.get_json()["lead_id"] == 4
    close = isolated_client.post(BATCH, json={"rows": [{"id": 5, "stage": "CLOSED", "close_reason": "withdrawn"}]})
    assert close.status_code == 409 and close.get_json()["lead_id"] == 5
