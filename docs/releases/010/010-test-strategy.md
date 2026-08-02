# Easy MCF POC Local - Test Strategy

## Purpose

This document defines *how* release `010` is tested and validated — the strategy milestone 04 (test cases) instantiates into concrete cases per requirement, and every functional milestone (09–11) builds against. It answers three questions: which component is tested where, what tooling gives an agent fast pass/fail feedback without a human in the loop, and what strategic decisions govern which test cases get written for a given requirement. It does not restate the tier mechanics [010-architecture.md](010-architecture.md) already fixed (`ARCH-TEST-01..08`) — it builds the component-silo layer on top of them and gives the reasoning a future test-case author needs.

Decisions carry a `STRAT-*` id (grouped `SILO`/`CASE`/`LOOP`), mirroring the `REQ-*`/`ARCH-*` convention in [010-01-requirements.md](010-01-requirements.md) and [010-architecture.md](010-architecture.md).

## References

- [010-01-requirements.md](010-01-requirements.md) — REQ-DEV-03..05 define the three test protocols (backend-only, mock e2e, live) this strategy operationalizes; every `REQ-*` in the functional sections is what test cases (milestone 04) trace back to.
- [010-architecture.md](010-architecture.md) — `ARCH-TEST-01..08` already fix the tiering (backend / mock e2e / live), pytest as the single test runner, state isolation (temp SQLite per session), the fixture corpus layout, and the agent build→test→debug command table. This document does not re-decide any of that.
- [010-data-model.md](010-data-model.md) — entities (`role`, `track`, `search_profile`, `cv`, `post`, `post_track`, `lead`, `lead_event`, `application`, `run_log`, `session`) the data-model silo below operates on.
- [010-prototype.md](010-prototype.md) — the named `jobsearch` defect (`updateOpenExpired()`'s unconditional status overwrite) this strategy requires a regression test against.
- `.claude/skills/deploy-and-validation-cycle/SKILL.md` — the manual golden-path checklist this strategy's automated silos are meant to make redundant, tier by tier, as milestone 07 lands.

## Guiding principle

**Test each component where its logic lives, in isolation, before testing how components fit together.** A bug in match-score arithmetic, a lead state-machine transition, or an apply-outcome mapping is a unit-level defect — it should be caught by a test that exercises only that unit, in milliseconds, without a browser, a second process, or another component's correctness as a precondition. Full-stack integration testing (`ARCH-TEST-04`'s mock e2e tier) exists to catch *wiring* defects — a screen calling the wrong endpoint, a status code the frontend doesn't handle — not to be the first or primary place a logic bug is discovered. Practically: **if a mock e2e test fails, the failure should almost always be about integration, because the component silos already proved the logic underneath it correct.**

This is what makes the loop closed for an AI agent. A component-silo test gives a narrow, fast, deterministic feedback signal — exit code plus a traceback naming the failing function/field — that an agent can act on without waiting on a browser, without a human interpreting a screenshot, and without one component's bug masking another's. Save the slower, harder-to-diagnose full-stack tier for confirming integration once each piece is already independently proven, per REQ-DEV-03/04's ordering (backend-only first, mock e2e second, live third and human-gated only).

**STRAT-01** Every component below has a dedicated silo: a way to exercise and validate its behavior directly, with no other component's correctness as a dependency, and no live network call. Where `ARCH-TEST-01..08` already fully specifies a silo's mechanics, this document points to it rather than re-deciding it; where a gap exists (a frontend silo isolated from the real backend), this document proposes the addition.

**STRAT-02** Full end-to-end testing (mock e2e, `ARCH-TEST-04`) is the **final confirmation step**, run after the relevant silos pass, not the primary tool for discovering a functional defect. The live tier (`ARCH-TEST-06`) is narrower still: a human-gated markup-drift smoke check, never a functional-correctness tool and never part of an agent's autonomous loop.

## Component silos

### Data model / db silo

