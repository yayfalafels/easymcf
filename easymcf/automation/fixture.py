"""ARCH-BOT-02 / ARCH-TEST-04 — the fixture-corpus implementation of MCFBrowser.

No network call, no browser: `search_page`/`detail_page` look up and return canned HTML
straight from `tests/fixtures/mcf/`, keyed by keyword+page or by the detail URL, for
whichever scenario `config.mcf_fixture_scenario` names (`default` or `slow` — the
Fixture corpus design note). A keyword/page combination the manifest doesn't list is
treated as a genuinely empty results page (zero cards), the same shape as MCF's own last
page of a sweep, rather than an error — this lets the corpus cover only the
keywords/pages a given case or oracle test actually exercises.
"""

from __future__ import annotations

import json
import os
import time

from ..config import Config

_FIXTURES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tests", "fixtures", "mcf"
)
_EMPTY_PAGE_HTML = "<html><body><div data-testid=\"no-search-result\">No jobs found</div></body></html>"


def _load_manifest() -> dict:
    with open(os.path.join(_FIXTURES_DIR, "routes.json"), encoding="utf-8") as handle:
        return json.load(handle)


def _read_html(filename: str) -> str:
    with open(os.path.join(_FIXTURES_DIR, filename), encoding="utf-8") as handle:
        return handle.read()


class FixtureMCFBrowser:
    def __init__(self, config: Config):
        self._config = config
        manifest = _load_manifest()
        self._scenario = manifest["scenarios"].get(config.mcf_fixture_scenario) or manifest["scenarios"]["default"]

    def _delay(self, route: dict) -> None:
        delay_ms = route.get("delay_ms")
        if delay_ms:
            time.sleep(delay_ms / 1000)

    def search_page(self, keyword: str, min_salary: int | None, page: int) -> str:
        route = self._scenario["search"].get(f"{keyword}|{page}")
        if route is None:
            return _EMPTY_PAGE_HTML
        self._delay(route)
        return _read_html(route["file"])

    def detail_page(self, url_ref: str) -> str:
        route = self._scenario["detail"].get(url_ref)
        if route is None:
            raise RuntimeError(f"fixture corpus has no detail route for {url_ref!r}")
        self._delay(route)
        return _read_html(route["file"])

    def close(self) -> None:
        pass
