#!/usr/bin/env python3
"""Probe 17.PB.01, and 17.PB.02 with --wait-for-approval: reach MCF's real Login -> Singpass QR page and
record what it takes to get there (docs/releases/010/features/010.17-mcf-website-session.md, Design Probes).

  MCF_MODE=live env/bin/python scripts/probe_mcf_singpass.py
  MCF_MODE=live env/bin/python scripts/probe_mcf_singpass.py --wait-for-approval
  MCF_MODE=live env/bin/python scripts/probe_mcf_singpass.py --capture-only

Refuses to run unless MCF_MODE=live is set explicitly for that invocation, the same opt-in ARCH-RUN-08
already requires of the app itself. A human triggers this script deliberately every time, per CLAUDE.md's
boundary against unattended live-site access; it is never invoked by an agent on its own initiative.

Singpass's request_uri is single-use: a first live run captured mcf_singpass_redirect_url only after this
browser had already fetched it and rendered its own QR from it, so a second browser opening the same URL was
rejected with PX-E0013 invalid_request_uri. Capturing without consuming is therefore the default behavior,
with or without --capture-only: this browser intercepts the matching request with context.route() and aborts
it before it reaches Singpass's server, so it never consumes it, then hands the URL to the human as the first
and only consumer. Nothing in this script fetches that redirect for real unless --wait-for-approval's own
branch 2 fallback chooses to.

--wait-for-approval runs the real two-branch workflow, preferring the redirect capture, falling back to the
on-page QR:

  branch 1 (preferred): capture the redirect the same way --capture-only does, print it as a plain clickable
  link for the human to open and approve in their own browser, and retry-check this original browser's own
  MCF cookies and Login control for a sign that its own session changed too.
  branch 2 (fallback): if branch 1 shows no change within the timeout, let this same browser complete a
  fresh Login click for real, reach Singpass's actual QR page, wait for it to render, and have the human scan
  it with their phone instead, the reference spec's already-confirmed working method.

Evidence lands under .dev/logs/<ts>-17.PB-probe/: a screenshot and an HTML dump per navigation step, a
findings.json summary, and a network.jsonl trace of every request and response the navigation made. The
script never submits, applies, or clicks anything outside the Login-to-Singpass-and-back path, and it only
ever writes what the rendered page shows, never a cookie or session value, to its own evidence files. Every
approval step is the user's own action on their own device, never automated, per out-of-scope item 04.
"""

from __future__ import annotations

import argparse
import base64
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time

import cv2
import numpy as np
from playwright.sync_api import Locator, Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

sys.stdout.reconfigure(line_buffering=True)  # stdout is fully buffered when redirected to a log file, not a
# terminal, so without this every print(), including the link the user has to click, sits invisible in the
# buffer until the process exits rather than appearing as this human-triggered run actually progresses.

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_SCRIPTS_DIR)
sys.path.insert(0, _REPO_ROOT)

from easymcf.config import Config  # noqa: E402

MCF_HOME = "https://www.mycareersfuture.gov.sg/"
SINGPASS_HOST_SEARCH_RE = re.compile(r"://[^/]*singpass\.gov\.sg")
QR_LINK_RE = re.compile(r"https://[\w.]*singpass\.gov\.sg/qrlogin\?swk_qr_ref=[\w-]+", re.I)
SINGPASS_AUTH_REQUEST_RE = re.compile(r"https://[\w.]*singpass\.gov\.sg/[^\s\"']*\?[^\s\"']*client_id=[^\s\"']+", re.I)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
# stand-in for the signed-in easyMCF user's own account, per scope item 06's account-confirmation check.
# The real feature reads this from the actual sign-in session, task 17.09; this probe has no login of its
# own, so this constant is the only source of that identity available to it.
EASYMCF_ACCOUNT_EMAIL = "yayfalafels@gmail.com"
MAX_SINGPASS_OPTION_HOPS = 3
QR_RENDER_TIMEOUT_MS = 20000
RETRY_INTERVAL_MS = 5000
QR_REFRESH_INTERVAL_MS = 15000

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

