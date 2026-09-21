"""13.TC.33 and 13.TC.34 - Google sign-in against the stub provider: the token matrix and the linking matrix.

The stub signs tokens with its own key and selects a failure from the email prefix. Every rejection must create
neither a user nor an auth_session, and every expected row is hard-coded from the Design section.
"""

from __future__ import annotations

import sqlite3
from urllib.parse import parse_qs, urlparse

import pytest
import requests

pytestmark = pytest.mark.backend


def _flow(app, stub_url, email, next_path="/leads", decision="approve"):
    """Run start, the stub's consent, and the callback. Returns (client, callback response)."""
    client = app.test_client()
    start = client.get(f"/api/v1/auth/google/start?next={next_path}")
    assert start.status_code == 302, start.get_data(as_text=True)
    query = parse_qs(urlparse(start.headers["Location"]).query)
    consent = requests.post(stub_url + "/authorize", allow_redirects=False, data={
        "email": email, "decision": decision, "redirect_uri": query["redirect_uri"][0], "state": query["state"][0],
        "nonce": query["nonce"][0], "code_challenge": query["code_challenge"][0], "client_id": query["client_id"][0]})
    callback = urlparse(consent.headers["Location"])
    return client, client.get(f"{callback.path}?{callback.query}")


def _rows(db_path, sql, *args):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(sql, args).fetchall()
    finally:
        conn.close()


def test_start_redirects_to_the_provider_with_state_nonce_and_pkce(google_app, stub_provider):
    response = google_app.test_client().get("/api/v1/auth/google/start?next=/leads")
    location = urlparse(response.headers["Location"])
    query = parse_qs(location.query)
    assert response.status_code == 302 and response.headers["Location"].startswith(stub_provider + "/authorize")
    assert query["client_id"] == ["stub-client-id"] and query["response_type"] == ["code"]
    assert query["code_challenge_method"] == ["S256"] and query["prompt"] == ["select_account"]
    assert query["scope"] == ["openid email profile"]
    for key in ("state", "nonce", "code_challenge"):
        assert query[key][0]


def test_auth_config_reports_google_enabled(anon_client, google_app):  # anon_client first, so it is built before the Google env is set
    assert google_app.test_client().get("/api/v1/auth/config").get_json() == {"google_enabled": True}
    assert anon_client.get("/api/v1/auth/config").get_json() == {"google_enabled": False}
    assert anon_client.get("/api/v1/auth/google/start").get_json()["error"] == "google_not_configured"


@pytest.mark.parametrize("email, location", [
    ("valid.user@example.test", "/leads"),
    ("badsig.user@example.test", "/signin?error=google_invalid"),
    ("badaud.user@example.test", "/signin?error=google_invalid"),
    ("badiss.user@example.test", "/signin?error=google_invalid"),
    ("expired.user@example.test", "/signin?error=google_invalid"),
    ("badnonce.user@example.test", "/signin?error=google_invalid"),
    ("badstate.user@example.test", "/signin?error=google_invalid"),
    ("unverified.user@example.test", "/signin?error=google_email_unverified"),
])
def test_token_matrix(google_app, stub_provider, isolated_db, email, location):
    users_before = _rows(isolated_db, "SELECT COUNT(*) FROM user")[0][0]
    client, response = _flow(google_app, stub_provider, email)
    assert response.status_code == 302 and response.headers["Location"] == location
    created = _rows(isolated_db, "SELECT COUNT(*) FROM user")[0][0] - users_before
    if location == "/leads":
        assert created == 1 and "easymcf_session" in response.headers["Set-Cookie"]
        assert client.get("/api/v1/auth/me").get_json()["email"] == email
    else:
        assert created == 0 and "easymcf_session" not in response.headers.get("Set-Cookie", "")
        assert client.get("/api/v1/auth/me").status_code == 401
    assert _rows(isolated_db, "SELECT COUNT(*) FROM auth_session WHERE user_id > 2")[0][0] == (1 if created else 0)


def test_denied_consent_redirects_with_a_message_and_creates_nothing(google_app, stub_provider, isolated_db):
    client, response = _flow(google_app, stub_provider, "valid.user@example.test", decision="deny")
    assert response.headers["Location"] == "/signin?error=google_denied"
    assert _rows(isolated_db, "SELECT COUNT(*) FROM user")[0][0] == 2


def test_callback_with_a_state_that_was_never_issued_is_invalid(google_app):
    response = google_app.test_client().get("/api/v1/auth/google/callback?state=wrong&code=x")
    assert response.status_code == 302 and response.headers["Location"] == "/signin?error=google_invalid"


