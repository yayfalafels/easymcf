---
name: local-infra-navigation
description: How to locate and run easymcf's local backend, frontend, and SQLite database, and where seed/sample data lives (REQ-DEV-01/02). Use when starting local dev services, resetting the database, or orienting in the repo layout before making changes.
---

# Local dev/test environment navigation

Supports [010-01-requirements.md](../../../docs/releases/010/010-01-requirements.md)'s "Local dev/test environment and seed data" section (REQ-DEV-01..03), owned by milestone 07/08 in [010-release-milestones.md](../../../docs/releases/010/010-release-milestones.md).

## Status: scaffold, not yet backed by a running system

As of this writing, milestones 07 (local dev and test env) and 08 (seed data) have not yet landed — there is no backend run command, frontend serve command, or seed-data location to document yet. This skill exists so it's the obvious place to fill in once they do, rather than letting that knowledge scatter across ad hoc `CLAUDE.md` edits or session memory.

**When milestone 07/08 work adds a real setup procedure, update this file** with:
- how to install backend (Python) and frontend (AngularJS/npm) dependencies
- the actual local run commands for backend, frontend, and SQLite
- where the SQLite database file lives and how to reset it to a clean or seeded state
- where seed/sample data (representative postings, leads, tracks/search profiles) lives and how it's loaded (REQ-DEV-02)
- how to run the automated test suite locally against seed data without live browser automation (REQ-DEV-03)

## Repo layout today

- `easymcf/` — this release's build (this repo).
- `easymcf/docs/releases/` — roadmap and per-release requirements/milestones/design docs; consult before implementing anything (`CLAUDE.md` REQ-AGENT-01).
- `jobsearch/` (sibling repo, `../jobsearch/`) — the prototype being re-platformed. Read-only reference: `agent.py` (search scrape), `mcf_profile.py` (detail scrape), `match.py`/`text.py` (scoring), `apply.py` (apply automation), `gsheet/applicationtrackingapp.gs` (CRM logic). Do not modify.
- `mcfpipe/` (sibling repo, `../mcfpipe/`) — reference data model and API design (`docs/data_model.md`, `docs/database_api.md`, `docs/architecture.md`), and the cautionary example of cloud-first scope creep this release avoids. Do not modify.

## Finding things without re-deriving them

[010-prototype.md](../../../docs/releases/010/010-prototype.md) already extracts the implementation-level detail from both sibling repos that most work needs — check there before reading `jobsearch/`/`mcfpipe/` source directly.
