---
name: easymcf-crm
description: Domain knowledge for easymcf's job-leads tracking / CRM pipeline feature (REQ-CRM-01..08) — the lead status/stage state machine, the deadline-maintenance rule behind auto-expiry, and the named regression (unconditional status overwrite) this release must not repeat. Use when implementing or reviewing lead promotion, stage transitions, or expiry handling.
---

# Job leads tracking (CRM pipeline)

Implements [010-01-requirements.md](../../../docs/releases/010/010-01-requirements.md)'s "Job leads tracking" section (REQ-CRM-01..08).

## Core distinction: pipeline status vs. apply status

These are two different questions held in two different fields:

- **pipeline status** — where a lead sits in the user's funnel (structured, first-class value).
- **apply status** — the mechanical outcome of an automated apply attempt (see [easymcf-apply](../easymcf-apply/SKILL.md)).

The prototype's `screened.apply` flag conflated both ("queued to apply" and, after a later step ran, "apply succeeded") — see [010-prototype.md](../../../docs/releases/010/010-prototype.md). Do not reintroduce a single flag doing both jobs.

## Stage state machine (REQ-CRM-02)

A lead carries two separate fields — conflating them is exactly the kind of mistake the "Core distinction" above warns against, and neither is ever the same thing as apply status:

- `status`: `OPEN` (default) or `CLOSED` — whether the lead is active at all.
- `stage`: `PROSPECT` → `TOAPPLY` → `APPLIED` → `CALLBACK` → `INTERVIEW` → `OFFER`, with `CLOSED` reachable from any of them (manual close, or auto: expiry/apply-failure). See [010-workflows.md](../../../docs/releases/010/design/010-workflows.md) Workflow 5 for the full stage diagram.

A lead promoted from a posting (REQ-CRM-01) defaults to `status=OPEN`/`stage=PROSPECT`. `TOAPPLY` replaces the prototype's `screened.apply` flag as the "queue for apply" signal. `APPLIED` is set automatically when an apply attempt records status `applied` (REQ-APPLY-09) or manually.

## Auto-expiry and the regression to guard against (REQ-CRM-05)

The prototype's `updateOpenExpired()` scanned deadlines and **unconditionally overwrote status to `"expired"`** for any row past its deadline — including leads already applied, interviewing, or closed. This was a defect. The 010 guard is `status='OPEN'`: only leads with `status='OPEN'` are evaluated, and every open stage, `PROSPECT` through `OFFER`, is an expiry candidate.

`lead.deadline` is a system-maintained field. It is set at promotion and refreshed from `CALLBACK` onward:

1. at promotion, the post's `closing_date` when that date is after the promotion date, `posted_date` plus 28 days when the post has no `closing_date`, and the promotion date plus 1 week when `closing_date` is on or before the promotion date
2. from `CALLBACK` onward (`CALLBACK`, `INTERVIEW`, `OFFER`), refreshed to 28 days from the most recent logged activity on every update — a genuinely rolling window

A lead auto-closes (`close_reason='expired'`) once the current date passes whatever `deadline` currently holds. Any code that updates lead state on a schedule/condition, rather than a direct user action, must check `status` first and write only when the guard holds.

## Lead fields (REQ-CRM-03/04)

deadline, applied date, first-attempt date, last-contact date, free-text notes, link back to posting profile — mirrors the prototype's `open` sheet. `deadline` is maintained by the system across the lifecycle, per "Auto-expiry" above; a user's own manual edit to it fires the same `deadline_changed` event an automatic reset does. A lead may override title/company independently of its source posting (REQ-CRM-04) and the posting record stays as scraped. Posting and lead are separate records.

## Interaction model (REQ-CRM-07)

All pipeline transitions happen through the AngularJS UI ([easymcf-frontend](../easymcf-frontend/SKILL.md)) via the backend API ([easymcf-backend-api](../easymcf-backend-api/SKILL.md)). The prototype's spreadsheet-menu-script model (`gsheet/applicationtrackingapp.gs`) is a reference for *what actions exist* (promote, close/archive), not for *how* they're triggered in 010.