# confirmed against a real authenticated dashboard capture: the user-initials circle sits inside
# <button data-testid="initial-circle-container"> wrapping <div data-testid="user-initials">, itself inside
# a <div data-testid="dropdown-menu"> wrapper, an account-menu trigger the first successful login never
# clicked. 17.PB.02's own dashboard-only capture found nothing beyond a display name; a profile or account
# settings page reached through this menu is the more likely place for a stronger identifier, per how
# government portals usually split "who's logged in" from "your account details".
ACCOUNT_MENU_TRIGGER = "[data-testid='initial-circle-container']"

PROFILE_LINK_LOCATORS = [
    ("role=link[name~=profile]", lambda pg: pg.get_by_role("link", name=re.compile("profile", re.I))),
    ("role=menuitem[name~=profile]", lambda pg: pg.get_by_role("menuitem", name=re.compile("profile", re.I))),
    ("role=link[name~=account]", lambda pg: pg.get_by_role("link", name=re.compile("account", re.I))),
    ("role=menuitem[name~=account]", lambda pg: pg.get_by_role("menuitem", name=re.compile("account", re.I))),
    ("text~=my profile", lambda pg: pg.get_by_text(re.compile("my profile", re.I))),
    ("text~=account settings", lambda pg: pg.get_by_text(re.compile("account settings", re.I))),
]

# id=ndi-qr-canvas first: the real Singpass QR, confirmed against a live page, renders as an inline <svg
# id="ndi-qr-canvas" data-testid="ndi-qr-canvas">, not a <canvas> or a data: <img>. A combined CSS selector
# list would have let DOM order pick a decorative icon <img> ahead of it, which is exactly the bug this
# ordered, explicit-priority list avoids, the same pattern LOGIN_LOCATORS already uses.
QR_ELEMENT_LOCATORS = [
    ("id=ndi-qr-canvas", lambda pg: pg.locator("#ndi-qr-canvas")),
    ("data-testid=ndi-qr-canvas", lambda pg: pg.locator("[data-testid='ndi-qr-canvas']")),
    ("canvas", lambda pg: pg.locator("canvas")),
    ("svg[role=img]", lambda pg: pg.locator("svg[role='img']")),
    ("img[data:image]", lambda pg: pg.locator("img[src^='data:image']")),
]


def _evidence_dir() -> str:
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    path = os.path.join(_REPO_ROOT, ".dev", "logs", f"{ts}-17.PB-probe")
    os.makedirs(path, exist_ok=True)
    return path


def _snapshot(page: Page, out_dir: str, step: str, findings: dict) -> None:
    """Save a screenshot, the full HTML, and the page's plain visible text for one navigation step, and
    record its URL and title. The visible-text file is 17.PB.02's raw material for account-identifying
    detail, a name, a masked identifier, a profile reference: read alongside the HTML by a human rather than
    parsed here, since no field name is assumed in advance."""
    page.screenshot(path=os.path.join(out_dir, f"{step}.png"), full_page=True)
    with open(os.path.join(out_dir, f"{step}.html"), "w", encoding="utf-8") as fh:
        fh.write(page.content())
    try:
        visible_text = page.inner_text("body")
    except Exception:
        visible_text = ""
    with open(os.path.join(out_dir, f"{step}.txt"), "w", encoding="utf-8") as fh:
        fh.write(visible_text)
    findings.setdefault("steps", []).append({"step": step, "url": page.url, "title": page.title()})
    print(f"[STEP] {step}: {page.url}")


def _first_match(page: Page, locators: list[tuple[str, object]]):
    """Try each candidate locator in order and return the first visible match, so the exact MCF/Singpass
    markup does not need to be known ahead of running this probe."""
    for name, locator_fn in locators:
        try:
            candidate = locator_fn(page)
            if candidate.count() > 0 and candidate.first.is_visible():
                return name, candidate.first
        except Exception:
            continue
    return None, None


