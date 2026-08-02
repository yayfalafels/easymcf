# Easy MCF POC Local - Architecture

## Purpose

Physical and runtime architecture for release `010` (POC local): what processes exist, what they run on, where data and credentials live on disk, and how every tier of testing is invoked. [010-workflows.md](010-workflows.md) says *what* happens, [010-data-model.md](010-data-model.md) says *what is stored*, [010-user-interface.md](010-user-interface.md) says *what the user sees*; this document says *what runs where* and is the direct input to milestone 07 (local dev and test env) and 08 (seed data). It is intended to be complete enough that 07 can be implemented without further design decisions.

Decisions carry an `ARCH-*` id (grouped `RUN`/`STO`/`NET`/`BOT`/`TEST`, mirroring the `REQ-*` grouping convention in [010-01-requirements.md](010-01-requirements.md)) so later docs, skills, and commit messages can reference them.

## References

- [010-01-requirements.md](010-01-requirements.md) — REQ-PLAT-01..04, REQ-FE-01..02, REQ-DEV-01..05 are the requirements this document operationalizes.
- [release-roadmap.md](../release-roadmap.md) — the feature table fixing python/AngularJS/SQLite/local, and the `mcfpipe` lesson that bounds how much infrastructure `010` is allowed to build.
- [010-prototype.md](010-prototype.md) — `jobsearch`'s runtime dependencies and local-env pain points (Selenium + matching chromedriver, Playwright Chromium, `cookies_mcf.json`, hardcoded Windows paths, `recommission.py`).
- [010-data-model.md](010-data-model.md) — the tables the storage section below is concrete about.
- `.claude/skills/local-infra-navigation/SKILL.md`, `.claude/skills/deploy-and-validation-cycle/SKILL.md` — both are scaffolds explicitly waiting on this document plus milestone 07/08; they are the intended destination for the run/reset/test commands defined here.

## Guiding constraint

`010`'s stated purpose is to reach a working product without repeating `mcfpipe`'s pre-MVP infrastructure investment. Every decision below is taken at the lowest-ceremony option that satisfies the requirement, and the burden of proof is on adding a tool, not on omitting one. Concretely: no containers, no orchestration, no process manager, no migration framework, no message queue, no build toolchain for the frontend, no CI.

## 1. Runtime and compute

### Topology

**ARCH-RUN-01** The entire system is **one machine, one user, one long-lived OS process**: a Flask application that serves both the JSON API and the AngularJS frontend's static files. There is no container, no VM, no reverse proxy, no separate frontend server, no worker process, and no service discovery. `mcfpipe`'s serverless/multi-tier topology is the explicit anti-pattern this release avoids (see [release-roadmap.md](../release-roadmap.md)); the correct number of moving parts for `010` is one.

**ARCH-RUN-02** Search and apply runs execute **in a background thread inside the same Flask process**, not as a separate worker or scheduled job. A run-trigger endpoint creates the `run_log` row, starts the thread, and returns the `run_log.id` immediately; the thread writes progress and outcome counts back to `run_log` (and posts/applications) incrementally. The UI polls `GET /api/run_log/{id}` — this is the mechanism behind [010-user-interface.md](010-user-interface.md)'s async-run pattern and REQ-FE-02. No Celery/RQ/redis. Rationale: the only thing a queue would buy at single-user scale is the ability to run two sweeps at once, which the next decision forbids anyway.

**ARCH-RUN-03** **At most one run of each type may be in flight.** A trigger request returns `409` with the in-flight `run_log.id` if a `run_log` row of that `run_type` has `status = running`. This keeps the threading model trivially safe and prevents two scrapes competing for the same browser/session.

