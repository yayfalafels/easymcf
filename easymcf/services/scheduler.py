"""REQ-SRCH-11, `ARCH-SCHED-01..06` — the in-process scheduled-run tick, no OS-level
scheduler of any kind (cron/systemd/APScheduler/Celery beat/a second process — explicitly
refused by the architecture's own out-of-scope list). `tick()` reads due `search_schedule`
rows through `clock.py::now()` and calls the same `start_run()` the manual trigger route
calls (`API-EP-04`), so a scheduled run is indistinguishable from a manual one downstream
of that one call, apart from `trigger_source`.

`next_run_after` is pure (Algorithms section, "Schedule advance") so the oracle case
(`10.TC.22`) can call it directly with no db and no clock. `tick` and `run_forever` do I/O
and are exercised through `10.TC.07`/`.14`/`.21` instead.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta

from .. import clock
from ..errors import RunInFlight
from . import search

logger = logging.getLogger(__name__)


def next_run_after(next_run_at: datetime | None, interval_hours: int, now: datetime) -> datetime:
    """Schedule advance (`ARCH-SCHED-03`): the first whole-interval step strictly after
    `now`, so windows missed while the app was closed collapse into one catch-up run
    rather than firing once per missed interval."""
    step = timedelta(hours=interval_hours)
    if next_run_at is None:
        return now + step
    return next_run_at + step * ((now - next_run_at) // step + 1)


def tick(db, now: datetime) -> None:
    """Selects schedules that are enabled, belong to an active track, and are due
    (`next_run_at` null or at/before `now`), oldest first, across all users, and calls
    `start_run` for each (Workflow, "Scheduled run"). On success `next_run_at` advances.
    On `RunInFlight` the collision is logged once, `next_run_at` is left untouched so the
    schedule retries on a later tick, and the rest of that same user's due schedules are
    skipped for this tick — each of them would collide too — while other users' due
    schedules proceed in the same tick (`ARCH-SCHED-04`). A skipped tick writes no
    `run_log` row of its own (`ARCH-SCHED-05`)."""
    due = db.execute(
        "SELECT ss.track_id, t.user_id, ss.schedule_interval_hours, ss.next_run_at FROM search_schedule ss "
        "JOIN track t ON t.id = ss.track_id WHERE ss.schedule_enabled = 1 AND t.is_active = 1 "
        "AND (ss.next_run_at IS NULL OR ss.next_run_at <= ?) ORDER BY ss.next_run_at",
        (now.isoformat(sep=" "),),
    ).fetchall()
    skipped_users: set[int] = set()
    for row in due:
        if row["user_id"] in skipped_users:
            continue
        try:
            search.start_run(db, row["user_id"], row["track_id"], trigger_source="scheduled")
        except RunInFlight as exc:
            logger.info(
                "scheduler: skipping track %s (user %s), run %s already in flight",
                row["track_id"], row["user_id"], exc.extra["run_id"],
            )
            skipped_users.add(row["user_id"])
            continue
        next_at = next_run_after(
            datetime.fromisoformat(row["next_run_at"]) if row["next_run_at"] else None,
            row["schedule_interval_hours"], now,
        )
        with db:
            db.execute(
                "UPDATE search_schedule SET next_run_at = ? WHERE track_id = ?",
                (next_at.isoformat(sep=" "), row["track_id"]),
            )


def run_forever(get_db_fn, tick_s: float, stop_event: threading.Event) -> None:
    """The loop `easymcf/__main__.py` starts (`10.EL.16`) — never `create_app()` itself
    (`ARCH-SCHED-06`), since `create_app()` also runs under the test client, where a live
    tick thread would be a leftover timer across tests. Each tick opens and closes its own
    connection (`ARCH-STO-07`); a tick's own exception is logged, not left to kill the
    loop, since a single bad tick must not silence every later scheduled run."""
    while not stop_event.wait(tick_s):
        db = get_db_fn()
        try:
            tick(db, clock.now())
        except Exception:  # noqa: BLE001 — one bad tick must not end the scheduler thread
            logger.exception("MCF_DIAG scheduler tick failed")
        finally:
            db.close()
