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

Those milestones own *how*: schema, API shape, algorithms, folder structure, test tooling. This document intentionally stops short of that.

__end user__

Single local job seeker, running the system on their own machine. Multi-user support is out of scope for this relesae

## References

- **release roadmap**: [release-roadmap.md](../release-roadmap.md), [010-release.md](010-release.md) — easymcf scope, feature table, and stated aim to avoid `mcfpipe`'s pre-MVP infrastructure investment.
- **prototype extraction**: [010-prototype.md](010-prototype.md) — implementation-level extraction from `jobsearch` and `mcfpipe`, sufficient for most of this document and the design stage. Use this first.
- **jobsearch prototype**: `jobsearch/` — the working prototype this release formalizes and re-platforms onto a local Python API + SQLite + AngularJS stack. Go to source directly for detail beyond what the **prototype extraction** captures: `agent.py`, `database.py`, `mcf_profile.py`, `match.py`/`text.py`, `apply.py`, `gsheet/applicationtrackingapp.gs`.
- **mcfpipe reference**: `mcfpipe/` — an earlier, more ambitious rebuild of the same product. Its data model and API design are worth reusing. Its cloud infrastructure pivot to a serverless, NoSQL, multi-tier VPC, IaC, and full CI/CD setup, undertaken before the functional product worked reliably, is the specific mistake release `010` is scoped to avoid. Go to source directly for detail beyond what the **prototype extraction** captures: `docs/data_model.md`, `docs/database_api.md`, `docs/architecture.md`, `docs/enhancements.md`.
- **API reference**: [010-api.md](010-api.md) — the concrete backend endpoint surface, including the per-entity CRUD/hook/named classification.

## Glossary

- **post:** A job listing on `MyCareerFutures` (MCF) discovered by search or entered manually. Source-of-truth for a role/company/URL; not user-specific.
- **MCF** MyCareerFutures
- **role:** A generic job title/domain (e.g. "Data Engineer"), not tied to any one user.
- **track:** A user's role at a given seniority level. The unit search profiles, CVs, and match scores are organized by.
- **search profile:** The keyword/salary/age search criteria for one track.
- **lead:** A single user's personal, trackable instance of a post for one track, followed from initial interest through to a closed outcome, either success or fail. Created when the user promotes a post under a track. Its first stage is `PROSPECT`.
- **application:** An MCF automated application that is managed by the app from selected-to-apply to submission success or fail.
- **pipeline status:** Where a post sits in the system's post search acquisition process — distinct from a lead's status/stage.
- **lead status:** Coarse open/closed indicator for a lead — `OPEN` while active, `CLOSED` once resolved.
- **lead stage:** Where an open lead sits within its lifecycle: `PROSPECT` (default on promotion) → `TOAPPLY` (queued for apply) → `APPLIED` → `CALLBACK` → `INTERVIEW` → `OFFER`. A closed lead's stage instead records why it closed: offer accepted, rejected, withdrawn, expired, cancelled, duplicate, or apply failed.
- **apply status:** The mechanical outcome of an automated application apply attempt, tracked separately from lead status/stage.
- **lead activity log:** The append-only, timestamped record of updates to a lead, covering stage transitions, contact logged, notes edits, and deadline changes. Its latest entry drives auto-expiry and backs the lead's activity history (REQ-CRM-08).

See each feature section below for the concrete structure and enumerations behind these terms.

## 6. Out of scope

- Cloud deployment (AWS EC2, API Gateway, Lambda)
  - AWS-hosted relational or NoSQL database — deferred to 020/100.
  - Serverless architecture, multi-stack IaC (CloudFormation), containerization (ECR/Fargate).
  - Private network endpoints, VPC/subnet tiering.
  - Fully automated CI/CD pipelines.
