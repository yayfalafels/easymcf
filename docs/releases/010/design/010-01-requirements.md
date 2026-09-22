# Easy MCF POC Local - Requirements

## Contents

- [Purpose](#purpose)
- [References](#references)
- [Glossary](#glossary)
- [6. Out of scope](#6-out-of-scope)
- [Functional Requirements](#functional-requirements)
  - [Search by keywords](#search-by-keywords)
  - [Job leads tracking](#job-leads-tracking)
  - [Automated apply](#automated-apply)
  - [Accounts and sign-in](#accounts-and-sign-in)
  - [Backend data platform](#backend-data-platform)
  - [Frontend](#frontend)
  - [Local dev/test environment and seed data](#local-devtest-environment-and-seed-data)
- [7. Open questions](#7-open-questions)

## Purpose

This document defines *what* this release must do. It is the input to the milestones that follow it.

01. test strategy.
02. test cases.
03. data model.
04. architecture.
05. design.
06. local dev/test environment.
07. seed data.
08. the three functional builds — job leads tracking, search by keywords, and apply automation.
09. accounts and sign-in, which every functional build's screens and data are scoped by.

Those milestones own *how*: schema, API shape, algorithms, folder structure, test tooling. This document intentionally stops short of that.

__end user__

Job seekers who run the system on their own machine and each hold their own account. A user creates an account, signs in with Google or with an email and password, and sees only their own data.

## References

- **release roadmap**: [release-roadmap.md](../release-roadmap.md), [010-release.md](010-release.md) — easymcf scope, feature table, and stated aim to avoid `mcfpipe`'s pre-MVP infrastructure investment.
- **prototype extraction**: [010-prototype.md](010-prototype.md) — implementation-level extraction from `jobsearch` and `mcfpipe`, sufficient for most of this document and the design stage. Use this first.
- **jobsearch prototype**: `jobsearch/` — the working prototype this release formalizes and re-platforms onto a local Python API + SQLite + AngularJS stack. Go to source directly for detail beyond what the **prototype extraction** captures: `agent.py`, `database.py`, `mcf_profile.py`, `match.py`/`text.py`, `apply.py`, `gsheet/applicationtrackingapp.gs`.
- **mcfpipe reference**: `mcfpipe/` — an earlier, more ambitious rebuild of the same product. Its data model and API design are worth reusing. Its cloud infrastructure pivot to a serverless, NoSQL, multi-tier VPC, IaC, and full CI/CD setup, undertaken before the functional product worked reliably, is the specific mistake release `010` is scoped to avoid. Go to source directly for detail beyond what the **prototype extraction** captures: `docs/data_model.md`, `docs/database_api.md`, `docs/architecture.md`, `docs/enhancements.md`.
- **API reference**: [010-api.md](010-api.md) — the concrete backend endpoint surface, including the per-entity CRUD/hook/named classification.

## Glossary

- **post:** A job listing on `MyCareerFutures` (MCF) discovered by search or entered manually. The shared, read-only source listing for a role, company, and URL. No user edits a post, and a user sees a post through their own tracks and leads.
- **user:** A person with an account. Every track, CV, lead, application, run, and MCF session belongs to exactly one user.
- **account:** A user's identity in the system, holding a name, a unique email address, a photo, and one or both sign-in methods, a password and a linked Google identity.
- **sign-in session:** The server-side record that keeps a user signed in across page loads, ended by sign-out or expiry. It is distinct from the **MCF session**.
- **MCF session:** The authenticated `MCF` cookie a user uploads so apply automation can act on their behalf (REQ-APPLY-06). Each user holds their own.
- **MCF** MyCareerFutures
- **role:** A generic job title/domain (e.g. "Data Engineer"), not tied to any one user.
- **track:** A user's role at a given seniority level. The unit search profiles, CVs, and match scores are organized by.
- **search profile:** The keyword/salary/age search criteria for one track, together with that track's scheduled-run configuration (REQ-SRCH-11).
- **lead:** A single user's personal, trackable instance of a post for one track, holding its own editable copy of the post's position title, company name, URL, and deadline, followed from initial interest through to a closed outcome, either success or fail. Created when the system promotes a qualifying post found by a track's search run, or when the user adds a lead manually. Its first stage is `TOAPPLY` for a system-created lead and `APPLIED` for a manually added one.
- **application:** An MCF automated application that is managed by the app from selected-to-apply to submission success or fail.
- **pipeline status:** Where a post sits in the system's post search acquisition process — distinct from a lead's status/stage.
- **lead status:** Coarse open/closed indicator for a lead — `OPEN` while active, `CLOSED` once resolved.
- **lead stage:** Where an open lead sits within its lifecycle: `TOAPPLY` (default on system promotion, and the apply queue) → `APPLIED` → `CALLBACK` → `INTERVIEW` → `OFFER`. A closed lead's stage instead records why it closed: offer accepted, rejected, withdrawn, expired, cancelled, duplicate, apply failed, or dropped.
- **apply queue:** The open leads at stage `TOAPPLY`. The automated apply run works through them, and the user prunes the queue by dropping leads or by moving leads they have already applied to on to `APPLIED`.
- **offer:** A job offer attached to a lead at `INTERVIEW`, with an amount, an offer date, a deadline, and a status (`open`, `accepted`, `rejected`, `withdrawn`, or `expired`). A lead reaches stage `OFFER` only through an offer, and the offer's final status closes the lead.
- **apply status:** The mechanical outcome of an automated application apply attempt, tracked separately from lead status/stage.
- **lead activity log:** The append-only, timestamped record of updates to a lead, covering stage transitions, contact logged, notes edits, and deadline changes. It backs the lead's `deadline` maintenance and auto-expiry (REQ-CRM-05) and the lead's activity history (REQ-CRM-08).

See each feature section below for the concrete structure and enumerations behind these terms.

## 6. Out of scope

- Cloud deployment (AWS EC2, API Gateway, Lambda)
  - AWS-hosted relational or NoSQL database — deferred to 020/100.
  - Serverless architecture, multi-stack IaC (CloudFormation), containerization (ECR/Fargate).
  - Private network endpoints, VPC/subnet tiering.
  - Fully automated CI/CD pipelines.
- Roles, teams, sharing of leads between users, and any admin console.
- Email verification, password reset by email, and any outbound email.
- Multi-factor authentication for easymcf accounts, sign-in providers other than Google, and account deletion or data export.
- Automated MCF login, including MFA or CAPTCHA handling.
- Multi-step questionnaire application automation.
- Analytics/BI/reporting pipelines (ETL, warehouse, dashboards) beyond in-app run status.
- NLP/semantic-based match scoring (title + job description) — deferred to release `020` (MVP cloud) per the release roadmap's match-algorithm feature row.
- Salary-percentile match scoring: a `jobsearch` prototype feature, deprecated and not carried forward into `010` (see match-algorithm feature row: prototype `primitive + salary` → `010` `primitive title`).

## Functional Requirements

### Search by keywords

On demand from the UI, or on a repeating schedule the user configures there for that track, easymcf runs a search against `MCF` for a track, retrieves matching posts, and fetches full detail for any post not already on file, so the results a user reviews are never a stale or partial snapshot. The user configures one or more tracks — a role at a given seniority level — each carrying its own search keywords, target salary, and maximum post age. Every post is scored for relevance against the track(s) it matches so the user can prioritize what to review first, and a post found elsewhere can also be entered manually and folds into the same review and scoring flow rather than living outside the system.

This reuses the job-search workflow and matching approach already proven in the `jobsearch` prototype largely as-is for 010. See the **prototype extraction** for its scraping, deduplication, and scoring mechanics. One improvement is made for this release: results must be saved as they are found rather than only once at the end of a full run.

The `jobsearch` prototype's match score combined a primitive title-keyword component with a salary-percentile component. The latter carried a brittle dependency on industry classification, per the **prototype extraction**, and is deprecated. `010` carries forward only the title-keyword component. Moving beyond keyword/title matching to NLP-based semantic matching of title and job description is out of scope for `010` and targeted for release `020`, the MVP cloud release.

- **REQ-SRCH-01** User can define one or more tracks, each a role at a seniority level, each carrying exactly one search profile: keyword(s), minimum salary, maximum post age, and minimum match score, with employment type defaulting to Full Time. Configurable by the user via the UI.
- **REQ-SRCH-02** User can trigger a search run for a given track on demand from the UI. 
- **REQ-SRCH-03** A search run retrieves `MCF` search results for a track's keyword(s), paginating until a page returns no results, and captures per post: position title, company name, post reference/URL, posted date, and salary if shown on the card.
- **REQ-SRCH-04** A search run persists posts incrementally as they are found (e.g. per page or per keyword/salary combination scraped), not only once at the end of the full multi-keyword sweep. A failure partway through a run must not discard posts already captured in that run.
- **REQ-SRCH-05** posts are deduplicated across runs via a stable identifier derived from source + post reference + posted date, so re-running a search does not create duplicate posts.
- **REQ-SRCH-06** Full post detail (closing date, years of experience, applicant count, industry classification, description, MCF reference) is retrieved as a distinct second pass over posts not yet detailed. A post found to be already closed during this pass is removed from the active posts set rather than retained as a stale record.
- **REQ-SRCH-07** User can manually enter a post that was not found by search, using the same downstream data model as a scraped post, naming the one track it belongs to on the request. Manually-entered posts bypass the match-score filter in REQ-SRCH-09.
- **REQ-SRCH-08** Each post is associated with the search run, and implicitly the track, that discovered it, or with the one track a user names when entering it manually. A post belongs to exactly one track: the track whose search found it, or the track named on its manual entry. The one track a resulting lead is filed under is that same track (REQ-CRM-01), and a post becomes at most one lead per user. The user can re-assign the lead to another track afterward (REQ-CRM-12).
- **REQ-SRCH-09** Each post found by a track's own search carries a match score (0–1) for that track, using the `jobsearch` prototype's primitive title-keyword approach, per the **prototype extraction**. Its salary-percentile component is deprecated and dropped from `010`, per the Out of scope section above. The score is recorded together with its scoring method so semantic/NLP-based matching, title plus job description, targeted for release `020`, can be added later without a schema change. Every result a track's own search returns already cleared that track's own keywords, so no further minimum-score filter screens it out of promotion; `min_match_score` is the threshold a future differentiating scoring method reads once one exists. Posts are screened for display by a configurable maximum age.
- **REQ-SRCH-10** User can archive a track without deleting it. An archived track is hidden from active track selectors (search run, manual lead add, apply default CV) but its historical posts, leads, and applications remain intact and readable, with a toggle available to view archived tracks.
- **REQ-SRCH-11** User can configure a repeating schedule for a track's search run from the UI — switching it on or off, and setting how often it repeats and when it next runs — alongside REQ-SRCH-02's on-demand trigger. A track has no schedule until the user gives it one, and the schedule is part of that track's search profile (REQ-SRCH-01), edited in the same place as its other search criteria rather than anywhere outside the app. Once triggered, a scheduled run is indistinguishable from an on-demand one: same run history record (REQ-PLAT-03), same incremental persistence, deduplication, detail pass, and scoring (REQ-SRCH-03..09), with the run history additionally recording which of the two started it. Schedules never stack up duplicate work. A run that falls due while a search run is already in progress does not run alongside it or get dropped, it starts once the in-progress run finishes, and a schedule whose due time passed while the app was closed produces one catch-up run on next start rather than one run per missed interval.

### Job leads tracking

The search process promotes each qualifying post into a lead — scoped to that one user and that one track — and the user tracks it through a defined lifecycle from initial interest to an outcome, instead of managing it as rows and free text in a spreadsheet. A lead's lifecycle is a first-class, structured value rather than free text, and is kept distinct from a post's own acquisition status and from the mechanical outcome of an automated apply attempt, covered in Automated apply below — those are three different questions: whether the post is still live on MCF, where the lead stands in the user's process, and whether a submission mechanically succeeded. A lead also carries the working details a user needs day to day — deadline, contact history, notes — without those living only in a spreadsheet column.

This formalizes and corrects the CRM behavior already piloted in the `jobsearch` prototype's spreadsheet-driven pipeline into structured, UI-driven lead management. See the **prototype extraction** for its menu actions, the two status values it actually implements, and a status-overwrite defect this release must not repeat.

_lead status_

| id | lead status | Set by       | description                                                             |
| -- | ----------- | ------------ | ----------------------------------------------------------------------- |
| 01 | TOAPPLY     | Auto         | Default stage when the system promotes a post, and the apply queue      |
| 02 | APPLIED     | Auto or user | Set on a successful apply attempt, manually, or at manual lead creation |
| 03 | CALLBACK    | User         | User records a callback from the employer                               |
| 04 | INTERVIEW   | User         | User records an interview                                               |
| 05 | OFFER       | User         | Set when the user attaches an offer (REQ-CRM-10)                        |

`CLOSED` is reachable from any stage above as a terminal action — manually by the user (a lead at `OFFER` closes through its offer, REQ-CRM-10), in a batch for `dropped` (REQ-CRM-11), or automatically for `expired` (REQ-CRM-05) and `apply_failed` (REQ-APPLY-10) — recording one of:

_lead closed reasons_

| id | lead close reason | description                                               |
| -- | ----------------- | --------------------------------------------------------- |
| 01 | offer_accepted    | User accepted an offer                                    |
| 02 | rejected          | Employer rejected the application                         |
| 03 | withdrawn         | User withdrew from consideration                          |
| 04 | expired           | No activity recorded on the lead for 28 days (REQ-CRM-05) |
| 05 | cancelled         | User cancelled pursuing the lead                          |
| 06 | duplicate         | Lead duplicates another tracked lead                      |
| 07 | apply_failed      | Automated apply could not be completed (see apply status) |
| 08 | dropped           | User dropped the lead from the apply queue (REQ-APPLY-11) |

- **REQ-CRM-01** The system promotes each qualifying post found by a search run, and each manually entered post, into a tracked lead under one track, owned by that user and that track, defaulting to status `OPEN` and stage `TOAPPLY`. The lead is filed under the track of the run that promotes the post (REQ-SRCH-08). The user adds a lead manually through a form that creates the lead and a copy of its post together, with status `OPEN` and stage `APPLIED`, because the user applied outside the tool. Promotion is a system action and offers the user no promote control. The lead copies the post's position title, company name, and URL, and computes its deadline, once at creation. A post can be promoted into at most one lead per user. Once promoted by a user, it is no longer available for that user's promotion under a different track.
- **REQ-CRM-02** A lead's status defaults to `OPEN` and remains open until `CLOSED`. While open, it progresses through the stages below (`TOAPPLY` replaces `jobsearch`'s `screened.apply` flag), distinct from its post's pipeline status and an application's apply status (REQ-APPLY-04):
- **REQ-CRM-03** A lead carries: position title, company name, post URL, deadline, applied date, first-attempt date, last-contact date, and free-text notes, mirroring the `open` sheet's fields. The position title, company name, and post URL start as copies of the post's values, and the user edits them on the lead. Editing a lead never changes the post, and a change to the post never changes the lead.
- **REQ-CRM-04** User can edit a lead's position title, company name, post URL, and deadline on the lead itself. The lead holds its own copies of these values, so an edit never mutates the post record (post vs. lead separation), and no user can edit a post.
- **REQ-CRM-05** A lead is automatically closed (`close_reason='expired'`) once the current date passes its `deadline`. `deadline` is a maintained field: at promotion (REQ-CRM-01) it is the post's `closing_date` when that date is after the promotion date, `posted_date` plus 28 days when the post has no `closing_date`, and the promotion date plus 1 week when `closing_date` is on or before the promotion date; at `CALLBACK` and `INTERVIEW` it becomes a rolling window, refreshed to 28 days from the most recent logged activity on every update, so continued activity keeps postponing expiry, and at `OFFER` it is the deadline of the lead's open offer (REQ-CRM-10). Only a lead with `status='OPEN'` is evaluated. Every automatic reset of `deadline` is itself recorded as a `deadline_changed` event (REQ-CRM-08).
- **REQ-CRM-06** User can close/archive a lead from any stage except `OFFER`, where the lead closes through the status of its offer (REQ-CRM-10). It is removed from the active pipeline view while its history is preserved.
- **REQ-CRM-07** All lead interactions happen through the AngularJS UI (REQ-FE-01). Spreadsheet-editing and menu-script-driven transitions, as used in `jobsearch`, are not carried forward as the interaction model.
- **REQ-CRM-08** Every update to a lead (stage transition, contact logged, note edit, deadline change, or another field edit) is recorded as a timestamped, append-only event in a per-lead activity log. This log backs `deadline`'s maintenance, feeding auto-expiry (REQ-CRM-05), and is shown to the user as an activity history alongside the lead's application attempts. Scheduled interview/callback details are captured as free text within notes or an event entry. There is no dedicated per-stage date field for them. Each event records the lead's stage before and after the update, so the activity history shows the stage at which every update happened.
- **REQ-CRM-09** Each lead carries an expected salary in SGD (`expected_salary_sgd`). It starts as the minimum salary of the search profile of the lead's track when the lead is created, and the user can edit it at any time from the lead detail. The lead lists show it, and at stage `OFFER` they show the offer amount in its place.
- **REQ-CRM-10** A lead reaches stage `OFFER` only through an offer attached at stage `INTERVIEW`. An offer records its lead, offer date, deadline (defaulting to the lead's deadline, which the user can override), amount in SGD, and a status of `open`, `accepted`, `rejected`, `withdrawn`, or `expired`, starting at `open`. An attached offer is never deleted. While `open`, its amount and deadline are editable. Setting a final status closes the lead (`offer_accepted`, `rejected`, `withdrawn`, or `expired`) and makes the offer read-only, and an offer whose deadline passes expires and closes its lead automatically. A lead closed from an offer can be re-opened at stage `INTERVIEW`, and a new offer moves it back to `OFFER`. The user reviews the complete offer history, closed offers included, on an Offers page.
- **REQ-CRM-11** The lead lists support working through many leads at a glance: stages `TOAPPLY` and `APPLIED` render as compact rows sized for 15 to 30 leads per page, and the later stages render cards showing the latest note and the last contact date. Leads sort by days remaining in `TOAPPLY` and `APPLIED`, by most recent contact from `CALLBACK` onward, and by last update when closed. The user can select several `TOAPPLY` leads and move them to `APPLIED` or drop them in one batch request, which applies every selected lead or none, and a drop asks for confirmation with the number of leads. Any change made on the lead detail refreshes the lead list.
- **REQ-CRM-12** User can re-assign a lead to a different active track from the lead detail, at any stage. The change is recorded as a `field_edited` event (REQ-CRM-08), and the lead's stage, deadline, and expected salary stay as they were. The lists and filters show the lead under its new track, and its apply run uses the new track's default CV.

### Automated apply

The open leads at stage `TOAPPLY` form the apply queue. The search process puts qualifying posts there, and the user prunes the queue by dropping leads or by moving leads they already applied to on to `APPLIED` (REQ-APPLY-01). Easymcf then automates the single-step ("1-click") MCF application flow: opening the post, selecting the right CV, and submitting, using a session the user has already authenticated. Every attempt records a specific, mechanical outcome — success, or one of several well-defined failure reasons — so the user always knows what happened and what, if anything, needs manual follow-up, and one failed attempt never blocks the rest of a queued batch.

The apply mechanics and full outcome vocabulary already implemented in the `jobsearch` prototype are proven and carry forward as the starting point for design, per the **prototype extraction**, including its explicit, deliberate non-goal: posts that require a multi-step questionnaire are detected and left for the user to complete manually.

_apply status_

| id | apply status           | description                                                                      |
| -- | ---------------------- | -------------------------------------------------------------------------------- |
| 01 | applied                | Application submitted successfully, including "already applied" detected on page |
| 02 | questionnaire_required | Submit failed; a multi-step questionnaire is assumed and not automated           |
| 03 | cv_selector_error      | Error selecting the CV on the application page                                   |
| 04 | unable_to_apply        | The apply button never resolved after all retries                                |
| 05 | post_unavailable       | The posting URL failed to load                                                   |
| 06 | cv_not_found           | The configured CV was not found among the resume options                         |
| 07 | post_closed            | The posting is no longer accepting applications                                  |
| 08 | invalid_input          | Required application fields (jobid, url, cv_version) were missing                |

- **REQ-APPLY-01** Every open lead at stage `TOAPPLY` is part of the next automated apply run. The user can select one or more `TOAPPLY` leads and move them to `APPLIED` (applied outside the tool), which removes them from the queue, or drop them (REQ-APPLY-11).
- **REQ-APPLY-02** User can assign a default CV/resume version per track, overridable per application. The apply run selects that CV by matching it against the resume options presented on the application page.
- **REQ-APPLY-03** The apply run automates the single-step ("1-click") flow per queued application: load the post, click apply, select the assigned CV, advance, and submit the final review.
- **REQ-APPLY-04** Each apply attempt records one of the apply statuses, distinct from a post's pipeline status or a lead's status/stage:
- **REQ-APPLY-05** A post whose submission requires a multi-step questionnaire is detected, because submit fails on the expected 1-click flow, and recorded as `questionnaire_required` without the run attempting to complete it or aborting. The user completes it manually. Automating questionnaire flows is out of scope for `010`.
- **REQ-APPLY-06** Apply automation operates against an already-authenticated `MCF` session supplied by the user. The UI provides a way to establish it: it redirects the user to MCF's Singpass-federated login page, the user logs in manually and exports the resulting session cookie, then uploads it back to the app through a dedicated upload dialog. Automating the login itself, including MFA or CAPTCHA handling, is out of scope for `010`. A session/authentication failure aborts the run.
- **REQ-APPLY-07** The apply-button detection step is retried up to 5 times with a 5-second delay between attempts before being marked `unable_to_apply`. A single slow page load must not immediately fail the job.
- **REQ-APPLY-08** A failure on one queued application does not stop the run from attempting the remaining queued applications, and each application's recorded outcome does not overwrite the outcomes already recorded for other applications.
- **REQ-APPLY-09** A lead whose application records apply status `applied` automatically transitions its stage to `APPLIED` (REQ-CRM-02).
- **REQ-APPLY-10** An apply attempt recording status `post_closed` or `post_unavailable` automatically closes the lead with close reason `apply_failed` (REQ-CRM-02). The underlying post can no longer be pursued, so no retry is offered. Any other failure status, `cv_selector_error`, `unable_to_apply`, `cv_not_found`, or `invalid_input`, leaves the lead at stage `TOAPPLY` for the user to resolve and retry.
- **REQ-APPLY-11** User can drop one or more leads from the apply queue before a run attempts them. A drop closes each lead with close reason `dropped` (REQ-CRM-02), and a dropped lead is never recycled into a future run.

### Accounts and sign-in

A visitor creates an account or signs in with Google or with an email and password, and everything the app shows and does is scoped to the signed-in user. The mechanics use standard, well-supported building blocks and invent no authentication scheme of their own.

- **REQ-AUTH-01** A visitor can create an account with a name, an email address, and a password. The email address is unique regardless of letter case, and a duplicate is rejected with a descriptive error.
- **REQ-AUTH-02** A password must be 12 to 128 characters and contain a lowercase letter, an uppercase letter, a digit, and a symbol, and must not contain the account's email local part or name. A rejected password reports every unmet rule together, and the sign-up screen shows the rules as the user types.
- **REQ-AUTH-03** A user can sign in with email and password. A wrong password, an unknown email, and an account without a password all fail with the same message and timing, so a failure never reveals whether an email is registered. Repeated failures for one email are rate limited.
- **REQ-AUTH-04** A visitor can sign in or create an account with Google. A Google identity already linked to an account signs in to that account. A Google identity with a verified email that matches an existing account links to it, after which both sign-in methods work. Any other Google identity creates a new account. A Google identity whose email is not verified is refused.
- **REQ-AUTH-05** A signed-in user stays signed in across page loads until they sign out or the session lifetime ends, and sign-out ends the session on the server. Every page and every API route except sign-up, sign-in, and the Google sign-in flow requires a signed-in user. An unauthenticated visit to a page redirects to sign-in and returns the user to that page afterward.
- **REQ-AUTH-06** Every screen and every API read shows only the signed-in user's own tracks, search profiles, leads, notes, events, applications, CVs, runs, and MCF session. A request for another user's record is indistinguishable from a request for a missing record. Posts are shared, read-only listings that a user sees through their own tracks and leads.
- **REQ-AUTH-07** Each search run, scheduled run, and apply run acts for one user and never reads or writes another user's data. Each user has at most one search run and one apply run in flight at a time, and different users' runs proceed independently.
- **REQ-AUTH-08** Every page shows a signed-in user section with the user's photo in a circle icon, or their initials when no photo exists, and a Log out control. A user can upload, replace, and remove their photo. A Google account's picture is the initial photo until the user uploads their own. A photo is visible only to its owner.
- **REQ-AUTH-09** Passwords are stored only as salted hashes. Client secrets, session keys, session tokens, and passwords never appear in the repository, the database, or the logs.

### Backend data platform

The backend is a locally-run Python service exposing the search, pipeline, and apply capabilities above to the frontend, backed by a local SQLite database — replacing the prototype's scripts-plus-spreadsheet coupling with a proper API and a single source of truth for application data. See the **prototype extraction** for a reference API design this can build on.

- **REQ-PLAT-01** Backend is implemented in Python as a locally-run REST/HTTP+JSON service, e.g. Flask. A generic, schema-validated CRUD interface per entity (`GET/PUT/DELETE /{table}/{id}`, `POST /{table}`, `POST /{table}/batch`, `GET /{table}/search`, `POST /{table}/delete`), per `mcfpipe`'s Database API design, is the default surface for an entity. It does not mandate that every entity's every write reach the database unmediated. An entity or action that carries a cross-table or state-machine invariant, such as lead-stage legality, apply-outcome propagation, or promoting a post into a lead, is instead exposed through a named, purpose-specific endpoint that internally reuses the same CRUD/persistence primitives rather than duplicating them, so the "no bespoke endpoint per feature" intent still holds for every entity that doesn't need one. See the **API reference** for the concrete per-entity classification and the full named-endpoint catalog.
- **REQ-PLAT-02** All domain data, including posts, leads, applications, tracks/search profiles, match scores, and run history, is persisted in a local SQLite database, replacing Google Sheets as both config store and data store.
- **REQ-PLAT-03** Every automated run, search, scoring, or apply, is logged with start/end time, outcome counts, and any errors, so a failure can be diagnosed from the log without re-running. The `jobsearch` prototype relied on bare `print`/`except` calls with no persisted run history.
- **REQ-PLAT-04** The system runs entirely on the user's local machine, with no cloud deployment and no cloud credentials. Its only outbound network destinations are `MCF`, for search and apply automation, and Google's identity service, while a user signs in with Google.

### Frontend

The frontend is a single local web application the user interacts with directly, replacing every spreadsheet tab and menu action the prototype relied on with an equivalent screen or control. See the **prototype extraction** for what those were. 010 commits to AngularJS per the roadmap's feature table.

- **REQ-FE-01** Frontend is an AngularJS single-page app, served locally, providing: track configuration, search-profile configuration, post/results browsing with match scores, lead management by stage, offers, apply-queue review and results, MCF session establishment/status (REQ-APPLY-06), and the sign-in and sign-up screens with the signed-in user section (REQ-AUTH-01..08). Track configuration and search-profile configuration are separate screens (**user interface design** pages 1 and 1b), split along a milestone boundary rather than a UX one: track identity/lifecycle, what a lead is scoped to and archived against (REQ-CRM-01, REQ-SRCH-10), belongs to job leads tracking; search-execution criteria (keywords, salary, age, schedule) belongs to search by keywords.
- **REQ-FE-02** The UI surfaces run status and errors from backend-triggered search and apply runs, so failures are visible to the user instead of being confined to a console or log file.

### Local dev/test environment and seed data

Developing and testing easymcf's UI, pipeline logic, and matching algorithm must not require a live browser session or a working scrape against the real MCF site day to day. The prototype's experience shows how easily that live dependency breaks and how much manual setup it demands, per the **prototype extraction**. Three distinct test protocols cover this: backend-only tests that never touch a browser, mocked end-to-end tests that exercise the full stack including the frontend without a live MCF dependency, and a separate live end-to-end protocol reserved for explicit, on-demand verification against the real site.

- **REQ-DEV-01** A documented local setup procedure lets a developer install dependencies and run backend, frontend, and database locally without cloud credentials.
- **REQ-DEV-02** Seed/sample data (two accounts with distinct data, representative posts, leads, applications, tracks/search profiles) is available so the UI, lead management, and matching logic can be developed and demoed without live scraping or an MCF session.
- **REQ-DEV-03** Backend-only automated tests exercise the API and SQLite data layer (search, lead lifecycle, apply-status logic) directly against seed/fixture data, with no browser and no frontend involved — the primary fast feedback loop for backend logic.
- **REQ-DEV-04** Mock end-to-end tests exercise the full stack — frontend through backend — against seed/fixture data, with MCF search and apply automation mocked or stubbed rather than driving a live browser session against the real site, and with Google sign-in served by a stub identity provider. This is the protocol routine and automated test runs use. Live-site dependence is unacceptable here.
- **REQ-DEV-05** A live end-to-end test protocol exercises the real scrape and apply automation against the live MCF site using an authenticated session. It is not part of routine or automated test runs and is only triggered explicitly, on demand, consistent with this project's boundary against unattended access to the live site.
- **REQ-DEV-06** A live sign-in test protocol signs in through the real Google identity service with a Google OAuth client and test account the user provides. It is not part of routine or automated test runs and is only triggered explicitly by the user, on demand.

## 7. Open questions

1. Session credential storage mechanism — where/how the uploaded MCF cookie (and any service credentials) is persisted — local dev/test env milestone.
