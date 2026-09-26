"""ARCH-TEST-04 — the fixture ApplyBrowser: BaseApplyBrowser's own Playwright code, with every request routed to
the local `tests/fixtures/mcf/apply/` corpus before the first navigation, so no request leaves the machine.

The scenario for a posting is resolved per URL, in this order: an apply scenario named by `MCF_FIXTURE_SCENARIO`
applies to every posting (`slow`, `signed_out`); else the manifest's `routes` entry for the URL; else a URL whose
last path segment is `apply-fixture-<scenario>`; else the manifest's `default_scenario`. One run can therefore mix
outcomes, which the batch-isolation case needs (REQ-APPLY-08). Each posting's apply and review steps are served at
`<posting URL>/apply` and `<posting URL>/apply/review`, the navigation the corpus pages' own buttons perform. The review
page's submit requests `<posting URL>/apply/review/submitted`, after which the posting serves the already-applied page,
as the live site does (11.IS.23).
"""

from __future__ import annotations

import json
import os
import time
from urllib.parse import urlparse

from playwright.sync_api import Page, Route

from ..config import Config
from .apply_browser import BaseApplyBrowser

APPLY_FIXTURES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tests", "fixtures", "mcf", "apply"
)
MCF_HOST = "www.mycareersfuture.gov.sg"
SLUG_PREFIX = "apply-fixture-"


def load_manifest() -> dict:
    with open(os.path.join(APPLY_FIXTURES_DIR, "manifest.json"), encoding="utf-8") as handle:
        return json.load(handle)


class FixtureApplyBrowser(BaseApplyBrowser):
    page_load_timeout_ms = 5000
    banner_timeout_ms = 500
    step_timeout_ms = 1500
    confirm_delay_ms = 50

    def __init__(self, config: Config, storage_path: str | None = None, init_script: str | None = None):
        super().__init__(config, storage_path, init_script)
        self._manifest = load_manifest()
        forced = config.mcf_fixture_scenario
        self._forced = forced if forced in self._manifest["scenarios"] else None
        self._current: dict | None = None
        self._lead_polls = 0
        self._submitted: set[str] = set()  # postings whose review submit landed; they now read already applied

    def scenario_for(self, url: str) -> str:
        if self._forced:
            return self._forced
        base = url.split("?", 1)[0].rstrip("/")
        if base in self._manifest["routes"]:
            return self._manifest["routes"][base]
        slug = base.rsplit("/", 1)[-1].split("--", 1)[0]  # apply-fixture-<scenario>--<n>: one posting per lead
        if slug.startswith(SLUG_PREFIX) and slug[len(SLUG_PREFIX):] in self._manifest["scenarios"]:
            return slug[len(SLUG_PREFIX):]
        return self._manifest["default_scenario"]

    def _setup_routing(self, page: Page) -> None:
        page.context.route("**/*", self._handle)

    def _handle(self, route: Route) -> None:
        url = route.request.url
        if urlparse(url).hostname != MCF_HOST:
            route.abort()  # nothing leaves the machine in fixture mode
            return
        base, step = url.split("?", 1)[0].rstrip("/"), "posting"
        for suffix, name in (("/apply/review/submitted", "submitted"), ("/apply/review", "review"), ("/apply", "apply")):
            if base.endswith(suffix):
                base, step = base[: -len(suffix)], name
                break
        if step == "submitted":
            self._submitted.add(base)
            route.fulfill(status=200, content_type="text/html", body="<html><body><p>Submitting...</p></body></html>")
            return
        if step == "posting" and base in self._submitted:
            step, scenario = "posting", self._manifest["scenarios"]["already_applied"]
        else:
            scenario = self._manifest["scenarios"][self.scenario_for(base)]
        if step == "posting" and scenario.get("delay_ms"):
            time.sleep(scenario["delay_ms"] / 1000)
        filename = scenario.get(step)
        if filename is None:
            route.abort("connectionrefused")  # post_unavailable: the posting never loads
            return
        with open(os.path.join(APPLY_FIXTURES_DIR, filename), encoding="utf-8") as handle:
            route.fulfill(status=200, content_type="text/html", body=handle.read())

    def load_posting(self, url_ref: str) -> tuple[str, str | None]:
        self._current = self._manifest["scenarios"][self.scenario_for(url_ref)]
        self._lead_polls = 0
        return super().load_posting(url_ref)

    def check_apply_button(self) -> tuple[str, str | None]:
        self._lead_polls += 1
        reveal_after = (self._current or {}).get("reveal_after_polls")
        if reveal_after and self._lead_polls >= reveal_after:
            self._page.evaluate("window.__revealApply && window.__revealApply()")  # a button that appears late
        return super().check_apply_button()
