# Easy MCF POC Local - Prototype

## Contents

- [References](#references)
- [Search by keywords — jobsearch implementation](#search-by-keywords--jobsearch-implementation)
  - [Scrape mechanics (agent.py)](#scrape-mechanics-agentpy)
  - [Posting detail fetch (mcf_profile.py)](#posting-detail-fetch-mcf_profilepy)
  - [Manual entry (post.py, referenced by database/report modules)](#manual-entry-postpy-referenced-by-databasereport-modules)
  - [Matching / scoring (match.py, text.py)](#matching--scoring-matchpy-textpy)
- [Search — mcfpipe reference data model (role/track/search_profile hierarchy)](#search--mcfpipe-reference-data-model-roletracksearch_profile-hierarchy)
- [Job leads tracking — jobsearch implementation](#job-leads-tracking--jobsearch-implementation)
  - [CRM menu logic (gsheet/applicationtrackingapp.gs, GAS_functions.md)](#crm-menu-logic-gsheetapplicationtrackingappgs-gas_functionsmd)
  - [Actual status values observed](#actual-status-values-observed)
  - [`open` sheet columns (13 fields)](#open-sheet-columns-13-fields)
- [Job leads tracking — mcfpipe reference data model](#job-leads-tracking--mcfpipe-reference-data-model)
- [Automated apply — jobsearch implementation (apply.py)](#automated-apply--jobsearch-implementation-applypy)
  - [Session handling](#session-handling)
  - [Per-job state machine (apply_job())](#per-job-state-machine-apply_job)
  - [Run-level behavior](#run-level-behavior)
- [Backend / data platform — mcfpipe reference architecture](#backend--data-platform--mcfpipe-reference-architecture)
- [Local dev environment — jobsearch pain points](#local-dev-environment--jobsearch-pain-points)

This document captures implementation-level detail extracted directly from the **jobsearch prototype** and the **mcfpipe reference**. See the **requirements doc** for how they relate to this release. It exists so the requirements, data model, architecture, and design milestones for release 010 don't need to repeatedly reread the original source repos. Treat this as the primary reference, and go back to the **jobsearch prototype** or the **mcfpipe reference** source directly only when a decision needs detail not captured here.

## References

- **jobsearch prototype**: `jobsearch/` — the sibling repo this document's "jobsearch implementation" sections extract from, read-only reference per `CLAUDE.md`.
- **mcfpipe reference**: `mcfpipe/` — the sibling repo this document's "mcfpipe reference" sections extract from, read-only reference per `CLAUDE.md`.
- **mcfpipe enhancements backlog**: `mcfpipe/docs/enhancements.md` — the known persistence-gap (#05) and performance (#06) issues named in the Scrape mechanics section.
- **mcfpipe data model**: `mcfpipe/docs/data_model.md` — the role/track/search_profile and crm_status/apply_status reference schema.
- **mcfpipe architecture**: `mcfpipe/docs/architecture.md` — the reference backend/data-platform component breakdown.
- **mcfpipe database API**: `mcfpipe/docs/database_api.md` — the generic, schema-validated CRUD API pattern.
- **mcfpipe validation**: `mcfpipe/docs/validation.md` — the documented validation test cases.
- **requirements doc**: [010-01-requirements.md](010-01-requirements.md) — how this extracted detail relates to release 010's scope.

## Search by keywords — jobsearch implementation

### Scrape mechanics (agent.py)

URL scheme: `search?search={keyword}&salary={level}&employmentType=Full%20Time&sort=new_posting_date&page={n}`, built by `JobSearchWebsite.jobsearch_URLquery()`. The scraper iterates nested loops over every configured salary level × keyword (`update_jobRecords()` → `jobRecords_query()`), paging (page=0,1,2...) until a page returns zero elements matching the `job-card-*` id prefix. It uses Selenium + headless Chrome to render the page, then BeautifulSoup, html5lib parser, to extract cards, with fixed sleeps of 15s after each page load (`refresh_pageSoup`) plus 4s between pages. There are no adaptive/explicit waits.

Per-card fields extracted (`get_jobRecord_fromcard`):

01. `position_title` — span `data-testid="job-card__job-title"`.
02. `company_name` — p `data-testid="company-hire-info"`.
03. `posted_date` — parsed from span `data-cy="job-card-date-info"` text "Posted today/yesterday/N days ago" into an actual date.
04. `salaryHigh` — the top figure from `$`-containing spans under `data-testid="salary-range"`.
05. `urlid` — a slug from the card's `<a href>` minus the `/job/` prefix and query string.
06. `source` — the site name, hardcoded to "MyCareerFutures".

A deterministic id is computed as `jobid = f"{source}-{urlid[-32:]}-{posted_date}"` and is the identifier used to de-duplicate against the existing `job` table, a set difference on jobid. It is not a database auto-increment.

Known persistence gap, flagged in the **mcfpipe enhancements backlog** #05 as "batching with intermediate DB writes, currently all-or-nothing": `update_jobRecords()` accumulates the entire multi-keyword, multi-page sweep into one in-memory DataFrame and only writes to SQLite once at the very end. A crash partway through loses everything scraped in that run. Each successful run writes one row to `execution_log`, id, function name, run timestamp, and one row per new job to `job_batch`, jobid to batchid, giving batch-level traceability of which run discovered which job. Full sweeps were observed at roughly 15 minutes for cards and 3-5 minutes for profiles, per the **mcfpipe enhancements backlog** #06, attributed to the fixed sleeps and lack of async/concurrency. This is flagged as backlog and never fixed.

### Posting detail fetch (mcf_profile.py)

This runs as a distinct second pass, `update_job_profiles(limit, progress_updates)`, over the set difference between `job` and `profile` tables, postings without detail yet, capped at a configurable `limit` per run. Per posting it scrapes:

01. `is_open` — checked first and true unless the expiry-date field contains "Closed".
02. `mcf_ref`.
03. `closing_date` — parsed `%d %b %Y`.
04. `years_experience` — present in config but deprecated/unused and always `None` in the current code.
05. `applicants` (int).
06. `industry_classification`.
07. `description` — full text.

If `is_open` is false, the posting is treated as already closed. Its detail fields are left blank and it is removed from the active `job` table (`db.remove_jobs()`) rather than kept as a stale record. Field extraction is done via a small declarative config, `FIELD_CONFIG`, mapping field name to HTML tag/attribute/keyword to search for. This is brittle to MCF markup changes, exactly the failure mode `recommission.py` (see Local dev environment section below) exists to catch.

### Manual entry (post.py, referenced by database/report modules)

A user-entered sheet, `manual_posts`, is diffed against the `job` table by jobid and merged into `job`/`profile` using the same schema as scraped postings, tagged `src_methodid=1` versus `0` for scraped. `match.py`'s `update_screened()` explicitly lets `src_methodid==1` rows bypass the match-score filter: `(recent.match_auto >= match_score_min) | (recent.src_methodid == 1)`.

### Matching / scoring (match.py, text.py)

`score_profile_title()` cleans and "de-ranks" the raw title, removing junk/generic words via `text.py`'s tag dictionaries, then builds a bigram feature matrix over the cleaned titles using scikit-learn's `CountVectorizer`. Each bigram's contribution is looked up from a maintained `title_tags` library, tag to score. The per-title `title_score` is the matrix-multiplication of the bigram matrix against that score vector. Salary percentile (`salary_pct`) is the rank-percentile of `salaryHigh` within the current batch of profiles being scored, 0 by default. A by-industry-classification percentile variant exists in the code but is commented out/disabled. The combined score, `match_score(pct, title_score)`, is computed as follows. If `title_score > 0`, bucket `pct` into a quartile, 1 through 4, where quartile 1 is the top 25th percentile, then `score = (1/quartile) * (1 + title_score)`. Otherwise the score is 0.

Screening (`update_screened()`) keeps postings whose `posted_date` is within a configurable `age_weeks`, whose `closing_date` is not in the past, and whose `match_auto >= match_score_min`, both thresholds read from `search_config.json`, itself synced from a Google Sheet `config` tab, or any manually-entered posting regardless of score. Both thresholds are per-installation config today, not per-track. The **mcfpipe data model**'s `search_profile` table (below) generalizes this to be per-track.

## Search — mcfpipe reference data model (role/track/search_profile hierarchy)

From the **mcfpipe data model**, this hierarchy has six entities.

01. **role** — a generic job title: id, role_name, description, not user-specific.
02. **track** — a user's role at a seniority level: id computed as a hash of user_id+role_id, user_id FK, role_id FK, seniority number. A user can have multiple tracks.
03. **search_profile** — exists one per track: track_id PK/FK, keywords, salary_target_sgd.
04. **job_track** — the many-to-many join between `job`, a user's personal instance of a posting, and `track`, carrying `search_match`, a bool for whether it showed up in this track's search, and `assigned`, a bool for whether it is the one track a job is categorized under. Only one track can be `assigned` per job.
05. **track_score** — holds, per `job_track` pair, a 0-1 `score` plus a `method` string, for example "keyword" or "BERT". The `method` field exists explicitly so the scoring approach can evolve without a schema change.
06. **post**/`job`/`job_details` — `post`, the source-of-truth scraped/entered listing shared across users, is distinct from `job`, one user's personal pointer to it, keyed on user_id + post_id. `job_details` lets a user override `position`/`company_name` on their own copy without touching `post`.

## Job leads tracking — jobsearch implementation

### CRM menu logic (gsheet/applicationtrackingapp.gs, GAS_functions.md)

All pipeline actions are manual menu clicks or sheet edits under a custom `JobsearchApp` Google Sheets menu, five functions.

01. `recordTrackAssignments()` copies manually-entered `(jobid, track_id)` pairs from a `track_un` staging sheet to `track_assignment`, then clears the staging cells.
02. `selectApplySuccess()` reads `apply_results` for rows with `apply_status = 1`, and sets `apply = 1` on the matching rows in `screened`. This is how the apply automation's outcome flows back into the CRM sheet.
03. `recordApplications()` is the main promote-to-pipeline action. It filters `screened` for rows flagged `apply = 1`, appends them to the `open` sheet with an initial status string of `"pending callback"`, clears the `apply` flag on those `screened` rows, then calls `clearApplyInProcess()` to prune `apply_results` rows no longer relevant, already `apply=1` or already `closed`.
04. `updateOpenExpired()` scans the `open` sheet's deadline column (G) against today's date and unconditionally overwrites the status column (M) to `"expired"` for any row whose deadline has passed. It does not check whether the row already has an applied, interview, or otherwise terminal status before overwriting. This is a defect, not an intentional design choice.
05. `closeLeads()` archives any `open` row with a `closed = 1` flag to a `closed` sheet with a timestamp, leaving the rest in `open`, reachable regardless of the row's current status column value.

### Actual status values observed

Only two structured status strings are ever written by the code: `"pending callback"`, set on promotion via `recordApplications()`, and `"expired"`, set by `updateOpenExpired()`. Outcomes like "applied", "interview", "rejected", "offer" are not structured statuses in `jobsearch`. They live only as free text in the `notes`/`last contact` columns, or as a manually-updated `offer_likelihood` KPI figure on a separate `kpi` sheet. This is the gap `mcfpipe`'s `crm_status` enum (below) is meant to close.

### `open` sheet columns (13 fields)

01. jobid
02. url
03. title
04. company
05. lead source
06. apply method
07. deadline
08. applied date
09. 1st attempt (date)
10. last contact (date)
11. notes
12. job profile (link/summary)
13. status

## Job leads tracking — mcfpipe reference data model

Three entities, from the **mcfpipe data model**.

01. `crm_status` — job_id PK/FK, status number, documents enum values `OPEN, CLOSED, EXPIRED, TOAPPLY, APPLIED, INTERVIEW`. The source notes "etc.." — the list is described as extensible, not exhaustive.
02. `apply_status` — job_id PK/FK, status number, documents enum values `OPEN, SUCCESS, FAILED`, deliberately a separate table/concept from `crm_status`, to avoid conflating "where is this lead in my funnel" with "did the automated apply mechanically succeed." `jobsearch`'s `screened.apply` flag conflates exactly these two ideas. It means both "queued to apply" and, after `selectApplySuccess()` runs, "apply succeeded."
03. `track_cv` — track_id PK/FK, cv_code, assigns a default CV per track, referenced by the CV identifier in the user's MCF profile.

## Automated apply — jobsearch implementation (apply.py)

### Session handling

There is no login automation. A Playwright Chromium context is created and cookies are loaded from a manually-exported `cookies_mcf.json` file. The code checks that at least one loaded cookie matches the target domain before proceeding. If cookie loading or the domain check fails, the whole run aborts with a connection error. There is no per-job fallback or retry at this level.

### Per-job state machine (apply_job())

01. Load the posting URL. Failure to load produces status `05_post_unavailable`.
02. `apply_start()`: poll for the apply button (`button#job-details-apply-button`) up to `MAX_RETRY=5` times with `RETRY_DELAY_MS=5000` between attempts. If the button is visible and enabled, click it, producing status `01_applied`. If the button is not found, check a status-message element (`p[data-testid="job-apply-error"]`) for "already"/"applied" text, also producing `01_applied` since already-applied is treated as a success outcome, not a separate code. If instead it shows "closed"/"no longer" text, the status is `07_post_closed`. If retries are exhausted with neither condition met, the status is `04_unable_to_apply`.
03. `cv_select(cv_version)`: match the configured `cv_version` string as a substring against resume card titles (`div[data-testid="resume-card"]` → `a.resume-link` text), click the matching card's radio button, then click the page-advance button (`button#application-details-save-button`). No substring match among the available CVs produces status `06_cv_not_found`. A selector/DOM error while locating cards/radio produces status `03_cv_selector_error`.
04. `apply_submit()`: click the final review-submit button (`button#job-application-review__submit-button`). Failure here is *assumed*, not confirmed, to mean the application requires a multi-page questionnaire rather than being a true 1-click flow, producing status `02_questionnaire`. The job is abandoned at this point, not retried or automated further.
05. Missing required input fields (`jobid`, `url`, `cv_version`) on a queued job are rejected before any browser action is attempted, producing status `91_invalid_input`.

Full status vocabulary: `01_applied`, `02_questionnaire`, `03_cv_selector_error`, `04_unable_to_apply`, `05_post_unavailable`, `06_cv_not_found`, `07_post_closed`, `91_invalid_input`.

### Run-level behavior

`fetch_jobs_to_apply()` excludes jobs already marked `applied=1` in prior results before queuing, so a re-run doesn't reapply. The loop over queued jobs (`jobs_apply()`) continues to the next job after any single job's exception/failure. Only a session-level failure in `site_load()`/`session_connect()` is fatal for the entire run. Results are merged back using pandas `combine_first()` against prior results, keyed by jobid, so posting results for a run never blanks out unrelated jobs' previously recorded outcomes.

## Backend / data platform — mcfpipe reference architecture

The **mcfpipe architecture** doc names Flask as the reference framework for its CRM API component, "CRM API (e.g., Flask on EC2/ALB/Fargate)", separate from its DynamoDB-fronting Lambda/API Gateway layer. The **mcfpipe database API** doc documents a generic, schema-validated CRUD API pattern, independent of its DynamoDB implementation, all validated against a canonical `db_schema.json`.

01. single-record `GET/PUT/DELETE /[table]/{id}`.
02. bulk `POST /[table]`.
03. `POST /[table]/batch`.
04. `GET /[table]/search`.
05. `POST /[table]/delete`.

Its documented validation test cases, the **mcfpipe validation** doc, cover four checks.

01. required-field enforcement (400 + field name).
02. type validation, for example integer fields.
03. strict date-format validation.
04. 404 with descriptive text for a missing record or an unknown table name.

`jobsearch` itself runs as local Python scripts against SQLite via SQLAlchemy, with pandas as the data-shaping layer and Google Sheets doubling as both config store and UI. This is the coupling release 010 is removing.

## Local dev environment — jobsearch pain points

Runtime dependencies:

01. Selenium plus a matching Chrome/chromedriver pair (`agent.py`, `mcf_profile.py`).
02. Playwright's Chromium (`apply.py`).
03. a manually-exported `cookies_mcf.json` session.
04. a Google service-account credential (`client_secret.json`) plus `gsheet_config.json` for Sheets API access.

`recommission.py` is a manual smoke-test script, not automated recovery, with six sequential checks, t001 through t006.

01. load browser.
02. load search page.
03. find cards.
04. parse a card.
05. parse a profile page.
06. run screening.

Results log pass/fail to `test_result.json`. It exists because MCF's page markup drifts over time and silently breaks the scraper between uses. There is no automatic detection otherwise. Hardcoded Windows paths, for example `C:\Users\taylo\...`, appear throughout, confirming this was built as a single-user desktop tool with no portable local dev setup. No scheduler is built in. Two Windows `.bat` files were meant to be wired into Windows Task Scheduler externally.
</content>
