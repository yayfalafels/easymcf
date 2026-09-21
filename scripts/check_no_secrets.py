#!/usr/bin/env python3
"""13.EL.11 (13.TC.24) - fail if a password, secret, or token appears where it must not.

`env/bin/python scripts/check_no_secrets.py [EXTRA_LITERAL ...]`

Real secrets (the Google client secret file, the cookie signing key, and any EXTRA_LITERAL such as a captured
session cookie or id token) are searched for in every tracked file, the database, and every file in .dev/logs/.
The fake seed passwords appear by design in the seed generator, tests/support/users.json, and the design
documents, so they are searched for in the database and the logs only. No matched value is ever printed.
"""

from __future__ import annotations

import glob
import json
import os
import subprocess
import sys

from dotenv import load_dotenv

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_SCRIPTS_DIR)
load_dotenv()  # before reading SECRETS_DIR / GCP_OAUTH_SECRET_FILE - ENV-CFG-03/07.02.03

SECRETS_DIR = os.environ.get("SECRETS_DIR", ".secrets")
MIN_LENGTH = 8


def _read(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read().strip()
    except OSError:
        return ""


def real_secrets(extra: list[str]) -> list[bytes]:
    secret_file = os.environ.get("GCP_OAUTH_SECRET_FILE") or os.path.join(SECRETS_DIR, "gcp_oauth_client_secret")
    values = [_read(secret_file), _read(os.path.join(SECRETS_DIR, "session_key")), *extra]
    return [v.encode() for v in values if len(v) >= MIN_LENGTH]


def test_passwords() -> list[bytes]:
    with open(os.path.join(ROOT, "tests", "support", "users.json"), encoding="utf-8") as handle:
        users = json.load(handle)
    return [u["password"].encode() for u in users.values()]


def scan(paths: list[str], needles: list[bytes], label: str) -> int:
    failed = 0
    for path in paths:
        if not os.path.isfile(path):
            continue
        with open(path, "rb") as handle:
            data = handle.read()
        if any(needle in data for needle in needles):
            print(f"[FAIL] {label} found in {os.path.relpath(path, ROOT)}")
            failed = 1
    return failed


def main() -> int:
    listed = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split("\n")
    tracked = [os.path.join(ROOT, p) for p in listed if p]
    database = os.environ.get("DB_PATH", os.path.join("data", "easymcf.db"))
    stored = [database if os.path.isabs(database) else os.path.join(ROOT, database)]
    stored += glob.glob(os.path.join(ROOT, ".dev", "logs", "*"))
    failed = scan(tracked + stored, real_secrets(sys.argv[1:]), "secret")
    failed |= scan(stored, test_passwords(), "test password")
    print("[FAIL] forbidden values found" if failed else "[PASS] no forbidden value found")
    return failed


if __name__ == "__main__":
    raise SystemExit(main())
