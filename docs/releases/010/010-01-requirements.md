# Easy MCF Release 010 (POC Local) - Requirements

Milestone `01 requirements`, see [010-release-milestones.md](010-release-milestones.md).

## Purpose

This document defines *what* release 010 (POC local) must do. It is the input to the milestones that follow it: test strategy, test cases, data model, architecture, design, local dev/test environment, seed data, and the three functional builds (job leads
tracking, search by keywords, apply automation). Those milestones own *how* — schema, API shape, algorithms, folder structure, test tooling. This document intentionally stops short of that: where a decision is genuinely deferred, it is called out explicitly in
[Section 7](#7-open-questions-deferred-to-later-milestones) rather than answered here.

__end user__

Single local job seeker, running the system on their own machine. Multi-user support is out of scope for 010 (see [Section 6](#6-out-of-scope-for-release-010)).

## References

- [release-roadmap.md](../release-roadmap.md), [010-release.md](010-release.md) — easymcf scope, feature table, and stated aim to avoid `mcfpipe`'s pre-MVP infrastructure investment.
- `jobsearch/` (sibling repo) — the working prototype. Its Selenium/Playwright scripts, SQLite tables, and Google-Sheet-driven CRM are the functional baseline being formalized and re-platformed onto a local Python API + SQLite + AngularJS stack.
- `mcfpipe/` (sibling repo) — an earlier, more ambitious rebuild of the same product. Its `docs/data_model.md` and `docs/workflows.md` describe a domain model worth reusing;
  its `docs/enhancements.md` and `docs/releases/010_cloud_infra.md` document a pivot into cloud infrastructure (serverless, NoSQL, multi-tier VPC, IaC, full CI/CD) undertaken before the functional product worked reliably — the specific mistake release `010` is scoped to avoid.

## Glossary

- **posting:** A job listing on MyCareersFuture discovered by search or entered manually. Source-of-truth for a role/company/URL; not user-specific. 
- **lead:** A user's personal, trackable instance of a posting in their pipeline (equivalent to `job` in `mcfpipe`, a row in `open`/`screened` in `jobsearch`). Multiple leads can reference the same posting details, and a user may override title/company on their own lead without changing the underlying posting. 
- **search profile** A named, user-configurable set of search criteria (keywords, salary floor, employment type, max posting age) that a search run is executed against. Generalizes `jobsearch`'s `search_config.json` keyword/salary loop. 
- **pipeline status:** Where a lead sits in the user's CRM funnel (e.g. new, to-apply, applied, interview, rejected, expired). 
- **apply status:**  The mechanical outcome of an automated apply attempt (e.g. success, failed, questionnaire-required, already-applied). Tracked separately from pipeline status, per `mcfpipe`'s `crm_status`/`apply_status` split — collapsing the two lost information in early prototypes. 

## 6. Out of scope for release 010

Carried over as explicit exclusions from `mcfpipe`'s documented pre-MVP infrastructure
investment ([Section 2](#2-sources)), plus prototype behaviors not being formalized yet:

- Cloud deployment of any kind (AWS EC2, API Gateway, Lambda) — deferred to 020 MVP cloud.
- AWS-hosted relational or NoSQL database — deferred to 020/100.
- Serverless architecture, multi-stack IaC (CloudFormation), containerization (ECR/Fargate).
- Private network endpoints, VPC/subnet tiering.
- Fully automated CI/CD pipelines.
- Multi-user support and any authentication/authorization beyond a single local user.
- Automated MyCareersFuture login, including MFA or CAPTCHA handling.
- Multi-step questionnaire application automation.
- Analytics/BI/reporting pipelines (ETL, warehouse, dashboards) beyond in-app run status.
- Scheduled/cron-triggered runs — 010 runs are user-initiated from the UI.

## 7. Open questions 

1. Exact pipeline status enumeration and allowed transitions: detailed design ref from mcfpipe
2. API protocol and backend framework: detailed design ref from mcfpipe
3. Matching/scoring algorithm: detail available in source code from jobsearch
4. Whether a `mcfpipe`-style role/track hierarchy is needed, or a flat list of search profiles is sufficient for one user: keep heirarchy

_delegated to later stage_

5. Session credential storage mechanism (MCF cookie, any service credentials) 
6. Retry counts/backoff 

## Functional Requirements

### Search by keywords 

- **REQ-SRCH-01** User can define one or more search profiles, each with keyword(s), minimum salary, and maximum posting age; employment type defaults to Full Time. 
- **REQ-SRCH-02** User can trigger a search run for a given search profile on demand from the UI. Scheduled/unattended runs such as OS cron, background service, are out of scope for `010`. 
- **REQ-SRCH-03** A search run retrieves MyCareersFuture search results for its profile's keyword(s), paginating until no further results, and captures per posting at minimum: position title, company name, posting reference/URL, posted date, and salary if shown.
- **REQ-SRCH-04** A search run persists each posting incrementally as it is found. A failure partway through a run must not discard postings already captured in that run (`jobsearch`'s scrape was all-or-nothing; this is a named lesson to fix, not carry forward). |
- **REQ-SRCH-05** Postings are deduplicated across runs via a stable identifier derived from source + posting reference, so re-running a search profile does not create duplicate postings.
- **REQ-SRCH-06** For a newly discovered posting, the system retrieves extended detail (closing date, years of experience, applicant count, industry classification, description, MCF reference) as a distinct step from the search-result scrape. 
- **REQ-SRCH-07** User can manually enter a posting that was not found by search, using the same downstream data model as a scraped posting. 
- **REQ-SRCH-08** Each posting is associated with the search run (and implicitly the search profile) that discovered it, or flagged as manually entered.
- **REQ-SRCH-09** Each posting has a computed match indicator relative to the search profile(s) it matches (keyword relevance, salary, recency), visible to the user for prioritization. The scoring method itself is a design-milestone decision. 

### Job leads tracking 

- **REQ-CRM-01** User can promote a posting (scraped or manual) into a tracked lead. 
- **REQ-CRM-02** A lead progresses through a pipeline of statuses covering at minimum: newly screened, to-apply, applied, interview, rejected, closed, and expired. The full enumeration and allowed transitions are defined in the data model/design milestones; this document only fixes that such a status must exist and be distinct from apply status. 
- **REQ-CRM-03** User can override a lead's title/company independently of the source posting, without mutating the posting record (posting vs. lead separation, adapted from `mcfpipe`'s `post`/`job` split). 
- **REQ-CRM-04** A lead is automatically marked expired once its posting's closing date has passed and it has not been applied to. 
- **REQ-CRM-05** User can attach free-text notes and contact-history entries to a lead. 
- **REQ-CRM-06** User can close/archive a lead, removing it from the active pipeline view while preserving its history. 
- **REQ-CRM-07** All pipeline interactions happen through the AngularJS UI (REQ-FE-01). Spreadsheet-editing and menu-script-driven transitions, as used in `jobsearch`, are not carried forward as the interaction model. 

### 5.3 Automated apply 

- **REQ-APPLY-01** User can select one or more leads and queue them for automated application. 
- **REQ-APPLY-02** User can associate a CV/resume version with a lead (or a default per search profile); the apply run selects that CV during submission. 
- **REQ-APPLY-03** The apply run automates the single-step ("1-click") apply flow: open posting, click apply, select CV, submit, confirm. 
- **REQ-APPLY-04** Each apply attempt records a mechanical apply status distinct from pipeline status, covering at minimum: success, failed, already-applied, posting closed/unavailable, questionnaire-required, CV-not-found, invalid input. |
- **REQ-APPLY-05** A posting whose application requires a multi-step questionnaire is detected and skipped without aborting the run; it is marked questionnaire-required so the user can complete it manually. Automating questionnaire flows is out of scope for 010. |
- **REQ-APPLY-06** Apply automation operates against an already-authenticated MyCareersFuture session (e.g. an exported/saved session) supplied by the user. Automating login, MFA, or CAPTCHA handling is out of scope for 010; establishing/refreshing the session is a manual user step. 
- **REQ-APPLY-07** A transient failure on one apply attempt is retried a bounded number of times before being marked failed. |
- **REQ-APPLY-08** A failure on one queued lead does not stop the run from proceeding to the remaining queued leads. |

### Backend data platform 

- **REQ-PLAT-01** Backend is implemented in Python and exposes the search, CRM, and apply capabilities above to the frontend over a local API. Protocol/framework choice is an architecture-milestone decision. |
- **REQ-PLAT-02** All domain data (postings, leads, search profiles, match scores, run history) is persisted in a local SQLite database. Exact schema is the data-model milestone's output; this document only fixes that the entities named in 5.1–5.3 must be represented.
- **REQ-PLAT-03** Every automated run (search, scoring, apply) is logged with start/end time, outcome counts, and any errors, so a failure can be diagnosed from the log without re-running (`jobsearch` relied on bare `print`/`except` with no persisted run history).
- **REQ-PLAT-04** The system runs entirely on the user's local machine with no required cloud dependency. Cloud deployment is out of scope  

### Frontend

-**REQ-FE-01** Frontend is an AngularJS single-page app, served locally, providing: search profile configuration, posting/results browsing, pipeline/lead management, and apply-queue review. 
- **REQ-FE-02** The UI surfaces run status and errors from backend-triggered search and apply runs; failures are visible to the user, not just written to a console or log file.

### Local dev/test environment and seed data

- **REQ-DEV-01** A documented local setup procedure lets a developer install dependencies and run backend, frontend, and database locally without cloud credentials.
- **REQ-DEV-02** Seed/sample data (representative postings, leads, search profiles) is available so the UI and pipeline can be developed and demoed without live scraping. 
- **REQ-DEV-03** Automated tests can run locally against seed data without invoking live browser automation against MyCareersFuture. Test strategy/tooling is a separate milestone; this document only fixes that live-site dependence is not acceptable for routine test runs. 
