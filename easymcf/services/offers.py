"""REQ-CRM-10 — offers: the only way a lead reaches OFFER, and the only way a lead at OFFER closes."""

from __future__ import annotations

from .. import clock
from ..errors import Conflict, RecordNotFound, ValidationFailed
from . import leads

FINAL_STATUSES = {"accepted": "offer_accepted", "rejected": "rejected", "withdrawn": "withdrawn", "expired": "expired"}


def _load(db, offer_id):
    row = db.execute("SELECT * FROM offer WHERE id = ?", (offer_id,)).fetchone()
    if row is None:
        raise RecordNotFound(f"offer {offer_id} not found")
    return row


def create_offer(db, body: dict) -> int:
    """POST /offer: attach an open offer and move the lead from INTERVIEW to OFFER in one transaction."""
    lead = leads._load(db, body["lead_id"])
    if lead["status"] != "OPEN" or lead["stage"] != "INTERVIEW":
        raise Conflict(f"lead {lead['id']} must be OPEN at INTERVIEW to receive an offer", lead_id=lead["id"])
    at = clock.stamp()
    deadline = body.get("deadline") or lead["deadline"]
    offer_id = db.execute(
        "INSERT INTO offer (lead_id, offer_date, deadline, amount_sgd, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, 'open', ?, ?)",
        (lead["id"], body["offer_date"], deadline, body["amount_sgd"], at, at),
    ).lastrowid
    leads.update_lead(db, lead["id"], {"stage": "OFFER", "deadline": deadline}, internal=True,
                      detail=f"offer attached: S$ {body['amount_sgd']:,} (offer {offer_id})")
    return offer_id


def update_offer(db, offer_id, body: dict) -> None:
    """PUT /offer/{id}: edit an open offer, or set a final status that closes the lead."""
    offer = _load(db, offer_id)
    if offer["status"] != "open":
        raise Conflict(f"offer {offer['id']} is {offer['status']} and read-only", offer_id=offer["id"])
    status = body.get("status")
    if status is not None and status not in FINAL_STATUSES:
        raise ValidationFailed(f"status must be one of {', '.join(FINAL_STATUSES)}", field="status")
    edits = {k: v for k, v in body.items() if k in ("amount_sgd", "deadline") and offer[k] != v}
    values = {**edits, **({"status": status} if status else {})}
    if not values:
        return
    at = clock.stamp()
    sets = ", ".join(f"{column} = ?" for column in values)
    db.execute(f"UPDATE offer SET {sets}, updated_at = ? WHERE id = ?", (*values.values(), at, offer["id"]))
    if "deadline" in edits:
        leads.update_lead(db, offer["lead_id"], {"deadline": edits["deadline"]}, internal=True)
    if status:
        leads.update_lead(db, offer["lead_id"], {"stage": "CLOSED", "close_reason": FINAL_STATUSES[status]},
                          internal=True, detail=f"close_reason: None -> {FINAL_STATUSES[status]}")
