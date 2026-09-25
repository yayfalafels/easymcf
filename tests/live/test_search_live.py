"""10.TC.24 — human-triggered: `pytest -m live --run-live -k search -v`.

Confirms the search pipeline still parses MCF's *real* markup end to end (REQ-DEV-05,
ARCH-TEST-06). It does not assert pipeline logic — dedup, the closed-post short-circuit, and the
fixed-score write are the fixture/oracle tiers' own job (`test_search_pipeline.py`). This test's
only job is: does a real search against mycareersfuture.gov.sg still return cards this codebase's
selectors can parse, and does the whole run still reach a lead at the end.

Search needs no MCF session (Design > Workflow, "Search needs no MCF session"), so
`mcf_mode="live"` is the only thing this test changes — `.secrets/mcf_session.json` is never read
or required, see `conftest.py` in this directory for why that's a deliberate difference from the
general live tier `ARCH-TEST-06` describes.
"""

from __future__ import annotations

import json
import sqlite3
import time

import pytest

from easymcf import create_app
from easymcf.config import Config

pytestmark = pytest.mark.live

SEED_A = {"email": "yayfalafels@gmail.com", "password": "Seed-Password-1!"}
# A first real run against "Data Analyst" found 24 cards / 22 new posts on page 1 alone — the
# detail pass (one page load per post, paced by search_page_delay_s) genuinely needs several
# minutes for a batch that size, not the fixture corpus's handful of postings.
POLL_TIMEOUT_S = 240


@pytest.mark.timeout(300)  # pytest.ini's global 60s is for the fixture/mock tiers; real Chromium
# against the live site plus this test's own POLL_TIMEOUT_S needs real headroom
def test_real_search_against_mcf_finds_and_promotes_a_lead(db_path, monkeypatch):
    """Track 1's seeded search_profile keywords is "Data Analyst" (db_util.py confirmed), a
    common, low-traffic-impact public search term. One page-1 sweep only — this is a markup-drift
    smoke check, not a load test.

    `search.py::_run_search` (the background thread `start_run` spawns) builds its own fresh
    `Config()` reading `os.environ` rather than reusing the triggering request's config object —
    `monkeypatch.setenv` here is the only way to reach it, matching the pattern `db_path`'s own
    fixture already uses to hand that same thread its `DB_PATH`. `monkeypatch` auto-restores
    `MCF_MODE` at teardown, so this is scoped to this one test regardless of pass/fail."""
    monkeypatch.setenv("MCF_MODE", "live")
    config = Config(db_path=db_path, mcf_mode="live", search_page_delay_s=1)
    app = create_app(config)
    client = app.test_client()

    signin = client.post("/api/v1/auth/signin", json=SEED_A)
    assert signin.status_code == 200, signin.get_json()

    before = sqlite3.connect(db_path).execute("SELECT COUNT(*) FROM lead WHERE track_id = 1").fetchone()[0]

    triggered = client.post("/api/v1/runs/search", json={"track_id": 1})
    assert triggered.status_code == 201, triggered.get_json()
    run_id = triggered.get_json()["id"]

    run = None
    deadline = time.monotonic() + POLL_TIMEOUT_S
    while time.monotonic() < deadline:
        run = client.get(f"/api/v1/run_log/{run_id}").get_json()
        if run["status"] != "running":
            break
        time.sleep(2)
    assert run is not None and run["status"] != "running", f"run {run_id} never reached a terminal status"
    assert run["status"] in ("success", "partial"), f"run ended {run['status']}: {run.get('error_detail')}"

    counts = json.loads(run["outcome_counts"])
    assert counts["mcf_mode"] == "live"
    assert counts["cards"] >= 1, "no cards parsed from a real MCF search page — possible markup drift"
    assert counts["detail_errors"] == 0, "a real detail page failed to parse — possible markup drift"

    after = sqlite3.connect(db_path).execute("SELECT COUNT(*) FROM lead WHERE track_id = 1").fetchone()[0]
    assert after > before, "no fresh lead was promoted from this run's real results"
