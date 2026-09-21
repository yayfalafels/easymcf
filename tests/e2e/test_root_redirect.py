"""The root path lands on the Leads page (FE-RTE-01): `/` and an unmatched path both end at `/leads`."""

from __future__ import annotations

import pytest

from tests._browser_support import sign_in


@pytest.mark.e2e
@pytest.mark.parametrize("path", ["/", "/no-such-page"])
def test_root_and_unknown_paths_land_on_leads(page, app_base_url, path):
    sign_in(page, app_base_url)
    page.goto(app_base_url + path)
    page.locator('[data-testid="leads-tab-toapply"]').wait_for(state="visible", timeout=10_000)
    assert page.url == app_base_url + "/leads"
