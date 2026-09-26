#!/usr/bin/env python3
"""12.EL.03 — replay tests/frontend/checks/*.json UI-check configs standalone,
outside pytest, against a real `python -m easymcf` process this script spawns
itself via tests/_browser_support.py's spawn_app/terminate_app (unmodified).
Assertions follow ARCH-TEST-05's convention exactly: rendered text,
visibility, or attribute value — never a JS-internals check.

Two modes:

    # (a) ad hoc — open one route, print one selector's text + visibility
    python scripts/ui_tester.py /leads '[data-testid="leads-tab-pipeline"]'

    # (b) case-replay — run every check in a file (or one named check)
    python scripts/ui_tester.py --case tests/frontend/checks/selftest_ui_tester.json
    python scripts/ui_tester.py --case tests/frontend/checks/selftest_ui_tester.json \\
        --name "selftest — leads column heading renders" --api-mode mocked
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time

from urllib.parse import urlparse

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_SCRIPTS_DIR)
sys.path.insert(0, _SCRIPTS_DIR)
sys.path.insert(0, _REPO_ROOT)

import _val_log  # noqa: E402
from initdb import apply_schema  # noqa: E402
from render_seed import PUBLIC_DEFAULTS  # noqa: E402
from resetdb import apply_seed  # noqa: E402
from tests._browser_support import spawn_app, terminate_app  # noqa: E402


def _slug(name: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-")


def _run_actions(page, actions: list[dict]) -> None:
    for step in actions:
        op = step["op"]
        locator = page.locator(step["selector"])
        if op == "wait_for":
            locator.wait_for(state="visible", timeout=step.get("timeout_ms", 10_000))
        elif op == "upload":
            locator.wait_for(state="attached", timeout=step.get("timeout_ms", 10_000))
            locator.set_input_files(os.path.join(_REPO_ROOT, step["path"]))
        elif op == "click":
            locator.click()
        elif op == "fill":
            locator.fill(step["value"])
        else:
            raise ValueError(f"unknown action op: {op!r}")


def _check_expect(page, expect: dict) -> tuple[bool, object, object]:
    op = expect["op"]
    if op == "url_path_equals":
        actual = urlparse(page.url).path
        return actual == expect["value"], expect["value"], actual
    locator = page.locator(expect["selector"])
    if op == "visible":
        value = expect.get("value", True)
        actual = locator.is_visible()
        return actual == value, value, actual
    if op == "text_equals":
        actual = locator.inner_text()
        return actual == expect["value"], expect["value"], actual
    if op == "attribute_equals":
        actual = locator.get_attribute(expect["attribute"])
        return actual == expect["value"], expect["value"], actual
    if op == "count_equals":
        actual = locator.count()
        return actual == expect["value"], expect["value"], actual
    raise ValueError(f"unknown expect op: {op!r}")


def _run_check(browser, base_url: str, check: dict, label: str, log_path: str) -> str:
    case_name = check["name"]
    start = time.monotonic()
    context = browser.new_context()
    page = context.new_page()
    page_errors: list[str] = []
    page.on("pageerror", lambda exc: page_errors.append(str(exc)))

    outcome, expected, actual, detail = "PASS", None, None, None
    try:
        if check.get("as_user"):
            with open(os.path.join(_REPO_ROOT, "tests", "support", "users.json"), encoding="utf-8") as handle:
                creds = json.load(handle).get(check["as_user"])
            if creds is None:
                raise RuntimeError(f"no user named {check['as_user']!r} in tests/support/users.json")
            signed = context.request.post(base_url + "/api/v1/auth/signin", data=creds)
            if signed.status != 200:
                raise RuntimeError(f"sign-in as {check['as_user']} returned {signed.status}")
        page.goto(base_url + check["route"], timeout=10_000)
        _run_actions(page, check.get("actions", []))
        if page_errors:
            raise RuntimeError(f"page error: {page_errors[0]}")
        for expect in check.get("expect", []):
            matched, expected, actual = _check_expect(page, expect)
            if not matched:
                outcome = "FAIL"
                break
    except (PlaywrightTimeoutError, RuntimeError) as exc:
        outcome, expected, actual, detail = "ERROR", None, None, str(exc)

    duration_ms = int((time.monotonic() - start) * 1000)
    screenshot = None
    if outcome != "PASS":
        screenshot = os.path.join(
            _REPO_ROOT, ".dev", "logs", "screenshots", f"{time.strftime('%Y%m%d%H%M%S')}-{label}-{_slug(case_name)}.png"
        )
        os.makedirs(os.path.dirname(screenshot), exist_ok=True)
        page.screenshot(path=screenshot)
    context.close()

    if outcome == "PASS":
        print(f"[PASS] {case_name}")
    else:
        print(f"[FAIL] {case_name} — {detail or f'expected {expected!r}, got {actual!r}'}", file=sys.stderr)

    _val_log.write_record(log_path, "ui_tester", case_name, outcome, duration_ms, expected, actual, detail, screenshot)
    return outcome


def _register_api_mock(page, fixtures_path: str | None) -> None:
    """ARCH-TEST-09's interception pattern, applied standalone. No fixtures
    file yet exists (07.EL.30/.32 — env-status makes no /api call), so an
    unmocked /api/** request falls through to the real backend (route.
    continue_()) rather than aborting — a stricter "fail on any unmocked
    call" behavior is deferred until milestone 09 ships a real
    tests/fixtures/api/*.json this script can point at (known limitation,
    010.12 Design section, --api-mode mocked self-test entry)."""
    fixtures: dict[str, dict] = {}
    if fixtures_path:
        with open(fixtures_path, "r", encoding="utf-8") as f:
            fixtures = json.load(f)

    def _handler(route):
        request_path = route.request.url.split("?")[0]
        entry = None
        for key, value in fixtures.items():
            if request_path.endswith(key):
                entry = value
                break
        if entry is None:
            route.continue_()
        else:
            route.fulfill(status=entry.get("status", 200), json=entry.get("body"))

    page.route("**/api/**", _handler)


def _case_batch(case_path: str, name: str | None, api_mode: str, api_fixtures: str | None, label: str) -> int:
    with open(case_path, "r", encoding="utf-8") as f:
        checks = json.load(f)
    if name is not None:
        checks = [c for c in checks if c["name"] == name]
        if not checks:
            print(f"[FAIL] no check named {name!r} in {case_path}", file=sys.stderr)
            return 1

    if api_mode == "mocked" and not api_fixtures:
        api_fixtures = os.path.join(_REPO_ROOT, "tests", "fixtures", "api", "auth.json")  # auth/me answers without a session
    db_dir = tempfile.mkdtemp(prefix="easymcf-ui-tester-")
    db_path = os.path.join(db_dir, "easymcf.db")
    apply_schema(db_path)
    apply_seed(db_path, PUBLIC_DEFAULTS)
    proc, base_url = spawn_app(db_path)
    log_path = _val_log.log_path("ui_tester", label)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=os.environ.get("HEADLESS", "1") != "0")
            try:
                exit_code = 0
                for check in checks:
                    if api_mode == "mocked":
                        page = browser.new_page()
                        _register_api_mock(page, api_fixtures)
                        page.close()  # wiring-only smoke: real per-check pages are opened in _run_check
                    outcome = _run_check(browser, base_url, check, label, log_path)
                    if outcome != "PASS":
                        exit_code = 1
                return exit_code
            finally:
                browser.close()
    finally:
        terminate_app(proc)


def _ad_hoc(route: str, selector: str) -> int:
    db_dir = tempfile.mkdtemp(prefix="easymcf-ui-tester-")
    db_path = os.path.join(db_dir, "easymcf.db")
    apply_schema(db_path)
    apply_seed(db_path, PUBLIC_DEFAULTS)
    proc, base_url = spawn_app(db_path)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=os.environ.get("HEADLESS", "1") != "0")
            page = browser.new_page()
            page.goto(base_url + route, timeout=10_000)
            locator = page.locator(selector)
            print(f"visible={locator.is_visible()}")
            if locator.count() and locator.is_visible():
                print(f"text={locator.inner_text()!r}")
            browser.close()
        return 0
    finally:
        terminate_app(proc)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--case", help="path to a tests/frontend/checks/*.json file")
    parser.add_argument("--name", default=None, help="run only this check (default: every check in --case's file)")
    parser.add_argument("--api-mode", choices=["real", "mocked"], default="real")
    parser.add_argument("--api-fixtures", default=None, help="tests/fixtures/api/*.json, --api-mode mocked only")
    parser.add_argument("--label", default="adhoc", help="caller's feature/task id for the log filename, e.g. 09.09")
    parser.add_argument("route", nargs="?", help="ad hoc mode: route to open")
    parser.add_argument("selector", nargs="?", help="ad hoc mode: selector to inspect")
    args = parser.parse_args()

    if args.case:
        return _case_batch(args.case, args.name, args.api_mode, args.api_fixtures, args.label)

    if not args.route or not args.selector:
        parser.error("ad hoc mode requires ROUTE and SELECTOR")
    return _ad_hoc(args.route, args.selector)


if __name__ == "__main__":
    raise SystemExit(main())