def _wait_for_render(page: Page, timeout_ms: int = 15000) -> None:
    """Wait for the page's own client-side app to finish its initial render instead of trusting
    domcontentloaded alone. MCF's home page is a client-rendered app that still shows its own loading
    skeleton, literal "Loading" text and no Login control, at domcontentloaded time."""
    try:
        page.wait_for_load_state("networkidle", timeout=timeout_ms)
    except PlaywrightTimeoutError:
        pass


def _wait_for_qr_render(page: Page, timeout_ms: int) -> Locator | None:
    """Wait for the page's own async QR rendering to finish instead of a fixed sleep. Singpass's login page
    loads its bot-detection and biometrics bundles first, fetches a CSRF token, and only then requests the
    QR data, so the network needs to go idle before it actually appears. Returns the matched element itself,
    the fixed, identifiable region the QR renders into, using QR_ELEMENT_LOCATORS' explicit priority order
    rather than just a bool, so the caller can read it directly instead of searching a full-page screenshot
    for a QR pattern, and never picks a same-selector decorative icon ahead of the real QR by DOM-order luck."""
    try:
        page.wait_for_load_state("networkidle", timeout=timeout_ms)
    except PlaywrightTimeoutError:
        pass
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        _, element = _first_match(page, QR_ELEMENT_LOCATORS)
        if element is not None:
            return element
        page.wait_for_timeout(250)
    return None


