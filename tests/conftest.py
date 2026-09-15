"""Session-scoped fixtures (ARCH-TEST-01).

State isolation: a fresh temp-file SQLite database per test session, seeded
from `seed/*.sql`, deleted on teardown. Temp *file*, not `:memory:` — an
in-memory database is per-connection, which breaks the moment the app opens
a second connection and diverges from the WAL/file semantics being tested.
No test run ever touches `data/easymcf.db`.
"""

from __future__ import annotations

import os
import sys

import pytest

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_TESTS_DIR)
_SCRIPTS_DIR = os.path.join(_REPO_ROOT, "scripts")
sys.path.insert(0, _REPO_ROOT)
sys.path.insert(0, _SCRIPTS_DIR)

from initdb import apply_schema  # noqa: E402
from resetdb import apply_seed  # noqa: E402
from tests._browser_support import browser, page  # noqa: E402,F401

# `browser`/`page` (ARCH-TEST-04/09) are registered exactly once, here at the
# top level, deliberately — 07.IS.06. Registering them separately in both
# tests/frontend/conftest.py and tests/e2e/conftest.py (each importing the
# same functions) creates two independent session-scoped fixture instances;
# when both tiers run in one pytest session, the second one to activate
# collides with the first's still-open sync_playwright() context. One shared
# registration point means one browser instance for the whole session,
# reused by whichever tier's tests request it.


@pytest.fixture(scope="session")
def db_path(tmp_path_factory):
    """Apply schema.sql + seed/*.sql to a session-scoped temp file, export DB_PATH.

    Deliberately does not call `load_dotenv()` (ENV-CFG-03/07.02.03) — this
    fixture sets DB_PATH explicitly per session (ARCH-TEST-01's state
    isolation); loading a developer's personal `.env` here would let a
    machine-local override silently change test behavior.
    """
    path = str(tmp_path_factory.mktemp("easymcf-db") / "easymcf.db")
    apply_schema(path)
    apply_seed(path)

    previous = os.environ.get("DB_PATH")
    os.environ["DB_PATH"] = path
    try:
        yield path
    finally:
        if previous is None:
            os.environ.pop("DB_PATH", None)
        else:
            os.environ["DB_PATH"] = previous


@pytest.fixture()
def app(db_path):
    """A Flask app instance bound to the session's temp db (ARCH-TEST-03)."""
    from easymcf import create_app
    from easymcf.config import Config

    return create_app(Config(db_path=db_path))


@pytest.fixture()
def client(app):
    return app.test_client()
