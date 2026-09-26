"""REQ-APPLY-01..11 — the apply-run trigger, the per-lead state machine, and Workflow 7's lead effects.

Mirrors `search.py`'s shape for the second `run_type`: `start_run` runs the preflight checks and inserts the
`run_log` row, whose partial unique index is the one-run-at-a-time guard (ARCH-RUN-03), then hands the batch to a
background thread with its own SQLite connection and its own browser context (ARCH-RUN-02/04, ARCH-STO-07).

`run_batch` and `attempt_one` take an `ApplyBrowser` (ARCH-BOT-02) explicitly, so the oracle tests in
`tests/backend/test_apply_pipeline.py` call them directly against `easymcf/automation/apply_fixture.py`'s corpus
with no HTTP request and no Flask route (STRAT-SILO-05). Every function takes the owning user id explicitly
(ARCH-AUTH-04/08) and reads only that user's leads.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time

from .. import clock
from ..automation.apply_browser import LIVE_APPLY_REFUSED
from ..config import Config
from ..db.connection import get_connection
from ..errors import Conflict, RunInFlight
from . import leads, mcf_connection

logger = logging.getLogger(__name__)

STATUSES = ("applied", "questionnaire_required", "cv_selector_error", "unable_to_apply",
            "post_unavailable", "cv_not_found", "post_closed", "invalid_input")

# Workflow 7: the lead effect of each outcome. None leaves the lead at TOAPPLY for repair and retry.
OUTCOME_EFFECTS = {
    "applied": {"stage": "APPLIED"},
    "post_closed": {"stage": "CLOSED", "close_reason": "apply_failed"},
    "post_unavailable": {"stage": "CLOSED", "close_reason": "apply_failed"},
    "questionnaire_required": None,
    "cv_selector_error": None,
    "unable_to_apply": None,
    "cv_not_found": None,
    "invalid_input": None,
}

SESSION_INVALID_MESSAGE = "mcf_session is not valid: sign in through the MCF nav page before running apply"

# Shared with the lead resource's read (easymcf/api/resources.py), so the Applications page and the run resolve
# the effective CV and the cv_not_found block by one rule (Data model item 03).
EFFECTIVE_CV_SQL = "COALESCE(lead.cv_id, (SELECT default_cv_id FROM track WHERE track.id = lead.track_id))"
LATEST_APPLICATION_SQL = (
    "SELECT a.id FROM application a WHERE a.lead_id = lead.id ORDER BY a.attempted_at DESC, a.id DESC LIMIT 1"
)
BLOCKED_SQL = (
    f"(CASE WHEN last_app.status = 'cv_not_found' AND last_app.cv_id IS {EFFECTIVE_CV_SQL} THEN 1 ELSE 0 END)"
)

_QUEUE_SQL = (
    "SELECT lead.id, lead.post_id, lead.url_ref, lead.position_title, lead.company_name, "
    f"{EFFECTIVE_CV_SQL} AS effective_cv_id, cv.label AS cv_label, {BLOCKED_SQL} AS blocked "
    "FROM lead "
    f"LEFT JOIN application last_app ON last_app.id = ({LATEST_APPLICATION_SQL}) "
    f"LEFT JOIN cv ON cv.id = {EFFECTIVE_CV_SQL} "
    "WHERE lead.user_id = ? AND lead.stage = 'TOAPPLY' AND lead.status = 'OPEN' "
    "ORDER BY lead.id"
)


class SessionExpired(Exception):
    """The posting page's banner showed "Login" in place of the account initials: a run-level failure."""


def queue(db, uid: int) -> list[dict]:
    """The open TOAPPLY leads of this user, each with its effective CV and cv_not_found block (REQ-APPLY-01)."""
    return [dict(row) for row in db.execute(_QUEUE_SQL, (uid,)).fetchall()]


def _session_storage(db, config: Config, uid: int) -> str | None:
    """The storage-state path of a valid session, or None. Feature 17's reconciliation runs first, so a `valid` row
    whose file is gone reads as `missing` here too (11.IS.01)."""
    mcf_connection.reconcile_local_sessions(config, db=db)
    row = db.execute("SELECT status, cookie_ref FROM mcf_session WHERE user_id = ?", (uid,)).fetchone()
    if row is None or row["status"] != "valid":
        return None
    return os.path.join(config.secrets_dir, row["cookie_ref"])