def _qr_element_image_bytes(qr_element: Locator) -> bytes | None:
    """The QR's own image bytes, read directly from the matched element's HTML rather than a full-page
    screenshot search. An <img src="data:..."> already carries its bitmap as base64 in the DOM, read straight
    from that, no screenshot at all. Anything else, a <canvas> or the real Singpass <svg>, has no such
    attribute, so it gets an element-scoped screenshot, Playwright crops to just that element."""
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
    """Decode the QR from its own element image bytes."""
    image_bytes = _qr_element_image_bytes(qr_element)
    if image_bytes is None:
        return None
    try:
        array = np.frombuffer(image_bytes, dtype=np.uint8)
        image = cv2.imdecode(array, cv2.IMREAD_COLOR)
        if image is None:
            return None
        # a QR rendered small in the DOM, one pixel per module with no quiet zone, reliably fails detection
        # regardless of source, confirmed offline against a freshly generated QR: upscale with nearest-
        # neighbor to keep the modules' hard edges, then pad a white quiet zone the standard requires.
        scale = max(1, 400 // max(image.shape[:2]))
        if scale > 1:
            image = cv2.resize(image, (image.shape[1] * scale, image.shape[0] * scale), interpolation=cv2.INTER_NEAREST)
        border = max(20, min(image.shape[:2]) // 4)
        image = cv2.copyMakeBorder(image, border, border, border, border, cv2.BORDER_CONSTANT, value=(255, 255, 255))
        value, _, _ = cv2.QRCodeDetector().detectAndDecode(image)
        return value or None
    except Exception:
        return None


def _save_qr_popup(qr_element: Locator, out_dir: str) -> str | None:
    """Save the QR's own cropped image to a fixed filename, qr-code.png, overwritten on every refresh rather
    than accumulating one file per step, since the same viewer window is meant to keep showing it."""
    image_bytes = _qr_element_image_bytes(qr_element)
    if image_bytes is None:
        return None
    path = os.path.join(out_dir, "qr-code.png")
    with open(path, "wb") as fh:
        fh.write(image_bytes)
    return path


def _open_image_popup(path: str) -> bool:
    """Best-effort: pop the QR up in the OS's own image viewer. Singpass is a phone app, not a website, so a
    clickable link in a desktop terminal is not itself scannable, the user needs to see the actual QR on
    screen for their phone camera. Tries WSL2's explorer.exe against the Windows-mapped path first, since
    ARCH-RUN environments run under WSL2, then xdg-open for a native Linux desktop. Never fatal either way,
    per CLAUDE.md's boundary against destructive/unverifiable actions: the file is always on disk regardless
    of whether a window actually appears, and explorer.exe's own exit code is not a reliable success signal,
    a known WSL interop quirk, so this only reports whether a launch was attempted, not whether it was seen."""
    explorer = shutil.which("explorer.exe") or next(
        (p for p in ("/mnt/c/WINDOWS/explorer.exe", "/mnt/c/Windows/explorer.exe") if os.path.exists(p)), None)
    wslpath = shutil.which("wslpath")
    if explorer and wslpath:
        try:
            win_path = subprocess.check_output([wslpath, "-w", path], text=True).strip()
            subprocess.Popen([explorer, win_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            pass
    xdg_open = shutil.which("xdg-open")
    if xdg_open:
        try:
            subprocess.Popen([xdg_open, path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            pass
    return False


def _extract_mcf_redirect(network_log: list[dict]) -> str | None:
    """The URL MCF's own redirect sends the browser to, carrying MCF's client id and its PAR request_uri
    reference, read back from the network trace after the fact. Diagnostic only: it confirms the client id
    and the redirect destination, but PX-E0013 already showed this reference does not survive a second use,
    so it is never handed to the user as an approval link once this browser has fetched it for real."""
    for entry in network_log:
        match = SINGPASS_AUTH_REQUEST_RE.search(entry.get("url", ""))
        if match:
            return match.group(0)
    return None


def _find_email(text: str) -> str | None:
    """Flag an email address in captured page text explicitly, confirmed by the user to appear under the
    account-menu dropdown, rather than leaving a human to spot it inside a full-page text dump."""
    match = EMAIL_RE.search(text)
    return match.group(0) if match else None


def _extract_qr_reference(page: Page, network_log: list[dict]) -> str | None:
    """Look for the literal Singpass app-launch URL in the rendered page first, then in the captured
    network trace, since the reference may travel only over the network rather than appear in the DOM."""
    match = QR_LINK_RE.search(page.content())
    if match:
        return match.group(0)
    for entry in network_log:
        match = QR_LINK_RE.search(entry.get("url", ""))
        if match:
            return match.group(0)
    return None


def _reach_qr_page(context, start_page: Page, login_control, out_dir: str, findings: dict, network_log: list[dict], prefix: str) -> Page | None:
    """Click login_control on start_page and follow it through to Singpass's real QR page, waiting for the
    QR to actually render. Returns the page that ended up on Singpass, or None if navigation never reached
    that host. Findings are recorded under f"{prefix}_..." keys so this can run more than once per probe."""
    current = start_page
    try:
        with context.expect_page(timeout=8000) as popup_info:
            login_control.click()
        current = popup_info.value
        findings[f"{prefix}_login_opened"] = "new_tab"
    except PlaywrightTimeoutError:
        findings[f"{prefix}_login_opened"] = "same_tab"
    current.wait_for_load_state("domcontentloaded")
    _snapshot(current, out_dir, f"{prefix}-post-login-click", findings)

    hop = 0
    while not SINGPASS_HOST_SEARCH_RE.search(current.url) and hop < MAX_SINGPASS_OPTION_HOPS:
        _, option_control = _first_match(current, SINGPASS_OPTION_LOCATORS)
        if option_control is None:
            break
        option_control.click()
        current.wait_for_load_state("domcontentloaded")
        hop += 1
        _snapshot(current, out_dir, f"{prefix}-hop-{hop}", findings)
    findings[f"{prefix}_singpass_option_hops"] = hop

    if not SINGPASS_HOST_SEARCH_RE.search(current.url):
        findings[f"{prefix}_reached_url"] = current.url
        return None

    qr_element = _wait_for_qr_render(current, QR_RENDER_TIMEOUT_MS)
    findings[f"{prefix}_qr_render_wait_matched"] = qr_element is not None
    _snapshot(current, out_dir, f"{prefix}-singpass-qr", findings)
    qr_ref = _extract_qr_reference(current, network_log)
    if not qr_ref and qr_element is not None:
        qr_ref = _decode_qr_element(qr_element)
        if qr_ref:
            findings[f"{prefix}_qr_reference_source"] = "decoded_from_element"
    findings[f"{prefix}_qr_reference_found"] = qr_ref is not None
    findings[f"{prefix}_qr_reference"] = qr_ref
    if qr_ref:
        print(f"[PASS] decoded the QR directly from the page:\n  {qr_ref}")
    if qr_element is not None:
        popup_path = _save_qr_popup(qr_element, out_dir)
        if popup_path and _open_image_popup(popup_path):
            findings[f"{prefix}_qr_popup_opened"] = True
            print(f"Opened {popup_path} in your image viewer. Singpass is a phone app: scan it there, not by clicking a link.")
        elif popup_path:
            findings[f"{prefix}_qr_popup_opened"] = False
            print(f"Could not open an image viewer automatically. Open {popup_path} yourself and scan it with your phone.")
    return current


def _write_findings(out_dir: str, findings: dict, network_log: list[dict]) -> None:
    with open(os.path.join(out_dir, "findings.json"), "w", encoding="utf-8") as fh:
        json.dump(findings, fh, indent=2)
    with open(os.path.join(out_dir, "network.jsonl"), "w", encoding="utf-8") as fh:
        for entry in network_log:
            fh.write(json.dumps(entry) + "\n")


def run(wait_for_approval: bool, approval_timeout_s: int, capture_only: bool) -> dict:
    config = Config()
    if config.mcf_mode != "live":
        print("[FAIL] MCF_MODE is not 'live'. Set MCF_MODE=live explicitly to run this probe against the real site.")
        raise SystemExit(1)

    out_dir = _evidence_dir()
    findings: dict = {"mcf_mode": config.mcf_mode, "headless": config.headless, "evidence_dir": out_dir,
                       "result": "incomplete", "capture_only": capture_only, "wait_for_approval": wait_for_approval}
    network_log: list[dict] = []
    captured_redirect: dict[str, str] = {}
    capture_event = threading.Event()

    route_calls: dict[str, int] = {"total": 0, "singpass": 0}

    def _intercept(route):
        """Routed every request, not just matching ones: a compiled Pattern and a Python predicate handed
        directly to context.route() as the matcher both failed to catch a real same-tab top-level navigation
        to the fapi/auth redirect, despite each being individually verified offline, so request selection
        happens here in Python instead of relying on Playwright's own pre-filtering. Non-matches continue
        untouched; the one matching request is captured and aborted before it ever reaches Singpass's server,
        so this browser never consumes the single-use request_uri PX-E0013 showed an already-fetched
        redirect had spent. route_calls counts every invocation, matched or not, so a run's log can show
        whether this handler ran at all rather than only whether it happened to match."""
        route_calls["total"] += 1
        url = route.request.url
        if "singpass.gov.sg" in url:
            route_calls["singpass"] += 1
            print(f"[DEBUG] route saw a singpass URL ({route.request.resource_type}): {url}")
        if SINGPASS_AUTH_REQUEST_RE.search(url):
            print(f"[DEBUG] intercepted: {url}")
            captured_redirect.setdefault("url", url)
            route.abort()
            capture_event.set()
        else:
            route.continue_()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=config.headless, channel="chromium")
        # Playwright's own docs: context.route() does not intercept requests a Service Worker handles first,
        # since the worker's fetch handler runs ahead of Playwright's routing layer, while a passive
        # context.on("request") listener still sees them, since CDP's Network events fire regardless. That
        # gap matches this script's exact symptom and explains why every offline reproduction, none of which
        # registered a service worker, passed while every live run against the real site kept failing.
        context = browser.new_context(service_workers="block")
        context.on("request", lambda req: network_log.append({"type": "request", "url": req.url, "method": req.method}))
        context.on("response", lambda res: network_log.append({"type": "response", "url": res.url, "status": res.status}))
        page = context.new_page()

        try:
            page.goto(MCF_HOME, wait_until="domcontentloaded")
            _wait_for_render(page)
            _snapshot(page, out_dir, "01-mcf-home", findings)

            locator_name, login_control = _first_match(page, LOGIN_LOCATORS)
            findings["login_locator_matched"] = locator_name
            if login_control is None:
                findings["result"] = "failed: no Login control matched any candidate locator"
                print("[FAIL] no Login control found on the MCF home page")
                return findings

            if capture_only:
                context.route("**/*", _intercept)

                current = page
                try:
                    with context.expect_page(timeout=8000) as popup_info:
                        login_control.click()
                    current = popup_info.value
                    findings["login_opened"] = "new_tab"
                except PlaywrightTimeoutError:
                    findings["login_opened"] = "same_tab"

                capture_event.wait(timeout=10)
                if not capture_event.is_set():
                    # the redirect may sit one click further behind a "choose Singpass" option
                    try:
                        current.wait_for_load_state("domcontentloaded", timeout=8000)
                    except PlaywrightTimeoutError:
                        pass
                    _, option_control = _first_match(current, SINGPASS_OPTION_LOCATORS)
                    if option_control is not None:
                        option_control.click()
                        capture_event.wait(timeout=10)

                redirect_url = captured_redirect.get("url")
                findings["mcf_singpass_redirect_url"] = redirect_url
                findings["route_calls"] = dict(route_calls)
                print(f"[DEBUG] route handler ran {route_calls['total']} times total, {route_calls['singpass']} for singpass.gov.sg URLs")

                _snapshot(current, out_dir, "02-capture-only", findings)
                if redirect_url:
                    findings["result"] = "captured, not consumed"
                    print(f"\n[PASS] captured without this browser ever fetching it:\n  {redirect_url}\n")
                    print("That request was aborted before it reached Singpass, so you are the first to open it.")
                    print("Open it yourself now in your own browser and let me know what happens.")
                else:
                    findings["result"] = "failed: redirect never intercepted"
                    print("[FAIL] never intercepted a client_id-bearing Singpass request")
                return findings

            # wait_for_approval: reach Singpass's real QR page directly and wait for the user's own approval
            # there. The redirect-capture path above answers 17.PB.01 as a standalone diagnostic, but a
            # confirmed Chromium/Playwright cross-origin routing gap (context.route() stops seeing requests
            # once the navigation crosses from mycareersfuture.gov.sg to singpass.gov.sg) makes it unfit as
            # the primary mechanism, so this path does not attempt it first.
            qr_page = _reach_qr_page(context, page, login_control, out_dir, findings, network_log, "qr")
            if qr_page is None:
                findings["result"] = "failed: navigation never reached a singpass.gov.sg host"
                print(f"[FAIL] never reached a singpass.gov.sg host, landed on {findings.get('qr_reached_url')}")
                return findings

            print("Scan the QR in the latest qr-singpass-qr screenshot with your phone now.")
            print(f"Waiting up to {approval_timeout_s}s for this browser to see MCF's callback complete.")
            print(f"Singpass's own QR expires faster than that, so qr-singpass-qr-latest.png refreshes every {QR_REFRESH_INTERVAL_MS // 1000}s: rescan that file if the first one expires.")
            callback_seen = False
            stopped_responding = False
            popup_opened = bool(findings.get("qr_qr_popup_opened"))
            deadline = time.monotonic() + approval_timeout_s
            while time.monotonic() < deadline:
                wait_slice_ms = min(QR_REFRESH_INTERVAL_MS, max(1, int((deadline - time.monotonic()) * 1000)))
                try:
                    qr_page.wait_for_url(lambda url: "mycareersfuture.gov.sg" in url, timeout=wait_slice_ms)
                    callback_seen = True
                    break
                except PlaywrightTimeoutError:
                    try:
                        _snapshot(qr_page, out_dir, "qr-singpass-qr-latest", findings)
                        _, latest_qr_element = _first_match(qr_page, QR_ELEMENT_LOCATORS)
                        latest_qr_ref = _decode_qr_element(latest_qr_element) if latest_qr_element is not None else None
                        findings["qr_reference_latest"] = latest_qr_ref
                        if latest_qr_ref:
                            print(f"[INFO] still waiting, refreshed QR decoded:\n  {latest_qr_ref}")
                        else:
                            print("[INFO] still waiting, refreshed qr-singpass-qr-latest.png, could not decode a QR from it")
                        if latest_qr_element is not None:
                            popup_path = _save_qr_popup(latest_qr_element, out_dir)
                            # only re-attempt the launch if nothing ever opened; qr-code.png is overwritten
                            # in place each refresh, so a window that did open keeps showing whatever the OS
                            # viewer last reloaded rather than spawning a new window every cycle.
                            if popup_path and not popup_opened:
                                popup_opened = _open_image_popup(popup_path)
                    except Exception as exc:
                        print(f"[INFO] still waiting, could not refresh the screenshot: {type(exc).__name__}: {exc}")
                except Exception as exc:
                    # a page crash, a closed target, or anything else Playwright doesn't call a plain
                    # timeout: caught here so findings.json still records what happened instead of the
                    # whole run silently dying mid-wait with no evidence.
                    findings["qr_wait_error"] = f"{type(exc).__name__}: {exc}"
                    print(f"[FAIL] the Singpass page stopped responding while waiting: {type(exc).__name__}: {exc}")
                    stopped_responding = True
                    break

            if callback_seen:
                # the same client-rendered-app gap MCF's own home page and Singpass's QR page both hit
                # already: the URL changes back to mycareersfuture.gov.sg before the authenticated page
                # actually finishes rendering, so a snapshot taken immediately risks capturing a loading
                # skeleton instead of 17.PB.02's actual target, the account-identifying page content.
                _wait_for_render(qr_page)
                _snapshot(qr_page, out_dir, "qr-post-approval", findings)
                findings["result"] = "authenticated via the on-page QR"
                print("[PASS] returned to an mycareersfuture.gov.sg page after approval")
                # 17.PB.02's actual target: print the account-identifying page text straight to the console
                # so success means seeing it now, not a pointer to a file to go open separately.
                try:
                    account_text = qr_page.inner_text("body")
                except Exception:
                    account_text = ""
                if account_text.strip():
                    print("\n[PASS] authenticated page text, read this for 17.PB.02's account-identifying fields:")
                    print("-" * 60)
                    print(account_text.strip())
                    print("-" * 60)
                    email = _find_email(account_text)
                    if email:
                        findings["account_email"] = email
                        print(f"[PASS] email found on the dashboard itself: {email}")
                else:
                    print("[FAIL] authenticated page returned no visible text; check qr-post-approval.png/.html by hand")

                # the dashboard's own text only ever showed a display name, but the user confirmed clicking
                # the account-menu trigger reveals the logged-in user's email directly underneath it. Click
                # it, and follow any profile/account link it also reveals, so one real login checks both
                # rather than costing a second one.
                try:
                    menu_trigger = qr_page.locator(ACCOUNT_MENU_TRIGGER)
                    if menu_trigger.count() > 0:
                        menu_trigger.first.click()
                        _wait_for_render(qr_page)
                        _snapshot(qr_page, out_dir, "qr-account-menu", findings)
                        menu_text = qr_page.inner_text("body")
                        print("\n[INFO] clicked the account menu, its revealed text:")
                        print("-" * 60)
                        print(menu_text.strip())
                        print("-" * 60)
                        email = _find_email(menu_text)
                        if email:
                            findings["account_email"] = email
                            print(f"[PASS] email found under the account menu: {email}")

                        _, profile_link = _first_match(qr_page, PROFILE_LINK_LOCATORS)
                        if profile_link is not None:
                            profile_link.click()
                            _wait_for_render(qr_page)
                            _snapshot(qr_page, out_dir, "qr-account-profile", findings)
                            findings["profile_page_url"] = qr_page.url
                            profile_text = qr_page.inner_text("body")
                            print(f"\n[PASS] followed a profile/account link to {qr_page.url}, its page text:")
                            print("-" * 60)
                            print(profile_text.strip())
                            print("-" * 60)
                            email = _find_email(profile_text)
                            if email:
                                findings["account_email"] = email
                                print(f"[PASS] email found on the profile page: {email}")
                        else:
                            print("[INFO] no profile or account settings link found in the opened menu")
                    else:
                        print("[INFO] no account-menu trigger found on this page")
                except Exception as exc:
                    print(f"[INFO] could not explore the account menu: {type(exc).__name__}: {exc}")

                # scope item 06: a first connection requires the user's own explicit confirmation of the
                # displayed MCF account before it becomes usable. EASYMCF_ACCOUNT_EMAIL stands in for the
                # signed-in easyMCF user's own account, which task 17.09's real implementation reads from
                # the actual sign-in session, not a probe constant; this is a live rehearsal of that check,
                # not the feature itself, and it prompts for a real interactive answer rather than assuming one.
                mcf_email = findings.get("account_email")
                if mcf_email:
                    match = mcf_email.lower() == EASYMCF_ACCOUNT_EMAIL.lower()
                    findings["account_confirmation_match"] = match
                    if match:
                        print(f"\n[PASS] MCF account {mcf_email} matches your easyMCF account {EASYMCF_ACCOUNT_EMAIL}.")
                    else:
                        print(f"\n[WARN] MCF account {mcf_email} does not match your easyMCF account {EASYMCF_ACCOUNT_EMAIL}.")
                    try:
                        answer = input(f"Confirm you are MCF user {mcf_email}. If this is not you, answer n and disconnect. [y/N]: ").strip().lower()
                    except EOFError:
                        answer = ""
                    findings["account_confirmed"] = answer == "y"
                    if findings["account_confirmed"]:
                        print("[PASS] account confirmed by the user; connection would become usable per scope item 06.")
                    else:
                        print("[FAIL] account not confirmed; connection stays blocked per scope item 06.")
                else:
                    print("[INFO] no email was found anywhere reachable from the dashboard, so there is nothing to confirm against yet")
            elif stopped_responding:
                findings["result"] = "failed: the Singpass page stopped responding while waiting"
            else:
                findings["result"] = "failed: no approval within the wait window"
                print("[FAIL] no return to mycareersfuture.gov.sg within the wait window")
            return findings
        except Exception as exc:
            # anything not already caught closer to where it happened, a page crash, a closed target, still
            # gets recorded here rather than leaving findings.json's result at its "incomplete" default with
            # no clue why a run stopped mid-way.
            findings["result"] = f"failed: unhandled {type(exc).__name__}: {exc}"
            print(f"[FAIL] unhandled {type(exc).__name__}: {exc}")
            raise
        finally:
            _write_findings(out_dir, findings, network_log)
            browser.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--wait-for-approval", action="store_true",
                         help="run both branches for real: capture-and-retry-check first, on-page QR as the fallback (probe 17.PB.02)")
    parser.add_argument("--approval-timeout-s", type=int, default=900,
                         help="seconds to wait per branch, default 900 (15 minutes), generous since this is a human-paced interactive wait")
    parser.add_argument("--capture-only", action="store_true",
                         help="isolated diagnostic: intercept and abort the redirect, hand it to the user, and stop, with no retry loop or fallback")
    args = parser.parse_args()
    if args.capture_only and args.wait_for_approval:
        print("[FAIL] --capture-only and --wait-for-approval are mutually exclusive: --wait-for-approval already includes the capture-only branch.")
        return 1

    # capture-without-consuming is the default behavior, not something you have to remember to flag: the
    # redirect is single-use (PX-E0013), so nothing should fetch it for real unless --wait-for-approval's own
    # branch 2 fallback deliberately chooses to.
    capture_only = args.capture_only or not args.wait_for_approval

    findings = run(args.wait_for_approval, args.approval_timeout_s, capture_only)
    print(f"evidence written to {findings['evidence_dir']}")
    ok_results = {"reached the Singpass QR page", "captured, not consumed",
                  "authenticated via branch 1, the captured redirect", "authenticated via branch 2, the on-page QR"}
    return 0 if findings.get("result") in ok_results else 1


if __name__ == "__main__":
    raise SystemExit(main())
