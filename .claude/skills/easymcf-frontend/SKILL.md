---
name: easymcf-frontend
description: Domain knowledge for easymcf's AngularJS frontend (REQ-FE-01..02) — the screen-to-requirement mapping and the constraint that this release commits to AngularJS, not a framework migration. Use when implementing or reviewing any frontend screen, controller, or run-status/error surfacing.
---

# Frontend (AngularJS SPA)

Implements [010-01-requirements.md](../../../docs/releases/010/010-01-requirements.md)'s "Frontend" section (REQ-FE-01..02).

## Framework commitment

`010` commits to AngularJS (the legacy 1.x framework, `docs.angularjs.org` — not to be confused with modern Angular 2+), per the roadmap's feature table in [release-roadmap.md](../../../docs/releases/release-roadmap.md). Do not introduce a different frontend framework or propose a migration as part of this release — that tradeoff was already made at the roadmap level. Follow standard AngularJS structure: modules, controllers, services for API calls, directives for reusable UI — see the [AngularJS Developer Guide](https://docs.angularjs.org/guide) and the community [AngularJS style guide](https://github.com/mgechev/angularjs-style-guide) (one component per file, controllers not defined as globals, consistent DI syntax) for conventions.

## Screens required (REQ-FE-01)

Every spreadsheet tab and menu action the `jobsearch` prototype relied on (see [010-prototype.md](../../../docs/releases/010/010-prototype.md)) is replaced by an equivalent screen or control here — nothing falls back to a spreadsheet or manual file edit:

- **Track / search-profile configuration** — create/edit tracks, each with its search profile (keywords, salary, age, employment type). See [easymcf-jobs-pipeline](../easymcf-jobs-pipeline/SKILL.md).
- **Posting / results browsing** — postings with per-track match scores, for prioritization.
- **Pipeline / lead management by status** — the CRM board/list driven by lead status. See [easymcf-crm](../easymcf-crm/SKILL.md).
- **Apply-queue review and results** — prune the apply queue (the `TOAPPLY` leads) with batch `Apply` and `Drop`, and review recorded outcomes. See [easymcf-apply](../easymcf-apply/SKILL.md).

## Run status surfacing (REQ-FE-02)

Backend-triggered search and apply runs must surface status and errors *in the UI* — a failure visible only in a console or log file does not satisfy this requirement. Pair with [easymcf-backend-api](../easymcf-backend-api/SKILL.md)'s run-logging requirement: the UI should be reading and displaying that same run history, not maintaining a separate status concept.