def start_run(db, config: Config, uid: int) -> sqlite3.Row:
    """Workflow 6 run preflight. Live mode without APPLY_LIVE_SUBMIT=1 is refused (11.IS.14), and an invalid
    session aborts the whole batch before any row is written (REQ-APPLY-06). The INSERT is the in-flight guard;
    a collision answers 409 with the running id."""
    if config.mcf_mode == "live" and not config.apply_live_submit:
        raise Conflict(LIVE_APPLY_REFUSED)
    storage_path = _session_storage(db, config, uid)
    if storage_path is None:
        raise Conflict(SESSION_INVALID_MESSAGE)
    try:
        with db:
            run_id = db.execute(
                "INSERT INTO run_log (run_type, user_id, track_id, started_at, status, trigger_source) "
                "VALUES ('apply', ?, NULL, ?, 'running', 'manual')",
                (uid, clock.stamp()),
            ).lastrowid
    except sqlite3.IntegrityError as exc:
        running = db.execute(
            "SELECT id FROM run_log WHERE user_id = ? AND run_type = 'apply' AND status = 'running'", (uid,)
        ).fetchone()
        raise RunInFlight("apply", running["id"]) from exc
    threading.Thread(target=_run_apply, args=(config, run_id, uid, storage_path), daemon=True).start()
    return db.execute("SELECT * FROM run_log WHERE id = ?", (run_id,)).fetchone()


def _poll_button(browser, config: Config) -> tuple[str, str | None]:
    """REQ-APPLY-07: up to APPLY_POLL_RETRIES checks, APPLY_POLL_DELAY_S apart, never an unbounded wait."""
    for attempt in range(config.apply_poll_retries):
        state, detail = browser.check_apply_button()
        if state != "pending":
            return state, detail
        if attempt < config.apply_poll_retries - 1:
            time.sleep(config.apply_poll_delay_s)
    return "unresolved", f"apply button unresolved after {config.apply_poll_retries} attempts"


def attempt_one(browser, lead: dict, config: Config) -> tuple[str, str | None]:
    """The State-machine contract for one lead: returns (status, error_detail) from the eight-code vocabulary,
    or raises SessionExpired. Invalid input is rejected before the first browser action."""
    missing = [name for name, key in (("job id", "post_id"), ("posting URL", "url_ref"), ("CV assignment", "cv_label"))
               if not lead.get(key)]
    if missing:
        return "invalid_input", "missing field: " + ", ".join(missing)
    try:
        loaded, detail = browser.load_posting(lead["url_ref"])
        if loaded == "signed_out":
            raise SessionExpired(detail)
        if loaded == "load_failed":
            return "post_unavailable", detail
        state, detail = _poll_button(browser, config)
        if state == "signed_out":
            raise SessionExpired(detail)
        if state == "already_applied":
            return "applied", None
        if state == "closed":
            return "post_closed", detail
        if state == "unresolved":
            return "unable_to_apply", detail
        browser.click_apply()
        selected, detail = browser.select_cv(lead["cv_label"])
        if selected == "not_found":
            return "cv_not_found", detail
        if selected == "selector_error":
            return "cv_selector_error", detail
        submitted, detail = browser.submit_review()
        return ("applied", None) if submitted else ("questionnaire_required", detail)
    except SessionExpired:
        raise
    except Exception as exc:  # noqa: BLE001 — an unnamed failure is unable_to_apply, and the batch continues
        return "unable_to_apply", f"unexpected {type(exc).__name__}: {exc}"


def record_outcome(db, uid: int, run_id: int, lead: dict, status: str, error_detail: str | None) -> int:
    """Outcome persistence (Workflow step 08): the append-only attempt row and its Workflow 7 lead effect, in one
    transaction, through leads.update_lead — the single lead write path, not a second one."""
    at = clock.stamp()
    with db:
        app_id = db.execute(
            "INSERT INTO application (lead_id, cv_id, status, error_detail, attempted_at, run_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (lead["id"], lead.get("effective_cv_id"), status, error_detail, at, run_id),
        ).lastrowid
        current = db.execute("SELECT stage, first_attempt_date FROM lead WHERE id = ? AND user_id = ?",
                             (lead["id"], uid)).fetchone()
        if current is None or current["stage"] != "TOAPPLY":
            return app_id  # the user moved the lead mid-run; the attempt is recorded, the lead is left as they set it
        body = dict(OUTCOME_EFFECTS[status] or {})
        if current["first_attempt_date"] is None:
            body["first_attempt_date"] = at[:10]
        if body.get("stage") == "APPLIED":
            body["applied_date"] = at[:10]
        if body:
            leads.update_lead(db, lead["id"], body, internal=True, detail=f"apply run {run_id}: {status}")
    return app_id


