"""ARCH-BOT-02 — the SingpassBrowser seam, parallel to MCFBrowser.

One interface, `fixture.py`/`live.py` behind it, selected by `MCF_MODE` (`ARCH-RUN-08`). The locator lists, waits,
and decode pipeline below are lifted directly from `scripts/probe_mcf_singpass.py`, validated against the real
site across the probe's own live runs (17.PB.01, 17.PB.02) before being promoted into this production seam.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import time
from collections.abc import Callable
from typing import Protocol
from urllib.parse import urlparse

import cv2
import numpy as np
from playwright.sync_api import Locator, Page, TimeoutError as PlaywrightTimeoutError

from ..config import Config

logger = logging.getLogger(__name__)

MCF_HOME = "https://www.mycareersfuture.gov.sg/"
MCF_HOST = "mycareersfuture.gov.sg"
SINGPASS_HOST_SEARCH_RE = re.compile(r"://[^/]*singpass\.gov\.sg")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
MAX_SINGPASS_OPTION_HOPS = 3
QR_RENDER_TIMEOUT_MS = 45000  # 17.IS.05..11: a busy host's real Chromium launch/navigation observed at 40s+
AUTHENTICATED_WAIT_MS = 900000
QR_REFRESH_INTERVAL_MS = 15000
CALLBACK_POLL_MS = 250
OPTION_HOP_TIMEOUT_MS = 2000

LOGIN_LOCATORS = [
    ("role=link[name~=login]", lambda pg: pg.get_by_role("link", name=re.compile("log ?in", re.I))),
    ("role=button[name~=login]", lambda pg: pg.get_by_role("button", name=re.compile("log ?in", re.I))),
    ("text~=login", lambda pg: pg.get_by_text(re.compile(r"^\s*log ?in\s*$", re.I))),
]

SINGPASS_OPTION_LOCATORS = [
    ("role=link[name~=singpass]", lambda pg: pg.get_by_role("link", name=re.compile("singpass", re.I))),
    ("role=button[name~=singpass]", lambda pg: pg.get_by_role("button", name=re.compile("singpass", re.I))),
    ("text~=singpass", lambda pg: pg.get_by_text(re.compile("singpass", re.I))),
]

# id=ndi-qr-canvas first: the real Singpass QR renders as an inline <svg id="ndi-qr-canvas">, confirmed against
# a live page (17.PB.01). A combined CSS selector list let DOM order pick a decorative icon ahead of it; this
# explicit-priority list is the fix, the same pattern LOGIN_LOCATORS already uses.
QR_ELEMENT_LOCATORS = [
    ("id=ndi-qr-canvas", lambda pg: pg.locator("#ndi-qr-canvas")),
    ("data-testid=ndi-qr-canvas", lambda pg: pg.locator("[data-testid='ndi-qr-canvas']")),
    ("canvas", lambda pg: pg.locator("canvas")),
    ("svg[role=img]", lambda pg: pg.locator("svg[role='img']")),
    ("img[data:image]", lambda pg: pg.locator("img[src^='data:image']")),
]

REFRESH_QR_LOCATORS = [
    ("role=button[name~=refresh qr]", lambda pg: pg.get_by_role("button", name=re.compile(r"refresh.*qr", re.I))),
    ("text~=refresh qr", lambda pg: pg.get_by_text(re.compile(r"refresh.*qr", re.I))),
]

# the account-menu trigger: <button data-testid="initial-circle-container">, confirmed against a real
# authenticated dashboard (17.PB.02) — the dashboard's own visible text exposes only a display name.
ACCOUNT_MENU_TRIGGER = "[data-testid='initial-circle-container']"

PROFILE_LINK_LOCATORS = [
    ("role=link[name~=profile]", lambda pg: pg.get_by_role("link", name=re.compile("profile", re.I))),
    ("role=menuitem[name~=profile]", lambda pg: pg.get_by_role("menuitem", name=re.compile("profile", re.I))),
    ("role=link[name~=account]", lambda pg: pg.get_by_role("link", name=re.compile("account", re.I))),
    ("role=menuitem[name~=account]", lambda pg: pg.get_by_role("menuitem", name=re.compile("account", re.I))),
    ("text~=my profile", lambda pg: pg.get_by_text(re.compile("my profile", re.I))),
    ("text~=account settings", lambda pg: pg.get_by_text(re.compile("account settings", re.I))),
]

LOGOUT_LOCATORS = [
    ("role=button[name~=logout]", lambda pg: pg.get_by_role("button", name=re.compile(r"log ?out|sign ?out", re.I))),
    ("role=link[name~=logout]", lambda pg: pg.get_by_role("link", name=re.compile(r"log ?out|sign ?out", re.I))),
    ("text~=logout", lambda pg: pg.get_by_text(re.compile(r"^\s*(log ?out|sign ?out)\s*$", re.I))),
]


class SingpassBrowser(Protocol):
    def open_qr_login(self) -> None: ...
    def read_qr(self) -> tuple[bytes, str | None]: ...
    def wait_for_authenticated(self, on_qr_refresh: Callable[[bytes, str | None], None] | None = None) -> None: ...
    def read_account_email(self) -> str: ...
    def export_storage_state(self, user_id: int) -> str: ...
    def logout(self) -> None: ...
    def close(self) -> None: ...


def _first_match(page: Page, locators, timeout: int = 5000):
    """The first locator in an explicit-priority list that actually matches, or a PlaywrightTimeoutError."""
    last_exc = None
    for name, build in locators:
        try:
            locator = build(page)
            locator.first.wait_for(state="visible", timeout=timeout)
            return name, locator
        except PlaywrightTimeoutError as exc:
            last_exc = exc
            continue
    raise last_exc or PlaywrightTimeoutError("no locator in the list matched")


def _wait_for_render(page: Page) -> None:
    """A client-rendered page shows a loading skeleton at domcontentloaded; wait for the network to settle
    before reading anything (17.PB.01's finding, hit on both the MCF home page and the Singpass QR page)."""
    try:
        page.wait_for_load_state("networkidle", timeout=QR_RENDER_TIMEOUT_MS)
    except PlaywrightTimeoutError:
        pass


def _wait_for_qr_render(page: Page, timeout: int = QR_RENDER_TIMEOUT_MS) -> Locator | None:
    try:
        _, element = _first_match(page, QR_ELEMENT_LOCATORS, timeout=timeout)
        return element.first
    except PlaywrightTimeoutError:
        return None


def _wait_for_visible_email(page: Page, timeout: int) -> str | None:
    deadline = time.monotonic() + timeout / 1000
    while time.monotonic() < deadline:
        match = EMAIL_RE.search(page.locator("body").inner_text())
        if match:
            return match.group(0)
        page.wait_for_timeout(250)
    return None


def _qr_element_image_bytes(qr_element: Locator) -> bytes | None:
    """An <img src="data:..."> already carries its bitmap as base64 in the DOM, read straight from that.
    Anything else, a <canvas> or the real Singpass <svg>, gets an element-scoped screenshot instead."""
    try:
        tag = qr_element.evaluate("el => el.tagName.toLowerCase()")
        if tag == "img":
            src = qr_element.get_attribute("src") or ""
            if src.startswith("data:image"):
                _, _, b64data = src.partition(",")
                return base64.b64decode(b64data)
        return qr_element.screenshot()
    except Exception:
        return None


def _decode_qr_element(qr_element: Locator) -> str | None:
    image_bytes = _qr_element_image_bytes(qr_element)
    if image_bytes is None:
        return None
    try:
        array = np.frombuffer(image_bytes, dtype=np.uint8)
        image = cv2.imdecode(array, cv2.IMREAD_COLOR)
        if image is None:
            return None
        # a QR rendered small with no quiet zone reliably fails detection; upscale with nearest-neighbor to
        # keep the modules' hard edges, then pad a white quiet zone the standard requires (confirmed offline).
        scale = max(1, 400 // max(image.shape[:2]))
        if scale > 1:
            image = cv2.resize(image, (image.shape[1] * scale, image.shape[0] * scale), interpolation=cv2.INTER_NEAREST)
        border = max(20, min(image.shape[:2]) // 4)
        image = cv2.copyMakeBorder(image, border, border, border, border, cv2.BORDER_CONSTANT, value=(255, 255, 255))
        value, _, _ = cv2.QRCodeDetector().detectAndDecode(image)
        return value or None
    except Exception:
        return None


class BaseSingpassBrowser:
    """Shared Playwright lifecycle and navigation logic. `fixture.py` and `live.py` differ only in whether
    `_setup_routing` intercepts requests before the first navigation (ARCH-TEST-04's pattern, one layer over)."""

    def __init__(self, config: Config):
        self._config = config
        self._playwright = None
        self._browser = None
        self._context = None
        self._page: Page | None = None
        self._origin_page: Page | None = None
        self._login_popup: Page | None = None

    def _setup_routing(self, page: Page) -> None:
        """No-op for live mode; fixture.py overrides this to route requests to its local corpus."""

    def _ensure_started(self) -> None:
        if self._playwright is not None:
            return
        from playwright.sync_api import sync_playwright

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self._config.headless, channel="chromium")
        self._context = self._browser.new_context(service_workers="block")
        self._page = self._context.new_page()
        self._setup_routing(self._page)

    def open_qr_login(self) -> None:
        self._ensure_started()
        page = self._page
        self._origin_page = page
        self._login_popup = None
        page.goto(MCF_HOME, wait_until="domcontentloaded")
        _wait_for_render(page)
        logger.warning("MCF_DIAG home rendered url=%s", page.url)
        _, login_control = _first_match(page, LOGIN_LOCATORS)
        try:
            with self._context.expect_page(timeout=8000) as popup_info:
                login_control.first.click()
            page = popup_info.value
            self._page = page
            self._login_popup = page
            logger.warning("MCF_DIAG login popup adopted url=%s", page.url)
        except PlaywrightTimeoutError:
            logger.warning("MCF_DIAG login continued in current page url=%s", page.url)
            pass
        page.wait_for_load_state("domcontentloaded")
        for _ in range(MAX_SINGPASS_OPTION_HOPS):
            if SINGPASS_HOST_SEARCH_RE.search(page.url or ""):
                break
            _wait_for_render(page)
            try:
                _, option_control = _first_match(page, SINGPASS_OPTION_LOCATORS, timeout=OPTION_HOP_TIMEOUT_MS)
            except PlaywrightTimeoutError:
                break
            option_control.first.click()
            page.wait_for_load_state("domcontentloaded")
        if not SINGPASS_HOST_SEARCH_RE.search(page.url or ""):
            raise RuntimeError("MCF Login did not reach the Singpass QR page")
        logger.warning("MCF_DIAG Singpass QR page reached url=%s", page.url)

    def read_qr(self) -> tuple[bytes, str | None]:
        element = _wait_for_qr_render(self._page)
        if element is None:
            raise RuntimeError("the Singpass QR did not render")
        image_bytes = _qr_element_image_bytes(element)
        if image_bytes is None:
            raise RuntimeError("could not read the QR's own image bytes")
        return image_bytes, _decode_qr_element(element)

    def _find_authenticated_page(self) -> Page | None:
        for page in self._context.pages:
            if MCF_HOST not in (page.url or ""):
                continue
            if "/dashboard/" in page.url:
                return page
            try:
                if page.locator(ACCOUNT_MENU_TRIGGER).first.is_visible():
                    return page
            except Exception:
                continue
        return None

    def _refresh_expired_qr(self) -> tuple[bytes, str | None] | None:
        authenticated_page = self._find_authenticated_page()
        if authenticated_page is not None:
            self._page = authenticated_page
            return None
        try:
            _, refresh_control = _first_match(self._page, REFRESH_QR_LOCATORS, timeout=250)
            refresh_control.first.click()
            deadline = time.monotonic() + QR_RENDER_TIMEOUT_MS / 1000
            while time.monotonic() < deadline:
                authenticated_page = self._find_authenticated_page()
                if authenticated_page is not None:
                    self._page = authenticated_page
                    return None
                element = _wait_for_qr_render(self._page, timeout=250)
                if element is not None:
                    image_bytes = _qr_element_image_bytes(element)
                    qr_link = _decode_qr_element(element)
                    if image_bytes is not None and qr_link:
                        return image_bytes, qr_link
                self._page.wait_for_timeout(250)
            return None
        except PlaywrightTimeoutError:
            return None

    def wait_for_authenticated(self, on_qr_refresh: Callable[[bytes, str | None], None] | None = None) -> None:
        if not SINGPASS_HOST_SEARCH_RE.search(self._page.url or ""):
            raise RuntimeError("authentication wait started before reaching Singpass")
        deadline = time.monotonic() + AUTHENTICATED_WAIT_MS / 1000
        next_qr_refresh = time.monotonic() + QR_REFRESH_INTERVAL_MS / 1000
        while True:
            authenticated_page = self._find_authenticated_page()
            if authenticated_page is not None:
                self._page = authenticated_page
                logger.warning("MCF_DIAG authenticated context page found url=%s", self._page.url)
                return
            if self._login_popup is not None and self._login_popup.is_closed() and self._origin_page is not None:
                logger.warning("MCF_DIAG login popup closed; reloading opener url=%s", self._origin_page.url)
                self._origin_page.reload(wait_until="domcontentloaded")
                self._page = self._origin_page
                self._login_popup = None
                continue
            remaining_ms = max(1, int((deadline - time.monotonic()) * 1000))
            try:
                if SINGPASS_HOST_SEARCH_RE.search(self._page.url or ""):
                    self._page.wait_for_url(
                        lambda url: MCF_HOST in url,
                        timeout=min(CALLBACK_POLL_MS, remaining_ms),
                    )
                    break
                self._page.wait_for_timeout(min(CALLBACK_POLL_MS, remaining_ms))
            except PlaywrightTimeoutError:
                if time.monotonic() >= deadline:
                    raise
                if on_qr_refresh is not None and time.monotonic() >= next_qr_refresh:
                    try:
                        qr_bytes, qr_link = self.read_qr()
                        if qr_link:
                            on_qr_refresh(qr_bytes, qr_link)
                        else:
                            refreshed = self._refresh_expired_qr()
                            if refreshed is not None:
                                on_qr_refresh(*refreshed)
                    except RuntimeError:
                        pass
                    next_qr_refresh = time.monotonic() + QR_REFRESH_INTERVAL_MS / 1000
        logger.warning("MCF_DIAG authenticated callback URL reached url=%s", self._page.url)

    def read_account_email(self) -> str:
        page = self._page
        logger.warning("MCF_DIAG account extraction started url=%s", page.url)
        menu_trigger = page.locator(ACCOUNT_MENU_TRIGGER).first
        menu_trigger.wait_for(state="visible", timeout=10000)
        logger.warning("MCF_DIAG account menu trigger visible")
        menu_trigger.click()
        logger.warning("MCF_DIAG account menu trigger clicked")
        email = _wait_for_visible_email(page, timeout=15000)
        if email:
            logger.warning("MCF_DIAG account email found in opened menu")
            return email
        logger.warning("MCF_DIAG account email absent from menu; trying profile link")
        _, profile_link = _first_match(page, PROFILE_LINK_LOCATORS)
        logger.warning("MCF_DIAG profile link found")
        profile_link.first.click()
        page.wait_for_load_state("domcontentloaded")
        email = _wait_for_visible_email(page, timeout=20000)
        if not email:
            raise RuntimeError("no account email found on the profile page")
        logger.warning("MCF_DIAG account email found on profile page")
        return email

    def export_storage_state(self, user_id: int) -> str:
        secrets_dir = self._config.secrets_dir
        os.makedirs(secrets_dir, exist_ok=True)
        os.chmod(secrets_dir, 0o700)
        filename = f"mcf_session_{user_id}.json"
        path = os.path.join(secrets_dir, filename)
        self._context.storage_state(path=path, indexed_db=True)
        os.chmod(path, 0o600)
        session_storage = {}
        for page in self._context.pages:
            parsed = urlparse(page.url or "")
            if parsed.hostname != MCF_HOST and not (parsed.hostname or "").endswith("." + MCF_HOST):
                continue
            origin = f"{parsed.scheme}://{parsed.netloc}"
            session_storage[origin] = page.evaluate("Object.fromEntries(Object.entries(sessionStorage))")
        sidecar_path = os.path.join(secrets_dir, f"mcf_session_{user_id}.session.json")
        with open(sidecar_path, "w", encoding="utf-8") as handle:
            json.dump(session_storage, handle)
        os.chmod(sidecar_path, 0o600)
        logger.warning("MCF_DIAG exported browser state session_origins=%s", len(session_storage))
        return filename

    def logout(self) -> None:
        page = self._page
        page.locator(ACCOUNT_MENU_TRIGGER).first.click()
        _, logout_control = _first_match(page, LOGOUT_LOCATORS, timeout=2000)
        logout_control.first.click()
        page.wait_for_load_state("domcontentloaded")

    def close(self) -> None:
        if self._playwright is None:
            return
        self._context.close()
        self._browser.close()
        self._playwright.stop()
        self._playwright = self._browser = self._context = self._page = self._origin_page = self._login_popup = None


def get_browser(config: Config | None = None) -> SingpassBrowser:
    config = config or Config()
    if config.mcf_mode == "live":
        from .singpass_live import LiveSingpassBrowser

        return LiveSingpassBrowser(config)
    from .singpass_fixture import FixtureSingpassBrowser

    return FixtureSingpassBrowser(config)