**ARCH-RUN-04** Browser automation runs **in-process within that background thread** (Playwright's sync API, one browser context per run), not as a separately-launched script. The prototype's model of independent scripts writing to a shared database is what the API replaces.

### Language, dependencies, entry points

**ARCH-RUN-05** **Python 3.11+**, single **`venv` + `pip` + `requirements.txt`**. Chosen over poetry/pdm/uv because it is the only option with zero install prerequisite beyond the Python already required, and because `010` ships no package and has no dependency-resolution problem worth a lockfile. Two files: `requirements.txt` (runtime: `flask`, `playwright`, `jsonschema`, `beautifulsoup4`, `html5lib`) and `requirements-dev.txt` (adds `pytest`, `pytest-timeout`, plus `-r requirements.txt`). Virtualenv at `.venv/` (already gitignored).

**ARCH-RUN-06** **No node/npm anywhere in the project.** AngularJS 1.x needs no build step, so the frontend is vendored `angular.min.js` plus hand-written modules served as-is. The one thing a node toolchain would conventionally provide — a browser for tests — comes from Playwright's Python package instead (ARCH-BOT-01). This removes an entire toolchain, its lockfile, and its version drift from a POC that has roughly eight screens.

**ARCH-RUN-07** Backend start: `python -m easymcf` (a `__main__.py` calling `create_app().run(host="127.0.0.1", port=5000, threaded=True)`). The Werkzeug dev server is the production server for `010`; gunicorn/waitress buy nothing for one local user and are deferred to `020`. Config comes from defaults in `easymcf/config.py`, overridable by environment variable — no `.env` file is required for the app to run:

| variable              | default                  | purpose                                        |
| --------------------- | ------------------------ | ---------------------------------------------- |
| `EASYMCF_DB_PATH`     | `data/easymcf.db`        | SQLite file (tests point this at a temp file)  |
| `EASYMCF_PORT`        | `5000`                   | HTTP port                                      |
| `EASYMCF_SECRETS_DIR` | `.secrets`               | where the MCF session file lives (ARCH-BOT-03) |
| `EASYMCF_MCF_MODE`    | `fixture`                | `fixture` \| `live` — browser target (ARCH-BOT-04) |
| `EASYMCF_HEADLESS`    | `1`                      | headless browser                               |

**ARCH-RUN-08** `EASYMCF_MCF_MODE` **defaults to `fixture`, never `live`.** Reaching the real MCF site requires an explicit, per-invocation opt-in. This is the runtime enforcement of `CLAUDE.md`'s boundary against unattended live-site access — an agent or test run that forgets to think about it gets fixtures, not traffic to `mycareersfuture.gov.sg`.

### Frontend serving

**ARCH-RUN-09** **Flask serves the AngularJS app's static files** from `frontend/` at `/`, with `index.html` returned for unmatched non-`/api` paths (AngularJS routing). Rejected alternative: a separate `python -m http.server` or `live-server` on its own port — it would add a second process for a developer to start, a second port, a cross-origin setup, and a CORS layer, all to gain live-reload on a project with no build step. One origin, one process, zero CORS is worth more than hot reload here (a browser refresh is the reload).

**ARCH-RUN-10** Because the frontend is served from `/`, the generic CRUD API (REQ-PLAT-01) is mounted under an **`/api` prefix**: `GET/PUT/DELETE /api/{table}/{id}`, `POST /api/{table}`, `POST /api/{table}/batch`, `GET /api/{table}/search`, `POST /api/{table}/delete`. The endpoint *shapes* documented in REQ-PLAT-01 and the [easymcf-backend-api](../../../.claude/skills/easymcf-backend-api/SKILL.md) skill are unchanged; only the prefix is added, so static asset paths can never shadow a table name. Any endpoint that is not one of those seven shapes (e.g. the run-trigger and session-upload endpoints) is a deliberate, named exception documented in the design milestone — not a drift back toward per-feature endpoints.

### Repo layout

```
easymcf/
  easymcf/                  # backend package
    __main__.py             # entry point (ARCH-RUN-07)
    config.py               # env-var config (ARCH-RUN-07)
    api/                    # generic CRUD blueprint + schema validation
    db/
      schema.sql            # full DDL, single file (ARCH-STO-02)
      connection.py         # WAL/pragma setup, per-thread connections
    services/               # search, scoring, apply orchestration; run_log writes
    automation/
      browser.py            # MCFBrowser interface (ARCH-BOT-02)
      live.py               # Playwright -> real MCF
      fixture.py            # Playwright -> route-intercepted fixture corpus
  frontend/                 # AngularJS SPA, no build step (ARCH-RUN-06)
    index.html
    app/                    # modules, controllers, services, templates
    vendor/                 # angular.min.js et al, vendored
  data/                     # gitignored; dev scratch database lives here
  seed/                     # seed dataset as SQL text (ARCH-STO-04)
  scripts/
    initdb.py               # create schema
    resetdb.py              # drop + recreate + optionally seed (ARCH-STO-06)
  tests/
    backend/                # tier 1 (ARCH-TEST-02)
    e2e/                    # tier 2 (ARCH-TEST-03)
    live/                   # tier 3, deselected by default (ARCH-TEST-06)
    fixtures/
      mcf/                  # canned MCF HTML + routes manifest (ARCH-TEST-04)
    conftest.py
  .secrets/                 # gitignored; MCF session file (ARCH-BOT-03)
  requirements.txt
  requirements-dev.txt
  pytest.ini
```

## 2. Storage

**ARCH-STO-01** One SQLite file holds every table in [010-data-model.md](010-data-model.md) (`role`, `track`, `search_profile`, `cv`, `post`, `post_track`, `lead`, `lead_event`, `application`, `run_log`, `session`). The dev database is **`data/easymcf.db`**; `data/` is gitignored in its entirety, so no database binary is ever committed. Path is overridable via `EASYMCF_DB_PATH`, which is how tests get their own.

**ARCH-STO-02** Schema is a **single hand-maintained `easymcf/db/schema.sql`** applied by `scripts/initdb.py`. No Alembic, no migration chain. During `010` a schema change is: edit `schema.sql`, run `scripts/resetdb.py --seed`, done — the database holds nothing a developer can't regenerate, and a migration framework's whole value (preserving production data) does not exist yet.

**ARCH-STO-03** `schema.sql` creates a `meta` table holding a `schema_version` integer, bumped by hand whenever `schema.sql` changes. The backend reads it at startup and **refuses to start with an explicit "database is version N, code expects M — run scripts/resetdb.py" message** rather than failing later with an obscure `no such column`. This is the entire substitute for migrations and it is sufficient because the remedy is always "recreate".

**ARCH-STO-04** The seed dataset (REQ-DEV-02) is **`seed/*.sql` — plain SQL text, not a checked-in `.db` binary** — so it diffs and reviews like code. Milestone 08 owns its contents; this document fixes only that it is text, that it is loaded by the same loader used by tests and by `resetdb.py --seed`, and that it must include at least: two tracks (one archived, exercising REQ-SRCH-10), CV labels, posts in both scraped and manual `src_method`, posts matching multiple tracks, leads at every stage including `CLOSED` with several close reasons, applications covering every one of REQ-APPLY-04's eight outcome codes, and `run_log` rows in each status.

**ARCH-STO-05** **Time-relative seed data.** Auto-expiry (REQ-CRM-05, 28 days of inactivity) and post-age screening (REQ-SRCH-09) make absolute dates in a seed file rot: a fixture written today asserts differently next month. Two rules: (a) the seed loader writes date/timestamp columns **relative to load time** (e.g. a lead 27 days stale and one 29 days stale, computed at load); (b) all application code reads current time through a single `easymcf/clock.py::now()` indirection so a test can substitute a fixed clock instead of sleeping or waiting for wall-clock drift. Without (b), REQ-CRM-05 is not deterministically testable.

**ARCH-STO-06** Three database roles, never shared:

| role            | location                              | lifecycle                                                        |
| --------------- | ------------------------------------- | ---------------------------------------------------------------- |
| dev scratch     | `data/easymcf.db` (gitignored)        | long-lived, mutated freely; reset on demand                       |
| seed fixture    | `seed/*.sql` (committed, text)        | read-only source; never opened as a database                      |
| test databases  | pytest temp dir, one per test session | created, seeded, and deleted by the test run (ARCH-TEST-01)       |

`scripts/resetdb.py [--seed]` is the single reset path: delete the file at `EASYMCF_DB_PATH`, apply `schema.sql`, optionally apply `seed/`. Backup is deliberately not a feature — a developer's clean-state story is "re-seed", and there is no data in `010` whose loss matters (real MCF postings are re-scrapable, and the release is a POC).

**ARCH-STO-07** SQLite is opened in **WAL mode** with `busy_timeout=5000` and one connection per thread (`check_same_thread` left at its default, connections not shared across threads). Necessary because ARCH-RUN-02 has a background run thread writing incrementally (REQ-SRCH-04) while HTTP request threads read for the polling UI; WAL keeps readers from blocking on the writer. Foreign keys are enabled per connection (`PRAGMA foreign_keys = ON`) — off by default in SQLite, and the data model leans on FKs.

## 3. Networking

**ARCH-NET-01** The Flask process binds **`127.0.0.1:5000` only** — loopback, not `0.0.0.0`. `010` has no authentication and no multi-user model (REQ-PLAT-04, out-of-scope list); not listening on a routable interface is what makes that acceptable.

**ARCH-NET-02** Frontend and API share the single origin `http://127.0.0.1:5000` (ARCH-RUN-09), so **no CORS configuration, no preflight handling, and no `flask-cors` dependency exist**. If a future change splits the frontend onto its own origin, CORS becomes a required part of that change — it is not pre-provisioned here.

**ARCH-NET-03** The system makes **no outbound network calls except browser automation to `mycareersfuture.gov.sg`** (and its Singpass login redirect, which the user completes manually in their own browser — the app never drives it, per REQ-APPLY-06). No telemetry, no CDN for frontend assets (hence vendored `angular.min.js`), no package downloads at runtime. A developer can run the full app and the whole default test suite offline.

**ARCH-NET-04** Those MCF calls happen only when `EASYMCF_MCF_MODE=live` (ARCH-RUN-08). In `fixture` mode the browser never resolves an MCF hostname — requests are intercepted before dispatch (ARCH-TEST-04). Setting `live` is a deliberate human action in that session, consistent with the `CLAUDE.md` boundary; nothing in the default run path, the seeded app, or the default test suite sets it.

## 4. Browser automation infrastructure

**ARCH-BOT-01** **Playwright (Python) with its bundled Chromium is the single browser dependency**, for search scraping, apply automation, and end-to-end tests alike. This supersedes the prototype's split of Selenium + system Chrome/chromedriver for scraping and Playwright for apply ([010-prototype.md](010-prototype.md)). Rationale: (a) it removes the chromedriver/Chrome version-matching failure mode, a named `jobsearch` local-env pain point; (b) `page.route()` interception is what makes the mock-e2e tier possible without a stub that bypasses the real scraping code (ARCH-TEST-04); (c) one browser dependency instead of two, installed by `playwright install --with-deps chromium` into a user cache — nothing system-wide, nothing in the repo. The [selenium](../../../.claude/skills/selenium/SKILL.md) skill's substance — explicit waits instead of the prototype's fixed `sleep(15)`, stable `data-testid`/`data-cy` locators — carries over unchanged; only the driver API differs. If a concrete blocker appears during milestone 09/11, reverting scraping to Selenium is a contained change behind ARCH-BOT-02's interface, but it starts as Playwright.

**ARCH-BOT-02** All MCF interaction goes through **one `MCFBrowser` interface** in `easymcf/automation/browser.py`, with implementations selected by `EASYMCF_MCF_MODE`: `live.py` (real navigation) and `fixture.py` (identical code path, requests route-intercepted to the fixture corpus). Services never instantiate a browser directly. This is the seam that makes the entire automation layer testable unattended.

**ARCH-BOT-03** **MCF session credential storage — resolves open question #1 in [010-01-requirements.md](010-01-requirements.md).** The cookie bundle uploaded via Workflow 8 is written to **`.secrets/mcf_session.json`** (directory from `EASYMCF_SECRETS_DIR`, created `0700`, file `0600`). `.secrets` is already in `.gitignore`. The `session` table stores `cookie_ref` as the **filename only** — the payload never enters SQLite, so the database file stays safe to share, copy, or attach to a bug report. Rejected: (a) storing the cookie JSON in an env var or committed `.env` — a multi-kilobyte JSON blob is a poor fit for the environment, and `.env` files get committed by accident; (b) storing the payload in the `session` row — it would spread credential material into every database dump and seed export; (c) an OS keyring — a real dependency and platform-specific behavior for a single-user POC whose threat model is "don't commit it". Test tiers never read this file: the fixture-mode browser uses a synthetic cookie fixture, so a missing or expired real session cannot break the autonomous loop.

**ARCH-BOT-04** Backend startup logs the active `EASYMCF_MCF_MODE`, and any run triggered in `live` mode records it in `run_log` (as part of `outcome_counts`/error detail), so it is always answerable after the fact whether a given run touched the real site.

## 5. Testing infrastructure

The design goal is stronger than "tests exist": **an AI agent must be able to run a build → test → debug loop end to end with no human in the loop.** That imposes four properties on every tier below the live one — single-command invocation, exit-code pass/fail, disposable isolated state, and a hard timeout — and it is why the live tier is deliberately excluded from the loop rather than merely discouraged.

### Common mechanics

**ARCH-TEST-01** **State isolation: a fresh temp-file SQLite database per test session, seeded from `seed/*.sql`, deleted on teardown.** A `conftest.py` session fixture creates the file under pytest's `tmp_path_factory`, applies `schema.sql` + seed, and exports `EASYMCF_DB_PATH` to it; function-scoped tests that mutate data wrap in a transaction rolled back at teardown, or request a function-scoped fresh copy where a rollback is impractical. Temp *file*, not `:memory:` — an in-memory database is per-connection, which breaks the moment the app opens a second connection (it does: background run thread, ARCH-RUN-02/STO-07) and diverges from the WAL/file semantics being tested; at `010`'s data volumes the file costs milliseconds. The consequence that matters for the agent loop: **no test run ever touches `data/easymcf.db`, and no iteration inherits state from the previous one** — an agent can run the loop fifty times without a human resetting anything.

**ARCH-TEST-02** **Tooling: pytest for all three tiers**, with markers `backend`, `e2e`, `live` and `pytest.ini` carrying `addopts = -m "not live" --timeout=60 -q`. Consequences: bare `pytest` runs exactly the unattended-safe tiers; a hung browser or a scraper waiting on a selector that will never appear fails in 60 seconds instead of stalling the loop indefinitely (`pytest-timeout`); exit code 0/1 is the pass/fail signal, with `--junit-xml` available when structured output is wanted. No separate test runner, no `make`, no shell wrapper — the command *is* `pytest`.

| tier       | command                     | scope                                    | duration  |
| ---------- | --------------------------- | ---------------------------------------- | --------- |
| 1 backend  | `pytest -m backend`         | Flask test client + SQLite               | seconds   |
| 2 mock e2e | `pytest -m e2e`             | real browser + real Flask + fixture MCF  | ~1-2 min  |
| 3 live     | `pytest -m live --run-live` | real MCF, human-gated (REQ-DEV-05)       | on demand |

### Tier 1 — backend only (REQ-DEV-03)

**ARCH-TEST-03** Flask's **built-in test client** (`app.test_client()`), not `requests`/`httpx` against a spawned server: it needs no port, no process lifecycle, and no readiness polling, and it gives tracebacks from the failing line rather than a `500` body. Coverage: every generic CRUD shape per table (including the `mcfpipe` validation checklist — required-field `400` naming the field, type and date-format validation, `404` for missing record and for unknown table), lead lifecycle transitions and close reasons, auto-expiry against the injectable clock (ARCH-STO-05), apply-outcome → lead propagation (Workflow 7's table), and `run_log` writes. Service-layer tests drive the search/apply orchestration with a stubbed `MCFBrowser` (ARCH-BOT-02) so scoring, dedup, incremental persistence (REQ-SRCH-04 — assert rows exist after an injected mid-sweep exception), and outcome propagation are all exercised without a browser starting. This is the fast loop; a backend change should be re-verified here before anything slower runs.