- Multi-user support and any authentication/authorization beyond a single local user.
- Automated MCF login, including MFA or CAPTCHA handling.
- Multi-step questionnaire application automation.
- Analytics/BI/reporting pipelines (ETL, warehouse, dashboards) beyond in-app run status.
- Scheduled/cron-triggered runs — 010 runs are user-initiated from the UI.
- NLP/semantic-based match scoring (title + job description) — deferred to release `020` (MVP cloud) per the release roadmap's match-algorithm feature row.
- Salary-percentile match scoring: a `jobsearch` prototype feature, deprecated and not carried forward into `010` (see match-algorithm feature row: prototype `primitive + salary` → `010` `primitive title`).

## Functional Requirements

### Search by keywords

On demand from the UI, easymcf runs a search against `MCF` for a track, retrieves matching posts, and fetches full detail for any post not already on file, so the results a user reviews are never a stale or partial snapshot. The user configures one or more tracks — a role at a given seniority level — each carrying its own search keywords, target salary, and maximum post age. Every post is scored for relevance against the track(s) it matches so the user can prioritize what to review first, and a post found elsewhere can also be entered manually and folds into the same review and scoring flow rather than living outside the system.

This reuses the job-search workflow and matching approach already proven in the `jobsearch` prototype largely as-is for 010. See the **prototype extraction** for its scraping, deduplication, and scoring mechanics. One improvement is made for this release: results must be saved as they are found rather than only once at the end of a full run.

The `jobsearch` prototype's match score combined a primitive title-keyword component with a salary-percentile component. The latter carried a brittle dependency on industry classification, per the **prototype extraction**, and is deprecated. `010` carries forward only the title-keyword component. Moving beyond keyword/title matching to NLP-based semantic matching of title and job description is out of scope for `010` and targeted for release `020`, the MVP cloud release.

- **REQ-SRCH-01** User can define one or more tracks, each a role at a seniority level, each carrying exactly one search profile: keyword(s), minimum salary, maximum post age, and minimum match score, with employment type defaulting to Full Time. Configurable by the user via the UI.
- **REQ-SRCH-02** User can trigger a search run for a given track on demand from the UI. 
- **REQ-SRCH-03** A search run retrieves `MCF` search results for a track's keyword(s), paginating until a page returns no results, and captures per post: position title, company name, post reference/URL, posted date, and salary if shown on the card.
- **REQ-SRCH-04** A search run persists posts incrementally as they are found (e.g. per page or per keyword/salary combination scraped), not only once at the end of the full multi-keyword sweep. A failure partway through a run must not discard posts already captured in that run.
- **REQ-SRCH-05** posts are deduplicated across runs via a stable identifier derived from source + post reference + posted date, so re-running a search does not create duplicate posts.
- **REQ-SRCH-06** Full post detail (closing date, years of experience, applicant count, industry classification, description, MCF reference) is retrieved as a distinct second pass over posts not yet detailed. A post found to be already closed during this pass is removed from the active posts set rather than retained as a stale record.
- **REQ-SRCH-07** User can manually enter a post that was not found by search, using the same downstream data model as a scraped post. Its matching track(s) are auto-assigned using the same match-scoring logic as REQ-SRCH-09, and the user can update that assignment via the UI. Manually-entered posts bypass the match-score filter in REQ-SRCH-09.
- **REQ-SRCH-08** Each post is associated with the search run, and implicitly the track, that discovered it, or flagged as manually entered. A post may match more than one track, with each match scored independently (REQ-SRCH-09). The one track a resulting lead is filed under is a choice the user makes at promotion (REQ-CRM-01); it is never assigned automatically.
- **REQ-SRCH-09** Each post has a computed match score (0–1) per track it matches, visible to the user for prioritization, using the `jobsearch` prototype's primitive title-keyword approach, per the **prototype extraction**. Its salary-percentile component is deprecated and dropped from `010`, per the Out of scope section above. Posts are screened by a configurable maximum age and minimum score. The score is recorded together with its scoring method so semantic/NLP-based matching, title plus job description, targeted for release `020`, can be added later without a schema change.
- **REQ-SRCH-10** User can archive a track without deleting it. An archived track is hidden from active track selectors (search run, promote-to-lead, apply default CV) but its historical posts, leads, and applications remain intact and readable, with a toggle available to view archived tracks.

