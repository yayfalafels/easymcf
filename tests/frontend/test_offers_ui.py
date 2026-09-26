"""09.13.CK.09 — the offer dialog, the Offers page, the OFFER cards, and re-open, in a real browser.

The tests share one seeded database and run in file order: the dialog test moves lead 4 to OFFER, the
page test settles that offer, the card test rejects lead 5's open offer, and the re-open test re-opens lead 5.
"""

from __future__ import annotations

import os
import sqlite3
import sys
from datetime import date

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


@pytest.fixture(scope="module")
def ui_app(tmp_path_factory):
    db_path = str(tmp_path_factory.mktemp("easymcf-offers-db") / "easymcf.db")
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


def _poll(db_path: str, sql: str, expected, *args, timeout_s: float = 8.0):
    import time
    end = time.time() + timeout_s
    while time.time() < end:
        rows = _rows(db_path, sql, *args)
        if rows == expected:
            return rows
        time.sleep(0.2)
    return _rows(db_path, sql, *args)


def _open_lead(page, base_url: str, lead_id: int, tab: str):
    page.goto(base_url + "/leads")
    _visible(page, "leads-tab-toapply")
    page.click(f'[data-testid="leads-tab-{tab}"]')
    _visible(page, f"lead-row-{lead_id}")
    page.click(f'[data-testid="lead-row-{lead_id}"]')
    return _visible(page, "lead-detail")


def test_move_to_offer_opens_the_dialog_with_its_defaults_and_attaches_the_offer(page, ui_app):
    base_url, db_path = ui_app
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO post (id, source, position_title, company_name, is_open, src_method) "
                 "VALUES ('zebra-post', 'UI', 'Zebra wrangler', 'Zoo Co', 1, 'manual')")
    conn.execute("INSERT INTO lead (user_id, post_id, track_id, status, stage, position_title, company_name, deadline, "
                 "expected_salary_sgd, created_at, updated_at) VALUES (1, 'zebra-post', 1, 'OPEN', 'INTERVIEW', 'Zebra wrangler', "
                 "'Zoo Co', '2026-12-31', 9000, '2026-09-19 07:00:00', '2026-09-19 07:00:00')")
    conn.commit()
    conn.close()
    title, deadline = _rows(db_path, "SELECT p.position_title, l.deadline FROM lead l JOIN post p ON p.id = l.post_id WHERE l.id = 4")[0]
    _open_lead(page, base_url, 4, "interviews")
    assert "OFFER" in _visible(page, "lead-detail-advance").inner_text().upper()
    page.click('[data-testid="lead-detail-advance"]')
    _visible(page, "offer-dialog")
    page.wait_for_function("document.querySelectorAll('[data-testid=\"offer-lead\"] option').length >= 2")
    assert page.input_value('[data-testid="offer-date"]') == date.today().isoformat()
    assert page.input_value('[data-testid="offer-amount"]') == "10000"
    assert page.input_value('[data-testid="offer-deadline"]') == deadline
    assert title in page.locator('[data-testid="offer-lead"] option:checked').inner_text()
    options = page.locator('[data-testid="offer-lead"] option').all_inner_texts()
    assert len(options) == 2 and any("Zebra wrangler" in o for o in options)
    listed = "document.querySelectorAll('[data-testid=\"offer-lead\"] option:not([value=\"?\"])').length"
    page.fill('[data-testid="offer-lead-search"]', "zebra")
    page.wait_for_function(f"{listed} === 1")
    page.fill('[data-testid="offer-lead-search"]', "")
    page.wait_for_function(f"{listed} === 2")
    page.select_option('[data-testid="offer-lead"]', label=next(o for o in options if title in o))
    page.fill('[data-testid="offer-amount"]', "12500")
    page.click('[data-testid="offer-save"]')
    assert _poll(db_path, "SELECT lead_id, amount_sgd, status FROM offer WHERE lead_id = 4", [(4, 12500, "open")]) == [(4, 12500, "open")]
    assert _rows(db_path, "SELECT stage FROM lead WHERE id = 4") == [("OFFER",)]
    _visible(page, "lead-detail-offer")
    assert page.locator('[data-testid="lead-detail-close"]').count() == 0
    assert page.locator('[data-testid="lead-detail-advance"]').count() == 0


