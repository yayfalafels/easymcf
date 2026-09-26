"""10.EL.30 — oracle for easymcf/services/scheduler.py (10.TC.21/.22), `tick`'s own function
object called directly against a fixed `clock.py::now()` (STRAT-SILO-05): no HTTP request,
no Flask route, and no real tick thread. Expected values are hand-coded from this
milestone's own Algorithms ("Schedule advance") and Workflow ("Scheduled run") sections,
never imported from the code under test (010.08's oracle precedent).
"""

from __future__ import annotations

import logging
import time
from datetime import datetime

import pytest

from easymcf import clock
from easymcf.db.connection import get_connection
from easymcf.services import scheduler

pytestmark = pytest.mark.backend

# Track 7 belongs to seed user 2 (seed/04_track.sql), distinct from the seed's own
# deliberately 'running' run_log row (user 1, track 1) that other oracle tests reconcile
# away — using user 2's own track here keeps each test's in-flight row explicit and
# self-contained rather than an incidental side effect of what the seed happens to carry.
TRACK_ID = 7
USER_ID = 2


@pytest.fixture()
def db(isolated_db):
    conn = get_connection(isolated_db)
    yield conn
    conn.close()


@pytest.fixture(autouse=True)
def _pinned_now(fixed_clock):
    fixed_clock("2026-09-24 08:00:00")
    yield


def _enable_schedule(db, track_id: int, next_run_at: str, interval_hours: int = 24) -> None:
    with db:
        db.execute(
            "UPDATE search_schedule SET schedule_enabled = 1, schedule_interval_hours = ?, "
            "next_run_at = ? WHERE track_id = ?",
            (interval_hours, next_run_at, track_id),
        )


def _run_log_count(db, track_id: int) -> int:
    return db.execute("SELECT COUNT(*) AS n FROM run_log WHERE track_id = ?", (track_id,)).fetchone()["n"]


def test_a_due_schedule_colliding_with_an_in_flight_run_skips_and_logs_once(db, caplog):
    """10.TC.21 / ARCH-SCHED-04: a pre-inserted `running` run_log row for this user/track
    makes `start_run`'s own partial unique index (`ux_run_log_running`) reject the
    scheduler's own insert. `tick` must catch that `RunInFlight`, log exactly one line
    naming the track and the in-flight run, leave `next_run_at` untouched, and write no
    second `run_log` row."""
    with db:
        in_flight_id = db.execute(
            "INSERT INTO run_log (run_type, user_id, track_id, started_at, status, trigger_source) "
            "VALUES ('search', ?, ?, ?, 'running', 'manual')",
            (USER_ID, TRACK_ID, clock.stamp()),
        ).lastrowid
    _enable_schedule(db, TRACK_ID, next_run_at="2026-09-24 07:00:00")
    # track 7 already carries one seeded run_log row (seed/07_run_log.sql, id 6); `before`
    # captures whatever that baseline is, rather than hard-coding it, so this test doesn't
    # silently drift if the seed's own row set changes later.
    before = _run_log_count(db, TRACK_ID)

    with caplog.at_level(logging.INFO, logger="easymcf.services.scheduler"):
        scheduler.tick(db, clock.now())

    assert _run_log_count(db, TRACK_ID) == before  # the UNIQUE/RunInFlight collision wrote no second row
    row = db.execute("SELECT next_run_at FROM search_schedule WHERE track_id = ?", (TRACK_ID,)).fetchone()
    assert row["next_run_at"] == "2026-09-24 07:00:00"  # left untouched, per ARCH-SCHED-04

    skip_records = [r for r in caplog.records if "skipping" in r.getMessage()]
    assert len(skip_records) == 1
    assert str(TRACK_ID) in skip_records[0].getMessage()
    assert str(in_flight_id) in skip_records[0].getMessage()


def test_a_schedule_three_intervals_stale_fires_exactly_one_catch_up_run(db, isolated_db, monkeypatch):
    """10.TC.22 / ARCH-SCHED-03: `next_run_at` three whole 24h intervals in the past ticks
    to exactly one new run, and `next_run_after` advances `next_run_at` to the next whole
    interval strictly after `now` — 2026-09-25 08:00:00, not one run per missed window."""
    # start_run (ARCH-RUN-02) spawns a real background thread that opens its own connection
    # through a fresh Config().db_path — point that at this test's own isolated_db file so
    # the run actually happens against it, not against whatever DB_PATH an earlier test in
    # this session already exported (ARCH-STO-07: each thread owns its own connection, but
    # they must still agree on which file).
    monkeypatch.setenv("DB_PATH", isolated_db)
    _enable_schedule(db, TRACK_ID, next_run_at="2026-09-21 08:00:00", interval_hours=24)
    before = _run_log_count(db, TRACK_ID)

    scheduler.tick(db, clock.now())

    assert _run_log_count(db, TRACK_ID) == before + 1  # exactly one run started, not three
    run = db.execute(
        "SELECT id, status, trigger_source FROM run_log WHERE track_id = ? ORDER BY id DESC LIMIT 1", (TRACK_ID,)
    ).fetchone()
    assert run["trigger_source"] == "scheduled"
    assert run["status"] in ("running", "success", "partial", "failed")  # the background thread may race ahead

    row = db.execute("SELECT next_run_at FROM search_schedule WHERE track_id = ?", (TRACK_ID,)).fetchone()
    next_run_at = datetime.fromisoformat(row["next_run_at"])
    assert next_run_at == datetime(2026, 9, 25, 8, 0, 0)
    assert next_run_at > clock.now()  # strictly after "now", per the Schedule advance algorithm

    # Let the background run thread (start_run spawns one) reach a terminal status before
    # this test's isolated_db temp file is torn down, so no daemon thread is left mid-write.
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        status = db.execute("SELECT status FROM run_log WHERE id = ?", (run["id"],)).fetchone()["status"]
        if status != "running":
            break
        time.sleep(0.1)


class TestNextRunAfter:
    """Pure-function cases for `next_run_after` (Algorithms, "Schedule advance"), the
    worked example from the design doc verbatim."""

    def test_null_next_run_at_starts_one_interval_from_now(self):
        now = datetime(2026, 9, 16, 8, 0, 0)
        assert scheduler.next_run_after(None, 24, now) == datetime(2026, 9, 17, 8, 0, 0)

    def test_three_missed_windows_collapse_into_one_advance(self):
        """The tracker's own worked example: a 24h interval, next_run_at of 2026-09-16
        08:00 and now of 2026-09-19 10:00 — three whole intervals have passed, and the
        next value is 2026-09-20 08:00, not 2026-09-19 08:00 (one instant per miss)."""
        next_run_at = datetime(2026, 9, 16, 8, 0, 0)
        now = datetime(2026, 9, 19, 10, 0, 0)
        assert scheduler.next_run_after(next_run_at, 24, now) == datetime(2026, 9, 20, 8, 0, 0)

    def test_exactly_on_the_boundary_still_advances_past_now(self):
        next_run_at = datetime(2026, 9, 21, 8, 0, 0)
        now = datetime(2026, 9, 21, 8, 0, 0)
        result = scheduler.next_run_after(next_run_at, 24, now)
        assert result == datetime(2026, 9, 22, 8, 0, 0)
        assert result > now
