"""13.TC.12 to 13.TC.18 and 13.TC.51 - sign in, sign up, the user section, and the route guard in a real browser.

Each test drives the UI and then reads SQLite directly, so a passing page cannot hide a wrong row. The module spawns
one real `python -m easymcf` on its own freshly seeded database, with Google sign-in not configured.
"""

from __future__ import annotations

import os
import sqlite3
import sys
from urllib.parse import parse_qs, urlparse

import pytest

_TESTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REPO_ROOT = os.path.dirname(_TESTS_DIR)
sys.path.insert(0, _REPO_ROOT)
sys.path.insert(0, os.path.join(_REPO_ROOT, "scripts"))

from initdb import apply_schema  # noqa: E402
from resetdb import apply_seed  # noqa: E402
from tests._browser_support import sign_in, spawn_app, terminate_app  # noqa: E402
from tests.support import images  # noqa: E402

pytestmark = pytest.mark.frontend

STRONG = "Correct-Horse-9!"


@pytest.fixture(scope="module")
def ui_app(tmp_path_factory):
    db_path = str(tmp_path_factory.mktemp("easymcf-auth-ui-db") / "easymcf.db")
    apply_schema(db_path)
    apply_seed(db_path)
    photos = str(tmp_path_factory.mktemp("easymcf-auth-ui-photos"))
    secrets = str(tmp_path_factory.mktemp("easymcf-auth-ui-secrets"))
    proc, base_url = spawn_app(db_path, extra_env={"PHOTO_DIR": photos, "SECRETS_DIR": secrets})
    try:
        yield base_url, db_path
    finally:
        terminate_app(proc)


@pytest.fixture()
def fresh(browser):
    """A signed-out page in its own browser context."""
    context = browser.new_context()
    yield context.new_page()
    context.close()


def _rows(db_path, sql, *args):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(sql, args).fetchall()
    finally:
        conn.close()


def _wait(page, testid, state="visible", timeout=10_000):
    page.locator(f'[data-testid="{testid}"]').wait_for(state=state, timeout=timeout)


def _login(page, base_url, email="yayfalafels@gmail.com", password="Seed-Password-1!", route="/signin"):
    page.goto(base_url + route)
    _wait(page, "signin-submit")
    page.fill('[data-testid="signin-email"]', email)
    page.fill('[data-testid="signin-password"]', password)
    page.click('[data-testid="signin-submit"]')


def _path(page):
    return urlparse(page.url).path


# 13.TC.12 - the guard and the return path
@pytest.mark.parametrize("route", ["/leads", "/tracks", "/offers", "/cvs"])
def test_signed_out_visit_redirects_to_sign_in_and_returns_after(fresh, ui_app, route):
    base_url, _ = ui_app
    fresh.goto(base_url + route)
    _wait(fresh, "signin-submit")
    assert _path(fresh) == "/signin" and parse_qs(urlparse(fresh.url).query)["next"] == [route]
    fresh.fill('[data-testid="signin-email"]', "yayfalafels@gmail.com")
    fresh.fill('[data-testid="signin-password"]', "Seed-Password-1!")
    fresh.click('[data-testid="signin-submit"]')
    fresh.wait_for_function(f"location.pathname === '{route}'")
    _wait(fresh, "user-avatar")


def test_root_signed_out_lands_on_sign_in_and_signed_in_on_leads(fresh, ui_app):
    base_url, _ = ui_app
    fresh.goto(base_url + "/")
    _wait(fresh, "signin-submit")
    sign_in(fresh, base_url)
    fresh.goto(base_url + "/")
    _wait(fresh, "leads-tab-toapply")
    assert _path(fresh) == "/leads"


def test_a_signed_in_user_opening_sign_in_goes_to_leads(fresh, ui_app):
    base_url, _ = ui_app
    sign_in(fresh, base_url)
    fresh.goto(base_url + "/signin")
    fresh.wait_for_function("location.pathname === '/leads'")


