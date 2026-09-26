"""12.EL.01 selftest — 12.CK.05's shared-schema guarantee, checked directly
against _val_log.write_record rather than by spawning both scripts, since
field parity is a property of the one shared function both scripts call
(structural, not behavioral). The only intentional divergence is the
`screenshot` key, present on a ui_tester FAIL/ERROR record and absent
everywhere else — asserted explicitly rather than assumed.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

pytestmark = pytest.mark.backend

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_REPO_ROOT, "scripts"))

import _val_log  # noqa: E402


def _last_record(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    return json.loads(lines[-1])


def test_base_field_set_matches_across_tools(tmp_path):
    api_log = str(tmp_path / "api.log")
    ui_log = str(tmp_path / "ui.log")

    _val_log.write_record(api_log, "api_tester", "case a", "PASS", 5, expected=None, actual=None, detail=None)
    _val_log.write_record(ui_log, "ui_tester", "case b", "PASS", 5, expected=None, actual=None, detail=None)

    api_record = _last_record(api_log)
    ui_record = _last_record(ui_log)
    assert set(api_record) == set(ui_record) == {
        "ts", "tool", "case", "outcome", "duration_ms", "expected", "actual", "detail",
    }


def test_screenshot_key_only_present_when_supplied(tmp_path):
    log_path = str(tmp_path / "ui.log")
    _val_log.write_record(log_path, "ui_tester", "no screenshot", "PASS", 5)
    _val_log.write_record(log_path, "ui_tester", "with screenshot", "FAIL", 5, screenshot="/tmp/x.png")

    with open(log_path, encoding="utf-8") as f:
        records = [json.loads(line) for line in f]
    assert "screenshot" not in records[0]
    assert records[1]["screenshot"] == "/tmp/x.png"
