"""ARCH-TEST-06 — tier 3, deselected by default (`pytest.ini`'s `addopts = -m "not live"`).

Two independent, explicit gates, both required: the `live` marker re-selected on the command
line (`-m live`) and this directory's own `--run-live` flag. Deliberately does **not** add a
third gate keyed on `.secrets/mcf_session.json`, unlike the general live tier the architecture
doc (`ARCH-TEST-06`) describes for apply/session-backed live cases — this milestone's search
pipeline needs no MCF session at all (Design > Workflow, "Search needs no MCF session").

`test_search_live.py` does set `MCF_MODE=live` itself, via `monkeypatch.setenv`, since
`search.py::_run_search`'s background thread builds its own fresh `Config()` from `os.environ`
rather than reusing the triggering request's config object. That is a deliberate, scoped,
in-test action, not ambient state this tier depends on: a developer's `.env` can say anything
(fixture, live, absent) and it has zero effect here, since the test never reads it — the only
way this tier reaches the real site is `--run-live` on the command line, and `monkeypatch`
restores `MCF_MODE` at teardown regardless of pass/fail.
"""

from __future__ import annotations

import pytest


def pytest_addoption(parser) -> None:
    parser.addoption(
        "--run-live", action="store_true", default=False,
        help="actually run tests marked `live` against the real MCF site (deliberate, in addition to -m live)",
    )


def pytest_collection_modifyitems(config, items) -> None:
    if config.getoption("--run-live"):
        return
    skip_live = pytest.mark.skip(reason="live tier needs --run-live (deliberate, in addition to -m live)")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)
