"""17.TC.05, 17.TC.07 - the full stack against the fixture SingpassBrowser (ARCH-TEST-04's tier, one layer over):
Playwright Chromium driving the real AngularJS app against a real Flask process, MCF_MODE=fixture routing every
Singpass/MCF request to tests/fixtures/singpass/ rather than dispatching it. The real automation code runs
unchanged; only the bytes come from disk.
"""

from __future__ import annotations

import os
import json
import sqlite3
import sys

import pytest

_TESTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REPO_ROOT = os.path.dirname(_TESTS_DIR)
sys.path.insert(0, _REPO_ROOT)
sys.path.insert(0, os.path.join(_REPO_ROOT, "scripts"))

from initdb import apply_schema  # noqa: E402
from render_seed import PUBLIC_DEFAULTS  # noqa: E402
from resetdb import apply_seed  # noqa: E402
from tests._browser_support import sign_in, spawn_app, terminate_app  # noqa: E402

pytestmark = pytest.mark.e2e

FOUND_EMAIL = "demo.user@example.test"  # tests/fixtures/singpass/profile.html's own captured value


def _rows(db_path, sql, *args):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, args)]
    finally:
        conn.close()


@pytest.fixture()
def app(tmp_path):
    db_path = str(tmp_path / "easymcf.db")
    apply_schema(db_path)
    apply_seed(db_path, PUBLIC_DEFAULTS)
    proc, base_url = spawn_app(db_path, extra_env={"SECRETS_DIR": str(tmp_path / "secrets")})
    try:
        yield base_url, db_path
    finally:
        terminate_app(proc)


@pytest.fixture()
def fresh(browser):
    context = browser.new_context()
    yield context.new_page()
    context.close()


@pytest.mark.timeout(180)  # 17.IS.05..11: real Chromium launch/navigation under load ran 40s+ for one step alone
def test_connect_confirm_writes_mcf_session_and_the_icon_reflects_it(fresh, app):
    base_url, db_path = app
    sign_in(fresh, base_url, "seed_b")  # seed user 2 starts 'missing', per 17.16's seed
    fresh.goto(base_url + "/leads")
    fresh.locator('[data-testid="mcf-nav-icon"]').wait_for(state="visible", timeout=10_000)
    icon_image = fresh.locator('[data-testid="mcf-nav-icon"] .mcf-nav-image')
    assert icon_image.get_attribute("src") == "/assets/mcf-icon-magnifying-glass.png"
    assert icon_image.evaluate("el => el.getBoundingClientRect().width") > 38.4
    assert fresh.locator('[data-testid="mcf-nav-icon"]').evaluate("el => getComputedStyle(el).overflow") == "hidden"
    fresh.click('[data-testid="mcf-nav-icon"]')
    fresh.locator('[data-testid="mcf-connect-modal"]').wait_for(state="visible", timeout=10_000)
    assert fresh.locator('[data-testid="mcf-connect-modal"]').evaluate("el => getComputedStyle(el).backgroundColor") == "rgb(227, 240, 232)"
    assert fresh.locator('[data-testid="mcf-connect-modal"]').evaluate("el => getComputedStyle(el, '::before').backgroundColor") == "rgba(0, 0, 0, 0)"
    fresh.click('[data-testid="mcf-nav-icon"]')
    assert fresh.locator('[data-testid="mcf-connect-modal"]').is_hidden()
    fresh.click('[data-testid="mcf-nav-icon"]')
    fresh.locator('[data-testid="mcf-authentication-retry"]').wait_for(state="visible", timeout=10_000)
    fresh.click('[data-testid="mcf-authentication-retry"]')

    fresh.locator('[data-testid="mcf-qr-image"]').wait_for(state="visible", timeout=60_000)
    fresh.locator('[data-testid="mcf-confirm-yes"]').wait_for(state="visible", timeout=60_000)
    assert FOUND_EMAIL in fresh.locator('[data-testid="mcf-confirm-message"]').inner_text()
    fresh.click('[data-testid="mcf-confirm-yes"]')
    fresh.locator('[data-testid="mcf-current-state"]').wait_for(state="visible", timeout=10_000)
    assert fresh.locator('[data-testid="mcf-disconnect"]').is_visible()
    fresh.click('[data-testid="mcf-modal-close"]')
    assert fresh.locator('[data-testid="mcf-connect-modal"]').is_hidden()

    # confirm() answers synchronously once mcf_session is written (mcf_connection.py's own bounded poll), so
    # the row is already final by the time the click's own response lands; a fresh page load, rather than
    # reopening the same in-memory Angular state, is what actually exercises the icon's own poll from cold.
    fresh.wait_for_timeout(200)
    fresh.goto(base_url + "/leads")
    fresh.locator('[data-testid="mcf-nav-icon"]').wait_for(state="visible", timeout=10_000)
    fresh.locator('[data-testid="mcf-status-dot"]').wait_for(state="visible", timeout=10_000)

    def _dot_class():
        return fresh.locator('[data-testid="mcf-status-dot"]').get_attribute("class") or ""

    fresh.wait_for_function(
        "document.querySelector('[data-testid=\"mcf-status-dot\"]').className.indexOf('mcf-status-green') !== -1",
        timeout=10_000,
    )
    assert "mcf-status-green" in _dot_class()

    fresh.click('[data-testid="mcf-nav-icon"]')
    fresh.locator('[data-testid="mcf-disconnect"]').wait_for(state="visible", timeout=10_000)
    assert fresh.locator('[data-testid="mcf-status"]').inner_text() == f"Connected as {FOUND_EMAIL}"
    assert fresh.locator('[data-testid^="mcf-attempt-row-"]').count() == 0  # 17.IS.08: no history rendered

    session = _rows(db_path, "SELECT * FROM mcf_session WHERE user_id = 2")[0]
    assert session["status"] == "valid"
    assert session["confirmed_account_email"] == FOUND_EMAIL
    assert session["cookie_ref"] == "mcf_session_2.json"


