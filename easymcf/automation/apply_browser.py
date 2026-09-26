"""ARCH-BOT-02 — the ApplyBrowser seam, the third beside MCFBrowser and SingpassBrowser.

Interactive and stateful, unlike MCFBrowser's two-method HTML-return shape: the apply flow loads a posting, polls
for the apply button, selects a CV, and submits. `BaseApplyBrowser` holds the one Playwright code path and every
selector (mycareerfutures skill's Apply flow table). `apply_live.py` runs it against the real site; `apply_fixture.py`
runs the same code with requests routed to the local `tests/fixtures/mcf/apply/` corpus (ARCH-TEST-04), so a
fixture run exercises the same locators a live run does. `get_browser()` selects one by `MCF_MODE` (ARCH-RUN-08),
and `easymcf/services/apply.py` never imports either concrete class.

Each call returns a (state, detail) pair and never raises for an expected page state; `detail` carries the
diagnostic the service records in `application.error_detail`. The service owns the poll loop (REQ-APPLY-07), so
`check_apply_button()` inspects the page once and returns at once. `diagnostics` counts browser actions, so the
oracle can prove, for example, that a load failure made zero button polls.
"""

from __future__ import annotations

import os
import re
from typing import Protocol

from playwright.sync_api import Error as PlaywrightError, Page, TimeoutError as PlaywrightTimeoutError

from ..config import Config
from .singpass_browser import ACCOUNT_MENU_TRIGGER, LOGIN_LOCATORS

APPLY_BUTTON = "button#job-details-apply-button"
APPLY_MESSAGE = "p[data-testid='job-apply-error']"
SIGNED_OUT_MARKER = "[data-cy='navbar-not-logged-in']"  # MCF's own signed-out navbar item, live capture 11.IS.21
RESUME_CARD = "div[data-testid='resume-card']"
RESUME_TITLE = "a.resume-link"
RESUME_RADIO = "input[type='radio']"
ADVANCE_BUTTON = "button#application-details-save-button"
SUBMIT_BUTTON = "button#job-application-review__submit-button"
LOGIN_TO_APPLY = re.compile(r"log ?in to apply", re.I)
ALREADY_APPLIED = re.compile(r"already|applied", re.I)
CLOSED = re.compile(r"closed|no longer", re.I)


LIVE_APPLY_REFUSED = ("live apply refused: MCF_MODE=live also needs APPLY_LIVE_SUBMIT=1, a deliberate human "
                      "choice, because a live apply run submits real job applications")


class LiveApplyNotConfirmed(RuntimeError):
    """MCF_MODE=live without APPLY_LIVE_SUBMIT=1 (11.IS.14): no live browser is ever started."""


class ApplyBrowser(Protocol):
    diagnostics: dict

    def load_posting(self, url_ref: str) -> tuple[str, str | None]: ...  # 'ok' | 'load_failed' | 'signed_out'

    def check_apply_button(self) -> tuple[str, str | None]: ...  # 'found' | 'already_applied' | 'closed' |
    #                                                               'signed_out' | 'pending'

    def click_apply(self) -> None: ...

    def select_cv(self, cv_label: str) -> tuple[str, str | None]: ...  # 'selected' | 'not_found' | 'selector_error'

    def submit_review(self) -> tuple[bool, str | None]: ...

    def close(self) -> None: ...


