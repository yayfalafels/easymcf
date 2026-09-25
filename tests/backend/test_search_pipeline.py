"""10.EL.29 — oracle for easymcf/services/search.py (10.TC.17..20), called directly
against easymcf/automation/fixture.py's known corpus (STRAT-SILO-05): no HTTP request,
no Flask route, no real browser. Expected values are hand-coded from this milestone's own
Scope/Design sections and tests/fixtures/mcf/'s own source files, never imported from the
code under test (010.08's oracle precedent).
"""

from __future__ import annotations

import pytest

from easymcf import clock
from easymcf.automation.fixture import FixtureMCFBrowser
from easymcf.config import Config
from easymcf.db.connection import get_connection
from easymcf.services import search

pytestmark = pytest.mark.backend

# tests/fixtures/mcf/search/data_analyst_p0.html and data_engineer_p0.html's own urlids,
# hand-computed against post_id()'s source-urlid[-32:]-posted_date rule with "today" pinned
# to 2026-09-23 (parse_cards resolves "today"/"2 days ago"/"yesterday" against that date).
CARD_A_ID = "MyCareerFutures-a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1-2026-09-23"
CARD_B_ID = "MyCareerFutures-b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2-2026-09-21"
CARD_C_ID = "MyCareerFutures-c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3-2026-09-22"


@pytest.fixture()
def db(isolated_db):
    conn = get_connection(isolated_db)
    # The seed carries a deliberately "running" run_log row (user 1, track 1) to exercise
    # startup reconciliation elsewhere; a direct service-layer call here bypasses
    # create_app()'s own reconcile_orphaned_runs(), so this fixture does the same thing
    # create_app() would before letting a test insert its own run_log rows for user 1.
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
    """A plain run_log row for run_sweep/run_detail_pass's own FK, not start_run's state
    machine (that's exercised elsewhere, via runs_search.json/test_scheduler.py) — inserted
    already 'success' so a test that calls this more than once for the same user never
    collides with ARCH-RUN-03's one-running-search-per-user partial unique index."""
    run_id = db.execute(
        "INSERT INTO run_log (run_type, user_id, track_id, started_at, ended_at, status, trigger_source) "
        "VALUES ('search', ?, ?, ?, ?, 'success', 'manual')",
        (user_id, track_id, clock.stamp(), clock.stamp()),
    ).lastrowid
    db.commit()
    return run_id


def test_dedup_id_matches_hand_computed_fixture_values(db, browser):
    """10.TC.17 — track 1's own profile keyword is "Data Analyst" (seed/05_search_profile.sql);
    its page 0 fixture (data_analyst_p0.html) carries cards A and B."""
    run_id = _new_run(db, track_id=1)
    counts = search.run_sweep(db, uid=1, track_id=1, run_id=run_id, browser=browser)
    assert counts == {"keywords": 1, "pages": 2, "cards": 2, "new_posts": 2, "existing_posts": 0}
    ids = {row["id"] for row in db.execute("SELECT id FROM post").fetchall()}
    assert CARD_A_ID in ids and CARD_B_ID in ids


def test_overlapping_cards_across_keywords_and_shared_by_two_tracks(db, browser):
    """Fixture corpus design note: card B is served by both the "Data Analyst" (track 1,
    seed user 1) and "Data Engineer" (track 3, same user's own second track) keyword
    searches — dedup keeps exactly one `post` row, and each track gets its own pairing."""
    run1 = _new_run(db, track_id=1)
    search.run_sweep(db, uid=1, track_id=1, run_id=run1, browser=browser)
    run2 = _new_run(db, track_id=3)
    counts2 = search.run_sweep(db, uid=1, track_id=3, run_id=run2, browser=browser)
    assert counts2["new_posts"] == 1 and counts2["existing_posts"] == 1  # card C new, card B already known
    assert db.execute("SELECT COUNT(*) FROM post WHERE id = ?", (CARD_B_ID,)).fetchone()[0] == 1
    pairings = {row["track_id"] for row in db.execute(
        "SELECT track_id FROM post_track WHERE post_id = ?", (CARD_B_ID,)).fetchall()}
    assert pairings == {1, 3}


