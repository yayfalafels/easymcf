---
name: easymcf-crm
description: Domain knowledge for easymcf's job-leads tracking / CRM pipeline feature (REQ-CRM-01..07) — the lead status state machine and the named regression (unconditional status overwrite) this release must not repeat. Use when implementing or reviewing lead promotion, status transitions, or expiry handling.
---

# Job leads tracking (CRM pipeline)

Implements [010-01-requirements.md](../../../docs/releases/010/010-01-requirements.md)'s "Job leads tracking" section (REQ-CRM-01..07).

## Core distinction: pipeline status vs. apply status

These are two different questions and must stay two different fields, never conflated:

- **pipeline status** — where a lead sits in the user's funnel (structured, first-class value).
- **apply status** — the mechanical outcome of an automated apply attempt (see [easymcf-apply](../easymcf-apply/SKILL.md)).

The prototype's `screened.apply` flag conflated both ("queued to apply" and, after a later step ran, "apply succeeded") — see [010-prototype.md](../../../docs/releases/010/010-prototype.md). Do not reintroduce a single flag doing both jobs.

## Status state machine (REQ-CRM-02)

```
OPEN (default) → TOAPPLY (user queues for apply run)
                → APPLIED (auto on successful apply, or manual)
                → INTERVIEW (manual)
CLOSED — reachable from ANY status (manual, terminal, archive)
```

A lead promoted from a posting (REQ-CRM-01) defaults to `OPEN`. `TOAPPLY` replaces the prototype's `screened.apply` flag as the "queue for apply" signal. `APPLIED` is set automatically when an apply attempt records status `applied` (REQ-APPLY-09) or manually.

## The regression to guard against (REQ-CRM-05)

The prototype's `updateOpenExpired()` scanned deadlines and **unconditionally overwrote status to `"expired"`** for any row past its deadline — including leads already `APPLIED`, `INTERVIEW`, or `CLOSED`. This is a defect, not a design choice. The 010 equivalent must only auto-transition to `EXPIRED` when current status is *not already* `APPLIED`, `INTERVIEW`, or `CLOSED`. Any code that updates lead status on a schedule/condition (not a direct user action) must check current status first — treat an unconditional status write as a bug, not a simplification.

## Lead fields (REQ-CRM-03/04)

deadline, applied date, first-attempt date, last-contact date, free-text notes, link back to posting profile — mirrors the prototype's `open` sheet. A lead may override title/company independently of its source posting (REQ-CRM-04) without mutating the posting record — posting and lead are always separate records, never the same row.

## Interaction model (REQ-CRM-07)

All pipeline transitions happen through the AngularJS UI ([easymcf-frontend](../easymcf-frontend/SKILL.md)) via the backend API ([easymcf-backend-api](../easymcf-backend-api/SKILL.md)). The prototype's spreadsheet-menu-script model (`gsheet/applicationtrackingapp.gs`) is a reference for *what actions exist* (promote, close/archive), not for *how* they're triggered in 010.