def test_user_avatar_is_a_fixed_square(fresh, ui_app):
    base_url, _ = ui_app
    sign_in(fresh, base_url)
    fresh.goto(base_url + "/leads")
    avatar = fresh.locator('[data-testid="user-avatar"]')
    avatar.wait_for(state="visible")
    box = avatar.bounding_box()
    assert box and box["width"] == box["height"] == 32


# 13.TC.13 - the forms
def test_a_wrong_password_shows_one_message_and_no_session(fresh, ui_app):
    base_url, db_path = ui_app
    before = _rows(db_path, "SELECT COUNT(*) FROM auth_session")[0][0]
    _login(fresh, base_url, password="Wrong-Password-1!")
    _wait(fresh, "signin-error")
    assert fresh.locator('[data-testid="signin-error"]').inner_text() == "Email or password is incorrect."
    assert _path(fresh) == "/signin" and _rows(db_path, "SELECT COUNT(*) FROM auth_session")[0][0] == before
    fresh.fill('[data-testid="signin-email"]', "nobody@example.test")
    fresh.click('[data-testid="signin-submit"]')
    fresh.wait_for_function("document.querySelector('[data-testid=\"signin-error\"]')?.innerText === 'Email or password is incorrect.'")


def test_the_google_button_is_hidden_when_google_is_not_configured(fresh, ui_app):
    base_url, _ = ui_app
    fresh.goto(base_url + "/signin")
    _wait(fresh, "signin-submit")
    assert fresh.locator('[data-testid="signin-google"]').count() == 0


def test_the_password_checklist_tracks_typing_and_the_server_lists_every_unmet_rule(fresh, ui_app):
    base_url, db_path = ui_app
    fresh.goto(base_url + "/signup")
    _wait(fresh, "signup-submit")
    state = lambda code: fresh.locator(f'[data-testid="signup-rule-{code}"]').get_attribute("data-state")
    assert all(state(c) == "unmet" for c in ("too_short", "no_lowercase", "no_uppercase", "no_digit", "no_symbol"))
    fresh.fill('[data-testid="signup-name"]', "Casey Case")
    fresh.fill('[data-testid="signup-email"]', "casey.ui@example.test")
    fresh.fill('[data-testid="signup-password"]', "abc")
    assert state("no_lowercase") == "met" and state("too_short") == "unmet" and state("no_uppercase") == "unmet"
    fresh.fill('[data-testid="signup-password"]', "casey.ui-Aa9!zz")                  # contains the email local part
    assert state("contains_identity") == "unmet" and state("too_short") == "met" and state("no_symbol") == "met"
    fresh.fill('[data-testid="signup-password"]', STRONG)
    assert all(state(c) == "met" for c in ("too_short", "no_lowercase", "no_uppercase", "no_digit", "no_symbol", "contains_identity"))
    assert _rows(db_path, "SELECT COUNT(*) FROM user WHERE email = 'casey.ui@example.test'")[0][0] == 0


def test_sign_up_creates_the_account_signs_in_and_shows_initials(fresh, ui_app):
    base_url, db_path = ui_app
    fresh.goto(base_url + "/signup")
    _wait(fresh, "signup-submit")
    fresh.fill('[data-testid="signup-name"]', "Riley Rowe")
    fresh.fill('[data-testid="signup-email"]', "Riley.Rowe@Example.test")
    fresh.fill('[data-testid="signup-password"]', STRONG)
    fresh.click('[data-testid="signup-submit"]')
    _wait(fresh, "user-initials")
    assert fresh.locator('[data-testid="user-initials"]').inner_text() == "RR" and _path(fresh) == "/leads"
    row = _rows(db_path, "SELECT email, password_hash, google_sub FROM user WHERE name = 'Riley Rowe'")
    assert row[0][0] == "riley.rowe@example.test" and row[0][1].startswith("scrypt:") and row[0][2] is None
    assert _rows(db_path, "SELECT status FROM mcf_session WHERE user_id = (SELECT id FROM user WHERE name = 'Riley Rowe')") == [("missing",)]
    fresh.wait_for_selector('[data-testid="leads-tab-toapply"]')
    assert fresh.locator('[data-testid^="lead-row-"]').count() == 0                        # a new account starts empty