def test_closed_fixture_posting_leaves_other_detail_fields_null(db, browser):
    """10.TC.12/.18 — card C's detail page (card_c_closed.html) reads "Closed on ...";
    parse_detail short-circuits, so mcf_ref/closing_date/applicants/industry/description
    stay null and only is_open flips (mcf_profile.py's get_profileRecord() short-circuit)."""
    run_id = _new_run(db, track_id=3)
    search.run_sweep(db, uid=1, track_id=3, run_id=run_id, browser=browser)
    detail_counts = search.run_detail_pass(db, run_id, browser)
    assert detail_counts["closed"] == 1
    row = db.execute("SELECT * FROM post WHERE id = ?", (CARD_C_ID,)).fetchone()
    assert row["is_open"] == 0
    assert row["mcf_ref"] is None
    assert row["closing_date"] is None
    assert row["applicants"] is None
    assert row["industry_classification"] is None
    assert row["description"] is None


def test_open_fixture_postings_are_fully_detailed(db, browser):
    run_id = _new_run(db, track_id=1)
    search.run_sweep(db, uid=1, track_id=1, run_id=run_id, browser=browser)
    detail_counts = search.run_detail_pass(db, run_id, browser)
    assert detail_counts == {"detailed": 2, "closed": 0, "detail_errors": 0}
    row = db.execute("SELECT * FROM post WHERE id = ?", (CARD_A_ID,)).fetchone()
    assert row["mcf_ref"] == "MCF-2026-0001234"
    assert row["closing_date"] == "2026-09-30"
    assert row["applicants"] == 12
    assert row["industry_classification"] == "Information Technology"
    assert row["description"] == "Full job description text for Data Analyst I at Acme Analytics."


def test_every_scraped_match_score_row_is_fixed_at_search_match_v1(db, browser):
    """10.TC.20 — every card a track's own search returns writes match_score=1.0,
    score_method='search_match_v1'."""
    run_id = _new_run(db, track_id=1)
    search.run_sweep(db, uid=1, track_id=1, run_id=run_id, browser=browser)
    rows = db.execute("SELECT * FROM match_score WHERE track_id = 1 AND post_id IN (?, ?)",
                       (CARD_A_ID, CARD_B_ID)).fetchall()
    assert len(rows) == 2
    assert all(row["match_score"] == 1.0 and row["score_method"] == "search_match_v1" for row in rows)


def test_manual_post_promotes_unconditionally_under_the_named_track(db):
    """10.TC.19 — a manual post is promoted under whichever track the request names, with
    no relevance check standing in the way (REQ-SRCH-07), carrying match_score=1.0 and
    score_method='manual_v1' (10.TC.20's manual-entry half)."""
    result = search.add_manual_post(db, uid=1, track_id=1, body={
        "position_title": "Manual Oracle Role", "company_name": "Oracle Testing Co",
        "posted_date": "2026-09-20",
    })
    assert result["lead_id"] is not None
    lead = db.execute("SELECT * FROM lead WHERE id = ?", (result["lead_id"],)).fetchone()
    assert lead["track_id"] == 1 and lead["stage"] == "TOAPPLY" and lead["user_id"] == 1
    pid = result["post"]["id"]
    assert result["post"]["src_method"] == "manual"
    match_score = db.execute(
        "SELECT * FROM match_score WHERE post_id = ? AND track_id = 1", (pid,)
    ).fetchone()
    assert match_score["match_score"] == 1.0 and match_score["score_method"] == "manual_v1"
    post_track = db.execute(
        "SELECT search_match FROM post_track WHERE post_id = ? AND track_id = 1", (pid,)
    ).fetchone()
    assert post_track["search_match"] == 0
