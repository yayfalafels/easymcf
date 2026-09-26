"""17.TC.01, .07 to .10, .13, .14 — the mcf_attempt coordinator's state machine, called directly against a
stubbed SingpassBrowser (STRAT-SILO-05's pattern for a service layer), never a real Playwright browser.
"""

from __future__ import annotations

import sqlite3
import time

import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from easymcf.config import Config
from easymcf.errors import Conflict, RecordNotFound
from easymcf.services import mcf_connection

pytestmark = pytest.mark.backend


class FakeBrowser:
    def __init__(self, email="second.user@example.test", fail=False, timeout=False, authentication_fail=False, refreshed_qr=None):
        self.closed = False
        self._email = email
        self._fail = fail
        self._timeout = timeout
        self._authentication_fail = authentication_fail
        self._refreshed_qr = refreshed_qr
        self.logged_out = False

    def open_qr_login(self):
        if self._fail:
            raise RuntimeError("stub failure")

    def read_qr(self):
        return b"fake-qr-bytes", "https://app.singpass.gov.sg/qrlogin?swk_qr_ref=stub"

    def wait_for_authenticated(self, on_qr_refresh=None):
        if self._timeout:
            raise PlaywrightTimeoutError("stub timeout")
        if self._authentication_fail:
            raise RuntimeError("Singpass authentication failed")
        if self._refreshed_qr and on_qr_refresh:
            on_qr_refresh(*self._refreshed_qr)

    def read_account_email(self):
        return self._email

    def export_storage_state(self, user_id):
        return f"mcf_session_{user_id}.json"

    def logout(self):
        self.logged_out = True

    def close(self):
        self.closed = True


@pytest.fixture()
def db(isolated_db):
    connection = sqlite3.connect(isolated_db)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    yield connection
    connection.close()


@pytest.fixture()
def config(isolated_db, tmp_path):
    return Config(db_path=isolated_db, secrets_dir=str(tmp_path / "secrets"))


