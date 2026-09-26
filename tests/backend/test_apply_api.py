"""11.TC.01..07, 11.TC.11..13 — the apply feature's API contract through the Flask test client (ARCH-TEST-03):
the CV catalog's descriptive FK-guard 409, the TOAPPLY queue read, the per-lead CV override, drop, the run trigger's
preflight/collision/poll, the application read, and ownership. Expected ids come from the 11.10 seed: user 1's
queue is leads 1 (override cv 2) and 20, user 2's is lead 15 (blocked on cv_not_found), cv 1 is a track default,
and cv 2 is referenced only by lead 1's override and application 6.
"""

from __future__ import annotations

import json
import os
import time

import pytest

from tests.conftest import signed_in

pytestmark = pytest.mark.backend


@pytest.fixture()
def apply_app(isolated_db, tmp_path, monkeypatch):
    """An app on its own seeded db and its own SECRETS_DIR, fixture mode, fast deterministic polling."""
    monkeypatch.setenv("SECRETS_DIR", str(tmp_path / "secrets"))
    monkeypatch.setenv("APPLY_POLL_RETRIES", "2")
    monkeypatch.setenv("APPLY_POLL_DELAY_S", "0.01")
    from easymcf import create_app
    from easymcf.config import Config

    return create_app(Config(db_path=isolated_db))


def _stage_valid_session(app, uid: int = 1) -> None:
    """A secret-free fixture storage state in the isolated SECRETS_DIR, and the row pointing at it (11.IS.01)."""
    config = app.config["EASYMCF_CONFIG"]
    os.makedirs(config.secrets_dir, exist_ok=True)
    with open(os.path.join(config.secrets_dir, f"mcf_session_{uid}.json"), "w", encoding="utf-8") as handle:
        json.dump({"cookies": [], "origins": []}, handle)
    from easymcf.db.connection import get_connection

    db = get_connection(config.db_path)
    with db:
        db.execute("UPDATE mcf_session SET status = 'valid', cookie_ref = ? WHERE user_id = ?",
                   (f"mcf_session_{uid}.json", uid))
    db.close()


def _poll(client, run_id: int, timeout_s: float = 45) -> dict:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        run = client.get(f"/api/v1/run_log/{run_id}").get_json()
        if run["status"] != "running":
            return run
        time.sleep(0.2)
    raise AssertionError(f"run {run_id} still running after {timeout_s}s")


def test_cv_create_edit_and_remove_rules(isolated_client):
    """11.TC.01 / 11.IS.19 — create 201 and edit 200; a label in live use answers a 409 naming the uses; a label only
    history still uses is retired, leaving pickers but keeping its attempt rows; re-adding it reactivates the row."""
    created = isolated_client.post("/api/v1/cv", json={"label": "Data CV 2026"})
    assert created.status_code == 201 and created.get_json()["is_active"] is True
    cv_id = created.get_json()["id"]
    edited = isolated_client.put(f"/api/v1/cv/{cv_id}", json={"label": "Data CV 2026b"})
    assert (edited.status_code, edited.get_json()["label"]) == (200, "Data CV 2026b")
    assert isolated_client.delete(f"/api/v1/cv/{cv_id}").status_code == 204  # unreferenced: deleted
    assert isolated_client.get(f"/api/v1/cv/{cv_id}").status_code == 404

    in_use = isolated_client.delete("/api/v1/cv/1")
    assert in_use.status_code == 409
    assert in_use.get_json() == {
        "error": "conflict",
        "message": "CV '13.2' is still in use as the default of active tracks Data Analyst (mid), Data Engineer (mid), "
                   "Data Scientist (mid), Software Developer (mid), Gen AI Developer (mid) "
                   "and 1 queued lead; choose another CV there first",
        "in_use": {"track_ids": [1, 3, 4, 5, 6], "lead_ids": [20]}}

    by_override = isolated_client.delete("/api/v1/cv/2")  # lead 1's override
    assert by_override.status_code == 409 and by_override.get_json()["in_use"] == {"track_ids": [], "lead_ids": [1]}

    assert isolated_client.put("/api/v1/lead/1", json={"cv_id": None}).status_code == 200  # back to the track default
    retired = isolated_client.delete("/api/v1/cv/2")  # now only application 6 uses it
    assert retired.status_code == 200 and retired.get_json()["is_active"] is False
    assert isolated_client.get("/api/v1/application/6").get_json()["cv_id"] == 2
    readded = isolated_client.post("/api/v1/cv", json={"label": "11.4"})
    assert (readded.status_code, readded.get_json()["id"], readded.get_json()["is_active"]) == (201, 2, True)


def test_queue_lists_the_signed_in_users_toapply_leads(isolated_client, isolated_client_b):
    """11.TC.02 — the TOAPPLY read with each lead's effective CV, latest attempt, and block flag."""
    mine = isolated_client.get("/api/v1/lead/search?stage=TOAPPLY").get_json()
    assert [(r["id"], r["effective_cv_id"], r["last_apply_status"], r["apply_blocked"]) for r in mine] == [
        (1, 2, "cv_selector_error", False), (20, 1, None, False)]
    theirs = isolated_client_b.get("/api/v1/lead/search?stage=TOAPPLY").get_json()
    assert [(r["id"], r["effective_cv_id"], r["last_apply_status"], r["apply_blocked"]) for r in theirs] == [
        (15, 3, "cv_not_found", True)]


