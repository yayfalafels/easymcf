"""Tier 1b/2 — Tracks, Leads, and Lead Detail screens in a real browser (09.TC.08 to .10).

Each test drives the UI, then reads the SQLite file directly, so the assertion
does not depend on what the page says about its own write. The module spawns
one real `python -m easymcf` on its own freshly seeded database.
"""

from __future__ import annotations

import os
import sqlite3
import sys
import uuid

import pytest

_TESTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REPO_ROOT = os.path.dirname(_TESTS_DIR)
sys.path.insert(0, _REPO_ROOT)
sys.path.insert(0, os.path.join(_REPO_ROOT, "scripts"))

from initdb import apply_schema  # noqa: E402
from resetdb import apply_seed  # noqa: E402
from tests._browser_support import spawn_app, terminate_app  # noqa: E402

pytestmark = pytest.mark.frontend


@pytest.fixture(scope="module")
def ui_app(tmp_path_factory):
    db_path = str(tmp_path_factory.mktemp("easymcf-ui-db") / "easymcf.db")
    apply_schema(db_path)
    apply_seed(db_path)
    proc, base_url = spawn_app(db_path)
    try:
        yield base_url, db_path
    finally:
        terminate_app(proc)


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


def test_tracks_create_edit_archive_unarchive(page, ui_app):
    base_url, db_path = ui_app
    page.goto(base_url + "/tracks")
    _visible(page, "track-row-1")
    assert page.locator('[data-testid^="track-row-"]').count() == 5

    page.select_option('[data-testid="track-role-select"]', label="Data Engineer")
    page.fill('[data-testid="track-seniority-input"]', "senior")
    page.click('[data-testid="track-save"]')
    _visible(page, "track-row-7")
    assert _rows(db_path, "SELECT user_id, role_id, seniority, default_cv_id, is_active FROM track WHERE id = 7") == [(1, 3, "senior", None, 1)]

    page.click('[data-testid="track-edit-7"]')
    page.fill('[data-testid="track-seniority-input"]', "lead")
    page.click('[data-testid="track-save"]')
    page.wait_for_function("document.querySelector('[data-testid=\"track-row-7\"]').innerText.includes('lead')")
    assert _rows(db_path, "SELECT seniority FROM track WHERE id = 7") == [("lead",)]

    page.click('[data-testid="track-archive-7"]')
    page.locator('[data-testid="track-row-7"]').wait_for(state="detached", timeout=10_000)
    assert _rows(db_path, "SELECT is_active FROM track WHERE id = 7") == [(0,)]

    page.check('[data-testid="tracks-show-archived"]')
    _visible(page, "track-row-7")
    page.click('[data-testid="track-unarchive-7"]')
    _visible(page, "track-archive-7")
    assert _rows(db_path, "SELECT is_active FROM track WHERE id = 7") == [(1,)]


def test_tracks_form_shows_track_fields_only(page, ui_app):
    base_url, _ = ui_app
    page.goto(base_url + "/tracks")
    _visible(page, "track-form")
    assert page.locator('[data-testid="track-form"] [data-testid^="search-profile-"]').count() == 0


TAB_COUNTS = {"toapply": 1, "applied": 1, "callbacks": 1, "interviews": 1, "offers": 1, "closed": 8}


def test_leads_tabs_follow_the_seeded_stages(page, ui_app):
    base_url, db_path = ui_app
    page.goto(base_url + "/leads")
    _visible(page, "lead-row-1")
    assert page.locator('[data-testid^="leads-tab-"]').count() == 6
    for key, expected in TAB_COUNTS.items():
        page.click(f'[data-testid="leads-tab-{key}"]')
        page.wait_for_function(f"document.querySelectorAll('[data-testid^=\"lead-row-\"]').length === {expected}")
        assert f"({expected})" in page.locator(f'[data-testid="leads-tab-{key}"]').inner_text()
    stage_counts = dict(_rows(db_path, "SELECT stage, COUNT(*) FROM lead GROUP BY stage"))
    assert stage_counts["CLOSED"] == TAB_COUNTS["closed"] and stage_counts["TOAPPLY"] == TAB_COUNTS["toapply"]


