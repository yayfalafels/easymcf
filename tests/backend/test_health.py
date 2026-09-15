"""Tier 1 smoke case (ARCH-TEST-03): drives `tests/backend/cases/health.json`
through the Flask test client — the same case format `scripts/api_tester.py`
(ENV-SCRIPT-04) replays with `requests` against a live process, so a
failing case can be reproduced either way without maintaining two case sets.
"""

from __future__ import annotations

import json
import os

import pytest

_CASES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cases", "health.json")

with open(_CASES_PATH, "r", encoding="utf-8") as _f:
    _CASES = json.load(_f)


@pytest.mark.backend
@pytest.mark.parametrize("case", _CASES, ids=lambda c: c["name"])
def test_health_cases(client, case):
    resp = client.open(case["path"], method=case["method"], json=case.get("body"))
    assert resp.status_code == case["expected_status"]
    if "expected_body" in case:
        assert resp.get_json() == case["expected_body"]
