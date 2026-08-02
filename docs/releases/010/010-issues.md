# Easy MCF POC Local - Design Audit Issues

## Purpose

Findings from a design audit of the release `010` document set (`docs/releases/010/*.md` plus
[release-roadmap.md](../release-roadmap.md) and root `CLAUDE.md`), scoped by the
[design-audit](../../../.claude/skills/design-audit/SKILL.md) skill against four questions: internal
consistency across the set, alignment with current external best practice, implementation risk if built
as written, and whether the requirements → workflows/data-model → architecture/UI/test-strategy hierarchy actually holds. This is a documentation audit — no `010` code exists yet — so every finding is about what the documents themselves claim and whether those claims agree with each other, with external practice, andwith the milestone tracker's own account of what's done.

Doc key: **REQ**=[010-01-requirements.md](010-01-requirements.md), **ARCH**=[010-architecture.md](010-architecture.md),
**DM**=[010-data-model.md](010-data-model.md), **WF**=[010-workflows.md](010-workflows.md),
**UI**=[010-user-interface.md](010-user-interface.md), **STRAT**=[010-test-strategy.md](010-test-strategy.md),
**TD**=[010-test-data.md](010-test-data.md), **MS**=[010-release-milestones.md](010-release-milestones.md),
**REL**=[010-release.md](010-release.md), **RM**=[release-roadmap.md](../release-roadmap.md),
**CA**=[010-claude-agent.md](010-claude-agent.md), **CM**=`CLAUDE.md`.

## Summary

| ID     | Severity | Category               | Title                                     | Docs                |
| ------ | -------- | ---------------------- | ------------------------------------------ | ------------------- |
| ISS-01 | High     | Hierarchy/Traceability | Milestone tracker status is stale          | MS, ARCH, DM, STRAT |
| ISS-02 | High     | Internal Consistency   | Generic CRUD vs lead state-machine rules   | REQ, ARCH, WF       |
| ISS-03 | Medium   | Implementation Risk    | Run-in-flight guard has no atomic check    | ARCH                |
| ISS-04 | Medium   | Internal Consistency   | 010-release.md contradicts Flask choice    | REL, REQ, ARCH, CM  |
| ISS-05 | Medium   | Hierarchy/Traceability | Frontend test tier left unconfirmed        | STRAT, ARCH         |
| ISS-06 | Medium   | Design Best Practice   | AngularJS 1.x is EOL, no revisit plan      | RM, REQ, CA         |
| ISS-07 | Medium   | Implementation Risk    | Apply-retry timing risks e2e budget        | REQ, ARCH, STRAT    |
| ISS-08 | Low      | Internal Consistency   | Login-redirect automation is ambiguous     | ARCH, WF, UI        |
| ISS-09 | Low      | Design Best Practice   | Table-mirroring CRUD is an anti-pattern    | REQ, ARCH           |

## Issues

### ISS-01 Milestone tracker status is stale

`010-release-milestones.md` shows **architecture** (id 05, sequence 02) as `pending`, **data model** (id 04,
sequence 05) as `pending`, and **test strategy** (id 02, sequence 03) as `open`. All three documents are, in
fact, long and complete: ARCH's own purpose line calls itself "intended to be complete enough that 07 can be
implemented without further design decisions," and STRAT explicitly builds on top of `ARCH-TEST-01..08` as
already-fixed. Beyond status drift, the *sequence numbers* contradict the documents' own dependency chain:
architecture is sequenced (02) before data model (05) and test strategy/test cases (03/04), yet ARCH's
References section lists DM as an input ("the tables the storage section below is concrete about") and
`ARCH-STO-01` enumerates the exact table names DM defines — architecture cannot have been meaningfully
authored before data model despite the tracker's ordering. Separately, several documents that already exist
(`010-workflows.md`, `010-user-interface.md`, `010-test-data.md`, `010-prototype.md`, `010-claude-agent.md`)
have no row in the milestone table at all, so there's no way to tell from MS alone which milestone id/status
they satisfy — `010-user-interface.md` is presumably the "design" milestone's (id 06) deliverable, but
nothing states that, and MS still marks "design" `pending`.

**Why it matters:** a milestone tracker whose statuses and ordering don't match reality stops being usable
for its one job — telling a reader (human or agent) what's actually safe to build on. An agent picking up
milestone 09 and trusting MS would look for an architecture doc that "doesn't exist yet."

