#!/usr/bin/env python3
"""ENV-SCRIPT-02 — the destructive human/agent-facing reset (ARCH-STO-06).

`python scripts/resetdb.py [--seed]`: delete the file at `DB_PATH`
if present, apply `easymcf/db/schema.sql`, then apply `seed/*.sql` if
`--seed` is passed. This is the single command that recovers from a
`schema_version` mismatch or a corrupted dev scratch db — never hand-edit
`data/easymcf.db`.
"""

from __future__ import annotations

import argparse
import glob
import os
import sqlite3
import sys

from dotenv import load_dotenv

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_SCRIPTS_DIR)
sys.path.insert(0, _SCRIPTS_DIR)
sys.path.insert(0, _REPO_ROOT)
load_dotenv()  # before Config() is built — ENV-CFG-03/07.02.03

from easymcf.config import Config  # noqa: E402
from initdb import apply_schema  # noqa: E402

_SEED_DIR = os.path.join(_REPO_ROOT, "seed")


def apply_seed(db_path: str) -> list[str]:
    """Apply every seed/*.sql file, sorted, in one transaction each. Returns files applied."""
    applied = []
    conn = sqlite3.connect(db_path)
    try:
        for seed_file in sorted(glob.glob(os.path.join(_SEED_DIR, "*.sql"))):
            with open(seed_file, "r", encoding="utf-8") as f:
                conn.executescript(f.read())
            applied.append(os.path.relpath(seed_file, _REPO_ROOT))
        conn.commit()
    finally:
        conn.close()
    return applied


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", default=None, help="overrides DB_PATH")
    parser.add_argument("--seed", action="store_true", help="also apply seed/*.sql")
    args = parser.parse_args()

    db_path = args.db_path or Config().db_path

    try:
        if os.path.exists(db_path):
            os.remove(db_path)
        apply_schema(db_path)
        print(f"[PASS] schema applied — {db_path}")

        if args.seed:
            applied = apply_seed(db_path)
            if applied:
                print(f"[PASS] seed applied — {', '.join(applied)}")
            else:
                print("[PASS] seed applied — no seed/*.sql files found")
    except sqlite3.Error as exc:
        print(f"[FAIL] reset error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
