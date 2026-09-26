"""13.TC.38 to 13.TC.42 and 13.TC.44 - Google sign-in through the real UI against the stub identity provider.

Full stack: Playwright Chromium, the real AngularJS app, the real Flask process, and the stub provider from
tests/support in place of Google. Each flow ends with a read of the `user` table, so a passing page cannot hide a
wrong row. The search-run case 13.TC.43 needs the search service from milestone 10.
"""

from __future__ import annotations

import os
import sqlite3
import sys
from urllib.parse import urlparse

import pytest

_TESTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REPO_ROOT = os.path.dirname(_TESTS_DIR)
sys.path.insert(0, _REPO_ROOT)
sys.path.insert(0, os.path.join(_REPO_ROOT, "scripts"))

from initdb import apply_schema  # noqa: E402
from resetdb import apply_seed  # noqa: E402
from tests._browser_support import _free_port, sign_in, spawn_app, terminate_app  # noqa: E402
from tests.support import stub_oidc  # noqa: E402

pytestmark = pytest.mark.e2e


@pytest.fixture(scope="module")
def google_ui(tmp_path_factory):
    server, stub_url = stub_oidc.serve()
    root = tmp_path_factory.mktemp("easymcf-google-ui")
    db_path = str(root / "easymcf.db")
    apply_schema(db_path)
    apply_seed(db_path)
    secret = root / "gcp_oauth_client_secret"
    secret.write_text("stub-client-secret\n")
    secret.chmod(0o600)
    port = _free_port()
    env = {
        "GOOGLE_DISCOVERY_URL": stub_url + "/.well-known/openid-configuration", "GCP_OAUTH_CLIENT_ID": "stub-client-id",
        "GCP_OAUTH_SECRET_FILE": str(secret), "GOOGLE_REDIRECT_URI": f"http://127.0.0.1:{port}/api/v1/auth/google/callback",
        "PHOTO_DIR": str(root / "photos"), "SECRETS_DIR": str(root / "secrets"),
    }
    proc, base_url = spawn_app(db_path, port=port, extra_env=env)
    try:
        yield base_url, db_path
    finally:
        terminate_app(proc)
        server.shutdown()


def _rows(db_path, sql, *args):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(sql, args).fetchall()
    finally:
        conn.close()


def _google(page, base_url, email, route="/signin", decision="stub-approve"):
    """Click Continue with Google, complete the stub's consent page as `email`, and wait to be back on the app."""
    page.goto(base_url + route)
    page.locator('[data-testid="signin-google"]').wait_for(state="visible", timeout=10_000)
    page.click('[data-testid="signin-google"]')
    page.locator('[data-testid="stub-email"]').wait_for(state="visible", timeout=10_000)
    page.fill('[data-testid="stub-email"]', email)
    page.click(f'[data-testid="{decision}"]')
    page.wait_for_function(f"location.origin === '{base_url}'", timeout=15_000)


@pytest.fixture()
def fresh(browser):
    context = browser.new_context()
    yield context.new_page()
    context.close()


def test_the_google_button_shows_when_google_is_configured(fresh, google_ui):
    base_url, _ = google_ui
    fresh.goto(base_url + "/signin")
    fresh.locator('[data-testid="signin-google"]').wait_for(state="visible", timeout=10_000)
    assert fresh.locator('[data-testid="signin-google"]').get_attribute("href").startswith("/api/v1/auth/google/start?next=")
    fresh.goto(base_url + "/signup")
    fresh.locator('[data-testid="signup-google"]').wait_for(state="visible", timeout=10_000)


# 13.TC.38
def test_a_new_google_identity_lands_on_the_requested_page_with_its_name_and_picture(fresh, google_ui):
    base_url, db_path = google_ui
    fresh.goto(base_url + "/tracks")                                   # signed out, so the app asks to sign in and remembers /tracks
    fresh.locator('[data-testid="signin-google"]').wait_for(state="visible", timeout=10_000)
    fresh.click('[data-testid="signin-google"]')
    fresh.fill('[data-testid="stub-email"]', "first.google@example.test")
    fresh.click('[data-testid="stub-approve"]')
    fresh.wait_for_function("location.pathname === '/tracks'", timeout=15_000)
    fresh.locator('[data-testid="user-photo"]').wait_for(state="visible", timeout=10_000)
    fresh.click('[data-testid="user-avatar"]')
    assert fresh.locator('[data-testid="user-name"]').inner_text() == "First Google"
    row = _rows(db_path, "SELECT name, email, password_hash, google_sub, photo_ref FROM user WHERE email = 'first.google@example.test'")
    assert len(row) == 1 and row[0][0] == "First Google" and row[0][2] is None and row[0][3].startswith("stub-sub-") and row[0][4]
    # A visible <img> can still be downloading; naturalWidth reads 0 until it finishes (13.IS.25).
    fresh.wait_for_function("document.querySelector('[data-testid=\"user-photo\"]').complete", timeout=10_000)
    assert fresh.evaluate("document.querySelector('[data-testid=\"user-photo\"]').naturalWidth") == 256


