"""ARCH-BOT-02 / ARCH-RUN-04 — Playwright sync-API implementation of MCFBrowser, one
browser context per run. Never run automatically (CLAUDE.md's live-site boundary,
REQ-DEV-03) — selected only when `MCF_MODE=live`, a human's own deliberate choice.

No MCF session is loaded or read; search needs none (mycareerfutures skill). `search_page`
paginates the mycareerfutures skill's search URL scheme and waits for either a result card
or the empty-results marker before reading the page's HTML (playwright skill's explicit-wait
pattern, no fixed sleeps). `detail_page` waits on the open/closed marker the same way.
`config.search_page_delay_s` paces page loads against the same host (webscraping skill's
"be a polite scraper" note) — fixture-mode tests set it to 0.
"""

from __future__ import annotations

import time
from urllib.parse import quote

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright

from ..config import Config

MCF_HOME = "https://www.mycareersfuture.gov.sg"
CARD_SELECTOR = "[id^='job-card-']"
EMPTY_RESULTS_SELECTOR = "[data-testid='no-search-result']"
DETAIL_MARKER_SELECTOR = "[data-testid='job-details-info-job-expiry-date']"  # confirmed real markup, 10.IS.15
PAGE_LOAD_TIMEOUT_MS = 15000


class LiveMCFBrowser:
    def __init__(self, config: Config):
        self._config = config
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None

    def _ensure_started(self) -> None:
        if self._playwright is not None:
            return
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self._config.headless, channel="chromium")
        self._context = self._browser.new_context()
        self._page = self._context.new_page()

    def _wait_for_page_settled(self) -> None:
        try:
            self._page.wait_for_selector(
                f"{CARD_SELECTOR}, {EMPTY_RESULTS_SELECTOR}", timeout=PAGE_LOAD_TIMEOUT_MS
            )
        except PlaywrightTimeoutError:
            pass  # neither marker rendered in time; parse_cards sees zero cards, same as a genuinely empty page

    def search_page(self, keyword: str, min_salary: int | None, page: int) -> str:
        self._ensure_started()
        if self._config.search_page_delay_s:
            time.sleep(self._config.search_page_delay_s)
        url = (
            f"{MCF_HOME}/search?search={quote(keyword)}&employmentType=Full%20Time"
            f"&sort=new_posting_date&page={page}"
        )
        if min_salary:
            url += f"&salary={min_salary}"
        self._page.goto(url, wait_until="domcontentloaded")
        self._wait_for_page_settled()
        return self._page.content()

    def detail_page(self, url_ref: str) -> str:
        self._ensure_started()
        if self._config.search_page_delay_s:
            time.sleep(self._config.search_page_delay_s)
        self._page.goto(url_ref, wait_until="domcontentloaded")
        try:
            self._page.wait_for_selector(DETAIL_MARKER_SELECTOR, timeout=PAGE_LOAD_TIMEOUT_MS)
        except PlaywrightTimeoutError:
            pass  # parse_detail raises its own ParseError when the marker never rendered
        return self._page.content()

    def close(self) -> None:
        if self._playwright is None:
            return
        self._context.close()
        self._browser.close()
        self._playwright.stop()
        self._playwright = self._browser = self._context = self._page = None
