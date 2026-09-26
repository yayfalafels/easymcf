"""11.EL.12 — oracle for easymcf/services/apply.py (11.TC.16..20, TC-AUTO-009..019), called directly against
easymcf/automation/apply_fixture.py's corpus (STRAT-SILO-05): no HTTP request, no Flask route. Expected values are
hand-coded from the tracker's State-machine contract, Workflow 7 table, and Error handling sections, never imported
from the code under test (010.08's oracle precedent). Every case runs with APPLY_POLL_RETRIES=2 and
APPLY_POLL_DELAY_S=0.01 (STRAT-CASE-06), except the production-default timing case, which stubs the sleep.
"""

from __future__ import annotations

import json
import os
import threading

import pytest

from easymcf import clock
from easymcf.automation.apply_fixture import FixtureApplyBrowser, load_manifest
from easymcf.config import Config
from easymcf.db.connection import get_connection
from easymcf.errors import Conflict, RunInFlight
from easymcf.services import apply, leads, search

pytestmark = pytest.mark.backend

CONFIG = Config(apply_poll_retries=2, apply_poll_delay_s=0.01, mcf_fixture_scenario="default")
URL = "https://www.mycareersfuture.gov.sg/job/apply-fixture-{}"

# State-machine contract x Workflow 7, transcribed: scenario -> (status, stage, lead status, close_reason,
# navigations, polls, cv selections, submits). invalid_input makes zero browser actions of any kind.
BRANCHES = {
    "success":          ("applied", "APPLIED", "OPEN", None, 1, 1, 1, 1),
    "already_applied":  ("applied", "APPLIED", "OPEN", None, 1, 1, 0, 0),
    "questionnaire":    ("questionnaire_required", "TOAPPLY", "OPEN", None, 1, 1, 1, 1),
    "selector_error":   ("cv_selector_error", "TOAPPLY", "OPEN", None, 1, 1, 1, 0),
    "poll_exhausted":   ("unable_to_apply", "TOAPPLY", "OPEN", None, 1, 2, 0, 0),
    "post_unavailable": ("post_unavailable", "CLOSED", "CLOSED", "apply_failed", 1, 0, 0, 0),
    "cv_not_found":     ("cv_not_found", "TOAPPLY", "OPEN", None, 1, 1, 1, 0),
    "post_closed":      ("post_closed", "CLOSED", "CLOSED", "apply_failed", 1, 1, 0, 0),
    "invalid_input":    ("invalid_input", "TOAPPLY", "OPEN", None, 0, 0, 0, 0),
    "submit_unconfirmed": ("questionnaire_required", "TOAPPLY", "OPEN", None, 1, 1, 1, 1),  # 11.IS.23
}


@pytest.fixture(scope="module")
def browser():
    b = FixtureApplyBrowser(CONFIG)
    yield b
    b.close()


@pytest.fixture()
def db(isolated_db):
    conn = get_connection(isolated_db)
    search.reconcile_orphaned_runs(conn)
    # an empty queue, so each case controls exactly which leads it attempts
    conn.execute("UPDATE lead SET stage = 'CLOSED', status = 'CLOSED', close_reason = 'dropped' "
                 "WHERE stage = 'TOAPPLY'")
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture(autouse=True)
def _pinned_today(fixed_clock):
    fixed_clock("2026-09-26 09:00:00")
    yield


_seq = iter(range(1, 10_000))


