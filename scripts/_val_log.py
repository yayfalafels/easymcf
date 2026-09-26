"""12.CK.05 — shared structured log writer for scripts/api_tester.py and
scripts/ui_tester.py: one JSON-lines record per case, appended as the run
progresses, so a downstream reader (human or the 12.EL.07/.08 oracle tests)
parses one log shape regardless of which script produced it. Pure logging —
this module never decides a process's exit code; that stays each caller's
own policy (implementation/REFERENCE.md's "no silent failures" convention),
so outcome-vs-exit-code logic never has two places to drift apart.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_SCRIPTS_DIR)
_LOGS_DIR = os.path.join(_REPO_ROOT, ".dev", "logs")


def log_path(tool: str, label: str = "adhoc") -> str:
    """<ts>-<label>-<tool>.log under .dev/logs/, per implementation/REFERENCE.md's
    <feature_id>.<subfeature_id> naming slot — label is the *caller's* task id
    (e.g. "09.09"), not this milestone's own, since 09-11 are the real callers."""
    os.makedirs(_LOGS_DIR, exist_ok=True)
    ts = time.strftime("%Y%m%d%H%M%S")
    return os.path.join(_LOGS_DIR, f"{ts}-{label}-{tool}.log")


def write_record(
    path: str,
    tool: str,
    case: str,
    outcome: str,
    duration_ms: int,
    expected: object = None,
    actual: object = None,
    detail: str | None = None,
    screenshot: str | None = None,
) -> None:
    """Append one JSON-lines record. outcome is PASS/FAIL/ERROR — see
    api_tester.py's/ui_tester.py's own classification logic for what each
    means; this function only shapes and writes, never classifies."""
    assert outcome in ("PASS", "FAIL", "ERROR"), f"unknown outcome: {outcome!r}"
    record = {
        "ts": datetime.now(timezone.utc).astimezone().isoformat(),
        "tool": tool,
        "case": case,
        "outcome": outcome,
        "duration_ms": duration_ms,
        "expected": expected,
        "actual": actual,
        "detail": detail,
    }
    if screenshot is not None:
        record["screenshot"] = screenshot
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
