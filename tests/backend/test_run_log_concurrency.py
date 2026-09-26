"""11.EL.13 — ARCH-RUN-03's one-running-row-per-user-and-run-type guard, proven at the database layer and shared
by both run types: milestone 10's search runs and milestone 11's apply runs (STRAT-SILO-08 ownership)."""

from __future__ import annotations

import sqlite3

import pytest

from easymcf.db.connection import get_connection
from easymcf.services import search

pytestmark = pytest.mark.backend


@pytest.fixture()
def db(isolated_db):
    conn = get_connection(isolated_db)
    search.reconcile_orphaned_runs(conn)
    yield conn
    conn.close()


def _running(db, run_type: str, uid: int) -> int:
    track_id = None if run_type == "apply" else (1 if uid == 1 else 7)
    with db:
        return db.execute(
            "INSERT INTO run_log (run_type, user_id, track_id, started_at, status, trigger_source) "
            "VALUES (?, ?, ?, '2026-09-26 09:00:00', 'running', 'manual')", (run_type, uid, track_id),
        ).lastrowid


@pytest.mark.parametrize("run_type", ["search", "apply"])
def test_one_running_row_per_user_and_run_type(db, run_type):
    _running(db, run_type, uid=1)
    with pytest.raises(sqlite3.IntegrityError):
        _running(db, run_type, uid=1)
    assert _running(db, run_type, uid=2)  # another user is independent
    other = "search" if run_type == "apply" else "apply"
    assert _running(db, other, uid=1)  # the other run type for the same user is independent


def test_a_finished_row_releases_the_guard(db):
    run_id = _running(db, "apply", uid=1)
    with db:
        db.execute("UPDATE run_log SET status = 'partial' WHERE id = ?", (run_id,))
    assert _running(db, "apply", uid=1)