def test_a_duplicate_email_shows_its_message_next_to_the_field(fresh, ui_app):
    base_url, _ = ui_app
    fresh.goto(base_url + "/signup")
    _wait(fresh, "signup-submit")
    fresh.fill('[data-testid="signup-name"]', "Someone Else")
    fresh.fill('[data-testid="signup-email"]', "YAYFALAFELS@gmail.com")
    fresh.fill('[data-testid="signup-password"]', STRONG)
    fresh.click('[data-testid="signup-submit"]')
    _wait(fresh, "signup-field-error")
    assert "already exists" in fresh.locator('[data-testid="signup-field-error"]').inner_text()
    assert _path(fresh) == "/signup"


# 13.TC.14 to 13.TC.16 and 13.TC.51 - the user section
@pytest.mark.parametrize("route", ["/leads", "/tracks", "/offers", "/cvs", "/tracks/1/search"])
def test_the_user_section_appears_once_on_every_signed_in_page(fresh, ui_app, route):
    base_url, _ = ui_app
    sign_in(fresh, base_url)
    fresh.goto(base_url + route)
    _wait(fresh, "user-avatar")
    assert fresh.locator('[data-testid="user-section"]').count() == 1
    assert fresh.locator('[data-testid="user-initials"]').inner_text() == "TH"


def test_the_sign_in_pages_have_no_user_section_or_nav_links(fresh, ui_app):
    base_url, _ = ui_app
    for route in ("/signin", "/signup"):
        fresh.goto(base_url + route)
        _wait(fresh, f"{route[1:]}-heading")
        assert fresh.locator('[data-testid="user-section"]').count() == 0
        assert fresh.locator('[data-testid="nav-leads"]').count() == 0


def test_photo_upload_replace_persist_and_remove(fresh, ui_app):
    base_url, db_path = ui_app
    _login(fresh, base_url, email="second.user@example.test", password="Seed-Password-2!")
    _wait(fresh, "user-avatar")
    assert fresh.locator('[data-testid="user-photo"]').count() == 0 and fresh.locator('[data-testid="user-initials"]').inner_text() == "SS"
    fresh.click('[data-testid="user-avatar"]')
    fresh.locator('[data-testid="user-menu-photo-input"]').set_input_files(images.path("photo_ok.png"))
    _wait(fresh, "user-photo")
    ref = _rows(db_path, "SELECT photo_ref FROM user WHERE id = 2")[0][0]
    assert ref.startswith("2/avatar-") and fresh.locator('[data-testid="user-initials"]').count() == 0
    src = fresh.locator('[data-testid="user-photo"]').get_attribute("src")
    assert src.startswith("/api/v1/users/2/photo?v=") and src.endswith(ref.split("-")[1].split(".")[0])
    assert fresh.evaluate("document.querySelector('[data-testid=\"user-photo\"]').naturalWidth") == 256
    fresh.reload()                                                                          # the photo persists across page loads
    _wait(fresh, "user-photo")
    fresh.click('[data-testid="user-avatar"]')
    fresh.locator('[data-testid="user-menu-photo-input"]').set_input_files(images.path("photo_wide.jpg"))
    fresh.wait_for_function(f"!document.querySelector('[data-testid=\"user-photo\"]').src.includes('{ref.split('-')[1].split('.')[0]}')")
    fresh.click('[data-testid="user-avatar"]')                                            # the menu closes after an upload
    fresh.click('[data-testid="user-menu-remove-photo"]')
    _wait(fresh, "user-initials")
    assert _rows(db_path, "SELECT photo_ref FROM user WHERE id = 2")[0][0] is None


