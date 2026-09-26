"""11.EL.25 — mock end to end (ARCH-TEST-04): Playwright drives the real Applications page against the real backend,
a real seeded database, and the fixture ApplyBrowser, whose own Chromium serves the local apply corpus. Each case
spawns its own app, since the fixture scenario is per process (MCF_FIXTURE_SCENARIO), with user 1's session staged
`valid` in an isolated SECRETS_DIR (11.IS.01). MCF_MODE=fixture is passed explicitly (11.IS.14).

11.TC.21 runs the `slow` scenario, three seconds per posting, so the running state is observable across polls.
11.TC.22 runs `signed_out` and reads feature 17's own MCF nav icon, with no session UI of this milestone's own.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys

import pytest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_REPO_ROOT, "scripts"))

from initdb import apply_schema  # noqa: E402
from resetdb import apply_seed  # noqa: E402
from tests._browser_support import sign_in, spawn_app, terminate_app  # noqa: E402

pytestmark = pytest.mark.e2e


def _apply_stack(tmp_path, scenario: str):
    db_path = str(tmp_path / "easymcf.db")
    apply_schema(db_path)
    apply_seed(db_path)
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    (secrets / "mcf_session_1.json").write_text(json.dumps({"cookies": [], "origins": []}))
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE mcf_session SET status = 'valid', cookie_ref = 'mcf_session_1.json' WHERE user_id = 1")
    conn.commit()
    conn.close()
    return spawn_app(db_path, extra_env={
        "MCF_MODE": "fixture", "SECRETS_DIR": str(secrets), "MCF_FIXTURE_SCENARIO": scenario,
        "APPLY_POLL_RETRIES": "2", "APPLY_POLL_DELAY_S": "0.1", "SCHEDULER_ENABLED": "0",
    })


@pytest.fixture()
def slow_app(tmp_path):
    proc, base_url = _apply_stack(tmp_path, "slow")
    yield base_url
    terminate_app(proc)


@pytest.fixture()
def signed_out_app(tmp_path):
    proc, base_url = _apply_stack(tmp_path, "signed_out")
    yield base_url
    terminate_app(proc)


def _open_applications(page, base_url: str) -> None:
    sign_in(page, base_url, "seed_a")
    page.goto(base_url + "/applications")
    page.locator('[data-testid="apply-row-20"]').wait_for(state="visible", timeout=10_000)
    page.wait_for_function(
        "() => !document.querySelector('[data-testid=\"apply-run-btn\"]').disabled", timeout=10_000)


def _confirm_run(page) -> None:
    page.click('[data-testid="apply-run-btn"]')
    page.locator('[data-testid="confirm-message"]').filter(has_text="This submits real applications").wait_for(timeout=5_000)
    page.click('[data-testid="confirm-yes"]')


@pytest.mark.timeout(120)
def test_run_batch_shows_progress_then_results_with_next_actions(page, slow_app):
    """11.TC.21 — Run apply batch -> confirmation -> running state whose progress text advances lead by lead ->
    results view with each lead's outcome and Workflow 7 next action, and the queue refreshed empty."""
    _open_applications(page, slow_app)
    assert page.locator('[data-testid="apply-session-value"]').inner_text() == "valid"
    _confirm_run(page)
    progress = page.locator('[data-testid="apply-run-progress-text"]')
    progress.wait_for(state="visible", timeout=10_000)
    page.locator('[data-testid="run-in-progress-badge"]').wait_for(state="visible", timeout=5_000)
    page.wait_for_function(
        "() => (document.querySelector('[data-testid=\"apply-run-progress-text\"]') || {}).textContent"
        " && document.querySelector('[data-testid=\"apply-run-progress-text\"]').textContent"
        ".includes('Applying: 1 of 2 leads done, now lead #20')", timeout=30_000)
    page.locator('[data-testid="apply-results"]').wait_for(state="visible", timeout=60_000)
    assert page.locator('[data-testid="apply-results-status"]').text_content() == "success"
    for lead_id in (1, 20):
        assert page.locator(f'[data-testid="apply-result-status-{lead_id}"]').inner_text().startswith("applied")
        assert page.locator(f'[data-testid="apply-result-action-{lead_id}"]').inner_text() == \
            "Moved to APPLIED. Follow it up on the Leads page."
    page.locator('[data-testid="apply-queue-empty"]').wait_for(state="visible", timeout=5_000)
    assert page.locator('[data-testid="run-in-progress-badge"]').count() == 0


@pytest.mark.timeout(120)
def test_signed_out_run_turns_the_mcf_nav_icon_to_expired(page, signed_out_app):
    """11.TC.22 — a signed-out banner ends the run; the next poll of feature 17's nav icon reads the lapsed
    session, and the page's own session line and results surface the run error (REQ-FE-02)."""
    _open_applications(page, signed_out_app)
    dot = page.locator('[data-testid="mcf-status-dot"]')
    assert "mcf-status-green" in dot.get_attribute("class")
    _confirm_run(page)
    page.locator('[data-testid="apply-results"]').wait_for(state="visible", timeout=60_000)
    assert page.locator('[data-testid="apply-results-status"]').text_content() == "failed"
    assert page.locator('[data-testid="apply-results-error"]').inner_text().startswith(
        "session expired: MCF banner shows Login in place of the account initials at lead 1")
    page.wait_for_function(
        "() => document.querySelector('[data-testid=\"mcf-status-dot\"]').className.includes('mcf-status-red')",
        timeout=10_000)
    page.locator('[data-testid="apply-session-value"]').filter(has_text="expired").wait_for(timeout=10_000)
    assert page.locator('[data-testid="apply-run-btn"]').is_disabled()
    assert page.locator('[data-testid="apply-row-1"]').is_visible()  # nothing was attempted; the queue is intact