### Tier 2 — mock end-to-end (REQ-DEV-04)

**ARCH-TEST-04** The full stack — Playwright Chromium driving the real AngularJS UI against the real Flask app against a seeded temp database — with **MCF itself replaced at the network boundary, not at the code boundary**. A session fixture spawns `python -m easymcf` on an ephemeral port with `EASYMCF_DB_PATH` set to the temp database, `EASYMCF_MCF_MODE=fixture`, and `EASYMCF_HEADLESS=1`, polls a `/api/health` endpoint until ready, and terminates it on teardown.

The stubbing mechanism is **Playwright `page.route()` interception**: requests matching `**mycareersfuture.gov.sg**` are fulfilled from a fixture corpus instead of dispatched. This is the load-bearing choice — the real scraper code runs, with its real selectors, waits, retries, pagination-termination and dedup logic; only the bytes come from disk. A stub that replaces the whole automation module would make this tier assert nothing about the automation it is supposed to cover.

Corpus layout under `tests/fixtures/mcf/`:

- `search/{keyword}_p{n}.html` — job-card list pages, including a final empty page so pagination termination (REQ-SRCH-03) is exercised, and overlapping cards across keywords so dedup (REQ-SRCH-05) is exercised.
- `detail/{urlid}.html` — profile pages, including at least one closed posting so REQ-SRCH-06's removal path is exercised.
- `apply/{scenario}/*.html` — one directory per REQ-APPLY-04 outcome, so **every one of the eight status codes is reachable deterministically** (apply button never resolving → `unable_to_apply`; no matching resume card → `cv_not_found`; submit failing → `questionnaire_required`; and so on). This is what lets the [deploy-and-validation-cycle](../../../.claude/skills/deploy-and-validation-cycle/SKILL.md) skill's "confirm each outcome code is reachable" check be an automated assertion rather than a manual exercise.
- `routes.json` — manifest mapping URL pattern → fixture file per scenario, so a test selects a scenario by name rather than wiring routes inline.