# 13.TC.39
def test_signing_out_and_in_with_google_returns_to_the_same_account(fresh, google_ui):
    base_url, db_path = google_ui
    _google(fresh, base_url, "returning.google@example.test")
    fresh.locator('[data-testid="user-avatar"]').wait_for(state="visible", timeout=10_000)
    first = _rows(db_path, "SELECT id FROM user WHERE email = 'returning.google@example.test'")
    fresh.click('[data-testid="user-avatar"]')
    fresh.click('[data-testid="user-menu-logout"]')
    fresh.locator('[data-testid="signin-submit"]').wait_for(state="visible", timeout=10_000)
    _google(fresh, base_url, "returning.google@example.test")
    fresh.locator('[data-testid="user-avatar"]').wait_for(state="visible", timeout=10_000)
    assert _rows(db_path, "SELECT id FROM user WHERE email = 'returning.google@example.test'") == first
    assert _rows(db_path, "SELECT COUNT(*) FROM user WHERE google_sub IS NOT NULL AND email = 'returning.google@example.test'") == [(1,)]


# 13.TC.40
def test_a_google_identity_matching_a_password_account_links_and_both_methods_work(fresh, google_ui, browser):
    base_url, db_path = google_ui
    _google(fresh, base_url, "second.user@example.test")
    fresh.locator('[data-testid="user-avatar"]').wait_for(state="visible", timeout=10_000)
    rows = _rows(db_path, "SELECT id, password_hash IS NOT NULL, google_sub FROM user WHERE email = 'second.user@example.test'")
    assert len(rows) == 1 and rows[0][0] == 2 and rows[0][1] == 1 and rows[0][2].startswith("stub-sub-")
    context = browser.new_context()
    page = context.new_page()
    sign_in(page, base_url, "seed_b")                                   # the password still signs in
    page.goto(base_url + "/leads")
    page.locator('[data-testid="user-avatar"]').wait_for(state="visible", timeout=10_000)
    context.close()


# 13.TC.44 and the failure messages
@pytest.mark.parametrize("email, decision, message", [
    ("any.user@example.test", "stub-deny", "Google sign-in was cancelled."),
    ("unverified.user@example.test", "stub-approve", "The Google account email is not verified."),
    ("badsig.user@example.test", "stub-approve", "Google sign-in could not be verified. Try again."),
    ("badnonce.user@example.test", "stub-approve", "Google sign-in could not be verified. Try again."),
])
def test_a_failed_google_sign_in_returns_to_sign_in_with_a_message_and_creates_nothing(fresh, google_ui, email, decision, message):
    base_url, db_path = google_ui
    before = _rows(db_path, "SELECT COUNT(*) FROM user")[0][0]
    _google(fresh, base_url, email, decision=decision)
    fresh.locator('[data-testid="signin-error"]').wait_for(state="visible", timeout=10_000)
    assert fresh.locator('[data-testid="signin-error"]').inner_text() == message
    assert urlparse(fresh.url).path == "/signin" and _rows(db_path, "SELECT COUNT(*) FROM user")[0][0] == before
    assert fresh.locator('[data-testid="user-section"]').count() == 0


# 13.TC.41
def test_sign_up_upload_a_photo_sign_out_and_in_and_the_photo_persists(fresh, google_ui):
    from tests.support import images

    base_url, db_path = google_ui
    fresh.goto(base_url + "/signup")
    fresh.locator('[data-testid="signup-submit"]').wait_for(state="visible", timeout=10_000)
    fresh.fill('[data-testid="signup-name"]', "Photo Person")
    fresh.fill('[data-testid="signup-email"]', "photo.person@example.test")
    fresh.fill('[data-testid="signup-password"]', "Correct-Horse-9!")
    fresh.click('[data-testid="signup-submit"]')
    fresh.locator('[data-testid="user-initials"]').wait_for(state="visible", timeout=10_000)
    fresh.click('[data-testid="user-avatar"]')
    fresh.locator('[data-testid="user-menu-photo-input"]').set_input_files(images.path("photo_ok.png"))
    fresh.locator('[data-testid="user-photo"]').wait_for(state="visible", timeout=10_000)
    ref = _rows(db_path, "SELECT photo_ref FROM user WHERE email = 'photo.person@example.test'")[0][0]
    assert ref
    fresh.click('[data-testid="user-avatar"]')
    fresh.click('[data-testid="user-menu-logout"]')
    fresh.locator('[data-testid="signin-submit"]').wait_for(state="visible", timeout=10_000)
    fresh.fill('[data-testid="signin-email"]', "photo.person@example.test")
    fresh.fill('[data-testid="signin-password"]', "Correct-Horse-9!")
    fresh.click('[data-testid="signin-submit"]')
    fresh.locator('[data-testid="user-photo"]').wait_for(state="visible", timeout=10_000)
    assert fresh.evaluate("document.querySelector('[data-testid=\"user-photo\"]').naturalWidth") == 256
