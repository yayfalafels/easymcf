#!/usr/bin/env python3
"""ENV-SCRIPT-04 (STRAT-SILO-03) — replay `tests/backend/cases/*.json` cases
with `requests` against an already-running instance, instead of the Flask
test client. A diagnostic convenience, never part of the automated tier-1
loop (`pytest -m backend` against the test client is).

Case file shape (one JSON array per resource, e.g. tests/backend/cases/health.json):

    [
      {
        "name": "health check returns ok",
        "method": "GET",
        "path": "/api/v1/health",
        "expected_status": 200,
        "expected_body": {"status": "ok"}
      }
    ]

Three modes:

    # (a) ad hoc — poke one endpoint while `python -m easymcf` is up
    python scripts/api_tester.py GET /api/v1/health
    python scripts/api_tester.py POST /api/v1/lead '{"post_id": 1, "track_id": 1}'

    # (b) single-case replay — reproduce a specific failing case against a live process
    python scripts/api_tester.py --case tests/backend/cases/health.json --name "health check returns ok"

    # (c) batch replay (12.CK.01) — run every case in a file, PASS/FAIL/ERROR verdict
    # per case, plus a structured .dev/logs/*.log record (12.CK.05)
    python scripts/api_tester.py --case tests/backend/cases/health.json --label 09.09
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

import requests
from dotenv import load_dotenv

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_SCRIPTS_DIR)
sys.path.insert(0, _SCRIPTS_DIR)
sys.path.insert(0, _REPO_ROOT)
load_dotenv()  # before Config() is built — ENV-CFG-03/07.02.03

import _val_log  # noqa: E402
from easymcf.config import Config  # noqa: E402


def _base_url() -> str:
    return f"http://127.0.0.1:{Config().port}"


def _classify_response(case: dict, resp) -> tuple[str, object, object, str | None]:
    """PASS/FAIL/ERROR for one response against one case's expectations
    (12.CK.02). ERROR is reserved for "the response can't be interpreted at
    all" (body isn't JSON when expected_body was supplied) — a value that
    parsed fine and simply didn't match is always FAIL, never ERROR."""
    expected_status = case.get("expected_status")
    expected_body = case.get("expected_body")

    actual_body = None
    if expected_body is not None:
        try:
            actual_body = resp.json()
        except ValueError:
            return "ERROR", expected_body, resp.text[:500], "response body is not valid JSON"

    if expected_status is not None and resp.status_code != expected_status:
        return "FAIL", expected_status, resp.status_code, None
    if expected_body is not None and actual_body != expected_body:
        return "FAIL", expected_body, actual_body, None
    return "PASS", None, None, None


def _run_case(case: dict, base_url: str) -> tuple[str, object, object, str | None]:
    """(outcome, expected, actual, detail) — a connection/timeout failure is
    ERROR, never FAIL, so an agent doesn't have to parse message text to tell
    "the endpoint isn't running" from "the endpoint returned the wrong thing"."""
    try:
        resp = requests.request(case["method"], base_url + case["path"], json=case.get("body"), timeout=10)
    except requests.RequestException as exc:
        return "ERROR", None, None, f"request error: {exc}"
    return _classify_response(case, resp)


def _report(case_name: str, outcome: str, expected: object, actual: object, detail: str | None) -> None:
    if outcome == "PASS":
        print(f"[PASS] {case_name}")
    elif outcome == "FAIL":
        print(f"[FAIL] {case_name} — expected {expected!r}, got {actual!r}")
    else:  # ERROR — stdout convention stays [FAIL], detail goes to stderr, matching this script's existing style
        print(f"[FAIL] {case_name} — {detail}", file=sys.stderr)


def _case_batch(case_path: str, name: str | None, label: str) -> int:
    with open(case_path, "r", encoding="utf-8") as f:
        cases = json.load(f)
    if name is not None:
        cases = [c for c in cases if c["name"] == name]
        if not cases:
            print(f"[FAIL] no case named {name!r} in {case_path}", file=sys.stderr)
            return 1

    base_url = _base_url()
    log = _val_log.log_path("api_tester", label)
    exit_code = 0
    for case in cases:
        start = time.monotonic()
        outcome, expected, actual, detail = _run_case(case, base_url)
        duration_ms = int((time.monotonic() - start) * 1000)
        _report(case["name"], outcome, expected, actual, detail)
        _val_log.write_record(log, "api_tester", case["name"], outcome, duration_ms, expected, actual, detail)
        if outcome != "PASS":
            exit_code = 1
    return exit_code


def _ad_hoc(method: str, path: str, body_json: str | None) -> int:
    body = json.loads(body_json) if body_json else None
    url = _base_url() + path
    try:
        resp = requests.request(method, url, json=body, timeout=10)
    except requests.RequestException as exc:
        print(f"[FAIL] request error: {exc} — is `python -m easymcf` running?", file=sys.stderr)
        return 1

    print(f"{resp.status_code} {resp.reason}")
    try:
        print(json.dumps(resp.json(), indent=2))
    except ValueError:
        print(resp.text)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--case", help="path to a tests/backend/cases/*.json file")
    parser.add_argument("--name", default=None, help="run only this case (default: every case in --case's file)")
    parser.add_argument("--label", default="adhoc", help="caller's feature/task id for the log filename, e.g. 09.09")
    parser.add_argument("method", nargs="?", help="HTTP method, ad hoc mode")
    parser.add_argument("path", nargs="?", help="request path, ad hoc mode")
    parser.add_argument("body", nargs="?", default=None, help="JSON request body, ad hoc mode")
    args = parser.parse_args()

    if args.case:
        return _case_batch(args.case, args.name, args.label)

    if not args.method or not args.path:
        parser.error("ad hoc mode requires METHOD and PATH")
    return _ad_hoc(args.method.upper(), args.path, args.body)


if __name__ == "__main__":
    raise SystemExit(main())
