from __future__ import annotations

import sqlite3

import pytest

pytestmark = pytest.mark.backend

LEAD_STAGES = {"PROSPECT", "TOAPPLY", "APPLIED", "CALLBACK", "INTERVIEW", "OFFER", "CLOSED"}
CLOSE_REASONS = {"offer_accepted", "rejected", "withdrawn", "expired", "cancelled", "duplicate", "apply_failed"}
APPLICATION_STATUSES = {
    "applied", "questionnaire_required", "cv_selector_error", "unable_to_apply",
    "post_unavailable", "cv_not_found", "post_closed", "invalid_input",
}
RUN_STATUSES = {"running", "success", "partial", "failed"}


@pytest.fixture()
def conn(db_path):
    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")
    yield connection
    connection.close()


def distinct(connection, query):
    return {row[0] for row in connection.execute(query)}


def test_track_and_post_coverage(conn):
    total, archived = conn.execute("SELECT COUNT(*), SUM(1 - is_active) FROM track").fetchone()
    assert total >= 2
    assert archived >= 1
    assert distinct(conn, "SELECT DISTINCT src_method FROM post") == {"scraped", "manual"}
    assert conn.execute("SELECT COUNT(*) FROM (SELECT post_id FROM post_track GROUP BY post_id HAVING COUNT(*) > 1)").fetchone()[0] >= 1


def test_closed_vocabularies_are_complete(conn):
    assert LEAD_STAGES <= distinct(conn, "SELECT DISTINCT stage FROM lead")
    assert CLOSE_REASONS <= distinct(conn, "SELECT DISTINCT close_reason FROM lead WHERE status = 'CLOSED'")
    assert APPLICATION_STATUSES <= distinct(conn, "SELECT DISTINCT status FROM application")
    assert RUN_STATUSES <= distinct(conn, "SELECT DISTINCT status FROM run_log")


def test_retry_pair_and_apply_failed_linkage(conn):
    assert conn.execute("SELECT COUNT(*) FROM (SELECT lead_id FROM application GROUP BY lead_id HAVING COUNT(*) > 1)").fetchone()[0] >= 1
    bad = conn.execute(
        "SELECT a.id FROM application a JOIN lead l ON l.id = a.lead_id "
        "WHERE a.status IN ('post_closed', 'post_unavailable') AND l.close_reason != 'apply_failed'"
    ).fetchall()
    assert bad == []