def test_cv_override_repairs_a_blocked_lead_and_rejects_a_foreign_cv(isolated_client_b):
    """Scope item 12.2 / Data model item 03 — overriding a cv_not_found lead's CV clears its block."""
    created = isolated_client_b.post("/api/v1/cv", json={"label": "S-2"}).get_json()
    repaired = isolated_client_b.put("/api/v1/lead/15", json={"cv_id": created["id"]})
    assert repaired.status_code == 200
    assert (repaired.get_json()["effective_cv_id"], repaired.get_json()["apply_blocked"]) == (created["id"], False)
    foreign = isolated_client_b.put("/api/v1/lead/15", json={"cv_id": 1})  # user 1's cv
    assert (foreign.status_code, foreign.get_json()["field"]) == (400, "cv_id")
    cleared = isolated_client_b.put("/api/v1/lead/15", json={"cv_id": None}).get_json()
    assert (cleared["effective_cv_id"], cleared["apply_blocked"]) == (3, True)  # back on the track default


def test_drop_closes_the_lead_and_the_queue_excludes_it(isolated_client):
    """11.TC.03 / 11.TC.11 — drop by PUT, then the next queue read excludes it."""
    dropped = isolated_client.put("/api/v1/lead/20", json={"stage": "CLOSED", "close_reason": "dropped"})
    assert dropped.status_code == 200
    assert (dropped.get_json()["stage"], dropped.get_json()["close_reason"]) == ("CLOSED", "dropped")
    assert [r["id"] for r in isolated_client.get("/api/v1/lead/search?stage=TOAPPLY").get_json()] == [1]


def test_trigger_with_an_invalid_session_aborts_with_zero_attempts(apply_app):
    """11.TC.06 — the seeded session is `missing`: 409 naming the session, no run_log or application row."""
    client = signed_in(apply_app, "seed_a")
    before = (len(client.get("/api/v1/run_log/search").get_json()),
              len(client.get("/api/v1/application/search").get_json()))
    response = client.post("/api/v1/runs/apply")
    assert response.status_code == 409
    assert response.get_json() == {
        "error": "conflict",
        "message": "mcf_session is not valid: sign in through the MCF nav page before running apply"}
    assert (len(client.get("/api/v1/run_log/search").get_json()),
            len(client.get("/api/v1/application/search").get_json())) == before


def test_trigger_polls_to_success_and_writes_one_application_per_lead(apply_app):
    """11.TC.04 / 11.TC.07 / 11.TC.11 — a valid session runs user 1's queue: lead 1 applied, lead 20
    questionnaire_required (the corpus routes), and the queue afterwards holds lead 20 alone."""
    _stage_valid_session(apply_app)
    client = signed_in(apply_app, "seed_a")
    response = client.post("/api/v1/runs/apply")
    assert response.status_code == 201
    started = response.get_json()
    assert (started["run_type"], started["track_id"], started["trigger_source"]) == ("apply", None, "manual")
    run = _poll(client, started["id"])
    assert run["status"] == "success" and run["error_detail"] is None
    assert json.loads(run["outcome_counts"]) == {"applied": 1, "questionnaire_required": 1}
    rows = client.get(f"/api/v1/application/search?run_id={started['id']}").get_json()
    assert sorted((r["lead_id"], r["status"]) for r in rows) == [(1, "applied"), (20, "questionnaire_required")]
    assert client.get("/api/v1/lead/1").get_json()["stage"] == "APPLIED"
    assert [r["id"] for r in client.get("/api/v1/lead/search?stage=TOAPPLY").get_json()] == [20]
    apply_runs = client.get("/api/v1/run_log/search?run_type=apply").get_json()
    assert started["id"] in [r["id"] for r in apply_runs]


def test_second_trigger_while_in_flight_is_409_with_the_run_id(apply_app, monkeypatch):
    """11.TC.05 — the slow scenario keeps the first run in flight while the second trigger arrives."""
    monkeypatch.setenv("MCF_FIXTURE_SCENARIO", "slow")
    from easymcf import create_app
    from easymcf.config import Config

    app = create_app(Config(db_path=apply_app.config["EASYMCF_CONFIG"].db_path))
    _stage_valid_session(app)
    client = signed_in(app, "seed_a")
    first = client.post("/api/v1/runs/apply").get_json()
    second = client.post("/api/v1/runs/apply")
    assert second.status_code == 409
    assert second.get_json() == {"error": "conflict", "message": "an apply run is already in progress",
                                 "run_id": first["id"]}
    assert _poll(client, first["id"])["status"] == "success"


def test_user_b_reads_only_its_own_apply_rows(isolated_client, isolated_client_b):
    """11.TC.12 / 11.TC.13 — cv, application, mcf_session, and run_log reads are each owner-scoped."""
    b_apps = isolated_client_b.get("/api/v1/application/search").get_json()
    assert sorted(r["id"] for r in b_apps) == [10, 11]
    assert isolated_client_b.get("/api/v1/application/1").status_code == 404
    assert [r["user_id"] for r in isolated_client_b.get("/api/v1/mcf_session/search").get_json()] == [2]
    assert {r["user_id"] for r in isolated_client_b.get("/api/v1/run_log/search?run_type=apply").get_json()} == {2}
    assert isolated_client_b.delete("/api/v1/cv/2").status_code == 404  # user 1's cv: not visible, not a 409
    assert isolated_client_b.put("/api/v1/cv/1", json={"label": "taken"}).status_code == 404
    assert isolated_client.get("/api/v1/cv/1").get_json()["label"] == "13.2"
