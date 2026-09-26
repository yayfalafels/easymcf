"""10.TC.08 — the promotion half of the search-run pipeline oracle (10.EL.32/10.09).

The tracker's own 10.EL.32 assigns this file both a hard-coded promotion-oracle assertion
(10.TC.08, squarely STRAT-SILO-05 service-level pytest) and the `visible`/`text_equals` UI
checks 10.TC.09 describes for the Posts page's results table and its manual/already-a-lead
tags. That second half is internally inconsistent with this file's own `tests/backend/`
home: `visible`/`text_equals` are `ui_tester.py` JSON-case primitives, and this repo's actual
`tests/frontend/` convention (test_leads_ui.py, test_auth_ui.py) is Playwright-via-pytest, not
a JSON-driven ui_tester.py case file. 10.TC.09's checks live instead in
`tests/frontend/test_posts_ui.py`, matching that real convention — see 10.IS.08 in the
tracker's Validate section for the write-up of this split.

Mirrors test_search_pipeline.py's own pattern: services called directly against
FixtureMCFBrowser's known corpus (STRAT-SILO-05), no HTTP request, no Flask route. Expected
values are hard-coded from this milestone's Scope/Design sections and seed/05_search_profile.sql
(track 1's own min_salary), never imported from the code under test.
"""

from __future__ import annotations

import pytest

from easymcf import clock
from easymcf.automation.fixture import FixtureMCFBrowser
from easymcf.config import Config
from easymcf.db.connection import get_connection
from easymcf.services import search

pytestmark = pytest.mark.backend

# tests/fixtures/mcf/search/data_analyst_p0.html's own cards (same corpus/ids as
# test_search_pipeline.py), both open and fully detailed per that file's own
# test_open_fixture_postings_are_fully_detailed.
CARD_A_ID = "MyCareerFutures-a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1-2026-09-23"
CARD_B_ID = "MyCareerFutures-b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2-2026-09-21"

# seed/05_search_profile.sql: track 1's own min_salary, copied to expected_salary_sgd on
# promotion (Workflow 4 step 04).
TRACK_1_MIN_SALARY = 10000


@pytest.fixture()
def db(isolated_db):
    conn = get_connection(isolated_db)
    # Startup reconciliation runs before create_app() accepts requests; a direct service-layer
    # call bypasses that, so this fixture does what create_app() would before a test inserts
    # its own run_log rows for user 1 (same rationale as test_search_pipeline.py's own db fixture).
    search.reconcile_orphaned_runs(conn)
    yield conn
    conn.close()


@pytest.fixture()
def browser():
    return FixtureMCFBrowser(Config(mcf_fixture_scenario="default"))


@pytest.fixture(autouse=True)
def _pinned_today(fixed_clock):
    fixed_clock("2026-09-23 09:00:00")
    yield


def _new_run(db, track_id: int, user_id: int = 1) -> int:
    run_id = db.execute(
        "INSERT INTO run_log (run_type, user_id, track_id, started_at, ended_at, status, trigger_source) "
        "VALUES ('search', ?, ?, ?, ?, 'success', 'manual')",
        (user_id, track_id, clock.stamp(), clock.stamp()),
    ).lastrowid
    db.commit()
    return run_id


def _sweep_detail_promote(db, browser, track_id: int, user_id: int = 1) -> dict:
    run_id = _new_run(db, track_id, user_id)
    search.run_sweep(db, uid=user_id, track_id=track_id, run_id=run_id, browser=browser)
    search.run_detail_pass(db, run_id, browser)
    return search.promote_qualifying(db, uid=user_id, track_id=track_id)


def test_a_search_run_promotes_every_open_detailed_post_to_a_toapply_lead_with_the_profile_min_salary(db, browser):
    """10.TC.08/10.CK.08 — every post the run's track found that is open and detailed and has
    no lead is promoted under that track at TOAPPLY, carrying the profile's own min_salary as
    expected_salary_sgd."""
    counts = _sweep_detail_promote(db, browser, track_id=1)
    assert counts == {"promoted": 2, "promote_errors": 0}

    leads = db.execute(
        "SELECT post_id, track_id, user_id, stage, status, expected_salary_sgd FROM lead "
        "WHERE user_id = 1 AND post_id IN (?, ?) ORDER BY post_id",
        (CARD_A_ID, CARD_B_ID),
    ).fetchall()
    assert [row["post_id"] for row in leads] == [CARD_A_ID, CARD_B_ID]
    for row in leads:
        assert row["track_id"] == 1
        assert row["stage"] == "TOAPPLY"
        assert row["status"] == "OPEN"
        assert row["expected_salary_sgd"] == TRACK_1_MIN_SALARY

    match_rows = db.execute(
        "SELECT post_id, match_score, score_method FROM match_score WHERE track_id = 1 AND post_id IN (?, ?)",
        (CARD_A_ID, CARD_B_ID),
    ).fetchall()
    assert all(row["match_score"] == 1.0 and row["score_method"] == "search_match_v1" for row in match_rows)


def test_a_second_run_over_the_same_posts_creates_no_second_lead(db, browser):
    """10.TC.08/10.CK.08 — a second run over posts the first run already promoted leaves the
    lead count unchanged: promote_qualifying's NOT EXISTS guard (Workflow 4 step 01) is the
    actual mechanism, exercised here across two full sweep+detail+promote passes rather than
    by calling promote_qualifying twice on the same connection state."""
    first = _sweep_detail_promote(db, browser, track_id=1)
    assert first["promoted"] == 2

    second = _sweep_detail_promote(db, browser, track_id=1)
    assert second == {"promoted": 0, "promote_errors": 0}

    lead_count = db.execute(
        "SELECT COUNT(*) FROM lead WHERE user_id = 1 AND post_id IN (?, ?)", (CARD_A_ID, CARD_B_ID)
    ).fetchone()[0]
    assert lead_count == 2