@pytest.mark.timeout(180)
def test_a_confirmed_identity_mismatch_lands_on_interaction_required(fresh, app):
    """17.TC.07: a later connection attempt under a different MCF account than the one already confirmed is
    blocked rather than silently overwritten."""
    base_url, db_path = app
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE mcf_session SET confirmed_account_email = 'someone.else@example.test' WHERE user_id = 2")
    conn.commit()
    conn.close()

    sign_in(fresh, base_url, "seed_b")
    fresh.goto(base_url + "/leads")
    fresh.locator('[data-testid="mcf-nav-icon"]').wait_for(state="visible", timeout=10_000)
    fresh.click('[data-testid="mcf-nav-icon"]')
    fresh.locator('[data-testid="mcf-authentication-retry"]').wait_for(state="visible", timeout=10_000)
    fresh.click('[data-testid="mcf-authentication-retry"]')

    fresh.locator('[data-testid="mcf-mismatch-message"]').wait_for(state="visible", timeout=60_000)
    message = fresh.locator('[data-testid="mcf-mismatch-message"]').inner_text()
    assert FOUND_EMAIL in message

    session = _rows(db_path, "SELECT * FROM mcf_session WHERE user_id = 2")[0]
    assert session["confirmed_account_email"] == "someone.else@example.test"  # untouched by the mismatch


def test_failed_authentication_offers_retry_or_cancel_without_confirmation(fresh, app):
    base_url, _ = app
    sign_in(fresh, base_url, "seed_b")  # user 2's seeded attempt is failed
    fresh.goto(base_url + "/leads")
    fresh.locator('[data-testid="mcf-nav-icon"]').wait_for(state="visible", timeout=10_000)
    fresh.click('[data-testid="mcf-nav-icon"]')
    fresh.locator('[data-testid="mcf-authentication-failed"]').wait_for(state="visible", timeout=10_000)
    assert "Singpass authentication failed" in fresh.locator('[data-testid="mcf-authentication-failed-message"]').inner_text()
    assert fresh.locator('[data-testid="mcf-authentication-retry"]').is_visible()
    assert fresh.locator('[data-testid="mcf-authentication-cancel"]').is_visible()
    assert fresh.locator('[data-testid="mcf-confirm-step"]').count() == 0
    fresh.click('[data-testid="mcf-authentication-cancel"]')
    assert fresh.locator('[data-testid="mcf-connect-modal"]').is_hidden()


