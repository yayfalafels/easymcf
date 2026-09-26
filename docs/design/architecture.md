# Easy MCF POC Local - Architecture

Release `010` design. Source: [docs/releases/010/design/010-architecture.md](https://github.com/yayfalafels/easymcf/blob/main/docs/releases/010/design/010-architecture.md).

## Contents

- [Purpose](#purpose)
- [References](#references)
- [Guiding constraint](#guiding-constraint)
- [6. Out of scope](#6-out-of-scope)
- [1. Runtime and compute](#1-runtime-and-compute) — `ARCH-RUN-01..10`, `ARCH-SCHED-01..06`
  - [Topology](#topology)
  - [Scheduled runs](#scheduled-runs) — `ARCH-SCHED-01..06`
  - [Language, dependencies, entry points](#language-dependencies-entry-points)
  - [Frontend serving](#frontend-serving)
  - [Repo layout](#repo-layout)
- [2. Storage](#2-storage) — `ARCH-STO-01..07`
- [3. Networking](#3-networking) — `ARCH-NET-01..04`
- [7. Accounts and authentication](#7-accounts-and-authentication) — `ARCH-AUTH-01..10`
- [4. Browser automation infrastructure](#4-browser-automation-infrastructure) — `ARCH-BOT-01..05`
- [5. Testing infrastructure](#5-testing-infrastructure) — `ARCH-TEST-01..09`
  - [Common mechanics](#common-mechanics)
  - [Tier 1 — backend only (REQ-DEV-03)](#tier-1--backend-only-req-dev-03)
  - [Tier 1b — frontend silo (STRAT-SILO-07)](#tier-1b--frontend-silo-strat-silo-07)
  - [Tier 3 — live MCF and Google sign-in (REQ-DEV-05, REQ-DEV-06)](#tier-3--live-mcf-and-google-sign-in-req-dev-05-req-dev-06)
  - [The agent's build → test → debug loop](#the-agents-build--test--debug-loop)

## Purpose

Physical and runtime architecture for release `010` (POC local): what processes exist, what they run on, where data and credentials live on disk, and how every tier of testing is invoked. The **workflows** say *what* happens, the **data model** says *what is stored*, and the **user interface design** says *what the user sees*. This document says *what runs where* and is the direct input to milestone 07 (local dev and test env) and 08 (seed data). It is intended to be complete enough that 07 can be implemented without further design decisions.

Decisions carry an `ARCH-*` id (grouped `RUN`/`SCHED`/`STO`/`NET`/`BOT`/`TEST`, mirroring the `REQ-*` grouping convention in the **requirements**) so later docs, skills, and commit messages can reference them.

## References

- **requirements**: [010-01-requirements.md](https://github.com/yayfalafels/easymcf/blob/main/docs/releases/010/design/010-01-requirements.md) — REQ-PLAT-01..04, REQ-FE-01..02, REQ-DEV-01..05 are the requirements this document operationalizes.
- **release roadmap**: [release-roadmap.md](https://github.com/yayfalafels/easymcf/blob/main/docs/releases/release-roadmap.md) — the feature table fixing python/AngularJS/SQLite/local, and the `mcfpipe` lesson that bounds how much infrastructure `010` is allowed to build.
- **prototype extraction**: [010-prototype.md](https://github.com/yayfalafels/easymcf/blob/main/docs/releases/010/design/010-prototype.md) — `jobsearch`'s runtime dependencies and local-env pain points (Selenium + matching chromedriver, Playwright Chromium, `cookies_mcf.json`, hardcoded Windows paths, `recommission.py`).
- **data model**: [010-data-model.md](data-model.md) — the tables the storage section below is concrete about.
- **test strategy**: [010-test-strategy.md](https://github.com/yayfalafels/easymcf/blob/main/docs/releases/010/design/010-test-strategy.md) — written after this document's first version. `ARCH-TEST-09` confirms its `STRAT-SILO-07` proposal (the `tests/frontend/` silo) back into this document's repo layout and tier table.
- **API reference**: [010-api.md](api.md) — elaborates `ARCH-RUN-10`'s endpoint surface into the full generic/hook/named classification and named-endpoint catalog, so that detail lives there instead of bloating this document.
- **frontend app design**: [010-frontend-app.md](frontend-app.md) — elaborates `ARCH-RUN-06/09`'s frontend decisions and `ARCH-TEST-05/09`'s Playwright tiers into the AngularJS module/routing/API-client structure and the `data-testid` convention those tiers assert against.
- **development env runbook**: [010-development-env.md](development-env.md) — the concrete install/config/script/agent-loop runbook that implements this document and the **test strategy** as an actual, executable environment. It is the direct input to milestone 07.
- **local-infra skills**: `.claude/skills/local-infra-navigation/SKILL.md`, `.claude/skills/deploy-and-validation-cycle/SKILL.md` — both are scaffolds explicitly waiting on this document plus milestone 07/08. They are the intended destination for the run/reset/test commands defined here.
- **workflows**: [010-workflows.md](workflows.md) — the process logic behind every `ARCH-*` decision that touches a run or a state transition.
- **user interface design**: [010-user-interface.md](user-interface.md) — what the user sees, referenced wherever an `ARCH-*` decision has a visible UI effect.
- **backend-api skill**: [.claude/skills/easymcf-backend-api/SKILL.md](https://github.com/yayfalafels/easymcf/blob/main/.claude/skills/easymcf-backend-api/SKILL.md) — the agent-facing skill covering the generic CRUD endpoint shapes.
- **playwright skill**: [.claude/skills/playwright/SKILL.md](https://github.com/yayfalafels/easymcf/blob/main/.claude/skills/playwright/SKILL.md) — explicit-wait and locator patterns that carry over from the prototype's Selenium usage.
- **project instructions**: `CLAUDE.md` (repo root) — the project's own boundaries on live-site access, secrets, and the two-venv rule.

## Guiding constraint

`010`'s stated purpose is to reach a working product without repeating `mcfpipe`'s pre-MVP infrastructure investment. Every decision below is taken at the lowest-ceremony option that satisfies the requirement, and the burden of proof is on adding a tool rather than on omitting one. Concretely, `010` adds none of the following.

01. containers.
02. orchestration.
03. a process manager.
04. a migration framework.
05. a message queue.
06. a build toolchain for the frontend.
07. CI.

## 6. Out of scope

Mirrors the **requirements**' out-of-scope section and the **project instructions**' boundaries. This is restated here so milestone 07/08 doesn't drift into it while building the local environment:

- **No cloud anything** — no AWS/GCP/Azure SDK, credential file, deployment target, or hosted service dependency. No S3/DynamoDB/RDS/Lambda/API Gateway. `010` runs offline apart from the gated MCF automation calls and the Google sign-in flow (ARCH-NET-03).
- **No containers or orchestration** — no Dockerfile, docker-compose, Kubernetes, or VM image. The install procedure is `python -m venv`, `pip install -r`, `playwright install chromium`.
- **No CI/CD** — no GitHub Actions workflow, no pipeline configuration, no automated deploy. Tests are run locally by a developer or an agent, on demand.
- **No roles, teams, or hosted identity** — accounts are local rows in the one SQLite file, every user has the same capabilities, and there is no admin console, no sharing between users, no email verification or reset, no hosted identity provider, and no `0.0.0.0` binding. Sign-in uses the standard mechanisms `ARCH-AUTH-01..10` defines and no scheme of its own.
- **No process manager, external scheduler, or queue** — no systemd unit or timer, cron entry, Celery/redis/celery-beat, APScheduler, or supervisor. Runs are either user-initiated (REQ-SRCH-02) or fired by the in-process tick thread `ARCH-SCHED-01` defines (REQ-SRCH-11), and both paths execute in-process through the same code path (ARCH-RUN-02) under the same one-run-at-a-time guard (ARCH-RUN-03). Scheduling in `010` is a loop inside the single Flask process reading `search_schedule` rows, never a second process and never a scheduling library.
- **No migration framework, no ORM migrations, no database backup tooling** — recreate-and-reseed is the whole story (ARCH-STO-02/06).
- **No frontend build toolchain** — no node, npm, webpack, bundler, transpiler, or JS test runner (ARCH-RUN-06, ARCH-TEST-05). The frontend-silo tier (ARCH-TEST-09) adds a second Playwright tier rather than a JS toolchain.

Each of these becomes a live question again at `020` (MVP cloud). None of them is a live question in `010`, and adding one is a scope change to be raised with the product-manager rather than decided in an implementation PR.

## 1. Runtime and compute

### Topology

**ARCH-RUN-01** The entire system is **one machine, one long-lived OS process serving every account**: a Flask application that serves both the JSON API and the AngularJS frontend's static files. There is none of the following.

01. a container.
02. a VM.
03. a reverse proxy.
04. a separate frontend server.
05. a worker process.
06. service discovery.

`mcfpipe`'s serverless/multi-tier topology is the explicit anti-pattern this release avoids, per the **release roadmap**. The correct number of moving parts for `010` is one.

**ARCH-RUN-02** Search and apply runs execute **in a background thread inside the same Flask process**, not as a separate worker or scheduled job. A run-trigger endpoint creates the `run_log` row, starts the thread, and returns the `run_log.id` immediately. The thread writes progress and outcome counts back to `run_log` (and posts/applications) incrementally. The UI polls `GET /api/v1/run_log/{id}` — this is the mechanism behind the **user interface design**'s async-run pattern and REQ-FE-02. No Celery/RQ/redis. Rationale: the only thing a queue would buy at this scale is the ability to run two sweeps of one user at once, which the next decision forbids anyway.

**ARCH-RUN-03** **At most one run of each type per user may be in flight.** This is enforced atomically at the database layer, not by a check-then-act sequence in application code: `schema.sql` defines a partial unique index, `CREATE UNIQUE INDEX ux_run_log_running ON run_log(user_id, run_type) WHERE status = 'running'`, so a second `INSERT` of a `running` row for the same user and `run_type` fails the constraint regardless of how two request threads interleave. The run-trigger endpoint attempts the insert directly. On a `UNIQUE` constraint failure it looks up the existing `running` row for that user and `run_type` and returns `409` with its `run_log.id`, rather than `SELECT`-ing for an existing row before inserting. A separate pre-check would reopen the exact race the index exists to close, where two threads both read "no row running" before either commits. This keeps the threading model trivially safe and prevents one user's two scrapes competing for the same browser and MCF session, even with `ARCH-RUN-07`'s `threaded=True`, while different users' runs proceed independently.

**ARCH-RUN-04** Browser automation runs **in-process within that background thread** (Playwright's sync API, one browser context per run), not as a separately-launched script. The prototype's model of independent scripts writing to a shared database is what the API replaces.

### Scheduled runs

REQ-SRCH-11 adds a second way to start a search run alongside REQ-SRCH-02's on-demand trigger: a per-track schedule the user configures in the UI. This subsection is the whole of that mechanism. It was added after the first version of this document, which flatly excluded any scheduler — the out-of-scope bullet above is the amended text, and nothing below relaxes any other boundary in it.

**ARCH-SCHED-01** A scheduled run is fired by **one in-process daemon thread that wakes on a fixed tick, asks the database which schedules are due, and calls the same in-process run-trigger service function `API-EP-04` calls**. There is no cron entry, no systemd timer, no separate scheduler process, and no scheduling library. The thread waits on a `threading.Event` rather than `time.sleep()`, so process shutdown and tests both interrupt it immediately instead of after a full tick, and it holds its own SQLite connection per ARCH-STO-07 exactly as a run thread does. The scheduled path and the HTTP path converge on the same function, not on an HTTP call the app makes to itself: everything ARCH-RUN-02 says about how a run executes, and everything ARCH-RUN-03 says about how two of them contend, applies unchanged to a scheduled run. At a handful of users and tracks, a tick is one indexed `SELECT` and at most one run start per user.

Rejected alternatives:

01. **a cron entry or systemd timer calling `curl` against the run endpoint.** It puts the schedule outside the application, where the UI can neither read nor edit it — REQ-SRCH-11 requires the user to configure it from the UI, not by editing a crontab — makes the feature OS-specific, and adds precisely the process-manager dependency the **guiding constraint** and the out-of-scope list both refuse.
02. **APScheduler (or any pure-Python scheduling library) inside the same process.** It solves this problem correctly and is still the wrong trade here. It introduces a second source of truth for schedule state, its own job registry alongside the `search_schedule` rows the UI edits, so "what is scheduled" becomes answerable two ways that can disagree. It layers its own misfire/coalescing/`max_instances` semantics over ARCH-RUN-03's database-level guard, which already decides the same question with a stronger mechanism. And it adds a runtime dependency to a manifest ARCH-RUN-05 deliberately keeps at nine packages, to replace a loop, a query, and a timestamp update. The **guiding constraint**'s burden of proof for adding a tool is not met.
03. **Celery beat, RQ-scheduler, or any broker-backed scheduler.** Already refused by ARCH-RUN-02 for the run itself, for the same reason: the only capability it adds is concurrency this design forbids.

**ARCH-SCHED-02** **The schedule is its own `search_schedule` table, a 1:1 extension of `track` the same way `search_profile` is.** It carries `schedule_enabled`, `schedule_interval_hours`, and `next_run_at` (see the **data model**), keyed on `track_id`, and those three columns are the complete definition of a schedule. It is reachable through the generic CRUD shape at `/api/v1/search_schedule/{track_id}`, the same pattern `search_profile` already uses. Because milestone 08's schema is already implemented, this is a schema change under ARCH-STO-02's recreate-don't-migrate rule: edit `schema.sql`, the `search_schedule` table lands in schema version 4 with milestone 09's seed update, task 09.13's lead and offer changes land in version 6, feature 13's account and ownership changes land in version 7, feature 17's `mcf_attempt` and `mcf_session` changes land in version 8, and milestone 10's `run_log.trigger_source` and `lead.close_reason` edit bumps `meta.schema_version` to 9 per ARCH-STO-03, followed by `scripts/resetdb.py --seed`.

Rejected alternatives:

01. **generalizing to a table keyed by `(run_type, track_id)`, covering apply runs too.** Nothing asks for scheduled apply runs: `010`'s apply run takes no track scope (ARCH-RUN-02, `run_log.track_id` nullable for apply) and is deliberately a decision the user makes after reviewing a queue. The cost of generalizing now is a join on every tick and a wider key to hold one row per track that a plain `track_id` key already covers. If `020` needs scheduled apply, widening the key is a contained change under the same recreate rule.
02. **a cron expression string.** It is the general answer and it drags in a parser — `croniter`, or APScheduler by the back door — and a UI for authoring a syntax the user should not have to learn. An enable flag, an interval, and a next-fire instant cover "every night at 8pm" and "every 6 hours", which is the whole of the stated need.
03. **a `last_run_at` column.** Rejected as duplicate state: `run_log` already records every run with its `track_id` and `started_at`, so "when did this track last search" has a source of truth. A second copy on `search_schedule` could only drift from it.

**ARCH-SCHED-03** **Due evaluation is `schedule_enabled = 1 AND (next_run_at IS NULL OR next_run_at <= now())`, read through `clock.py::now()`** per ARCH-STO-05, so a test controls "now" instead of waiting for it. `next_run_at` is user-writable — setting it is how the user picks the first fire time, and "daily at 08:00" is expressed as `next_run_at` = tomorrow 08:00 with `schedule_interval_hours` = 24, rather than as a separate time-of-day column. After the first fire the scheduler owns the column. The `NULL` branch is what makes this work without a write hook: enabling a schedule without naming a first fire time leaves `next_run_at` null, the next tick treats it as due, starts a run, and writes the column forward. `search_schedule` is therefore its own `API-CAT-01` pure generic resource in the **API reference**, the same shape `search_profile` already uses — REQ-SRCH-11 adds a new generic resource, but no table-specific write hook and no named endpoint.

**implementation decision** — **missed windows coalesce into at most one run.** If the app was closed for three days against a daily schedule, `next_run_at` is three days stale at boot; the scheduler starts **one** run and advances `next_run_at` in whole multiples of the interval to the next instant in the future, rather than replaying the missed windows or advancing by exactly one interval into the past. A search run re-scrapes current listings, so three replayed runs would produce what one produces, three times as slowly. This is the one piece of behavior a scheduling library would have given for free, and it is the arithmetic above.

**ARCH-SCHED-04** **A scheduled trigger that collides with an in-flight run skips, logs, and retries on the next tick.** ARCH-RUN-03's partial unique index is the guard and is unchanged: the scheduler attempts the same insert the endpoint attempts and catches the same `UNIQUE` failure. What differs is the handling. There is no request context, so there is no `409` to return and nobody to show it to — the scheduler logs one line naming the skipped track and the in-flight `run_log.id`, and leaves `next_run_at` untouched. Leaving it untouched is the load-bearing half: because the column advances only after a run actually starts, the skipped schedule is retried on the next tick and fires as soon as the conflicting run ends, instead of being silently dropped until tomorrow. It also cannot cascade, since a schedule that never starts never accumulates missed windows to catch up on.

Note the emergent consequence, which is intended rather than incidental: the index is on `(user_id, run_type)`, not on `track_id`, so two tracks of one user scheduled at the same instant do not search concurrently. The first starts, the second skips and starts when the first finishes. That is the correct behavior for one MCF session and one browser per user (ARCH-RUN-03), and it means a user can schedule every track at 08:00 without thinking about it. A skip applies to the colliding user only. The tick logs it, leaves that schedule's `next_run_at` untouched, skips the remaining due schedules of the same user for this tick, and continues with the due schedules of other users, whose runs do not collide. The tick reads the run's user from `track.user_id`, since no request context exists.

**ARCH-SCHED-05** **`run_log` gains a `trigger_source` discriminator (`manual` | `scheduled`, defaulting to `manual`)** so the run history answers "did last night's schedule actually fire" rather than leaving a scheduled run indistinguishable from one the user started. It is set by whichever path created the row.

**implementation decision** — **a skipped tick writes no `run_log` row, and no `skipped` value is added to `run_log.status`.** `run_log` is the record of runs that happened; a trigger that never started a run is not one. Widening that closed vocabulary would ripple into milestone 08's `CHECK` constraint, its seed enumeration oracle, and the UI's status badge, to represent a non-event whose only reader is a developer reading the log. The skip is an application-log line (ARCH-SCHED-04) and nothing more.

**ARCH-SCHED-06** **The tick thread is started by `__main__.py`, never by `create_app()`**, and is governed by two entries in ARCH-RUN-07's config table: `SCHEDULER_ENABLED` (default `1`) and `SCHEDULER_TICK_S` (default `60`). The split matters for the test tiers. Tier 1 uses `app.test_client()` against `create_app()` (ARCH-TEST-03), which must not acquire a background thread that fires runs at wall-clock intervals underneath an assertion; a scheduler test instead constructs the tick function and calls it directly against a controlled clock. Tier 1b/2 spawn `python -m easymcf` (ARCH-TEST-04/09) and set `SCHEDULER_ENABLED=0` unless the test is about scheduling, in which case it sets a sub-second `SCHEDULER_TICK_S` so the full loop still runs rather than being stubbed out — the same env-var-indirection pattern, and the same "shrink the wait, don't skip the code path" rule, as ARCH-BOT-05's apply-poll timings. The default local run sets neither, so a user who starts the app gets the scheduler.

### Language, dependencies, entry points

**ARCH-RUN-05** **Python 3.11+**, single **`venv` + `pip` + `pyproject.toml`**. Chosen over poetry/pdm/uv because it is the only option with zero install prerequisite beyond the Python already required, and because `010` ships no package and has no dependency-resolution problem worth a lockfile. This release keeps one manifest per venv instead of splitting a manifest into runtime and dev variants: `010` makes no runtime/dev process split, since the same venv runs the app and its own tests, so a single git-tracked `pyproject.toml`, listing `flask`, `authlib`, `pillow`, `playwright`, `jsonschema`, `beautifulsoup4`, `html5lib`, `pytest`, and `pytest-timeout` as dependencies, already gives everything a `requirements.txt`/`requirements-dev.txt` pair would. The **project instructions**' two-venv rule fixes where the venv actually lives, `.dev/dev-env` and `env`, both nested inside the repo at the repo root, never a home-directory or other external path, and never literally named `.venv/`. It also names its git-tracked manifests, `python-envs/dev-env/pyproject.toml` and `python-envs/ops-env/pyproject.toml`. The **development env runbook**'s `ENV-SETUP-01..03` gives the concrete target contents and install/sync commands.

**ARCH-RUN-06** **No node/npm anywhere in the project.** AngularJS 1.x needs no build step, so the frontend is vendored `angular.min.js` plus hand-written modules served as-is. The one thing a node toolchain would conventionally provide, a browser for tests, comes from Playwright's Python package instead (ARCH-BOT-01). This removes an entire toolchain, its lockfile, and its version drift from a POC that has roughly eight screens. AngularJS 1.x's EOL/security-patch status is a separate, already-weighed risk. It is accepted for `010` specifically because of `ARCH-NET-01`'s loopback-only binding and `ARCH-AUTH-02`'s HttpOnly session cookie, which keeps a script-injection flaw in the frontend from reading the session token. This acceptance is independent of the no-build-step rationale above. See the **release roadmap**'s feature-table note for why that acceptance does not carry forward to `020`.

**ARCH-RUN-07** Backend start: `python -m easymcf` (a `__main__.py` calling `create_app().run(host="127.0.0.1", port=5000, threaded=True)`). The Werkzeug dev server is the production server for `010`; gunicorn/waitress buy nothing for a local app and are deferred to `020`. Config comes from defaults in `easymcf/config.py`, overridable by environment variable — no `.env` file is required for the app to run:

| variable                | default               | purpose                                               |
| ----------------------- | --------------------- | ----------------------------------------------------- |
| `DB_PATH`               | `data/easymcf.db`     | SQLite file, tests point this at a temp file          |
| `PORT`                  | `5000`                | HTTP port                                             |
| `SECRETS_DIR`           | `.secrets`            | credential directory, ARCH-BOT-03 and ARCH-AUTH-06    |
| `MCF_MODE`              | `fixture`             | `fixture` \| `live`, browser target, ARCH-BOT-04      |
| `HEADLESS`              | `1`                   | headless browser                                      |
| `APPLY_POLL_RETRIES`    | `5`                   | apply-button poll attempts, REQ-APPLY-07              |
| `APPLY_POLL_DELAY_S`    | `5`                   | seconds between poll attempts, REQ-APPLY-07           |
| `APPLY_LIVE_SUBMIT`     | `0`                   | `1` lets live mode run apply, ARCH-BOT-02             |
| `SCHEDULER_ENABLED`     | `1`                   | run ARCH-SCHED-01's tick thread, `0` disables it      |
| `SCHEDULER_TICK_S`      | `60`                  | seconds between scheduler ticks, ARCH-SCHED-06        |
| `SECRET_KEY`            | file in `SECRETS_DIR` | signs cookies, generated on first start, ARCH-AUTH-02 |
| `SESSION_LIFETIME_H`    | `336`                 | absolute sign-in session lifetime in hours            |
| `COOKIE_SECURE`         | `0`                   | set `1` only when served over https                   |
| `SIGNIN_MAX_FAILURES`   | `5`                   | failed sign-ins per email before `429`                |
| `SIGNIN_WINDOW_S`       | `900`                 | failure counting window in seconds                    |
| `PASSWORD_MIN_LENGTH`   | `12`                  | minimum password length, maximum fixed at 128         |
| `PHOTO_DIR`             | `data/photos`         | profile photo store, ARCH-AUTH-07                     |
| `PHOTO_MAX_BYTES`       | `2097152`             | profile photo upload size limit                       |
| `GCP_OAUTH_CLIENT_ID`   | empty                 | Google OAuth client id, from `.env`                   |
| `GCP_OAUTH_SECRET_FILE` | file in `SECRETS_DIR` | Google client secret file, ARCH-AUTH-06               |
| `GOOGLE_DISCOVERY_URL`  | Google discovery URL  | swapped to the stub provider in tests                 |
| `GOOGLE_REDIRECT_URI`   | derived from `PORT`   | must equal the console registration                   |
| `GCP_OAUTH_TEST_EMAIL`  | empty                 | test account address, read only by the live tier      |

**implementation decision** — no project-specific prefix, previously \`\`, on these names. With only two venvs and no other project sharing this shell, per the **project instructions**' two-venv rule, the collision risk a prefix would guard against, another tool on the same machine also reading `PORT`/`DB_PATH`/`HEADLESS`, is accepted as a known and deliberate tradeoff. If it bites in practice, reintroducing a prefix is a contained rename rather than a re-architecture.

**ARCH-RUN-08** `MCF_MODE` accepts only `fixture` or `live` and defaults to `fixture` in code. Automated tests set `fixture` explicitly. A human may set `MCF_MODE=live` in the gitignored `.env`; `scripts/restart.sh` reads and exports that exact value before startup and reports it in the startup line. Invalid values fail during configuration instead of silently selecting fixture behavior. Live-site access remains human-gated by the **project instructions**.

### Frontend serving

**ARCH-RUN-09** **Flask serves the AngularJS app's static files** from `frontend/` at `/`, with `index.html` returned for unmatched non-`/api` paths, per AngularJS routing. Rejected alternative: a separate `python -m http.server` or `live-server` on its own port. It would add the following, all to gain live-reload on a project with no build step.

01. a second process for a developer to start.
02. a second port.
03. a cross-origin setup.
04. a CORS layer.

One origin, one process, zero CORS is worth more than hot reload here. A browser refresh is the reload.

**ARCH-RUN-10** Because the frontend is served from `/`, the generic CRUD API (REQ-PLAT-01) is mounted under an **`/api/v1` prefix**: `GET/PUT/DELETE /api/v1/{table}/{id}`, `POST /api/v1/{table}`, `POST /api/v1/{table}/batch`, `GET /api/v1/{table}/search`, `POST /api/v1/{table}/delete`. The endpoint *shapes* documented in REQ-PLAT-01 and the **backend-api skill** are unchanged. Only the prefix is added, so static asset paths can never shadow a table name. The `v1` segment costs nothing at this stage: it is a path literal rather than a versioning framework or content-negotiation scheme, so it violates nothing in the guiding constraint above. It also avoids a breaking change to every client, frontend, tests, or any future integration, the day `020` needs to add or retire a shape. It is not itself a commitment to ever ship a `v2`. The **API reference** is the single source of truth for the classification: which entities get this generic shape unmediated, which entities get the same shape backed by a per-table write/read hook enforcing an invariant, and which operations fall outside all seven shapes entirely as named endpoints.

01. run-trigger.
02. MCF session upload.
03. manual post entry.
04. account and sign-in actions.
05. profile photo upload, removal, and read.

An endpoint that is neither a generic shape nor in that catalog is a drift back toward per-feature endpoints. It is never a deliberate exception.

### Repo layout

```
easymcf/
  easymcf/                  # backend package
    __main__.py             # entry point (ARCH-RUN-07)
    config.py               # env-var config (ARCH-RUN-07)
    api/                    # generic CRUD blueprint + schema validation + named endpoints (010-api.md)
    auth/                   # accounts, sessions, Google flow, photo pipeline (ARCH-AUTH-01..10)
    tenancy.py              # per-table ownership predicates (ARCH-AUTH-04)
    db/
      schema.sql            # full DDL, single file (ARCH-STO-02)
      connection.py         # WAL/pragma setup, per-thread connections
    services/               # search, scoring, apply orchestration; lead/application write hooks (010-api.md)
      scheduler.py          # due-schedule tick thread (ARCH-SCHED-01)
    automation/
      browser.py            # MCFBrowser interface (ARCH-BOT-02)
      live.py               # Playwright -> real MCF
      fixture.py            # Playwright -> route-intercepted fixture corpus
  frontend/                 # AngularJS SPA, no build step (ARCH-RUN-06)
    index.html
    app/                    # modules, controllers, services, templates
    vendor/                 # angular.min.js et al, vendored
  data/                     # gitignored; dev scratch database and profile photos live here
  seed/                     # seed dataset as SQL text (ARCH-STO-04)
  scripts/
    initdb.py               # create schema
    resetdb.py              # drop + recreate + optionally seed (ARCH-STO-06)
  tests/
    backend/                # tier 1 (ARCH-TEST-02)
    frontend/               # tier 1b, frontend silo against mocked /api (ARCH-TEST-09)
    e2e/                    # tier 2 (ARCH-TEST-03)
    live/                   # tier 3, deselected by default (ARCH-TEST-06)
    support/                # stub identity provider, seeded account list, photo fixtures (ARCH-AUTH-10)
    fixtures/
      mcf/                  # canned MCF HTML + routes manifest (ARCH-TEST-04)
      api/                  # canned /api/** JSON responses (ARCH-TEST-09)
    conftest.py
  .secrets/                 # gitignored; MCF session files, Google client secret, cookie key (ARCH-AUTH-06)
  pytest.ini
```

## 2. Storage

**ARCH-STO-01** One SQLite file holds every table in the **data model**: `user`, `auth_session`, `role`, `track`, `search_profile`, `cv`, `post`, `post_track`, `match_score`, `lead`, `lead_note`, `lead_event`, `application`, `run_log`, `mcf_session`. The dev database is **`data/easymcf.db`**. `data/` is gitignored in its entirety, so no database binary is ever committed. Path is overridable via `DB_PATH`, which is how tests get their own.

**ARCH-STO-02** Schema is a **single hand-maintained `easymcf/db/schema.sql`** applied by `scripts/initdb.py`. No Alembic, no migration chain. During `010` a schema change is: edit `schema.sql`, run `scripts/resetdb.py --seed`, done — the database holds nothing a developer can't regenerate, and a migration framework's whole value (preserving production data) does not exist yet.

**ARCH-STO-03** `schema.sql` creates a `meta` table holding a `schema_version` integer, bumped by hand whenever `schema.sql` changes. The backend reads it at startup and **refuses to start with an explicit "database is version N, code expects M — run scripts/resetdb.py" message** rather than failing later with an obscure `no such column`. This is the entire substitute for migrations and it is sufficient because the remedy is always "recreate".

**ARCH-STO-04** The seed dataset (REQ-DEV-02) is **`seed/*.sql`, plain SQL text rather than a checked-in `.db` binary**, so it diffs and reviews like code. Milestone 08 owns its contents. This document fixes only that it is text, that it is loaded by the same loader used by tests and by `resetdb.py --seed`, and that it must include at least:

01. two tracks, one archived, exercising REQ-SRCH-10.
02. CV labels.
03. posts in both scraped and manual `src_method`.
04. posts matching multiple tracks.
05. leads at every stage including `CLOSED` with several close reasons.
06. applications covering every one of REQ-APPLY-04's eight outcome codes.
07. `run_log` rows in each status.
08. two accounts with distinct data, posts matched to tracks of both, and a lead on a shared post for each account.

**ARCH-STO-05** **Time-relative seed data.** Auto-expiry (REQ-CRM-05, 28 days of inactivity) and post-age screening (REQ-SRCH-09) make absolute dates in a seed file rot: a fixture written today asserts differently next month. Two rules apply.

01. the seed loader writes date and timestamp columns **relative to load time**. For example, a `CALLBACK` lead with its last activity 27 days old and one 29 days old, both computed at load.
02. all application code reads current time through a single `easymcf/clock.py::now()` indirection, so a test can substitute a fixed clock instead of sleeping or waiting for wall-clock drift.

Without rule 02, REQ-CRM-05 is not deterministically testable.

**ARCH-STO-06** Three database roles, never shared:

| role            | location                              | lifecycle                                                        |
| --------------- | ------------------------------------- | ---------------------------------------------------------------- |
| dev scratch     | `data/easymcf.db` (gitignored)        | long-lived, mutated freely, reset on demand                       |
| seed fixture    | `seed/*.sql` (committed, text)        | read-only source, never opened as a database                      |
| test databases  | pytest temp dir, one per test session | created, seeded, and deleted by the test run (ARCH-TEST-01)       |

`scripts/resetdb.py [--seed]` is the single reset path: delete the file at `DB_PATH`, apply `schema.sql`, optionally apply `seed/`. Backup is deliberately not a feature — a developer's clean-state story is "re-seed", and there is no data in `010` whose loss matters (real MCF postings are re-scrapable, and the release is a POC).

**ARCH-STO-07** SQLite is opened in **WAL mode** with `busy_timeout=5000` and one connection per thread (`check_same_thread` left at its default, connections not shared across threads). Necessary because ARCH-RUN-02 has a background run thread writing incrementally (REQ-SRCH-04) while HTTP request threads read for the polling UI. WAL keeps readers from blocking on the writer. Foreign keys are enabled per connection (`PRAGMA foreign_keys = ON`). They are off by default in SQLite, and the data model leans on FKs.

## 3. Networking

**ARCH-NET-01** The Flask process binds **`127.0.0.1:5000` only**, loopback rather than `0.0.0.0`. Every account lives on this one machine, and every API route except the sign-in flow requires a signed-in user (ARCH-AUTH-03). `010` serves plain http and terminates no TLS, so staying off a routable interface is what keeps passwords and the session cookie off the network.

**ARCH-NET-02** Frontend and API share the single origin `http://127.0.0.1:5000` (ARCH-RUN-09), so **no CORS configuration, no preflight handling, and no `flask-cors` dependency exist**. If a future change splits the frontend onto its own origin, CORS becomes a required part of that change — it is not pre-provisioned here.

**ARCH-NET-03** Runtime outbound calls are limited to MCF and Singpass browser automation, plus Google sign-in while a user chooses that method. The MCF connection flow drives navigation to MCF and Singpass through `SingpassBrowser`, while the user performs Singpass approval and MFA manually. Google calls are limited to the configured identity provider's discovery, token, and key endpoints, and the profile picture URL named in the verified token (ARCH-AUTH-05). There is no telemetry, CDN dependency, or runtime package download. The default test suite remains offline because fixture mode intercepts all MCF and Singpass requests and the auth tests use the stub identity provider.

**ARCH-NET-04** Real MCF and Singpass calls happen only when `MCF_MODE=live` (ARCH-RUN-08). In `fixture` mode the browser never resolves either hostname because requests are intercepted before dispatch (ARCH-TEST-04). The checked-in default and every automated test remain fixture mode. A human-operated `.env` may select live mode, and `scripts/restart.sh` makes that selection explicit in its startup output.

## 7. Accounts and authentication

**ARCH-AUTH-01** **Every mechanism is a maintained standard.** Password hashing is Werkzeug's scrypt implementation, which ships with Flask. The signed session cookie uses `itsdangerous`, also shipped with Flask. The Google flow uses Authlib's Flask client. Profile photos are validated and re-encoded with Pillow. `authlib` and `pillow` are the two additions to the ops manifest (ARCH-RUN-05), and no hand-written cryptography, token parsing, or image parsing exists in the codebase.

**ARCH-AUTH-02** **Sign-in sessions are server-side rows, referenced by a signed cookie.** The `auth_session` table holds the SHA-256 digest of a random 32 byte token, the user id, and an absolute `expires_at`. The cookie `easymcf_session` carries that token signed with `itsdangerous.URLSafeSerializer` and the salt `easymcf-session`. It is HttpOnly, `SameSite=Lax`, `Path=/`, and `Secure` only when `COOKIE_SECURE=1`. A database read yields no usable cookie, sign-out deletes the row so the cookie stops working at once, and a tampered or expired cookie is treated as no cookie. The signing key is `SECRET_KEY` when set, otherwise 32 random bytes generated on first start into `<SECRETS_DIR>/session_key` with mode `0600`, so a restart keeps users signed in.

**ARCH-AUTH-03** **One request pipeline guards every route.** A `before_request` hook runs three steps in order. It rejects an unsafe method whose `Origin` header names another host with `403`. It resolves the cookie to `g.user_id`. It answers `401` for any `/api/v1` route outside the public set, which is `health`, sign-up, sign-in, sign-out, the auth config read, and the two Google flow routes. The SPA static route is public since it serves code only. Together with `SameSite=Lax` the origin check is the whole cross-site request forgery defense, which suits a single-origin app.

**ARCH-AUTH-04** **Ownership is declared once and applied by the framework.** `easymcf/tenancy.py` holds one SQL predicate per table, bound to `:uid`. The generic CRUD blueprint appends the predicate to every read, update, and delete, checks declared parent references on create, and sets ownership columns on the server after validation. `register()` raises at import time for a resource with no declaration, so an unscoped resource cannot ship. A row outside the caller's predicate answers `404`, the same as a missing row. Services take the user id explicitly and call the same helpers, since background threads have no request context. The `post` table is shared and read-only to every user, and a lead holds its own copy of the display fields it needs (see the **data model**).

**ARCH-AUTH-05** **Google sign-in is the standard authorization code flow with PKCE and OpenID Connect.** Authlib performs discovery, state, nonce, and PKCE handling, and validates the id token signature, issuer, audience, and expiry. The transient state travels in a signed ten minute cookie `easymcf_oauth`. Every callback outcome is a redirect, to the requested page on success and to `/signin?error=<code>` on any failure, and no failure creates a user or a session. An identity links to an existing account only when Google reports the email verified, which closes the account takeover path through an unverified address. The redirect URI is `http://127.0.0.1:{PORT}/api/v1/auth/google/callback` unless `GOOGLE_REDIRECT_URI` overrides it, and it must equal the URI registered on the OAuth client.

**ARCH-AUTH-06** **Credentials live in three places, none tracked.** The Google client id is not secret and lives in `.env` as `GCP_OAUTH_CLIENT_ID`. The Google client secret lives only in `<SECRETS_DIR>/gcp_oauth_client_secret`, mode `0600`, located by `GCP_OAUTH_SECRET_FILE`, and is never an environment variable, so it cannot leak through a process listing or an environment dump. The cookie signing key lives in `<SECRETS_DIR>/session_key`. With the client id or the secret file absent, Google sign-in reports itself unavailable and the sign-in page hides the button. No secret, token, code, cookie, password, or email address appears in a log line, and auth log lines carry the user id and the event name only.

**ARCH-AUTH-07** **Profile photos are files outside the web root.** The upload pipeline decodes the image with Pillow, refuses anything that is not JPEG, PNG, or WebP, center-crops to a square, resizes to 256 by 256, and re-encodes as PNG, which discards metadata and any embedded payload. The file is written to `<PHOTO_DIR>/<user_id>/avatar-<sha8>.png` with mode `0600` in a `0700` directory through a temp file and an atomic rename, and `user.photo_ref` records it. The API serves a photo only to its owner. `PHOTO_DIR` defaults to `data/photos`, which `.gitignore` already covers through `data/`.

**ARCH-AUTH-08** **Runs execute for one user.** `start_run` takes the user id and writes it to `run_log.user_id`. A search run scores against the run user's active tracks and details only posts visible to that user. An apply run reads that user's queue, MCF session row, and session file. The scheduler resolves the user from `track.user_id`. Startup reconciliation marks every user's orphaned `running` row `failed`.

**ARCH-AUTH-09** **Sign-in attempts are rate limited in process.** A table keyed by lowercased email holds failure timestamps read through `clock.py::now()`. With `SIGNIN_MAX_FAILURES=5` and `SIGNIN_WINDOW_S=900`, failures one to five answer `401` and the next attempt answers `429` with `Retry-After`, even with the correct password, until the oldest failure ages out. A success clears the key. One process holds one table, so no shared store is needed.

**ARCH-AUTH-10** **Tests stub the provider and sign in for real.** `tests/support/stub_oidc.py` is a small OpenID Connect provider that signs tokens with a key it generates at startup and selects a failure scenario from the email's local part prefix. Fixtures sign in through the real sign-in endpoint as seeded accounts. The stub covers valid, unverified email, expired, wrong audience, wrong issuer, bad signature, wrong nonce, and wrong state cases. The live tier (ARCH-TEST-06) is the only place the real Google endpoints are called. Authlib validates token expiry against the wall clock, the one place `clock.py::now()` does not apply, so the stub sets explicit timestamps relative to the real clock.

## 4. Browser automation infrastructure

**ARCH-BOT-01** **Playwright (Python) with its bundled Chromium is the single browser dependency**, for search scraping, apply automation, and end-to-end tests alike. This supersedes the prototype's split of Selenium + system Chrome/chromedriver for scraping and Playwright for apply, per the **prototype extraction**.

Rationale:

01. it removes the chromedriver/Chrome version-matching failure mode, a named `jobsearch` local-env pain point.
02. `page.route()` interception is what makes the mock-e2e tier possible without a stub that bypasses the real scraping code, per ARCH-TEST-04.
03. one browser dependency instead of two, installed by `playwright install --with-deps chromium` into a user cache. Nothing system-wide, nothing in the repo.

The **playwright skill** covers the substance that carries over from the prototype unchanged, explicit waits instead of its fixed `sleep(15)`, stable `data-testid`/`data-cy` locators, just expressed against Playwright's driver API instead of Selenium's. If a concrete blocker appears during milestone 09/11, reverting scraping to Selenium is a contained change behind ARCH-BOT-02's interface, but it starts as Playwright.

**ARCH-BOT-02** Browser automation is split by responsibility into three seams, each with fixture and live implementations selected by `MCF_MODE`, and services obtain them through factories rather than instantiating concrete browsers. Fixture implementations route requests to checked-in HTML before dispatch. Search uses `MCFBrowser`, which returns raw page HTML for `easymcf/automation/parsing.py` to parse rather than driving DOM interaction itself. Apply uses `ApplyBrowser` from `easymcf/automation/apply_browser.py`, an interactive seam distinct from `MCFBrowser` because the apply flow clicks, selects, and submits rather than reading a page for parsing. Its live implementation also requires `APPLY_LIVE_SUBMIT=1`: the factory refuses to build a live `ApplyBrowser` without it, so `MCF_MODE=live` alone never submits an application. Session establishment uses `SingpassBrowser` from `easymcf/automation/singpass_browser.py`. The connection browser automates navigation, QR extraction, callback detection, account extraction, and state export. The user's Singpass approval remains manual per REQ-APPLY-06.

**ARCH-BOT-03** **MCF session credential storage.** Workflow 8 writes Playwright storage state to **`.secrets/mcf_session_<user_id>.json`** and sessionStorage to **`.secrets/mcf_session_<user_id>.session.json`**. `SECRETS_DIR` is created `0700`, each file is `0600`, and `.secrets` is gitignored. The `mcf_session` table stores only the primary filename in `cookie_ref`. Credential payloads never enter SQLite.

Storage-state export includes IndexedDB. User-triggered Open actions restore storage state and sessionStorage into `headless=False` Chromium. One daemon thread owns Playwright until the user closes the final window, but performs no page action after initial navigation. A restored page that shows Login marks the session expired and the latest attempt `reauthentication_required`. Startup and session reads downgrade a locally impossible valid row when its referenced state file is absent.

Rejected alternatives:

01. storing the cookie JSON in an env var or committed `.env`. A multi-kilobyte JSON blob is a poor fit for the environment, and `.env` files get committed by accident.
02. storing the payload in the `mcf_session` row. It would spread credential material into every database dump and seed export.
03. an OS keyring. This is a real dependency and platform-specific behavior for a local POC whose threat model is "don't commit it".

Test tiers never read this file: the fixture-mode browser uses a synthetic cookie fixture, so a missing or expired real session cannot break the autonomous loop.

**ARCH-BOT-04** Backend startup logs the active `MCF_MODE`, and any run triggered in `live` mode records it in `run_log` (as part of `outcome_counts`/error detail), so it is always answerable after the fact whether a given run touched the real site.

**ARCH-BOT-05** REQ-APPLY-07's apply-button poll (production default: 5 retries, 5s apart, up to 25s to reach `unable_to_apply`) reads its retry count and delay through `APPLY_POLL_RETRIES`/`APPLY_POLL_DELAY_S` (ARCH-RUN-07's config table) rather than hardcoded constants — the same env-var-indirection pattern `ARCH-STO-05` uses for `clock.py::now()`. Production and the default local run never set these, so the real 25-second wait is what a human sees. Fixture-mode tests exercising the `unable_to_apply` scenario (ARCH-TEST-04's `apply/{scenario}/` corpus) set both to a small value (e.g. 2 retries, 0.01s) so the full retry loop still runs — proving the retry logic and its terminal state, not skipping it — without spending real wall-clock seconds against `pytest-timeout`'s 60s per-test budget (ARCH-TEST-02).

## 5. Testing infrastructure

The design goal is stronger than "tests exist": **an AI agent must be able to run a build → test → debug loop end to end with no human in the loop.** That imposes four properties on every tier below the live one — single-command invocation, exit-code pass/fail, disposable isolated state, and a hard timeout — and it is why the live tier is deliberately excluded from the loop rather than merely discouraged.

### Common mechanics

**ARCH-TEST-01** **State isolation: a fresh temp-file SQLite database per test session, seeded from `seed/*.sql`, deleted on teardown.** A `conftest.py` session fixture creates the file under pytest's `tmp_path_factory`, applies `schema.sql` + seed, and exports `DB_PATH` to it. Function-scoped tests that mutate data wrap in a transaction rolled back at teardown, or request a function-scoped fresh copy where a rollback is impractical. Temp *file*, rather than `:memory:`. An in-memory database is per-connection, which breaks the moment the app opens a second connection, and it does: a background run thread (ARCH-RUN-02/STO-07). It also diverges from the WAL/file semantics being tested. At `010`'s data volumes the file costs milliseconds. The consequence that matters for the agent loop: **no test run ever touches `data/easymcf.db`, and no iteration inherits state from the previous one** — an agent can run the loop fifty times without a human resetting anything.

**ARCH-TEST-02** **Tooling: pytest for all four tiers**, with markers `backend`, `frontend`, `e2e`, `live` and `pytest.ini` carrying `addopts = -m "not live" --timeout=60 -q`.

Consequences:

01. bare `pytest` runs exactly the unattended-safe tiers.
02. a hung browser or a scraper waiting on a selector that will never appear fails in 60 seconds instead of stalling the loop indefinitely, via `pytest-timeout`.
03. exit code 0/1 is the pass/fail signal, with `--junit-xml` available when structured output is wanted.

No separate test runner, no `make`, no shell wrapper. The command *is* `pytest`.

| tier        | command                     | scope                                     | duration  |
| ----------- | --------------------------- | ------------------------------------------ | --------- |
| 1 backend   | `pytest -m backend`         | Flask test client + SQLite                | seconds   |
| 1b frontend | `pytest -m frontend`        | real browser + real Flask, `/api` mocked  | seconds   |
| 2 mock e2e  | `pytest -m e2e`             | real browser + real Flask + fixture MCF   | ~1-2 min  |
| 3 live     | `pytest -m live --run-live` | real MCF, human-gated (REQ-DEV-05)       | on demand |

### Tier 1 — backend only (REQ-DEV-03)

**ARCH-TEST-03** Flask's **built-in test client** (`app.test_client()`), used instead of `requests`/`httpx` against a spawned server, needs no port, no process lifecycle, and no readiness polling, and it gives tracebacks from the failing line rather than a `500` body.

Coverage:

01. every generic CRUD shape per table, including the `mcfpipe` validation checklist: required-field `400` naming the field, type and date-format validation, and `404` for missing record and for unknown table.
02. lead lifecycle transitions and close reasons.
03. auto-expiry against the injectable clock (ARCH-STO-05).
04. apply-outcome → lead propagation (Workflow 7's table).
05. `run_log` writes.

Service-layer tests drive the search/apply orchestration with a stubbed `MCFBrowser` (ARCH-BOT-02) so scoring, dedup, incremental persistence, asserting rows exist after an injected mid-sweep exception per REQ-SRCH-04, and outcome propagation are all exercised without a browser starting. This is the fast loop. A backend change should be re-verified here before anything slower runs.

### Tier 1b — frontend silo (STRAT-SILO-07)

**ARCH-TEST-09** Confirms `010-test-strategy.md`'s `STRAT-SILO-07` proposal: a second Playwright tier, `tests/frontend/`, isolating AngularJS controller/template/rendering logic from whether the real backend and database produced the response being rendered. Mechanically it mirrors ARCH-TEST-04's fixture-interception pattern one layer up the stack. A session fixture spawns `python -m easymcf` the same way, a real backend process with real Flask static-file serving, so the JS/HTML has a real HTTP origin to load from, but every `**/api/**` request is intercepted via `page.route()` and fulfilled from `tests/fixtures/api/*.json` canned responses instead of reaching the real Flask routes or SQLite. No second frontend-only server, no stubbed Angular services. It is the same AngularJS app and the same `page.route()` mechanism ARCH-TEST-04 already established, applied to the app's own `/api` boundary instead of MCF's. This tier is additive to ARCH-TEST-05's full-stack assertions: that tier remains the integration confirmation, run after this silo and ARCH-TEST-03's backend silo both pass. It also remains distinct from a Karma/Jasmine JS unit tier, since there is no node/npm/build toolchain (ARCH-RUN-06): the browser is Playwright's, the runner is pytest, same as every other tier.

**ARCH-TEST-04** The full stack — Playwright Chromium driving the real AngularJS UI against the real Flask app against a seeded temp database — with **MCF itself replaced at the network boundary rather than the code boundary**. A session fixture spawns `python -m easymcf` on an ephemeral port with `DB_PATH` set to the temp database, `MCF_MODE=fixture`, and `HEADLESS=1`, polls a `/api/v1/health` endpoint until ready, and terminates it on teardown.

The stubbing mechanism is **Playwright `page.route()` interception**: requests matching `**mycareersfuture.gov.sg**` are fulfilled from a fixture corpus instead of dispatched. This is the load-bearing choice — the real scraper code runs, with its real selectors, waits, retries, pagination-termination and dedup logic. Only the bytes come from disk. A stub that replaces the whole automation module would make this tier assert nothing about the automation it is supposed to cover.

Google sign-in is replaced the same way, at the network boundary. A stub OpenID Connect provider under `tests/support/` serves the discovery document, the signing keys, and the authorize and token endpoints, and `GOOGLE_DISCOVERY_URL` points the app at it. The real Authlib flow, cookie handling, linking rules, and photo import run against tokens the stub signs (ARCH-AUTH-10). Every test that needs a signed-in user signs in through the real sign-in endpoint as a seeded account, and the app has no authentication bypass switch.

Corpus layout under `tests/fixtures/mcf/`:

- `search/{keyword}_p{n}.html` — job-card list pages, including a final empty page so pagination termination (REQ-SRCH-03) is exercised, and overlapping cards across keywords so dedup (REQ-SRCH-05) is exercised.
- `detail/{urlid}.html` — profile pages, including at least one closed posting so REQ-SRCH-06's removal path is exercised.
- `apply/{scenario}/*.html` — one directory per REQ-APPLY-04 outcome, so **every one of the eight status codes is reachable deterministically**. For example: apply button never resolving leads to `unable_to_apply`, no matching resume card leads to `cv_not_found`, submit failing leads to `questionnaire_required`, and so on. This is what lets the **local-infra skills**' `deploy-and-validation-cycle` "confirm each outcome code is reachable" check be an automated assertion rather than a manual exercise.
- `routes.json` — manifest mapping URL pattern → fixture file per scenario, so a test selects a scenario by name rather than wiring routes inline.

Fixture HTML is captured from real MCF pages once, by hand, in a live session (tier 3's territory) and committed — it is public job-listing markup, and it contains no session material. Because MCF's markup drifts, which is the reason `jobsearch/recommission.py` exists, a **fixture-staleness check belongs in tier 3 rather than tier 2**: tier 2's job is to be deterministic, and a fixture that no longer matches the live site is a real-site-drift finding rather than a tier-2 failure.

**ARCH-TEST-05** **Full-stack frontend verification lives in this tier. There is no separate Karma/Jasmine JS unit tier in `010`.** The frontend-silo tier, ARCH-TEST-09, is Playwright against a mocked `/api` boundary rather than a JS unit-test framework, so it doesn't change this. Assertions are DOM-level Playwright assertions on rendered text, element state, and attributes. Examples include the following.

01. a run's status badge reaching `success`.
02. an error banner appearing after a failed run, per REQ-FE-02.
03. a post that became a lead showing `already a lead`.
04. a lead card moving tabs on stage change.

The tradeoff is stated plainly: a JS unit tier would give faster isolated feedback on controllers, at the cost of introducing node/npm/karma to a build-free frontend (ARCH-RUN-06). For roughly eight screens, DOM assertions in a tier that already exists give better signal per unit of infrastructure. On failure, Playwright writes a screenshot and the page HTML to `.dev/test-artifacts/` — **diagnostic aids for a human afterward, never a substitute for a pass/fail assertion.** No test may require a person to look at a browser to determine whether it passed.

### Tier 3 — live MCF and Google sign-in (REQ-DEV-05, REQ-DEV-06)

**ARCH-TEST-06** Explicitly **outside the autonomous loop, by design.** Running it requires three independent conditions, none of which occurs by default: the `live` marker is deselected by `pytest.ini` and must be re-selected (`pytest -m live --run-live`), `MCF_MODE=live` must be set (ARCH-RUN-08 defaults it to `fixture`), and a valid `.secrets/mcf_session.json` must exist (ARCH-BOT-03) — which only a human can produce, since login/MFA is manual and out of scope. An agent cannot satisfy the third condition at all, which is the point: this is the **project instructions**' boundary against unattended live-site access made structural rather than advisory. **No agent may run this tier on its own initiative, and no automated loop invokes it.** The Google sign-in live case (REQ-DEV-06) belongs to the same tier under the same rule. It needs `GCP_OAUTH_CLIENT_ID`, the client secret file, and `GCP_OAUTH_TEST_EMAIL`, plus a Google consent that only the account's owner can give, so an agent cannot satisfy it either.

Content is the local successor to `jobsearch`'s `recommission.py`: a short sequential smoke protocol (browser loads → search page loads → cards found and parsed → detail page parsed → apply page selectors resolve) whose purpose is detecting MCF markup drift and refreshing the tier-2 fixture corpus when it is found. Apply-submission steps are excluded by default — they mutate real MCF-side application state — and gated behind a further explicit flag when genuinely needed.

### The agent's build → test → debug loop

**ARCH-TEST-07** What to run after each kind of change, and where the signal comes from:

| change | command | signal |
| ------ | ------- | ------ |
| backend (API, schema, services, scoring, CRM logic) | `pytest -m backend` | exit code, assertion tracebacks name the failing endpoint/field |
| frontend (AngularJS controller, template, service) | `pytest -m e2e -k <screen>` then `pytest -m e2e` | exit code from DOM assertions, screenshot + HTML artifact on failure for diagnosis |
| automation (scraper, apply state machine, selectors) | `pytest -m e2e -k automation` | exit code, each apply outcome asserted against its fixture scenario |
| schema (`schema.sql` or `seed/`) | `python scripts/resetdb.py --seed && pytest` | reset failure or test failure, `schema_version` mismatch surfaces as a startup error rather than a cryptic SQL error |
| anything, before reporting done | `pytest` | runs tiers 1+2, excludes live automatically |

**ARCH-TEST-08** The properties that make the loop closed, stated as obligations on every future test added:

01. single-command invocation.
02. pass/fail from the exit code alone.
03. per-session disposable database seeded from `seed/` (ARCH-TEST-01).
04. MCF replaced by fixtures (ARCH-TEST-04).
05. a hard timeout (ARCH-TEST-02).

A test that needs a human to inspect output, or that leaves state behind for the next run, is a defect in the test. It is never an acceptable category of test.