def _lead(db, scenario: str, *, uid: int = 1, track_id: int = 1, cv_id: int | None = None,
          url: str | None = "") -> int:
    """A queued TOAPPLY lead whose posting URL names its fixture scenario. url=None makes a lead with no URL."""
    n = next(_seq)
    # a distinct posting per lead: a submitted posting reads already applied afterwards, as on MCF (11.IS.23)
    url_ref = f"{URL.format(scenario)}--{n}" if url == "" else url
    post_id = f"fx-{scenario}-{n}"
    db.execute("INSERT INTO post (id, source, position_title, company_name, url_ref, posted_date, src_method) "
               "VALUES (?, 'MyCareerFutures', ?, 'Fixture Co', ?, '2026-09-20', 'scraped')",
               (post_id, f"fixture {scenario}", url_ref))
    lead_id = db.execute(
        "INSERT INTO lead (user_id, post_id, track_id, cv_id, status, stage, position_title, company_name, url_ref, "
        "deadline, created_at, updated_at) VALUES (?, ?, ?, ?, 'OPEN', 'TOAPPLY', ?, 'Fixture Co', ?, '2026-10-30', "
        "?, ?)", (uid, post_id, track_id, cv_id, f"fixture {scenario}", url_ref, clock.stamp(), clock.stamp()),
    ).lastrowid
    db.commit()
    return lead_id


def _run(db, uid: int = 1) -> int:
    run_id = db.execute(
        "INSERT INTO run_log (run_type, user_id, track_id, started_at, status, trigger_source) "
        "VALUES ('apply', ?, NULL, ?, 'running', 'manual')", (uid, clock.stamp())).lastrowid
    db.commit()
    return run_id


def _apps(db, run_id: int) -> dict[int, dict]:
    return {r["lead_id"]: dict(r) for r in db.execute("SELECT * FROM application WHERE run_id = ?", (run_id,))}


def _lead_row(db, lead_id: int) -> dict:
    return dict(db.execute("SELECT * FROM lead WHERE id = ?", (lead_id,)).fetchone())


def _delta(before: dict, after: dict) -> tuple:
    return tuple(after[k] - before[k] for k in ("navigations", "polls", "cv_selections", "submits"))


@pytest.mark.parametrize("scenario", list(BRANCHES))
def test_branch_matrix_outcome_lead_effect_and_browser_boundary(db, browser, scenario):
    """11.TC.16 / 11.TC.19 — each branch's application status, Workflow 7 lead effect, and browser boundary."""
    status, stage, lead_status, reason, *actions = BRANCHES[scenario]
    lead_id = _lead(db, "success", url=None) if scenario == "invalid_input" else _lead(db, scenario)
    run_id = _run(db)
    before = dict(browser.diagnostics)
    outcome = apply.run_batch(db, 1, run_id, browser, CONFIG)
    assert _delta(before, browser.diagnostics) == tuple(actions)
    assert outcome["counts"] == {status: 1} and outcome["error"] is None
    app = _apps(db, run_id)[lead_id]
    assert app["status"] == status and app["cv_id"] == 1  # track 1's default CV, label 13.2
    assert (app["error_detail"] is None) == (status == "applied")
    row = _lead_row(db, lead_id)
    assert (row["stage"], row["status"], row["close_reason"]) == (stage, lead_status, reason)
    assert row["first_attempt_date"] == "2026-09-26"
    assert row["applied_date"] == ("2026-09-26" if stage == "APPLIED" else None)


def test_error_detail_names_the_cause_per_status(db, browser):
    """Error handling table: each non-applied status carries its own diagnostic."""
    ids = {s: _lead(db, s) for s in ("questionnaire", "poll_exhausted", "cv_not_found", "post_closed",
                                     "post_unavailable", "selector_error")}
    ids["invalid_input"] = _lead(db, "success", url=None)
    run_id = _run(db)
    apply.run_batch(db, 1, run_id, browser, CONFIG)
    detail = {s: _apps(db, run_id)[i]["error_detail"] for s, i in ids.items()}
    assert detail["questionnaire"].startswith("final submit failed")
    assert detail["poll_exhausted"] == "apply button unresolved after 2 attempts"
    assert detail["cv_not_found"] == "no resume option matched CV label '13.2'"
    assert detail["post_closed"] == "This job is no longer available."
    assert "ERR_CONNECTION_REFUSED" in detail["post_unavailable"]
    assert detail["selector_error"].startswith("LookupError")
    assert detail["invalid_input"] == "missing field: posting URL"