Fixture HTML is captured from real MCF pages once, by hand, in a live session (tier 3's territory) and committed — it is public job-listing markup, and it contains no session material. Because MCF's markup drifts (the reason `jobsearch/recommission.py` exists), a **fixture-staleness check belongs in tier 3, not tier 2**: tier 2's job is to be deterministic, and a fixture that no longer matches the live site is a real-site-drift finding, not a tier-2 failure.

**ARCH-TEST-05** **Frontend verification lives in this tier; there is no separate Karma/Jasmine JS unit tier in `010`.** Assertions are DOM-level Playwright assertions on rendered text, element state, and attributes — a run's status badge reaching `success`, an error banner appearing after a failed run (REQ-FE-02), a promoted post's row switching to `already promoted`, a lead card moving tabs on stage change. The tradeoff is stated plainly: a JS unit tier would give faster isolated feedback on controllers, at the cost of introducing node/npm/karma to a build-free frontend (ARCH-RUN-06). For roughly eight screens, DOM assertions in a tier that already exists give better signal per unit of infrastructure. On failure, Playwright writes a screenshot and the page HTML to `.dev/test-artifacts/` — **diagnostic aids for a human afterward, never a substitute for a pass/fail assertion.** No test may require a person to look at a browser to determine whether it passed.

### Tier 3 — live MCF (REQ-DEV-05)

**ARCH-TEST-06** Explicitly **outside the autonomous loop, by design.** Running it requires three independent conditions, none of which occurs by default: the `live` marker is deselected by `pytest.ini` and must be re-selected (`pytest -m live --run-live`), `EASYMCF_MCF_MODE=live` must be set (ARCH-RUN-08 defaults it to `fixture`), and a valid `.secrets/mcf_session.json` must exist (ARCH-BOT-03) — which only a human can produce, since login/MFA is manual and out of scope. An agent cannot satisfy the third condition at all, which is the point: this is the `CLAUDE.md` boundary against unattended live-site access made structural rather than advisory. **No agent may run this tier on its own initiative, and no automated loop invokes it.**

Content is the local successor to `jobsearch`'s `recommission.py`: a short sequential smoke protocol (browser loads → search page loads → cards found and parsed → detail page parsed → apply page selectors resolve) whose purpose is detecting MCF markup drift and refreshing the tier-2 fixture corpus when it is found. Apply-submission steps are excluded by default — they mutate real MCF-side application state — and gated behind a further explicit flag when genuinely needed.

### The agent's build → test → debug loop

**ARCH-TEST-07** What to run after each kind of change, and where the signal comes from:

| change | command | signal |
| ------ | ------- | ------ |
| backend (API, schema, services, scoring, CRM logic) | `pytest -m backend` | exit code; assertion tracebacks name the failing endpoint/field |
| frontend (AngularJS controller, template, service) | `pytest -m e2e -k <screen>` then `pytest -m e2e` | exit code from DOM assertions; screenshot + HTML artifact on failure for diagnosis |
| automation (scraper, apply state machine, selectors) | `pytest -m e2e -k automation` | exit code; each apply outcome asserted against its fixture scenario |
| schema (`schema.sql` or `seed/`) | `python scripts/resetdb.py --seed && pytest` | reset failure or test failure; `schema_version` mismatch surfaces as a startup error, not a cryptic SQL error |
| anything, before reporting done | `pytest` | runs tiers 1+2, excludes live automatically |

**ARCH-TEST-08** The properties that make the loop closed, stated as obligations on every future test added: single-command invocation; pass/fail from the exit code alone; per-session disposable database seeded from `seed/` (ARCH-TEST-01); MCF replaced by fixtures (ARCH-TEST-04); a hard timeout (ARCH-TEST-02). A test that needs a human to inspect output, or that leaves state behind for the next run, is a defect in the test — not an acceptable category of test.

## 6. Out of scope

Mirrors [010-01-requirements.md](010-01-requirements.md)'s out-of-scope section and `CLAUDE.md`'s boundaries; restated here so milestone 07/08 doesn't drift into it while building the local environment:

- **No cloud anything** — no AWS/GCP/Azure SDK, credential file, deployment target, or hosted service dependency. No S3/DynamoDB/RDS/Lambda/API Gateway. `010` runs offline apart from the gated MCF automation calls (ARCH-NET-03).
- **No containers or orchestration** — no Dockerfile, docker-compose, Kubernetes, or VM image. The install procedure is `python -m venv`, `pip install -r`, `playwright install chromium`.
- **No CI/CD** — no GitHub Actions workflow, no pipeline configuration, no automated deploy. Tests are run locally by a developer or an agent, on demand.
- **No multi-user concerns** — no auth, no sessions (beyond the single MCF credential), no per-user data partitioning, no `user_id` columns (see [010-data-model.md](010-data-model.md)'s deliberate divergence from `mcfpipe`'s multi-user `track`), no `0.0.0.0` binding.
- **No process manager, scheduler, or queue** — no systemd unit, cron entry, Celery/redis, or supervisor. Runs are user-initiated (REQ-SRCH-02) and in-process (ARCH-RUN-02).
- **No migration framework, no ORM migrations, no database backup tooling** — recreate-and-reseed is the whole story (ARCH-STO-02/06).
- **No frontend build toolchain** — no node, npm, webpack, bundler, transpiler, or JS test runner (ARCH-RUN-06, ARCH-TEST-05).

Each of these becomes a live question again at `020` (MVP cloud). None of them is a live question in `010`, and adding one is a scope change to be raised with the product-manager rather than decided in an implementation PR.
