"""Tier 2 smoke case (ARCH-TEST-04) — same DOM assertion as the frontend
silo (tests/frontend/test_env_status.py), against the real backend/db this
time, not a mocked one. Passing both independently is 010.07.TC.13's oracle.
"""

from __future__ import annotations

import pytest


@pytest.mark.e2e
def test_env_status_heading_renders(page, app_base_url):
    page.goto(app_base_url + "/")
    heading = page.locator('[data-testid="env-status-heading"]')
    heading.wait_for(state="visible", timeout=10_000)
    assert heading.inner_text() == "Easy MCF — local dev environment ready"