def test_invalid_input_names_each_missing_field_with_no_browser_action(db):
    """TC-AUTO-016 — missing job id, URL, and CV assignment are all rejected before any browser call."""
    class NoBrowser:
        def __getattr__(self, name):
            raise AssertionError(f"browser.{name} called for invalid input")

    status, detail = apply.attempt_one(NoBrowser(), {"id": 1, "post_id": None, "url_ref": None, "cv_label": None},
                                       CONFIG)
    assert (status, detail) == ("invalid_input", "missing field: job id, posting URL, CV assignment")


def test_manifest_expectations_match_this_oracle(browser):
    """The corpus manifest's recorded markers agree with the hand-coded contract above."""
    manifest = load_manifest()["scenarios"]
    for scenario, (status, *_, polls, cv_selections, submits) in BRANCHES.items():
        if scenario == "invalid_input":
            continue
        assert manifest[scenario]["expect"] == {"status": status, "polls": polls, "cv_selections": cv_selections,
                                                "submits": submits}, scenario


def test_poll_boundary_one_short_of_exhaustion_and_at_exhaustion(db, browser):
    """11.TC.17 — the button on poll 2 of 2 is found; a button that never resolves exhausts at exactly 2 polls."""
    late, never = _lead(db, "button_late"), _lead(db, "poll_exhausted")
    run_id = _run(db)
    before = browser.diagnostics["polls"]
    apply.run_batch(db, 1, run_id, browser, CONFIG)
    assert browser.diagnostics["polls"] - before == 4
    apps = _apps(db, run_id)
    assert apps[late]["status"] == "applied"
    assert apps[never]["status"] == "unable_to_apply"


def test_production_default_retry_timing(monkeypatch):
    """11.TC.17 — defaults are 5 retries and 5 s; the loop sleeps between polls only, never after the last."""
    monkeypatch.delenv("APPLY_POLL_RETRIES", raising=False)
    monkeypatch.delenv("APPLY_POLL_DELAY_S", raising=False)
    config = Config()
    assert (config.apply_poll_retries, config.apply_poll_delay_s) == (5, 5.0)
    sleeps = []
    monkeypatch.setattr(apply.time, "sleep", sleeps.append)

    class Pending:
        polls = 0

        def check_apply_button(self):
            self.polls += 1
            return "pending", None

    pending = Pending()
    assert apply._poll_button(pending, config) == ("unresolved", "apply button unresolved after 5 attempts")
    assert pending.polls == 5 and sleeps == [5.0] * 4


def test_mixed_batch_continues_and_keeps_each_outcome(db, browser):
    """11.TC.18 / REQ-APPLY-08 — one cv_not_found, one questionnaire, two applied: every lead is attempted once,
    in one browser pass, and every earlier application row of every other lead is untouched."""
    earlier = [dict(r) for r in db.execute("SELECT * FROM application ORDER BY id")]
    ids = [_lead(db, "cv_not_found"), _lead(db, "questionnaire"), _lead(db, "success"), _lead(db, "success")]
    run_id = _run(db)
    before = dict(browser.diagnostics)
    outcome = apply.run_batch(db, 1, run_id, browser, CONFIG)
    assert outcome["counts"] == {"cv_not_found": 1, "questionnaire_required": 1, "applied": 2}
    assert outcome["results"] == dict(zip(ids, ["cv_not_found", "questionnaire_required", "applied", "applied"]))
    assert browser.diagnostics["navigations"] - before["navigations"] == 4
    assert [a["status"] for a in map(_apps(db, run_id).get, ids)] == [
        "cv_not_found", "questionnaire_required", "applied", "applied"]
    assert [dict(r) for r in db.execute("SELECT * FROM application WHERE id <= ? ORDER BY id",
                                        (earlier[-1]["id"],))] == earlier


