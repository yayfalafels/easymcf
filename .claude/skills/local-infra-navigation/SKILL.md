---
name: local-infra-navigation
description: How to locate and run easymcf's local backend, frontend, and SQLite database, and where seed/sample data lives (REQ-DEV-01/02). Use when starting local dev services, resetting the database, or orienting in the repo layout before making changes.
---

# Local dev/test environment navigation

Supports [010-01-requirements.md](../../../docs/releases/010/010-01-requirements.md)'s "Local dev/test environment and seed data" section (REQ-DEV-01..03), owned by milestone 07/08 in [010-release-milestones.md](../../../docs/releases/010/010-release-milestones.md).

## Python virtual environments — hard rule

There are exactly two reusable Python virtual environments for this project. **Never create a disposable, one-off, or on-the-fly venv (`python -m venv /tmp/...`, a throwaway `.venv` in some scratch dir, etc.) for any operation, ever** — a fresh ad hoc env for every task is exactly the clutter this rule exists to avoid. Every Python operation in this project's development runs through one of the two below.

Both live **inside the repo, at the repo root** — never a home-directory or other external path (`CLAUDE.md`'s hard rule), referenced relative to wherever the repo is checked out:

| Env | Path | Dependency manifest (git-tracked) | Used for |
|---|---|---|---|
| **dev-env** | `.dev/dev-env` | [python-envs/dev-env/pyproject.toml](../../../python-envs/dev-env/pyproject.toml) | One-time/throwaway development tasks: debugging probes, ad hoc diagnostics, generating mock/seed data from rules, exploratory scripts. Nothing here is part of the app's runtime. |
| **ops env** ("main"/operational env) | `env` | [python-envs/ops-env/pyproject.toml](../../../python-envs/ops-env/pyproject.toml) | Anything in the app's actual lifecycle, dev or prod: running the Flask backend, DB init/seed loading, CRUD modules, scraping and apply-automation runs, and maintenance/commissioning/support tasks (data patching, infra stand-up) an operator would run against a real deployment later. |

Both are gitignored (the venv contents, not the manifests) — invoke them as `env/bin/python`, `.dev/dev-env/bin/python` from the repo root, never `~/env`/`~/.dev/dev-env` or a bare `python`.

Rule of thumb from the examples that motivated this: "would this code/task still make sense to run against a live/production instance of the app?" — if yes (run the app, init/patch the DB, scrape/apply, CRUD), it's the **ops env**. If it's disposable scaffolding to get through *this* dev session (a debug probe, a mock-data generator, a scratch script answering "why is X broken") it's the **dev env**.

The same operational-vs-throwaway split governs where a script's *file* lives, not just which venv runs it. `scripts/` is the permanent, git-tracked operational toolkit (`resetdb.py`, `db_util.py`, `api_tester.py`, `ui_tester.py`, `gen_test_data.py`, `envcheck.py`, `restart.sh`, `check_no_secrets.py` — things that still make sense against a real deployment). `.dev/scripts/` (gitignored, never committed) holds one-off probes and setup-verification checks written to get through a specific feature's development, such as `probe_mcf_singpass.py` or `check_gcp_oauth.py` — run with the dev env, kept locally for later reuse instead of deleted outright, but never part of the tracked toolkit.

Both envs are created with plain `python3 -m venv <path>` — this machine's system Python already includes `ensurepip`, so `pip` is present in a freshly created venv with no extra bootstrap step. To (re)sync an env's packages with its `pyproject.toml` after editing dependencies:

```bash
<env-path>/bin/python -c "
import tomllib
deps = tomllib.load(open('python-envs/<dev-env|ops-env>/pyproject.toml', 'rb'))['project']['dependencies']
print('\n'.join(deps))
" | <env-path>/bin/pip install -r /dev/stdin
```

Adding a new dependency: edit the relevant `pyproject.toml` (git-tracked, so the manifest is reviewable like any other code change) and re-run the sync command above — don't `pip install` a package into an env without also recording it in its `pyproject.toml`, or the manifest drifts from what's actually installed.

## Running the app locally

No separate frontend install/build step — the AngularJS frontend is vendored (`frontend/vendor/angular.min.js`/`angular-route.min.js`, committed to git, no npm) and served by the same Flask process as the API, one origin, no CORS. Chromium's binary (for automation/tests) is a one-time download into a user cache, not part of either venv:

```bash
env/bin/python -m playwright install chromium          # once, or after a Playwright version bump
MCF_MODE=fixture env/bin/python -m easymcf &             # starts the backend + serves the frontend
curl -sf http://127.0.0.1:5000/api/v1/health             # confirm it's up
# browser: http://127.0.0.1:5000
kill %1                                                   # stop it when done
```

`MCF_MODE=fixture` is explicit above, not left to `.env` — a bare `python -m easymcf` has none of `tests/conftest.py`'s defensive scrub, and this repo's `.env` may carry a human-confirmed `MCF_MODE=live` left in place from an earlier session (`010.10`'s `10.IS.09`: an agent's own manual smoke test silently made one real request against the live MCF site this way). A human deliberately browsing against live MCF data overrides this explicitly, on purpose, in that one invocation.

Use the tracked restart helper for repeat local runs. It reads and exports `MCF_MODE` from `.env`, reads the configured port, refuses to kill a listener unless `/proc` identifies this repo's `python -m easymcf` process, and starts through the operational environment. The default preserves the database. `--reset-seed` performs the destructive clean-seed flow before starting.

```bash
scripts/restart.sh                 # kill the current EasyMCF listener and restart
scripts/restart.sh --reset-seed    # kill, reset schema and seed data, then restart
```

If Chromium's binary is present but fails to *launch* (a `libnspr4.so`/similar dynamic-linker error), the sandboxed OS is missing shared libraries `playwright install` alone doesn't provide — that needs a one-time, human-run `sudo env/bin/python -m playwright install --with-deps chromium` (or the equivalent `apt-get install`); an agent session has no `sudo` by default.

## Database — location, reset, seed data

The dev scratch database is a single SQLite file at `data/easymcf.db` (gitignored — never committed, never hand-edited). Seed/sample data (representative postings, leads, tracks/search profiles, REQ-DEV-02) lives as plain SQL text under `seed/*.sql`, applied on top of the schema, never opened as a database itself.

```bash
env/bin/python scripts/resetdb.py --seed     # drop + recreate schema + apply seed/*.sql — the only sanctioned reset path
env/bin/python scripts/db_util.py <table> search '{}'    # direct CRUD against any table, bypassing Flask entirely
```

## Automated tests (REQ-DEV-03)

Three tiers, no live browser automation by default — `pytest.ini` deselects the `live` marker (real MCF site, human-gated, never run unattended):

```bash
env/bin/python scripts/envcheck.py && env/bin/python -m pytest
```

`envcheck.py` is a preflight (right venv active, Chromium present, vendor assets present, db schema current, port free, `MCF_MODE` not `live`) — run it before trusting any test failure as a code defect. Narrower runs: `pytest -m backend` (Flask test client, no browser), `pytest -m frontend` (Playwright against a mocked `/api`), `pytest -m e2e` (full stack, real backend + real frontend).

## Validation utilities — ad hoc/iterative agent checking (010.12)

Two scripts, standalone and independent of the pytest tiers above, for driving and checking a running instance while implementing or debugging one endpoint or screen — see `deploy-and-validation-cycle` for when to reach for these versus the pytest tiers.

```bash
# backend — batch-replay every case in a file, or one named case
env/bin/python scripts/api_tester.py --case tests/backend/cases/health.json --label <your-task-id>

# frontend — spawns its own app/browser, batch-replays every check in a file
env/bin/python scripts/ui_tester.py --case tests/frontend/checks/selftest_ui_tester.json --label <your-task-id>
```

Both exit `0` only if every case passes, and write one JSON-lines record per case to `.dev/logs/<ts>-<label>-<tool>.log` alongside the familiar `[PASS]`/`[FAIL]` stdout lines — the log file is what a later analysis step or another agent session reads, not stdout.

## Configuration

No `.env` file is required — every setting has a default. `.env.example` (git-tracked, at the repo root) documents every override-able variable (`DB_PATH`, `PORT`, `SECRETS_DIR`, `MCF_MODE`, `HEADLESS`, `APPLY_POLL_RETRIES`, `APPLY_POLL_DELAY_S`, `APPLY_LIVE_SUBMIT` — no project-specific prefix, an accepted tradeoff given only two venvs and no other project sharing this shell); copy it to `.env` and edit only what you want to change. `.env` itself stays gitignored and is loaded automatically (`python-dotenv`) by `python -m easymcf` and every `scripts/*.py` entry point — never by the test suite, which sets its own env vars explicitly per session so a personal `.env` can't leak into test behavior.

## Repo layout today

- `easymcf/` — this release's build (this repo).
- `easymcf/docs/releases/` — roadmap and per-release requirements/milestones/design docs; consult before implementing anything (`CLAUDE.md` REQ-AGENT-01).
- `jobsearch/` (sibling repo, `../jobsearch/`) — the prototype being re-platformed. Read-only reference: `agent.py` (search scrape), `mcf_profile.py` (detail scrape), `match.py`/`text.py` (scoring), `apply.py` (apply automation), `gsheet/applicationtrackingapp.gs` (CRM logic). Do not modify.
- `mcfpipe/` (sibling repo, `../mcfpipe/`) — reference data model and API design (`docs/data_model.md`, `docs/database_api.md`, `docs/architecture.md`), and the cautionary example of cloud-first scope creep this release avoids. Do not modify.

## Finding things without re-deriving them

[010-prototype.md](../../../docs/releases/010/010-prototype.md) already extracts the implementation-level detail from both sibling repos that most work needs — check there before reading `jobsearch/`/`mcfpipe/` source directly.