def test_leads_track_filter(page, ui_app):
    base_url, _ = ui_app
    page.goto(base_url + "/leads")
    _visible(page, "lead-row-1")
    page.select_option('[data-testid="leads-track-filter"]', value="2")
    page.wait_for_function("document.querySelectorAll('[data-testid^=\"lead-row-\"]').length === 0")
    page.select_option('[data-testid="leads-track-filter"]', value="1")
    page.wait_for_function("document.querySelectorAll('[data-testid^=\"lead-row-\"]').length === 1")


def test_leads_search_and_pipeline_order(page, ui_app):
    base_url, _ = ui_app
    page.goto(base_url + "/leads")
    _visible(page, "lead-row-1")
    columns = page.locator('[data-testid^="leads-column-"]')
    assert columns.nth(0).get_attribute("data-testid") == "leads-column-TOAPPLY"
    page.fill('[data-testid="leads-search"]', "gen ai engineer")
    page.wait_for_function("document.querySelectorAll('[data-testid^=\"lead-row-\"]').length === 1")
    assert page.locator('[data-testid="lead-row-1"]').count() == 1


def test_expiry_warning_marks_leads_close_to_their_deadline(page, ui_app):
    base_url, db_path = ui_app
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE lead SET deadline = date('now', '+3 days') WHERE id = 1")
    conn.execute("UPDATE lead SET deadline = date('now', '+20 days') WHERE id = 2")
    conn.commit()
    conn.close()
    page.goto(base_url + "/leads")
    _visible(page, "lead-expiry-1")
    assert "warn" in (page.locator('[data-testid="lead-expiry-1"]').get_attribute("class") or "")
    assert "3 days left" in page.locator('[data-testid="lead-expiry-1"]').inner_text()
    page.click('[data-testid="leads-tab-applied"]')
    _visible(page, "lead-expiry-2")
    assert "warn" not in (page.locator('[data-testid="lead-expiry-2"]').get_attribute("class") or "")


def _open_lead(page, base_url: str, lead_id: int, tab: str = "toapply"):
    page.goto(base_url + "/leads")
    _visible(page, "leads-tab-toapply")
    page.click(f'[data-testid="leads-tab-{tab}"]')
    _visible(page, f"lead-row-{lead_id}")
    page.click(f'[data-testid="lead-row-{lead_id}"]')
    return _visible(page, "lead-detail")


def test_lead_detail_shows_the_lead_fields(page, ui_app):
    base_url, _ = ui_app
    _open_lead(page, base_url, 2, tab="applied")
    for field in ("title_override", "company_override", "deadline", "applied_date", "first_attempt_date", "last_contact_date"):
        _visible(page, f"lead-detail-field-{field}")
    assert page.locator('[data-testid="lead-detail-activity"]').count() >= 1
    assert page.locator('[data-testid="lead-detail-post-link"]').get_attribute("href").startswith("https://")


def test_activity_history_shows_stage_context(page, ui_app):
    base_url, _ = ui_app
    _open_lead(page, base_url, 3, tab="callbacks")
    page.locator('[data-testid="lead-detail-activity-stage"]').first.wait_for(state="visible", timeout=10_000)
    labels = page.locator('[data-testid="lead-detail-activity-stage"]').all_inner_texts()
    for expected in ("new → TOAPPLY", "TOAPPLY → APPLIED", "APPLIED → CALLBACK", "at CALLBACK"):
        assert expected in labels


def test_switching_leads_discards_unsaved_detail_edits(page, ui_app):
    base_url, db_path = ui_app
    _open_lead(page, base_url, 1)
    page.fill('[data-testid="lead-detail-field-title_override"]', "Do not save")
    page.click('[data-testid="leads-tab-applied"]')
    page.click('[data-testid="lead-row-2"]')
    detail = _visible(page, "lead-detail")
    assert "seed manual role" in detail.inner_text().lower()
    assert _rows(db_path, "SELECT title_override FROM lead WHERE id = 1") == [(None,)]