class BaseApplyBrowser:
    """Playwright lifecycle (the BaseSingpassBrowser pattern) plus the apply-flow steps. Subclasses override
    `_setup_routing` and the timeouts only."""

    page_load_timeout_ms = 15000
    banner_timeout_ms = 10000
    step_timeout_ms = 10000
    confirm_checks = 3          # 11.IS.23: re-open the posting up to this many times after the submit click
    confirm_delay_ms = 3000

    def __init__(self, config: Config, storage_path: str | None = None, init_script: str | None = None):
        self._config = config
        self._storage_path = storage_path
        self._init_script = init_script
        self._playwright = None
        self._browser = None
        self._context = None
        self._page: Page | None = None
        self.diagnostics = {"navigations": 0, "polls": 0, "clicks": 0, "cv_selections": 0, "submits": 0}
        # Opt-in page capture for live markup validation; the pages carry personal details, so only a human-run
        # tier sets it, to a git-ignored directory. Off for every app run.
        self.snapshot_dir: str | None = None
        self._snapshots = 0

    def _snap(self, step: str) -> None:
        if not self.snapshot_dir or self._page is None:
            return
        self._snapshots += 1
        os.makedirs(self.snapshot_dir, exist_ok=True)
        path = os.path.join(self.snapshot_dir, f"{self._snapshots:02d}-{step}.html")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(f"<!-- {self._page.url} -->\n" + self._page.content())

    def _setup_routing(self, page: Page) -> None:
        """No-op for live mode; apply_fixture.py routes requests to its local corpus."""

    def _ensure_started(self) -> None:
        if self._playwright is not None:
            return
        from playwright.sync_api import sync_playwright

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self._config.headless, channel="chromium")
        storage = self._storage_path if self._storage_path and os.path.isfile(self._storage_path) else None
        self._context = self._browser.new_context(storage_state=storage, service_workers="block")
        if self._init_script:
            self._context.add_init_script(script=self._init_script)
        self._context.set_default_timeout(self.step_timeout_ms)
        self._page = self._context.new_page()
        self._setup_routing(self._page)

    def _replace_page(self) -> None:
        """A failed navigation leaves Chromium committing its own chrome-error page after goto() has raised, which
        interrupts the next lead's goto() (11.IS.12). A fresh page in the same context, whose routing and storage
        state it keeps, starts the next lead clean."""
        try:
            self._page.close()
        except PlaywrightError:
            pass
        self._page = self._context.new_page()

    def _signed_in_state(self) -> str | None:
        """The banner's account control: initials when signed in, "Login" once the session has lapsed."""
        page = self._page
        try:
            page.wait_for_selector(ACCOUNT_MENU_TRIGGER, state="visible", timeout=self.banner_timeout_ms)
            return "signed_in"
        except PlaywrightTimeoutError:
            pass
        if page.locator(SIGNED_OUT_MARKER).count():
            return "signed_out"
        for _, build in LOGIN_LOCATORS:
            if build(page).first.is_visible():
                return "signed_out"
        return None

    def load_posting(self, url_ref: str) -> tuple[str, str | None]:
        self._ensure_started()
        self.diagnostics["navigations"] += 1
        self._posting_url = url_ref
        try:
            response = self._page.goto(url_ref, wait_until="domcontentloaded", timeout=self.page_load_timeout_ms)
        except PlaywrightError as exc:
            self._replace_page()
            return "load_failed", f"{type(exc).__name__}: {str(exc).splitlines()[0]}"
        if response is not None and response.status >= 400:
            return "load_failed", f"HTTPError: posting navigation failed with HTTP {response.status}"
        signed_in = self._signed_in_state()
        self._snap(f"posting-{signed_in or 'unknown'}")  # after the banner decision, so the capture shows what it read
        if signed_in == "signed_out":
            return "signed_out", "MCF banner shows Login in place of the account initials"
        return "ok", None

    def check_apply_button(self) -> tuple[str, str | None]:
        self.diagnostics["polls"] += 1
        page = self._page
        message = page.locator(APPLY_MESSAGE)
        if message.count() and message.first.is_visible():
            text = message.first.inner_text().strip()
            if CLOSED.search(text):
                return "closed", text
            if ALREADY_APPLIED.search(text):
                return "already_applied", text
        button = page.locator(APPLY_BUTTON)
        if button.count() and button.first.is_visible():
            if LOGIN_TO_APPLY.search(button.first.inner_text()):
                return "signed_out", "the apply button reads Login to Apply"
            if button.first.is_enabled():
                return "found", None
        if page.get_by_text(LOGIN_TO_APPLY).count():
            return "signed_out", "the posting shows Login to Apply in place of the apply button"
        return "pending", None

    def click_apply(self) -> None:
        self.diagnostics["clicks"] += 1
        self._page.locator(APPLY_BUTTON).first.click()
        try:
            self._page.wait_for_selector(RESUME_CARD, timeout=self.step_timeout_ms)
        except PlaywrightTimeoutError:
            pass  # select_cv reports the missing cards as selector_error
        self._snap("application")

    def resume_options(self) -> list[str]:
        """The resume card titles on the application page, read only. Raises on an unexpected card DOM."""
        page = self._page
        page.wait_for_selector(RESUME_CARD, timeout=self.step_timeout_ms)
        cards = page.locator(RESUME_CARD)
        titles = []
        for index in range(cards.count()):
            title = cards.nth(index).locator(RESUME_TITLE)
            if title.count() == 0:
                raise LookupError(f"resume card {index} has no {RESUME_TITLE} title")
            titles.append(title.first.inner_text().strip())
        return titles

    def select_cv(self, cv_label: str) -> tuple[str, str | None]:
        self.diagnostics["cv_selections"] += 1
        page = self._page
        try:
            titles = self.resume_options()
            match = next((i for i, text in enumerate(titles) if cv_label in text), None)
            if match is None:
                return "not_found", f"no resume option matched CV label {cv_label!r}"
            page.locator(RESUME_CARD).nth(match).locator(RESUME_RADIO).first.check()
            page.locator(ADVANCE_BUTTON).first.click()
            return "selected", None
        except (PlaywrightError, LookupError) as exc:
            return "selector_error", f"{type(exc).__name__}: {str(exc).splitlines()[0]}"

    def submit_review(self) -> tuple[bool, str | None]:
        self.diagnostics["submits"] += 1
        page = self._page
        try:
            page.wait_for_selector(SUBMIT_BUTTON, timeout=self.step_timeout_ms)
        except PlaywrightTimeoutError:
            self._snap("after-advance")
            return False, "final submit failed: the review page's submit button never appeared (multi-step flow)"
        button = page.locator(SUBMIT_BUTTON).first
        if not (button.is_visible() and button.is_enabled()):
            return False, "final submit failed: the submit button is present but not clickable"
        self._snap("review")
        button.click()
        return self._confirm_submitted()

    def _confirm_submitted(self) -> tuple[bool, str | None]:
        """11.IS.23: MCF shows no in-page confirmation right after the click, so success is verified, not inferred.
        The posting's own already-applied message, proven on the live site, is the confirmation. Without it the
        attempt is left for the human to check on MCF (questionnaire_required's manual route)."""
        page = self._page
        for _ in range(self.confirm_checks):
            page.wait_for_timeout(self.confirm_delay_ms)
            page.goto(self._posting_url, wait_until="domcontentloaded", timeout=self.page_load_timeout_ms)
            try:
                page.wait_for_selector(f"{APPLY_MESSAGE}, {APPLY_BUTTON}", timeout=self.step_timeout_ms)
            except PlaywrightTimeoutError:
                continue
            message = page.locator(APPLY_MESSAGE)
            if message.count() and ALREADY_APPLIED.search(message.first.inner_text()) \
                    and not CLOSED.search(message.first.inner_text()):
                self._snap("confirmed")
                return True, None
        self._snap("unconfirmed")
        return False, (f"final submit not confirmed: the posting never showed the already-applied message after "
                       f"{self.confirm_checks} checks; check the application on MCF")

    def close(self) -> None:
        if self._playwright is None:
            return
        try:
            self._context.close()
            self._browser.close()
        finally:
            self._playwright.stop()
            self._playwright = self._browser = self._context = self._page = None


def get_browser(config: Config | None = None, storage_path: str | None = None,
                init_script: str | None = None) -> ApplyBrowser:
    """storage_path is the session's exported storage state; init_script is feature 17's sessionStorage replay."""
    config = config or Config()
    if config.mcf_mode == "live":
        if not config.apply_live_submit:
            raise LiveApplyNotConfirmed(LIVE_APPLY_REFUSED)
        from .apply_live import LiveApplyBrowser

        return LiveApplyBrowser(config, storage_path, init_script)
    from .apply_fixture import FixtureApplyBrowser

    return FixtureApplyBrowser(config, storage_path, init_script)
