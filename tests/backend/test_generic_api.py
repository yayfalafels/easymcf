"""REQ-PLAT-01 — the seven generic shapes and the error shapes, exercised through a
test-only resource that opens every verb on `cv` (no production resource opens
`batch` or bulk delete in this milestone)."""

from __future__ import annotations

import sqlite3
import uuid

import pytest

from easymcf.api import generic

pytestmark = pytest.mark.backend

_CV_CREATE = {"type": "object", "properties": {"user_id": {"type": "integer"}, "label": {"type": "string", "minLength": 1}},
              "required": ["user_id", "label"], "additionalProperties": False}


@pytest.fixture()
def cv_client(isolated_client):
    original = generic.REGISTRY["cv"]
    generic.REGISTRY["cv"] = generic.Resource("cv", create_schema=_CV_CREATE, update_schema={**_CV_CREATE, "required": []},
                                              verbs=generic.GENERIC)
    yield isolated_client
    generic.REGISTRY["cv"] = original


def _count(db_path: str) -> int:
    return sqlite3.connect(db_path).execute("SELECT COUNT(*) FROM cv").fetchone()[0]


def test_create_get_update_delete_round_trip(cv_client):
    created = cv_client.post("/api/v1/cv", json={"user_id": 1, "label": "9.9"})
    assert created.status_code == 201
    row_id = created.get_json()["id"]
    assert cv_client.get(f"/api/v1/cv/{row_id}").get_json()["label"] == "9.9"
    assert cv_client.put(f"/api/v1/cv/{row_id}", json={"label": "9.8"}).get_json()["label"] == "9.8"
    assert cv_client.delete(f"/api/v1/cv/{row_id}").status_code == 204
    assert cv_client.get(f"/api/v1/cv/{row_id}").status_code == 404


def test_batch_creates_all_rows_or_none(cv_client, isolated_db):
    before = _count(isolated_db)
    ok = cv_client.post("/api/v1/cv/batch", json={"rows": [{"user_id": 1, "label": "b1"}, {"user_id": 1, "label": "b2"}]})
    assert ok.status_code == 201 and len(ok.get_json()) == 2 and _count(isolated_db) == before + 2
    duplicate = cv_client.post("/api/v1/cv/batch", json={"rows": [{"user_id": 1, "label": "b3"}, {"user_id": 1, "label": "b1"}]})
    assert duplicate.status_code == 409 and _count(isolated_db) == before + 2


def test_bulk_delete_by_filter(cv_client, isolated_db):
    cv_client.post("/api/v1/cv/batch", json={"rows": [{"user_id": 1, "label": "d1"}, {"user_id": 1, "label": "d2"}]})
    assert cv_client.post("/api/v1/cv/delete", json={"filter": {"label": "d1"}}).get_json() == {"deleted": 1}
    assert cv_client.post("/api/v1/cv/delete", json={"filter": {}}).status_code == 400
    assert cv_client.post("/api/v1/cv/delete", json={"filter": {"nope": 1}}).status_code == 400


def test_delete_of_a_referenced_row_is_a_conflict(cv_client):
    response = cv_client.delete("/api/v1/cv/1")
    assert response.status_code == 409 and response.get_json()["error"] == "conflict"


@pytest.mark.parametrize("method,path,body,status", [
    ("get", "/api/v1/cv/999", None, 404),
    ("put", "/api/v1/cv/999", {"label": "x"}, 404),
    ("delete", "/api/v1/cv/999", None, 404),
    ("get", "/api/v1/nope/1", None, 404),
    ("get", "/api/v1/cv/search?bogus=1", None, 400),
    ("post", "/api/v1/cv", {"user_id": 1}, 400),
    ("post", "/api/v1/cv", {"user_id": "a", "label": "x"}, 400),
])
def test_error_shapes(cv_client, method, path, body, status):
    response = getattr(cv_client, method)(path, **({"json": body} if body is not None else {}))
    assert response.status_code == status
    assert response.get_json()["error"] in {"not_found", "validation_error"}


def test_missing_field_is_named(cv_client):
    body = cv_client.post("/api/v1/cv", json={"user_id": 1}).get_json()
    assert body == {"error": "validation_error", "field": "label", "message": "label is required"}


def test_manual_lead_endpoint_creates_post_and_promotes(isolated_client, isolated_db):
    response = isolated_client.post("/api/v1/lead/manual", json={
        "track_id": 1, "position_title": "Manual backend role", "company_name": "Example Co",
        "salary_high": 10500, "posted_date": "2026-09-19",
    })
    assert response.status_code == 201
    lead = response.get_json()
    assert lead["stage"] == "PROSPECT" and lead["status"] == "OPEN"
    post = sqlite3.connect(isolated_db).execute(
        "SELECT src_method, url_ref FROM post WHERE id = ?", (lead["post_id"],)
    ).fetchone()
    assert post[0] == "manual" and str(uuid.UUID(post[1])) == post[1]