def test_unexpected_exception_is_unable_to_apply_and_the_batch_continues(db, browser):
    """Error handling: an exception no branch names is unable_to_apply with its type, and the next lead runs."""
    class Exploding:
        diagnostics: dict = {}
        calls = 0

        def load_posting(self, url_ref):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("renderer crashed")
            return browser.load_posting(url_ref)

        def __getattr__(self, name):
            return getattr(browser, name)

    first, second = _lead(db, "success"), _lead(db, "success")
    run_id = _run(db)
    apply.run_batch(db, 1, run_id, Exploding(), CONFIG)
    apps = _apps(db, run_id)
    assert apps[first]["status"] == "unable_to_apply"
    assert apps[first]["error_detail"] == "unexpected RuntimeError: renderer crashed"
    assert apps[second]["status"] == "applied"


def test_cv_not_found_blocks_until_repaired_and_keeps_retry_history(db, browser):
    """11.TC.19 / Data model item 03 — a cv_not_found lead is skipped while its effective CV is unchanged; an
    override repairs it, and the retry adds a second attempt row rather than replacing the first."""
    db.execute("INSERT INTO cv (id, user_id, label) VALUES (90, 1, 'Z-9')")
    lead_id = _lead(db, "success", cv_id=90)
    first = _run(db)
    apply.run_batch(db, 1, first, browser, CONFIG)
    apply.finish_run(db, first, {}, None, False)
    assert _apps(db, first)[lead_id]["status"] == "cv_not_found"
    assert [q["blocked"] for q in apply.queue(db, 1) if q["id"] == lead_id] == [1]

    blocked_run = _run(db)
    assert apply.run_batch(db, 1, blocked_run, browser, CONFIG)["counts"] == {}
    apply.finish_run(db, blocked_run, {}, None, False)

    with db:
        leads.update_lead(db, lead_id, {"cv_id": 2})  # override to label 11.4
    retry = _run(db)
    apply.run_batch(db, 1, retry, browser, CONFIG)
    history = [(r["cv_id"], r["status"]) for r in
               db.execute("SELECT * FROM application WHERE lead_id = ? ORDER BY id", (lead_id,))]
    assert history == [(90, "cv_not_found"), (2, "applied")]
    assert _lead_row(db, lead_id)["stage"] == "APPLIED"


def test_mid_batch_signed_out_banner_ends_the_run(db, browser):
    """TC-AUTO-019 — a later lead's signed-out banner marks the session expired and the latest attempt
    reauthentication_required, stops the batch, and keeps the earlier lead's recorded outcome."""
    done, lapsed, never = _lead(db, "success"), _lead(db, "signed_out"), _lead(db, "success")
    run_id = _run(db)
    outcome = apply.run_batch(db, 1, run_id, browser, CONFIG)
    assert outcome["counts"] == {"applied": 1}
    assert outcome["error"].startswith(f"session expired: MCF banner shows Login in place of the account initials "
                                       f"at lead {lapsed} after 1 of 3 leads attempted")
    assert set(_apps(db, run_id)) == {done}
    assert _lead_row(db, never)["stage"] == "TOAPPLY" and _lead_row(db, lapsed)["stage"] == "TOAPPLY"
    assert db.execute("SELECT status FROM mcf_session WHERE user_id = 1").fetchone()[0] == "expired"
    assert db.execute("SELECT status FROM mcf_attempt WHERE user_id = 1 ORDER BY id DESC").fetchone()[0] == \
        "reauthentication_required"
    assert db.execute("SELECT status FROM mcf_session WHERE user_id = 2").fetchone()[0] == "missing"
    assert apply.finish_run(db, run_id, outcome["counts"], outcome["error"], False) == "partial"