def test_a_fake_image_is_refused_with_a_message(fresh, ui_app):
    base_url, db_path = ui_app
    sign_in(fresh, base_url)
    fresh.goto(base_url + "/leads")
    _wait(fresh, "user-avatar")
    fresh.click('[data-testid="user-avatar"]')
    fresh.locator('[data-testid="user-menu-photo-input"]').set_input_files(images.path("photo_fake.png"))
    _wait(fresh, "user-menu-error")
    assert "accepted image" in fresh.locator('[data-testid="user-menu-error"]').inner_text() or "JPEG" in fresh.locator('[data-testid="user-menu-error"]').inner_text()
    assert _rows(db_path, "SELECT photo_ref FROM user WHERE id = 1")[0][0] is None


def test_log_out_ends_the_session_and_back_does_not_reopen_a_page(fresh, ui_app):
    base_url, db_path = ui_app
    sign_in(fresh, base_url)
    fresh.goto(base_url + "/leads")
    _wait(fresh, "user-avatar")
    sessions_before = _rows(db_path, "SELECT COUNT(*) FROM auth_session WHERE user_id = 1")[0][0]
    fresh.click('[data-testid="user-avatar"]')
    fresh.click('[data-testid="user-menu-logout"]')
    _wait(fresh, "signin-submit")
    assert _path(fresh) == "/signin" and _rows(db_path, "SELECT COUNT(*) FROM auth_session WHERE user_id = 1")[0][0] == sessions_before - 1
    fresh.go_back()
    _wait(fresh, "signin-submit")
    assert _path(fresh) == "/signin" and fresh.locator('[data-testid^="lead-row-"]').count() == 0


# 13.TC.18 - a 401 in the middle of a session
def test_a_session_that_ends_mid_use_returns_to_sign_in_and_back(fresh, ui_app):
    base_url, _ = ui_app
    sign_in(fresh, base_url)
    fresh.goto(base_url + "/leads")
    _wait(fresh, "leads-tab-toapply")
    fresh.context.clear_cookies()
    fresh.click('[data-testid="nav-tracks"]')
    _wait(fresh, "signin-submit")
    assert _path(fresh) == "/signin" and parse_qs(urlparse(fresh.url).query)["next"] == ["/tracks"]
    fresh.fill('[data-testid="signin-email"]', "yayfalafels@gmail.com")
    fresh.fill('[data-testid="signin-password"]', "Seed-Password-1!")
    fresh.click('[data-testid="signin-submit"]')
    fresh.wait_for_function("location.pathname === '/tracks'")


# 13.TC.17 and 13.TC.52 - each user sees only their own data
def test_two_users_in_two_browser_contexts_see_only_their_own_data(browser, ui_app):
    base_url, db_path = ui_app
    contexts, pages = [], []
    for name in ("seed_a", "seed_b"):
        context = browser.new_context()
        page = context.new_page()
        sign_in(page, base_url, name)
        page.goto(base_url + "/leads")
        _wait(page, "leads-tab-toapply")
        contexts.append(context)
        pages.append(page)
    a, b = pages
    a_lead, b_lead = "lead-row-1", "lead-row-15"
    assert a.locator(f'[data-testid="{a_lead}"]').count() == 1 and a.locator(f'[data-testid="{b_lead}"]').count() == 0
    b.wait_for_selector(f'[data-testid="{b_lead}"]')
    assert b.locator(f'[data-testid="{a_lead}"]').count() == 0
    for page, user in ((a, 1), (b, 2)):
        page.goto(base_url + "/tracks")
        _wait(page, "track-form")
        page.wait_for_selector('[data-testid^="track-row-"]')
        shown = {int(e.get_attribute("data-testid").rsplit("-", 1)[1]) for e in page.locator('[data-testid^="track-row-"]').all()}
        owned = {r[0] for r in _rows(db_path, "SELECT id FROM track WHERE user_id = ? AND is_active = 1", user)}
        assert shown == owned
    assert b.request.get(base_url + "/api/v1/lead/1").status == 404
    for context in contexts:
        context.close()
