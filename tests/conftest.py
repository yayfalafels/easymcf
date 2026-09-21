"""Session-scoped fixtures (ARCH-TEST-01).

State isolation: a fresh temp-file SQLite database per test session, seeded
from `seed/*.sql`, deleted on teardown. Temp *file*, not `:memory:` — an
in-memory database is per-connection, which breaks the moment the app opens
a second connection and diverges from the WAL/file semantics being tested.
No test run ever touches `data/easymcf.db`.
"""

from __future__ import annotations

import json
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


_USERS = json.load(open(os.path.join(_TESTS_DIR, "support", "users.json"), encoding="utf-8"))


def signed_in(app, name: str):
    """A test client signed in through the real sign-in endpoint as a seeded account (STRAT-SILO-08)."""
    test_client = app.test_client()
    response = test_client.post("/api/v1/auth/signin", json=_USERS[name])
    assert response.status_code == 200, response.get_json()
    return test_client


@pytest.fixture()
def anon_client(app):
    return app.test_client()


@pytest.fixture(scope="session")
def stub_provider():
    """The stub OpenID Connect provider on an ephemeral port, for the whole session."""
    from tests.support import stub_oidc

    server, base_url = stub_oidc.serve()
    yield base_url
    server.shutdown()


@pytest.fixture()
def google_app(db_path, stub_provider, tmp_path, monkeypatch):
    """An app configured for Google sign-in against the stub provider and a temp photo store."""
    secret = tmp_path / "gcp_oauth_client_secret"
    secret.write_text("stub-client-secret\n")
    secret.chmod(0o600)
    monkeypatch.setenv("GOOGLE_DISCOVERY_URL", stub_provider + "/.well-known/openid-configuration")
    monkeypatch.setenv("GCP_OAUTH_CLIENT_ID", "stub-client-id")
    monkeypatch.setenv("GCP_OAUTH_SECRET_FILE", str(secret))
    monkeypatch.setenv("PHOTO_DIR", str(tmp_path / "photos"))
    from easymcf import create_app
    from easymcf.config import Config

    return create_app(Config(db_path=db_path))


from datetime import datetime


@pytest.fixture()
def fixed_clock():
    from easymcf import clock

    def _pin(value: str) -> None:
        clock.set_fixed(datetime.fromisoformat(value))

    yield _pin
    clock.set_fixed(None)


@pytest.fixture()
def isolated_db(tmp_path):
    path = str(tmp_path / "easymcf.db")
    apply_schema(path)
    apply_seed(path)
    return path


@pytest.fixture()
def isolated_client(isolated_db):
    from easymcf import create_app
    from easymcf.config import Config

    return create_app(Config(db_path=isolated_db)).test_client()