def _wait_until(fn, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = fn()
        if value:
            return value
        time.sleep(0.05)
    raise AssertionError("condition never became true")


def _run_to(db, config, uid, monkeypatch, browser, status):
    monkeypatch.setattr(mcf_connection, "get_browser", lambda cfg: browser)
    row = mcf_connection.start_attempt(db, config, uid)
    _wait_until(lambda: db.execute("SELECT status FROM mcf_attempt WHERE id = ?", (row["id"],)).fetchone()["status"] == status)
    return dict(db.execute("SELECT * FROM mcf_attempt WHERE id = ?", (row["id"],)).fetchone())


def test_start_attempt_reuses_the_existing_active_row(db, config, monkeypatch):
    # user 2, not user 1: the seed (17.16) already gives user 1 a terminal 'connected' mcf_attempt row, which
    # would make a raw row count assert the wrong thing here.
    before = db.execute("SELECT COUNT(*) FROM mcf_attempt WHERE user_id = 2").fetchone()[0]
    slow = FakeBrowser()
    monkeypatch.setattr(slow, "wait_for_authenticated", lambda: time.sleep(1))
    monkeypatch.setattr(mcf_connection, "get_browser", lambda cfg: slow)
    first = mcf_connection.start_attempt(db, config, 2)
    second = mcf_connection.start_attempt(db, config, 2)
    assert first["id"] == second["id"]
    after = db.execute("SELECT COUNT(*) FROM mcf_attempt WHERE user_id = 2").fetchone()[0]
    assert after == before + 1


def test_start_attempt_retires_an_active_row_without_its_runner(db, config, monkeypatch):
    now = "2026-09-23T00:00:00"
    with db:
        stale = 999_001
        db.execute(
            "INSERT INTO mcf_attempt (id, user_id, status, created_at, updated_at) VALUES (?, 2, 'account_confirmation_required', ?, ?)",
            (stale, now, now),
        )
    monkeypatch.setattr(mcf_connection, "get_browser", lambda cfg: FakeBrowser())

    row = mcf_connection.start_attempt(db, config, 2)
    assert row["id"] != stale
    stale_row = dict(db.execute("SELECT * FROM mcf_attempt WHERE id = ?", (stale,)).fetchone())
    assert stale_row["status"] == "failed"
    assert stale_row["error_code"] == "runner_unavailable"


def test_full_happy_path_writes_mcf_session_on_confirm(db, config, monkeypatch):
    # user 2: the seed leaves user 2's mcf_session.confirmed_account_email NULL, so any first confirmation
    # is legal; user 1 already carries a confirmed email from the seed and would hit the mismatch path below.
    row = _run_to(db, config, 2, monkeypatch, FakeBrowser(email="second.user@example.test"), "account_confirmation_required")
    assert row["account_email"] == "second.user@example.test"
    assert mcf_connection.get_qr_bytes(row["id"]) == b"fake-qr-bytes"

    confirmed = mcf_connection.confirm(db, config, 2, row["id"], accept=True)
    assert confirmed["status"] == "connected"
    session = dict(db.execute("SELECT * FROM mcf_session WHERE user_id = 2").fetchone())
    assert session["status"] == "valid"
    assert session["cookie_ref"] == "mcf_session_2.json"
    assert session["confirmed_account_email"] == "second.user@example.test"
    assert mcf_connection.get_qr_bytes(row["id"]) is None  # the registry entry is gone once confirmed


def test_previously_confirmed_account_reconnects_without_confirmation(db, config, monkeypatch):
    prior_email = db.execute(
        "SELECT confirmed_account_email FROM mcf_session WHERE user_id = 1"
    ).fetchone()["confirmed_account_email"]

    row = _run_to(db, config, 1, monkeypatch, FakeBrowser(email=prior_email), "connected")

    assert row["account_email"] == prior_email
    session = dict(db.execute("SELECT * FROM mcf_session WHERE user_id = 1").fetchone())
    assert session["status"] == "valid"
    assert session["cookie_ref"] == "mcf_session_1.json"
    assert session["confirmed_account_email"] == prior_email


def test_qr_refresh_replaces_the_pending_handoff(db, config, monkeypatch):
    refreshed_qr = (b"fresh-qr-bytes", "https://app.singpass.gov.sg/qrlogin?swk_qr_ref=fresh")
    row = _run_to(db, config, 2, monkeypatch, FakeBrowser(refreshed_qr=refreshed_qr), "account_confirmation_required")
    assert mcf_connection.get_qr_bytes(row["id"]) == refreshed_qr[0]
    assert mcf_connection.get_qr_link(row["id"]) == refreshed_qr[1]


def test_reject_leaves_mcf_session_untouched(db, config, monkeypatch):
    before = dict(db.execute("SELECT * FROM mcf_session WHERE user_id = 2").fetchone())
    row = _run_to(db, config, 2, monkeypatch, FakeBrowser(), "account_confirmation_required")
    rejected = mcf_connection.confirm(db, config, 2, row["id"], accept=False)
    assert rejected["status"] == "cancelled"
    after = dict(db.execute("SELECT * FROM mcf_session WHERE user_id = 2").fetchone())
    assert after == before


def test_account_mismatch_blocks_and_leaves_mcf_session_untouched(db, config, monkeypatch):
    with db:
        db.execute("UPDATE mcf_session SET confirmed_account_email = 'already.confirmed@example.test' WHERE user_id = 1")
    row = _run_to(db, config, 1, monkeypatch, FakeBrowser(email="different@example.test"), "interaction_required")
    assert row["error_code"] == "account_mismatch"
    assert row["account_email"] == "different@example.test"
    session = dict(db.execute("SELECT * FROM mcf_session WHERE user_id = 1").fetchone())
    assert session["confirmed_account_email"] == "already.confirmed@example.test"
    with pytest.raises(Conflict):
        mcf_connection.confirm(db, config, 1, row["id"], accept=True)


def test_approval_timeout_lands_on_expired_not_failed(db, config, monkeypatch):
    """17.IS.02: mcf_attempt.status='expired' names the QR's own approval window lapsing, distinct from a
    hard failure, which stays 'failed'."""
    row = _run_to(db, config, 1, monkeypatch, FakeBrowser(timeout=True), "expired")
    assert row["error_code"] is None


def test_authentication_failure_never_reaches_account_confirmation(db, config, monkeypatch):
    row = _run_to(db, config, 2, monkeypatch, FakeBrowser(authentication_fail=True), "failed")
    assert row["error_code"] == "RuntimeError"
    assert row["account_email"] is None


def test_unexpected_error_lands_on_failed_with_its_type_as_error_code(db, config, monkeypatch):
    row = _run_to(db, config, 1, monkeypatch, FakeBrowser(fail=True), "failed")
    assert row["error_code"] == "RuntimeError"


def test_disconnect_clears_mcf_session_and_removes_the_cookie_file(db, config, monkeypatch, tmp_path):
    row = _run_to(db, config, 2, monkeypatch, FakeBrowser(), "account_confirmation_required")
    mcf_connection.confirm(db, config, 2, row["id"], accept=True)
    cookie_path = tmp_path / "secrets" / "mcf_session_2.json"
    cookie_path.parent.mkdir(parents=True, exist_ok=True)
    cookie_path.write_text("{}")

    disconnected = mcf_connection.cancel(db, config, 2, row["id"])
    assert disconnected["status"] == "cancelled"
    session = dict(db.execute("SELECT * FROM mcf_session WHERE user_id = 2").fetchone())
    assert session["status"] == "missing"
    assert session["cookie_ref"] is None
    assert not cookie_path.exists()


def test_cancel_authenticated_browser_logs_out_before_closing(db, config, monkeypatch):
    browser = FakeBrowser()
    row = _run_to(db, config, 2, monkeypatch, browser, "account_confirmation_required")
    mcf_connection.cancel(db, config, 2, row["id"])
    _wait_until(lambda: browser.closed)
    assert browser.logged_out


def test_mark_reauthentication_required_expires_session_and_moves_latest_attempt(db, config, monkeypatch):
    row = _run_to(db, config, 2, monkeypatch, FakeBrowser(), "account_confirmation_required")
    mcf_connection.confirm(db, config, 2, row["id"], accept=True)

    mcf_connection.mark_reauthentication_required(db, 2)

    session = dict(db.execute("SELECT * FROM mcf_session WHERE user_id = 2").fetchone())
    assert session["status"] == "expired"
    latest = dict(db.execute("SELECT * FROM mcf_attempt WHERE id = ?", (row["id"],)).fetchone())
    assert latest["status"] == "reauthentication_required"


def test_tenancy_a_second_users_attempt_id_is_not_found(db, config, monkeypatch):
    row = _run_to(db, config, 2, monkeypatch, FakeBrowser(), "account_confirmation_required")
    with pytest.raises(RecordNotFound):
        mcf_connection.confirm(db, config, 1, row["id"], accept=True)
    with pytest.raises(RecordNotFound):
        mcf_connection.cancel(db, config, 1, row["id"])
