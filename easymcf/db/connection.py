"""SQLite connection helper — WAL mode, per-thread connections (ARCH-STO-07)."""

from __future__ import annotations

import os
import sqlite3


def get_connection(db_path: str) -> sqlite3.Connection:
    """Open a connection tuned for this app's threading model.

    One connection per thread (`check_same_thread` left at its sqlite3
    default — connections are never shared across threads), WAL journal mode
    so the background run thread's writes don't block request-thread reads,
    a 5s busy timeout, and foreign keys enabled (off by default in SQLite).
    """
    parent = os.path.dirname(db_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def schema_version(db_path: str) -> int | None:
    """Read `meta.schema_version`, or None if the db file/table doesn't exist yet."""
    if not os.path.exists(db_path):
        return None
    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT schema_version FROM meta").fetchone()
        return row["schema_version"] if row else None
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()
