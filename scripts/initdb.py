#!/usr/bin/env python3
"""ENV-SCRIPT-01 — idempotent schema application.

`python scripts/initdb.py [--db-path PATH]` applies `easymcf/db/schema.sql`
to `DB_PATH` (or `--db-path`), creating the file if absent. Never
deletes an existing file itself — that's `resetdb.py`'s job. Run through
`env`, never an ad hoc venv.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()  # before Config() is built — ENV-CFG-03/07.02.03

from easymcf.config import Config  # noqa: E402

_SCHEMA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "easymcf", "db", "schema.sql"
)


def apply_schema(db_path: str) -> bool:
    """Apply schema.sql to db_path if it doesn't already exist. Returns True if applied."""
    if os.path.exists(db_path):
        return False
    parent = os.path.dirname(db_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(_SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema_sql = f.read()
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", default=None, help="overrides DB_PATH")
    args = parser.parse_args()

    db_path = args.db_path or Config().db_path

    try:
        applied = apply_schema(db_path)
    except sqlite3.Error as exc:
        print(f"[FAIL] schema apply error: {exc}", file=sys.stderr)
        return 1

    if applied:
        print(f"[PASS] schema applied — {db_path}")
    else:
        print(f"[PASS] db already exists, schema not re-applied — {db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
