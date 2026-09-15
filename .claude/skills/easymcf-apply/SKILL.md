---
name: easymcf-apply
description: Domain knowledge for easymcf's automated apply feature (REQ-APPLY-01..09) — the per-lead apply state machine, full outcome vocabulary, session handling, and the local/seed-data-only test constraint. Use when implementing or reviewing the apply run, CV selection, or apply-outcome recording.
---

# Automated apply

Implements [010-01-requirements.md](../../../docs/releases/010/010-01-requirements.md)'s "Automated apply" section (REQ-APPLY-01..09). Site-specific selectors live in [mycareerfutures](../mycareerfutures/SKILL.md); wait/retry mechanics live in [playwright](../playwright/SKILL.md).

## Hard constraint

Any test or dev run of apply automation must run against local/seed data (REQ-DEV-03), never the live MCF site or a real session cookie, unless the user explicitly runs it interactively themselves. This is the highest-blast-radius skill in the project — a bug here submits real job applications.

## Session handling (REQ-APPLY-06)

No login automation. Apply runs against an already-authenticated session the user supplies (an exported cookie jar, per the prototype's `cookies_mcf.json` pattern). Validate that the session actually matches the target domain before proceeding; a session/authentication failure aborts the *whole run* (not a per-job failure) — there is no per-job fallback at this level.

## Per-lead state machine

Mirrors `jobsearch/apply.py`'s `apply_job()`, adapted to 010's status vocabulary (REQ-APPLY-04):

1. Load the posting URL. Load failure → `post_unavailable`.
2. Poll for the apply button, bounded retries with delay (REQ-APPLY-07 — see [playwright](../playwright/SKILL.md) for the wait pattern). Button found and clickable → click → proceed. Not found, but an "already applied" status message is present → treat as **success**, not a separate failure code. Not found, but a "closed"/"no longer available" message is present → `post_closed`. Retries exhausted with neither signal → `unable_to_apply`.
3. Select the lead's assigned CV (REQ-APPLY-02) by matching its configured CV identifier against the resume options presented on the page; advance. No match among available CVs → `cv_not_found`. A DOM/selector error while locating the resume cards → `cv_selector_error`.
4. Submit the final review. A failed submit here is *inferred* (not confirmed by an explicit questionnaire indicator) to mean the posting requires a multi-step flow → `questionnaire_required` — the run does not attempt to complete it or treat the failure as an error; the user finishes it manually (REQ-APPLY-05, explicit non-goal).
5. Missing required input on a queued lead (jobid/url/cv assignment) is rejected before any browser action → `invalid_input`.

Full outcome vocabulary (REQ-APPLY-04): `applied`, `questionnaire_required`, `cv_selector_error`, `unable_to_apply`, `post_unavailable`, `cv_not_found`, `post_closed`, `invalid_input`.

## Run-level behavior (REQ-APPLY-08)

A failure on one queued lead must not stop the run from attempting the rest, and one lead's recorded outcome must never overwrite another lead's already-recorded outcome — merge results keyed by lead id (the prototype uses pandas `combine_first()` for this), don't replace the whole result set per run.

## Feedback into CRM (REQ-APPLY-09)

A lead whose apply attempt records `applied` automatically transitions its *pipeline* status to `APPLIED` — see [easymcf-crm](../easymcf-crm/SKILL.md) for why apply status and pipeline status are still two separate fields even though this one outcome bridges them.