**Suggested resolution:** product-manager pass to reconcile MS against actual document state: mark
architecture/data-model/test-strategy `closed`, map the unlisted documents to milestone ids (or add rows),
and either drop the sequence-number column or renumber it to match the dependency order the documents
themselves already assert.

### ISS-02 Generic CRUD vs lead state-machine rules

`REQ-PLAT-01` mandates "a generic, schema-validated CRUD interface per entity ... rather than bespoke
endpoints per feature" covering *all* domain data, explicitly including `lead`. But `REQ-CRM-02/05`, `REQ-APPLY-09/10`,
and Workflow 5's state diagram define a lead lifecycle with real invariants a client must not be able to
violate directly: `stage` transitions follow a fixed graph, `CLOSED` requires a `close_reason`, auto-expiry
is keyed off `lead.updated_at` (not a raw field write), and apply outcomes auto-propagate to specific stage
changes. Nothing in `010-architecture.md` states that writes to these fields are routed through a service
layer rather than a raw generic `PUT /api/lead/{id}` — the repo layout's `services/` folder is described only
as "search, scoring, apply orchestration; run_log writes" (`ARCH-RUN-*` repo layout section), with no mention
of lead-write mediation. `ARCH-RUN-10` names exactly two deliberate exceptions to the seven generic CRUD
shapes — the run-trigger and session-upload endpoints — but omits several other clearly non-generic
operations the requirements/workflows actually need: promote-post-to-lead (`REQ-CRM-01`, a cross-table,
uniqueness-checked create), queue-for-apply and remove-from-queue (`REQ-APPLY-01/11`, each with a specific
side effect beyond a field write), and auto-expiry evaluation, which Workflow 5 says happens "on each backend
list call (e.g. `GET /lead/search`)" — meaning the *generic* search endpoint must itself carry table-specific
business logic, which is not generic. `REQ-CRM-07` ("all lead interactions happen through the AngularJS UI")
reads as an attempt to paper over this by trusting the frontend to only ever issue "correct" writes, which is
a well-known insufficient control (see ISS-09) since nothing stops a stray or buggy request from bypassing it.

**Why it matters:** this is the single largest unresolved seam between the platform requirement and the
functional requirements. Built literally as REQ-PLAT-01 states, a client (or a backend test, or a future bug)
could `PUT` `lead.stage=OFFER` directly from `PROSPECT`, or close a lead with no reason, or hand-roll an
apply-outcome propagation that the generic layer never validates.

**Suggested resolution:** architect decision needed on milestone 06 (design) or during milestone 09: name
the full set of non-generic-CRUD endpoints (promote, queue, dequeue, run-trigger, session-upload — expiry
evaluation is presumably fine as a read-time computation but should say so explicitly), and state whether
generic `PUT`/`POST` on `lead`/`application`/`post_track` is disabled entirely in favor of the named
endpoints, or whether the generic layer gets field-level write restrictions for state-machine-governed
tables.

### ISS-03 Run-in-flight guard has no atomic check

`ARCH-RUN-03` states "at most one run of each type may be in flight," enforced by a trigger endpoint checking
for an existing `run_log` row with `status = running` before returning `409` or proceeding. The Flask process
runs `threaded=True` (`ARCH-RUN-07`), and no document specifies that the check-for-existing-row-then-insert
sequence is atomic (e.g. a single transaction, a `UNIQUE` partial index on `run_log(run_type)` filtered to
`status='running'`, or an in-process lock). As written, two near-simultaneous trigger requests on separate
threads can both read "no row running" before either commits its own `running` row, defeating the invariant
the rest of `ARCH-RUN-02/04`'s threading-safety argument depends on ("prevents two scrapes competing for the
same browser/session").

**Why it matters:** this is exactly the failure mode SQLite's own concurrency model warns about — WAL mode
guarantees a single committing writer, but does nothing to make an application-level check-then-act sequence
atomic across two connections. Two concurrent search runs sharing one Playwright browser context would be a
confusing, hard-to-reproduce bug to chase down after the fact.

**Suggested resolution:** architect should specify the atomicity mechanism explicitly — the simplest fix
consistent with `ARCH-STO-02`'s low-ceremony stance is a `UNIQUE` index on `(run_type)` scoped to
`status='running'` (SQLite supports partial indexes) so the second insert fails at the database level instead
of relying on a race-prone application check.

