---
name: local-infra-navigation
description: How to locate and run easymcf's local backend, frontend, and SQLite database, and where seed/sample data lives (REQ-DEV-01/02). Use when starting local dev services, resetting the database, or orienting in the repo layout before making changes.
---

# Local dev/test environment navigation

Supports [010-01-requirements.md](../../../docs/releases/010/010-01-requirements.md)'s "Local dev/test environment and seed data" section (REQ-DEV-01..03), owned by milestone 07/08 in [010-release-milestones.md](../../../docs/releases/010/010-release-milestones.md).

## Python virtual environments — hard rule

There are exactly two reusable Python virtual environments for this project. **Never create a disposable, one-off, or on-the-fly venv (`python -m venv /tmp/...`, a throwaway `.venv` in some scratch dir, etc.) for any operation, ever** — a fresh ad hoc env for every task is exactly the clutter this rule exists to avoid. Every Python operation in this project's development runs through one of the two below.

| Env | Path | Dependency manifest (git-tracked) | Used for |
|---|---|---|---|
| **dev-env** | `~/.dev/dev-env` | [python-envs/dev-env/pyproject.toml](../../../python-envs/dev-env/pyproject.toml) | One-time/throwaway development tasks: debugging probes, ad hoc diagnostics, generating mock/seed data from rules, exploratory scripts. Nothing here is part of the app's runtime. |
| **ops env** ("main"/operational env) | `~/env` | [python-envs/ops-env/pyproject.toml](../../../python-envs/ops-env/pyproject.toml) | Anything in the app's actual lifecycle, dev or prod: running the Flask backend, DB init/seed loading, CRUD modules, scraping and apply-automation runs, and maintenance/commissioning/support tasks (data patching, infra stand-up) an operator would run against a real deployment later. |

Rule of thumb from the examples that motivated this: "would this code/task still make sense to run against a live/production instance of the app?" — if yes (run the app, init/patch the DB, scrape/apply, CRUD), it's the **ops env**. If it's disposable scaffolding to get through *this* dev session (a debug probe, a mock-data generator, a scratch script answering "why is X broken") it's the **dev env**.

Both envs are created with `python3 -m venv --without-pip <path>` (this machine's system Python has no `pip`/`ensurepip`/`python3-venv`, and installing those needs `sudo`, which agent sessions don't have) then bootstrapped via `bootstrap.pypa.io/get-pip.py` inside the venv. To (re)sync an env's packages with its `pyproject.toml` after editing dependencies:

```bash
<env-path>/bin/python -c "
import tomllib
deps = tomllib.load(open('python-envs/<dev-env|ops-env>/pyproject.toml', 'rb'))['project']['dependencies']
print('\n'.join(deps))
" | <env-path>/bin/pip install -r /dev/stdin
```

Adding a new dependency: edit the relevant `pyproject.toml` (git-tracked, so the manifest is reviewable like any other code change) and re-run the sync command above — don't `pip install` a package into an env without also recording it in its `pyproject.toml`, or the manifest drifts from what's actually installed.

## Status: partial scaffold — envs exist, app doesn't yet

The two Python environments above are set up and installable, but milestones 07 (local dev and test env) and 08 (seed data) haven't otherwise landed — there is no backend run command, frontend serve command, or seed-data location to document yet. This skill exists so it's the obvious place to fill in once they do, rather than letting that knowledge scatter across ad hoc `CLAUDE.md` edits or session memory.

**When milestone 07/08 work adds a real setup procedure, update this file** with:
- how to install frontend (AngularJS/npm) dependencies (Python deps are covered above)
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