def test_active_qr_attempt_can_be_cancelled_from_the_popup(fresh, app):
    base_url, _ = app
    sign_in(fresh, base_url, "seed_b")
    fresh.goto(base_url + "/leads")
    fresh.locator('[data-testid="mcf-nav-icon"]').wait_for(state="visible", timeout=10_000)
    fresh.click('[data-testid="mcf-nav-icon"]')
    fresh.locator('[data-testid="mcf-authentication-retry"]').wait_for(state="visible", timeout=10_000)
    fresh.click('[data-testid="mcf-authentication-retry"]')
    fresh.locator('[data-testid="mcf-qr-image"]').wait_for(state="visible", timeout=60_000)
    fresh.click('[data-testid="mcf-cancel-attempt"]')
    fresh.locator('[data-testid="mcf-connect"]').wait_for(state="visible", timeout=10_000)


def test_valid_session_routes_popup_and_lead_links_to_authenticated_browser(fresh, app):
    base_url, db_path = app
    opened = []
    external_requests = []

    secrets_dir = os.path.join(os.path.dirname(db_path), "secrets")
    os.makedirs(secrets_dir, exist_ok=True)
    with open(os.path.join(secrets_dir, "mcf_session_1.json"), "w", encoding="utf-8") as handle:
        handle.write("{}")
    conn = sqlite3.connect(db_path)
    conn.execute(
        "UPDATE mcf_session SET status = 'valid', cookie_ref = 'mcf_session_1.json' WHERE user_id = 1"
    )
    conn.commit()
    conn.close()

    def authenticated_open(route, request):
        opened.append(request.post_data_json)
        route.fulfill(status=202, content_type="application/json", body=json.dumps({"mode": "authenticated"}))

    fresh.context.route("**/api/v1/mcf_session/open", authenticated_open)
    fresh.context.route(
        "https://www.mycareersfuture.gov.sg/**",
        lambda route, request: (external_requests.append(request.url), route.abort()),
    )
    sign_in(fresh, base_url, "seed_a")
    fresh.goto(base_url + "/leads")
    fresh.click('[data-testid="mcf-nav-icon"]')
    fresh.locator('[data-testid="mcf-open"]').wait_for(state="visible", timeout=10_000)
    fresh.click('[data-testid="mcf-open"]')
    fresh.wait_for_function("() => true", timeout=1_000)
    assert opened == [{"url": "https://www.mycareersfuture.gov.sg/"}]

    fresh.click('[data-testid="mcf-modal-close"]')
    lead_link = fresh.locator('[data-testid^="lead-title-link-"]').first
    target_url = lead_link.get_attribute("href")
    lead_link.click()
    fresh.wait_for_timeout(100)
    assert opened[-1] == {"url": target_url}
    assert external_requests == []


def test_missing_session_keeps_plain_mcf_link_fallback(fresh, app):
    base_url, _ = app
    api_requests = []
    external_requests = []
    fresh.context.on(
        "request",
        lambda request: api_requests.append(request.url) if "/api/v1/mcf_session/open" in request.url else None,
    )
    fresh.context.route(
        "https://www.mycareersfuture.gov.sg/**",
        lambda route, request: (external_requests.append(request.url), route.abort()),
    )
    sign_in(fresh, base_url, "seed_b")
    fresh.goto(base_url + "/leads")
    lead_link = fresh.locator('[data-testid^="lead-title-link-"]').first
    target_url = lead_link.get_attribute("href")

    with fresh.context.expect_page() as popup_info:
        lead_link.click()
    popup = popup_info.value
    popup.wait_for_load_state("domcontentloaded")

    assert external_requests == [target_url]
    assert api_requests == []
    popup.close()
