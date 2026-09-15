"""Tier 1b smoke case (ARCH-TEST-09) — DOM-level assertion, ARCH-TEST-05's
convention: rendered text, never a JS-internals check. Proves the vendor
assets, Flask static serving, Angular bootstrap, and routing wiring work
end to end (ENV-SETUP-06) — the same thing a human opening the app in an
ordinary browser sees.
"""

from __future__ import annotations

import pytest


@pytest.mark.frontend
def test_env_status_heading_renders(page, app_base_url):
    page.goto(app_base_url + "/")
    heading = page.locator('[data-testid="env-status-heading"]')
    heading.wait_for(state="visible", timeout=10_000)
    assert heading.inner_text() == "Easy MCF — local dev environment ready"
