"""TC-DB-011 - account, session, and ownership constraints, checked on a schema-only temp database (13.EL.03)."""

from __future__ import annotations

import sqlite3

import pytest

from initdb import apply_schema
from easymcf.db.connection import get_connection

pytestmark = pytest.mark.backend

AT = "2026-01-01 00:00:00"


@pytest.fixture()
def conn(tmp_path):
    path = str(tmp_path / "schema.db")
    apply_schema(path)
    connection = get_connection(path)
    yield connection
    connection.close()


def _user(conn, email, **extra):
    fields = {"name": "N", "email": email, "status": "active", "password_hash": "h", "created_at": AT, **extra}
    conn.execute(
        f"INSERT INTO user ({', '.join(fields)}) VALUES ({', '.join('?' for _ in fields)})", tuple(fields.values())
    )
    return conn.execute("SELECT id FROM user WHERE email = ?", (email,)).fetchone()["id"]


def _lead_parents(conn, user_id, email):
    """A role, a track owned by user_id, and a post, returning (track_id, post_id)."""
    conn.execute("INSERT OR IGNORE INTO role (id, name) VALUES (1, 'r')")
    conn.execute("INSERT INTO track (user_id, role_id, seniority) VALUES (?, 1, 'mid')", (user_id,))
    track_id = conn.execute("SELECT MAX(id) FROM track").fetchone()[0]
    conn.execute(
        "INSERT OR IGNORE INTO post (id, source, position_title, company_name, src_method) VALUES ('p1', 's', 't', 'c', 'scraped')"
    )
    return track_id, "p1"


def _lead(conn, user_id, track_id, post_id="p1"):
    conn.execute(
        "INSERT INTO lead (user_id, post_id, track_id, status, stage, position_title, company_name, created_at, updated_at) "
        "VALUES (?, ?, ?, 'OPEN', 'TOAPPLY', 't', 'c', ?, ?)",
        (user_id, post_id, track_id, AT, AT),
    )


def test_email_is_lowercase_and_unique(conn):
    _user(conn, "a@example.test")
    with pytest.raises(sqlite3.IntegrityError):
        _user(conn, "A@example.test")
    with pytest.raises(sqlite3.IntegrityError):
        _user(conn, "a@example.test")


def test_user_needs_a_sign_in_method(conn):
    with pytest.raises(sqlite3.IntegrityError):
        _user(conn, "b@example.test", password_hash=None)
    _user(conn, "c@example.test", password_hash=None, google_sub="sub-1")


def test_google_sub_is_unique(conn):
    _user(conn, "a@example.test", google_sub="sub-1")
    with pytest.raises(sqlite3.IntegrityError):
        _user(conn, "b@example.test", google_sub="sub-1")


def test_auth_session_token_unique_and_cascades(conn):
    uid = _user(conn, "a@example.test")
    conn.execute("INSERT INTO auth_session (user_id, token_hash, created_at, expires_at) VALUES (?, 'd', ?, ?)", (uid, AT, AT))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO auth_session (user_id, token_hash, created_at, expires_at) VALUES (?, 'd', ?, ?)", (uid, AT, AT))
    conn.execute("DELETE FROM user WHERE id = ?", (uid,))
    assert conn.execute("SELECT COUNT(*) FROM auth_session").fetchone()[0] == 0


def test_one_mcf_session_per_user(conn):
    uid = _user(conn, "a@example.test")
    conn.execute("INSERT INTO mcf_session (user_id, status) VALUES (?, 'missing')", (uid,))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO mcf_session (user_id, status) VALUES (?, 'missing')", (uid,))


def test_mcf_attempt_status_is_constrained(conn):
    uid = _user(conn, "a@example.test")
    row = "INSERT INTO mcf_attempt (user_id, status, created_at, updated_at) VALUES (?, ?, ?, ?)"
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(row, (uid, "bogus", AT, AT))
    conn.execute(row, (uid, "starting", AT, AT))


def test_mcf_attempt_active_is_unique_per_user(conn):
    a, b = _user(conn, "a@example.test"), _user(conn, "b@example.test")
    row = "INSERT INTO mcf_attempt (user_id, status, created_at, updated_at) VALUES (?, ?, ?, ?)"
    conn.execute(row, (a, "starting", AT, AT))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(row, (a, "awaiting_approval", AT, AT))  # a second active status still conflicts
    conn.execute(row, (b, "starting", AT, AT))               # another user's own active attempt is unaffected

    conn.execute(row, (a, "failed", AT, AT))                 # a terminal status never conflicts, even repeated
    conn.execute(row, (a, "failed", AT, AT))


def test_cv_label_unique_within_a_user_only(conn):
    a, b = _user(conn, "a@example.test"), _user(conn, "b@example.test")
    conn.execute("INSERT INTO cv (user_id, label) VALUES (?, 'L')", (a,))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO cv (user_id, label) VALUES (?, 'L')", (a,))
    conn.execute("INSERT INTO cv (user_id, label) VALUES (?, 'L')", (b,))


def test_lead_is_unique_per_user_and_post(conn):
    a, b = _user(conn, "a@example.test"), _user(conn, "b@example.test")
    track_a, _ = _lead_parents(conn, a, "a")
    track_b, _ = _lead_parents(conn, b, "b")
    _lead(conn, a, track_a)
    with pytest.raises(sqlite3.IntegrityError):
        _lead(conn, a, track_a)
    _lead(conn, b, track_b)                      # another user may hold a lead on the same post


def test_lead_owner_trigger_on_insert_and_update(conn):
    a, b = _user(conn, "a@example.test"), _user(conn, "b@example.test")
    track_a, _ = _lead_parents(conn, a, "a")
    with pytest.raises(sqlite3.IntegrityError, match="track owner"):
        _lead(conn, b, track_a)
    _lead(conn, a, track_a)
    with pytest.raises(sqlite3.IntegrityError, match="track owner"):
        conn.execute("UPDATE lead SET user_id = ?", (b,))


def test_lead_url_must_be_http_or_null(conn):
    a = _user(conn, "a@example.test")
    track_a, _ = _lead_parents(conn, a, "a")
    _lead(conn, a, track_a)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE lead SET url_ref = 'ftp://x'")
    conn.execute("UPDATE lead SET url_ref = 'https://x.example'")
    conn.execute("UPDATE lead SET url_ref = NULL")


def test_running_run_is_unique_per_user_and_type(conn):
    a, b = _user(conn, "a@example.test"), _user(conn, "b@example.test")
    row = "INSERT INTO run_log (run_type, user_id, started_at, status) VALUES ('search', ?, ?, 'running')"
    conn.execute(row, (a, AT))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(row, (a, AT))
    conn.execute(row, (b, AT))