### Job leads tracking

Once a post is worth pursuing under a track, the user promotes it into a lead — scoped to that one user and that one track — and tracks it through a defined lifecycle from initial interest to an outcome, instead of managing it as rows and free text in a spreadsheet. A lead's lifecycle is a first-class, structured value rather than free text, and is kept distinct from a post's own acquisition status and from the mechanical outcome of an automated apply attempt, covered in Automated apply below — those are three different questions: whether the post is still live on MCF, where the lead stands in the user's process, and whether a submission mechanically succeeded. A lead also carries the working details a user needs day to day — deadline, contact history, notes — without those living only in a spreadsheet column.

This formalizes and corrects the CRM behavior already piloted in the `jobsearch` prototype's spreadsheet-driven pipeline into structured, UI-driven lead management. See the **prototype extraction** for its menu actions, the two status values it actually implements, and a status-overwrite defect this release must not repeat.

_lead status_

| id | lead status | Set by       | description                                                  |
| -- | ----------- | ------------ | ------------------------------------------------------------ |
| 01 | PROSPECT    | Auto         | Default stage when a lead is first promoted                  |
| 02 | TOAPPLY     | User         | User queues the lead for the apply run                       |
| 03 | APPLIED     | Auto or user | Set automatically on a successful apply attempt, or manually |
| 04 | CALLBACK    | User         | User records a callback from the employer                    |
| 05 | INTERVIEW   | User         | User records an interview                                    |
| 06 | OFFER       | User         | User records a job offer                                     |

`CLOSED` is reachable from any stage above as a terminal action — manually by the user, or automatically for `expired` (REQ-CRM-05) and `apply_failed` (REQ-APPLY-10) — recording one of:

_lead closed reasons_

| id | lead close reason | description                                                               |
| -- | ----------------- | --------------------------------------------------------------------------- |
| 01 | offer_accepted    | User accepted an offer                                                      |
| 02 | rejected          | Employer rejected the application                                           |
| 03 | withdrawn         | User withdrew from consideration                                            |
| 04 | expired           | No activity recorded on the lead for 28 days (REQ-CRM-05)                   |
| 05 | cancelled         | User cancelled pursuing the lead                                            |
| 06 | duplicate         | Lead duplicates another tracked lead                                        |
| 07 | apply_failed      | Automated apply could not be completed (see apply status)                   |

- **REQ-CRM-01** User can promote a post, whether scraped or manual, into a tracked lead under one track, owned by that user and that track, defaulting to status `OPEN` and stage `PROSPECT`. If the post matches more than one track (REQ-SRCH-08), the user selects which track to promote it under. A post can be promoted into at most one lead. Once promoted, it is no longer available for promotion under a different track.
- **REQ-CRM-02** A lead's status defaults to `OPEN` and remains open until `CLOSED`. While open, it progresses through the stages below (`TOAPPLY` replaces `jobsearch`'s `screened.apply` flag), distinct from its post's pipeline status and an application's apply status (REQ-APPLY-04):
- **REQ-CRM-03** A lead carries: deadline, applied date, first-attempt date, last-contact date, free-text notes, and a link back to its post's profile/description — mirroring the `open` sheet's fields.
- **REQ-CRM-04** User can override a lead's title/company independently of the source post, without mutating the post record (post vs. lead separation).
- **REQ-CRM-05** A lead is automatically closed (stage `expired`) once 28 days pass with no activity recorded on it. The expiry threshold is the lead's last-updated timestamp plus 28 days, refreshed by any update to the lead (stage change, contact logged, notes edited, etc.), and applies at every open stage, `PROSPECT` through `OFFER`, until the lead is `CLOSED`.
- **REQ-CRM-06** User can close/archive a lead from any stage. It is removed from the active pipeline view while its history is preserved.
- **REQ-CRM-07** All lead interactions happen through the AngularJS UI (REQ-FE-01). Spreadsheet-editing and menu-script-driven transitions, as used in `jobsearch`, are not carried forward as the interaction model.
- **REQ-CRM-08** Every update to a lead (stage transition, contact logged, note edit, deadline change) is recorded as a timestamped, append-only event in a per-lead activity log. This log's latest entry is the lead's last-activity time, feeding auto-expiry (REQ-CRM-05), and is shown to the user as an activity history alongside the lead's application attempts. Scheduled interview/callback details are captured as free text within notes or an event entry. There is no dedicated per-stage date field for them.