def test_offers_page_lists_the_history_filters_edits_and_settles_an_open_offer(page, ui_app):
    base_url, db_path = ui_app
    page.goto(base_url + "/leads")
    _visible(page, "nav-offers")
    page.click('[data-testid="nav-offers"]')
    _visible(page, "offers-table")
    for offer_id in (1, 2, 3, 4):
        _visible(page, f"offer-row-{offer_id}")
    assert [page.locator(f'[data-testid="offer-status-{i}"]').inner_text() for i in (1, 2, 3, 4)] == ["rejected", "open", "accepted", "open"]
    assert page.locator('[data-testid="offer-accept-1"]').count() == 0
    page.select_option('[data-testid="offers-status-filter"]', value="accepted")
    page.wait_for_function("document.querySelectorAll('[data-testid^=\"offer-row-\"]').length === 1")
    _visible(page, "offer-row-3")
    page.select_option('[data-testid="offers-status-filter"]', value="")
    page.wait_for_function("document.querySelectorAll('[data-testid^=\"offer-row-\"]').length === 4")
    page.fill('[data-testid="offer-edit-amount-4"]', "13000")
    page.click('[data-testid="offer-save-4"]')
    assert _poll(db_path, "SELECT amount_sgd FROM offer WHERE id = 4", [(13000,)]) == [(13000,)]
    page.click('[data-testid="offer-accept-4"]')
    _visible(page, "confirm-modal")
    page.click('[data-testid="confirm-yes"]')
    assert _poll(db_path, "SELECT status FROM offer WHERE id = 4", [("accepted",)]) == [("accepted",)]
    assert _rows(db_path, "SELECT status, close_reason FROM lead WHERE id = 4") == [("CLOSED", "offer_accepted")]
    page.wait_for_function("document.querySelectorAll('[data-testid=\"offer-accept-4\"]').length === 0")


def test_offer_cards_show_the_offer_amount_and_settle_through_their_buttons(page, ui_app):
    base_url, db_path = ui_app
    page.goto(base_url + "/leads")
    _visible(page, "leads-tab-offers")
    page.click('[data-testid="leads-tab-offers"]')
    assert _visible(page, "lead-salary-5").inner_text() == "S$ 12,000"
    assert [page.locator(f'[data-testid="offer-{a}-2"]').inner_text().upper() for a in ("accept", "reject", "withdraw")] == ["ACCEPT", "REJECT", "WITHDRAWN"]
    page.click('[data-testid="offer-reject-2"]')
    _visible(page, "confirm-modal")
    page.click('[data-testid="confirm-yes"]')
    assert _poll(db_path, "SELECT status FROM offer WHERE id = 2", [("rejected",)]) == [("rejected",)]
    assert _rows(db_path, "SELECT status, close_reason FROM lead WHERE id = 5") == [("CLOSED", "rejected")]


def test_a_lead_closed_from_an_offer_reopens_at_interview(page, ui_app):
    base_url, db_path = ui_app
    _open_lead(page, base_url, 5, "closed")
    page.click('[data-testid="lead-detail-reopen"]')
    assert _poll(db_path, "SELECT status, stage, close_reason FROM lead WHERE id = 5", [("OPEN", "INTERVIEW", None)]) == [("OPEN", "INTERVIEW", None)]
    assert "OFFER" in _visible(page, "lead-detail-advance").inner_text().upper()
    assert page.locator('[data-testid="lead-detail-reopen"]').count() == 0


def test_a_lead_closed_from_another_stage_offers_no_reopen(page, ui_app):
    base_url, _ = ui_app
    _open_lead(page, base_url, 7, "closed")
    assert page.locator('[data-testid="lead-detail-reopen"]').count() == 0
