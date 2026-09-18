# Easy MCF POC Local - Test Strategy

## Contents

- [Purpose](#purpose)
- [Out of scope](#out-of-scope)
- [References](#references)
- [Guiding principle](#guiding-principle)
- [Component silos](#component-silos) — `STRAT-SILO-01..07`
  - [Data model / db silo](#data-model--db-silo)
  - [Backend API silo](#backend-api-silo)
  - [Automation silo (scraping + apply)](#automation-silo-scraping--apply)
  - [Frontend silo](#frontend-silo)
- [Strategic decisions: what test cases get written](#strategic-decisions-what-test-cases-get-written) — `STRAT-CASE-*`
- [The agent's silo-aware build→test→debug loop](#the-agents-silo-aware-buildtestdebug-loop) — `STRAT-LOOP`

## Purpose

This document defines *how* release `010` is tested and validated. Milestone 03, the test-cases milestone, instantiates this strategy into concrete cases per requirement, and every functional milestone from 09 to 11 builds against it. It answers three questions.

01. which component is tested where
02. what tooling gives an agent fast pass/fail feedback without a human in the loop
03. what strategic decisions govern which test cases get written for a given requirement

It does not restate the tier mechanics the **architecture** doc already fixed as `ARCH-TEST-01..08`. It builds the component-silo layer on top of them and gives the reasoning a future test-case author needs.

Decisions carry a `STRAT-*` id, grouped as `SILO`, `CASE`, or `LOOP`, mirroring the `REQ-*`/`ARCH-*` convention in the **requirements** and **architecture** docs.

## Out of scope

- Restating `ARCH-TEST-01..08`'s tier mechanics, isolation strategy, pytest configuration, or fixture corpus layout. Read the **architecture** doc directly. This document only adds the silo layer and the case-selection reasoning on top.
- The concrete enumeration of test cases per requirement. That is milestone 03, the test-cases milestone, which this document is the direct input to.
- A JS unit-test tier such as Karma or Jasmine. `ARCH-TEST-05` already rejects this for `010`. The frontend silo proposed above, `STRAT-SILO-07`, is Playwright-based specifically so no node or npm build toolchain is introduced, per `ARCH-RUN-06`.
- Performance and load testing. `010` is a single local user, so this is not a meaningful category of risk for this release.

## References

- **requirements** [010-01-requirements.md](010-01-requirements.md): REQ-DEV-03..05 define the three test protocols this strategy operationalizes, backend-only, mock e2e, and live. Every `REQ-*` in the functional sections is what test cases, milestone 03, trace back to.
- **architecture** [010-architecture.md](010-architecture.md): `ARCH-TEST-01..08` already fix the tiering across backend, mock e2e, and live tiers, pytest as the single test runner, state isolation via a temp SQLite database per session, the fixture corpus layout, and the agent build→test→debug command table. This document does not re-decide any of that.
- **data model** [010-data-model.md](010-data-model.md): the entities the data-model silo below operates on: `user`, `role`, `track`, `search_profile`, `cv`, `post`, `post_track`, `match_score`, `lead`, `lead_note`, `lead_event`, `application`, `run_log`, `session`.
- **prototype extraction** [010-prototype.md](010-prototype.md): the named `jobsearch` defect this strategy requires a regression test against, `updateOpenExpired()`'s unconditional status overwrite.
- **deploy-and-validation-cycle skill** `.claude/skills/deploy-and-validation-cycle/SKILL.md`: the manual golden-path checklist this strategy's automated silos are meant to make redundant, tier by tier, as milestone 07 lands.
- **playwright skill** [playwright](../../../.claude/skills/playwright/SKILL.md): explicit-wait guidance for automation-silo and frontend-silo test cases.

## Guiding principle

**Test each component where its logic lives, in isolation, before testing how components fit together.** A bug in match-score arithmetic, a lead state-machine transition, or an apply-outcome mapping is a unit-level defect. It should be caught by a test that exercises only that unit, in milliseconds, without a browser, a second process, or another component's correctness as a precondition. Full-stack integration testing, `ARCH-TEST-04`'s mock e2e tier, exists to catch *wiring* defects such as a screen calling the wrong endpoint or a status code the frontend doesn't handle. Its job is to confirm integration once the component silos already prove the underlying logic correct. It is not meant to be the first or primary place a logic bug is discovered. Practically: **if a mock e2e test fails, the failure should almost always be about integration, because the component silos already proved the logic underneath it correct.**

This is what makes the loop closed for an AI agent. A component-silo test gives a narrow, fast, deterministic feedback signal, an exit code plus a traceback naming the failing function or field, that an agent can act on without waiting on a browser, without a human interpreting a screenshot, and without one component's bug masking another's. Save the slower, harder-to-diagnose full-stack tier for confirming integration once each piece is already independently proven, following REQ-DEV-03/04's ordering: backend-only first, mock e2e second, and live third and human-gated only.

**STRAT-01** Every component below has a dedicated silo: a way to exercise and validate its behavior directly, with no other component's correctness as a dependency, and no live network call. Where `ARCH-TEST-01..08` already fully specifies a silo's mechanics, this document points to it rather than re-deciding it. Where a gap exists, such as a frontend silo isolated from the real backend, this document proposes the addition.

**STRAT-02** Full end-to-end testing, mock e2e per `ARCH-TEST-04`, is the **final confirmation step**, run after the relevant silos pass. It is not the primary tool for discovering a functional defect. The live tier, `ARCH-TEST-06`, is narrower still: a human-gated markup-drift smoke check, never a functional-correctness tool and never part of an agent's autonomous loop.

## Component silos

### Data model / db silo

**STRAT-SILO-01** A CRUD utility, `scripts/db_util.py`, wraps `easymcf/db/connection.py` with `get`/`insert`/`update`/`delete`/`search` operations against any table, using the stdlib `sqlite3` driver. `010`'s store is SQLite per `ARCH-STO-01`, so no ODBC layer such as `pyodbc` exists to wrap. It is both a CLI, for example `python scripts/db_util.py lead insert '{"post_id": 1, "track_id": 1, ...}'`, for a human or agent to poke a database directly, and an importable module the backend silo's config-driven cases and the automation silo's fixtures both reuse. There is one CRUD implementation, shared across every caller.

This lets a schema or data-model change be validated **before** any service, API route, or UI exists on top of it. Apply the new `schema.sql`, point `db_util.py` at a temp database, reusing `ARCH-TEST-01`'s isolation pattern, and confirm a row round-trips through insert, get, and a match, and that a constraint holds, such as a rejected FK violation or a rejected `UNIQUE` violation on `post.id`. Feedback arrives in milliseconds, with the failing SQL error as the signal, and no Flask process involved.

**STRAT-SILO-02** The db utility is also the seam `tests/backend/` fixtures use to seed and assert against state directly, bypassing the API, when a test's subject is the API layer itself. For example, a test can assert that a `POST /api/v1/lead` call wrote the row the CRUD layer expects, without also trusting `GET /api/v1/lead/{id}` to read it back correctly. Reading and writing through two independent paths, the API and direct CRUD, is what catches a bug that lives in only one of them.

### Backend API silo

**STRAT-SILO-03** Endpoint test cases are expressed as data: `tests/backend/cases/*.json`, one file per table or feature area, each entry carrying `name`, `req_id` for traceability back to the **requirements** doc, `method`, `path`, `params`, `body`, `headers`, and an `expect` block with `status` and either a `body_contains` or a JSON-path value check. A single harness, `tests/backend/test_api_cases.py`, parametrizes pytest over every case in the directory. Adding a test case means editing JSON rather than writing a new Python function, which keeps the case count that milestone 03 produces from becoming a maintenance burden.

The harness executes cases against Flask's **test client**, per `ARCH-TEST-03`'s decision. This avoids a spawned process or a port, and gives tracebacks straight from the failing line, and it is what the automated tier-1 loop runs. The same case format is also replayable by `scripts/api_tester.py`, a thin swap of the test client for the `requests` library against an already-running `python -m easymcf` instance. This is useful when a developer or agent has the dev server up and wants to poke a single endpoint interactively, and it is the `requests`-based tool the CRM/apply/platform skills' "hit the affected endpoint directly" guidance in `deploy-and-validation-cycle` refers to. This interactive mode is a convenience rather than part of the automated closed loop. `pytest -m backend` via the test client is the automated closed loop.

**STRAT-SILO-04** Case coverage per endpoint shape follows `easymcf-backend-api`'s checklist.

01. a required-field `400` naming the field
02. a type or date-format validation `400`
03. a `404` for a missing record id
04. a `404` for an unknown table name
05. a happy-path `200` or `201` with the expected body shape

This is written once as a template of cases and instantiated per table. REQ-PLAT-01 calls for generic CRUD over bespoke endpoints, and this silo mirrors that with generic test cases instantiated per table instead of bespoke assertions written separately for each one.

### Automation silo (scraping + apply)

**STRAT-SILO-05** No new tooling is needed here. This silo is the concrete instantiation of what `ARCH-TEST-03` already scoped: service-layer tests in `tests/backend/` call `easymcf/services/search.py` and `apply.py` directly, with `easymcf/automation/fixture.py` supplying `MCFBrowser` per `ARCH-BOT-02`. No HTTP request, no Flask route, and no real browser chrome is involved in asserting scrape-parse-dedup-score correctness or an apply attempt's outcome mapping. Only once that logic is proven does a case belong in the mock e2e tier, where the *browser* driving real selectors against fixture HTML is what's under test, per `ARCH-TEST-04`.

**STRAT-SILO-06** Every one of REQ-APPLY-04's eight apply-status outcomes and REQ-SRCH-06's post-closed-during-detail-pass path must be reachable as a named fixture scenario at this silo level, meaning a service call plus fixture browser, and not only at the mock e2e tier. A service-level assertion such as `apply(application_id) → status == "cv_not_found"` is cheaper to write and faster to run than a DOM-level one. Mock e2e's job, per `ARCH-TEST-04`, is then only to confirm the same scenario is reachable by clicking through the real UI, rather than to re-derive the outcome logic.

### Frontend silo

**STRAT-SILO-07, proposed addition to `ARCH-TEST`'s repo layout, for architect confirmation alongside milestone 02/05.** `ARCH-TEST-05` defines one frontend-verification tier: full-stack Playwright DOM assertions against the real backend and database, with only MCF mocked. That is correct as the integration confirmation tier, but it is not a silo. A frontend defect there is indistinguishable at a glance from a backend defect. This document proposes a second, faster Playwright tier, `tests/frontend/`, that drives the same AngularJS app served by a real `python -m easymcf` process. JS and HTML still need an HTTP origin to load, but every `/api/**` call is intercepted via `page.route()` and fulfilled from `tests/fixtures/api/*.json` canned responses. This mirrors the MCF-interception pattern `ARCH-TEST-04` already established, applied to the app's own API boundary instead of MCF's.

This isolates controller, template, and rendering logic, such as a run's status badge reflecting `run_log.status`, an error banner appearing on a failed-run response, or a lead card's tab following its stage, from whether the real backend and database produced that response correctly. A frontend rendering bug and a backend logic bug now fail in different tiers instead of the same one. `ARCH-TEST-05`'s full-stack tier remains the integration confirmation once both silos pass.

## Strategic decisions: what test cases get written

**STRAT-CASE-01 Traceability.** Every `REQ-*` line item in `010-01-requirements.md` has at least one test case somewhere in the case config, whether `tests/backend/cases/*.json`, an automation fixture scenario, or a frontend fixture scenario, tagged with that requirement's id. Milestone 04, the test-cases milestone, is the enumeration of this mapping. A requirement with no `req_id` appearing anywhere in the case configs counts as an untested requirement rather than an implicit pass.

**STRAT-CASE-02 State machines get full transition tables.** The lead status/stage machine, REQ-CRM-02 and the glossary, and the apply-status vocabulary, REQ-APPLY-04, are the two places `010` has the most behavioral surface area. Test cases enumerate every valid transition reachable from every open stage to `CLOSED` with each close reason, per the REQ-CRM section's close-reason table. They also cover the specific regression this release must not repeat, from the **prototype extraction**'s `updateOpenExpired()`: a case asserting that a lead already at `APPLIED`, `INTERVIEW`, `OFFER`, or `CLOSED` is **not** overwritten by the auto-expiry sweep just because its `deadline` has passed. Expiry keys off `lead.updated_at` plus 28 days via the injectable clock, `ARCH-STO-05`. It never keys off `deadline`, and it never touches a lead with more recent activity than the threshold.

**STRAT-CASE-03 Every threshold gets boundary-value cases.** Every numeric or time threshold in the requirements gets a case on both sides of the boundary. Examples include REQ-CRM-05's 28-day expiry, where a lead at 27 days stale stays open and one at 29 days closes, a pair `ARCH-STO-05`'s seed-data guidance already names. REQ-SRCH-01's `max_age_weeks` and `min_match_score` screening cutoffs, and REQ-SRCH-03's pagination termination, where a search's last page returns zero cards, follow the same pattern.

**STRAT-CASE-04 Named prototype regressions become permanent regression cases.** Where the **prototype extraction** documents a `jobsearch` defect this release is explicitly correcting, a test case exists specifically to keep that defect from being reintroduced. Examples include the expiry overwrite above, salary-percentile scoring's removal per REQ-SRCH-09, and end-of-run-only persistence replaced by incremental persistence per REQ-SRCH-04, asserted by injecting a mid-sweep failure and checking that posts already found survived. The case's name and comment cite the requirement and the prototype behavior it supersedes, so a future change that regresses it fails loudly and legibly rather than silently.

**STRAT-CASE-05 Enumeration completeness for closed vocabularies.** REQ-APPLY-04's eight apply-status codes, the lead close-reason table, and `post.src_method`, `scraped` and `manual`, are closed enumerations. Every value needs a reachable case, per `STRAT-SILO-06`. Seed data, per `ARCH-STO-04`, is required to include at least one row per value so a case can assert against real seeded state rather than only a purpose-built fixture.

**STRAT-CASE-06 Determinism over realism where they conflict.** No test case may depend on wall-clock time, a live network call, or a `sleep()`-based wait. `ARCH-STO-05`'s `clock.py::now()` indirection is mandatory for anything expiry- or age-related, and the **playwright skill**'s explicit-wait guidance applies to every automation-silo and frontend-silo case. A test that passes only "usually" is a defect in the test, per `ARCH-TEST-08`.

**STRAT-CASE-07 Silo-first authoring order for new work.** When a functional milestone from 09 to 11 implements a requirement, its test cases are written in silo order, cheapest and most logic-proximate first: a data-model case for schema or constraints, then a backend-API or automation-silo case for service logic, then a frontend-silo case for rendering, and finally a mock e2e case, added only if the requirement has cross-component wiring worth confirming beyond what the silos already proved. REQ-FE-02's run-status polling is one such case, since it genuinely spans the backend run thread and the frontend poll loop. Not every requirement needs a mock e2e case. One is added only where silo coverage alone would leave a real integration risk unverified.

## The agent's silo-aware build→test→debug loop

This extends `ARCH-TEST-07`'s table with which silo to reach for **first**, before the broader tier it already specifies:

| id | change                          | narrowest signal                                          | then                                                    | 
| -- | -------------------------------- | ----------------------------------------------------------- | ----------------------------------------------------------- |
| 01 | schema / data model             | `scripts/db_util.py` CRUD round-trip against a temp db    | `python scripts/resetdb.py --seed && pytest -m backend` | 
| 02 | backend route / validation      | add/edit a case in `tests/backend/cases/*.json`           | run `pytest -m backend -k <case name>` then full tier   |
| 03 | search/apply/scoring logic      | service-level test against `automation/fixture.py`        | `pytest -m backend`                                     |
| 04 | frontend controller/template    | `tests/frontend/` case with mocked `/api`                 | `pytest -m e2e -k <screen>` then `pytest -m e2e`        |
| 05 | general                         | the silo(s) touched                                       | `pytest`                                                |

_why narrowest first_

01. a constraint or type error surfaces from SQL directly, at the source, instead of surfacing three layers up as a 400
02. one parametrized case fails with the exact `req_id` and field, no browser involved
03. the outcome/parse/score assertion is checked without a real browser's timing or selectors as a variable 
04. a rendering bug is isolated from whether the real backend behaved correctly
05. matches `ARCH-TEST-07`'s existing "anything, before reporting done" row