### ISS-04 010-release.md contradicts Flask choice

`010-release.md` (cited from `010-01-requirements.md`'s References section) states: "The current release will
run locally with a segregated frontend - backend model with front-end running python fast api with a backend
local sqlite db, and frontend on angular js." This both garbles the frontend/backend split (a frontend
"running python fast api" makes no sense) and names FastAPI, while every other document unanimously specifies
Flask: `REQ-PLAT-01` ("e.g. Flask"), `ARCH-RUN-01/05/07` (Flask serving both API and static files, Werkzeug
dev server), and `CLAUDE.md` ("Python (Flask) backend").

**Why it matters:** `010-release.md` is a referenced source-of-truth document, not dead scaffolding — a
reader who starts there before requirements.md would form the wrong framework expectation immediately.

**Suggested resolution:** rewrite the "Features" table row 12 sentence in `010-release.md` to match the
`release-roadmap.md` feature table it otherwise mirrors ("be runtime: python", "fe runtime: angular js"),
dropping the FastAPI reference entirely.

### ISS-05 Frontend test tier left unconfirmed

`010-test-strategy.md`'s `STRAT-SILO-07` proposes a new `tests/frontend/` Playwright tier with its own fixture
corpus (`tests/fixtures/api/*.json`), explicitly labeled "proposed addition to `ARCH-TEST`'s repo layout, for
architect confirmation alongside milestone 02/05." `010-architecture.md`'s repo layout (the section that owns
`tests/`) lists only `tests/backend/`, `tests/e2e/`, `tests/live/`, and `tests/fixtures/mcf/` — it has not
been updated to include the proposal, and `ARCH-TEST-02`'s pytest marker list (`backend`, `e2e`, `live`) has
no corresponding `frontend` marker either.

**Why it matters:** this is a live, named cross-document decision that neither document currently resolves —
STRAT assumes it will likely be adopted (it's referenced elsewhere in the silo-aware build/test table as if
settled) while ARCH is silent on it. Left as-is, milestone 07 has no single authoritative answer for whether
`tests/frontend/` exists.

