# Easy MCF POC Local - Prototype

This document captures implementation-level detail extracted directly from the `jobsearch` prototype and the `mcfpipe` reference architecture (see [010-01-requirements.md](010-01-requirements.md) for how they relate to this release). It exists so the requirements, data model, architecture, and design milestones for release 010 don't need to repeatedly reread the original source repos — treat this as the primary reference, and go back to `jobsearch/` or `mcfpipe/` source directly only when a decision needs detail not captured here.

## Search by keywords — jobsearch implementation

### Scrape mechanics (agent.py)

URL scheme: `search?search={keyword}&salary={level}&employmentType=Full%20Time&sort=new_posting_date&page={n}`, built by `JobSearchWebsite.jobsearch_URLquery()`. The scraper iterates nested loops over every configured salary level × keyword (`update_jobRecords()` → `jobRecords_query()`), paging (page=0,1,2...) until a page returns zero elements matching the `job-card-*` id prefix. It uses Selenium + headless Chrome to render the page, then BeautifulSoup (html5lib parser) to extract cards, with fixed sleeps of 15s after each page load (`refresh_pageSoup`) plus 4s between pages — no adaptive/explicit waits.

Per-card fields extracted (`get_jobRecord_fromcard`): `position_title` (span `data-testid="job-card__job-title"`), `company_name` (p `data-testid="company-hire-info"`), `posted_date` (parsed from span `data-cy="job-card-date-info"` text "Posted today/yesterday/N days ago" into an actual date), `salaryHigh` (top figure from `$`-containing spans under `data-testid="salary-range"`), `urlid` (slug from the card's `<a href>`, minus `/job/` prefix and query string), `source` (site name, hardcoded "MyCareerFutures"). A deterministic id is computed as `jobid = f"{source}-{urlid[-32:]}-{posted_date}"` and is the identifier used to de-duplicate against the existing `job` table (set difference on jobid) — not a database auto-increment.

Known persistence gap (flagged in `mcfpipe/docs/enhancements.md` #05, "batching with intermediate DB writes, currently all-or-nothing"): `update_jobRecords()` accumulates the entire multi-keyword, multi-page sweep into one in-memory DataFrame and only writes to SQLite once at the very end. A crash partway through loses everything scraped in that run. Each successful run writes one row to `execution_log` (id, function name, run timestamp) and one row per new job to `job_batch` (jobid → batchid), giving batch-level traceability of which run discovered which job. Full sweeps were observed at roughly 15 minutes for cards and 3–5 minutes for profiles (`mcfpipe` enhancements backlog #06), attributed to the fixed sleeps and lack of async/concurrency — flagged as backlog, never fixed.

### Posting detail fetch (mcf_profile.py)

Runs as a distinct second pass, `update_job_profiles(limit, progress_updates)`, over the set difference between `job` and `profile` tables (postings without detail yet), capped at a configurable `limit` per run. Per posting it scrapes: `is_open` (checked first — true unless the expiry-date field contains "Closed"), `mcf_ref`, `closing_date` (parsed `%d %b %Y`), `years_experience` (present in config but deprecated/unused — always `None` in the current code), `applicants` (int), `industry_classification`, and `description` (full text). If `is_open` is false, the posting is treated as already closed: its detail fields are left blank and it is removed from the active `job` table (`db.remove_jobs()`) rather than kept as a stale record. Field extraction is done via a small declarative config (`FIELD_CONFIG`) mapping field name → HTML tag/attribute/keyword to search for — brittle to MCF markup changes, which is exactly the failure mode `recommission.py` (see Local dev environment section below) exists to catch.

### Manual entry (post.py, referenced by database/report modules)

A user-entered sheet (`manual_posts`) is diffed against the `job` table by jobid and merged into `job`/`profile` using the same schema as scraped postings, tagged `src_methodid=1` (vs `0` for scraped). `match.py`'s `update_screened()` explicitly lets `src_methodid==1` rows bypass the match-score filter: `(recent.match_auto >= match_score_min) | (recent.src_methodid == 1)`.

### Matching / scoring (match.py, text.py)

`score_profile_title()` cleans and "de-ranks" the raw title (removes junk/generic words via `text.py`'s tag dictionaries), then builds a bigram feature matrix over the cleaned titles using scikit-learn's `CountVectorizer`. Each bigram's contribution is looked up from a maintained `title_tags` library (tag → score); the per-title `title_score` is the matrix-multiplication of the bigram matrix against that score vector. Salary percentile (`salary_pct`) is the rank-percentile of `salaryHigh` within the current batch of profiles being scored (0 by default — a by-industry-classification percentile variant exists in the code but is commented out/disabled). The combined score (`match_score(pct, title_score)`) is: if `title_score > 0`, bucket `pct` into a quartile (1–4, where quartile 1 = top 25th percentile), then `score = (1/quartile) * (1 + title_score)`; otherwise the score is 0.

Screening (`update_screened()`) keeps postings whose `posted_date` is within a configurable `age_weeks`, whose `closing_date` is not in the past, and whose `match_auto >= match_score_min` (both thresholds read from `search_config.json`, itself synced from a Google Sheet `config` tab) — or any manually-entered posting regardless of score. Both thresholds are per-installation config today, not per-track; `mcfpipe`'s `search_profile` table (below) generalizes this to be per-track.

## Search — mcfpipe reference data model (role/track/search_profile hierarchy)

From `mcfpipe/docs/data_model.md`: a **role** is a generic job title (id, role_name, description), not user-specific. A **track** is a user's role at a seniority level (id = hash of user_id+role_id, user_id FK, role_id FK, seniority number); a user can have multiple tracks. A **search_profile** exists one per track (track_id PK/FK, keywords, salary_target_sgd). A **job_track** table is the many-to-many join between `job` (a user's personal instance of a posting) and `track`, carrying `search_match` (bool: did it show up in this track's search) and `assigned` (bool: is this the one track a job is categorized under — only one track can be `assigned` per job). A **track_score** table holds, per `job_track` pair, a 0–1 `score` plus a `method` string (e.g. "keyword", "BERT") — the `method` field exists explicitly so the scoring approach can evolve without a schema change. Separately, `post` (the source-of-truth scraped/entered listing, shared across users) is distinct from `job` (one user's personal pointer to it, keyed on user_id + post_id); `job_details` lets a user override `position`/`company_name` on their own copy without touching `post`.

## Job leads tracking — jobsearch implementation

### CRM menu logic (gsheet/applicationtrackingapp.gs, GAS_functions.md)

All pipeline actions are manual menu clicks or sheet edits under a custom `JobsearchApp` Google Sheets menu. `recordTrackAssignments()` copies manually-entered `(jobid, track_id)` pairs from a `track_un` staging sheet to `track_assignment`, then clears the staging cells. `selectApplySuccess()` reads `apply_results` for rows with `apply_status = 1`, and sets `apply = 1` on the matching rows in `screened` — this is how the apply automation's outcome flows back into the CRM sheet. `recordApplications()` is the main promote-to-pipeline action: it filters `screened` for rows flagged `apply = 1`, appends them to the `open` sheet with an initial status string of `"pending callback"`, clears the `apply` flag on those `screened` rows, then calls `clearApplyInProcess()` to prune `apply_results` rows no longer relevant (already `apply=1` or already `closed`). `updateOpenExpired()` scans the `open` sheet's deadline column (G) against today's date and unconditionally overwrites the status column (M) to `"expired"` for any row whose deadline has passed — it does not check whether the row already has an applied, interview, or otherwise terminal status before overwriting. This is a defect, not an intentional design choice. `closeLeads()` archives any `open` row with a `closed = 1` flag to a `closed` sheet with a timestamp, leaving the rest in `open`, reachable regardless of the row's current status column value.

### Actual status values observed

Only two structured status strings are ever written by the code: `"pending callback"` (set on promotion via `recordApplications()`) and `"expired"` (set by `updateOpenExpired()`). Outcomes like "applied", "interview", "rejected", "offer" are not structured statuses in `jobsearch` — they live only as free text in the `notes`/`last contact` columns, or as a manually-updated `offer_likelihood` KPI figure on a separate `kpi` sheet. This is the gap `mcfpipe`'s `crm_status` enum (below) is meant to close.

### `open` sheet columns (13 fields)

jobid, url, title, company, lead source, apply method, deadline, applied date, 1st attempt (date), last contact (date), notes, job profile (link/summary), status.

## Job leads tracking — mcfpipe reference data model

`crm_status` (job_id PK/FK, status number) documents enum values `OPEN, CLOSED, EXPIRED, TOAPPLY, APPLIED, INTERVIEW` (the source notes "etc.." — the list is described as extensible, not exhaustive). `apply_status` (job_id PK/FK, status number) documents enum values `OPEN, SUCCESS, FAILED` — deliberately a separate table/concept from `crm_status`, to avoid conflating "where is this lead in my funnel" with "did the automated apply mechanically succeed." `jobsearch`'s `screened.apply` flag conflates exactly these two ideas (it means both "queued to apply" and, after `selectApplySuccess()` runs, "apply succeeded"). `track_cv` (track_id PK/FK, cv_code) assigns a default CV per track, referenced by the CV identifier in the user's MCF profile.

## Automated apply — jobsearch implementation (apply.py)

### Session handling

No login automation. A Playwright Chromium context is created and cookies are loaded from a manually-exported `cookies_mcf.json` file; the code checks that at least one loaded cookie matches the target domain before proceeding. If cookie loading or the domain check fails, the whole run aborts with a connection error — there is no per-job fallback or retry at this level.

### Per-job state machine (apply_job())

1. Load the posting URL. Failure to load → status `05_post_unavailable`.
2. `apply_start()`: poll for the apply button (`button#job-details-apply-button`) up to `MAX_RETRY=5` times with `RETRY_DELAY_MS=5000` between attempts. Button visible and enabled → click it → status `01_applied`. Button not found → check a status-message element (`p[data-testid="job-apply-error"]`) for "already"/"applied" text → also `01_applied` (already-applied is treated as a success outcome, not a separate code) — or "closed"/"no longer" text → `07_post_closed`. Retries exhausted with neither condition met → `04_unable_to_apply`.
3. `cv_select(cv_version)`: match the configured `cv_version` string as a substring against resume card titles (`div[data-testid="resume-card"]` → `a.resume-link` text); click the matching card's radio button, then click the page-advance button (`button#application-details-save-button`). No substring match among the available CVs → `06_cv_not_found`. A selector/DOM error while locating cards/radio → `03_cv_selector_error`.
4. `apply_submit()`: click the final review-submit button (`button#job-application-review__submit-button`). Failure here is *assumed* (not confirmed) to mean the application requires a multi-page questionnaire rather than being a true 1-click flow → status `02_questionnaire`; the job is abandoned at this point, not retried or automated further.
5. Missing required input fields (`jobid`, `url`, `cv_version`) on a queued job are rejected before any browser action is attempted → status `91_invalid_input`.

Full status vocabulary: `01_applied`, `02_questionnaire`, `03_cv_selector_error`, `04_unable_to_apply`, `05_post_unavailable`, `06_cv_not_found`, `07_post_closed`, `91_invalid_input`.

### Run-level behavior

`fetch_jobs_to_apply()` excludes jobs already marked `applied=1` in prior results before queuing, so a re-run doesn't reapply. The loop over queued jobs (`jobs_apply()`) continues to the next job after any single job's exception/failure — only a session-level failure in `site_load()`/`session_connect()` is fatal for the entire run. Results are merged back using pandas `combine_first()` against prior results (keyed by jobid), so posting results for a run never blanks out unrelated jobs' previously recorded outcomes.

## Backend / data platform — mcfpipe reference architecture

`mcfpipe/docs/architecture.md` names Flask as the reference framework for its CRM API component ("CRM API (e.g., Flask on EC2/ALB/Fargate)"), separate from its DynamoDB-fronting Lambda/API Gateway layer. `mcfpipe/docs/database_api.md` documents a generic, schema-validated CRUD API pattern, independent of its DynamoDB implementation: single-record `GET/PUT/DELETE /[table]/{id}`, and bulk `POST /[table]`, `POST /[table]/batch`, `GET /[table]/search`, `POST /[table]/delete`, all validated against a canonical `db_schema.json`. Its documented validation test cases (`mcfpipe/docs/validation.md`) cover required-field enforcement (400 + field name), type validation (e.g. integer fields), strict date-format validation, and 404 with descriptive text for a missing record or an unknown table name. `jobsearch` itself runs as local Python scripts against SQLite via SQLAlchemy, with pandas as the data-shaping layer and Google Sheets doubling as both config store and UI — the coupling release 010 is removing.

## Local dev environment — jobsearch pain points

Runtime dependencies: Selenium plus a matching Chrome/chromedriver pair (`agent.py`, `mcf_profile.py`), Playwright's Chromium (`apply.py`), a manually-exported `cookies_mcf.json` session, and a Google service-account credential (`client_secret.json`) plus `gsheet_config.json` for Sheets API access. `recommission.py` is a manual smoke-test script (not automated recovery) with six sequential checks (t001–t006: load browser → load search page → find cards → parse a card → parse a profile page → run screening), logging pass/fail to `test_result.json`. It exists because MCF's page markup drifts over time and silently breaks the scraper between uses — there is no automatic detection otherwise. Hardcoded Windows paths (e.g. `C:\Users\taylo\...`) appear throughout, confirming this was built as a single-user desktop tool with no portable local dev setup. No scheduler is built in; two Windows `.bat` files were meant to be wired into Windows Task Scheduler externally.