def test_signed_out_on_the_first_lead_fails_the_run_with_zero_attempts(db, browser):
    _lead(db, "signed_out")
    run_id = _run(db)
    outcome = apply.run_batch(db, 1, run_id, browser, CONFIG)
    assert outcome["counts"] == {} and _apps(db, run_id) == {}
    assert apply.finish_run(db, run_id, outcome["counts"], outcome["error"], False) == "failed"


def test_queue_is_scoped_to_the_owner(db):
    """STRAT-SILO-08 — each user's queue holds only that user's open TOAPPLY leads."""
    mine, theirs = _lead(db, "success"), _lead(db, "success", uid=2, track_id=7)
    assert [q["id"] for q in apply.queue(db, 1)] == [mine]
    assert [(q["id"], q["cv_label"]) for q in apply.queue(db, 2)] == [(theirs, "S-1")]


def _stage_session(db, secrets_dir: str, uid: int = 1) -> None:
    os.makedirs(secrets_dir, exist_ok=True)
    with open(os.path.join(secrets_dir, f"mcf_session_{uid}.json"), "w", encoding="utf-8") as handle:
        json.dump({"cookies": [], "origins": []}, handle)
    db.execute("UPDATE mcf_session SET status = 'valid', cookie_ref = ? WHERE user_id = ?",
               (f"mcf_session_{uid}.json", uid))
    db.commit()


def test_invalid_session_aborts_before_any_row_or_browser(db, tmp_path, monkeypatch):
    """11.TC.20 — a missing or expired session raises the session conflict; no run_log or application row is
    written, and no browser is created."""
    monkeypatch.setattr(apply.threading, "Thread", lambda **kw: pytest.fail("a worker was started"))
    _lead(db, "success")
    config = Config(db_path="unused", secrets_dir=str(tmp_path))
    counts = [db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("run_log", "application")]
    for status in ("missing", "expired"):
        db.execute("UPDATE mcf_session SET status = ? WHERE user_id = 1", (status,))
        db.commit()
        with pytest.raises(Conflict) as info:
            apply.start_run(db, config, 1)
        assert info.value.message == apply.SESSION_INVALID_MESSAGE
    # a `valid` row whose storage file is gone is reconciled to missing first (11.IS.01)
    db.execute("UPDATE mcf_session SET status = 'valid', cookie_ref = 'mcf_session_1.json' WHERE user_id = 1")
    db.commit()
    with pytest.raises(Conflict):
        apply.start_run(db, config, 1)
    assert [db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("run_log", "application")] == counts


def test_in_flight_apply_run_answers_run_in_flight(db, tmp_path, monkeypatch):
    """11.TC.20 — a second trigger while an apply run is running names the running id."""
    monkeypatch.setattr(apply.threading, "Thread", lambda **kw: pytest.fail("a worker was started"))
    _stage_session(db, str(tmp_path))
    running = _run(db)
    with pytest.raises(RunInFlight) as info:
        apply.start_run(db, Config(db_path="unused", secrets_dir=str(tmp_path)), 1)
    assert info.value.extra == {"run_id": running}
    assert info.value.message == "an apply run is already in progress"


def test_worker_thread_runs_the_batch_to_a_terminal_status(isolated_db, tmp_path):
    """Workflow step 09 — the background worker, run synchronously: a seeded queue (lead 1 success on override cv
    2, lead 20 questionnaire, per the corpus routes) ends `success` with counts equal to its own rows."""
    db = get_connection(isolated_db)
    search.reconcile_orphaned_runs(db)
    config = Config(db_path=isolated_db, secrets_dir=str(tmp_path), apply_poll_retries=2, apply_poll_delay_s=0.01,
                    mcf_fixture_scenario="default")
    _stage_session(db, str(tmp_path))
    run_id = _run(db)
    # its own thread, as start_run spawns it: Playwright's sync API refuses a second instance on a thread that
    # already runs one, and this module's `browser` fixture may hold one on pytest's thread (11.IS.13)
    worker = threading.Thread(target=apply._run_apply, args=(config, run_id, 1, str(tmp_path / "mcf_session_1.json")))
    worker.start()
    worker.join(timeout=60)
    run = dict(db.execute("SELECT * FROM run_log WHERE id = ?", (run_id,)).fetchone())
    apps = _apps(db, run_id)
    assert run["status"] == "success" and run["ended_at"] and run["error_detail"] is None, run
    assert json.loads(run["outcome_counts"]) == {"applied": 1, "questionnaire_required": 1}, \
        [a["error_detail"] for a in apps.values()]
    assert {(a["lead_id"], a["cv_id"], a["status"]) for a in apps.values()} == {
        (1, 2, "applied"), (20, 1, "questionnaire_required")}
    db.close()


