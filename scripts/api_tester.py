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

Two modes:

    # (a) ad hoc — poke one endpoint while `python -m easymcf` is up
    python scripts/api_tester.py GET /api/v1/health
    python scripts/api_tester.py POST /api/v1/lead '{"post_id": 1, "track_id": 1}'

    # (b) case-replay — reproduce a specific failing case against a live process
    python scripts/api_tester.py --case tests/backend/cases/health.json --name "health check returns ok"
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import requests
from dotenv import load_dotenv

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO_ROOT)
load_dotenv()  # before Config() is built — ENV-CFG-03/07.02.03

from easymcf.config import Config  # noqa: E402


def _base_url() -> str:
    return f"http://127.0.0.1:{Config().port}"


def _run_case(case: dict, base_url: str) -> bool:
    method = case["method"]
    url = base_url + case["path"]
    body = case.get("body")
    try:
        resp = requests.request(method, url, json=body, timeout=10)
    except requests.RequestException as exc:
        print(f"[FAIL] {case['name']} — request error: {exc}", file=sys.stderr)
        return False

    ok = True
    expected_status = case.get("expected_status")
    if expected_status is not None and resp.status_code != expected_status:
        print(f"[FAIL] {case['name']} — status {resp.status_code}, expected {expected_status}")
        ok = False

    expected_body = case.get("expected_body")
    if expected_body is not None:
        try:
            actual_body = resp.json()
        except ValueError:
            actual_body = None
        if actual_body != expected_body:
            print(f"[FAIL] {case['name']} — body {actual_body!r}, expected {expected_body!r}")
            ok = False

    if ok:
        print(f"[PASS] {case['name']}")
    return ok


def _case_replay(case_path: str, name: str) -> int:
    with open(case_path, "r", encoding="utf-8") as f:
        cases = json.load(f)
    matches = [c for c in cases if c["name"] == name]
    if not matches:
        print(f"[FAIL] no case named {name!r} in {case_path}", file=sys.stderr)
        return 1
    return 0 if _run_case(matches[0], _base_url()) else 1


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
    parser.add_argument("--name", help="case name within --case's file")
    parser.add_argument("method", nargs="?", help="HTTP method, ad hoc mode")
    parser.add_argument("path", nargs="?", help="request path, ad hoc mode")
    parser.add_argument("body", nargs="?", default=None, help="JSON request body, ad hoc mode")
    args = parser.parse_args()

    if args.case:
        if not args.name:
            parser.error("--case requires --name")
        return _case_replay(args.case, args.name)

    if not args.method or not args.path:
        parser.error("ad hoc mode requires METHOD and PATH")
    return _ad_hoc(args.method.upper(), args.path, args.body)


if __name__ == "__main__":
    raise SystemExit(main())
