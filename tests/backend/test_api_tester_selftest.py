"""12.EL.07 — oracle for scripts/api_tester.py's PASS/FAIL/ERROR classification
(12.CK.01/.02). Invoked as a subprocess (process boundary, 12.TC.02), never
imported, so this exercises exactly what an agent running the script would
see. Expected outcomes are hard-coded from the 010.12 tracker's Design
section fixture descriptions, never imported from api_tester.py itself
(010.08's oracle precedent — a bug in the script under test and a check that
only re-reads its own claim shouldn't share a blind spot).
"""

from __future__ import annotations

import glob
import json
import os
import subprocess
import sys

import pytest

_TESTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REPO_ROOT = os.path.dirname(_TESTS_DIR)
_SCRIPTS_DIR = os.path.join(_REPO_ROOT, "scripts")
sys.path.insert(0, _REPO_ROOT)
sys.path.insert(0, _SCRIPTS_DIR)

from initdb import apply_schema  # noqa: E402
from render_seed import PUBLIC_DEFAULTS  # noqa: E402
from resetdb import apply_seed  # noqa: E402
from tests._browser_support import spawn_app, terminate_app  # noqa: E402
from api_tester import _poll  # noqa: E402

pytestmark = pytest.mark.backend

_CASES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cases")
_LOGS_DIR = os.path.join(_REPO_ROOT, ".dev", "logs")


@pytest.fixture(scope="module")
def app_base_url_env(tmp_path_factory):
    """A real spawned app, same pattern as tests/frontend/conftest.py's
    app_base_url — except this yields the process's env dict (carrying the
    ephemeral PORT) rather than a base-url string, since api_tester.py
    resolves its target from Config().port/env PORT, not a CLI flag
    (12.EL.02's note: no --base-url flag was added). Module-scoped, not
    session-scoped, since this fixture is only used within this file."""
    db_path = str(tmp_path_factory.mktemp("easymcf-api-tester-selftest-db") / "easymcf.db")
    apply_schema(db_path)
    apply_seed(db_path, PUBLIC_DEFAULTS)
    proc, base_url = spawn_app(db_path)
    port = base_url.rsplit(":", 1)[-1]
    env = os.environ.copy()
    env["PORT"] = port
    env["DB_PATH"] = db_path
    try:
        yield env
    finally:
        terminate_app(proc)


def _run_api_tester(env: dict, case_file: str, label: str) -> tuple[int, list[dict]]:
    result = subprocess.run(
        [
            sys.executable,
            os.path.join(_REPO_ROOT, "scripts", "api_tester.py"),
            "--case",
            os.path.join(_CASES_DIR, case_file),
            "--label",
            label,
        ],
        cwd=_REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    log_glob = os.path.join(_LOGS_DIR, f"*-{label}-api_tester.log")
    log_files = sorted(glob.glob(log_glob))
    assert log_files, f"no log file matched {log_glob} — stderr:\n{result.stderr}"
    with open(log_files[-1], encoding="utf-8") as f:
        records = [json.loads(line) for line in f]
    return result.returncode, records


def test_live_target_outcomes(app_base_url_env):
    exit_code, records = _run_api_tester(app_base_url_env, "selftest_api_tester.json", "12.TC.live")
    by_name = {r["case"]: r["outcome"] for r in records}
    assert by_name["selftest — health check passes"] == "PASS"
    assert by_name["selftest — deliberately wrong expected body"] == "FAIL"
    assert by_name["selftest — non-JSON body where JSON expected"] == "ERROR"
    assert exit_code != 0  # batch contains a FAIL and an ERROR (12.CK.06)


def test_connection_refused_is_error():
    env = os.environ.copy()
    env["PORT"] = "1"  # a port nothing is listening on
    exit_code, records = _run_api_tester(env, "selftest_api_tester_unreachable.json", "12.TC.unreachable")
    assert records[0]["outcome"] == "ERROR"
    assert exit_code != 0


# 13.TC.37 - the as_user extension (13.EL.46, STRAT-TOOL-05). Expected outcomes are hard-coded from the design.
def test_as_user_cases_pass_and_each_user_keeps_its_own_cookie(app_base_url_env):
    exit_code, records = _run_api_tester(app_base_url_env, "selftest_api_tester_as_user.json", "13.TC.37")
    outcomes = {r["case"]: r["outcome"] for r in records}
    assert len(outcomes) == 7 and set(outcomes.values()) == {"PASS"}, outcomes
    assert exit_code == 0


def test_an_unknown_as_user_is_an_error_not_a_failure(app_base_url_env):
    exit_code, records = _run_api_tester(app_base_url_env, "selftest_api_tester_bad_user.json", "13.TC.37.bad")
    assert records[0]["outcome"] == "ERROR" and "no_such_user" in records[0]["detail"]
    assert exit_code != 0


# 10.EL.31 — oracle for the poll extension (10.EL.25), `_poll` called directly, no HTTP
# server involved: expected outcomes hard-coded from the 010.10 tracker's Validation
# utility extension section, never imported from api_tester.py itself.
class _FakeResponse:
    def __init__(self, body: dict):
        self._body = body

    def json(self):
        return self._body


class _FakeSession:
    """Always answers the same body, regardless of path/kwargs — enough to drive _poll's
    own loop without a real running app."""

    def __init__(self, body: dict):
        self._body = body

    def get(self, _url, timeout=10):  # noqa: ARG002 — signature matches requests.Session.get
        return _FakeResponse(self._body)


def test_poll_reaching_terminal_success_classifies_pass():
    case = {"poll": {"path": "/api/v1/run_log/{id}", "until": {"status": ["success", "partial", "failed"]},
                      "timeout_s": 5}, "expected_final": {"status": "success"}}
    outcome, expected, actual, detail = _poll(_FakeSession({"status": "success"}), "http://unused", case, {"id": 1})
    assert outcome == "PASS" and actual == {"status": "success"} and detail is None


def test_poll_that_never_reaches_terminal_classifies_error():
    case = {"poll": {"path": "/api/v1/run_log/{id}", "until": {"status": ["success", "partial", "failed"]},
                      "timeout_s": 0}, "expected_final": {"status": "success"}}
    outcome, expected, actual, detail = _poll(_FakeSession({"status": "running"}), "http://unused", case, {"id": 1})
    assert outcome == "ERROR" and actual is None and detail is not None


def test_a_rejected_sign_in_is_an_error(app_base_url_env, tmp_path):
    case = tmp_path / "wrong_password.json"
    case.write_text(json.dumps([{"name": "x", "as_user": "seed_a", "method": "GET", "path": "/api/v1/auth/me", "expected_status": 200}]))
    users = tmp_path / "users.json"
    users.write_text(json.dumps({"seed_a": {"email": "demo.user@example.test", "password": "Not-The-Password-1!"}}))
    exit_code, records = _run_api_tester({**app_base_url_env, "EASYMCF_TEST_USERS": str(users)}, str(case), "13.TC.37.rejected")
    assert records[0]["outcome"] == "ERROR" and "returned 401" in records[0]["detail"]
    assert exit_code != 0
