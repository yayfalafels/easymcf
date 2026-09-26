"""Tier 1b/2 — Posts screen (page 3) and the Manual Post Entry dialog (page 4) in a real
browser (10.TC.09, 10.CK.07/.08/.09).

10.EL.32 assigns the `visible`/`text_equals` UI checks 10.TC.09 describes to
tests/backend/test_search_promotion.py, "in the same file" as 10.TC.08's backend promotion
oracle — an internally inconsistent instruction, since `visible`/`text_equals` are
`ui_tester.py` JSON-case primitives, not pytest assertions, and this repo's actual
tests/frontend/ convention (test_leads_ui.py, test_auth_ui.py) is Playwright-via-pytest, not a
JSON-driven ui_tester.py case. This file carries 10.TC.09 instead, following that real
convention; see 10.IS.08 in the tracker's Validate section.

Each test drives the UI, then reads the SQLite file directly, so the assertion does not depend
on what the page says about its own write. The module spawns one real `python -m easymcf` on
its own freshly seeded database (tests/_browser_support.spawn_app).
"""

from __future__ import annotations

import os
import sqlite3
import sys

import pytest

_TESTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REPO_ROOT = os.path.dirname(_TESTS_DIR)
sys.path.insert(0, _REPO_ROOT)
sys.path.insert(0, os.path.join(_REPO_ROOT, "scripts"))

from initdb import apply_schema  # noqa: E402
from render_seed import PUBLIC_DEFAULTS  # noqa: E402
from resetdb import apply_seed  # noqa: E402
from tests._browser_support import sign_in, spawn_app, terminate_app  # noqa: E402

pytestmark = pytest.mark.frontend

# seed/08_post.sql / seed/09_post_track.sql / seed/11_lead.sql, track 1 (Data Analyst, user 1).
# clock.today() is pinned to "now" by the running app itself (no fixed_clock in this browser
# tier), so these ids/tags are asserted against the seed's own fixed posted_date values instead
# of a computed age, matching test_leads_ui.py's own style of reading known seed rows directly.
MANUAL_SEED_POST = "manual-seed-1"          # src_method='manual', lead_id=2 (APPLIED) -> both tags
SCRAPED_LEAD_POST = "MyCareerFutures-771e413d7bc340c16dfeac6ba88503ff"   # lead_id=1 -> lead tag, no manual tag
SCRAPED_NO_LEAD_POST = "MyCareerFutures-ba8ace4ad4d006a1f179ace0860a9657"  # lead_id null -> neither tag


@pytest.fixture(scope="module")
def ui_app(tmp_path_factory):
    db_path = str(tmp_path_factory.mktemp("easymcf-posts-ui-db") / "easymcf.db")
    apply_schema(db_path)
    apply_seed(db_path, PUBLIC_DEFAULTS)
    proc, base_url = spawn_app(db_path)
    try:
        yield base_url, db_path
    finally:
        terminate_app(proc)


@pytest.fixture()
def page(browser, ui_app):
    """A page signed in as seeded user 1 through the real sign-in endpoint."""
    context = browser.new_context()
    pg = context.new_page()
    sign_in(pg, ui_app[0])
    yield pg
    context.close()


def _rows(db_path: str, sql: str, *args):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(sql, args).fetchall()
    finally:
        conn.close()


def _visible(page, testid: str, timeout: int = 10_000):
    locator = page.locator(f'[data-testid="{testid}"]')
    locator.wait_for(state="visible", timeout=timeout)
    return locator


def _goto_track1(page, base_url):
    page.goto(base_url + "/posts")
    _visible(page, "posts-heading")
    page.wait_for_function("document.querySelectorAll('[data-testid=\"posts-track-select\"] option').length > 1")
    page.select_option('[data-testid="posts-track-select"]', label="Data Analyst / mid")
    _visible(page, "posts-results-table")


def test_posts_page_renders_filter_controls_and_results_table_with_the_default_age_filter(page, ui_app):
    """10.TC.09/10.CK.07 — the track selector, age filter, run/add controls and results table
    all render, populated live from the real backend API (the joined GET /api/v1/post read)."""
    base_url, _ = ui_app
    _goto_track1(page, base_url)
    for testid in ("posts-track-select", "posts-filter-max-age", "posts-run-search-btn",
                   "posts-add-manual-btn", "posts-results-table"):
        assert _visible(page, testid).count() == 1
    page.wait_for_function(f"!!document.querySelector('[data-testid=\"posts-row-{MANUAL_SEED_POST}\"]')")


def test_a_manual_post_row_carries_the_manual_and_already_a_lead_tags(page, ui_app):
    """10.CK.07 — the manual tag and the already-a-lead indicator both render for a manually
    entered, already-promoted seed row, at the profile's own default age filter."""
    base_url, _ = ui_app
    _goto_track1(page, base_url)
    row = _visible(page, f"posts-row-{MANUAL_SEED_POST}")
    assert row.count() == 1
    assert _visible(page, f"posts-row-{MANUAL_SEED_POST}-manual-tag").inner_text() == "manual"
    assert _visible(page, f"posts-row-{MANUAL_SEED_POST}-lead-tag").inner_text() == "already a lead"


