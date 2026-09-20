---
name: easymcf-crm
description: Domain knowledge for easymcf's job-leads tracking / CRM pipeline feature (REQ-CRM-01..12) — the lead status/stage state machine, the offer-gated OFFER stage, the deadline-maintenance rule behind auto-expiry, and the named regression (unconditional status overwrite) this release must not repeat. Use when implementing or reviewing lead creation, stage transitions, batch moves, offers, or expiry handling.
---

# Job leads tracking (CRM pipeline)

Implements [010-01-requirements.md](../../../docs/releases/010/010-01-requirements.md)'s "Job leads tracking" section (REQ-CRM-01..12).

## Core distinction: pipeline status vs. apply status

These are two different questions held in two different fields:

- **pipeline status** — where a lead sits in the user's funnel (structured, first-class value).
- **apply status** — the mechanical outcome of an automated apply attempt (see [easymcf-apply](../easymcf-apply/SKILL.md)).

The prototype's `screened.apply` flag conflated both ("queued to apply" and, after a later step ran, "apply succeeded") — see [010-prototype.md](../../../docs/releases/010/010-prototype.md). Do not reintroduce a single flag doing both jobs.

## Stage state machine (REQ-CRM-02)

A lead carries two separate fields — conflating them is exactly the kind of mistake the "Core distinction" above warns against, and neither is ever the same thing as apply status:

- `status`: `OPEN` (default) or `CLOSED` — whether the lead is active at all.
- `stage`: `TOAPPLY` → `APPLIED` → `CALLBACK` → `INTERVIEW` → `OFFER`, with `CLOSED` reachable from any of them (manual close, batch drop, or auto: expiry/apply-failure). `OFFER` is reached only through an offer, a lead at `OFFER` closes only through its offer's status, and a lead closed from `OFFER` can re-open at `INTERVIEW`. See [010-workflows.md](../../../docs/releases/010/design/010-workflows.md) Workflow 5 for the full stage diagram.

Promotion is a system action: the search process promotes each qualifying post (REQ-CRM-01) into a lead at `status=OPEN`/`stage=TOAPPLY`, and the user adds a lead manually at `APPLIED` (the form creates a copy of the post with it). No user-facing promote control exists. Every `lead_event` records `stage_from` and `stage_to`: the promotion runs from no stage to `TOAPPLY` (`APPLIED` for a manual add), a transition from the old stage to the new one, and every other event holds the current stage in both. The open `TOAPPLY` leads are the apply queue and replace the prototype's `screened.apply` flag as the "queue for apply" signal. `APPLIED` is set automatically when an apply attempt records status `applied` (REQ-APPLY-09) or manually.

## Auto-expiry and the regression to guard against (REQ-CRM-05)

The prototype's `updateOpenExpired()` scanned deadlines and **unconditionally overwrote status to `"expired"`** for any row past its deadline — including leads already applied, interviewing, or closed. This was a defect. The 010 guard is `status='OPEN'`: only leads with `status='OPEN'` are evaluated, and every open stage, `TOAPPLY` through `OFFER`, is an expiry candidate.

`lead.deadline` is a system-maintained field. It is set at creation, refreshed at `CALLBACK` and `INTERVIEW`, and follows the open offer's deadline at `OFFER`:

1. at creation, the post's `closing_date` when that date is after the promotion date, `posted_date` plus 28 days when the post has no `closing_date`, and the creation date plus 1 week when `closing_date` is on or before the creation date
2. at `CALLBACK` and `INTERVIEW`, refreshed to 28 days from the most recent logged activity on every update — a genuinely rolling window
3. at `OFFER`, the deadline of the lead's open offer, which activity does not move

A lead auto-closes (`close_reason='expired'`) once the current date passes whatever `deadline` currently holds. Any code that updates lead state on a schedule/condition, rather than a direct user action, must check `status` first and write only when the guard holds.

## Lead fields (REQ-CRM-03/04)

deadline, applied date, first-attempt date, last-contact date, free-text notes, link back to posting profile — mirrors the prototype's `open` sheet. `deadline` is maintained by the system across the lifecycle, per "Auto-expiry" above; a user's own manual edit to it fires the same `deadline_changed` event an automatic reset does. A lead may override title/company independently of its source posting (REQ-CRM-04) and the posting record stays as scraped. Posting and lead are separate records.

## Expected salary, batch moves, offers, and track (REQ-CRM-09..12)

- `expected_salary_sgd` is copied from the track's search profile `min_salary` when the lead is created, and the user edits it on Lead Detail at any stage. Lists show it, and at `OFFER` they show the offer amount instead.
- The `TOAPPLY` column moves many leads at once through `POST /api/v1/lead/batch` (the generic `batch` shape opened on `lead`): `Apply` sends `stage: APPLIED` and `Drop` sends `stage: CLOSED` with `close_reason: dropped`. The batch is atomic, each row goes through the same `update_lead` write path as `PUT /lead/{id}`, and a drop asks for confirmation with the lead count.
- An `offer` (`open`, `accepted`, `rejected`, `withdrawn`, `expired`) is created through `POST /api/v1/offer` on an `INTERVIEW` lead, which moves the lead to `OFFER` in the same transaction. While `open`, its amount and deadline are editable, a final status closes the lead (`offer_accepted`, `rejected`, `withdrawn`, `expired`) and makes the offer read-only, offers are never deleted, and a lead closed from an offer can be re-opened at `INTERVIEW` and given a new offer.
- The user can re-assign a lead to another active track from Lead Detail (`PUT /lead/{id}` with `track_id`, logged as a `field_edited` event). The stage, deadline, and expected salary stay as they were.

## Interaction model (REQ-CRM-07)

All pipeline transitions happen through the AngularJS UI ([easymcf-frontend](../easymcf-frontend/SKILL.md)) via the backend API ([easymcf-backend-api](../easymcf-backend-api/SKILL.md)). The prototype's spreadsheet-menu-script model (`gsheet/applicationtrackingapp.gs`) is a reference for *what actions exist* (promote, close/archive), not for *how* they're triggered in 010.
