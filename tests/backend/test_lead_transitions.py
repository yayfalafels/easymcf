from __future__ import annotations

import itertools
import sqlite3

import pytest

pytestmark = pytest.mark.backend

STAGES = ["TOAPPLY", "APPLIED", "CALLBACK", "INTERVIEW", "OFFER", "CLOSED"]
# What `PUT /lead/{id}` accepts. INTERVIEW -> OFFER and any close at OFFER belong to the offer routes, and
# CLOSED -> INTERVIEW is the re-open, legal only for a lead closed from OFFER (tested below).
LEGAL_PUT = {
    "TOAPPLY": {"APPLIED", "CLOSED"}, "APPLIED": {"CALLBACK", "CLOSED"}, "CALLBACK": {"INTERVIEW", "CLOSED"},
    "INTERVIEW": {"CLOSED"}, "OFFER": set(), "CLOSED": set(),
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
        "INSERT INTO lead (user_id, post_id, track_id, status, stage, close_reason, position_title, company_name, deadline, "
        "created_at, updated_at) VALUES (1, ?, 1, ?, ?, ?, 'Matrix role', 'Matrix Co', '2099-01-01', "
        "'2026-01-01 00:00:00', '2026-01-01 00:00:00')",
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
    expected = 200 if src == dst or dst in LEGAL_PUT[src] else 409
    assert response.status_code == expected, (src, dst, response.get_json())


def test_offer_gates_name_the_offer_routes(isolated_client, isolated_db):
    interview = _lead_at(isolated_db, "INTERVIEW", 901)
    to_offer = isolated_client.put(f"/api/v1/lead/{interview}", json={"stage": "OFFER"})
    assert to_offer.status_code == 409 and "POST /api/v1/offer" in to_offer.get_json()["message"]
    at_offer = _lead_at(isolated_db, "OFFER", 902)
    close = isolated_client.put(f"/api/v1/lead/{at_offer}", json={"stage": "CLOSED", "close_reason": "withdrawn"})
    assert close.status_code == 409 and "through its offer" in close.get_json()["message"]


@pytest.mark.parametrize("closed_from,expected", [("OFFER", 200), ("APPLIED", 409)])
def test_reopen_is_legal_only_for_a_lead_closed_from_offer(isolated_client, isolated_db, closed_from, expected):
    lead_id = _lead_at(isolated_db, "CLOSED", 910 + len(closed_from))
    conn = sqlite3.connect(isolated_db)
    conn.execute(
        "INSERT INTO lead_event (lead_id, event_type, stage_from, stage_to, occurred_at) "
        "VALUES (?, 'stage_change', ?, 'CLOSED', '2026-01-01 00:00:00')", (lead_id, closed_from))
    conn.commit()
    conn.close()
    response = isolated_client.put(f"/api/v1/lead/{lead_id}", json={"stage": "INTERVIEW"})
    assert response.status_code == expected, response.get_json()
    if expected == 200:
        lead = response.get_json()
        assert (lead["status"], lead["stage"], lead["close_reason"]) == ("OPEN", "INTERVIEW", None)