def _progress(db, run_id: int, counts: dict, extra: dict) -> None:
    with db:
        db.execute("UPDATE run_log SET outcome_counts = ? WHERE id = ?", (json.dumps({**counts, **extra}), run_id))


def run_batch(db, uid: int, run_id: int, browser, config: Config) -> dict:
    """Attempts every runnable queued lead once, in lead-id order. A lead blocked on an unrepaired cv_not_found
    is skipped. Each outcome is committed before the next lead starts, so one lead's failure never touches
    another's recorded row (REQ-APPLY-08). Returns the counts, the run error, and the per-lead results."""
    runnable = [lead for lead in queue(db, uid) if not lead["blocked"]]
    counts: dict[str, int] = {}
    results: dict[int, str] = {}
    run_error = None
    for index, lead in enumerate(runnable):
        _progress(db, run_id, counts, {"queued": len(runnable), "processed": index, "current_lead_id": lead["id"]})
        still_queued = db.execute(
            "SELECT 1 FROM lead WHERE id = ? AND stage = 'TOAPPLY' AND status = 'OPEN'", (lead["id"],)
        ).fetchone()
        if still_queued is None:
            continue  # dropped or moved by the user after the run started
        started = time.monotonic()
        try:
            status, detail = attempt_one(browser, lead, config)
        except SessionExpired as exc:
            mcf_connection.mark_reauthentication_required(db, uid)
            run_error = (f"session expired: {exc} at lead {lead['id']} after {index} of {len(runnable)} leads "
                         "attempted; reconnect through the MCF nav icon")
            logger.warning("MCF_DIAG apply run=%s user=%s lead=%s session expired", run_id, uid, lead["id"])
            break
        app_id = record_outcome(db, uid, run_id, lead, status, detail)
        counts[status] = counts.get(status, 0) + 1
        results[lead["id"]] = status
        logger.info("MCF_DIAG apply run=%s user=%s lead=%s application=%s mode=%s outcome=%s elapsed=%.2fs",
                    run_id, uid, lead["id"], app_id, config.mcf_mode, status, time.monotonic() - started)
    return {"counts": counts, "error": run_error, "results": results, "queued": len(runnable)}


def finish_run(db, run_id: int, counts: dict, error: str | None, crashed: bool) -> str:
    attempted = sum(counts.values())
    if crashed or (error and attempted == 0):
        status = "failed"
    elif error:
        status = "partial"
    else:
        status = "success"
    with db:
        db.execute(
            "UPDATE run_log SET status = ?, ended_at = ?, outcome_counts = ?, error_detail = ? WHERE id = ?",
            (status, clock.stamp(), json.dumps(counts), error, run_id),
        )
    return status


def _run_apply(config: Config, run_id: int, uid: int, storage_path: str) -> None:
    """The background thread start_run spawns. Every exception ends the run with a terminal status, never a
    crashed thread; application rows already committed keep their outcomes (Run-level failure 05)."""
    from ..automation.apply_browser import get_browser  # raises LiveApplyNotConfirmed before any live browser

    db = get_connection(config.db_path)
    browser = None
    counts: dict[str, int] = {}
    error, crashed = None, False
    try:
        init_script = mcf_connection._session_storage_script(storage_path) if storage_path else None
        browser = get_browser(config, storage_path, init_script)
        outcome = run_batch(db, uid, run_id, browser, config)
        counts, error = outcome["counts"], outcome["error"]
    except Exception as exc:  # noqa: BLE001
        logger.exception("MCF_DIAG apply run %s failed", run_id)
        crashed = True
        counts = _committed_counts(db, run_id)
        error = f"{type(exc).__name__}: {exc}"
    finally:
        if browser is not None:
            try:
                browser.close()
            except Exception:  # noqa: BLE001 — closing a browser that never fully started must not mask the error
                pass
    finish_run(db, run_id, counts, error, crashed)
    db.close()


def _committed_counts(db, run_id: int) -> dict[str, int]:
    rows = db.execute("SELECT status, COUNT(*) AS n FROM application WHERE run_id = ? GROUP BY status", (run_id,))
    return {row["status"]: row["n"] for row in rows}
