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
- [6. Authentication and ownership silo](#6-authentication-and-ownership-silo)

## Purpose

This document's direct input is the **test-strategy doc**'s concrete test-case inventory. Every case below traces to at least one requirement (`STRAT-CASE-01`), is organized by the silo that owns its logic (`STRAT-01`, the "test each component where its logic lives" principle) rather than by requirement section, and states enough to write the actual pytest case from: preconditions, action, and expected outcome in one line, not a template to be filled in later. This document doesn't restate `STRAT-SILO-*`'s tooling/mechanics or `ARCH-TEST-*`'s tier mechanics. Read those first for *how* a silo runs. This document is *which* cases run in it.

## Out of scope

- Live-tier (tier 3) test cases. `ARCH-TEST-06`'s human-gated protocols, the MCF markup-drift smoke check and the Google sign-in check, have no case-authoring guidance here or in the **test-strategy doc**. They are confirmation checks, not case suites.
- The literal pytest source: `tests/backend/cases/*.json` entries, fixture-scenario wiring, Playwright selectors. This is milestone 09-11 (functional builds) implementation detail. This document specifies *what* each case asserts, not the harness code that asserts it.
- Performance/load cases. The **test-strategy doc** already excludes this category for a local app with a handful of accounts.

## References

- **test-strategy doc**: [010-test-strategy.md](010-test-strategy.md) — `STRAT-SILO-01..08` names the silos this document's sections instantiate. `STRAT-CASE-01..08` names the strategic rules: traceability, transition tables not spot checks, boundary values, named-regression permanence, enumeration completeness, determinism, silo-first authoring order, ownership leaks as a named regression class. Every case below follows at least one of these.
- **requirements doc**: [010-01-requirements.md](010-01-requirements.md) — every `REQ-*` id cited below. This is the source of truth a case's expected outcome is checked against.
- **api doc**: [010-api.md](010-api.md) — the endpoint/hook/named-endpoint catalog the Backend API silo's cases are organized around.
- **workflows doc**: [010-workflows.md](010-workflows.md) — Workflow 5 (lead lifecycle) and 7 (apply-outcome propagation), the transition tables `TC-API-012/013/025` enumerate in full rather than spot-checking.
- **data model**: [010-data-model.md](010-data-model.md) — entity/constraint definitions the Data model silo's cases assert against directly.
- **user-interface doc**: [010-user-interface.md](010-user-interface.md) — the page inventory the Frontend silo's cases are organized around, one case group per page.
- **prototype extraction**: [010-prototype.md](010-prototype.md) — the named `jobsearch` defects, `updateOpenExpired()`'s unconditional overwrite, end-of-run-only persistence, salary-percentile scoring, that `TC-API-018`, `TC-AUTO-003`, and `TC-AUTO-008` are permanent regression cases against (`STRAT-CASE-04`).
- **architecture doc**: [010-architecture.md](010-architecture.md) — `ARCH-TEST-*` tier mechanics the REQ-DEV-* infrastructure requirements are satisfied against.

Case ids carry a `TC-<silo>-NNN` scheme (`DB`/`API`/`AUTO`/`FE`/`E2E`/`AUTH`), matching the six silos below.

## Traceability note

Every functional `REQ-*` (`REQ-SRCH-*`, `REQ-CRM-*`, `REQ-APPLY-*`, `REQ-PLAT-01..03`, `REQ-FE-02`, `REQ-AUTH-*`) has at least one case below tagged with its id, satisfying `STRAT-CASE-01`. Three groups are the deliberate exception, each satisfied collectively rather than by a single tagged row. `REQ-DEV-01..06` describe the test *infrastructure itself*, a documented local setup, seed data availability, the test protocols existing, rather than product behavior. These are satisfied by this document, the **architecture doc**'s `ARCH-TEST-*` tiers, and the seed dataset existing and being used to run every case below. `REQ-FE-01`, the screen inventory covering track config, post browsing, lead management, apply-queue review, and session status, is satisfied by `TC-FE-001..019` as a set, one page-group per inventory item, not by any single row. `REQ-PLAT-04`, "runs entirely on the user's local machine," is a topology assertion verified by inspection: the absence of a cloud SDK, cloud credential file, or non-loopback bind (`ARCH-NET-01`), and outbound destinations limited to MCF and the Google sign-in flow (`ARCH-NET-03`). This is the same category as `REQ-DEV-*`, not a behavior a functional case exercises. The live tier (`ARCH-TEST-06`, `REQ-DEV-05`, `REQ-DEV-06`) is out of scope for the same reason the **test-strategy doc** gives it no case-authoring guidance. It's a human-gated confirmation check, never a functional-correctness tool, and no case in this document may require it to pass.

## 1. Data model / DB silo

Direct against `scripts/db_util.py` and a temp SQLite database (`STRAT-SILO-01`), no Flask process, no browser. This is the fastest signal. It validates schema, constraints, and dedup identity before any service or route exists on top of them.

| id        | requirement(s)           | title                                                         |
| --------- | ------------------------ | ------------------------------------------------------------- |
| TC-DB-001 | ARCH-STO-02              | Schema applies cleanly from schema.sql                        |
| TC-DB-002 | REQ-PLAT-02              | Round-trip insert/get for catalog tables                      |
| TC-DB-003 | REQ-SRCH-05, REQ-SRCH-08 | Round-trip insert/get for FK-heavy tables                     |
| TC-DB-004 | REQ-CRM-01               | UNIQUE constraint on lead (user_id, post_id)                  |
| TC-DB-005 | ARCH-STO-07              | FK violation rejected                                         |
| TC-DB-006 | ARCH-RUN-03              | run_log partial UNIQUE index blocks a user's same-type runs   |
| TC-DB-007 | REQ-APPLY-02             | cv delete blocked while referenced                            |
| TC-DB-008 | REQ-SRCH-05              | post.id dedup scheme                                          |
| TC-DB-009 | ARCH-STO-03              | Stale schema_version refuses to start                         |
| TC-DB-010 | REQ-CRM-02, REQ-CRM-10   | stage, close reason, and offer constraints                    |
| TC-DB-011 | REQ-AUTH-01, 04, 06, 09  | account, session, ownership constraints                       |

- **TC-DB-001** — `scripts/initdb.py` against a fresh temp file creates every table in the **data model** with no error. The meta `schema_version` row is set.
- **TC-DB-002** — `db_util.py insert`/`get` on `role`, `track`, `search_profile`, `cv` each return the row unchanged. A follow-up `update`/`delete` round-trips too.
- **TC-DB-003** — `post`, `post_track`, `lead`, `application` each round-trip through `db_util.py`, including their FK columns (`track_id`, `post_id`, `lead_id`, `cv_id`, `run_id`) resolving to real parent rows.
- **TC-DB-004** — A second `INSERT` into `lead` with a `user_id` and `post_id` pair already present in another `lead` row fails the `UNIQUE` constraint, while a `lead` for the same post under a different user is accepted. This is what backs the `409` of a second promotion by one user, per the **api doc**'s `lead` resource entry.
- **TC-DB-005** — Inserting a `lead` row with a `track_id` that doesn't exist in `track` fails the FK constraint, `PRAGMA foreign_keys = ON` is active on the connection, rather than silently succeeding.
- **TC-DB-006** — Two `INSERT`s of `run_log(run_type='search', status='running')` for the same `user_id` in the same database: the second fails `ux_run_log_running`'s constraint even without an application-level pre-check, while a `running` search row for a different user is accepted. This is the regression `ISS-03` named.
- **TC-DB-007** — `DELETE FROM cv WHERE id=?` for a `cv.id` still referenced by `track.default_cv_id` or `application.cv_id` fails the FK constraint, backing the **api doc**'s `cv` `409`-translation rule.
- **TC-DB-008** — Two `post` rows built from the same `source`+`posting_reference`+`posted_date` collapse to the same primary key value. A raw duplicate insert is rejected by the database. Search-service upsert behavior belongs to the later jobs-pipeline milestone.
- **TC-DB-009** — Pointing the backend at a temp database whose `meta.schema_version` doesn't match the code's expected version fails startup with the explicit `"database is version N, code expects M"` message, not a downstream `no such column` error.
- **TC-DB-010** — Direct inserts show the schema constraints: `PROSPECT` is rejected in `lead.stage`, `lead_event.stage_from`, and `lead_event.stage_to`, `dropped` is accepted in `lead.close_reason`, a second `open` `offer` for one lead is rejected by the partial unique index, and an `offer` with `amount_sgd <= 0` or an unknown `status` is rejected.
- **TC-DB-011** — Direct inserts show the account and ownership constraints. A `user` with an email that differs only in letter case from an existing one is rejected, a `user` with neither a `password_hash` nor a `google_sub` is rejected, and a second `user` with the same `google_sub` is rejected. An `auth_session` with a duplicate `token_hash` is rejected, and deleting a `user` cascades to its `auth_session` rows. A second `mcf_session` row for one `user_id` is rejected, and a `cv` label that repeats within one user is rejected while the same label under another user is accepted. A `lead` whose `user_id` differs from the owner of its `track_id` is rejected by the ownership trigger.

## 2. Backend API silo

Flask's test client against a seeded temp database (`ARCH-TEST-03`, `STRAT-SILO-03`) exercises every generic CRUD shape's validation checklist, plus the hook-backed and named-endpoint behavior the **api doc** specifies. This is the fast loop. A backend change is re-verified here before anything slower runs.

| id         | requirement(s)             | title                                                      |
| ---------- | -------------------------- | ---------------------------------------------------------- |
| TC-API-001 | REQ-PLAT-01                | Generic CRUD happy path                                    |
| TC-API-002 | REQ-PLAT-01                | Generic CRUD validation errors                             |
| TC-API-003 | REQ-PLAT-01                | Generic CRUD not-found errors                              |
| TC-API-004 | REQ-SRCH-10                | Track archive/unarchive                                    |
| TC-API-005 | REQ-APPLY-02               | cv delete-while-referenced 409                             |
| TC-API-006 | REQ-SRCH-06                | post read-only surface                                     |
| TC-API-007 | REQ-SRCH-07                | API-EP-01 manual post entry                                |
| TC-API-008 | REQ-SRCH-07                | Manual post promotes unconditionally, same as search       |
| TC-API-009 | REQ-SRCH-08                | post_track/match_score: exactly one pairing per post       |
| TC-API-010 | REQ-CRM-01                 | lead create (system promote at TOAPPLY)                    |
| TC-API-011 | REQ-CRM-01                 | lead create rejects a second promotion of one post         |
| TC-API-012 | REQ-CRM-02                 | lead legal stage transitions accepted                      |
| TC-API-013 | REQ-CRM-02                 | lead illegal stage transitions rejected                    |
| TC-API-014 | REQ-CRM-02                 | lead close requires close_reason                           |
| TC-API-015 | REQ-CRM-08                 | Every lead write appends a lead_event                      |
| TC-API-016 | REQ-CRM-03, REQ-CRM-04     | lead free fields unrestricted                              |
| TC-API-017 | REQ-CRM-05                 | Auto-expiry boundary — 27 vs 29 days                       |
| TC-API-018 | REQ-CRM-05                 | Auto-expiry never overwrites an advanced/closed lead       |
| TC-API-019 | REQ-CRM-05                 | Auto-expiry evaluated on every read                        |
| TC-API-020 | REQ-CRM-06                 | lead delete not exposed                                    |
| TC-API-021 | REQ-CRM-08                 | lead_event read-only                                       |
| TC-API-022 | REQ-APPLY-01, REQ-CRM-11   | POST /lead/batch moves TOAPPLY leads to APPLIED atomically |
| TC-API-023 | REQ-APPLY-11, REQ-CRM-11   | POST /lead/batch drop closes leads as dropped              |
| TC-API-024 | REQ-APPLY-01               | application write surface is restricted                    |
| TC-API-025 | REQ-APPLY-09, REQ-APPLY-10 | Apply-outcome → lead propagation, all eight codes          |
| TC-API-026 | REQ-APPLY-08               | One application failure never overwrites another           |
| TC-API-027 | REQ-APPLY-08               | Retry is a new row, not an overwrite                       |
| TC-API-028 | REQ-PLAT-03                | run_log read-only surface                                  |
| TC-API-029 | REQ-SRCH-02                | API-EP-04 search run trigger                               |
| TC-API-030 | REQ-APPLY-03               | API-EP-05 apply run trigger                                |
| TC-API-031 | ARCH-RUN-03                | Run-in-flight guard returns 409                            |
| TC-API-032 | REQ-PLAT-03                | run_log diagnosable without re-running                     |
| TC-API-033 | REQ-APPLY-06               | session read-only, write blocked                           |
| TC-API-034 | REQ-APPLY-06               | API-EP-06 session upload validates domain                  |
| TC-API-035 | ARCH-TEST-04               | API-EP-07 health check                                     |
| TC-API-036 | REQ-PLAT-02                | SQLite is the only store                                   |
| TC-API-037 | REQ-CRM-10                 | offer create gates the OFFER stage                         |
| TC-API-038 | REQ-CRM-10                 | offer status closes the lead, offers are never deleted     |
| TC-API-039 | REQ-CRM-10                 | re-open of a lead closed from an offer                     |
| TC-API-040 | REQ-CRM-09                 | expected_salary_sgd copy at creation and edit              |
| TC-API-041 | REQ-CRM-01, REQ-CRM-11     | manual lead add at APPLIED                                 |
| TC-API-042 | REQ-CRM-12                 | lead re-assigns to another active track                    |

- **TC-API-001** — For each pure-generic table (`role`, `search_profile`, `search_schedule`, `cv`): `POST` creates (`201`), `GET` reads it back unchanged, `PUT` updates, `GET /search` lists/filters it, `DELETE` removes it, `POST /batch` creates/updates several rows in one call. This is the `STRAT-SILO-04` checklist's happy-path leg, run once per table. `track`'s create hook (`API-EP-01`'s classification note) and `post_track`/`match_score`'s internal-only write path are each covered by their own case instead.
- **TC-API-002** — Omitting a required field on `POST`/`PUT` for any pure-generic table returns `400` naming the missing field. A malformed type or date-format value returns `400` naming the offending field, per `mcfpipe`'s validation checklist (`easymcf-backend-api` skill).
- **TC-API-003** — `GET/PUT/DELETE` on a nonexistent row id returns `404` with a descriptive message. Any of the seven generic shapes against an unrecognized `{table}` name returns `404` naming the unknown table, not a `500`.
- **TC-API-004** — `PUT /api/v1/track/{id} {"is_active": false}` succeeds as a plain generic write. The track's historical `post_track`/`lead`/`application` rows stay readable, and `is_active=true` un-archives it the same way.
- **TC-API-005** — `DELETE /api/v1/cv/{id}` for a label referenced by `track.default_cv_id` or `application.cv_id` returns `409` naming the referencing rows, per the **api doc**'s `cv` entry, not a bare SQL error.
- **TC-API-006** — `GET`/`search /api/v1/post` work normally including `is_open`/`closing_date`/`applicants`/etc. `PUT`/`DELETE /api/v1/post/{id}` and a bare `POST /api/v1/post` are all rejected. Only `API-EP-01` may create one.
- **TC-API-007** — `POST /api/v1/posts/manual` with `track_id` plus position/company/url/salary/date creates the `post` (`src_method='manual'`) and the named track's one `post_track`/`match_score` row pair (`search_match=false`, `match_score=1.0`, `score_method='manual_v1'`) in the same request, returning the post, its pairing, and the new lead's id.
- **TC-API-008** — A manually-entered post is promoted to a lead under the one track named on the request, unconditionally, exactly as a search-discovered post is (`REQ-SRCH-09`) — neither this release's fixed score nor the still-present `min_match_score` field gates promotion.
- **TC-API-009** — A single `post` carries exactly one `post_track` row and its one paired `match_score` row, to whichever track found it or was named on its manual entry; neither is reachable through a client-facing generic endpoint of its own (`POST`/`PUT /api/v1/post_track`, `/api/v1/match_score`), only through the joined `post` read.
- **TC-API-010** — `POST /api/v1/lead {post_id, track_id}` creates the row with `status='OPEN'`, `stage='TOAPPLY'`, `created_at`/`updated_at` set, `expected_salary_sgd` copied from the track's profile, and one `stage_change` `lead_event` from `NULL` to `TOAPPLY`. This is the **api doc**'s `lead` create path, called by the search process.
- **TC-API-011** — A second `POST /api/v1/lead` for a `post_id` that already has a `lead` row returns `409` naming the existing `lead_id`. This drives the Posts screen's `already a lead` state.
- **TC-API-012** — Every edge in the **workflows doc**'s Workflow 5 state diagram (`TOAPPLY→APPLIED→CALLBACK→INTERVIEW`, and each stage's path to `CLOSED`) is accepted by `PUT /api/v1/lead/{id}`, except `INTERVIEW→OFFER` and the `CLOSED` of a lead at `OFFER`, which only `TC-API-037` and `TC-API-038` cover, and `CLOSED→INTERVIEW` for a lead closed from `OFFER` (`TC-API-039`).
- **TC-API-013** — A `PUT` attempting a transition not on Workflow 5's diagram, for example `TOAPPLY` straight to `OFFER`, returns `409`, never silently applied.
- **TC-API-014** — `PUT` setting `stage='CLOSED'` without a `close_reason` returns `400`. Supplying one of the eight valid reasons succeeds. A ninth/invalid value returns `400`.
- **TC-API-015** — A `notes` edit, a `deadline` change, a `last_contact_date` update, and a `stage` change each append exactly one `lead_event` row of the matching `event_type` and refresh `lead.updated_at` from it. This is REQ-CRM-08's single write path. No field bypasses it.
- **TC-API-016** — `notes`, `deadline`, `position_title`, `company_name`, `url_ref`, `applied_date`, `first_attempt_date`, `last_contact_date` all accept a plain write with no transition-legality check, and the underlying `post` row is never mutated by a `title_override`/`company_override` write.
- **TC-API-017** — A `lead` at `CALLBACK` or later whose latest `lead_event` is 27 days old stays `OPEN` on the next `GET`. One at 29 days has passed its rolling `deadline` and is closed (`stage='CLOSED'`, `close_reason='expired'`) on read, using the injectable clock (`ARCH-STO-05`), not a live sleep.
- **TC-API-018** — The named `jobsearch` regression this release must not repeat: a `lead` already at `APPLIED`/`INTERVIEW`/`OFFER`/`CLOSED` is untouched by the expiry check even when its `deadline` has passed. Expiry keys off `updated_at` alone, never `deadline`, and never touches a lead with recent activity (`STRAT-CASE-02`).
- **TC-API-019** — Two consecutive `GET /api/v1/lead/search` calls against a lead that crosses the 28-day threshold between them: the first call still shows it `OPEN`, the second shows it `CLOSED`, with no background job or scheduler involved.
- **TC-API-020** — `DELETE /api/v1/lead/{id}` is rejected. The only way to remove a lead from the active pipeline is `PUT stage='CLOSED'`, which preserves its history.
- **TC-API-021** — `GET/search /api/v1/lead_event` returns the log for a given `lead_id`. `POST`/`PUT`/`DELETE /api/v1/lead_event` are all rejected. Every row must come from a `lead` write's internal side effect.
- **TC-API-022** — `POST /api/v1/lead/batch {rows: [...]}` with two `TOAPPLY` leads and `stage: "APPLIED"` returns `200` with the leads at `APPLIED` in row order, each with its own `lead_event`. A batch that holds one illegal row returns `409` naming that `lead_id` and changes no lead. An empty list, a repeated `id`, more than 200 rows, or an extra key returns `400` with `field: rows`.
- **TC-API-023** — `POST /api/v1/lead/batch` with `stage: "CLOSED"` and `close_reason: "dropped"` closes each `TOAPPLY` lead with `dropped`, and a dropped lead is not eligible for the next apply run.
- **TC-API-024** — A bare `POST`/`PUT`/`DELETE /api/v1/application` is rejected. The only writer is the internal apply-run write path, one row per attempt.
- **TC-API-025** — For each of REQ-APPLY-04's eight outcome codes, this asserts the lead-side effect the **workflows doc**'s Workflow 7 specifies: `applied`→`APPLIED`; `post_closed`/`post_unavailable`→`CLOSED`/`apply_failed`; the remaining five (`questionnaire_required`, `cv_selector_error`, `unable_to_apply`, `cv_not_found`, `invalid_input`) leave the lead at `TOAPPLY`.
- **TC-API-026** — Two applications in the same batch, one failing and one succeeding: the failing one's outcome doesn't block or overwrite the succeeding one's recorded status, and both rows persist independently.
- **TC-API-027** — A lead that failed with `cv_not_found`, gets its CV fixed, and is attempted again in the next run ends up with two `application` rows for the one lead, both readable. This is the retry history REQ-APPLY-08 requires.
- **TC-API-028** — `GET/search /api/v1/run_log` returns rows including `outcome_counts`/`error_detail`. `PUT`/`POST`/`DELETE /api/v1/run_log` are all rejected. Only `API-EP-04`/`05` and the background thread write it.
- **TC-API-029** — `POST /api/v1/runs/search {track_id}` creates a `run_log(run_type='search', status='running')` row, starts the background thread, and returns the new `run_log.id` immediately, not blocking on the sweep.
- **TC-API-030** — `POST /api/v1/runs/apply` with no body creates a `run_log(run_type='apply', status='running')` row and starts the apply thread over every open lead at `TOAPPLY`.
- **TC-API-031** — Triggering `API-EP-04` a second time while a `search` run is still `running` returns `409` with the in-flight `run_log.id`, without racing the atomic index. This complements `TC-DB-006` at the HTTP layer.
- **TC-API-032** — A completed run's `run_log` row carries `outcome_counts` and, on partial/failed status, a populated `error_detail` sufficient to explain the outcome without re-triggering the run.
- **TC-API-033** — `GET /api/v1/session/1` returns the singleton row. `PUT`/`POST /api/v1/session` are rejected. Only `API-EP-06` may change `status`.
- **TC-API-034** — `POST /api/v1/session/upload` with a cookie payload containing a `mycareersfuture.gov.sg` cookie sets `status='valid'`. A payload with no matching-domain cookie returns `400` and leaves the session untouched.
- **TC-API-035** — `GET /api/v1/health` returns `200 {"status": "ok"}` once the app is ready to serve. This is the signal the mock-e2e harness's readiness poll depends on.
- **TC-API-036** — A search run, a lead promotion, and an apply run each leave a fully-reconstructable trail in `data/easymcf.db` alone. No parallel config file or external store holds state the database doesn't.
- **TC-API-037** — `POST /api/v1/offer {lead_id, offer_date, amount_sgd}` on an `INTERVIEW` lead returns `201`, inserts an `open` offer, moves the lead to `OFFER` with a `stage_change` event, and sets `lead.deadline` to the offer deadline. The same request for a lead at any other stage or a `CLOSED` lead returns `409`. `PUT /api/v1/lead/{id}` with `stage: "OFFER"` returns `409`, and so does `stage: "CLOSED"` on a lead at `OFFER`.
- **TC-API-038** — `PUT /api/v1/offer/{id}` with each of `accepted`, `rejected`, `withdrawn`, and `expired` closes the lead with `offer_accepted`, `rejected`, `withdrawn`, and `expired` in the same transaction. An `open` offer's `amount_sgd` and `deadline` are editable, a final offer rejects any write with `409`, and `DELETE /api/v1/offer/{id}` is not routed. With the clock past the offer deadline, a `GET /api/v1/lead/search` closes the lead as `expired` and sets its offer to `expired`.
- **TC-API-039** — `PUT /api/v1/lead/{id}` with `stage: "INTERVIEW"` on a lead closed from `OFFER` reopens it (`status='OPEN'`, `close_reason` cleared, event `CLOSED → INTERVIEW`), the earlier offer keeps its final status, and a new `POST /api/v1/offer` moves the lead to `OFFER` again. The same request on a lead closed from any other stage returns `409`.
- **TC-API-040** — A new lead carries the `min_salary` of its track's profile in `expected_salary_sgd` (`NULL` when the profile has none), a later change to the profile leaves it alone, and `PUT /api/v1/lead/{id}` edits it (an integer `>= 0` or `null`, `400` with `field` otherwise).
- **TC-API-041** — `POST /api/v1/lead/manual` creates a `post` copy and a lead at `APPLIED` with `applied_date` set to the creation date and one event from `NULL` to `APPLIED`.
- **TC-API-042** — `PUT /api/v1/lead/{id}` with `track_id` of another active track returns `200`, writes one `field_edited` event (`track_id: 1 -> 3`) that holds the lead's stage, and leaves the stage, deadline, and `expected_salary_sgd` as they were. An unknown or archived track returns `400` with `field: track_id` and changes nothing, and a `POST /api/v1/lead/batch` row that carries `track_id` returns `400`.

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
- **TC-AUTO-006** — A scored post's `match_score.match_score` matches the title-keyword formula's output for that title/track pair, and `score_method='title_keyword_v1'` is recorded alongside it.
- **TC-AUTO-007** — A post older than a track's `max_age_weeks`, or scored below its `min_match_score`, is excluded from that track's screened view. A manually-entered post with the same low score is not excluded, per `REQ-SRCH-07`'s bypass.
- **TC-AUTO-008** — The named deprecated-feature regression: no code path in the scoring service references a salary-percentile or industry-classification component. The score is a pure function of title-keyword match (`STRAT-CASE-04`).
- **TC-AUTO-009** — The apply-service fixture scenario where the button click and final submit both succeed yields `status='applied'`, including the "already applied" page-text variant of the same outcome.
- **TC-AUTO-010** — The fixture scenario where the final review-submit fails, assumed multi-step questionnaire, yields `status='questionnaire_required'`. The run does not attempt to complete it or abort, REQ-APPLY-05's explicit non-goal, and moves on to the next queued application.
- **TC-AUTO-011** — The fixture scenario with a broken/unexpected resume-selector DOM yields `status='cv_selector_error'`, distinct from a genuine no-match.
- **TC-AUTO-012** — The fixture scenario where the apply button never resolves exhausts all configured retries and yields `status='unable_to_apply'`.
- **TC-AUTO-013** — The fixture scenario where the posting URL fails to load yields `status='post_unavailable'` without attempting the button poll at all.
- **TC-AUTO-014** — The fixture scenario with resume cards present but none matching the configured CV substring yields `status='cv_not_found'`.
- **TC-AUTO-015** — The fixture scenario where the apply-error message text indicates the posting has closed yields `status='post_closed'`, distinct from `post_unavailable`.
- **TC-AUTO-016** — A `TOAPPLY` lead missing `jobid`/`url`/`cv_version` is rejected with `status='invalid_input'` before any browser action is attempted.
- **TC-AUTO-017** — The default 5-retry/5-second-delay policy is exercised against the `unable_to_apply` fixture in production timing once, and against a shortened `APPLY_POLL_RETRIES`/`_DELAY_S` override for routine test runs, proving the retry loop and its terminal state without spending real wall-clock seconds each run.
- **TC-AUTO-018** — The configured CV label matches the correct resume card by substring against the fixture's card titles, independent of card ordering. No match falls through to `cv_not_found` (`TC-AUTO-014`).

## 4. Frontend silo

Playwright drives the real AngularJS app served by a real `python -m easymcf` process, with every `/api/**` call intercepted and fulfilled from `tests/fixtures/api/*.json` (`ARCH-TEST-09`, `STRAT-SILO-07`). This isolates controller/template/rendering defects from whether the real backend produced the response correctly.

| id        | requirement(s)         | title                                                      |
| --------- | ---------------------- | ---------------------------------------------------------- |
| TC-FE-001 | REQ-SRCH-01            | Tracks — create/edit track and search profile              |
| TC-FE-002 | REQ-SRCH-10            | Tracks — archive toggle                                    |
| TC-FE-003 | REQ-APPLY-02           | CVs — add/rename/remove, blocked-delete message            |
| TC-FE-004 | REQ-SRCH-09            | Posts — results sorted by score, filters                   |
| TC-FE-005 | REQ-FE-02              | Posts — async search-run state                             |
| TC-FE-006 | REQ-CRM-01             | Posts — already-a-lead indicator, no promote action        |
| TC-FE-007 | REQ-SRCH-07            | Manual Post Entry — save, promoted by the system           |
| TC-FE-008 | REQ-CRM-02, REQ-CRM-11 | Leads — TOAPPLY queue, batch Apply and Drop                |
| TC-FE-009 | REQ-CRM-02, REQ-CRM-11 | Leads — Applied rows and Callbacks/Interviews/Offers cards |
| TC-FE-010 | REQ-CRM-06             | Leads — Closed tab                                         |
| TC-FE-011 | REQ-CRM-05             | Leads — expiry warning indicator                           |
| TC-FE-012 | REQ-CRM-03, REQ-CRM-08 | Lead Detail — edit fields and activity history             |
| TC-FE-013 | REQ-CRM-06             | Lead Detail — close behind confirmation                    |
| TC-FE-014 | REQ-APPLY-01           | Applications — TOAPPLY list and CV override                |
| TC-FE-015 | REQ-APPLY-11           | Applications — drop behind confirmation                    |
| TC-FE-016 | REQ-APPLY-03           | Applications — run batch behind confirmation, async state  |
| TC-FE-017 | REQ-APPLY-04           | Applications — results view per-outcome actions            |
| TC-FE-018 | REQ-PLAT-03, REQ-FE-02 | Automation — Runs tab and Session tab                      |
| TC-FE-019 | REQ-FE-02              | Cross-cutting — error surfacing and empty states           |
| TC-FE-020 | REQ-CRM-10             | Offers — dialog, page history, and actions                 |
| TC-FE-021 | REQ-CRM-09             | Leads — expected salary display and edit                   |
| TC-FE-022 | REQ-CRM-12             | Lead Detail — re-assign the track                          |

- **TC-FE-001** — The Tracks screen's combined role+seniority+search-profile form (page 1) saves in one step and the new track appears in the list with its search-profile summary.
- **TC-FE-002** — Archiving a track drops it from the active list and from every track selector elsewhere, mocked responses for Posts/promote/apply-CV selectors. The archived-tracks toggle reveals it again.
- **TC-FE-003** — The CVs screen (page 2) adds and renames a label normally. Removing a label the mocked `/api` response marks as in-use surfaces the inline blocked-delete explanation instead of silently failing.
- **TC-FE-004** — The Posts results table (page 3) renders sorted by match score descending by default. Adjusting the score-threshold and "include below-threshold" filters re-renders the mocked result set accordingly.
- **TC-FE-005** — Clicking "Run search" switches the page into the running state, progress indicator, live counts, against a mocked polling sequence, and a completion toast summarizes the mocked terminal outcome.
- **TC-FE-006** — A post that already became a lead shows `already a lead`, and the Posts page offers no promote action for any row.
- **TC-FE-007** — Submitting the manual-entry dialog (page 4) returns to Posts with the new "manual"-tagged posting visible and already a lead, promoted by the system on save.
- **TC-FE-008** — The `TOAPPLY` tab (page 5) renders compact rows sorted by days remaining, with a checkbox per row. `Apply (n)` sends one batch that moves the checked leads to the `APPLIED` column, and `Drop (n)` asks for confirmation with the lead count and then closes them as `dropped`. A batch that holds one illegal lead changes nothing and keeps every row checked. Every one of these interactions is a UI/API round-trip, with no spreadsheet-editing or menu-script equivalent anywhere in the app (REQ-CRM-07).
- **TC-FE-009** — The `APPLIED` tab renders compact rows, and the Callbacks, Interviews, and Offers tabs render cards with the latest note and last contact date, sorted by last contact, from the same mocked `lead` list, filtered client-side by stage.
- **TC-FE-010** — The Closed tab lists `close_reason` per row and marks an auto-closed (`expired`/`apply_failed`) lead distinctly from a manually-closed one.
- **TC-FE-011** — A card/row's days-since-last-activity indicator shifts into its warning state as the mocked `lead_event` timestamp approaches the 28-day threshold, on every tab, not only the board.
- **TC-FE-012** — The Lead Detail panel (page 6) saves deadline, notes, title, company, and post URL edits, and its activity history renders the mocked `lead_event` list in reverse-chronological order interleaved with `application` attempts.
- **TC-FE-013** — The manual close action requires selecting one of the eight reasons and confirming via the shared confirm-modal before the mocked close request fires.
- **TC-FE-014** — The Applications screen (page 7) lists the `TOAPPLY` leads with the track-default CV pre-filled and an override control drawing on the mocked CV catalog.
- **TC-FE-015** — Dropping a lead from the queue requires confirmation, then removes it from the list and reflects the mocked lead-closed-as-dropped outcome.
- **TC-FE-016** — "Run apply batch" requires confirmation, since it mutates MCF-side state, then enters the async running state with mocked per-application progress counts.
- **TC-FE-017** — Post-run, each mocked outcome renders its Workflow-7 next action inline. `cv_not_found` gets "fix CV and retry," `post_closed` gets "lead auto-closed" with a link, `applied` gets "lead moved to Applied."
- **TC-FE-018** — The Runs tab (page 8) lists mocked `run_log` rows reverse-chronological with expandable error detail. The Session tab shows mocked status/upload-history and the upload dialog round-trips a mocked cookie payload.
- **TC-FE-019** — A mocked failed/partial run surfaces inline on its triggering page and in the Runs tab, never console-only. A mocked missing/expired session blocks the Applications run button specifically. Every list page's mocked-empty response renders its documented empty-state call to action.
- **TC-FE-020** — `Move to OFFER` on an `INTERVIEW` lead opens the offer dialog with today's date, the current lead, the lead's expected salary as the amount, and the lead's deadline. The Offers page (page 9) lists every offer including closed ones, filters by status, and its `Accept`, `Reject`, and `Withdrawn` buttons ask for confirmation and then show the final status. A lead at `OFFER` shows no close control, and a lead closed from an offer shows `Re-open`.
- **TC-FE-021** — The lead lists show `S$` expected salary, the Lead Detail field edits it, and a lead at `OFFER` shows its offer amount instead.
- **TC-FE-022** — The Lead Detail Track drop-down lists the active tracks only, saving a new choice updates the lead, and the Leads table shows the new track name.

## 5. Mock end-to-end tier

Playwright Chromium drives the real UI against the real Flask app against a seeded temp database, with MCF replaced at the network boundary (`ARCH-TEST-04`). Per `STRAT-02`, this tier is the **final confirmation step**, not the primary place a logic defect is found. Every case here exists to catch a wiring defect the silos above can't see, not to re-derive logic they already proved.

| id         | requirement(s) | title                                         |
| ---------- | -------------- | --------------------------------------------- |
| TC-E2E-001 | REQ-FE-02      | Search-run golden path through the real UI    |
| TC-E2E-002 | REQ-APPLY-03   | Apply-run golden path through the real UI     |
| TC-E2E-003 | REQ-APPLY-04   | All eight apply outcomes reachable end-to-end |
| TC-E2E-004 | REQ-CRM-01     | System promotion and manual add end-to-end    |
| TC-E2E-005 | REQ-APPLY-06   | Session establishment round-trip              |
| TC-E2E-006 | ARCH-TEST-07   | Full-suite regression smoke                   |

- **TC-E2E-001** — Trigger a search run from the real Posts screen against the fixture MCF corpus. The poll loop reaches `success` and results render with match scores. This confirms the backend-thread/frontend-poll wiring `STRAT-CASE-07` calls out as needing a mock-e2e case beyond the silos.
- **TC-E2E-002** — Queue a lead from Leads, run the apply batch from Applications against the fixture apply corpus, and confirm the results view renders the real per-application outcome.
- **TC-E2E-003** — Each of the eight `apply/{scenario}/` fixture directories is driven through the real Applications UI at least once, confirming the DOM-level result matches what `TC-AUTO-009..016` already proved at the service level.
- **TC-E2E-004** — A search run ends by promoting its qualifying posts, which appear on Leads at `TOAPPLY` and show `already a lead` on Posts. A second run over the same posts creates no second lead. A lead added through the manual form appears at `APPLIED`.
- **TC-E2E-005** — "Log in to MCF" opens an ordinary, non-Playwright-automated, browser context per `ARCH-NET-03`. Uploading a fixture-shaped cookie payload through the dialog updates the real session-status badge.
- **TC-E2E-006** — `python scripts/resetdb.py --seed && pytest` stays green from a clean reseed. This is the "anything, before reporting done" check every functional change is re-verified against.
</content>

## 6. Authentication and ownership silo

Accounts, sign-in, and per-user ownership (`STRAT-SILO-08`). Every case signs in through the real sign-in endpoint as a seeded account and never through a bypass. Google cases run against the stub identity provider. Two seeded users with distinct data exist in every database.

| id          | requirement(s)     | title                                                        |
| ----------- | ------------------ | ------------------------------------------------------------ |
| TC-AUTH-001 | REQ-AUTH-01, 03    | Sign up, sign in, sign out, and current user round trip      |
| TC-AUTH-002 | REQ-AUTH-02        | Password policy, each rule alone and both length boundaries  |
| TC-AUTH-003 | REQ-AUTH-03        | Uniform sign-in failure and the sign-in rate limit           |
| TC-AUTH-004 | REQ-AUTH-05, 09    | Session cookie flags, tampering, and lifetime boundary       |
| TC-AUTH-005 | REQ-AUTH-05        | Protected routes answer 401, public routes stay open         |
| TC-AUTH-006 | REQ-AUTH-04        | Google id token validation matrix                            |
| TC-AUTH-007 | REQ-AUTH-04        | Google account linking matrix                                |
| TC-AUTH-008 | REQ-AUTH-08        | Photo upload, replace, remove, and validation                |
| TC-AUTH-009 | REQ-AUTH-06        | Ownership matrix over every registered resource              |
| TC-AUTH-010 | REQ-AUTH-06        | Shared post visibility and read-only posts                   |
| TC-AUTH-011 | REQ-CRM-01, 03, 04 | Lead copies its post fields and edits change the lead only   |
| TC-AUTH-012 | REQ-AUTH-07        | Per-user runs, run guard, scheduler, and MCF session         |
| TC-AUTH-013 | REQ-AUTH-05, 08    | Route guard, redirect back, and the user section on each page |
| TC-AUTH-014 | REQ-AUTH-01, 02    | Sign in and sign up forms and the password rule checklist    |
| TC-AUTH-015 | REQ-AUTH-04, 08    | Google sign-in and photo persistence end to end              |
| TC-AUTH-016 | REQ-AUTH-06        | Two signed-in users see only their own data end to end       |
| TC-AUTH-017 | REQ-AUTH-09        | No password, token, or secret in the database, logs, or repo |

- **TC-AUTH-001** — Sign up with a valid body returns `201`, a user object with no hash field, and a session cookie. Sign out returns `204` and the same cookie then answers `401` on `auth/me`. Sign in returns `200` and a new cookie.
- **TC-AUTH-002** — A compliant 12 character password passes and the same password one character shorter fails with only `too_short`. A 128 character password passes and 129 fails with `too_long`. Removing each of the lowercase, uppercase, digit, and symbol classes in turn fails with exactly that code. A password containing the email local part fails `contains_identity`. A password failing three rules reports all three codes together.
- **TC-AUTH-003** — A wrong password, an unknown email, and a Google-only account all return the identical `401` status and body. Five failed attempts for one email inside the window return `401` and the sixth returns `429` with `Retry-After`, even with the correct password. The window is driven by the injectable clock.
- **TC-AUTH-004** — The cookie is HttpOnly and signed, and a tampered value answers `401`. A session one tick before `expires_at` is valid and one at `expires_at` is not. The database holds only a digest, so a cookie built from the stored value does not authenticate.
- **TC-AUTH-005** — With no cookie, every route in the resource registry and every named endpoint outside the public set answers `401`, and `health`, sign-up, sign-in, sign-out, `auth/config`, and the two Google routes answer without one. A `POST` whose `Origin` names another host answers `403`.
- **TC-AUTH-006** — Against the stub provider, a valid verified token signs in. A token signed by an unknown key, with another audience, with another issuer, already expired, with a mismatched nonce, or returned with a mismatched state redirects to sign-in with `google_invalid`, and a token whose email is not verified redirects with `google_email_unverified`. A cancelled consent redirects with `google_denied`. No case creates a user or a session.
- **TC-AUTH-007** — A new subject with a verified email and no matching account creates an account with a null password hash. A verified email matching a password account links to it without a second row, and both methods then work. An unverified email matching an account is refused with no link. A returning subject signs in to the same account.
- **TC-AUTH-008** — Upload stores a 256 by 256 PNG under the per-user path with owner-only permissions and outside the web root, replace deletes the previous file, and remove deletes the file and clears the reference. A file one byte over the limit answers `413`. An unsupported type, a file whose bytes are not an image, and a declared type that disagrees with the bytes answer `415`. Another user's photo address answers `404`.
- **TC-AUTH-009** — The matrix is generated from the resource registry. For every resource and every verb, user B acting on user A's row gets `404` or an empty list, creating a child of user A's row gets `404`, and a body carrying `user_id` gets `400`. A `db_util.py` read afterward shows user A's rows unchanged. A resource registered without an ownership declaration fails at import.
- **TC-AUTH-010** — A post matched to tracks of both users appears in each user's list, and a post matched only to user 2's track is absent from user 1's. `PUT`, `POST`, and `DELETE` on a post answer `404`. Manual entry of a posting whose id already exists and is invisible to the caller reuses the post and writes only the caller's pairs.
- **TC-AUTH-011** — Promoting a post writes a lead whose `position_title`, `company_name`, and `url_ref` equal the post's and whose `deadline` follows the initial deadline rule. Updating the post directly through `db_util.py` leaves the lead unchanged. Editing the lead's title, company, URL, and deadline returns `200`, writes the matching events, and leaves the post row and another user's lead on the same post unchanged. A `url_ref` that is not `http` or `https` answers `400`.
- **TC-AUTH-012** — Each user can hold one running search at the same time as the other. A second trigger by the same user answers `409`. A search run for user A writes no `post_track` or `match_score` row for user B's tracks. Two users with due schedules each fire, and a collision skips only that user's remaining schedules. An apply run reads only its user's queue and `mcf_session`, and one user's session upload leaves the other's row unchanged.
- **TC-AUTH-013** — A signed-out visit to each guarded route lands on `/signin?next=<path>` and returns to that path after sign-in. A `401` mid-session redirects the same way. The user section appears once on every signed-in page and never on the sign-in pages. The circle shows initials without a photo and the image with one. Log out returns to sign-in and the browser back button does not reopen a signed-in page.
- **TC-AUTH-014** — Submitting each form with invalid input shows the field error inline. The sign-up checklist marks each rule met or unmet as the user types and marks the rows named by a rejected password's `rules` array. The Continue with Google link shows only when `auth/config` reports it enabled.
- **TC-AUTH-015** — Through the real UI against the stub provider, a new Google identity lands on the requested page with its name and picture in the header, signing out and in again returns to the same account, and a matching email account links. A user who signs up, uploads a photo, signs out, and signs in sees the photo again.
- **TC-AUTH-016** — Two browser contexts signed in as different users each see only their own Tracks, Leads, and Applications, and the second context requesting the first user's lead or photo address gets the not found outcome.
- **TC-AUTH-017** — A scan of the database, every file in `.dev/logs/`, and the tracked files finds none of the test passwords, a captured session cookie, a stub id token, or the client secret. It reruns against the log of every live sign-in.
