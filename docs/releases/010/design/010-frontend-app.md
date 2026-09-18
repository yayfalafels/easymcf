# Easy MCF POC Local - Frontend App Design

## Contents

- [Purpose](#purpose)
- [Out of scope](#out-of-scope)
- [References](#references)
- [1. App structure and module layout](#1-app-structure-and-module-layout) — `FE-APP-01..03`
- [2. Routing](#2-routing) — `FE-RTE-01`
- [3. API client service](#3-api-client-service) — `FE-SVC-01..03a`
- [4. Async run handling (REQ-FE-02, 010-user-interface.md's "Async run handling")](#4-async-run-handling-req-fe-02-010-user-interfacemds-async-run-handling) — `FE-RUN-01..03`
- [5. Session status and the shared session panel](#5-session-status-and-the-shared-session-panel) — `FE-SVC-04`
- [6. Error and validation surfacing (REQ-FE-02)](#6-error-and-validation-surfacing-req-fe-02) — `FE-ERR-01..03`
- [7. Per-screen controller/service map](#7-per-screen-controllerservice-map) — `FE-SCR-01`
- [8. Testing hooks (supports `ARCH-TEST-05`, `ARCH-TEST-09`)](#8-testing-hooks-supports-arch-test-05-arch-test-09) — `FE-TEST-01..02`

## Purpose

This document elaborates the **user-interface doc**'s page inventory and UX behavior, and the **architecture doc**'s `ARCH-RUN-06/09/10` frontend-serving decisions, into an implementable AngularJS app.

01. module/file layout.
02. the API-client service wrapping the **api doc**'s surface.
03. the async run-polling implementation.
04. error/validation surfacing.
05. a controller/service map for every page in the inventory.

This document sits between what the user sees, covered by the **user-interface doc**, and the actual controller/template code milestones 09-11 write. It does not restate UX behavior, page purpose, or field lists. Read the **user-interface doc** first for those. Nor does it re-decide the API surface. Read the **api doc** for which endpoint answers which write.

Decisions carry an `FE-*` id grouped `APP`/`RTE`/`SVC`/`RUN`/`ERR`/`SCR`/`TEST`, mirroring the `REQ-*`/`ARCH-*`/`API-*` convention.

## Out of scope

01. Visual design: colors, spacing, layout grid, component library. The **user-interface doc** already scopes itself as wireframe-level only. This document doesn't add one either.
02. The generic-CRUD/named-endpoint/hook classification itself. That's the **api doc**'s job. This document only consumes it.
03. Actual controller/template/service code. Milestones 09-11, the functional builds, own this implementation detail, written against the structure fixed here.
04. A component-library or CSS-framework decision. This is not named by any requirement. It is deferred to whoever implements milestone 09's first screen, as a small, contained choice, not a design-milestone blocker.

## References

- **user-interface doc**: [010-user-interface.md](010-user-interface.md) — the page inventory, navigation structure, and cross-cutting UX patterns, async run handling, error surfacing, confirmation modals, empty states, this document implements one-to-one.
- **api doc**: [010-api.md](010-api.md) — the generic CRUD shapes, per-entity CAT-01/02/03 classification, and the `API-EP-01..07` named-endpoint catalog the API-client service (section 3) wraps.
- **architecture doc**: [010-architecture.md](010-architecture.md) — `ARCH-RUN-06` fixes no node/npm, vendored `angular.min.js`, no build step. `ARCH-RUN-09` fixes that Flask serves `frontend/` at `/`, with `index.html` returned for unmatched non-`/api` paths. This is what makes HTML5-mode routing possible without a rewrite proxy. `ARCH-RUN-10` fixes the `/api/v1` prefix. `ARCH-TEST-05`/`ARCH-TEST-09` fix the two Playwright tiers this document's `data-testid` convention exists to support.
- **workflows doc**: [010-workflows.md](010-workflows.md) — workflow numbers cited per screen below, for the process logic each controller drives.
- **data model**: [010-data-model.md](010-data-model.md) — the entity/field definitions, `lead_event` included, that the API-client service and per-screen data reads are checked against.
- **frontend skill**: `.claude/skills/easymcf-frontend/SKILL.md` — the AngularJS framework commitment, which is not a migration target for `010`, and the screen list this elaborates.
- **AngularJS style guide**: [github.com/mgechev/angularjs-style-guide](https://github.com/mgechev/angularjs-style-guide) — the one-component-per-file convention `FE-APP-03` commits to, per the **frontend skill**'s framework reference.

## 1. App structure and module layout

**FE-APP-01** Elaborates `ARCH-RUN-06`'s repo-layout stub, `frontend/{index.html, app/, vendor/}`:

```
frontend/
  index.html              # ng-app root, loads vendor/ then app/, single <div ng-view> shell (ngRoute, FE-RTE-01)
  vendor/
    angular.min.js
    angular-route.min.js  # ngRoute — the one additional vendored file beyond ARCH-RUN-06's baseline
  app/
    app.module.js          # angular.module('easymcfApp', ['ngRoute']) — the one module (FE-APP-02)
    app.routes.js           # $routeProvider table (FE-RTE-01)
    app.config.js            # constants: API base path, poll interval, poll timeout
    core/
      api-client.service.js  # FE-SVC-01/02/03
      run-poller.service.js   # FE-RUN-01/02/03
      session-status.service.js # FE-SVC-04
      error.service.js         # FE-ERR-01
      confirm-dialog.service.js # FE-ERR-03
    shared/
      nav-bar/                # sidebar + session badge, FE-SCR row "shell"
      confirm-modal/           # <confirm-modal> directive backing confirm-dialog.service.js
      empty-state/              # <empty-state> directive (010-user-interface's empty-state pattern)
    tracks/           # screen 1 — tracks.controller.js, tracks.html
    search-profiles/    # screen 1b — search-profiles.controller.js, search-profiles.html (opened as a modal from Tracks, FE-RTE-02)
    cvs/               # screen 2 — cvs.controller.js, cvs.html (also opened as a modal, FE-RTE-02)
    posts/              # screens 3–4 — posts.controller.js, posts.html, manual-post-entry.controller.js, manual-post-entry.html
    leads/                # screens 5–6 — leads.controller.js, leads.html, lead-detail.controller.js, lead-detail.html
    applications/          # screen 7 — applications.controller.js, applications.html
    automation/              # screen 8 — automation.controller.js, automation.html, session-panel/ (shared with the badge)
```

**FE-APP-02** **One Angular module, `easymcfApp`, no per-feature submodules.** AngularJS submodules exist to let independent teams or independently-loaded bundles compose. `010` has one developer, one `<script>` load order, and no lazy loading, since there is no build step to split on, per `ARCH-RUN-06`. Splitting into eight feature modules would add eight registration points and eight places to get DI wiring wrong for zero runtime benefit at this scale. Folder-per-screen (above) gets the organizational benefit without the module-boundary ceremony.

**FE-APP-03** **One component per file**, a controller, or a controller+template pair, per the **AngularJS style guide** that `ARCH-RUN-06`'s skill reference already commits to. This means `<feature>.controller.js` / `<feature>.html` naming, with folders matching the **user-interface doc**'s page numbering, so a reader can go from "page 5, Leads" to `app/leads/` without an intermediate lookup table. `index.html` lists every script explicitly, since there is no build step to generate the list, per `ARCH-RUN-06`. Load order is vendor → `core/` → `shared/` → feature folders → `app.routes.js` last, since route definitions reference the controllers above them.

## 2. Routing

**FE-RTE-01** `ngRoute`, vendored `angular-route.min.js`, the one dependency `ARCH-RUN-06` doesn't already name, runs in **HTML5 mode**, `$locationProvider.html5Mode(true)`: plain paths such as `/tracks`, `/posts`, rather than `#!/tracks` hashbang URLs. This is possible without a rewrite proxy specifically because `ARCH-RUN-09` already has Flask return `index.html` for any unmatched non-`/api` path. A hashbang fallback would be solving a problem `010`'s backend doesn't have. Route table, one entry per nav destination, per the **user-interface doc**'s Navigation structure:

| path            | controller           | template                          | nav destination |
| --------------- | --------------------- | ----------------------------------- | ------------------ |
| `/tracks`       | `TracksCtrl`           | `tracks/tracks.html`               | Tracks              |
| `/posts`        | `PostsCtrl`            | `posts/posts.html`                 | Posts               |
| `/leads`        | `LeadsCtrl`            | `leads/leads.html`                 | Leads               |
| `/applications` | `ApplicationsCtrl`     | `applications/applications.html`   | Applications        |
| `/automation`   | `AutomationCtrl`       | `automation/automation.html`       | Automation          |
| (unmatched)     | redirect to `/tracks`  | —                                  | —                   |

**FE-RTE-02** **CVs, Search Profiles, Manual Post Entry, and Lead Detail are not routes.** The **user-interface doc** is explicit that these four are dialogs/panels reached from a page, not nav destinations. Giving each its own URL would let a bookmark or browser-back land on a dialog with no parent list underneath it, and the **user-interface doc** never specifies a standalone rendering for that state. Each is a controller instantiated by its parent, `PostsCtrl` opens `ManualPostEntryCtrl` in an `ng-if`-gated modal, `LeadsCtrl` opens `LeadDetailCtrl` the same way, and `TracksCtrl` opens `SearchProfilesCtrl` the same way from its "Configure search" row action, per the **user-interface doc**'s page 1b description, dismissed back to the parent's existing route rather than a route transition. `CvsCtrl` is the one exception with two call sites, opened from two different parents, Tracks and Applications, per the **user-interface doc**'s page 2 description. It is one controller/template pair, instantiated by whichever parent's "Manage CVs" control was clicked, per `FE-APP-03`'s one-component-per-file rule, still one file, two call sites.

## 3. API client service

**FE-SVC-01** **One `ApiClient` service is the only code that issues an `/api/**` request.** No controller constructs a raw `$http` call. This is the seam `ARCH-TEST-09`'s frontend-silo tier (`page.route()` intercepting `/api/**`) and `ARCH-TEST-05`'s mock-e2e tier both rely on. Since every request funnels through one service, mocking at the network boundary requires no test-only branch in application code, and a future change to the **api doc**'s surface touches one file, not eight controllers.

**FE-SVC-02** **Table-generic methods**, parameterized by table name, thin promise-returning wrappers over the **api doc**'s seven generic shapes: `get(table, id)`, `list(table, params)` (→ `GET /api/v1/{table}/search`), `create(table, body)`, `update(table, id, body)`, `remove(table, id)`, `batch(table, ops)`. These are used directly for every `API-CAT-01` pure-generic table, `role`, `track`, `search_profile`, `cv`, `post_track`, and every `API-CAT-02` hook-backed table's non-restricted verbs, for example `ApiClient.update('lead', id, {stage: 'TOAPPLY'})`. The hook is transparent to the client per the **api doc**'s `lead` resource entry, so the call shape does not differ from a pure-generic table. The backend enforces the invariant. The frontend does not need to know one exists beyond surfacing whatever `400`/`409` comes back (`FE-ERR-01`).

**FE-SVC-03** **Named-endpoint methods, one per `API-EP-*`, spelled by name rather than as a generic POST.**

01. `promoteManualPost(body)` — `API-EP-01`.
02. `queueApplications(leadIds)` — `API-EP-02`.
03. `dequeueApplication(id)` — `API-EP-03`.
04. `triggerSearchRun(trackId)` — `API-EP-04`.
05. `triggerApplyRun()` — `API-EP-05`.
06. `uploadSession(payload)` — `API-EP-06`.
07. `health()` — `API-EP-07`, used only by `ARCH-TEST-04`'s readiness poll, never by application code.

Naming them distinctly from the generic methods means a reader of a controller can tell, without cross-referencing the **api doc**, which calls are "special." This mirrors why the **api doc** itself keeps `API-EP-*` as a named catalog rather than folding them into the generic classification.

**FE-SVC-03a** `lead_event`, the **data model**'s activity-log table, is read-only from the frontend: `ApiClient.list('lead_event', {lead_id})` backs Lead Detail's activity history, the **user-interface doc**'s page 6, used only for `GET`/`search`. Every write to it happens inside `API-HOOK-01`'s server-side path, the **api doc**'s `lead` resource entry, as a side effect of a `lead` write. No frontend code ever calls `create`/`update`/`remove` against it.

## 4. Async run handling (REQ-FE-02, 010-user-interface.md's "Async run handling")

**FE-RUN-01** **One `RunPoller` service, not two copies of the same loop.** Both Posts' search-run trigger and Applications' apply-run trigger are the identical pattern per `ARCH-RUN-02`: the trigger endpoint returns a `run_log.id` immediately, and the UI polls `GET /api/v1/run_log/{id}` until `status` leaves `running`. `RunPoller.start(runId)` returns a promise-like handle a controller subscribes to for progress updates and a terminal resolution (`success`/`partial`/`failed`), so `PostsCtrl` and `ApplicationsCtrl` both call the same service rather than each hand-rolling a poll loop.

**FE-RUN-02** Polling uses Angular's `$interval`, not a recursive `$timeout` chain or a raw `setInterval`, at a configurable interval (`app.config.js`, default 2s), cancelled explicitly on terminal status or on the triggering `$scope`'s `$destroy`. An abandoned poll loop after the user navigates away is a defect per the same discipline `ARCH-TEST-08` holds test code to: no leftover state/timers between actions. There is no fixed-duration `sleep`-equivalent in Angular code. The poll cadence is the only timing constant, and it is a constant, not inferred from a UI wait.

**FE-RUN-03** **The "run in progress" indicator is a service-level singleton, not controller-scoped state.** The **user-interface doc** requires the badge area to show a run-in-progress indicator visible from any page, including pages that did not trigger the run. So `RunPoller`'s active-run state lives on the service, surviving navigation since Angular services are singletons for the app's lifetime, and the `nav-bar` shared component reads it directly, rather than the triggering controller broadcasting an event that a not-yet-instantiated nav controller would miss.

## 5. Session status and the shared session panel

**FE-SVC-04** `SessionStatus` service holds the current `valid`/`expired`/`missing` state, backed by `ApiClient.get('session', 1)`, the singleton row, refreshed after `uploadSession` resolves and on each route change, a cheap operation since it is one row read. The **user-interface doc** is explicit that the top-right badge and Automation's Session tab are one component reached two ways, not two implementations. This is implemented as a single `<session-panel>` directive bound to the one `SessionStatus` service instance, rendered inline inside `automation.html`'s Session tab and rendered inside an overlay when the badge is clicked. There is no second directive or second service instance for the badge.

## 6. Error and validation surfacing (REQ-FE-02)

**FE-ERR-01** **One `ErrorService`** wraps every `ApiClient` promise rejection, a single `.catch` point inside `ApiClient`'s methods, not one per controller, and converts it into a toast plus an entry the Automation Runs tab can also read. Run-level and general request errors surface this way, never only to the browser console, per the **user-interface doc**'s error-surfacing rules and REQ-FE-02.

**FE-ERR-02** **Field-level validation errors stay local to the form controller**, rendered inline at the point of entry, per the **user-interface doc**'s distinction between run/general errors and field validation. A required-field or format error from a `400` response is read from the rejection's body and shown next to the offending field, not routed through `ErrorService`'s toast.

**FE-ERR-03** **One `confirm-dialog.service.js` / `<confirm-modal>` pair**, parameterized by message and confirm-label, backs every destructive action the **user-interface doc** names behind its confirmation-modal pattern.

01. closing a lead.
02. submitting an apply batch.
03. overwriting a valid session.
04. dequeuing an application.

No screen implements its own modal markup. `ConfirmDialog.ask({message, confirmLabel}).then(...)` is the only call site shape.

## 7. Per-screen controller/service map

**FE-SCR-01** Elaborates the **user-interface doc**'s Page inventory table with the implementation seam for each: the controller that owns the page, the services it calls, and, where it isn't obvious from the API-client naming alone, which **api doc** operation a page action maps to:

| # | page                          | controller               | primary services                                                                                 | notes |
| - | ------------------------------ | --------------------------- | ---------------------------------------------------------------------------------------------------- | ------- |
| 1 | Tracks                          | `TracksCtrl`                  | `ApiClient` (`track`, `cv` list for the CV picker, read-only `search_profile` for the row summary)                                     | archive toggle is `ApiClient.update('track', id, {is_active: false})` — `FE-SVC-02`, no named endpoint (010-api.md's classification); search-profile editing happens on Search Profiles (1b), not here |
| 1b | Search Profiles                | `SearchProfilesCtrl`           | `ApiClient` (`search_profile`)                                                                                | opened from Tracks as a modal, `FE-RTE-02`; generic `PUT /api/v1/search_profile/{track_id}` |
| 2 | CVs                               | `CvsCtrl`                       | `ApiClient` (`cv`)                                                                                            | opened from Tracks or Applications, `FE-RTE-02` |
| 3 | Posts                              | `PostsCtrl`                       | `ApiClient` (`post`, `post_track`), `ApiClient.triggerSearchRun`, `RunPoller`, `ErrorService`                     | promote-to-lead is `ApiClient.create('lead', {post_id, track_id})` — a generic `POST /api/v1/lead`, not a named endpoint; see note below |
| 4 | Manual Post Entry                   | `ManualPostEntryCtrl`               | `ApiClient.promoteManualPost`                                                                                       | `API-EP-01`; opened as a modal from Posts, `FE-RTE-02` |
| 5 | Leads                                 | `LeadsCtrl`                           | `ApiClient` (`lead`), `ConfirmDialog`                                                                                  | stage transitions and closes are generic `PUT /api/v1/lead/{id}` (`API-HOOK-01` is transparent, `FE-SVC-02`); tab filters are client-side on one `list('lead')` fetch, not one request per tab; the expiry-warning indicator is computed client-side from the fetched `deadline` field, not a separate API flag |
| 6 | Lead Detail                            | `LeadDetailCtrl`                        | `ApiClient` (`lead`, read-only `lead_event` per `FE-SVC-03a`), `ConfirmDialog`                                           | opened as a panel from Leads, `FE-RTE-02` |
| 7 | Applications                             | `ApplicationsCtrl`                        | `ApiClient` (`application`), `ApiClient.queueApplications`/`dequeueApplication`/`triggerApplyRun`, `RunPoller`, `ConfirmDialog` | `API-EP-02/03/05` |
| 8 | Automation (Runs / Session)                | `AutomationCtrl`                            | `ApiClient.list('run_log')`, `SessionStatus`, `<session-panel>`, `ApiClient.uploadSession`                                 | `API-EP-06`; Runs tab is generic `GET`/`search` per `API-HOOK-04` |

Promote-to-lead (row 3) is not in the **api doc**'s named-endpoint catalog as a distinct `API-EP-*`. Because `lead` is `API-CAT-02` hook-backed, `API-HOOK-01`'s invariant, a `post_id` already promoted is rejected, per the **data model**'s uniqueness rule, is enforced server-side on this same generic call, not by a named endpoint. `PostsCtrl` calls `ApiClient.create`, not a special "promote" method, and reads the resulting `409` through `ErrorService`/inline handling like any other constraint violation.

## 8. Testing hooks (supports `ARCH-TEST-05`, `ARCH-TEST-09`)

**FE-TEST-01** **Every interactive control carries a `data-testid` attribute**, kebab-case, scoped `{screen}-{element}[-{id}]`, for example `posts-run-search-btn`, `lead-card-{id}-close-btn`, `applications-run-apply-btn`. This is fixed here rather than left to whoever writes each template, so the two Playwright tiers' DOM assertions (`ARCH-TEST-05` full-stack, `ARCH-TEST-09` frontend-silo) have a stable, deliberate contract to assert against instead of reverse-engineering one from markup after the fact. This is the same rationale `ARCH-BOT-01`'s skill reference gives for MCF's own markup, applied to this app's own templates.

**FE-TEST-02** Because `FE-SVC-01` makes `ApiClient` the sole `/api` call site, `ARCH-TEST-09`'s frontend-silo mocking, `page.route('**/api/**', ...)` fulfilled from `tests/fixtures/api/*.json`, requires no test-only conditional anywhere in `app/`. The same `ApiClient` code runs against the real backend, `ARCH-TEST-05`, tier 2, and the mocked one, tier 1b, with the interception happening entirely at the network layer Playwright already controls.
</content>
