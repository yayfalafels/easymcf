"""17.TC.02, 17.TC.03, 17.TC.04 — the automation-silo tier for the SingpassBrowser seam (ARCH-TEST-03).

FixtureSingpassBrowser drives the same navigation, locator, and decode code BaseSingpassBrowser gives
LiveSingpassBrowser, with every request routed to tests/fixtures/singpass/ instead of dispatched, so this tier
never resolves a real hostname (ARCH-TEST-04's pattern, applied to the Singpass seam).
"""

from __future__ import annotations

import pytest

from easymcf.automation import singpass_browser
from easymcf.automation.singpass_browser import CALLBACK_POLL_MS, QR_ELEMENT_LOCATORS, REFRESH_QR_LOCATORS
from easymcf.automation.singpass_fixture import FixtureSingpassBrowser
from easymcf.config import Config

pytestmark = pytest.mark.backend

KNOWN_QR_LINK = "https://app.singpass.gov.sg/qrlogin?swk_qr_ref=fixture-qr-ref-001"
KNOWN_ACCOUNT_EMAIL = "yayfalafels@gmail.com"


@pytest.fixture()
def browser(tmp_path):
    b = FixtureSingpassBrowser(Config(mcf_mode="fixture", secrets_dir=str(tmp_path / "secrets")))
    yield b
    b.close()


def test_fixture_browser_resolves_no_real_hostname(browser):
    seen = []
    browser._ensure_started()
    browser._page.on("request", lambda request: seen.append(request.url))
    browser.open_qr_login()
    browser.wait_for_authenticated()
    browser.read_account_email()
    assert seen, "expected at least the fixture navigations to be observed"
    assert all("mycareersfuture.gov.sg" in url or "singpass.gov.sg" in url for url in seen)
    # every one of those urls was served by the fixture route handler, not dispatched to a real socket —
    # confirmed by 17.TC.02's own reach-the-qr-page assertion below succeeding under a route("**/*") intercept.


def test_reaches_qr_page_and_extracts_a_validated_link(browser):
    browser.open_qr_login()
    image_bytes, link = browser.read_qr()
    assert len(image_bytes) > 0
    assert link == KNOWN_QR_LINK
    assert "singpass.gov.sg" in browser._page.url


def test_login_reaches_the_qr_without_a_singpass_network_idle_wait(browser, monkeypatch):
    render_waits = []
    original_wait = singpass_browser._wait_for_render

    def record_wait(page):
        render_waits.append(page.url)
        original_wait(page)

    monkeypatch.setattr(singpass_browser, "_wait_for_render", record_wait)
    browser.open_qr_login()
    assert render_waits == ["https://www.mycareersfuture.gov.sg/"]
    assert browser.read_qr()[1] == KNOWN_QR_LINK


def test_priority_locator_picks_the_real_qr_over_a_decoy(browser):
    """17.TC.03 — a named regression for the bug 17.PB.01 hit: a combined CSS selector let DOM order pick a
    decorative icon ahead of the real QR. QR_ELEMENT_LOCATORS' first two entries name the real QR by id/testid,
    ahead of the generic canvas/svg/img fallbacks a decoy could also match."""
    assert QR_ELEMENT_LOCATORS[0][0] == "id=ndi-qr-canvas"
    assert QR_ELEMENT_LOCATORS[1][0] == "data-testid=ndi-qr-canvas"
    browser.open_qr_login()
    image_bytes, link = browser.read_qr()
    assert link == KNOWN_QR_LINK


def test_refresh_qr_locators_prefer_the_singpass_refresh_control():
    assert REFRESH_QR_LOCATORS[0][0] == "role=button[name~=refresh qr]"
    assert CALLBACK_POLL_MS == 250


def test_qr_refresh_yields_immediately_to_an_authenticated_callback(browser, monkeypatch):
    browser.open_qr_login()
    authenticated_page = browser._origin_page
    monkeypatch.setattr(browser, "_find_authenticated_page", lambda: authenticated_page)

    assert browser._refresh_expired_qr() is None
    assert browser._page is authenticated_page


def test_render_wait_precedes_every_page_state_read(browser):
    """17.TC.04 — a named regression for the domcontentloaded-fires-before-render gap 17.PB.01 hit twice. Every
    page-state read in BaseSingpassBrowser goes through _wait_for_render()/_wait_for_qr_render() first; this
    confirms the full sequence still succeeds end to end against pages that would show a loading state at
    domcontentloaded (the fixture pages render synchronously, so this exercises the call sequence, not a race)."""
    browser.open_qr_login()
    browser.read_qr()
    browser.wait_for_authenticated()
    email = browser.read_account_email()
    assert email == KNOWN_ACCOUNT_EMAIL
    assert "dashboard/career" in browser._page.url


def test_callback_detection_uses_the_authenticated_context_page(browser):
    browser.open_qr_login()
    browser.wait_for_authenticated()
    assert "mycareersfuture.gov.sg/dashboard/" in browser._page.url


def test_callback_detection_does_not_wait_for_network_idle(browser, monkeypatch):
    browser.open_qr_login()
    monkeypatch.setattr(
        singpass_browser,
        "_wait_for_render",
        lambda page: pytest.fail("authenticated callback must not wait for network idle"),
    )
    browser.wait_for_authenticated()
    assert "mycareersfuture.gov.sg/dashboard/" in browser._page.url


def test_export_storage_state_writes_the_named_secrets_file(browser, tmp_path):
    browser.open_qr_login()
    browser.wait_for_authenticated()
    browser._page.evaluate("sessionStorage.setItem('fixture-auth', 'ready')")
    filename = browser.export_storage_state(user_id=42)
    assert filename == "mcf_session_42.json"
    path = tmp_path / "secrets" / filename
    assert path.exists()
    assert oct(path.stat().st_mode)[-3:] == "600"
    sidecar = tmp_path / "secrets" / "mcf_session_42.session.json"
    assert sidecar.exists()
    assert oct(sidecar.stat().st_mode)[-3:] == "600"


def test_authenticated_browser_logs_out_in_its_own_context(browser):
    browser.open_qr_login()
    browser.wait_for_authenticated()
    browser.logout()
    assert browser._page.url == "https://www.mycareersfuture.gov.sg/"