def _poll(db_path: str, sql: str, expected, timeout_s: float = 8.0, *args):
    import time
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        rows = _rows(db_path, sql, *args)
        if rows == expected:
            return rows
        time.sleep(0.2)
    return _rows(db_path, sql, *args)


def test_advance_stage_from_lead_detail(page, ui_app):
    base_url, db_path = ui_app
    _open_lead(page, base_url, 2, tab="applied")
    assert "CALLBACK" in _visible(page, "lead-detail-advance").inner_text()
    page.click('[data-testid="lead-detail-advance"]')
    assert _poll(db_path, "SELECT stage, status FROM lead WHERE id = 2", [("CALLBACK", "OPEN")]) == [("CALLBACK", "OPEN")]
    events = [r[0] for r in _rows(db_path, "SELECT event_type FROM lead_event WHERE lead_id = 2 ORDER BY id")]
    assert events[-1] in ("stage_change", "deadline_changed") and "stage_change" in events[-2:]
    page.wait_for_function("[...document.querySelectorAll('[data-testid=\"lead-detail-activity\"]')].some(e => e.innerText.includes('CALLBACK'))")
    page.wait_for_function("[...document.querySelectorAll('[data-testid=\"lead-detail-activity-stage\"]')].some(e => e.innerText === 'APPLIED → CALLBACK')")


def test_log_contact_and_edit_fields_write_events(page, ui_app):
    base_url, db_path = ui_app
    _open_lead(page, base_url, 4, tab="interviews")
    page.fill('[data-testid="lead-detail-contact-date"]', "2026-09-18")
    page.click('[data-testid="lead-detail-contact"]')
    assert _poll(db_path, "SELECT last_contact_date FROM lead WHERE id = 4", [("2026-09-18",)]) == [("2026-09-18",)]
    page.fill('[data-testid="lead-detail-field-title_override"]', "Renamed by UI")
    page.click('[data-testid="lead-detail-save"]')
    assert _poll(db_path, "SELECT title_override FROM lead WHERE id = 4", [("Renamed by UI",)]) == [("Renamed by UI",)]
    events = [r[0] for r in _rows(db_path, "SELECT event_type FROM lead_event WHERE lead_id = 4 ORDER BY id")]
    assert "contact_logged" in events and "field_edited" in events


def test_add_note_writes_note_and_event(page, ui_app):
    base_url, db_path = ui_app
    _open_lead(page, base_url, 3, tab="callbacks")
    page.fill('[data-testid="lead-detail-note-input"]', "Called the recruiter")
    page.click('[data-testid="lead-detail-note-add"]')
    assert _poll(db_path, "SELECT note FROM lead_note WHERE lead_id = 3 AND note LIKE 'Called%'", [("Called the recruiter",)]) == [("Called the recruiter",)]
    assert ("note_edited", "Called the recruiter") in _rows(db_path, "SELECT event_type, detail FROM lead_event WHERE lead_id = 3")
    _visible(page, "lead-detail-note")
    assert "Called the recruiter" in page.locator('[data-testid="lead-detail-note"]').first.inner_text()


def test_close_asks_for_confirmation_and_records_the_reason(page, ui_app):
    base_url, db_path = ui_app
    _open_lead(page, base_url, 1)
    page.select_option('[data-testid="lead-detail-close-reason"]', label="withdrawn")
    page.click('[data-testid="lead-detail-close"]')
    _visible(page, "confirm-modal")
    page.click('[data-testid="confirm-no"]')
    assert _rows(db_path, "SELECT status, close_reason FROM lead WHERE id = 1") == [("OPEN", None)]
    page.click('[data-testid="lead-detail-close"]')
    _visible(page, "confirm-modal")
    page.click('[data-testid="confirm-yes"]')
    assert _poll(db_path, "SELECT status, stage, close_reason FROM lead WHERE id = 1", [("CLOSED", "CLOSED", "withdrawn")]) == [("CLOSED", "CLOSED", "withdrawn")]
    page.locator('[data-testid="lead-detail"]').wait_for(state="detached", timeout=10_000)
    page.wait_for_function("document.querySelectorAll('[data-testid=\"lead-row-1\"]').length === 0")