### Automated apply

For leads at stage `PROSPECT` that the user queues to apply to, easymcf advances the lead to `TOAPPLY` and creates an application entity for it. Easymcf then automates the single-step ("1-click") MCF application flow: opening the post, selecting the right CV, and submitting, using a session the user has already authenticated. Every attempt records a specific, mechanical outcome — success, or one of several well-defined failure reasons — so the user always knows what happened and what, if anything, needs manual follow-up, and one failed attempt never blocks the rest of a queued batch.

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

- **REQ-APPLY-01** User can select one or more leads at stage `PROSPECT` and queue them for an automated apply run. This advances each lead to stage `TOAPPLY` and creates an application entity for it, queued and ready to apply.
- **REQ-APPLY-02** User can assign a default CV/resume version per track, overridable per application. The apply run selects that CV by matching it against the resume options presented on the application page.
- **REQ-APPLY-03** The apply run automates the single-step ("1-click") flow per queued application: load the post, click apply, select the assigned CV, advance, and submit the final review.
- **REQ-APPLY-04** Each apply attempt records one of the apply statuses, distinct from a post's pipeline status or a lead's status/stage:
- **REQ-APPLY-05** A post whose submission requires a multi-step questionnaire is detected, because submit fails on the expected 1-click flow, and recorded as `questionnaire_required` without the run attempting to complete it or aborting. The user completes it manually. Automating questionnaire flows is out of scope for `010`.
- **REQ-APPLY-06** Apply automation operates against an already-authenticated `MCF` session supplied by the user. The UI provides a way to establish it: it redirects the user to MCF's Singpass-federated login page, the user logs in manually and exports the resulting session cookie, then uploads it back to the app through a dedicated upload dialog. Automating the login itself, including MFA or CAPTCHA handling, is out of scope for `010`. A session/authentication failure aborts the run.
- **REQ-APPLY-07** The apply-button detection step is retried up to 5 times with a 5-second delay between attempts before being marked `unable_to_apply`. A single slow page load must not immediately fail the job.
- **REQ-APPLY-08** A failure on one queued application does not stop the run from attempting the remaining queued applications, and each application's recorded outcome does not overwrite the outcomes already recorded for other applications.
- **REQ-APPLY-09** A lead whose application records apply status `applied` automatically transitions its stage to `APPLIED` (REQ-CRM-02).
- **REQ-APPLY-10** An apply attempt recording status `post_closed` or `post_unavailable` automatically closes the lead with close reason `apply_failed` (REQ-CRM-02). The underlying post can no longer be pursued, so no retry is offered. Any other failure status, `cv_selector_error`, `unable_to_apply`, `cv_not_found`, or `invalid_input`, leaves the lead at stage `TOAPPLY` for the user to resolve and retry.
- **REQ-APPLY-11** User can remove a queued, not yet run, application from the queue. Removal closes the owning lead with close reason `withdrawn` (REQ-CRM-02) instead of reverting it to stage `PROSPECT`. A removed application is never recycled into a future batch.

### Backend data platform

The backend is a locally-run Python service exposing the search, pipeline, and apply capabilities above to the frontend, backed by a local SQLite database — replacing the prototype's scripts-plus-spreadsheet coupling with a proper API and a single source of truth for application data. See the **prototype extraction** for a reference API design this can build on.

