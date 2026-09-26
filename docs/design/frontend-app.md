# Easy MCF POC Local - Frontend App Design

Release `010` design. Source: [docs/releases/010/design/010-frontend-app.md](https://github.com/yayfalafels/easymcf/blob/main/docs/releases/010/design/010-frontend-app.md).

## Contents

- [Purpose](#purpose)
- [Out of scope](#out-of-scope)
- [References](#references)
- [1. App structure and module layout](#1-app-structure-and-module-layout) — `FE-APP-01..03`
- [2. Routing](#2-routing) — `FE-RTE-01..04`
- [3. API client service](#3-api-client-service) — `FE-SVC-01..03a`
- [4. Async run handling (REQ-FE-02, 010-user-interface.md's "Async run handling")](#4-async-run-handling-req-fe-02-010-user-interfacemds-async-run-handling) — `FE-RUN-01..03`
- [5. MCF connection state and shared controls](#5-mcf-connection-state-and-shared-controls) — `FE-SVC-04`
- [6. Error and validation surfacing (REQ-FE-02)](#6-error-and-validation-surfacing-req-fe-02) — `FE-ERR-01..03`
- [7. Per-screen controller/service map](#7-per-screen-controllerservice-map) — `FE-SCR-01`
- [8. Testing hooks (supports `ARCH-TEST-05`, `ARCH-TEST-09`)](#8-testing-hooks-supports-arch-test-05-arch-test-09) — `FE-TEST-01..02`
- [9. Authentication and the user section](#9-authentication-and-the-user-section) — `FE-AUTH-01..05`

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

- **user-interface doc**: [010-user-interface.md](user-interface.md) — the page inventory, navigation structure, and cross-cutting UX patterns, async run handling, error surfacing, confirmation modals, empty states, this document implements one-to-one.
- **api doc**: [010-api.md](api.md) — the generic CRUD shapes, per-entity CAT-01/02/03 classification, and the `API-EP-01..07` named-endpoint catalog the API-client service (section 3) wraps.
- **architecture doc**: [010-architecture.md](architecture.md) — `ARCH-RUN-06` fixes no node/npm, vendored `angular.min.js`, no build step. `ARCH-RUN-09` fixes that Flask serves `frontend/` at `/`, with `index.html` returned for unmatched non-`/api` paths. This is what makes HTML5-mode routing possible without a rewrite proxy. `ARCH-RUN-10` fixes the `/api/v1` prefix. `ARCH-TEST-05`/`ARCH-TEST-09` fix the two Playwright tiers this document's `data-testid` convention exists to support.
- **workflows doc**: [010-workflows.md](workflows.md) — workflow numbers cited per screen below, for the process logic each controller drives.
- **data model**: [010-data-model.md](data-model.md) — the entity/field definitions, `lead_event` included, that the API-client service and per-screen data reads are checked against.
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
      mcf-connect.service.js     # FE-SVC-04
      auth.service.js          # FE-AUTH-01
      auth.interceptor.js       # FE-AUTH-03
      error.service.js         # FE-ERR-01
      confirm-dialog.service.js # FE-ERR-03
      offer-dialog.service.js   # OfferDialog, the offer form modal (page 9, Lead Detail)
    shared/
      nav-bar/                # sidebar + MCF icon + user section, FE-SCR row "shell"
      mcf-nav-icon/           # status indicator and connection pop-up toggle
      mcf-connect-modal/      # QR, confirmation, session state, Open, Disconnect
      mcf-link/               # authenticated MCF links with native fallback
      user-menu/               # <user-menu> photo circle, upload, remove, log out (FE-AUTH-04)
      confirm-modal/           # <confirm-modal> directive backing confirm-dialog.service.js
      offer-modal/             # <offer-modal> directive backing offer-dialog.service.js
      empty-state/              # <empty-state> directive (010-user-interface's empty-state pattern)
    auth/                # screens 10–11 — auth.controller.js, signin.html, signup.html (FE-AUTH-05)
    tracks/           # screen 1 — tracks.controller.js, tracks.html, and screen 1b's search-profile.controller.js,
                       # search-profile.html, its own route reached from Tracks (FE-RTE-02), colocated here rather
                       # than a separate top-level folder since it has no lifecycle apart from Tracks
    cvs/               # screen 2 — cvs.controller.js, cvs.html, its own route reached from Tracks or Applications (FE-RTE-02)
    posts/              # screen 3 — posts.controller.js, posts.html; screen 4, Manual Post Entry, is a dialog backed
                       # by manual-post-dialog.service.js and the shared manual-post-modal directive (FE-RTE-04),
                       # not a controller of its own
    leads/                # screens 5–6 — leads.controller.js, leads.html, lead-detail.controller.js, lead-detail.html
    offers/                # screen 9 — offers.controller.js, offers.html
    applications/          # screen 7 — applications.controller.js, applications.html
```

**FE-APP-02** **One Angular module, `easymcfApp`, no per-feature submodules.** AngularJS submodules exist to let independent teams or independently-loaded bundles compose. `010` has one developer, one `<script>` load order, and no lazy loading, since there is no build step to split on, per `ARCH-RUN-06`. Splitting into eight feature modules would add eight registration points and eight places to get DI wiring wrong for zero runtime benefit at this scale. Folder-per-screen (above) gets the organizational benefit without the module-boundary ceremony.

**FE-APP-03** **One component per file**, a controller, or a controller+template pair, per the **AngularJS style guide** that `ARCH-RUN-06`'s skill reference already commits to. This means `<feature>.controller.js` / `<feature>.html` naming, with folders matching the **user-interface doc**'s page numbering, so a reader can go from "page 5, Leads" to `app/leads/` without an intermediate lookup table. `index.html` lists every script explicitly, since there is no build step to generate the list, per `ARCH-RUN-06`. Load order is vendor → `core/` → `shared/` → feature folders → `app.routes.js` last, since route definitions reference the controllers above them.

## 2. Routing

**FE-RTE-01** `ngRoute`, vendored `angular-route.min.js`, the one dependency `ARCH-RUN-06` doesn't already name, runs in **HTML5 mode**, `$locationProvider.html5Mode(true)`: plain paths such as `/tracks`, `/posts`, rather than `#!/tracks` hashbang URLs. This is possible without a rewrite proxy specifically because `ARCH-RUN-09` already has Flask return `index.html` for any unmatched non-`/api` path. A hashbang fallback would be solving a problem `010`'s backend doesn't have. `/` and any unmatched path redirect to `/leads`, so the app opens on the Leads page for a signed-in user. Route table, one entry per nav destination plus the two public sign-in pages, per the **user-interface doc**'s Navigation structure:

| path                      | controller           | template                         | nav destination |
| ------------------------- | -------------------- | -------------------------------- | --------------- |
| `/tracks`                 | `TracksCtrl`         | `tracks/tracks.html`             | Tracks          |
| `/tracks/:trackId/search` | `SearchProfileCtrl`  | `tracks/search-profile.html`     | — (from Tracks) |
| `/posts`                  | `PostsCtrl`          | `posts/posts.html`               | Posts           |
| `/leads`                  | `LeadsCtrl`          | `leads/leads.html`               | Leads           |
| `/offers`                 | `OffersCtrl`         | `offers/offers.html`             | Offers          |
| `/applications`           | `ApplicationsCtrl`   | `applications/applications.html` | Applications    |
| `/automation`             | `AutomationCtrl`     | `automation/automation.html`     | Automation      |
| `/signin`                 | `AuthCtrl`           | `auth/signin.html`               | — (public)      |
| `/signup`                 | `AuthCtrl`           | `auth/signup.html`               | — (public)      |
| (unmatched)               | redirect to `/leads` | —                                | —               |

**FE-RTE-02** **Manual Post Entry, Lead Detail, and the offer dialog are not routes; Search Profiles and CVs are.** The **user-interface doc** calls Search Profiles and CVs "reached from a page" rather than standalone nav destinations, but each turned out to need its own bookmarkable URL and its own full-page form once built, so each is a real route above (`/tracks/:trackId/search`, `/cvs`), reached by `$location.path()` from its parent row action rather than an `ng-if`-gated overlay, and dismissed by navigating back. Manual Post Entry, Lead Detail, and the offer dialog have no parent list of their own underneath them, so each stays a dialog: `PostsCtrl` opens `ManualPostEntryCtrl` in an `ng-if`-gated modal, and `LeadsCtrl` opens `LeadDetailCtrl` the same way, per `FE-RTE-04`'s dialog-service pattern. `CvsCtrl` has two call sites, opened from two different parents, Tracks and Applications, per the **user-interface doc**'s page 2 description. It is one controller/template pair, instantiated by whichever parent's "Manage CVs" control was clicked, per `FE-APP-03`'s one-component-per-file rule, still one file, two call sites.

**FE-RTE-04** **A dialog that isn't a route is a shared state service plus a directive, not a controller.** `ManualPostDialog`/`OfferDialog`-shaped: a factory holds an `open()`/`save()`/`cancel()` API and a `state` object a directive's `link` function reads (`manual-post-modal`/`offer-modal`), rendered with `ng-if="dialog.open"`. The opening controller calls `open()` and gets a promise back, exactly the shape `ConfirmDialog` and `OfferDialog` already established. There is no separate `*Ctrl` for a dialog — the directive's own scope and the shared service are enough, and a second call site never needs a second instantiation path.

**FE-RTE-03** **Every route except `/signin` and `/signup` is guarded.** Each guarded route carries `resolve: { auth: ['AuthService', function (a) { return a.require(); }] }`, which rejects with `'unauthenticated'` when nobody is signed in. One `$routeChangeError` handler turns that rejection into `$location.path('/signin').search({next: <requested path>})`. The public routes resolve `AuthService.redirectIfSignedIn()`, which sends an already signed-in user to `/leads`. The guard is a convenience for navigation. The `401` from the API remains the actual enforcement (`FE-AUTH-03`).

## 3. API client service

**FE-SVC-01** **One `ApiClient` service is the only code that issues an `/api/**` request.** No controller constructs a raw `$http` call. This is the seam `ARCH-TEST-09`'s frontend-silo tier (`page.route()` intercepting `/api/**`) and `ARCH-TEST-05`'s mock-e2e tier both rely on. Since every request funnels through one service, mocking at the network boundary requires no test-only branch in application code, and a future change to the **api doc**'s surface touches one file, not eight controllers.

**FE-SVC-02** **Table-generic methods**, parameterized by table name, thin promise-returning wrappers over the **api doc**'s seven generic shapes: `get(table, id)`, `list(table, params)` (→ `GET /api/v1/{table}/search`), `create(table, body)`, `update(table, id, body)`, `remove(table, id)`, `batch(table, rows)`. These are used directly for every `API-CAT-01` pure-generic table, `role`, `search_profile`, `search_schedule`, `cv`, and every `API-CAT-02` hook-backed table's non-restricted verbs — `track`'s create hook and every restriction below are invisible at this call shape, so `ApiClient.create('track', body)` is still a plain generic call, for example `ApiClient.update('lead', id, {stage: 'APPLIED'})`. `LeadsCtrl` uses `ApiClient.batch('lead', rows)` (`POST /api/v1/lead/batch`) for the Apply and Drop actions on the `TOAPPLY` column, and reads a `409` naming the failing `lead_id` through `ErrorService`. The hook is transparent to the client per the **api doc**'s `lead` resource entry, so the call shape does not differ from a pure-generic table. The backend enforces the invariant. The frontend does not need to know one exists beyond surfacing whatever `400`/`409` comes back (`FE-ERR-01`).

**FE-SVC-03** **Named-endpoint methods, one per `API-EP-*`, spelled by name rather than as a generic POST.**

01. `promoteManualPost(body)` — `API-EP-01`.
02. `triggerSearchRun(trackId)` — `API-EP-04`.
03. `triggerApplyRun()` — `API-EP-05`.
04. `startMcfAttempt()`, `mcfAttemptQrUrl(id)`, `mcfAttemptQrLink(id)`, `confirmMcfAttempt(id, accept)`, and `cancelMcfAttempt(id)` — the MCF attempt endpoints.
05. `openMcfSession(url)` — authenticated visible-browser launch or plain-link fallback.
06. `health()` — `API-EP-07`, used only by `ARCH-TEST-04`'s readiness poll, never by application code.
07. `signup(body)`, `signin(body)`, `signout()`, `me()`, and `authConfig()` — `API-EP-08..12`, called only by `AuthService`.
08. `uploadPhoto(userId, file)` and `removePhoto(userId)` — `API-EP-15/16`, called only by `AuthService`. The photo itself loads through an `<img src>` bound to the user's `photo_url` (`API-EP-17`), never through `ApiClient`.

`API-EP-02` and `API-EP-03` are retired (the apply queue is the set of open `TOAPPLY` leads), so no `queueApplications` or `dequeueApplication` method exists.

Naming them distinctly from the generic methods means a reader of a controller can tell, without cross-referencing the **api doc**, which calls are "special." This mirrors why the **api doc** itself keeps `API-EP-*` as a named catalog rather than folding them into the generic classification.

**FE-SVC-03a** `lead_event`, the **data model**'s activity-log table, is read-only from the frontend: `ApiClient.list('lead_event', {lead_id})` backs Lead Detail's activity history, the **user-interface doc**'s page 6, used only for `GET`/`search`. Every write to it happens inside `API-HOOK-01`'s server-side path, the **api doc**'s `lead` resource entry, as a side effect of a `lead` write. No frontend code ever calls `create`/`update`/`remove` against it. The rows carry `stage_from` and `stage_to`, which `LeadDetailCtrl` maps into each activity entry so the panel shows the stage context of every event.

## 4. Async run handling (REQ-FE-02, 010-user-interface.md's "Async run handling")

**FE-RUN-01** **One `RunPoller` service, not two copies of the same loop.** Both Posts' search-run trigger and Applications' apply-run trigger are the identical pattern per `ARCH-RUN-02`: the trigger endpoint returns a `run_log.id` immediately, and the UI polls `GET /api/v1/run_log/{id}` until `status` leaves `running`. `RunPoller.start(runId)` returns a promise-like handle a controller subscribes to for progress updates and a terminal resolution (`success`/`partial`/`failed`), so `PostsCtrl` and `ApplicationsCtrl` both call the same service rather than each hand-rolling a poll loop.

**FE-RUN-02** Polling uses Angular's `$interval`, not a recursive `$timeout` chain or a raw `setInterval`, at a configurable interval (`app.config.js`, default 2s), cancelled explicitly on terminal status or on the triggering `$scope`'s `$destroy`. An abandoned poll loop after the user navigates away is a defect per the same discipline `ARCH-TEST-08` holds test code to: no leftover state/timers between actions. There is no fixed-duration `sleep`-equivalent in Angular code. The poll cadence is the only timing constant, and it is a constant, not inferred from a UI wait.

**FE-RUN-03** **The "run in progress" indicator is a service-level singleton, not controller-scoped state.** The **user-interface doc** requires the badge area to show a run-in-progress indicator visible from any page, including pages that did not trigger the run. So `RunPoller`'s active-run state lives on the service, surviving navigation since Angular services are singletons for the app's lifetime, and the `nav-bar` shared component reads it directly, rather than the triggering controller broadcasting an event that a not-yet-instantiated nav controller would miss.

## 5. MCF connection state and shared controls

**FE-SVC-04** `McfConnect` holds the latest attempt and current `valid`/`expired`/`missing` session in one singleton state object. It polls `mcf_attempt` and `mcf_session` every three seconds. `<mcf-nav-icon>` renders the state as red, amber, or green and toggles the single `<mcf-connect-modal>` overlay. The modal starts and cancels attempts, shows the current QR, confirms a first account, disconnects a session, and opens MCF home through `openMcfSession`. The `mcf-link` directive gives lead links the same authenticated launch behavior while valid and leaves native new-tab navigation untouched otherwise.

## 6. Error and validation surfacing (REQ-FE-02)

**FE-ERR-01** **One `ErrorService`** wraps every `ApiClient` promise rejection, a single `.catch` point inside `ApiClient`'s methods, not one per controller, and converts it into a toast plus an entry the Automation Runs tab can also read. A `401` produces no toast, because `FE-AUTH-03` redirects to sign in instead, and a `429` shows the server's wait message. Run-level and general request errors surface this way, never only to the browser console, per the **user-interface doc**'s error-surfacing rules and REQ-FE-02.

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
| 1b | Search Profiles                | `SearchProfileCtrl`           | `ApiClient` (`search_profile`, `search_schedule`)                                                                                | its own route from Tracks, `FE-RTE-02`; generic `PUT /api/v1/search_profile/{track_id}` and `/search_schedule/{track_id}` |
| 2 | CVs                               | `CvsCtrl`                       | `ApiClient` (`cv`)                                                                                            | its own route from Tracks or Applications, `FE-RTE-02` |
| 3 | Posts                              | `PostsCtrl`                       | `ApiClient` (`post`), `ApiClient.triggerSearchRun`, `RunPoller`, `ManualPostDialog`, `ErrorService`                     | the page offers no promote action, since promotion is a system action (Workflow 4); see note below |
| 4 | Manual Post Entry                   | `ManualPostDialog` (service) + `manual-post-modal` directive               | `ApiClient.promoteManualPost`                                                                                       | `API-EP-01`; dialog opened from Posts, `FE-RTE-04` |
| 5 | Leads                                 | `LeadsCtrl`                           | `ApiClient` (`lead`, `batch`, `createManualLead`), `ConfirmDialog`                                                       | single-lead stage transitions are generic `PUT /api/v1/lead/{id}` (`API-HOOK-01` is transparent, `FE-SVC-02`) and the `TOAPPLY` column's Apply and Drop are `ApiClient.batch('lead', rows)`; tab filters, layouts, and sorts are client-side on one `list('lead')` fetch, not one request per tab; the expiry-warning indicator is computed client-side from the fetched `deadline` field, not a separate API flag |
| 6 | Lead Detail                            | `LeadDetailCtrl`                        | `ApiClient` (`lead`, `offer`, read-only `lead_event` per `FE-SVC-03a`), `ConfirmDialog`, `OfferDialog`                   | opened as a panel from Leads, `FE-RTE-02`; the Track drop-down reads the active tracks from `LeadsCtrl`'s `list('track')` fetch; a stage move to `OFFER` opens the offer dialog, and every action ends in `changed()`, which reloads the panel and the list |
| 7 | Applications                             | `ApplicationsCtrl`                        | `ApiClient` (`lead` for the apply queue, `application`), `ApiClient.triggerApplyRun`, `RunPoller`, `ConfirmDialog`     | `API-EP-05`; a per-row drop is `ApiClient.update('lead', id, {stage: 'CLOSED', close_reason: 'dropped'})` |
| 8 | MCF connection pop-up                     | `McfConnect`                                | `ApiClient` (`mcf_attempt`, `mcf_session`), `<mcf-nav-icon>`, `<mcf-connect-modal>`, `mcf-link`                            | QR login, account confirmation, status, disconnect, authenticated Open, and native fallback |
| 9 | Offers | `OffersCtrl` | `ApiClient` (`offer`, `lead`), `OfferDialog` | history via `list('offer')` |
| 10 | Sign in | `AuthCtrl` | `AuthService` | public route, `FE-RTE-03`; Google button is a plain link to `API-EP-13` |
| 11 | Sign up | `AuthCtrl` | `AuthService` | public route; live password rule checklist, `FE-AUTH-05` |

Lead creation has no user-facing promote method. The search process calls `POST /api/v1/lead` (`API-HOOK-01`) as a system caller, and the manual add on the Leads page (row 5) posts to `POST /api/v1/lead/manual` through `ApiClient.createManualLead`. `API-HOOK-01`'s invariant, that a `post_id` already promoted is rejected per the **data model**'s uniqueness rule, is enforced server-side on the `POST /api/v1/lead` call.

`McfConnect` owns one polled state object for the latest attempt and current session. `<mcf-nav-icon>` renders the red, amber, or green status and toggles `<mcf-connect-modal>`. The modal renders the QR, account confirmation, current connection state, Open, and Disconnect controls. The `mcf-link` attribute intercepts MCF links only while the session is valid. Otherwise native `target="_blank"` navigation remains unchanged.

## 8. Testing hooks (supports `ARCH-TEST-05`, `ARCH-TEST-09`)

**FE-TEST-01** **Every interactive control carries a `data-testid` attribute**, kebab-case, scoped `{screen}-{element}[-{id}]`, for example `posts-run-search-btn`, `lead-card-{id}-close-btn`, `applications-run-apply-btn`. The authentication controls use the ids `user-section`, `user-avatar`, `user-photo`, `user-initials`, `user-menu`, `user-name`, `user-menu-upload`, `user-menu-photo-input`, `user-menu-remove-photo`, `user-menu-logout`, `signin-email`, `signin-password`, `signin-submit`, `signin-google`, `signin-error`, `signup-name`, `signup-email`, `signup-password`, `signup-submit`, `signup-error`, and `signup-rule-<code>` for each password rule row. This is fixed here rather than left to whoever writes each template, so the two Playwright tiers' DOM assertions (`ARCH-TEST-05` full-stack, `ARCH-TEST-09` frontend-silo) have a stable, deliberate contract to assert against instead of reverse-engineering one from markup after the fact. This is the same rationale `ARCH-BOT-01`'s skill reference gives for MCF's own markup, applied to this app's own templates.

**FE-TEST-02** Because `FE-SVC-01` makes `ApiClient` the sole `/api` call site, `ARCH-TEST-09`'s frontend-silo mocking, `page.route('**/api/**', ...)` fulfilled from `tests/fixtures/api/*.json`, requires no test-only conditional anywhere in `app/`. The same `ApiClient` code runs against the real backend, `ARCH-TEST-05`, tier 2, and the mocked one, tier 1b, with the interception happening entirely at the network layer Playwright already controls. The mocked tier answers `GET /api/v1/auth/me` with a canned user, and the full-stack tier signs in as a seeded account through the real sign-in endpoint.
</content>

## 9. Authentication and the user section

**FE-AUTH-01** **One `AuthService` owns the signed-in user.** It holds `user`, a `ready` promise resolved by the first `ApiClient.me()` call at app start, and `config`, the result of `authConfig()`. Methods are `require()`, which resolves when signed in and otherwise rejects with `'unauthenticated'`, `redirectIfSignedIn()`, `signin(body)`, `signup(body)`, `signout()`, `uploadPhoto(file)`, `removePhoto()`, and `initials()`. `signin` and `signup` set `user` on success, and `signout` calls the API and then clears `user`. `initials()` returns the first letters of the first two words of the name, uppercased, or the first letter of the email when the name is empty.

**FE-AUTH-02** **Sign-in state is never stored in the browser.** The session lives in the HttpOnly cookie, which script cannot read. `AuthService.user` is memory only and is rebuilt from `me()` on every full page load, so no token, password, or session value reaches `localStorage`, `sessionStorage`, or any JavaScript variable other than the user object.

**FE-AUTH-03** **One `$http` interceptor ends the session client-side.** A `401` from any call other than `auth/signin`, `auth/signup`, and `auth/me` clears `AuthService.user` and redirects to `/signin?next=<current path>`, so a session that expired mid-use returns the user to sign in without an error toast. The startup `auth/me` call is exempt, because the route guard (`FE-RTE-03`) handles a signed-out start. `AuthCtrl` accepts a `next` value only when it starts with a single `/`, which keeps the return path same-origin.

**FE-AUTH-04** **The `<user-menu>` directive renders the user section inside `nav-bar`.** It shows only while `AuthService.user` is set, and the nav links show only then as well. The circle button is 32 pixels and shows an `<img>` bound to `user.photo_url`, cropped by `border-radius: 50%` and `object-fit: cover`, or the initials when `photo_url` is null. The menu holds the name and email, `Upload photo`, `Remove photo` when a photo exists, and `Log out`. Upload uses a hidden file input accepting `image/png,image/jpeg,image/webp`, refuses a file over 2 MB before sending, and posts through `uploadPhoto` with `Content-Type` left for the browser to set. `Log out` calls `signout()` and navigates to `/signin`, and each guarded route reloads its own state on the next visit.

**FE-AUTH-05** **`AuthCtrl` serves both pages.** Sign in has email and password inputs, a submit button, a `Continue with Google` link to `/api/v1/auth/google/start?next=<next>` shown only when `config.google_enabled`, and a link to Sign up. Sign up has name, email, and password inputs, a live checklist of the password rules, and a link back. The checklist mirrors the server's rules for feedback only, and the server response stays authoritative. Field errors render through `ErrorService.fieldMessage` per `FE-ERR-02`, and the `rules` array of a rejected password marks the matching checklist rows. The `error` query parameter maps to a message.

| id | error code                | message                                          |
| -- | ------------------------- | ------------------------------------------------ |
| 01 | `google_denied`           | Google sign-in was cancelled.                    |
| 02 | `google_invalid`          | Google sign-in could not be verified. Try again. |
| 03 | `google_unavailable`      | Google could not be reached. Try again later.    |
| 04 | `google_email_unverified` | The Google account email is not verified.        |
