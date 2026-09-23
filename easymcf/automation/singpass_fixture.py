"""ARCH-TEST-04's fixture-interception pattern, one layer over: every request this browser makes is routed to
`tests/fixtures/singpass/` instead of dispatched, so an automated run never resolves a real MCF or Singpass
hostname. The real navigation, locator, wait, and decode logic in `singpass_browser.py` runs unchanged; only
the bytes come from disk.
"""

from __future__ import annotations

import os

from playwright.sync_api import Page, Route

from .singpass_browser import BaseSingpassBrowser

_FIXTURES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                              "tests", "fixtures", "singpass")

_ROUTES = {
    "https://www.mycareersfuture.gov.sg/": "mcf_home.html",
    "https://login.id.singpass.gov.sg/main": "qr.html",
    "https://www.mycareersfuture.gov.sg/dashboard/career": "dashboard.html",
    "https://www.mycareersfuture.gov.sg/profile": "profile.html",
}


class FixtureSingpassBrowser(BaseSingpassBrowser):
    def _setup_routing(self, page: Page) -> None:
        def handler(route: Route) -> None:
            url = route.request.url.split("#", 1)[0]
            filename = _ROUTES.get(url)
            if filename is None:
                route.fulfill(status=204, body="")
                return
            with open(os.path.join(_FIXTURES_DIR, filename), encoding="utf-8") as handle:
                route.fulfill(status=200, content_type="text/html", body=handle.read())

        page.context.route("**/*", handler)
