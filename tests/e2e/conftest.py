"""Tier 2 fixtures — full stack, real backend + real frontend (ARCH-TEST-04).

Mechanically identical to tests/frontend/'s fixture for this milestone —
both spawn the real `python -m easymcf` process the same way (ARCH-TEST-09)
via the shared tests/_browser_support helper. They diverge once a real,
data-backed screen exists: tier 1b intercepts `/api/**` from canned JSON,
this tier lets every request reach the real Flask routes and SQLite. For
the root redirect both tiers assert the identical thing, since the redirect makes no `/api` call.
"""

from __future__ import annotations

import os
import sys

import pytest

_TESTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REPO_ROOT = os.path.dirname(_TESTS_DIR)
_SCRIPTS_DIR = os.path.join(_REPO_ROOT, "scripts")
sys.path.insert(0, _REPO_ROOT)
sys.path.insert(0, _SCRIPTS_DIR)

from initdb import apply_schema  # noqa: E402
from resetdb import apply_seed  # noqa: E402
from tests._browser_support import spawn_app, terminate_app  # noqa: E402

# `browser`/`page` are registered once, in tests/conftest.py, not here — see
# that file's comment (07.IS.06: two independent registrations collide when
# both tiers run in the same pytest session).


@pytest.fixture(scope="session")
def app_base_url(tmp_path_factory):
    db_path = str(tmp_path_factory.mktemp("easymcf-e2e-db") / "easymcf.db")
    apply_schema(db_path)
    apply_seed(db_path)
    proc, base_url = spawn_app(db_path)
    try:
        yield base_url
    finally:
        terminate_app(proc)