**Suggested resolution:** architect confirms or rejects `STRAT-SILO-07` explicitly in `010-architecture.md`
(updating the repo layout and `ARCH-TEST-02`'s marker table either way) rather than leaving the proposal
standing only in the test-strategy document.

### ISS-06 AngularJS 1.x is EOL, no revisit plan

`release-roadmap.md`'s feature table commits `fe runtime: angular js` across `010`, `020` (MVP cloud), and
`100` (beta single user) — three releases. AngularJS (1.x) reached end-of-life on 2021-12-31 and has received
no security patches since; it has known, unfixed template-injection/XSS exposure in its expression parser and
no Trusted Types or CSP-nonce support (sources below). `010-architecture.md`'s justification for AngularJS —
no build step, no node/npm toolchain, roughly eight screens — is a reasonable, well-argued trade-off for a
loopback-only, single-user, offline POC, and the low network exposure (`ARCH-NET-01` binds to `127.0.0.1`
only) meaningfully reduces the practical risk today. But the roadmap carries the same choice into `020`
(cloud-deployed, presumably network-exposed) with no stated revisit trigger, and `010-claude-agent.md`'s
`REQ-AGENT-17` frames the constraint only as "not a framework migration" for `010`, without flagging the
EOL status as a fact a future release decision should weigh.

**Why it matters:** the risk is low for `010` specifically but the design set gives no signal that the
EOL status was a known, weighed trade-off rather than an oversight — and the roadmap's un-caveated repetition
of "angular js" through `020`/cloud makes it easy to carry the choice into a network-exposed context without
re-examining it.

**Suggested resolution:** add one sentence to `release-roadmap.md` or `010-architecture.md` naming the
AngularJS EOL status explicitly as an accepted `010`-scope risk (mitigated by loopback-only binding), and
flag it as a decision `020` must explicitly re-affirm rather than silently inherit.

Sources: [AngularJS End of Life: Support Options, LTS, and Migration in 2026](https://scand.com/company/blog/angularjs-end-of-life-legacy-apps/), [EOL AngularJS Security Patches — Versions 1.5.x–1.8.x](https://tuxcare.com/endless-lifecycle-support/angularjs-eol-support/), [Angular Security Vulnerabilities: What Unsupported Versions Expose in 2026](https://frontendminds.com/blog/angular-security-vulnerabilities)

### ISS-07 Apply-retry timing risks e2e budget

`REQ-APPLY-07` fixes the apply-button poll at 5 retries with a 5-second delay between attempts — up to 25
seconds for a single application to reach `unable_to_apply`. No document mentions a test-mode override for
this timing. `010-architecture.md`'s tier table states the mock e2e tier (`ARCH-TEST-04`) targets "~1-2 min"
total duration, and the fixture corpus (`ARCH-TEST-04`) requires one directory per REQ-APPLY-04 outcome
including `unable_to_apply` specifically "so the apply button never resolving" is deterministically
reachable — meaning at least one real test must let the full 25-second retry loop run to completion.

**Why it matters:** one or two such scenarios are affordable inside a "~1-2 min" budget, but there's no
stated mechanism (an env-var-driven retry delay, a fixture-mode short-circuit) preventing this from silently
growing as more retry-dependent scenarios are added, and `pytest-timeout`'s default 60s per-test ceiling
(`ARCH-TEST-02`) leaves comparatively little headroom once page-load and browser-launch time are added on
top of a 25-second poll loop.

**Suggested resolution:** add an environment-variable override for the retry delay/count (mirroring the
`clock.py::now()` indirection pattern `ARCH-STO-05` already uses for time) so fixture-mode tests can shrink
the loop to milliseconds without changing production behavior.

### ISS-08 Login-redirect automation is ambiguous

`ARCH-NET-03` states the system makes "no outbound network calls except browser automation to
`mycareersfuture.gov.sg` (and its Singpass login redirect, which the user completes manually in their own
browser — the app never drives it, per REQ-APPLY-06)." This bundles the login redirect into the same clause
as Playwright browser automation while simultaneously saying the app never drives it, leaving unclear whether
the login step ever involves the app's own Playwright-controlled browser context at all, or is purely a
plain hyperlink/redirect the user's ordinary browser follows outside the app's process. Workflow 8 step 2
("App opens MCF's login flow") and the UI's Automation-tab description ("'Log in to MCF' button — opens
MCF's Singpass login flow (external browser context...)") both lean toward the latter reading but don't use
identical language to rule out the former.

**Why it matters:** low risk, but this is precisely the kind of ambiguity that could lead an implementer to
accidentally wire the login step through the same `MCFBrowser`/Playwright automation used for scraping and
apply (`ARCH-BOT-02`) — which would put automated code in the path of a step this release deliberately keeps
manual (login/MFA automation is explicitly out of scope).

**Suggested resolution:** one clarifying sentence in `ARCH-NET-03` or `ARCH-BOT-02`: the login step opens an
ordinary browser tab/window (or is simply a link), never a Playwright-controlled context.

### ISS-09 Table-mirroring CRUD is an anti-pattern

`REQ-PLAT-01`'s generic, per-table CRUD interface — inherited deliberately from `mcfpipe`'s Database API
design — is a documented, widely-recognized anti-pattern in current API design practice: mirroring the
internal data model 1:1 in a public API tends to push business-rule enforcement onto every caller (exactly
the seam described in ISS-02) and couples the API's shape to internal schema changes. This is a known,
named trade-off in the design set (mcfpipe's own validation checklist is explicitly reused, and REQ-PLAT-01's
rationale — avoiding "bespoke endpoints per feature" — is a real, defensible reason for a single-developer
POC to prefer it), so this is not a case for reversing the decision. It is a case for documenting the
mitigation the design set is implicitly relying on (see ISS-02) rather than leaving the trade-off unstated.

**Why it matters:** the pattern's known failure mode (business logic bypassed or duplicated per client) is
exactly the mechanism behind ISS-02's concrete finding — this entry records the general practice basis for
that finding separately, since it would recur with any future entity given a state machine, not only `lead`.

**Suggested resolution:** none beyond ISS-02's — recorded here as the general principle underlying that
specific finding.

Sources: [Rethinking CRUD For REST API Designs — Palantir Blog](https://blog.palantir.com/rethinking-crud-for-rest-api-designs-a2a8287dc2af), [Web API Design Anti-Pattern: Exposing your database model](https://shekhargulati.com/2021/10/15/web-api-design-anti-pattern-exposing-your-database-model/), [The CRUD Anti-Pattern in REST APIs](https://codeboje.de/the-crud-anti-pattern-in-rest-apis/)