def test_widening_the_age_filter_reveals_scraped_rows_including_one_with_no_lead_tag(page, ui_app):
    """10.CK.07 — the age filter reloads the list; a scraped (non-manual) row that a run
    promoted shows the lead tag and no manual tag, and a scraped row with no lead on it shows
    neither tag — the tags are independent, not implied by src_method alone."""
    base_url, _ = ui_app
    _goto_track1(page, base_url)
    assert page.locator(f'[data-testid="posts-row-{SCRAPED_LEAD_POST}"]').count() == 0  # older than 4 weeks

    page.fill('[data-testid="posts-filter-max-age"]', "60")
    page.wait_for_function(f"!!document.querySelector('[data-testid=\"posts-row-{SCRAPED_LEAD_POST}\"]')")

    assert page.locator(f'[data-testid="posts-row-{SCRAPED_LEAD_POST}-manual-tag"]').count() == 0
    assert _visible(page, f"posts-row-{SCRAPED_LEAD_POST}-lead-tag").inner_text() == "already a lead"

    assert page.locator(f'[data-testid="posts-row-{SCRAPED_NO_LEAD_POST}"]').count() == 1
    assert page.locator(f'[data-testid="posts-row-{SCRAPED_NO_LEAD_POST}-manual-tag"]').count() == 0
    assert page.locator(f'[data-testid="posts-row-{SCRAPED_NO_LEAD_POST}-lead-tag"]').count() == 0


def test_run_search_shows_the_running_status_then_resolves_and_reloads_the_list(page, ui_app):
    """10.CK.05/.07 — REQ-FE-02: the async run/poll state surfaces on screen, not only in a
    log, and the results list reloads once the run reaches a terminal status."""
    base_url, db_path = ui_app
    _goto_track1(page, base_url)
    page.click('[data-testid="posts-run-search-btn"]')
    _visible(page, "posts-run-status")
    page.wait_for_function(
        "document.querySelector('[data-testid=\"posts-run-search-btn\"]') "
        "&& !document.querySelector('[data-testid=\"posts-run-search-btn\"]').disabled",
        timeout=15_000,
    )
    assert page.locator('[data-testid="posts-run-status"]').count() == 0
    rows = _rows(db_path, "SELECT status, trigger_source FROM run_log WHERE track_id = 1 ORDER BY id DESC LIMIT 1")
    assert rows[0][0] in ("success", "partial") and rows[0][1] == "manual"


def test_manual_post_entry_creates_a_tagged_lead_and_a_duplicate_shows_the_inline_error(page, ui_app):
    """10.TC.28/10.CK.09 — REQ-SRCH-07: the dialog's golden path (a new posting appears tagged
    manual and already a lead) and its error path (a 409 duplicate shows inline, per page 4's
    own design, not only as the global toast)."""
    base_url, db_path = ui_app
    _goto_track1(page, base_url)
    page.click('[data-testid="posts-add-manual-btn"]')
    _visible(page, "manual-post-dialog")
    page.select_option('[data-testid="manual-post-track-select"]', label="Data Analyst / mid")
    page.fill('[data-testid="manual-post-title"]', "UI test manual analyst role")
    page.fill('[data-testid="manual-post-company"]', "UI Test Co")
    page.fill('[data-testid="manual-post-posted-date"]', "2026-09-19")
    page.click('[data-testid="manual-post-save"]')
    page.locator('[data-testid="manual-post-dialog"]').wait_for(state="detached", timeout=8_000)

    page.wait_for_function(
        "[...document.querySelectorAll('[data-testid^=\"posts-row-\"]')]"
        ".some(e => e.innerText.includes('UI test manual analyst role'))",
        timeout=8_000,
    )
    lead = _rows(
        db_path,
        "SELECT l.id, l.stage, p.src_method FROM lead l JOIN post p ON p.id = l.post_id WHERE p.position_title = ?",
        "UI test manual analyst role",
    )
    assert lead and lead[0][1] == "TOAPPLY" and lead[0][2] == "manual"
    post_id = _rows(
        db_path, "SELECT id FROM post WHERE position_title = ?", "UI test manual analyst role"
    )[0][0]
    assert _visible(page, f"posts-row-{post_id}-manual-tag").inner_text() == "manual"
    assert _visible(page, f"posts-row-{post_id}-lead-tag").inner_text() == "already a lead"

    page.click('[data-testid="posts-add-manual-btn"]')
    _visible(page, "manual-post-dialog")
    page.select_option('[data-testid="manual-post-track-select"]', label="Data Analyst / mid")
    page.fill('[data-testid="manual-post-title"]', "UI test manual analyst role")
    page.fill('[data-testid="manual-post-company"]', "UI Test Co")
    page.fill('[data-testid="manual-post-posted-date"]', "2026-09-19")
    page.click('[data-testid="manual-post-save"]')
    error = _visible(page, "manual-post-error")
    assert "already visible" in error.inner_text()
    assert _visible(page, "error-toast").count() == 1
    lead_count = _rows(
        db_path, "SELECT COUNT(*) FROM lead l JOIN post p ON p.id = l.post_id WHERE p.position_title = ?",
        "UI test manual analyst role",
    )[0][0]
    assert lead_count == 1