@pytest.mark.parametrize("next_path, expected", [("/tracks", "/tracks"), ("//evil.example", "/"), ("https://evil.example", "/")])
def test_next_is_kept_only_when_it_is_a_same_origin_path(google_app, stub_provider, next_path, expected):
    _, response = _flow(google_app, stub_provider, "valid.user@example.test", next_path=next_path)
    assert response.headers["Location"] == expected


# 13.TC.34 - the account linking matrix
def _google_user(db_path, email, sub, password_hash="x"):
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO user (name, email, status, password_hash, google_sub, created_at) VALUES ('P', ?, 'active', ?, ?, '2026-01-01 00:00:00')",
                 (email, password_hash, sub))
    conn.commit()
    conn.close()


def test_a_new_subject_with_no_account_creates_one_with_a_null_hash(google_app, stub_provider, isolated_db):
    _flow(google_app, stub_provider, "brand.new@example.test")
    row = _rows(isolated_db, "SELECT email, password_hash, google_sub, photo_ref FROM user WHERE email = 'brand.new@example.test'")
    assert len(row) == 1 and row[0][1] is None and row[0][2].startswith("stub-sub-") and row[0][3]
    assert _rows(isolated_db, "SELECT status FROM mcf_session WHERE user_id = (SELECT id FROM user WHERE email = 'brand.new@example.test')") == [("missing",)]


def test_a_verified_identity_links_to_the_password_account_with_that_email(google_app, stub_provider, isolated_db, anon_client):
    _flow(google_app, stub_provider, "second.user@example.test")     # seeded user 2 signs up with Google after the fact
    rows = _rows(isolated_db, "SELECT id, password_hash IS NOT NULL, google_sub FROM user WHERE email = 'second.user@example.test'")
    assert len(rows) == 1 and rows[0][0] == 2 and rows[0][1] == 1 and rows[0][2].startswith("stub-sub-")
    client = google_app.test_client()                                  # the password still works
    assert client.post("/api/v1/auth/signin", json={"email": "second.user@example.test", "password": "Seed-Password-2!"}).status_code == 200


def test_an_unverified_identity_never_links_or_creates(google_app, stub_provider, isolated_db):
    _, response = _flow(google_app, stub_provider, "unverified.second@example.test")
    assert response.headers["Location"] == "/signin?error=google_email_unverified"
    conn_rows = _rows(isolated_db, "SELECT google_sub FROM user WHERE google_sub IS NOT NULL")
    assert conn_rows == []


def test_a_returning_subject_signs_in_to_the_same_account(google_app, stub_provider, isolated_db):
    _flow(google_app, stub_provider, "returning.user@example.test")
    first = _rows(isolated_db, "SELECT id FROM user WHERE email = 'returning.user@example.test'")
    _flow(google_app, stub_provider, "returning.user@example.test")
    assert _rows(isolated_db, "SELECT id FROM user WHERE email = 'returning.user@example.test'") == first
    assert _rows(isolated_db, "SELECT COUNT(*) FROM user WHERE google_sub IS NOT NULL")[0][0] == 1


def test_google_account_cannot_use_the_password_form(google_app, stub_provider):
    _flow(google_app, stub_provider, "only.google@example.test")
    failure = google_app.test_client().post("/api/v1/auth/signin", json={"email": "only.google@example.test", "password": "Correct-Horse-9!"})
    assert failure.status_code == 401 and failure.get_json()["error"] == "invalid_credentials"


def test_the_google_picture_becomes_the_initial_photo_and_a_user_photo_is_kept(google_app, stub_provider, isolated_db, tmp_path):
    _flow(google_app, stub_provider, "photo.first@example.test")
    ref = _rows(isolated_db, "SELECT photo_ref FROM user WHERE email = 'photo.first@example.test'")[0][0]
    assert ref and ref.endswith(".png")
    conn = sqlite3.connect(isolated_db)
    conn.execute("UPDATE user SET photo_ref = 'kept/avatar-aaaaaaaa.png' WHERE email = 'photo.first@example.test'")
    conn.commit()
    conn.close()
    _flow(google_app, stub_provider, "photo.first@example.test")       # a returning identity never replaces the photo
    assert _rows(isolated_db, "SELECT photo_ref FROM user WHERE email = 'photo.first@example.test'")[0][0] == "kept/avatar-aaaaaaaa.png"
