# Easy MCF POC Local - Development Environment

Release `010` design. Source: [docs/releases/010/design/010-development-env.md](https://github.com/yayfalafels/easymcf/blob/main/docs/releases/010/design/010-development-env.md).

## Contents

- [Purpose](#purpose)
- [Out of scope](#out-of-scope)
- [References](#references)
- [Guiding constraint](#guiding-constraint)
- [1. Runtimes, SDKs, and the two-venv model](#1-runtimes-sdks-and-the-two-venv-model) 
- [2. Configuration surface](#2-configuration-surface) 
- [3. Reusable, re-runnable scripts](#3-reusable-re-runnable-scripts) 
- [4. Running the app interactively](#4-running-the-app-interactively)
- [5. The agent's closed install → build → run → test → debug loop, per component](#5-the-agents-closed-install--build--run--test--debug-loop-per-component) 
- [6. Troubleshooting signatures](#6-troubleshooting-signatures) 


## Purpose

This document is the concrete runbook that implements the **architecture doc** and the **test-strategy doc** as an actual, executable environment. It covers the architecture doc's `ARCH-RUN`/`STO`/`NET`/`BOT`/`TEST` decision groups and the test-strategy doc's `STRAT-SILO`/`CASE`/`LOOP` decision groups. It fixes four things.

01. the exact SDK/runtime install steps.
02. the full environment-variable and config surface an operator or agent actually sets.
03. the CLI contract of every reusable helper script.
04. the closed install → build → run → test → debug sequence for each project component: data model, backend API, automation, and frontend.

It is written so a Claude Code agent can execute it unattended, read the failure signal, fix the code, and re-run without a human in the loop.

It elaborates architecture and test-strategy the same way the **api doc** elaborates `ARCH-RUN-10` and the **frontend-app doc** elaborates `ARCH-TEST-05/09`. It does not re-decide anything either document already fixed. It only makes those decisions operable.

It is the direct input milestone 07, local dev and test env, is implemented against. The **infra-navigation skill** and the **deploy-cycle skill** both explicitly scaffold "waiting on this document plus milestone 07/08" and get filled in from here once that implementation lands.

Decisions carry an `ENV-*` id grouped `SETUP`/`CFG`/`SCRIPT`/`LOOP`/`TRBL`, mirroring the `ARCH-*`/`STRAT-*` convention.

## Out of scope

01. seed dataset content. Milestone 08 owns what `seed/*.sql` contains. This document only fixes how it's loaded.
02. test case enumeration, which is scope for milestone 03/`010-test-cases.md`.

## References

Every alias below is used bolded, unlinked, throughout the rest of this document instead of repeating the full link. Resolve it back to the row here.

- **architecture doc** — [010-architecture.md](architecture.md) — `ARCH-RUN-01..10` fixes the runtime/process model and repo layout, `ARCH-STO-01..07` fixes storage, seed, and reset, `ARCH-BOT-01..05` fixes Playwright, `ARCH-TEST-01..09` fixes tier mechanics. This document does not restate any of these. It operationalizes them.
- **test-strategy doc** — [010-test-strategy.md](https://github.com/yayfalafels/easymcf/blob/main/docs/releases/010/design/010-test-strategy.md) — `STRAT-SILO-01..07` names the helper scripts (`db_util.py`, `api_tester.py`) and the frontend silo this document gives install/run instructions for. `STRAT-LOOP`, the agent's silo-aware build→test→debug table, is what section 5 below adds a preflight/install layer beneath.
- **requirements doc** — [010-01-requirements.md](https://github.com/yayfalafels/easymcf/blob/main/docs/releases/010/design/010-01-requirements.md) — REQ-DEV-01..05, the requirement this whole document satisfies.
- **api doc** — [010-api.md](api.md) — `API-EP-07 GET /api/v1/health`, the readiness probe section 4 polls.
- **frontend-app doc** — [010-frontend-app.md](frontend-app.md) — the sibling design doc, elaborated under the same milestone-06 grouping this document belongs to.
- `CLAUDE.md` — the two-venv hard rule, `.dev/dev-env` and `env`, both nested inside the repo at the repo root, that this document's install section maps onto `ARCH-RUN-05`. Kept unaliased below since it is already short and never linked, being a root-level file with no relative path to carry.
- **infra-navigation skill** — [local-infra-navigation](https://github.com/yayfalafels/easymcf/blob/main/.claude/skills/local-infra-navigation/SKILL.md) — scaffold skill this document is written to fill in. Once milestone 07 is implemented, its content should be copied forward from here rather than re-derived.
- **deploy-cycle skill** — [deploy-and-validation-cycle](https://github.com/yayfalafels/easymcf/blob/main/.claude/skills/deploy-and-validation-cycle/SKILL.md) — same scaffold status as the infra-navigation skill. It is the golden-path checklist this document's automated loop, section 5, is meant to make redundant, tier by tier.
- `python-envs/dev-env/pyproject.toml`, `python-envs/ops-env/pyproject.toml` — the manifests section 1 fixes the target dependency contents of. Kept unaliased since these are plain file paths, not linked docs.
- **local-dev-env tracker** — [010.07-local-dev-env.md](https://github.com/yayfalafels/easymcf/blob/main/docs/releases/010/features/010.07-local-dev-env.md) — the feature tracker whose `07.05` task breakdown produces the artifacts this document's bootstrap sequence assumes already exist.

## Guiding constraint

This document follows the lowest-ceremony principle `ARCH-RUN`'s preamble states, with one addition specific to this document. Every step below must be expressible as a single non-interactive shell command with an exit code. This document exists so an agent runs it unattended. No step may require watching a terminal, clicking through a wizard, or interpreting colored output. Where a step is inherently human-gated, tier 3 live testing, `.secrets/mcf_session.json` upload, that gate is stated explicitly, not left implicit.

## 1. Runtimes, SDKs, and the two-venv model

**ENV-SETUP-01 Mapping `ARCH-RUN-05` onto the two-venv rule.** `ARCH-RUN-05` already fixes both the dependency mechanism, Python 3.11+, plain `venv` plus `pip`, no poetry/pdm/uv, no lockfile, and the manifest format, one `pyproject.toml` per venv, no `requirements.txt`/`requirements-dev.txt` split, against `CLAUDE.md`'s two-venv rule. This document adds only which venv is used for what. `env`, the ops venv, is the concrete realization of `ARCH-RUN-05`'s single venv for everything in the app's actual lifecycle: running `python -m easymcf`, `scripts/initdb.py`/`resetdb.py`, and the automated test suite. Tests are included deliberately and are not filed under "throwaway": `tests/backend/` imports `create_app()` and drives it via Flask's test client, and `tests/frontend/`/`tests/e2e/` spawn the real `python -m easymcf` process. Both need the exact runtime the app needs, not a separate one. `.dev/dev-env` remains scoped to what the **infra-navigation skill** already says: throwaway diagnostic probes, ad hoc mock-data generation, exploratory scripts. It never holds anything imported by `easymcf/` or `tests/`.

**ENV-SETUP-02 Target `python-envs/ops-env/pyproject.toml` contents.** The manifest as it stands predates `ARCH-BOT-01`'s decision and is missing the test/schema-validation packages `ARCH-RUN-05` names. It also drops `scikit-learn`. REQ-SRCH-09 and the jobs-pipeline skill deliberately leave the scoring method open rather than committing to the prototype's exact bigram/`CountVectorizer` approach, so pulling in a scoring library ahead of that design work is premature. `pandas`/`numpy` stay, since basic tabular/array handling for scoring is a safe bet independent of which method is eventually chosen. Target state:

| id | package         | status | why                                                                |
| -- | --------------- | ------ | ------------------------------------------------------------------- |
| 01 | flask           | keep   | `ARCH-RUN-01` — backend + static-file serving                       |
| 02 | playwright      | add    | `ARCH-BOT-01` — single browser dependency, scraping+apply+e2e       |
| 03 | jsonschema      | add    | `ARCH-RUN-10`/REQ-PLAT-01 — schema-validated generic CRUD           |
| 04 | beautifulsoup4  | keep   | detail-page/list-page HTML parsing (`010-prototype.md`)             |
| 05 | html5lib        | add    | `ARCH-RUN-05` — lenient HTML parser BS4 backend for MCF markup      |
| 06 | pytest          | add    | `ARCH-TEST-02` — single test runner, all four tiers                 |
| 07 | pytest-timeout  | add    | `ARCH-TEST-02` — 60s hard ceiling per test                          |
| 08 | requests        | keep   | `scripts/api_tester.py`'s interactive mode (`STRAT-SILO-03`)        |
| 09 | python-dotenv   | keep   | optional personal `.env` overrides (`ENV-CFG-02`/`03`), not required |
| 10 | pandas          | keep   | scoring/matching (`010-prototype.md`'s `match.py`)     |
| 11 | numpy           | keep   | scoring/matching — unaffected                                       |
| 12 | authlib         | add    | `ARCH-AUTH-01` — Google OpenID Connect authorization code flow      |
| 13 | pillow          | add    | `ARCH-AUTH-07` — profile photo validation and re-encoding           |

Applying this table is a `python-envs/ops-env/pyproject.toml` edit plus the sync command below. It is implementation work for milestone 07. `python-envs/dev-env/pyproject.toml` needs no change: `pytest`, `ipython`, `faker`, and `requests` already match what throwaway diagnostic/mock-data work needs.

**ENV-SETUP-03 Sync command.** After editing either manifest, re-sync the corresponding venv, per the **infra-navigation skill**'s pattern. Never `pip install` a package without recording it in the manifest first:

```bash
env/bin/python -c "
import tomllib
deps = tomllib.load(open('python-envs/ops-env/pyproject.toml', 'rb'))['project']['dependencies']
print('\n'.join(deps))
" | env/bin/pip install -r /dev/stdin
```

**ENV-SETUP-04 Playwright browser binary.** `pip install playwright` installs the Python package only. The Chromium binary is a separate download into a user cache, `~/.cache/ms-playwright`, not the repo:

```bash
env/bin/python -m playwright install chromium
```

Do **not** add `--with-deps` by default. It shells out to `apt-get` for OS-level shared libraries, which needs `sudo`, unavailable to agent sessions on this machine. This is the same constraint the **infra-navigation skill** already notes for bootstrapping `pip` itself. Run plain `playwright install chromium` first. Only escalate to a human for the `--with-deps` / manual `apt-get` path if the browser fails to launch with a missing-shared-library error (`ENV-TRBL-09` below).

**ENV-SETUP-05 Frontend vendored assets.** Per `ARCH-RUN-06`/`ARCH-NET-03` the frontend is vendored `angular.min.js`, no CDN reference at runtime, no npm. The **frontend-app doc**'s `FE-APP-01` fixes where in the repo it lands: `frontend/vendor/angular.min.js`, `angular-route.min.js`.

Pinned version: **AngularJS 1.8.3**, the final 1.x release, matching `ARCH-RUN-06`'s already-accepted EOL tradeoff. There is no reason to track a later 1.x patch that doesn't exist. This is a one-time fetch, run once by whoever implements this milestone. It is not a routine step re-run per clone. The files are committed to git afterward, the same as any other vendored asset:

```bash
mkdir -p frontend/vendor
curl -sfL https://ajax.googleapis.com/ajax/libs/angularjs/1.8.3/angular.min.js -o frontend/vendor/angular.min.js
curl -sfL https://ajax.googleapis.com/ajax/libs/angularjs/1.8.3/angular-route.min.js -o frontend/vendor/angular-route.min.js
git add frontend/vendor/angular.min.js frontend/vendor/angular-route.min.js
```

This is the one step in this document that is not part of the routine agent loop below, section 5, precisely because it's a one-time commit, not a per-session install. `scripts/envcheck.py` (`ENV-SCRIPT-05`) checks that the two files are present. It never fetches them, and no code path in the running app or its tests reaches `ajax.googleapis.com`. `ARCH-NET-03` still holds: this curl runs once, by a human or an agent doing this specific milestone's implementation work, never as part of `ENV-SETUP-07`'s bootstrap or any test tier.

**ENV-SETUP-06 Minimal frontend bootstrap shell.** The **frontend-app doc**'s `FE-APP-01` `app/` tree is the full eight-screen target, built out across milestones 09-11. This document's frontend/e2e test tiers (`ENV-LOOP-06`) need something real to load before any of those screens exist, otherwise they can only collect and pass vacuously, with no assertion behind the pass. A human opening the app in an ordinary browser needs the same thing, otherwise they see a blank page and have no way to tell the environment apart from a broken one.

This document fixes it as a shell rather than a full screen. Four files, hand-authored:

01. `frontend/index.html` — the `ng-app` root from `FE-APP-01`'s tree. It loads `vendor/angular.min.js`, `vendor/angular-route.min.js`, `app/app.module.js`, `app/app.routes.js`, in that order, per `FE-APP-03`'s load-order rule, with a single `<div ng-view>` body.
02. `frontend/app/app.module.js` — `angular.module('easymcfApp', ['ngRoute'])` per `FE-APP-02`, nothing else.
03. `frontend/app/app.routes.js` — **one** route, `/` → `env-status`. `FE-RTE-01`'s route table gets its first real entry here, a placeholder default that milestones 09-11 repoint at whichever real screen becomes the app's landing page. There is no `/tracks`, `/leads`, and so on yet. Each of milestones 09-11 adds its own route entry as it builds that screen.
04. `frontend/app/env-status/env-status.controller.js` + `env-status.html` — the one screen this milestone renders (milestone 09 removed it and repointed `/` at `/leads`, so the app opens on the Leads page): static text confirming the shell is alive, for example `<h1 data-testid="env-status-heading">Easy MCF — local dev environment ready</h1>`, following `FE-TEST-01`'s `data-testid` convention, so the assertion below has a deliberate contract instead of reverse-engineering one from markup.

**Two independent health checks.**

`env-status` does **not** call `GET /api/v1/health`, even though that would be a natural way to prove frontend-to-backend wiring in one page. `API-EP-07` fixes that endpoint as used by the mock-e2e test harness's readiness poll, with application code never calling it. Routing the frontend's own render path through it would quietly repeal that restriction.

Keeping the two checks separate is also the stronger evidence. A human confirms the frontend stack (this page) and confirms the backend independently (section 4's `curl`, unchanged). These are two independent proofs, neither able to paper over a defect in the other, rather than one page whose "backend: ok" text could itself be the thing hiding a bug.

`ENV-LOOP-06` below is what actually exercises this shell. Its first `pytest -m frontend`/`-m e2e` run is a **DOM-level assertion**: the page contains `[data-testid="env-status-heading"]` with the expected text. This follows `ARCH-TEST-05`'s own assertion convention, asserting rendered text/element state and never a JS-internals check like `window.angular.module(...)` resolving, and never something requiring a person to look at a browser to know if it passed.

That assertion is checking the same thing a human opening `http://127.0.0.1:5000` in an ordinary browser sees (section 4 below). It proves the vendor-asset + Flask-static-serving + Angular-bootstrap + routing wiring end to end. Each of milestones 09-11 replaces this placeholder screen's route, not its own screen's route, with a real one as it's built. Milestone 07 does not pre-create empty placeholder folders (`tracks/`, `leads/`, and so on) for screens it doesn't implement.

**ENV-SETUP-07 First-time bootstrap sequence.** In order, each step gated on the previous one's exit code:

```bash
# 1. dependencies (assumes env already exists per the infra-navigation skill)
env/bin/python -c "import tomllib; ..." | env/bin/pip install -r /dev/stdin   # ENV-SETUP-03

# 2. browser binary
env/bin/python -m playwright install chromium                                   # ENV-SETUP-04

# 3. schema + seed, dev scratch database
env/bin/python scripts/resetdb.py --seed                                         # ARCH-STO-06

# 4. start the app in the background, confirm it's serving
env/bin/python -m easymcf &
curl -sf http://127.0.0.1:5000/api/v1/health

# 5. run the unattended test tiers
env/bin/python -m pytest
```

Frontend vendored assets (`ENV-SETUP-05`) are not a step in this sequence. They're committed to git once, during this milestone's implementation, so every subsequent clone already has them. Step 5 above (`pytest -m frontend`/`-m e2e`) is what actually exercises them, and `envcheck.py` is what catches it early if they're ever missing. Step 5 succeeding end to end, exit code 0, is the definition of "environment correctly set up," not a subjective checklist.

This five-step sequence is the **steady-state, repeat-clone bootstrap**. It assumes `scripts/*.py`, `easymcf/`, `frontend/`, including `ENV-SETUP-05`/`06`'s vendored assets and bootstrap shell, and the pytest scaffold already exist and are already committed. It is not literally runnable on the first day milestone 07 implements those artifacts: step 3 has no `resetdb.py` to call yet, and step 5 has no test scaffold to collect. The **local-dev-env tracker**'s `07.05` task breakdown fixes the one-time build-up order that produces those artifacts. This sequence is what that breakdown's last two steps prove out, and what every subsequent clone runs verbatim thereafter.

## 2. Configuration surface

**ENV-CFG-01** `ARCH-RUN-07`'s env-var table is the canonical list of defaults. This harness's shell state does **not** persist between tool calls, since no `export` survives to the next command. Every invocation that needs a non-default value sets it inline on the same command line.

```bash
DB_PATH=/tmp/scratch.db MCF_MODE=fixture env/bin/python -m easymcf
```

The env variables toggled routinely during development:

| id | variable      | routine value       | when                                                   |
| -- | ------------- | ------------------- | ------------------------------------------------------ |
| 01 | `DB_PATH`     | temp file / default | pointing a one-off run at a scratch db, never prod     |
| 02 | `MCF_MODE`    | `fixture` (default) | `live` only on explicit, human-confirmed request       |
| 03 | `PORT`        | default `5000`      | only if `5000` is already bound (`ENV-TRBL-01`)        |
| 04 | `HEADLESS`    | `1` (default)       | `0` only for a human visually debugging a selector     |

**ENV-CFG-02** No `.env` file is required to run anything in this document. Every default in `ARCH-RUN-07`'s table is sufficient. A personal `.env`, already gitignored, may hold machine-local overrides a developer doesn't want to type repeatedly. It holds no secret material. The Google client id is not secret, and the credential files, the per-user MCF session files (`ARCH-BOT-03`), the Google client secret, and the cookie signing key (`ARCH-AUTH-06`), live in `.secrets/`. `CLAUDE.md`'s boundary against reading or committing them in an automated context applies regardless of `.env`.

The human-operated restart helper is the one exception to ordinary dotenv precedence: `scripts/restart.sh` parses `MCF_MODE` directly from `.env`, validates that it is `fixture` or `live`, exports that exact value, and reports it before startup. This prevents an inherited shell value from silently selecting a different browser implementation. Automated tests continue to set `MCF_MODE=fixture` inline and do not use the restart helper.

**ENV-CFG-03 Making `.env` actually do something, and what's tracked about it.** `ENV-CFG-02` says a personal `.env` *may* hold overrides. That's necessary but not sufficient. `python-dotenv` being an installed dependency (`ENV-SETUP-02` row 10) does not by itself make anything read `.env`, and nothing in this codebase calls it yet. Two things fix that.

01. **Loading.** `easymcf/__main__.py` calls `dotenv.load_dotenv()` as its first statement, before `Config()` is instantiated. `load_dotenv()` populates `os.environ`, and `Config`'s `default_factory` fields (`ARCH-RUN-07`) already re-read `os.environ` on every call, so no change to `config.py` itself is needed, only the one call before the app starts. Every `scripts/*.py` CLI entry point (`ENV-SCRIPT-01..05`) that reads a config-relevant env var does the same at its own top. A script run directly never goes through `__main__.py`'s load, so it needs its own. Test entry points (`tests/conftest.py`, `pytest` itself) deliberately do **not** call `load_dotenv()`. `ARCH-TEST-01`'s state isolation already sets `DB_PATH`, and any other test-relevant var, explicitly per session. Loading a developer's personal `.env` into a test run would let a machine-local override silently change test behavior, exactly what that isolation exists to prevent.
02. **The template.** A git-tracked `.env.example` at the repo root, `.env` itself stays gitignored per `ENV-CFG-02`, is the only reviewable record of what's actually available to override, since nobody can `git show` another developer's `.env`. One line per `ARCH-RUN-07` variable, set to its own default and annotated with its purpose. Copying the file verbatim to `.env` is a no-op for every default line, so a developer edits only the lines whose value they actually want to change, and can delete the rest. The Google lines hold placeholders that the developer replaces to enable Google sign-in:

```bash
# .env.example — copy to .env, then edit only the values you want to override.
# .env is gitignored (personal, machine-local); this file is the tracked reference.
# Nothing here is required — every line already matches the default ARCH-RUN-07 fixes.

DB_PATH=data/easymcf.db   # SQLite file; point at a scratch path for a one-off run, never prod
PORT=5000                 # HTTP port; change only if 5000 is already bound 
SECRETS_DIR=.secrets      # where the MCF session file lives 
MCF_MODE=fixture          # fixture | live — never set live except on explicit, human-confirmed ask
HEADLESS=1                # 0 only for a human visually debugging a selector
APPLY_POLL_RETRIES=5      # apply-button poll attempts before unable_to_apply 
APPLY_POLL_DELAY_S=5      # seconds between apply-button poll attempts 
APPLY_LIVE_SUBMIT=0       # 1 lets MCF_MODE=live submit real applications; a deliberate human choice (11.IS.14)

GOOGLE_REDIRECT_URI=http://127.0.0.1:5000/api/v1/auth/google/callback   # must equal the OAuth client's registered URI
GCP_OAUTH_CLIENT_ID=%%GCP_OAUTH_CLIENT_ID%%       # Google OAuth client id, not secret
GCP_OAUTH_TEST_EMAIL=%%test_user%%@gmail.com      # test account for the live sign-in tier only
# The client secret is never an environment variable. It lives in .secrets/gcp_oauth_client_secret (ARCH-AUTH-06).
```

## 3. Reusable, re-runnable scripts

These are the "helpers" the **test-strategy doc** names but doesn't fully specify the CLI contract of. All live under `scripts/`, all run through `env`, all exit `0` on success and non-zero on failure, so they compose into the loop in section 5.

**ENV-SCRIPT-01 `scripts/initdb.py`** — idempotent schema application. `python scripts/initdb.py [--db-path PATH]` applies `easymcf/db/schema.sql` to `DB_PATH`, or `--db-path`, creating the file if absent. This is the primitive `conftest.py`'s per-session fixture (`ARCH-TEST-01`) and `resetdb.py` both call. It never deletes an existing file itself.

**ENV-SCRIPT-02 `scripts/resetdb.py`** — the destructive human/agent-facing reset (`ARCH-STO-06`). `python scripts/resetdb.py [--seed]` deletes the file at `DB_PATH` if present, calls `initdb.py`'s apply-schema routine, then applies `seed/*.sql` if `--seed` is passed. This is the single command that recovers from a `schema_version` mismatch (`ARCH-STO-03`) or a corrupted dev scratch db. Never hand-edit `data/easymcf.db`.

**ENV-SCRIPT-02a `scripts/restart.sh`** — the human-operated kill and restart helper. It reads `MCF_MODE` from `.env`, resolves the configured port, and refuses to kill a listener unless `/proc` identifies this repo's `python -m easymcf` process. `scripts/restart.sh` preserves the database. `scripts/restart.sh --reset-seed` runs ENV-SCRIPT-02 before starting. Both launch through `env/bin/python` and remain attached to the terminal.

**ENV-SCRIPT-03 `scripts/db_util.py`** (`STRAT-SILO-01`) — direct CRUD against any table, stdlib `sqlite3`, no Flask involved. `python scripts/db_util.py <table> <op> [json]` where `op` is one of `get`/`insert`/`update`/`delete`/`search`, for example `python scripts/db_util.py lead insert '{"post_id": 1, "track_id": 1, "stage": "OPEN"}'`. It prints the resulting row as JSON on success (exit `0`), and prints the raw SQL error, constraint name, column, on failure (exit `1`). This is the narrowest, fastest signal in the whole loop, per the **test-strategy doc**'s row 01. It is also importable as a module. `tests/backend/` fixtures and automation-silo fixtures both reuse it rather than each re-implementing CRUD.

**ENV-SCRIPT-04 `scripts/api_tester.py`** (`STRAT-SILO-03`) — the same case format `tests/backend/cases/*.json` uses, replayed with `requests` against an already-running instance instead of the Flask test client. Two modes:

01. **Ad hoc** — `python scripts/api_tester.py GET /api/v1/lead/1` — for interactively poking one endpoint while `python -m easymcf` is up.
02. **Case-replay** — `python scripts/api_tester.py --case tests/backend/cases/lead.json --name "<case name>"` — for reproducing a specific failing case against a live process when the test-client signal alone isn't enough to diagnose it, for example suspected WAL/threading behavior the test client's in-process call wouldn't exercise.

Mode 02 is a diagnostic convenience, never part of the automated tier-1 loop. `pytest -m backend` against the test client is.

**ENV-SCRIPT-05 `scripts/envcheck.py`** — this is a proposed new helper, flagged for `testing-validation`/architect confirmation the same way `STRAT-SILO-07` was, not yet in `ARCH-TEST` or the **test-strategy doc**. It is a single preflight command an agent runs **before** any loop iteration in section 5, so an environment defect, wrong venv active, browser binary missing, stale schema, port already bound, is never misdiagnosed as a code bug three layers up. `python scripts/envcheck.py` checks, in order: Python version is at least 3.11 and `sys.prefix` resolves to `env`, catching a stray system-Python invocation; `~/.cache/ms-playwright` contains a Chromium build; `frontend/vendor/angular.min.js` and `angular-route.min.js` both exist per `ENV-SETUP-05`, catching a fresh clone with the vendor commit missing before it surfaces three layers up as a blank-page Playwright failure; `DB_PATH`, or the default, is either absent or has a `meta.schema_version` matching `schema.sql`'s current value; `PORT` (default `5000`) is free; `MCF_MODE` is unset or `fixture`, never silently `live`. It exits `0` with `all checks passed` on success. On failure, it prints one line per failed check naming the check and the fix, for example `[FAIL] playwright chromium missing — run: python -m playwright install chromium`, and exits `1`. This turns the "installation, sdks, runtime, helpers" concern into one runnable diagnostic instead of a document a human re-reads.

## 4. Running the app interactively

For a human, or an agent doing a manual golden-path check per the **deploy-cycle skill**, distinct from the automated test tiers, which spawn and tear down their own process per `ARCH-TEST-04`:

```bash
env/bin/python -m easymcf &                        # background, per ARCH-RUN-01/07
curl -sf http://127.0.0.1:5000/api/v1/health || echo "not ready"       # backend liveness, independent check
# open http://127.0.0.1:5000 in an ordinary browser — it lands on the Leads page (/leads)
# ... exercise the UI / hit endpoints via scripts/api_tester.py ...
kill %1                                               # stop it when done
```

The two checks on the first two lines are deliberately independent, `ENV-SETUP-06`'s implementation decision. The `curl` proves the backend is alive. The browser page proves the frontend stack is alive. Neither one's result depends on the other's code path. Never run this against `MCF_MODE=live` unless the user has explicitly asked for a live check in that turn, per `ARCH-RUN-08`, `ARCH-TEST-06`, and `CLAUDE.md`'s boundary. The default `fixture` mode is always what an agent's own interactive check uses.

## 5. The agent's closed install → build → run → test → debug loop, per component

**ENV-LOOP-01 "Build" and "compile" in this stack.** Neither Python nor build-free AngularJS (`ARCH-RUN-05/06`) has a compile step. That is a deliberate design decision. This document does not need to fill a gap here. The nearest equivalent signal is a Python `ImportError`/`SyntaxError` surfacing at pytest **collection time**, before any test body runs. That failure is this stack's "compile error," and it is already what `pytest -m backend` reports first if it occurs. The loop below is therefore install → run → test → debug, with `scripts/envcheck.py` (`ENV-SCRIPT-05`) standing in for the "is the toolchain even installed correctly" check a compiled-language project would need separately.

**ENV-LOOP-02** Run `python scripts/envcheck.py` once per session, or after any environment-affecting change: new dependency, browser reinstall, schema edit, before trusting any test failure below as a code defect rather than an environment defect. This precedes the **test-strategy doc**'s silo-aware table, reproduced below with the preflight column this document adds. Once `envcheck.py` passes, `ARCH-TEST-07`'s change→command→signal table already covers what to run next. This table only adds what to check/start first.

| id | component     | preflight                | then                                         |
| -- | ------------- | ------------------------ | -------------------------------------------- |
| 01 | data model/db | envcheck; resetdb --seed | `db_util.py` round trip, `pytest -m backend` |
| 02 | backend API   | envcheck                 | edit case json, `pytest -m backend -k`       |
| 03 | automation    | envcheck (Chromium)      | service test, `pytest -m backend -k`         |
| 04 | frontend      | envcheck; port `5000` free | `pytest -m frontend -k`, `pytest -m e2e`   |

A preflight runs before every silo, not just once, because `envcheck.py` is cheap: sub-second, no browser launch, no server start, relative to any tier it precedes. Running it on every iteration costs nothing and converts "the test suite is flaky" into "the environment drifted" whenever that's the real cause. This is the failure mode the **test-strategy doc**'s `STRAT-CASE-06` (determinism) guards against from the code side. This guards from the environment side.

**ENV-LOOP-03 Data model / db.** No process needs to be running. Preflight, then edit `easymcf/db/schema.sql`, then `python scripts/resetdb.py --seed`, where a failure here, a SQL syntax error or a seed row violating a new constraint, is caught before any Python/Flask code runs at all, then `python scripts/db_util.py <table> insert/get '...'` for a fast round-trip check of the specific change, then `pytest -m backend` for the full tier. Debug signal: the raw SQLite error message, constraint name, column, from whichever of `resetdb.py`/`db_util.py`/pytest failed first. No traceback climbing through Flask or a browser is ever needed for a data-model defect.

**ENV-LOOP-04 Backend API.** `pytest -m backend` drives the app via Flask's test client (`ARCH-TEST-03`). Preflight, edit the route/service code, add or edit the relevant case in `tests/backend/cases/*.json`, `pytest -m backend -k "<case name>"` for the single case, then `pytest -m backend` for the full tier. Debug signal: pytest's traceback names the failing assertion and the case's `req_id` directly. `scripts/api_tester.py`'s mode 01 remains available for interactive poking, per `ENV-SCRIPT-04`.

**ENV-LOOP-05 Automation (scraping + apply).** Preflight confirms Chromium is installed, the one automation-specific failure mode `envcheck.py` exists to catch early. Then run service-level tests against `easymcf/automation/fixture.py` (`STRAT-SILO-05/06`) with `MCF_MODE=fixture`, the default and never overridden to `live` in this loop, via `pytest -m backend -k automation`, then the fixture-driven mock e2e case for the specific scenario touched (`pytest -m e2e -k <scenario>`), then the full `pytest -m e2e`. Debug signal at the service tier: an outcome-mapping assertion failure naming the expected vs. actual status code, no browser chrome involved. At the e2e tier: the exit code plus the screenshot/HTML artifact `ARCH-TEST-05` writes to `.dev/test-artifacts/` on failure. Read the artifact rather than re-running with a visible browser as the first debugging step. `HEADLESS=0` is a last resort.

**ENV-LOOP-06 Frontend.** Preflight, including confirming port `5000` isn't already bound by a leftover background process from a previous manual check (`ENV-TRBL-01`). The frontend test tiers spawn their own `python -m easymcf` instance (`ARCH-TEST-04/09`) and will fail confusingly if one is already running on that port. Edit the AngularJS controller/template/service, then `pytest -m frontend -k <screen>`, tier 1b, mocked `/api`, isolating rendering logic per `STRAT-SILO-07`, then `pytest -m e2e -k <screen>`, tier 2, real backend, confirming wiring, then the full `pytest -m e2e`. `<screen>` in milestone 07 is `env-status` (`ENV-SETUP-06`). It is the same loop, run against the bootstrap shell before any of milestones 09-11's real screens exist. Debug signal: tier 1b failing but tier 2 passing means the mocked-`/api` fixture in `tests/fixtures/api/*.json` no longer matches the real response shape, a fixture-staleness bug, not a rendering bug. Tier 1b passing but tier 2 failing means the rendering logic is correct and the defect is in real backend/database wiring. The split itself is the diagnostic signal `STRAT-SILO-07` was designed to produce.

**ENV-LOOP-07 "Anything, before reporting done."** `python scripts/envcheck.py && python -m pytest` is the full unattended suite, tiers 1/1b/2, with the live tier excluded by `pytest.ini`'s default marker expression (`ARCH-TEST-02`). This is the same closing command `ARCH-TEST-07`'s last row and the **deploy-cycle skill** already converge on. This document's only addition is putting `envcheck.py` in front of it.

## 6. Troubleshooting signatures

| id | symptom                  | cause                                 | fix                                |
| -- | ------------------------- | ------------------------------------ | ----------------------------------- |
| 01 | address already in use    | port left bound, prior run           | kill it, or set `PORT`             |
| 02 | db version mismatch       | `schema.sql` changed since reset     | `resetdb.py --seed`                |
| 03 | playwright exe not found  | Chromium not installed               | `playwright install chromium`      |
| 04 | wrong Python used         | bare `python`, not venv path         | use `env/bin/python` always        |
| 05 | `easymcf.db` got mutated  | `DB_PATH` unset for call             | fixture must set it every time     |
| 06 | hit real MCF site         | `MCF_MODE=live` leaked               | stop, tell the user                |
| 07 | e2e fails, no traceback   | port `5000` already bound            | kill the leftover process          |
| 08 | frontend renders blank    | `frontend/vendor/*.min.js` missing   | re-fetch per `ENV-SETUP-05`, commit |
| 09 | chromium fails to launch  | OS-level shared library missing      | human-gated `--with-deps`/`apt-get` |
| 10 | `.env` value has no effect | entry point never calls `load_dotenv()` | confirm `ENV-CFG-03`'s call exists |

Detail on the rows above too narrow to fit in a cell:

- (03) run plain `python -m playwright install chromium` first. This row is only the binary being absent, fixed by the plain install, no `sudo` needed.
- (04) shell state, including any `activate`, does not persist between tool calls in this harness, so every command must spell out the full venv path rather than assume a prior `activate` carried forward.
- (06) `scripts/envcheck.py` (`ENV-SCRIPT-05`) is meant to catch this before it happens. If it already happened, this is the `CLAUDE.md` live-site boundary being crossed, not a routine bug. Surface it. Do not quietly re-run in fixture mode and move on.
- (08) `ENV-SETUP-05`'s fetch is one-time/per-implementer, not per-clone. A fresh checkout should already have the files from git. Hitting this means the commit never happened or the files were deleted. It does not mean the environment needs re-installing.
- (09) distinct from (03): the Chromium binary is present but fails to *launch*, which is what a missing OS-level shared library looks like. That needs the `--with-deps`/`apt-get` path, which needs `sudo`, so it is escalated to a human rather than retried by an agent (`ENV-SETUP-04`).
</content>