def test_closing_without_a_reason_shows_the_field_error_inline(page, ui_app):
    base_url, db_path = ui_app
    _open_lead(page, base_url, 4, tab="interviews")
    page.click('[data-testid="lead-detail-close"]')
    page.click('[data-testid="confirm-yes"]')
    error = _visible(page, "lead-detail-field-error")
    assert "close_reason" in error.inner_text()
    assert page.locator('[data-testid="error-toast"]').count() == 0
    assert _rows(db_path, "SELECT status FROM lead WHERE id = 4") == [("OPEN",)]


def test_a_rejected_write_shows_a_toast(page, ui_app):
    base_url, db_path = ui_app
    _open_lead(page, base_url, 3, tab="callbacks")
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE lead SET stage = 'CLOSED', status = 'CLOSED', close_reason = 'cancelled' WHERE id = 3")
    conn.commit()
    conn.close()
    page.click('[data-testid="lead-detail-advance"]')
    toast = _visible(page, "error-toast")
    assert "illegal transition" in toast.inner_text()


def test_manual_lead_creation_promotes_a_manual_post(page, ui_app):
    base_url, db_path = ui_app
    page.goto(base_url + "/leads")
    _visible(page, "lead-add")
    page.click('[data-testid="lead-add"]')
    _visible(page, "manual-lead-form")
    page.locator('[data-testid="manual-lead-track"] option').nth(1).wait_for(state="attached")
    page.fill('[data-testid="manual-lead-title"]', "Manual product analyst")
    page.fill('[data-testid="manual-lead-company"]', "Example Co")
    page.select_option('[data-testid="manual-lead-track"]', label="Data Analyst / mid")
    page.click('[data-testid="manual-lead-save"]')
    assert _poll(
        db_path,
        "SELECT l.stage, l.status FROM lead l JOIN post p ON p.id = l.post_id WHERE p.position_title = ?",
        [("TOAPPLY", "OPEN")],
        8.0,
        "Manual product analyst",
    ) == [("TOAPPLY", "OPEN")]
    lead_id, url_ref = _rows(
        db_path,
        "SELECT l.id, p.url_ref FROM lead l JOIN post p ON p.id = l.post_id WHERE p.position_title = ?",
        "Manual product analyst",
    )[0]
    assert str(uuid.UUID(url_ref)) == url_ref

    page.goto(base_url + "/leads")
    _visible(page, f"lead-row-{lead_id}")
    page.click(f'[data-testid="lead-row-{lead_id}"]')
    _visible(page, "lead-detail")
    _visible(page, "lead-detail-post-unavailable")
    assert page.locator('[data-testid="lead-detail-post-link"]').count() == 0
    page.fill('[data-testid="lead-detail-post-url"]', "https://example.com/manual-post")
    page.click('[data-testid="lead-detail-post-url-save"]')
    assert _poll(
        db_path,
        "SELECT url_ref FROM post WHERE id = (SELECT post_id FROM lead WHERE id = ?)",
        [("https://example.com/manual-post",)],
        8.0,
        lead_id,
    ) == [("https://example.com/manual-post",)]
    _visible(page, "lead-detail-post-link")


def test_search_configuration_updates_profile_and_schedule(page, ui_app):
    base_url, db_path = ui_app
    page.goto(base_url + "/tracks")
    _visible(page, "configure-search-1")
    page.click('[data-testid="configure-search-1"]')
    _visible(page, "search-profile-page")
    page.fill('[data-testid="profile-keywords"]', "data analyst refreshed")
    page.fill('[data-testid="profile-schedule-interval"]', "12")
    page.check('[data-testid="profile-schedule-enabled"]')
    page.click('[data-testid="profile-save"]')
    assert _poll(db_path, "SELECT keywords FROM search_profile WHERE track_id = 1", [("data analyst refreshed",)]) == [("data analyst refreshed",)]
    assert _poll(db_path, "SELECT schedule_enabled, schedule_interval_hours FROM search_schedule WHERE track_id = 1", [(1, 12)]) == [(1, 12)]


