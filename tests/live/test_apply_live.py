"""11.TC.23 — human-triggered only: the apply flow against the real MCF site, one posting the human chooses.

Gates, all required: `-m live` and `--run-live` on the command line (this directory's conftest), `APPLY_LIVE_URL`
naming one throwaway posting, and a valid MCF session storage state from feature 17's connect flow. The submit case
additionally needs `APPLY_LIVE_SUBMIT=1` (11.IS.14) and `APPLY_LIVE_CV`, and it submits a real application.

    # step 1, no submission: the banner and apply-button selectors against real markup
    APPLY_LIVE_URL=https://www.mycareersfuture.gov.sg/job/... \\
        env/bin/python -m pytest tests/live/test_apply_live.py -m live --run-live -k apply_probe -v -s
    # step 2, submits one real application
    APPLY_LIVE_URL=... APPLY_LIVE_CV="<a label matching one of your MCF resumes>" APPLY_LIVE_SUBMIT=1 \\
        env/bin/python -m pytest tests/live/test_apply_live.py -m live --run-live -k apply_submit -v -s

Apply runs headless like the app's own apply workflow (`HEADLESS=1`, the default); prefix `HEADLESS=0` only
when a human wants to watch one run. The storage state defaults to `$SECRETS_DIR/mcf_session_1.json`, feature 17's export for user 1; `APPLY_LIVE_STORAGE`
overrides it. Outcome mapping is the oracle's job (`test_apply_pipeline.py`); this tier only confirms the real site
still matches the fixture corpus.
"""

from __future__ import annotations

import os

import pytest

from easymcf.config import Config

pytestmark = pytest.mark.live

APPLY_STATUSES = ("applied", "questionnaire_required", "cv_selector_error", "unable_to_apply",
                  "post_unavailable", "cv_not_found", "post_closed", "invalid_input")


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        pytest.skip(f"{name} is not set; the live apply tier needs it from the human running it")
    return value


def _storage_path() -> str:
    path = os.environ.get("APPLY_LIVE_STORAGE") or os.path.join(Config().secrets_dir, "mcf_session_1.json")
    if not os.path.isfile(path):
        pytest.skip(f"no MCF session storage state at {path}: connect MCF through the app's nav icon first")
    return path


def _live_config(monkeypatch) -> Config:
    monkeypatch.setenv("MCF_MODE", "live")
    return Config()


@pytest.mark.timeout(180)
def test_live_apply_probe_reads_banner_and_button_without_submitting(monkeypatch):
    """Step 1: load, banner, and button poll only. Never clicks, so it constructs the live class directly
    rather than through get_browser(), whose APPLY_LIVE_SUBMIT gate guards submission."""
    from easymcf.automation.apply_live import LiveApplyBrowser
    from easymcf.services import apply

    url = _required("APPLY_LIVE_URL")
    config = _live_config(monkeypatch)
    browser = LiveApplyBrowser(config, _storage_path())
    browser.snapshot_dir = os.environ.get("APPLY_LIVE_SNAPSHOT_DIR") or None
    try:
        loaded, detail = browser.load_posting(url)
        print(f"\nload_posting -> {loaded} {detail or ''}")
        assert loaded == "ok", f"expected a signed-in posting page, got {loaded}: {detail}"
        state, detail = apply._poll_button(browser, config)
        print(f"apply button -> {state} {detail or ''} after {browser.diagnostics['polls']} polls")
        assert state in {"found", "already_applied", "closed"}, (state, detail)
        assert browser.diagnostics["clicks"] == 0 and browser.diagnostics["submits"] == 0
    finally:
        browser.close()


@pytest.mark.timeout(180)
def test_live_apply_deep_probe_reads_resume_cards_without_submitting(monkeypatch):
    """Step 1b: click Apply and read the resume cards, then stop before Next and Submit. Confirms the CV selectors
    and that APPLY_LIVE_CV matches one of the human's own MCF resumes before any real submit."""
    from easymcf.automation.apply_live import LiveApplyBrowser
    from easymcf.services import apply

    url = _required("APPLY_LIVE_URL")
    cv_label = _required("APPLY_LIVE_CV")
    config = _live_config(monkeypatch)
    browser = LiveApplyBrowser(config, _storage_path())
    try:
        assert browser.load_posting(url)[0] == "ok"
        state, detail = apply._poll_button(browser, config)
        assert state == "found", (state, detail)
        browser.click_apply()
        titles = browser.resume_options()
        print(f"\nresume options -> {titles}")
        assert any(cv_label in title for title in titles), f"{cv_label!r} matches none of {titles}"
        assert browser.diagnostics["submits"] == 0 and browser.diagnostics["cv_selections"] == 0
    finally:
        browser.close()


@pytest.mark.timeout(240)
def test_live_apply_submit_reaches_a_real_outcome_code(monkeypatch):
    """Step 2: the whole state machine for one posting. Submits a real application."""
    from easymcf.automation.apply_browser import get_browser
    from easymcf.services import apply

    url = _required("APPLY_LIVE_URL")
    cv_label = _required("APPLY_LIVE_CV")
    if os.environ.get("APPLY_LIVE_SUBMIT") != "1":
        pytest.skip("APPLY_LIVE_SUBMIT=1 is not set: the submit case never runs without it")
    config = _live_config(monkeypatch)
    browser = get_browser(config, _storage_path())
    browser.snapshot_dir = os.environ.get("APPLY_LIVE_SNAPSHOT_DIR") or None
    try:
        lead = {"id": 0, "post_id": "live-probe", "url_ref": url, "cv_label": cv_label}
        status, detail = apply.attempt_one(browser, lead, config)
        print(f"\noutcome -> {status} {detail or ''} | diagnostics {browser.diagnostics}")
        assert status in APPLY_STATUSES and status != "invalid_input"
    finally:
        browser.close()