**STRAT-SILO-01** A CRUD utility, `scripts/db_util.py`, wraps `easymcf/db/connection.py` with `get`/`insert`/`update`/`delete`/`search` operations against any table, using the stdlib `sqlite3` driver (not `pyodbc` — `010`'s store is SQLite per `ARCH-STO-01`, so no ODBC layer exists to wrap). It is both a CLI (`python scripts/db_util.py lead insert '{"post_id": 1, "track_id": 1, ...}'`) for a human or agent to poke a database directly, and an importable module the backend silo's config-driven cases and the automation silo's fixtures both reuse — one CRUD implementation, not one per caller.

This lets a schema or data-model change be validated **before** any service, API route, or UI exists on top of it: apply the new `schema.sql`, point `db_util.py` at a temp database (`ARCH-TEST-01`'s isolation pattern, reused here), and confirm a row round-trips (insert → get → matches) and a constraint holds (FK violation rejected, `UNIQUE` on `post.id` rejected) — feedback in milliseconds, with the failing SQL error as the signal, and no Flask process involved.

**STRAT-SILO-02** The db utility is also the seam `tests/backend/` fixtures use to seed and assert against state directly (bypassing the API) when a test's subject is the API layer itself — e.g. asserting a `POST /api/lead` call wrote the row the CRUD layer expects, without also trusting `GET /api/lead/{id}` to read it back correctly. Reading and writing through two independent paths (API vs. direct CRUD) is what catches a bug that lives in only one of them.

### Backend API silo

**STRAT-SILO-03** Endpoint test cases are **data, not code**: `tests/backend/cases/*.json`, one file per table or feature area, each entry carrying `name`, `req_id` (traceability back to `010-01-requirements.md`), `method`, `path`, `params`, `body`, `headers`, and an `expect` block (`status`, and either `body_contains` or a JSON-path value check). A single harness, `tests/backend/test_api_cases.py`, parametrizes pytest over every case in the directory — adding a test case is editing JSON, not writing a new Python function, which keeps the case count that milestone 04 produces from becoming a maintenance burden.

The harness executes cases against Flask's **test client** (`ARCH-TEST-03`'s decision — no spawned process, no port, tracebacks from the failing line), which is what the automated tier-1 loop runs. The same case format is also replayable by `scripts/api_tester.py`, a thin swap of the test client for the `requests` library against an already-running `python -m easymcf` instance — useful when a developer or agent has the dev server up and wants to poke a single endpoint interactively (this is the `requests`-based tool the CRM/apply/platform skills' "hit the affected endpoint directly" guidance in `deploy-and-validation-cycle` refers to) — but this interactive mode is a convenience, not part of the automated closed loop; `pytest -m backend` via the test client is.

**STRAT-SILO-04** Case coverage per endpoint shape, per `easymcf-backend-api`'s checklist: required-field `400` naming the field, type/date-format validation `400`, `404` for a missing record id, `404` for an unknown table name, and a happy-path `200`/`201` with the expected body shape. This is written once as a template of cases and instantiated per table, so REQ-PLAT-01's "generic CRUD, not bespoke endpoints" is mirrored by "generic test cases, not bespoke assertions per table."

### Automation silo (scraping + apply)

**STRAT-SILO-05** No new tooling here — this silo is the concrete instantiation of what `ARCH-TEST-03` already scoped: service-layer tests (`tests/backend/`) call `easymcf/services/search.py` / `apply.py` directly, with `easymcf/automation/fixture.py` supplying `MCFBrowser` (`ARCH-BOT-02`). No HTTP request, no Flask route, no real browser chrome is involved in asserting scrape-parse-dedup-score correctness or an apply attempt's outcome mapping — only once that logic is proven does a case belong in the mock e2e tier, where the *browser* driving real selectors against fixture HTML is what's under test (`ARCH-TEST-04`).

**STRAT-SILO-06** Every one of REQ-APPLY-04's eight apply-status outcomes and REQ-SRCH-06's post-closed-during-detail-pass path must be reachable as a named fixture scenario at **this** silo level (service call + fixture browser), not only at the mock e2e tier — a service-level assertion (`apply(application_id) → status == "cv_not_found"`) is cheaper to write and faster to run than a DOM-level one, and mock e2e's job (`ARCH-TEST-04`) is then only to confirm the same scenario is reachable by clicking through the real UI, not to re-derive the outcome logic.

### Frontend silo

**STRAT-SILO-07 (proposed addition to `ARCH-TEST`'s repo layout, for architect confirmation alongside milestone 02/05).** `ARCH-TEST-05` defines one frontend-verification tier: full-stack Playwright DOM assertions against the real backend and database (mock MCF only). That is correct as the integration confirmation tier but is not a silo — a frontend defect there is indistinguishable at a glance from a backend defect. This document proposes a second, faster Playwright tier, `tests/frontend/`, that drives the same AngularJS app served by a real `python -m easymcf` process (JS/HTML still need an HTTP origin to load) but with **every `/api/**` call intercepted via `page.route()`** and fulfilled from `tests/fixtures/api/*.json` canned responses — mirroring the MCF-interception pattern `ARCH-TEST-04` already established, applied to the app's own API boundary instead of MCF's.

This isolates controller/template/rendering logic (a run's status badge reflecting `run_log.status`, an error banner appearing on a failed-run response, a lead card's tab following its stage) from whether the real backend and database produced that response correctly — a frontend rendering bug and a backend logic bug now fail in different tiers instead of the same one. `ARCH-TEST-05`'s full-stack tier remains the integration confirmation once both silos pass.

## Strategic decisions: what test cases get written

**STRAT-CASE-01 Traceability.** Every `REQ-*` line item in `010-01-requirements.md` has at least one test case somewhere in the case config (`tests/backend/cases/*.json`, automation fixture scenarios, or frontend fixture scenarios) tagged with that requirement's id. Milestone 04 (test cases) is the enumeration of this mapping; a requirement with no `req_id` appearing anywhere in the case configs is an untested requirement, not an implicit pass.

**STRAT-CASE-02 State machines get transition tables, not spot checks.** The lead status/stage machine (REQ-CRM-02, glossary) and the apply-status vocabulary (REQ-APPLY-04) are the two places `010` has the most behavioral surface area. Test cases enumerate: every valid transition reachable from every open stage to `CLOSED` with each close reason (REQ-CRM section's close-reason table), and — the specific regression this release must not repeat (`010-prototype.md`'s `updateOpenExpired()`) — a case asserting that a lead already at `APPLIED`/`INTERVIEW`/`OFFER`/`CLOSED` is **not** overwritten by the auto-expiry sweep just because its `deadline` has passed; expiry keys off `lead.updated_at` + 28 days via the injectable clock (`ARCH-STO-05`), never off `deadline`, and never touches a lead with more recent activity than the threshold.

**STRAT-CASE-03 Boundary values, not just typical values.** Every numeric or time threshold in the requirements gets a case on both sides of the boundary: REQ-CRM-05's 28-day expiry (a lead at 27 days stale stays open, one at 29 days closes — `ARCH-STO-05`'s seed-data guidance already names this pair), REQ-SRCH-01's `max_age_weeks`/`min_match_score` screening cutoffs, and REQ-SRCH-03's pagination termination (a search's last page returns zero cards).

**STRAT-CASE-04 Named prototype regressions become permanent regression cases.** Where `010-prototype.md` documents a `jobsearch` defect this release is explicitly correcting (the expiry overwrite above; salary-percentile scoring's removal per REQ-SRCH-09; end-of-run-only persistence replaced by incremental persistence per REQ-SRCH-04, asserted by injecting a mid-sweep failure and checking posts already found survived), a test case exists specifically to keep that defect from being reintroduced — the case's name and comment cite the requirement and the prototype behavior it supersedes, so a future change that regresses it fails loudly and legibly rather than silently.

**STRAT-CASE-05 Enumeration completeness for closed vocabularies.** REQ-APPLY-04's eight apply-status codes, the lead close-reason table, and `post.src_method` (`scraped`/`manual`) are closed enumerations — every value needs a reachable case (`STRAT-SILO-06`), and seed data (`ARCH-STO-04`) is required to include at least one row per value so a case can assert against real seeded state rather than only a purpose-built fixture.

**STRAT-CASE-06 Determinism over realism where they conflict.** No test case may depend on wall-clock time (`ARCH-STO-05`'s `clock.py::now()` indirection is mandatory for anything expiry- or age-related), a live network call, or a `sleep()`-based wait — the [selenium](../../../.claude/skills/selenium/SKILL.md) skill's explicit-wait guidance applies to every automation-silo and frontend-silo case. A test that passes only "usually" is a defect in the test, per `ARCH-TEST-08`.

**STRAT-CASE-07 Silo-first authoring order for new work.** When a functional milestone (09–11) implements a requirement, its test cases are written in silo order, cheapest and most logic-proximate first: data-model case (schema/constraint) → backend-API or automation-silo case (service logic) → frontend-silo case (rendering) → mock e2e case only if the requirement has cross-component wiring worth confirming beyond what the silos already proved (e.g. REQ-FE-02's run-status polling, which genuinely spans backend run thread + frontend poll loop). Not every requirement needs a mock e2e case — one is added only where silo coverage alone would leave a real integration risk unverified.

## The agent's silo-aware build→test→debug loop

This extends `ARCH-TEST-07`'s table with which silo to reach for **first**, before the broader tier it already specifies:

| change | first, narrowest signal | then | why narrowest-first |
| ------ | ------------------------ | ---- | -------------------- |
| schema / data model | `scripts/db_util.py` CRUD round-trip against a temp db | `python scripts/resetdb.py --seed && pytest -m backend` | a constraint or type error surfaces from SQL directly, not from a 400 three layers up |
| backend route / validation | add/edit a case in `tests/backend/cases/*.json`, run `pytest -m backend -k <case name>` | `pytest -m backend` (full tier) | one parametrized case fails with the exact `req_id` and field, no browser involved |
| search/apply/scoring logic | service-level test against `automation/fixture.py` (`STRAT-SILO-05`) | `pytest -m backend` | the outcome/parse/score assertion is checked without a real browser's timing or selectors as a variable |
| frontend controller/template | `tests/frontend/` case with mocked `/api` (`STRAT-SILO-07`) | `pytest -m e2e -k <screen>` then `pytest -m e2e` | a rendering bug is isolated from whether the real backend behaved correctly |
| anything, before reporting done | the silo(s) touched | `pytest` (tiers 1+2, excludes live per `ARCH-TEST-02`) | matches `ARCH-TEST-07`'s existing "anything, before reporting done" row |

## Out of scope

- Restating `ARCH-TEST-01..08`'s tier mechanics, isolation strategy, pytest configuration, or fixture corpus layout — read [010-architecture.md](010-architecture.md) directly; this document only adds the silo layer and the case-selection reasoning on top.
- The concrete enumeration of test cases per requirement — that is milestone 04 (test cases), which this document is the direct input to.
- A JS unit-test tier (Karma/Jasmine) — `ARCH-TEST-05` already rejects this for `010`; the frontend silo proposed above (`STRAT-SILO-07`) is Playwright-based specifically so no node/npm/build toolchain is introduced (`ARCH-RUN-06`).
- Performance/load testing — `010` is a single local user; not a meaningful category of risk for this release.