- **REQ-PLAT-01** Backend is implemented in Python as a locally-run REST/HTTP+JSON service, e.g. Flask. A generic, schema-validated CRUD interface per entity (`GET/PUT/DELETE /{table}/{id}`, `POST /{table}`, `POST /{table}/batch`, `GET /{table}/search`, `POST /{table}/delete`), per `mcfpipe`'s Database API design, is the default surface for an entity. It does not mandate that every entity's every write reach the database unmediated. An entity or action that carries a cross-table or state-machine invariant, such as lead-stage legality, apply-outcome propagation, or promoting a post into a lead, is instead exposed through a named, purpose-specific endpoint that internally reuses the same CRUD/persistence primitives rather than duplicating them, so the "no bespoke endpoint per feature" intent still holds for every entity that doesn't need one. See the **API reference** for the concrete per-entity classification and the full named-endpoint catalog.
- **REQ-PLAT-02** All domain data, including posts, leads, applications, tracks/search profiles, match scores, and run history, is persisted in a local SQLite database, replacing Google Sheets as both config store and data store.
- **REQ-PLAT-03** Every automated run, search, scoring, or apply, is logged with start/end time, outcome counts, and any errors, so a failure can be diagnosed from the log without re-running. The `jobsearch` prototype relied on bare `print`/`except` calls with no persisted run history.
- **REQ-PLAT-04** The system runs entirely on the user's local machine 

### Frontend

The frontend is a single local web application the user interacts with directly, replacing every spreadsheet tab and menu action the prototype relied on with an equivalent screen or control. See the **prototype extraction** for what those were. 010 commits to AngularJS per the roadmap's feature table.

- **REQ-FE-01** Frontend is an AngularJS single-page app, served locally, providing: track/search-profile configuration, post/results browsing with match scores, lead management by stage, apply-queue review and results, and MCF session establishment/status (REQ-APPLY-06).
- **REQ-FE-02** The UI surfaces run status and errors from backend-triggered search and apply runs, so failures are visible to the user instead of being confined to a console or log file.

### Local dev/test environment and seed data

Developing and testing easymcf's UI, pipeline logic, and matching algorithm must not require a live browser session or a working scrape against the real MCF site day to day. The prototype's experience shows how easily that live dependency breaks and how much manual setup it demands, per the **prototype extraction**. Three distinct test protocols cover this: backend-only tests that never touch a browser, mocked end-to-end tests that exercise the full stack including the frontend without a live MCF dependency, and a separate live end-to-end protocol reserved for explicit, on-demand verification against the real site.

- **REQ-DEV-01** A documented local setup procedure lets a developer install dependencies and run backend, frontend, and database locally without cloud credentials.
- **REQ-DEV-02** Seed/sample data (representative posts, leads, applications, tracks/search profiles) is available so the UI, lead management, and matching logic can be developed and demoed without live scraping or an MCF session.
- **REQ-DEV-03** Backend-only automated tests exercise the API and SQLite data layer (search, lead lifecycle, apply-status logic) directly against seed/fixture data, with no browser and no frontend involved — the primary fast feedback loop for backend logic.
- **REQ-DEV-04** Mock end-to-end tests exercise the full stack — frontend through backend — against seed/fixture data, with MCF search and apply automation mocked or stubbed rather than driving a live browser session against the real site. This is the protocol routine and automated test runs use. Live-site dependence is unacceptable here.
- **REQ-DEV-05** A live end-to-end test protocol exercises the real scrape and apply automation against the live MCF site using an authenticated session. It is not part of routine or automated test runs and is only triggered explicitly, on demand, consistent with this project's boundary against unattended access to the live site.

## 7. Open questions

1. Session credential storage mechanism — where/how the uploaded MCF cookie (and any service credentials) is persisted — local dev/test env milestone.
