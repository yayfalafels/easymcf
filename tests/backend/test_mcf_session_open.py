from __future__ import annotations

import os

import pytest

from easymcf.services import mcf_connection

pytestmark = pytest.mark.backend

MCF_URL = "https://www.mycareersfuture.gov.sg/job/example"


def test_interactive_browser_uses_public_playwright_error_type():
    from playwright.sync_api import Error

    assert issubclass(Error, Exception)


def test_external_url_is_rejected(client):
    response = client.post("/api/v1/mcf_session/open", json={"url": "https://example.com/job"})
    assert response.status_code == 400
    assert response.get_json()["field"] == "url"


def test_missing_session_uses_plain_redirect(client_b):
    response = client_b.post("/api/v1/mcf_session/open", json={"url": MCF_URL})
    assert response.status_code == 200
    assert response.get_json() == {"mode": "redirect", "url": MCF_URL}


def test_file_missing_valid_session_is_downgraded_before_redirect(client, app):
    with app.app_context():
        from easymcf.api.db import get_db

        db = get_db()
        with db:
            db.execute(
                "UPDATE mcf_session SET status = 'valid', cookie_ref = 'deleted-state.json' WHERE user_id = 1"
            )

    response = client.post("/api/v1/mcf_session/open", json={"url": MCF_URL})

    assert response.status_code == 200
    assert response.get_json() == {"mode": "redirect", "url": MCF_URL}
    with app.app_context():
        row = get_db().execute("SELECT status, cookie_ref FROM mcf_session WHERE user_id = 1").fetchone()
        assert tuple(row) == ("missing", None)


def test_valid_session_opens_saved_state_in_interactive_browser(client, app, monkeypatch):
    config = app.config["EASYMCF_CONFIG"]
    os.makedirs(config.secrets_dir, exist_ok=True)
    storage_path = os.path.join(config.secrets_dir, "mcf_session_1.json")
    with open(storage_path, "w", encoding="utf-8") as handle:
        handle.write("{}")
    with app.app_context():
        from easymcf.api.db import get_db

        db = get_db()
        with db:
            db.execute(
                "UPDATE mcf_session SET status = 'valid', cookie_ref = 'mcf_session_1.json' WHERE user_id = 1"
            )
    started = []
    monkeypatch.setattr(
        mcf_connection,
        "_start_interactive_browser",
        lambda received_config, uid, path, url: started.append((received_config, uid, path, url)),
    )

    response = client.post("/api/v1/mcf_session/open", json={"url": MCF_URL})

    assert response.status_code == 202
    assert response.get_json() == {"mode": "authenticated", "url": MCF_URL}
    assert started == [(config, 1, storage_path, MCF_URL)]


def test_startup_marks_missing_saved_state_as_missing(isolated_db, tmp_path):
    from easymcf.config import Config

    config = Config(db_path=isolated_db, secrets_dir=str(tmp_path / "secrets"), mcf_mode="live")
    mcf_connection.reconcile_local_sessions(config)

    import sqlite3

    db = sqlite3.connect(isolated_db)
    try:
        assert db.execute("SELECT status, cookie_ref FROM mcf_session WHERE user_id = 1").fetchone() == (
            "missing",
            None,
        )
    finally:
        db.close()


def test_session_status_poll_downgrades_file_missing_after_startup(client, app):
    with app.app_context():
        from easymcf.api.db import get_db

        db = get_db()
        with db:
            db.execute(
                "UPDATE mcf_session SET status = 'valid', cookie_ref = 'deleted-state.json' WHERE user_id = 1"
            )

    response = client.get("/api/v1/mcf_session/search")

    assert response.status_code == 200
    assert response.get_json()[0]["status"] == "missing"
    assert response.get_json()[0]["cookie_ref"] is None