def test_cv_catalog_create_rename_and_remove(page, ui_app):
    base_url, db_path = ui_app
    page.goto(base_url + "/cvs")
    _visible(page, "cvs-page")
    page.fill('[data-testid="cv-label"]', "UI Catalog CV")
    page.click('[data-testid="cv-save"]')
    assert _poll(db_path, "SELECT label FROM cv WHERE label = ?", [("UI Catalog CV",)], 8.0, "UI Catalog CV") == [("UI Catalog CV",)]
    cv_id = _rows(db_path, "SELECT id FROM cv WHERE label = ?", "UI Catalog CV")[0][0]
    page.click(f'[data-testid="cv-row-{cv_id}"] button')
    page.fill('[data-testid="cv-label"]', "UI Catalog CV renamed")
    page.click('[data-testid="cv-save"]')
    assert _poll(db_path, "SELECT label FROM cv WHERE id = ?", [("UI Catalog CV renamed",)], 8.0, cv_id) == [("UI Catalog CV renamed",)]
    page.locator(f'[data-testid="cv-row-{cv_id}"] button').nth(1).click()
    assert _poll(db_path, "SELECT label FROM cv WHERE id = ?", [], 8.0, cv_id) == []


def _add_leads(db_path: str, stage: str, count: int, prefix: str, contacts=None, updated=None) -> list[int]:
    """Insert leads (with their posts) straight into SQLite, so a test owns the leads it drives."""
    conn = sqlite3.connect(db_path)
    ids = []
    for n in range(count):
        post_id = f"{prefix}-{uuid.uuid4()}"
        conn.execute(
            "INSERT INTO post (id, source, position_title, company_name, is_open, src_method) "
            "VALUES (?, 'UI', ?, 'Batch Co', 1, 'manual')", (post_id, f"{prefix} role {n}"))
        closed = stage == "CLOSED"
        ids.append(conn.execute(
            "INSERT INTO lead (post_id, track_id, status, stage, close_reason, deadline, last_contact_date, expected_salary_sgd, "
            "created_at, updated_at) VALUES (?, 1, ?, ?, ?, date('now', ?), ?, 10000, '2026-09-19 07:00:00', ?)",
            (post_id, "CLOSED" if closed else "OPEN", stage, "cancelled" if closed else None, f"+{20 + n} days",
             contacts[n] if contacts else None, updated[n] if updated else "2026-09-19 07:00:00")).lastrowid)
    conn.commit()
    conn.close()
    return ids


def _add_toapply_leads(db_path: str, count: int, prefix: str = "batch") -> list[int]:
    return _add_leads(db_path, "TOAPPLY", count, prefix)


def test_saved_change_refreshes_the_list_and_the_detail(page, ui_app):
    base_url, _db = ui_app
    lead_id = _add_toapply_leads(_db, 1, "refresh")[0]
    _open_lead(page, base_url, lead_id)
    assert page.locator(f'[data-testid="leads-column-TOAPPLY"] [data-testid="lead-row-{lead_id}"]').count() == 1
    assert "APPLIED" in _visible(page, "lead-detail-advance").inner_text().upper()
    page.click('[data-testid="lead-detail-advance"]')
    page.wait_for_function("document.querySelector('[data-testid=\"lead-detail-advance\"]').innerText.toUpperCase().includes('CALLBACK')")
    page.wait_for_function(f"document.querySelectorAll('[data-testid=\"lead-row-{lead_id}\"]').length === 0")
    assert "APPLIED / OPEN" in page.locator("[data-testid=lead-detail] .detail-header p").inner_text()
    page.click('[data-testid="leads-tab-applied"]')
    _visible(page, f"lead-row-{lead_id}")
