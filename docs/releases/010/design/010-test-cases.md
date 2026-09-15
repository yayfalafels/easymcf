# Easy MCF POC Local - Test Cases

## Contents

- [Purpose](#purpose)
- [Out of scope](#out-of-scope)
- [References](#references)
- [Traceability note](#traceability-note)
- [1. Data model / DB silo](#1-data-model--db-silo)
- [2. Backend API silo](#2-backend-api-silo)
- [3. Automation silo](#3-automation-silo)
- [4. Frontend silo](#4-frontend-silo)
- [5. Mock end-to-end tier](#5-mock-end-to-end-tier)

## Purpose

This document's direct input is the **test-strategy doc**'s concrete test-case inventory. Every case below traces to at least one requirement (`STRAT-CASE-01`), is organized by the silo that owns its logic (`STRAT-01`, the "test each component where its logic lives" principle) rather than by requirement section, and states enough to write the actual pytest case from: preconditions, action, and expected outcome in one line, not a template to be filled in later. This document doesn't restate `STRAT-SILO-*`'s tooling/mechanics or `ARCH-TEST-*`'s tier mechanics. Read those first for *how* a silo runs. This document is *which* cases run in it.

## Out of scope

- Live-tier (tier 3) test cases. `ARCH-TEST-06`'s human-gated smoke protocol has no case-authoring guidance here or in the **test-strategy doc**. It is a markup-drift check, not a case suite.
- The literal pytest source: `tests/backend/cases/*.json` entries, fixture-scenario wiring, Playwright selectors. This is milestone 09-11 (functional builds) implementation detail. This document specifies *what* each case asserts, not the harness code that asserts it.
- Performance/load cases. The **test-strategy doc** already excludes this category for a single local user.

## References

- **test-strategy doc**: [010-test-strategy.md](010-test-strategy.md) — `STRAT-SILO-01..07` names the five silos this document's five sections instantiate. `STRAT-CASE-01..07` names the strategic rules: traceability, transition tables not spot checks, boundary values, named-regression permanence, enumeration completeness, determinism, silo-first authoring order. Every case below follows at least one of these.
- **requirements doc**: [010-01-requirements.md](010-01-requirements.md) — every `REQ-*` id cited below. This is the source of truth a case's expected outcome is checked against.
- **api doc**: [010-api.md](010-api.md) — the endpoint/hook/named-endpoint catalog the Backend API silo's cases are organized around.
- **workflows doc**: [010-workflows.md](010-workflows.md) — Workflow 5 (lead lifecycle) and 7 (apply-outcome propagation), the transition tables `TC-API-012/013/025` enumerate in full rather than spot-checking.
- **data model**: [010-data-model.md](010-data-model.md) — entity/constraint definitions the Data model silo's cases assert against directly.
- **user-interface doc**: [010-user-interface.md](010-user-interface.md) — the page inventory the Frontend silo's cases are organized around, one case group per page.
- **prototype extraction**: [010-prototype.md](010-prototype.md) — the named `jobsearch` defects, `updateOpenExpired()`'s unconditional overwrite, end-of-run-only persistence, salary-percentile scoring, that `TC-API-018`, `TC-AUTO-003`, and `TC-AUTO-008` are permanent regression cases against (`STRAT-CASE-04`).
- **architecture doc**: [010-architecture.md](010-architecture.md) — `ARCH-TEST-*` tier mechanics the REQ-DEV-* infrastructure requirements are satisfied against.

Case ids carry a `TC-<silo>-NNN` scheme (`DB`/`API`/`AUTO`/`FE`/`E2E`), matching the five silos below.

## Traceability note

Every functional `REQ-*` (`REQ-SRCH-*`, `REQ-CRM-*`, `REQ-APPLY-*`, `REQ-PLAT-01..03`, `REQ-FE-02`) has at least one case below tagged with its id, satisfying `STRAT-CASE-01`. Three groups are the deliberate exception, each satisfied collectively rather than by a single tagged row. `REQ-DEV-01..05` describe the test *infrastructure itself*, a documented local setup, seed data availability, the three test protocols existing, rather than product behavior. These are satisfied by this document, the **architecture doc**'s `ARCH-TEST-*` tiers, and the seed dataset existing and being used to run every case below. `REQ-FE-01`, the screen inventory covering track config, post browsing, lead management, apply-queue review, and session status, is satisfied by `TC-FE-001..019` as a set, one page-group per inventory item, not by any single row. `REQ-PLAT-04`, "runs entirely on the user's local machine," is a topology assertion verified by inspection: the absence of a cloud SDK, credential file, or non-loopback bind (`ARCH-NET-01`). This is the same category as `REQ-DEV-*`, not a behavior a functional case exercises. The live tier (`ARCH-TEST-06`, `REQ-DEV-05`) is out of scope for the same reason the **test-strategy doc** gives it no case-authoring guidance. It's a human-gated markup-drift smoke check, never a functional-correctness tool, and no case in this document may require it to pass.

## 1. Data model / DB silo

Direct against `scripts/db_util.py` and a temp SQLite database (`STRAT-SILO-01`), no Flask process, no browser. This is the fastest signal. It validates schema, constraints, and dedup identity before any service or route exists on top of them.

| id        | requirement(s)           | title                                                         |
| --------- | ------------------------ | ------------------------------------------------------------- |
| TC-DB-001 | ARCH-STO-02              | Schema applies cleanly from schema.sql                        |
| TC-DB-002 | REQ-PLAT-02              | Round-trip insert/get for catalog tables                      |
| TC-DB-003 | REQ-SRCH-05, REQ-SRCH-08 | Round-trip insert/get for FK-heavy tables                     |
| TC-DB-004 | REQ-CRM-01               | UNIQUE constraint on lead.post_id                             |
| TC-DB-005 | ARCH-STO-07              | FK violation rejected                                         |
| TC-DB-006 | ARCH-RUN-03              | run_log partial UNIQUE index blocks concurrent same-type runs |
| TC-DB-007 | REQ-APPLY-02             | cv delete blocked while referenced                            |
| TC-DB-008 | REQ-SRCH-05              | post.id dedup scheme                                          |
| TC-DB-009 | ARCH-STO-03              | Stale schema_version refuses to start                         |

- **TC-DB-001** — `scripts/initdb.py` against a fresh temp file creates every table in the **data model** with no error. The meta `schema_version` row is set.
- **TC-DB-002** — `db_util.py insert`/`get` on `role`, `track`, `search_profile`, `cv` each return the row unchanged. A follow-up `update`/`delete` round-trips too.
- **TC-DB-003** — `post`, `post_track`, `lead`, `application` each round-trip through `db_util.py`, including their FK columns (`track_id`, `post_id`, `lead_id`, `cv_id`, `run_id`) resolving to real parent rows.
- **TC-DB-004** — A second `INSERT` into `lead` with a `post_id` already present in another `lead` row fails the `UNIQUE` constraint. This is what backs the promote-endpoint's `409`, per the **api doc**'s `lead` resource entry.
- **TC-DB-005** — Inserting a `lead` row with a `track_id` that doesn't exist in `track` fails the FK constraint, `PRAGMA foreign_keys = ON` is active on the connection, rather than silently succeeding.
- **TC-DB-006** — Two `INSERT`s of `run_log(run_type='search', status='running')` in the same database: the second fails `ux_run_log_running`'s constraint even without an application-level pre-check. This is the regression `ISS-03` named.
- **TC-DB-007** — `DELETE FROM cv WHERE id=?` for a `cv.id` still referenced by `track.default_cv_id` or `application.cv_id` fails the FK constraint, backing the **api doc**'s `cv` `409`-translation rule.
- **TC-DB-008** — Two `post` rows built from the same `source`+`posting_reference`+`posted_date` collapse to the same primary key value. A raw duplicate insert is rejected by the database. Search-service upsert behavior belongs to the later jobs-pipeline milestone.
- **TC-DB-009** — Pointing the backend at a temp database whose `meta.schema_version` doesn't match the code's expected version fails startup with the explicit `"database is version N, code expects M"` message, not a downstream `no such column` error.

## 2. Backend API silo

Flask's test client against a seeded temp database (`ARCH-TEST-03`, `STRAT-SILO-03`) exercises every generic CRUD shape's validation checklist, plus the hook-backed and named-endpoint behavior the **api doc** specifies. This is the fast loop. A backend change is re-verified here before anything slower runs.

| id         | requirement(s)             | title                                                |
| ---------- | --------------------------- | ---------------------------------------------------- |
| TC-API-001 | REQ-PLAT-01                | Generic CRUD happy path                              |
| TC-API-002 | REQ-PLAT-01                | Generic CRUD validation errors                       |
| TC-API-003 | REQ-PLAT-01                | Generic CRUD not-found errors                        |
| TC-API-004 | REQ-SRCH-10                | Track archive/unarchive                              |
| TC-API-005 | REQ-APPLY-02               | cv delete-while-referenced 409                       |
| TC-API-006 | REQ-SRCH-06                | post read-only surface                               |
| TC-API-007 | REQ-SRCH-07                | API-EP-01 manual post entry                          |
| TC-API-008 | REQ-SRCH-07                | Manual post bypasses score filter                    |
| TC-API-009 | REQ-SRCH-08                | post_track many-to-many                              |
| TC-API-010 | REQ-CRM-01                 | lead create (promote)                                |
| TC-API-011 | REQ-CRM-01                 | lead create rejects double-promotion                 |
| TC-API-012 | REQ-CRM-02                 | lead legal stage transitions accepted                |
| TC-API-013 | REQ-CRM-02                 | lead illegal stage transitions rejected              |
| TC-API-014 | REQ-CRM-02                 | lead close requires close_reason                     |
| TC-API-015 | REQ-CRM-08                 | Every lead write appends a lead_event                |
| TC-API-016 | REQ-CRM-03, REQ-CRM-04     | lead free fields unrestricted                        |
| TC-API-017 | REQ-CRM-05                 | Auto-expiry boundary — 27 vs 29 days                 |
| TC-API-018 | REQ-CRM-05                 | Auto-expiry never overwrites an advanced/closed lead |
| TC-API-019 | REQ-CRM-05                 | Auto-expiry evaluated on every read                  |
| TC-API-020 | REQ-CRM-06                 | lead delete not exposed                              |
| TC-API-021 | REQ-CRM-08                 | lead_event read-only                                 |
| TC-API-022 | REQ-APPLY-01               | API-EP-02 queue applications                         |
| TC-API-023 | REQ-APPLY-11               | API-EP-03 dequeue application                        |
| TC-API-024 | REQ-APPLY-01               | application write surface is restricted              |
| TC-API-025 | REQ-APPLY-09, REQ-APPLY-10 | Apply-outcome → lead propagation, all eight codes    |
| TC-API-026 | REQ-APPLY-08               | One application failure never overwrites another     |
| TC-API-027 | REQ-APPLY-08               | Retry is a new row, not an overwrite                 |
| TC-API-028 | REQ-PLAT-03                | run_log read-only surface                            |
| TC-API-029 | REQ-SRCH-02                | API-EP-04 search run trigger                         |
| TC-API-030 | REQ-APPLY-03               | API-EP-05 apply run trigger                          |
| TC-API-031 | ARCH-RUN-03                | Run-in-flight guard returns 409                      |
| TC-API-032 | REQ-PLAT-03                | run_log diagnosable without re-running               |
| TC-API-033 | REQ-APPLY-06               | session read-only, write blocked                     |
| TC-API-034 | REQ-APPLY-06               | API-EP-06 session upload validates domain            |
| TC-API-035 | ARCH-TEST-04               | API-EP-07 health check                               |
| TC-API-036 | REQ-PLAT-02                | SQLite is the only store                             |

- **TC-API-001** — For each pure-generic table (`role`, `track`, `search_profile`, `cv`, `post_track`): `POST` creates (`201`), `GET` reads it back unchanged, `PUT` updates, `GET /search` lists/filters it, `DELETE` removes it, `POST /batch` creates/updates several rows in one call. This is the `STRAT-SILO-04` checklist's happy-path leg, run once per table.
- **TC-API-002** — Omitting a required field on `POST`/`PUT` for any pure-generic table returns `400` naming the missing field. A malformed type or date-format value returns `400` naming the offending field, per `mcfpipe`'s validation checklist (`easymcf-backend-api` skill).
- **TC-API-003** — `GET/PUT/DELETE` on a nonexistent row id returns `404` with a descriptive message. Any of the seven generic shapes against an unrecognized `{table}` name returns `404` naming the unknown table, not a `500`.
- **TC-API-004** — `PUT /api/v1/track/{id} {"is_active": false}` succeeds as a plain generic write. The track's historical `post_track`/`lead`/`application` rows stay readable, and `is_active=true` un-archives it the same way.
- **TC-API-005** — `DELETE /api/v1/cv/{id}` for a label referenced by `track.default_cv_id` or `application.cv_id` returns `409` naming the referencing rows, per the **api doc**'s `cv` entry, not a bare SQL error.
- **TC-API-006** — `GET`/`search /api/v1/post` work normally including `is_open`/`closing_date`/`applicants`/etc. `PUT`/`DELETE /api/v1/post/{id}` and a bare `POST /api/v1/post` are all rejected. Only `API-EP-01` may create one.
- **TC-API-007** — `POST /api/v1/posts/manual` with position/company/url/salary/date creates the `post` (`src_method='manual'`), scores it against every track, and creates the resulting `post_track` rows (`search_match=false`) in the same request.
- **TC-API-008** — A manually-entered post whose computed match score is below a track's `min_match_score` is still visible for promotion under that track. The score filter (`REQ-SRCH-09`) only screens search-discovered posts.
- **TC-API-009** — A single `post` scored against two different tracks produces two independent `post_track` rows with independent `match_score`/`score_method` values, editable/removable independently via generic CRUD.
- **TC-API-010** — `POST /api/v1/lead {post_id, track_id}` creates the row with `status='OPEN'`, `stage='PROSPECT'`, `created_at`/`updated_at` set, and one `stage_change` `lead_event`. This is the **api doc**'s `lead` create path.
- **TC-API-011** — A second `POST /api/v1/lead` for a `post_id` that already has a `lead` row returns `409` naming the existing `lead_id`. This drives the Posts screen's "already promoted" state.
- **TC-API-012** — Every edge in the **workflows doc**'s Workflow 5 state diagram (`PROSPECT→TOAPPLY→APPLIED→CALLBACK→INTERVIEW→OFFER`, and each stage's manual path to `CLOSED`) is accepted by `PUT /api/v1/lead/{id}`.
- **TC-API-013** — A `PUT` attempting a transition not on Workflow 5's diagram, for example `PROSPECT` straight to `OFFER`, returns `409`, never silently applied.
- **TC-API-014** — `PUT` setting `stage='CLOSED'` without a `close_reason` returns `400`. Supplying one of the seven valid reasons succeeds. An eighth/invalid value returns `400`.
- **TC-API-015** — A `notes` edit, a `deadline` change, a `last_contact_date` update, and a `stage` change each append exactly one `lead_event` row of the matching `event_type` and refresh `lead.updated_at` from it. This is REQ-CRM-08's single write path. No field bypasses it.
- **TC-API-016** — `notes`, `deadline`, `title_override`, `company_override`, `applied_date`, `first_attempt_date`, `last_contact_date` all accept a plain write with no transition-legality check, and the underlying `post` row is never mutated by a `title_override`/`company_override` write.
- **TC-API-017** — A `lead` whose latest `lead_event` is 27 days old stays `OPEN` on the next `GET`. One at 29 days is closed (`stage='CLOSED'`, `close_reason='expired'`) on read, using the injectable clock (`ARCH-STO-05`), not a live sleep.
- **TC-API-018** — The named `jobsearch` regression this release must not repeat: a `lead` already at `APPLIED`/`INTERVIEW`/`OFFER`/`CLOSED` is untouched by the expiry check even when its `deadline` has passed. Expiry keys off `updated_at` alone, never `deadline`, and never touches a lead with recent activity (`STRAT-CASE-02`).
- **TC-API-019** — Two consecutive `GET /api/v1/lead/search` calls against a lead that crosses the 28-day threshold between them: the first call still shows it `OPEN`, the second shows it `CLOSED`, with no background job or scheduler involved.
- **TC-API-020** — `DELETE /api/v1/lead/{id}` is rejected. The only way to remove a lead from the active pipeline is `PUT stage='CLOSED'`, which preserves its history.
- **TC-API-021** — `GET/search /api/v1/lead_event` returns the log for a given `lead_id`. `POST`/`PUT`/`DELETE /api/v1/lead_event` are all rejected. Every row must come from a `lead` write's internal side effect.
- **TC-API-022** — `POST /api/v1/applications/queue {lead_ids: [...]}` with every id at stage `PROSPECT` creates one `application(status='queued')` per lead and transitions each lead to `TOAPPLY`. An id not at `PROSPECT` returns `409` naming it and queues nothing from that request.
- **TC-API-023** — `POST /api/v1/applications/{id}/dequeue` on a `queued` row deletes it and closes the owning lead with `close_reason='withdrawn'`. This is not a revert to `PROSPECT`, and the lead is not eligible to be re-queued afterward.
- **TC-API-024** — A bare `POST`/`PUT`/`DELETE /api/v1/application` is rejected. The only entry points are `API-EP-02`/`API-EP-03` and the internal apply-run write path.
- **TC-API-025** — For each of REQ-APPLY-04's eight outcome codes, this asserts the lead-side effect the **workflows doc**'s Workflow 7 specifies: `applied`→`APPLIED`; `post_closed`/`post_unavailable`→`CLOSED`/`apply_failed`; the remaining five (`questionnaire_required`, `cv_selector_error`, `unable_to_apply`, `cv_not_found`, `invalid_input`) leave the lead at `TOAPPLY`.
- **TC-API-026** — Two applications in the same batch, one failing and one succeeding: the failing one's outcome doesn't block or overwrite the succeeding one's recorded status, and both rows persist independently.
- **TC-API-027** — A lead that failed with `cv_not_found`, gets its CV fixed, and is re-queued/re-run ends up with two `application` rows for the one lead, both readable. This is the retry history REQ-APPLY-08 requires.
- **TC-API-028** — `GET/search /api/v1/run_log` returns rows including `outcome_counts`/`error_detail`. `PUT`/`POST`/`DELETE /api/v1/run_log` are all rejected. Only `API-EP-04`/`05` and the background thread write it.
- **TC-API-029** — `POST /api/v1/runs/search {track_id}` creates a `run_log(run_type='search', status='running')` row, starts the background thread, and returns the new `run_log.id` immediately, not blocking on the sweep.
- **TC-API-030** — `POST /api/v1/runs/apply` with no body creates a `run_log(run_type='apply', status='running')` row and starts the apply thread over every currently-`queued` application.
- **TC-API-031** — Triggering `API-EP-04` a second time while a `search` run is still `running` returns `409` with the in-flight `run_log.id`, without racing the atomic index. This complements `TC-DB-006` at the HTTP layer.
- **TC-API-032** — A completed run's `run_log` row carries `outcome_counts` and, on partial/failed status, a populated `error_detail` sufficient to explain the outcome without re-triggering the run.
- **TC-API-033** — `GET /api/v1/session/1` returns the singleton row. `PUT`/`POST /api/v1/session` are rejected. Only `API-EP-06` may change `status`.
- **TC-API-034** — `POST /api/v1/session/upload` with a cookie payload containing a `mycareersfuture.gov.sg` cookie sets `status='valid'`. A payload with no matching-domain cookie returns `400` and leaves the session untouched.
- **TC-API-035** — `GET /api/v1/health` returns `200 {"status": "ok"}` once the app is ready to serve. This is the signal the mock-e2e harness's readiness poll depends on.
- **TC-API-036** — A search run, a lead promotion, and an apply run each leave a fully-reconstructable trail in `data/easymcf.db` alone. No parallel config file or external store holds state the database doesn't.

## 3. Automation silo

Service-layer calls (`easymcf/services/search.py`/`apply.py`) against the fixture `MCFBrowser` (`ARCH-BOT-02`, `STRAT-SILO-05`), with no HTTP request and no real browser chrome. Every one of REQ-APPLY-04's eight outcomes and REQ-SRCH-06's post-closed-during-detail-pass path is reachable here, per `STRAT-SILO-06`, before the mock e2e tier re-confirms the same scenario is reachable by clicking through the UI.

| id          | requirement(s)             | title                                                |
| ----------- | --------------------------- | ---------------------------------------------------- |
| TC-AUTO-001 | REQ-SRCH-03                | Search pagination terminates                         |
| TC-AUTO-002 | REQ-SRCH-05                | Dedup id prevents duplicate posts across runs        |
| TC-AUTO-003 | REQ-SRCH-04                | Incremental persistence survives a mid-sweep failure |
| TC-AUTO-004 | REQ-SRCH-06                | Detail pass populates full fields                    |
| TC-AUTO-005 | REQ-SRCH-06                | Detail pass removes an already-closed post           |
| TC-AUTO-006 | REQ-SRCH-09                | Match score uses title-keyword method                |
| TC-AUTO-007 | REQ-SRCH-01, REQ-SRCH-09   | Screening applies age and score cutoffs              |
| TC-AUTO-008 | REQ-SRCH-09                | Salary-percentile scoring is absent                  |
| TC-AUTO-009 | REQ-APPLY-04               | Apply outcome: applied                               |
| TC-AUTO-010 | REQ-APPLY-04, REQ-APPLY-05 | Apply outcome: questionnaire_required                |
| TC-AUTO-011 | REQ-APPLY-04               | Apply outcome: cv_selector_error                     |
| TC-AUTO-012 | REQ-APPLY-04, REQ-APPLY-07 | Apply outcome: unable_to_apply                       |
| TC-AUTO-013 | REQ-APPLY-04               | Apply outcome: post_unavailable                      |
| TC-AUTO-014 | REQ-APPLY-04               | Apply outcome: cv_not_found                          |
| TC-AUTO-015 | REQ-APPLY-04               | Apply outcome: post_closed                           |
| TC-AUTO-016 | REQ-APPLY-04               | Apply outcome: invalid_input                         |
| TC-AUTO-017 | REQ-APPLY-07, ARCH-BOT-05  | Apply-button retry timing, overridable               |
| TC-AUTO-018 | REQ-APPLY-02               | CV selection by substring match                      |

- **TC-AUTO-001** — The service-level search sweep against the fixture corpus's final empty page stops paginating rather than looping. This uses the `search/{keyword}_p{n}.html` empty-page fixture (`ARCH-TEST-04`).
- **TC-AUTO-002** — Running the same search twice against overlapping fixture cards produces exactly one `post` row per card, keyed on `source`+`posting_reference`+`posted_date`.
- **TC-AUTO-003** — The named `jobsearch` regression: an injected exception partway through a multi-keyword sweep leaves every post already scraped before the failure persisted in `post`. It is not lost to an all-or-nothing write (`STRAT-CASE-04`).
- **TC-AUTO-004** — A post run through the detail-pass fixture gets `closing_date`, `applicants`, `industry_classification`, `description`, and `mcf_ref` populated from the fixture profile page.
- **TC-AUTO-005** — A post whose fixture detail page indicates it's closed is flipped `is_open=false`, soft-removed from the active set, rather than left with stale open-looking fields.
- **TC-AUTO-006** — A scored post's `post_track.match_score` matches the title-keyword formula's output for that title/track pair, and `score_method='title_keyword_v1'` is recorded alongside it.
- **TC-AUTO-007** — A post older than a track's `max_age_weeks`, or scored below its `min_match_score`, is excluded from that track's screened view. A manually-entered post with the same low score is not excluded, per `REQ-SRCH-07`'s bypass.
- **TC-AUTO-008** — The named deprecated-feature regression: no code path in the scoring service references a salary-percentile or industry-classification component. The score is a pure function of title-keyword match (`STRAT-CASE-04`).
- **TC-AUTO-009** — The apply-service fixture scenario where the button click and final submit both succeed yields `status='applied'`, including the "already applied" page-text variant of the same outcome.
- **TC-AUTO-010** — The fixture scenario where the final review-submit fails, assumed multi-step questionnaire, yields `status='questionnaire_required'`. The run does not attempt to complete it or abort, REQ-APPLY-05's explicit non-goal, and moves on to the next queued application.
- **TC-AUTO-011** — The fixture scenario with a broken/unexpected resume-selector DOM yields `status='cv_selector_error'`, distinct from a genuine no-match.
- **TC-AUTO-012** — The fixture scenario where the apply button never resolves exhausts all configured retries and yields `status='unable_to_apply'`.
- **TC-AUTO-013** — The fixture scenario where the posting URL fails to load yields `status='post_unavailable'` without attempting the button poll at all.
- **TC-AUTO-014** — The fixture scenario with resume cards present but none matching the configured CV substring yields `status='cv_not_found'`.
- **TC-AUTO-015** — The fixture scenario where the apply-error message text indicates the posting has closed yields `status='post_closed'`, distinct from `post_unavailable`.
- **TC-AUTO-016** — A queued application missing `jobid`/`url`/`cv_version` is rejected with `status='invalid_input'` before any browser action is attempted.
- **TC-AUTO-017** — The default 5-retry/5-second-delay policy is exercised against the `unable_to_apply` fixture in production timing once, and against a shortened `APPLY_POLL_RETRIES`/`_DELAY_S` override for routine test runs, proving the retry loop and its terminal state without spending real wall-clock seconds each run.
- **TC-AUTO-018** — The configured CV label matches the correct resume card by substring against the fixture's card titles, independent of card ordering. No match falls through to `cv_not_found` (`TC-AUTO-014`).

## 4. Frontend silo

Playwright drives the real AngularJS app served by a real `python -m easymcf` process, with every `/api/**` call intercepted and fulfilled from `tests/fixtures/api/*.json` (`ARCH-TEST-09`, `STRAT-SILO-07`). This isolates controller/template/rendering defects from whether the real backend produced the response correctly.

| id        | requirement(s)         | title                                                     |
| --------- | ------------------------ | ----------------------------------------------------------- |
| TC-FE-001 | REQ-SRCH-01            | Tracks — create/edit track and search profile             |
| TC-FE-002 | REQ-SRCH-10            | Tracks — archive toggle                                   |
| TC-FE-003 | REQ-APPLY-02           | CVs — add/rename/remove, blocked-delete message           |
| TC-FE-004 | REQ-SRCH-09            | Posts — results sorted by score, filters                  |
| TC-FE-005 | REQ-FE-02              | Posts — async search-run state                            |
| TC-FE-006 | REQ-CRM-01             | Posts — promote-to-lead row action                        |
| TC-FE-007 | REQ-SRCH-07            | Manual Post Entry — save and promote                      |
| TC-FE-008 | REQ-CRM-02, REQ-CRM-07 | Leads — pipeline board and stage control                  |
| TC-FE-009 | REQ-CRM-02             | Leads — Applied/Callbacks/Interviews/Offers tabs          |
| TC-FE-010 | REQ-CRM-06             | Leads — Closed tab                                        |
| TC-FE-011 | REQ-CRM-05             | Leads — expiry warning indicator                          |
| TC-FE-012 | REQ-CRM-03, REQ-CRM-08 | Lead Detail — edit fields and activity history            |
| TC-FE-013 | REQ-CRM-06             | Lead Detail — close behind confirmation                   |
| TC-FE-014 | REQ-APPLY-01           | Applications — queued list and CV override                |
| TC-FE-015 | REQ-APPLY-11           | Applications — dequeue behind confirmation                |
| TC-FE-016 | REQ-APPLY-03           | Applications — run batch behind confirmation, async state |
| TC-FE-017 | REQ-APPLY-04           | Applications — results view per-outcome actions           |
| TC-FE-018 | REQ-PLAT-03, REQ-FE-02 | Automation — Runs tab and Session tab                     |
| TC-FE-019 | REQ-FE-02              | Cross-cutting — error surfacing and empty states          |

- **TC-FE-001** — The Tracks screen's combined role+seniority+search-profile form (page 1) saves in one step and the new track appears in the list with its search-profile summary.
- **TC-FE-002** — Archiving a track drops it from the active list and from every track selector elsewhere, mocked responses for Posts/promote/apply-CV selectors. The archived-tracks toggle reveals it again.
- **TC-FE-003** — The CVs screen (page 2) adds and renames a label normally. Removing a label the mocked `/api` response marks as in-use surfaces the inline blocked-delete explanation instead of silently failing.
- **TC-FE-004** — The Posts results table (page 3) renders sorted by match score descending by default. Adjusting the score-threshold and "include below-threshold" filters re-renders the mocked result set accordingly.
- **TC-FE-005** — Clicking "Run search" switches the page into the running state, progress indicator, live counts, against a mocked polling sequence, and a completion toast summarizes the mocked terminal outcome.
- **TC-FE-006** — Promoting a single-track post creates the lead directly. Promoting a multi-track post opens the track-picker defaulting to the currently-viewed track. Either way the row switches to "already promoted" with the action disabled.
- **TC-FE-007** — Submitting the manual-entry dialog (page 4) returns to Posts with the new "manual"-tagged posting visible and immediately promotable.
- **TC-FE-008** — The Pipeline tab's `PROSPECT`/`TOAPPLY` board (page 5) renders one column per stage. The move-to-next-stage control and stage-jump dropdown both update a card's column against the mocked response. Every one of these interactions is a UI/API round-trip, with no spreadsheet-editing or menu-script equivalent anywhere in the app (REQ-CRM-07).
- **TC-FE-009** — Each of the four flat-list tabs renders its stage-specific fields, applied date, last contact, interview notes, offer deadline, from the same mocked `lead` list, filtered client-side by stage.
- **TC-FE-010** — The Closed tab lists `close_reason` per row and marks an auto-closed (`expired`/`apply_failed`) lead distinctly from a manually-closed one.
- **TC-FE-011** — A card/row's days-since-last-activity indicator shifts into its warning state as the mocked `lead_event` timestamp approaches the 28-day threshold, on every tab, not only the board.
- **TC-FE-012** — The Lead Detail panel (page 6) saves deadline/notes/override edits, and its activity history renders the mocked `lead_event` list in reverse-chronological order interleaved with `application` attempts.
- **TC-FE-013** — The manual close action requires selecting one of the seven reasons and confirming via the shared confirm-modal before the mocked close request fires.
- **TC-FE-014** — The Applications screen (page 7) lists queued rows with the track-default CV pre-filled and an override control drawing on the mocked CV catalog.
- **TC-FE-015** — Removing a queued row requires confirmation, then removes it from the list and reflects the mocked lead-closed-as-withdrawn outcome.
- **TC-FE-016** — "Run apply batch" requires confirmation, since it mutates MCF-side state, then enters the async running state with mocked per-application progress counts.
- **TC-FE-017** — Post-run, each mocked outcome renders its Workflow-7 next action inline. `cv_not_found` gets "fix CV and retry," `post_closed` gets "lead auto-closed" with a link, `applied` gets "lead moved to Applied."
- **TC-FE-018** — The Runs tab (page 8) lists mocked `run_log` rows reverse-chronological with expandable error detail. The Session tab shows mocked status/upload-history and the upload dialog round-trips a mocked cookie payload.
- **TC-FE-019** — A mocked failed/partial run surfaces inline on its triggering page and in the Runs tab, never console-only. A mocked missing/expired session blocks the Applications run button specifically. Every list page's mocked-empty response renders its documented empty-state call to action.

## 5. Mock end-to-end tier

Playwright Chromium drives the real UI against the real Flask app against a seeded temp database, with MCF replaced at the network boundary (`ARCH-TEST-04`). Per `STRAT-02`, this tier is the **final confirmation step**, not the primary place a logic defect is found. Every case here exists to catch a wiring defect the silos above can't see, not to re-derive logic they already proved.

| id         | requirement(s) | title                                               |
| ---------- | --------------- | ---------------------------------------------------- |
| TC-E2E-001 | REQ-FE-02      | Search-run golden path through the real UI          |
| TC-E2E-002 | REQ-APPLY-03   | Apply-run golden path through the real UI           |
| TC-E2E-003 | REQ-APPLY-04   | All eight apply outcomes reachable end-to-end       |
| TC-E2E-004 | REQ-CRM-01     | Promote-to-lead end-to-end, including the 409 state |
| TC-E2E-005 | REQ-APPLY-06   | Session establishment round-trip                    |
| TC-E2E-006 | ARCH-TEST-07   | Full-suite regression smoke                         |

- **TC-E2E-001** — Trigger a search run from the real Posts screen against the fixture MCF corpus. The poll loop reaches `success` and results render with match scores. This confirms the backend-thread/frontend-poll wiring `STRAT-CASE-07` calls out as needing a mock-e2e case beyond the silos.
- **TC-E2E-002** — Queue a lead from Leads, run the apply batch from Applications against the fixture apply corpus, and confirm the results view renders the real per-application outcome.
- **TC-E2E-003** — Each of the eight `apply/{scenario}/` fixture directories is driven through the real Applications UI at least once, confirming the DOM-level result matches what `TC-AUTO-009..016` already proved at the service level.
- **TC-E2E-004** — Promoting a post through the real Posts UI creates a real lead visible on Leads. Attempting to promote the same post again, via a second fixture-backed post row, shows the "already promoted" UI state.
- **TC-E2E-005** — "Log in to MCF" opens an ordinary, non-Playwright-automated, browser context per `ARCH-NET-03`. Uploading a fixture-shaped cookie payload through the dialog updates the real session-status badge.
- **TC-E2E-006** — `python scripts/resetdb.py --seed && pytest` stays green from a clean reseed. This is the "anything, before reporting done" check every functional change is re-verified against.
</content>
