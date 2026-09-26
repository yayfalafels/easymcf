# Easy MCF POC Local - API Reference

Release `010` design. Source: [docs/releases/010/design/010-api.md](https://github.com/yayfalafels/easymcf/blob/main/docs/releases/010/design/010-api.md).

## Contents

- [Purpose](#purpose)
- [Out of scope](#out-of-scope)
- [References](#references)
- [1. Conventions](#1-conventions) — `API-CAT-01..03`
- [2. Named endpoint index](#2-named-endpoint-index) — `API-EP-01..17`
- [3. Resources](#3-resources)
  - [Accounts, `user` and `auth_session`](#accounts-user-and-auth_session)
  - [`role`](#role)
  - [`track`](#track)
  - [`search_profile`](#search_profile)
  - [`cv`](#cv)
  - [`post`](#post)
  - [`post_track` and `match_score`](#post_track-and-match_score)
  - [`lead`](#lead)
  - [`lead_note`](#lead_note)
  - [`lead_event`](#lead_event)
  - [`offer`](#offer)
  - [`application`](#application)
  - [`run_log`](#run_log)
  - [`mcf_session`](#mcf_session)

## Purpose

The concrete backend API surface: every endpoint, its request/response shape, and which entities get the generic CRUD pattern unmediated versus behind table-specific validation versus a named endpoint entirely. The **requirements** and the **architecture design** state the *principle*, per `REQ-PLAT-01`/`ARCH-RUN-10`: generic CRUD is the default shape for a table, leaving room for entities that need something else. This document is the reference other design docs and implementation code consume for the concrete surface. The **frontend app design**'s API-client service wraps it call-for-call, and the **backend-api skill** points here for anything beyond the generic pattern. It also resolves the gap the **issues log**'s ISS-02 identified between `REQ-PLAT-01`'s literal wording and the lead/apply state-machine's invariants.

## Out of scope

- The Flask blueprint/decorator implementation itself, the schema-validation library choice, and the SQL for each hook — milestone 09-11 (functional builds) implementation detail, not design.
- Re-deciding any `ARCH-*` topology/storage/testing decision — this document only elaborates the endpoint surface `ARCH-RUN-10` already delegates to it.

## References

- **requirements**: [010-01-requirements.md](https://github.com/yayfalafels/easymcf/blob/main/docs/releases/010/design/010-01-requirements.md) — REQ-PLAT-01 (the generic-CRUD default this elaborates), REQ-CRM-01..08 and REQ-APPLY-01..11 (the invariants behind every hook and named endpoint below)
- **architecture design**: [010-architecture.md](architecture.md) — `ARCH-RUN-09/10` (the one-process topology and `/api/v1` prefix these endpoints are mounted under), `ARCH-RUN-03` (the run-in-flight guard `API-EP-04`/`05` cite), `ARCH-AUTH-01..10` (the session, ownership, and Google flow decisions the account endpoints and the ownership rule implement), `ARCH-BOT-05` (the apply-retry env-var override `API-EP-05` cites)
- **data model**: [010-data-model.md](data-model.md) — the entity/field definitions this surface reads and writes. Field lists aren't repeated here beyond what an example needs
- **workflows**: [010-workflows.md](workflows.md) — Workflow 4 (promote), 5 (lead lifecycle), 6 (apply queue/run/drop), 7 (apply-outcome propagation), 8 (session) — the process logic each hook or named endpoint implements
- **frontend app design**: [010-frontend-app.md](frontend-app.md) — the AngularJS `ApiClient` service that wraps every endpoint below. Consult it for how a screen calls this surface, rather than for the surface's own definition
- **issues log**: [010-issues.md](https://github.com/yayfalafels/easymcf/blob/main/docs/releases/010/010-issues.md) — ISS-02 (generic CRUD vs. lead state-machine rules), the audit finding this document resolves
- **user interface design**: [010-user-interface.md](user-interface.md) — the screens and controls that call each endpoint below
- **backend-api skill**: [.claude/skills/easymcf-backend-api/SKILL.md](https://github.com/yayfalafels/easymcf/blob/main/.claude/skills/easymcf-backend-api/SKILL.md) — the agent-facing skill that points here for anything beyond the generic CRUD pattern

Decisions carry an `API-*` id (grouped `CAT` classification, `HOOK` per-table hook behavior, `EP` named endpoint), mirroring the `REQ-*`/`ARCH-*` grouping convention.

## 1. Conventions

**Base URL** `http://127.0.0.1:5000/api/v1` (`ARCH-RUN-09/10`). Versioned by path segment (`v1`) rather than a header or content-type scheme. This is cheap to add now and avoids a breaking change to every client the day the surface needs to change. Every route except the public set below requires a signed-in user, identified by the HttpOnly `easymcf_session` cookie (`ARCH-AUTH-02`). The process binds loopback only (`ARCH-NET-01`).

**Format** `Content-Type: application/json` on every request and response body that has one.

**Errors** — every non-2xx response is a JSON object naming what went wrong:

```json
{ "error": "validation_error", "field": "track_id", "message": "track_id is required" }
```

| status | error                    | when                                                                      |
| ------ | ------------------------ | ------------------------------------------------------------------------- |
| 400    | `validation_error`       | missing/malformed required field, bad type or date format                 |
| 401    | `unauthenticated`        | no valid sign-in session cookie on a route that requires one              |
| 403    | `forbidden_origin`       | a `POST`, `PUT`, or `DELETE` whose `Origin` names another host            |
| 404    | `not_found`              | the record is missing or belongs to another user, or `{table}` is unknown |
| 409    | `conflict`               | a uniqueness/FK/state-machine invariant blocks the write                  |
| 413    | `payload_too_large`      | an upload exceeds its size limit                                          |
| 415    | `unsupported_media_type` | an upload is not an accepted image type                                   |
| 429    | `too_many_attempts`      | repeated failed sign-ins for one email, with `Retry-After`                |

**Authentication and ownership.** Two rules apply to every endpoint in this document.

01. **authentication.** The public routes are `GET /health`, `POST /auth/signup`, `POST /auth/signin`, `POST /auth/signout`, `GET /auth/config`, `GET /auth/google/start`, and `GET /auth/google/callback`. Every other route answers `401 unauthenticated` without a valid session cookie, and never reveals whether the route exists.
02. **ownership.** Every read, update, and delete is filtered to the signed-in user's own rows, and a row outside that filter answers `404`, exactly as a missing row does. `track`, `cv`, `lead`, `run_log`, and `mcf_session` are owned directly. `search_profile`, `search_schedule`, `post_track`, and `match_score` are owned through their track, and `lead_note`, `lead_event`, `offer`, and `application` through their lead. `post` is shared, read-only, and visible through the user's tracks and leads, and `role` is a shared catalog. The owner is never a request field. A create sets `user_id` on the server from the session, so a body carrying `user_id` is `400` as not writable, and a create that names a parent row, such as `track_id` or `lead_id`, answers `404` unless the caller owns the parent. Search filters cannot reach across users.

**Three endpoint categories, beyond a simple generic-versus-bespoke split.** `REQ-PLAT-01`'s generic CRUD shape is the default for a table. It does not mandate that every table's every write reach the database unmediated:

- **API-CAT-01 pure generic** — the table has no invariant beyond schema/type/FK validation. The generic CRUD blueprint serves it with zero table-specific code.
- **API-CAT-02 generic-shaped, hook-backed** — the same URL and verb a caller would expect from CAT-01, but the table registers a hook the blueprint calls before or after the write, or before serializing a read, to enforce an invariant or apply a side effect. This stays invisible to the caller beyond the errors it can now return.
- **API-CAT-03 named** — the operation spans more than one row-level create/update, triggers a background process, or has no natural single-table CRUD shape at all. It gets a purpose-specific endpoint that internally reuses the same persistence primitives rather than duplicating them.

**The seven generic shapes** — the pattern every CAT-01 table gets in full, and every CAT-02 table gets in part (its own entry in section 3 says which verbs are actually open):

| method | path                     | purpose                                       |
| ------ | ------------------------ | --------------------------------------------- |
| GET    | `/api/v1/{table}/{id}`   | fetch one row by id                           |
| PUT    | `/api/v1/{table}/{id}`   | update one row by id                          |
| DELETE | `/api/v1/{table}/{id}`   | delete one row by id                          |
| POST   | `/api/v1/{table}`        | create one row                                |
| POST   | `/api/v1/{table}/batch`  | create/update multiple rows in one request    |
| GET    | `/api/v1/{table}/search` | list/filter rows — query params are filters   |
| POST   | `/api/v1/{table}/delete` | delete multiple rows matched by a filter body |

Example against a pure-generic table:

```
GET /api/v1/track/3
→ 200 {"id": 3, "user_id": 1, "role_id": 1, "seniority": "senior", "default_cv_id": 2, "is_active": true}

PUT /api/v1/track/3 {"is_active": false}
→ 200 {"id": 3, "user_id": 1, "role_id": 1, "seniority": "senior", "default_cv_id": 2, "is_active": false}
```

Archiving a track (REQ-SRCH-10, the **user interface design** page 1) is exactly this generic `PUT`. No named action exists for it.

## 2. Named endpoint index

Every operation outside the seven generic shapes, in full below (section 3). An endpoint that is neither a generic shape nor in this table is a design gap to raise with the architect, never a drift to build around silently. `ARCH-RUN-10` treats this table as the single source of truth for that boundary. Named endpoints trigger runs, establish and open MCF sessions, manually add a post, and sign in or manage an account. Creating a `lead` uses the generic-shaped, hook-validated `POST` shown in section 3's `lead` entry, rather than a dedicated named endpoint, and moving many leads at once uses the generic `batch` shape opened on `lead`. `API-EP-02` and `API-EP-03` are retired and their ids are not reused. The apply queue is the set of open `TOAPPLY` leads, and the user prunes it through that `batch`.

| id        | method + path                            |
| --------- | ---------------------------------------- |
| API-EP-01 | `POST /api/v1/posts/manual`              |
| API-EP-04 | `POST /api/v1/runs/search`               |
| API-EP-05 | `POST /api/v1/runs/apply`                |
| API-EP-06 | `POST /api/v1/mcf_attempt/start`         |
| API-EP-07 | `GET /api/v1/health`                     |
| API-EP-08 | `POST /api/v1/auth/signup`               |
| API-EP-09 | `POST /api/v1/auth/signin`               |
| API-EP-10 | `POST /api/v1/auth/signout`              |
| API-EP-11 | `GET /api/v1/auth/me`                    |
| API-EP-12 | `GET /api/v1/auth/config`                |
| API-EP-13 | `GET /api/v1/auth/google/start`          |
| API-EP-14 | `GET /api/v1/auth/google/callback`       |
| API-EP-15 | `PUT /api/v1/users/{id}/photo`           |
| API-EP-16 | `DELETE /api/v1/users/{id}/photo`        |
| API-EP-17 | `GET /api/v1/users/{id}/photo`           |
| API-EP-18 | `GET /api/v1/mcf_attempt/{id}/qr`        |
| API-EP-19 | `GET /api/v1/mcf_attempt/{id}/qr_link`   |
| API-EP-20 | `POST /api/v1/mcf_attempt/{id}/confirm`  |
| API-EP-21 | `DELETE /api/v1/mcf_attempt/{id}`        |
| API-EP-22 | `POST /api/v1/mcf_session/open`          |

## 3. Resources

### Accounts, `user` and `auth_session`

Neither table is a generic resource. `user` holds a password hash and a Google subject that no read may expose, and `auth_session` holds token digests, so accounts are reached only through the named endpoints `API-EP-08..17`. Endpoints that return a user return this object, which never includes the hash, the subject, or the digest:

```json
{ "id": 2, "name": "Sam Second", "email": "second.user@example.test",
  "photo_url": "/api/v1/users/2/photo?v=1a2b3c4d", "auth_methods": ["password", "google"] }
```

`photo_url` is `null` when the user has no photo. `auth_methods` lists `password` when a hash exists and `google` when a Google subject exists.

**API-EP-08 `POST /api/v1/auth/signup`** (REQ-AUTH-01, REQ-AUTH-02)

```json
// request
{ "name": "Sam Second", "email": "second.user@example.test", "password": "Correct-Horse-9!" }

// 201 response, plus Set-Cookie: easymcf_session=...; HttpOnly; SameSite=Lax; Path=/
{ "id": 2, "name": "Sam Second", "email": "second.user@example.test", "photo_url": null, "auth_methods": ["password"] }
```

`400` names the failing `field`. A password that breaks the policy answers `400 {"error": "validation_error", "field": "password", "message": "Password does not meet the requirements.", "rules": ["too_short", "no_symbol"]}` listing every unmet rule from `too_short`, `too_long`, `no_lowercase`, `no_uppercase`, `no_digit`, `no_symbol`, and `contains_identity`. A duplicate email, compared in lowercase, answers `409` with `field: "email"`. The response signs the new user in and creates their `mcf_session` row with `status='missing'`.

**API-EP-09 `POST /api/v1/auth/signin`** (REQ-AUTH-03)

```json
// request
{ "email": "second.user@example.test", "password": "Correct-Horse-9!" }
```

`200` returns the user object and the session cookie. A wrong password, an unknown email, a disabled account, and an account with no password all answer the same `401 {"error": "invalid_credentials", "message": "Email or password is incorrect."}`. After `SIGNIN_MAX_FAILURES` failures for one email inside `SIGNIN_WINDOW_S`, the next attempt answers `429 too_many_attempts` with a `Retry-After` header, even with the correct password.

**API-EP-10 `POST /api/v1/auth/signout`** (REQ-AUTH-05)

`204`, always. It deletes the caller's `auth_session` row when one exists and expires the cookie.

**API-EP-11 `GET /api/v1/auth/me`** (REQ-AUTH-05)

`200` with the user object, or `401`.

**API-EP-12 `GET /api/v1/auth/config`**

`200 {"google_enabled": true}`. `google_enabled` is false when the OAuth client id or the client secret file is absent. The sign-in page reads it to decide whether to show the Google button.

**API-EP-13 `GET /api/v1/auth/google/start?next=/leads`** (REQ-AUTH-04)

`302` to the identity provider's authorization endpoint with `state`, `nonce`, and a PKCE `code_challenge`. `next` is kept only when it is a same-origin path, one that starts with a single `/`. `404 google_not_configured` when Google sign-in is unavailable.

**API-EP-14 `GET /api/v1/auth/google/callback`** (REQ-AUTH-04)

Always `302`. Success creates the sign-in session cookie and redirects to `next`, or to `/`. Any failure redirects to `/signin?error=<code>` and creates no user and no session.

| id | error code                | meaning                                                  |
| -- | ------------------------- | -------------------------------------------------------- |
| 01 | `google_denied`           | the user cancelled at the provider                       |
| 02 | `google_invalid`          | state, nonce, or the id token failed validation          |
| 03 | `google_unavailable`      | the provider could not be reached                        |
| 04 | `google_email_unverified` | the identity has no verified email                       |

The linking rules are evaluated in order. A user with this Google subject signs in. A user with this email and a verified identity is linked by setting `google_sub`. Otherwise a new user is created with a null password hash. The picture claim becomes the initial photo when the user has none.

**API-EP-15 `PUT /api/v1/users/{id}/photo`** (REQ-AUTH-08)

`multipart/form-data` with one part named `photo`. The service accepts JPEG, PNG, or WebP up to `PHOTO_MAX_BYTES`, center-crops to a square, resizes to 256 by 256, and stores a PNG. `200` returns the user object with the new `photo_url`. `400` when the part is missing, `413` over the size limit, `415` when the bytes are not an accepted image or disagree with the declared content type, and `404` when `{id}` is not the caller's id.

**API-EP-16 `DELETE /api/v1/users/{id}/photo`** (REQ-AUTH-08)

`200` with the user object and `photo_url: null`. `404` when `{id}` is not the caller's id.

**API-EP-17 `GET /api/v1/users/{id}/photo`** (REQ-AUTH-08)

`200 image/png` with `Cache-Control: private, max-age=31536000, immutable`, since the `v` query value changes with each new file. `404` when `{id}` is not the caller's id or the user has no photo.

### `role`

CAT-01 generic. Fields: `id`, `name`, `description`, per the **data model**. No restrictions beyond schema validation.

### `track`

CAT-02 hook, create only. `user_id` is set from the session on create and is never a request field. The create hook additionally writes that track's default `search_profile` row (`keywords` set to its role name) and its default `search_schedule` row (`schedule_enabled=false`), both in the same transaction, per Workflow 1 — a plain generic create would leave a track with neither, and search-profile edit still has nothing to `PUT` against. `GET`/`search`/`PUT`/`DELETE` stay plain generic. Archive/unarchive is the plain `PUT {"is_active": false}` shown in section 1, never a named action. There is no other invariant beyond the visibility filtering the **user interface design**'s track selectors already apply at read time.

### `search_profile`

CAT-01 generic. Its primary key is `track_id` (1:1 extension of `track`, REQ-SRCH-01), so every generic path is `/api/v1/search_profile/{track_id}`, not a separate numeric id.

### `search_schedule`

CAT-01 generic, the same shape as `search_profile`. Its primary key is `track_id` (1:1 extension of `track`, REQ-SRCH-11), so every generic path is `/api/v1/search_schedule/{track_id}`. `schedule_interval_hours` rejects a value below `1` with `400`, per the **data model**. `next_run_at` is a plain writable field: leaving it null while setting `schedule_enabled=true` means due now, and the scheduler owns it from the first tick that fires it (`ARCH-SCHED-03`).

### `cv`

CAT-01 generic, `user_id` set from the session on create, and a label unique within its owner (a duplicate is `409`). `DELETE /api/v1/cv/{id}` runs a delete hook (11.IS.19) with three outcomes. A label in live use, the default of an active track or the effective CV of a queued lead, answers a `409` naming those uses. A label that only attempt history or an archived track uses is retired, `is_active` set to 0, and answers `200` with the row. A label nothing references is deleted, `204`. Adding a label equal to a retired one reactivates that row. Pickers offer active labels only.

```json
409 { "error": "conflict", "message": "CV '13.2' is still in use as the default of active track Data Analyst (mid); choose another CV there first", "in_use": {"track_ids": [1], "lead_ids": []} }
```

Every other CAT-01 table with an inbound FK keeps the generic blueprint's translation: a delete that fails the FK constraint answers `409` with `referenced_by`, each `child_table.column` and its row count.

### `post`

CAT-02 hook (`API-HOOK-03`). `GET`/`search` generic, returning only posts visible to the caller through one of their tracks or leads. A post is read-only to every user, so `PUT`/`DELETE` are not exposed at the API surface at all. A post's fields past creation are written only internally by the search/detail-pass service. `POST /api/v1/post` is not exposed generically either: creating a post is always `API-EP-01`, because a bare generic create would produce a post with no scored `post_track` rows, breaking REQ-SRCH-07.

**API-EP-01 `POST /api/v1/posts/manual`** (REQ-SRCH-07)

```json
// request
{ "track_id": 3, "position_title": "Data Engineer", "company_name": "Acme Pte Ltd", "url_ref": "https://...", "salary_high": 9000, "posted_date": "2026-08-16" }

// 201 response
{ "post": { "id": "MyCareerFutures-abc123-2026-08-16", "src_method": "manual", "position_title": "Data Engineer", "company_name": "Acme Pte Ltd", "is_open": true },
  "post_track": { "post_id": "MyCareerFutures-abc123-2026-08-16", "track_id": 3, "search_match": false },
  "lead_id": 88 }
```

`track_id` names the one track the post belongs to and is required. Creates the `post` row (`src_method='manual'`) and that track's `post_track`/`match_score` row pair (`search_match=false`, `match_score=1.0`, `score_method='manual_v1'`) in the same request, then promotes the pair to a lead at `TOAPPLY` and returns its id alongside the post and pairing, so the dialog never issues a second request. When the derived id already exists and the caller cannot see that post, the service reuses the existing row and writes only the caller's pairing, answering `201`. When the caller can already see it, the answer is `409` naming the existing post.

### `post_track` and `match_score`

Neither is exposed as its own generic resource. Both are written only internally, by the search run's persist step and by `API-EP-01`, never by a bare client-facing `POST`/`PUT /api/v1/post_track` or `/api/v1/match_score` — a client-writable path would let a caller create the second pairing REQ-SRCH-08 rules out. `match_score.match_score` is written as the fixed `1.0` on every insert this release, and the column itself stays a plain, unconstrained real number so a future differentiating scoring method can write a real value later under its own `score_method`, without a schema change. Their values are read back only as extra columns on the joined `post` read below, never as a standalone resource.

### `lead`

CAT-02 hook (`API-HOOK-01`), the richest entry in this document.

01. `GET`/`search` generic, subject to the read-time behavior below.
02. `PUT` generic-shaped and hook-validated.
03. `POST` generic-shaped and hook-validated. This is how the search process promotes a post into a lead, a system caller that the frontend never uses. There is no separate named "promote" endpoint.
04. `POST /api/v1/lead/manual` hook-validated, the manual add of a lead with a copy of its post (see Manual create below).
05. `POST /api/v1/lead/batch` the generic `batch` shape opened on `lead` (see Batch below).
06. `DELETE` not exposed. A lead is closed via `PUT` with `stage='CLOSED'`, never deleted.

**Create** — `POST /api/v1/lead`:

```json
// request
{ "post_id": "MyCareerFutures-abc123-2026-08-01", "track_id": 3 }
```

`post_id` and `track_id` are both required (`400` naming the missing one otherwise). The post must be visible to the caller and the track owned by the caller, or the answer is `404`. The service sets `user_id` from the session and copies the post's `position_title`, `company_name`, and `url_ref` onto the lead. It copies `expected_salary_sgd` from the track's `search_profile.min_salary` (`NULL` when the profile has none). If the caller already holds a `lead` on `post_id`, per the **data model**'s uniqueness rule, the write is rejected:

```json
409 { "error": "conflict", "message": "post MyCareerFutures-abc123-2026-08-01 is already promoted", "lead_id": 88 }
```

This `409` is what a second promotion of one post meets, and the Posts screen's `already a lead` row state in the **user interface design** reads the same fact. On success the row gets `status='OPEN'`, `stage='TOAPPLY'`, `created_at`/`updated_at` set, and one `lead_event(event_type='stage_change', detail='promoted to TOAPPLY')` row is written — creation is just another accepted write, subject to the same event-logging rule as every update below. The promotion event records `stage_from=NULL` and `stage_to='TOAPPLY'`.

**Manual create** — `POST /api/v1/lead/manual` with `track_id`, `position_title`, `company_name`, and optional `url_ref`, `salary_high`, `posted_date`, and `expected_salary_sgd`: creates a `post` copy (`source='Manual'`, `src_method='manual'`) on the server and its lead in one transaction, with the lead's `position_title`, `company_name`, and `url_ref` taken from the request, at `status='OPEN'`, `stage='APPLIED'`, with `applied_date` set to the creation date. The first `lead_event` records `stage_from=NULL`, `stage_to='APPLIED'`, with detail `added manually at APPLIED`. The `expected_salary_sgd` default and the initial `deadline` follow the same rules as the system create.

**Batch** — `POST /api/v1/lead/batch` is the generic `batch` shape (`POST /api/v1/{table}/batch`, a `rows` list) opened on `lead` with a hook that applies stage moves. The body is `{ "rows": [ {"id": 12, "stage": "APPLIED"}, {"id": 47, "stage": "CLOSED", "close_reason": "dropped"} ] }` with 1 to 200 rows, and an empty or oversized list, a repeated `id`, or a key other than `id`, `stage`, and `close_reason` is `400` with `field: rows`. The service applies the rows in order inside one transaction through the same write function as `PUT`, so each row passes the transition table and the offer gates and writes its own `lead_event`. The first illegal row is `409` with that row's `lead_id`, and no lead changes. A valid batch answers `200` with the updated `lead` rows in request order.

**Update** — every `PUT /api/v1/lead/{id}`:

- a `stage` change must be a legal transition per the **workflows**' Workflow 5 state diagram. An illegal one is `409`. A `stage` equal to the current stage leaves the lead as it is.
- `close_reason` is required, and checked against the eight-value enum (`offer_accepted`, `rejected`, `withdrawn`, `expired`, `cancelled`, `duplicate`, `apply_failed`, `dropped`), whenever `stage` becomes `CLOSED`. Omitting it on a closing write is `400`.
- `stage: "OFFER"` is `409` naming the offer requirement, because a lead reaches `OFFER` only through `POST /api/v1/offer`. A `stage: "CLOSED"` on a lead at `OFFER` is `409` naming the offer action, because the offer status closes that lead. `stage: "INTERVIEW"` on a `CLOSED` lead is the re-open and is legal only when the lead's closing event ran from `OFFER`: it sets `status='OPEN'`, clears `close_reason`, and writes `stage_from='CLOSED'`, `stage_to='INTERVIEW'`.
- every other field (`position_title`, `company_name`, `url_ref`, `deadline`, `applied_date`, `first_attempt_date`, `last_contact_date`, `expected_salary_sgd`, `track_id`, `cv_id`) is unrestricted, `position_title` and `company_name` accept a string of at least one character, `url_ref` accepts `null` or a string matching `^https?://\S+$` (`400` with `field` otherwise), `expected_salary_sgd` accepts an integer `>= 0` or `null` (`400` with `field` otherwise), `track_id` names an existing, active track (`400` with `field: track_id` for an unknown or archived track), and `cv_id`, the per-lead CV override, accepts `null` or a CV owned by the caller (`404` otherwise). A re-assignment leaves the stage, deadline, and expected salary alone. Notes are not written here. See `lead_note` below.
- every accepted write, create or update, appends one `lead_event` row, with `event_type` inferred from what changed: `stage_change` for a `stage`/`close_reason` change, `deadline_changed` for `deadline`, `contact_logged` for `last_contact_date`, `field_edited` for a `position_title`/`company_name`/`url_ref`/`applied_date`/`first_attempt_date`/`expected_salary_sgd`/`track_id`/`cv_id` change in a request that carries only those fields. The event's `detail` field names the specific field and value in every case. When the system moves `deadline`, it appends one further `deadline_changed` row. It also refreshes `updated_at` from the primary event's timestamp. This is REQ-CRM-08's single code path for `lead` fields, and every `lead` write flows through it. Every event records the lead's stage before the write in `stage_from` and after it in `stage_to`. The two are equal for writes that leave the stage alone, and `detail` lists the changed fields other than `stage`.

**Read** — `GET`/`search` evaluates auto-expiry (REQ-CRM-05) against the injectable clock (`ARCH-STO-05`) before serializing: any `lead` still `status='OPEN'` whose `deadline` is before the current date is closed (`status`/`stage='CLOSED'`, `close_reason='expired'`) as a write-on-read side effect, by calling into this same `PUT` write path internally so the closing `lead_event` is written the same way any other close is, mirroring the apply-outcome propagation pattern below. `deadline` itself is maintained across the lead's lifecycle per REQ-CRM-05 (derived from the post at creation, rolling at `CALLBACK` and `INTERVIEW`, and the open offer's deadline at `OFFER`). This is what "evaluated on each backend list call", per the **workflows**' Workflow 5, means concretely, and why the check runs on the request path. The closing event records the stage at expiry in `stage_from` and `CLOSED` in `stage_to`, and an expiring lead at `OFFER` also moves its open offer to `expired` in the same transaction. Each `lead` row carries the read-only derived fields `latest_note` (the newest `lead_note` text, `NULL` when none), `offer_id`, `offer_amount_sgd`, `offer_date`, `offer_deadline`, and `offer_status` (the lead's open offer, `NULL` when none), and `closed_from` (the `stage_from` of the latest event with `stage_to='CLOSED'`, `NULL` for an open lead), returned by subqueries in the resource `SELECT` and never stored.

A manual stage transition or close, the **user interface design**'s Lead Detail "move to next stage" / close-with-reason controls, is a plain `PUT /api/v1/lead/{id}` carrying the new `stage`/`close_reason`, or one row of `POST /api/v1/lead/batch`. It is never a named endpoint. Once this hook exists, keeping every transition generic-shaped is what actually delivers `REQ-PLAT-01`'s "no bespoke endpoint per feature" intent.

### `lead_note`

CAT-02 hook, grouped with `lead` under `API-HOOK-01`. `GET`/`search` generic. `POST /api/v1/lead_note { "lead_id": 88, "note": "Interview scheduled with hiring manager" }` creates the row and, as a side effect, appends one `lead_event(event_type='note_edited', detail=<note excerpt>)` row against the same lead, refreshing its `updated_at`. This is the same append-instead-of-overwrite shape `lead_event` already uses. `PUT`/`DELETE` are not exposed. A note, once added, is part of the lead's permanent history. The paired event carries the lead's current stage in both `stage_from` and `stage_to`.

### `lead_event`

CAT-02 hook, grouped with `run_log`/`mcf_session` under `API-HOOK-04` below — `GET`/`search` only. Every row is written internally as a side effect of a `lead` write, described above. There is no `POST`/`PUT`/`DELETE /api/v1/lead_event` at all. Lead Detail's activity history, the **user interface design** page 6, reads this as `GET /api/v1/lead_event/search?lead_id={id}`. Each row exposes `stage_from` and `stage_to`, and both work as `search` filters, for example `GET /api/v1/lead_event/search?lead_id=88&stage_to=CLOSED`.

### `offer`

CAT-02 hook, grouped with `lead` under `API-HOOK-01`. `GET`/`search` generic, `POST` and `PUT` hook-validated, `DELETE` not exposed, so an offer stays in the history.

**Create** — `POST /api/v1/offer`:

```json
// request
{ "lead_id": 12, "offer_date": "2026-09-21", "amount_sgd": 11500, "deadline": "2026-10-05" }
```

`lead_id`, `offer_date`, and `amount_sgd` are required (`400` naming the missing one), and `deadline` defaults to the lead's current `deadline`. The lead must be `OPEN` at `INTERVIEW` (`409` otherwise). One transaction inserts the offer with `status='open'`, moves the lead to `OFFER` with a `lead_event` of `stage_from='INTERVIEW'`, `stage_to='OFFER'`, and sets `lead.deadline` to the offer deadline.

**Update** — `PUT /api/v1/offer/{id}`:

- while `status='open'`, `amount_sgd` and `deadline` are editable, and a deadline edit also sets `lead.deadline` and writes a `deadline_changed` event.
- a `status` of `accepted`, `rejected`, `withdrawn`, or `expired` sets the status and closes the lead in the same transaction (`stage_from='OFFER'`, `stage_to='CLOSED'`) with `close_reason` `offer_accepted`, `rejected`, `withdrawn`, or `expired`. Any other `status` value is `400`.
- an offer whose status is final is read-only, and any write to it is `409`.

**Read** — `GET`/`search` accepts `lead_id` and `status` as filters and returns each offer with `lead_title`, `lead_company`, and `track_id` joined from its lead, so the Offers page needs one request. The auto-expiry pre-pass of `lead` moves the open offer of an expiring lead to `expired`.

### `application`

CAT-02 hook (`API-HOOK-02`). `GET`/`search` generic. `POST`/`PUT`/`DELETE` are not exposed. One row is created per attempt by the apply-run service, internally, and `status`/`error_detail`/`attempted_at` are written only there, via the same persistence call the generic blueprint would use, never a second write path. The queue is the set of open `TOAPPLY` leads, so no application row exists before its attempt.

**Apply-outcome → lead propagation** is internal to the apply-run service, never a client-visible endpoint, per the **workflows**' Workflow 7:

01. `status='applied'` transitions the lead to `APPLIED` (REQ-APPLY-09).
02. `status` in (`post_closed`, `post_unavailable`) closes the lead with `close_reason='apply_failed'` (REQ-APPLY-10).
03. any other status leaves the lead at `TOAPPLY`.

Each of these calls into `lead`'s own write path above, so the resulting `lead_event` is written. One lead-mutation code path serves every caller.

### `run_log`

CAT-02 hook (`API-HOOK-04`). `GET`/`search` generic — the Automation Runs tab and the frontend's `RunPoller` both read a run this way. There is no client `PUT`/`POST`/`DELETE`. Rows are created and updated only by `API-EP-04`/`API-EP-05` and the background thread each one starts, each stamped with the caller's `user_id`. `trigger_source` (`manual` \| `scheduled`) tells the two starts apart: a search run also starts when a `search_schedule` comes due (REQ-SRCH-11, `ARCH-SCHED-01`), through the same service function `API-EP-04` calls, writing `trigger_source='scheduled'` on that row instead.

**API-EP-04 `POST /api/v1/runs/search`** (REQ-SRCH-02)

```json
// request
{ "track_id": 3 }

// 201 response
{ "id": 501, "run_type": "search", "status": "running", "track_id": 3, "started_at": "2026-08-16T09:00:00Z" }
```

Starts the background search thread for that track. Concurrency is `ARCH-RUN-03`'s `UNIQUE` partial index on `run_log(user_id, run_type) WHERE status='running'`. A second trigger of the same `run_type` by the same user while one is in flight receives `409` with the in-flight `run_log.id`. This detail is covered fully in `ARCH-RUN-03` and isn't repeated here.

**API-EP-05 `POST /api/v1/runs/apply`** (REQ-APPLY-03)

No request body — attempts every open lead of the caller at `TOAPPLY`, writing one `application` row per attempt, using the caller's `mcf_session`. Same response shape and concurrency guard as `API-EP-04`. Apply-button retry timing comes from `ARCH-BOT-05`'s env-var overrides rather than a request parameter.

### `mcf_session`

CAT-02 hook (`API-HOOK-04`). One row per user, created at sign-up. `GET /api/v1/mcf_session/search` is generic and returns the caller's single row after reconciling any valid state against its local storage-state file. `PUT`/`POST /api/v1/mcf_session` are blocked because a raw field write could claim `status='valid'` without verified browser state.

**`POST /api/v1/mcf_session/open`** accepts one HTTPS `mycareersfuture.gov.sg` URL. When the caller has a valid saved state, it returns `202 {"mode":"authenticated","url":"..."}` and starts visible Chromium restored from that caller's state. Missing or unusable state returns `200 {"mode":"redirect","url":"..."}` for ordinary new-tab navigation. Other origins return `400` with `field: "url"`. The request cannot select a user, cookie reference, filesystem path, or browser option.

### `mcf_attempt`

CAT-02 hook (`API-HOOK-04`). `GET /api/v1/mcf_attempt/search` returns the caller's attempt history. Writes use named endpoints because starting, confirming, and cancelling an attempt drive the browser state machine.

01. `POST /api/v1/mcf_attempt/start` creates or reuses the caller's active attempt and starts the browser owner thread.
02. `GET /api/v1/mcf_attempt/{id}/qr` returns the current QR image with `Cache-Control: no-store`.
03. `GET /api/v1/mcf_attempt/{id}/qr_link` returns the decoded Singpass app link when available.
04. `POST /api/v1/mcf_attempt/{id}/confirm` accepts or rejects the first account identity confirmation.
05. `DELETE /api/v1/mcf_attempt/{id}` cancels an active attempt or disconnects its established session.

Every attempt endpoint is scoped to the signed-in user. Another user's attempt id returns `404`.

**API-EP-07 `GET /api/v1/health`** (`ARCH-TEST-04`)

No body. `200 {"status": "ok"}` once the app is ready to serve. Used by the mock-e2e test harness's readiness poll. Application code never calls it.

