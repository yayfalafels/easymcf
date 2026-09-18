"""12.EL.08 — oracle for scripts/ui_tester.py's PASS/FAIL/ERROR classification
and screenshot capture (12.CK.03/.04). ui_tester.py spawns its own app
internally (12.EL.03), so this test needs no app_base_url fixture — it only
invokes the script as a subprocess and reads back its log + screenshot.
"""

from __future__ import annotations

import glob
import json
import os
import subprocess
import sys

import pytest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_CHECKS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "checks")
_LOGS_DIR = os.path.join(_REPO_ROOT, ".dev", "logs")


def _run_ui_tester(api_mode: str, label: str, name: str | None = None) -> tuple[int, list[dict]]:
    args = [
        sys.executable,
        os.path.join(_REPO_ROOT, "scripts", "ui_tester.py"),
        "--case",
        os.path.join(_CHECKS_DIR, "selftest_ui_tester.json"),
        "--api-mode",
        api_mode,
        "--label",
        label,
    ]
    if name is not None:
        args += ["--name", name]
    result = subprocess.run(args, cwd=_REPO_ROOT, capture_output=True, text=True, timeout=60)
    log_glob = os.path.join(_LOGS_DIR, f"*-{label}-ui_tester.log")
    log_files = sorted(glob.glob(log_glob))
    assert log_files, f"no log file matched {log_glob} — stderr:\n{result.stderr}"
    with open(log_files[-1], encoding="utf-8") as f:
        records = [json.loads(line) for line in f]
    return result.returncode, records


@pytest.mark.e2e
def test_real_mode_outcomes_and_screenshots():
    exit_code, records = _run_ui_tester("real", "12.TC.real")
    by_name = {r["case"]: r for r in records}
    assert by_name["selftest — env-status heading renders"]["outcome"] == "PASS"

    fail_record = by_name["selftest — deliberately wrong expected heading text"]
    assert fail_record["outcome"] == "FAIL"
    assert os.path.exists(fail_record["screenshot"])

    error_record = by_name["selftest — nonexistent selector times out"]
    assert error_record["outcome"] == "ERROR"
    assert os.path.exists(error_record["screenshot"])

    assert exit_code != 0  # batch contains a FAIL and an ERROR (12.CK.06)


@pytest.mark.frontend
def test_mocked_mode_wiring_smoke():
    """Known limitation (010.12 Design section): env-status makes no /api
    call, so this only proves --api-mode mocked doesn't error out wiring
    page.route() — not that a mocked response diverges from a real one.
    Closes once milestone 09 adds the first API-backed screen. Runs only the
    PASS check by name — the FAIL/ERROR checks are already covered in real
    mode above, and this test's job is only to prove the mocked-mode flag
    doesn't itself break wiring, not to re-run the full batch a second time."""
    exit_code, records = _run_ui_tester("mocked", "12.TC.mocked", name="selftest — env-status heading renders")
    assert records[0]["outcome"] == "PASS"
    assert exit_code == 0