def test_worker_failure_ends_the_run_failed_with_the_exception(isolated_db, tmp_path, monkeypatch):
    """Run-level failure 05 — an exception outside any one lead ends the run `failed` with its type and message."""
    db = get_connection(isolated_db)
    search.reconcile_orphaned_runs(db)
    run_id = _run(db)

    def broken(*args, **kwargs):
        raise RuntimeError("database is locked")

    monkeypatch.setattr(apply, "run_batch", broken)
    apply._run_apply(Config(db_path=isolated_db, secrets_dir=str(tmp_path)), run_id, 1, None)
    run = dict(db.execute("SELECT * FROM run_log WHERE id = ?", (run_id,)).fetchone())
    assert (run["status"], run["error_detail"]) == ("failed", "RuntimeError: database is locked")
    db.close()


def test_a_load_failure_does_not_break_the_next_leads_navigation(db, browser):
    """11.IS.12 — a failed posting load is followed by a clean load of the next lead in the same browser."""
    gone, fine = _lead(db, "post_unavailable"), _lead(db, "success")
    run_id = _run(db)
    apply.run_batch(db, 1, run_id, browser, CONFIG)
    apps = _apps(db, run_id)
    assert (apps[gone]["status"], apps[fine]["status"]) == ("post_unavailable", "applied")


def test_live_mode_without_the_submission_flag_is_refused(db, tmp_path, monkeypatch):
    """11.IS.14 — MCF_MODE=live alone never starts a live apply: preflight answers 409 before any row, and the
    seam itself refuses to build a live browser for a direct caller."""
    from easymcf.automation.apply_browser import LiveApplyNotConfirmed, get_browser

    monkeypatch.setattr(apply.threading, "Thread", lambda **kw: pytest.fail("a worker was started"))
    _stage_session(db, str(tmp_path))
    live = Config(db_path="unused", secrets_dir=str(tmp_path), mcf_mode="live", apply_live_submit=False)
    runs = db.execute("SELECT COUNT(*) FROM run_log").fetchone()[0]
    with pytest.raises(Conflict) as info:
        apply.start_run(db, live, 1)
    assert "APPLY_LIVE_SUBMIT=1" in info.value.message
    assert db.execute("SELECT COUNT(*) FROM run_log").fetchone()[0] == runs
    with pytest.raises(LiveApplyNotConfirmed):
        get_browser(live)
    monkeypatch.delenv("APPLY_LIVE_SUBMIT", raising=False)
    assert Config().apply_live_submit is False


def test_an_unconfirmed_submit_is_left_for_the_human(db, browser):
    """11.IS.23 — a submit click MCF never confirms is not `applied`: the lead stays at TOAPPLY with the reason."""
    lead_id = _lead(db, "submit_unconfirmed")
    run_id = _run(db)
    apply.run_batch(db, 1, run_id, browser, CONFIG)
    app = _apps(db, run_id)[lead_id]
    assert (app["status"], _lead_row(db, lead_id)["stage"]) == ("questionnaire_required", "TOAPPLY")
    assert app["error_detail"] == ("final submit not confirmed: the posting never showed the already-applied message "
                                   "after 3 checks; check the application on MCF")
