from __future__ import annotations

import itertools
import sqlite3

import pytest

pytestmark = pytest.mark.backend

STAGES = ["PROSPECT", "TOAPPLY", "APPLIED", "CALLBACK", "INTERVIEW", "OFFER", "CLOSED"]
LEGAL = {
    "PROSPECT": {"TOAPPLY", "CLOSED"}, "TOAPPLY": {"APPLIED", "CLOSED"}, "APPLIED": {"CALLBACK", "CLOSED"},
    "CALLBACK": {"INTERVIEW", "CLOSED"}, "INTERVIEW": {"OFFER", "CLOSED"}, "OFFER": {"CLOSED"}, "CLOSED": set(),
}


def _lead_at(db_path: str, stage: str, n: int) -> int:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        "INSERT INTO post (id, source, position_title, company_name, is_open, src_method) "
        "VALUES (?, 'Matrix', 'Matrix role', 'Matrix Co', 1, 'manual')", (f"matrix-{n}",))
    status = "CLOSED" if stage == "CLOSED" else "OPEN"
    reason = "cancelled" if stage == "CLOSED" else None
    lead_id = conn.execute(
        "INSERT INTO lead (post_id, track_id, status, stage, close_reason, deadline, created_at, updated_at) "
        "VALUES (?, 1, ?, ?, ?, '2099-01-01', '2026-01-01 00:00:00', '2026-01-01 00:00:00')",
        (f"matrix-{n}", status, stage, reason)).lastrowid
    conn.commit()
    conn.close()
    return lead_id


@pytest.mark.parametrize("src,dst", list(itertools.product(STAGES, STAGES)))
def test_transition_matrix(isolated_client, isolated_db, src, dst):
    lead_id = _lead_at(isolated_db, src, STAGES.index(src) * 10 + STAGES.index(dst))
    body = {"stage": dst}
    if dst == "CLOSED" and src != "CLOSED":
        body["close_reason"] = "withdrawn"
    response = isolated_client.put(f"/api/v1/lead/{lead_id}", json=body)
    expected = 200 if src == dst or dst in LEGAL[src] else 409
    assert response.status_code == expected, (src, dst, response.get_json())
