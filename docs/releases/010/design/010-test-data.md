# Easy MCF POC Local - Test Data

## Contents

- [Purpose](#purpose)
- [Out of scope](#out-of-scope)
- [References](#references)
- [1. Source data inventory](#1-source-data-inventory) — `TESTDATA-SRC-01..03`
- [2. What's missing, and how it's inferred](#2-whats-missing-and-how-its-inferred) — `TESTDATA-GAP-01..04`
- [3. Column-level cleaning rules](#3-column-level-cleaning-rules)
- [4. Reference schema → target schema mapping](#4-reference-schema--target-schema-mapping) — `TESTDATA-MAP-*`
  - [`role`](#role)
  - [`track`](#track)
  - [`search_profile`](#search_profile)
  - [`cv`](#cv)
  - [`post`](#post)
  - [`post_track`](#post_track)
  - [`lead`](#lead)
  - [`lead_event`](#lead_event)
  - [`application`](#application)
  - [`run_log`](#run_log)
  - [`session`](#session)
- [5. Two output modes, one generator](#5-two-output-modes-one-generator) — `TESTDATA-GEN-*`
- [6. Open questions for milestone 08](#6-open-questions-for-milestone-08)

## Purpose

This document defines where test/seed data for `010` comes from, what it's missing, and how it is transformed from the `jobsearch` prototype's reference schema into the `010` target **data model**. This document is the direct input to milestone 08 (setup database seed data) and to milestone 03 (test cases) wherever a test case needs a real-shaped fixture rather than a hand-built one. It is analogous to how the **workflows doc** is the input to the **data model**. It does not restate the **architecture doc**'s seed-loading mechanics, `ARCH-STO-04..06`: seed is plain SQL text, loaded by `resetdb.py --seed`, dates are relative-to-load-time. It supplies the *content* those mechanics load, and the transformation logic that produces it.

Decisions carry a `TESTDATA-*` id grouped `SRC`/`GAP`/`MAP`/`GEN`, mirroring the `REQ-*`/`ARCH-*`/`STRAT-*` convention.

## Out of scope

- The generator script's actual implementation. This document specifies its required behavior. Writing `scripts/gen_test_data.py` is milestone 08's work.
- Re-deciding any `ARCH-STO-*`/`STRAT-CASE-*` mechanics already fixed by the **architecture doc**/**test-strategy doc**. This document only supplies the source-to-target content those mechanics load.
- `report.csv`/`post-statistics.csv` — aggregate views excluded from generation per `TESTDATA-SRC-01`'s inventory table.

## References

- **data model**: [010-data-model.md](010-data-model.md) — the target entities (`role`, `track`, `search_profile`, `cv`, `post`, `post_track`, `lead`, `lead_event`, `application`, `run_log`, `session`) every mapping below produces rows for.
- **workflows doc**: [010-workflows.md](010-workflows.md) — the process logic the **data model** was itself derived to support, referenced here only to explain this document's own relationship to the **data model**.
- **architecture doc**: [010-architecture.md](010-architecture.md) `ARCH-STO-04..06` — seed is text SQL, dates are relative-to-load-time via a shift, and the minimum enumeration the seed set must cover.
- **test-strategy doc**: [010-test-strategy.md](010-test-strategy.md) `STRAT-CASE-05` — closed vocabularies (apply-status codes, close reasons, `src_method`) each need at least one seeded row.
- **requirements doc**: [010-01-requirements.md](010-01-requirements.md) — REQ-CRM-02 (lead status/stage table), REQ-CRM's close-reason table, REQ-APPLY-04 (apply status vocabulary), REQ-DEV-02.
- **prototype extraction**: [010-prototype.md](010-prototype.md) — the `jobsearch` pipeline (`agent.py` → `mcf_profile.py` → `match.py` → gsheet) whose stages this document's source data was extracted from.
- **mycareerfutures skill**: [.claude/skills/mycareerfutures/SKILL.md](../../../.claude/skills/mycareerfutures/SKILL.md) — the MCF URL scheme used to synthesize a placeholder `url_ref` for redacted/blank source rows.
- `test-data/*.csv` — the actual source files this document operationalizes, downloaded from the `jobsearch` prototype's operational Google Sheet.
- CLAUDE.md — no live-site or real-session material may enter automated/unattended context. This document's privacy rule (`TESTDATA-GEN-05`) is the concrete application of that boundary to personal job-search history.

## 1. Source data inventory

`test-data/*.csv` are hand-downloaded tabs from the `jobsearch` prototype's live operational Google Sheet: real job-search history, not synthetic. `jobsearch` itself is a four-stage pipeline.

01. `agent.py` scrapes.
02. `mcf_profile.py` details.
03. `match.py` scores.
04. the sheet is the human-facing CRM.

Each CSV corresponds to a stage or a view carved out of one:

| file | pipeline stage | rows | role in generation |
| --- | --- | --- | --- |
| `screened.csv` | `match.py` output, synced to sheet | 2085 (2085 unique jobid... see caveat) | `post` + `post_track` source: title/company/salary/dates/match score for postings that cleared scoring |
| `track-assignment.csv` | `match.py` × every track | 3520 rows, 3520 jobids | **primary `post_track` source** — every (jobid, track) pair with a `match_score`, covers 3477 of 3478 lead jobids |
| `track-cv.csv` | sheet config | 9 rows | `role` + `track` + `cv` source — track_id, track name (doubles as role name), default cv_version |
| `config.csv` | `search_config.json`, synced from sheet | 7 rows | `search_profile` source — one **global** config (salary_min, keywords, match_score_min, age_weeks), not per-track |
| `applied-leads.csv` | CRM master (`open` ∪ `closed` sheets) | 4586 rows / 3478 unique jobids | **primary `lead` source** — see `TESTDATA-SRC-02`, this is a superset of `open.csv` and `closed.csv` |
| `open.csv` | CRM `open` sheet, current view | 82 jobids | supplements `applied-leads.csv` with a finer-grained `stage` column for currently-open leads only |
| `closed.csv` | CRM `closed` sheet, current view | 3396 jobids | fully redundant with `applied-leads.csv` (100% overlap) — reference only, not read by the generator |
| `active.csv` | CRM `open` sheet, small recent extract | 6 jobids | fully redundant with `open.csv` (100% overlap) — reference only, not read by the generator |
| `response-stages.csv` | CRM activity log | 210 jobids | **primary `lead_event` source** — literal (jobid, date, stage, notes) log |
| `callbacks.csv`, `interviews.csv`, `offers.csv` | CRM activity log, filtered views | 200/47/8 jobids | 100% subsets of `response-stages.csv`'s jobids — reference/cross-check only, not read by the generator |
| `apply-results.csv`, `apply-failed.csv`, `apply-in-process.csv` | apply automation output | **0 data rows each** | headers only — see `TESTDATA-GAP-02`, `application` has no real source data at all |
| `post-statistics.csv`, `report.csv` | aggregate/pivot views | n/a | weekly counts and a hand-built pivot table; not row-level source data, excluded from generation entirely |

**TESTDATA-SRC-01** `screened.csv`'s header row has two structural defects from how it was exported: `posted_date` and `open`/`closed` each appear **twice** as column names. A naive `csv.DictReader`, a dict keyed by header name, silently keeps only the second occurrence of each and drops the first. The generator must read this file positionally, `csv.reader`, indexing into the row by column position, or rename duplicate headers before dict-based access, whichever is used. This must be called out in the script's own comments, since it is exactly the kind of bug that reads as "working," no exception, no error, while quietly discarding a column.

**TESTDATA-SRC-02** `applied-leads.csv` is the master. `open.csv`'s 82 jobids and `closed.csv`'s 3396 jobids are both 100%-contained subsets of `applied-leads.csv`'s jobids, verified by set intersection. The generator's canonical lead source is **`applied-leads.csv`**, with `open.csv`'s `stage` column joined in by jobid for currently-open leads only, since `applied-leads.csv` has no equivalent fine-grained `stage` field, only the coarser `status`/`last_stage_reached`. `closed.csv` and `active.csv` are not read by the generator. They exist in the export only because they mirror live sheet tabs.

**TESTDATA-SRC-03** `applied-leads.csv` has 4586 rows but only 3478 non-blank unique jobids. 1061 rows have a blank `jobid`, trailing/formula artifacts from the sheet export, and are skipped on read, and 47 jobids appear exactly twice. Inspection of the duplicate pairs shows genuine re-application history, same posting, two attempt records with different `notes`/`closed` dates, not export corruption. See `TESTDATA-MAP-04` for how these become a *retry*, not a discarded duplicate.

## 2. What's missing, and how it's inferred

**TESTDATA-GAP-01 Pre-screening posts.** `jobsearch` writes every scraped card to a local SQLite `job` table and every detail-pass result to `profile`, per the **prototype extraction**'s Scrape mechanics / Posting detail fetch sections. Neither table was ever synced to the Google Sheet. Only `match.py`'s output (`screened.csv`) was. This means the source data has **no examples of a post that was found by search but scored below `match_score_min` and was therefore never promoted to `screened`**. Every post in the export already cleared scoring. Since `010`'s `post`/`post_track` model stores every scored candidate regardless of threshold, screening is a query-time filter over `search_profile.min_match_score`, not a stored flag, per the **data model**'s `post_track` entry, this tier must be **synthesized**. The generator additionally emits a handful of `post`/`post_track` rows with `match_score` deliberately below the relevant track's `min_match_score`, so the UI's screened-out state and REQ-SRCH-09's threshold behavior have something real to filter. `run_log`/`job_batch`, the prototype's execution-log tables, were likewise never synced. `run_log` is entirely synthesized, see `TESTDATA-MAP-07`.

**TESTDATA-GAP-02 Apply attempts.** `apply-results.csv`, `apply-failed.csv`, and `apply-in-process.csv` are headers with zero data rows. The prototype's apply automation ran, but its output was apparently never committed back to the sheet, or the sheet was cleared before this export. The `010` `application` table therefore has **no real source data whatsoever**. What can be inferred: `applied-leads.csv`'s `applied` date column is a reliable signal that *a* successful apply happened, whether by the prototype's automation or manually. The generator derives one `application(status='applied')` row per such lead (`TESTDATA-MAP-06`). Every other one of REQ-APPLY-04's eight status codes (`questionnaire_required`, `cv_selector_error`, `unable_to_apply`, `post_unavailable`, `cv_not_found`, `post_closed`, `invalid_input`) has **zero real examples** and must be fabricated from scratch, clearly flagged as synthetic in the generator's own output/comments (`TESTDATA-GEN-04`).

**TESTDATA-GAP-03 Pre-apply lead stages.** Every row in `applied-leads.csv` already has an `applied` date populated. By construction, the export only contains leads that were *already applied to*. There is consequently **no real example of a lead at stage `PROSPECT` or `TOAPPLY`**, REQ-CRM-02's first two stages, before an apply attempt exists. These must be synthesized: a handful of `post`/`post_track` rows promoted into `lead` rows with no `applied_date`, some left at `PROSPECT`, at least one moved to `TOAPPLY` with a queued, not-yet-run, `application` row so REQ-APPLY-11 (removing a queued application) has something to act on.

**TESTDATA-GAP-04 `post` detail-pass fields.** `industry_classification` and `mcf_ref`, REQ-SRCH-06's detail-pass fields, appear in no CSV at all. `screened.csv`'s `description` column is populated for only a minority of rows. These stay `NULL` in generated seed rows rather than being fabricated. They are optional detail fields, and a `NULL` is itself a legitimate, testable state: a post that hasn't had its detail pass completed yet.

## 3. Column-level cleaning rules

01. **Percent-as-string → float.** `track-assignment.csv`'s `match_score` is a string like `"100%"`/`"62%"`. Convert to a `0-1` float (`"62%" → 0.62`), matching `post_track.match_score`'s documented range.
02. **Boolean spelling.** Source booleans appear as `'TRUE'`/`'FALSE'` (`track-assignment.csv`), `'1'`/`'0'`/`''` (`screened.csv`), and implied by tab membership (`open.csv` vs `closed.csv`). Normalize all to Python `bool`/SQLite `0`/`1` at the boundary, once, rather than re-parsing per field.
03. **Blank rows.** `open.csv` has at least one fully-blank leading data row, a stray sheet artifact. Skip any row whose `jobid` is empty, across every file.
04. **Redacted URLs.** Recent `MyCareerFutures`-sourced rows in `active.csv`/`open.csv` show `link` as literal `***`. The user appears to have redacted these before export, unrelated to any actual data-loss. Where `url_ref` is `***` or blank, synthesize a placeholder MCF-shaped URL from the post id, per the **mycareerfutures skill**'s URL scheme, rather than leaving it blank. The tier-2 fixture corpus keys detail pages off the URL slug (`ARCH-TEST-04`), so a null/garbage `url_ref` would silently break fixture wiring for those posts.
05. **`post.id` scheme already matches.** Most `jobid` values already are `{source}-{urlid}-{posted_date}`, for example `MyCareerFutures-771e413d7bc340c16dfeac6ba88503ff-2026-07-11`, exactly the **data model**'s documented `post.id` scheme, `source + posting_reference + posted_date`. These pass through as `post.id` unchanged. A small number of legacy rows in `applied-leads.csv`/`closed.csv` use a bare integer id (`jobid = "1"`, `"2"`, and so on) from a pre-migration era of the prototype and carry no embedded source/date. For these, synthesize a `post.id` in the target scheme using the row's `lead source` column as `source` and the nearest known date, `applied` minus a small offset, as `posted_date`.
06. **Excluded files.** `report.csv` and `post-statistics.csv` are pivot/aggregate views, weekly counts, a hand-built KPI table with merged header rows, with no stable row-per-entity shape. These are excluded from generation entirely. They exist in the export as sheet artifacts, not row-level source data.

## 4. Reference schema → target schema mapping

For each target table: source file(s), field mapping, and the transform/inference the generator applies. "Shift" below always refers to the single global date-shift anchor defined in `TESTDATA-MAP-08`. No field is date-shifted independently.

### `role`

Source: `track-cv.csv`'s `track` column, for example "Data Analyst", "Data Scientist", "GenAI Developer". The prototype has no role/seniority split, one `track` row per name, so each distinct name becomes exactly one `role.name`. `role.description` is left `NULL`.

### `track`

Source: `track-cv.csv` (`track_id`, `track`, `cv_version`).

| target field | source | notes |
| --- | --- | --- |
| `id` | `track_id` | direct |
| `role_id` | `track` (name) | FK lookup into generated `role` |
| `seniority` | — | no source signal; set to a constant placeholder (`"mid"`) for every row — flagged as synthetic since the prototype never modeled seniority independently of role name |
| `default_cv_id` | `cv_version` | FK lookup into generated `cv` (`TESTDATA-MAP` below) |
| `is_active` | — | `true` for all 9 source tracks; **TESTDATA-GAP**: no archived track exists in the source, so the generator additionally flips one track (the lowest-volume one by lead count, to minimize disruption to downstream row counts) to `is_active = false` — required by `ARCH-STO-04`'s "two tracks (one archived)" minimum, and must be called out as synthetic in generator output |

### `search_profile`

Source: `config.csv`, a single global row (`salary_min=10000`, `keywords="Data Scientist, Machine Learning, Gen AI, LLM"`, `match_score_min=0`, `age_weeks=4`). The prototype had one installation-wide config, not one per track, the exact gap REQ-SRCH-01/the **data model** already documents `010` closing. The generator broadcasts this config to every generated `track_id` as its `search_profile` row, **except** `keywords`, which is instead derived per track from that track's `role.name`, for example track "Sustainability Consultant" gets keywords seeded from that phrase, not the literal Gen-AI-flavored global config value, so each track's search profile is demo-plausible rather than nine identical rows. `min_match_score` is set to a non-zero value, for example `0.3`, rather than the source's literal `0`, since `0` would make `TESTDATA-GAP-01`'s below-threshold synthetic posts meaningless: nothing would ever fail the filter. `employment_type` defaults to `'Full Time'`, a constant matching the **data model**'s stated default, since there is no source field for it.

### `cv`

Source: distinct `cv_version` values across `track-cv.csv` (`13.2`, `11.4`, `14.0`). `cv.label` is the version string verbatim. Three rows.

### `post`

Primary source: `screened.csv` for scored posts. `track-assignment.csv` and `applied-leads.csv` fill in posts that reached a lead but aren't in `screened.csv`'s smaller 2085-row extract, since a post can be promoted into a lead even if the local `screened.csv` snapshot doesn't happen to include it. The sheet's various tabs were exported at different times.

| target field | source | notes |
| --- | --- | --- |
| `id` | `jobid` | per `TESTDATA-SRC` cleaning rules above |
| `source` | parsed from `jobid` prefix (`MyCareerFutures`, `LinkedIn`, …) | for legacy bare-integer ids, from `lead source` column instead |
| `position_title` | `screened.clean_title` / `deranked_title` / `position_title`, else `applied-leads.position` | first non-empty, in that precedence |
| `company_name` | `screened.company_name`, else `applied-leads.company` | |
| `url_ref` | `screened.url` / `applied-leads.link`, redaction-handled per `TESTDATA-SRC` rules | |
| `posted_date` | `screened.posted_date`, else parsed from `jobid` suffix, else `applied_date` minus a small synthetic offset | shifted |
| `salary_high` | `screened.salaryHigh` | |
| `is_open` | **derived, not copied from any single column** — see note below | |
| `closing_date` | `screened.closing_date` / `applied-leads.deadline` | shifted |
| `applicants` | `screened.applicants` | |
| `industry_classification`, `mcf_ref`, `description` | mostly absent | left `NULL` per `TESTDATA-GAP-04`; `description` populated only where `screened.description` is non-empty |
| `src_method` | see note below | `'scraped'` \| `'manual'` |
| `run_id` | FK into synthesized `run_log` | `TESTDATA-MAP-07` |

**`is_open` note:** the source data conflates *the lead's* status with *the posting's* own MCF lifecycle. `open.csv`/`closed.csv` tab membership reflects the user's pipeline state, not whether the listing is still live. Setting `post.is_open` from lead-closed status would incorrectly close a post whose lead was closed for `withdrawn`/`offer_accepted`. The posting may well still be live. Instead, `is_open` is derived independently from `closing_date` relative to the shifted "now": `closing_date < now ⇒ false`, else `true`. This reconstructs the field `010`'s model actually needs rather than passing through a conflated proxy.

**`src_method` note:** `screened.csv`'s `src_methodid` column is one of the two duplicated-header casualties (`TESTDATA-SRC-01`). After fixing the positional read, real values are sparse. Per the **prototype extraction**, `src_methodid=1` means manual, `0` means scraped, and manual entries were rare in practice, the generator defaults every post to `'scraped'` except rows identifiable as manual by having no hash-shaped `urlid` segment in their `jobid`, an id that couldn't have come from a scrape. This is a conservative heuristic, documented as such, that satisfies `STRAT-CASE-05`'s requirement for at least one seeded `'manual'` row without overclaiming precision on the rest.

### `post_track`

Primary source: `track-assignment.csv` (`jobid`, `trackid`, `match_score`), covering 3477 of 3478 lead jobids directly.

| target field | source | notes |
| --- | --- | --- |
| `post_id` | `jobid` | |
| `track_id` | `trackid` | |
| `match_score` | `match_score`, `"NN%"` → float | |
| `score_method` | — | constant `'title_keyword_v1'`, matching [010-prototype.md](010-prototype.md)'s actual `match.py` bigram-title method name |
| `search_match` | — | `true` for every row sourced from `track-assignment.csv`/`screened.csv` (both are search-pipeline outputs); `false` for rows belonging to a `post` tagged `src_method='manual'` (per REQ-SRCH-07, a manual post's track match is auto-assigned by scoring, not discovered by search) |

`TESTDATA-GAP-01`'s synthesized below-threshold posts get a `post_track` row here too, with `match_score` set below the owning track's `search_profile.min_match_score`. No separate table/flag exists for "screened out." It's purely a function of the two values at query time.

### `lead`

Primary source: `applied-leads.csv`, enriched by `open.csv.stage` for currently-open rows (`TESTDATA-SRC-02`).

**TESTDATA-MAP-04 status/stage translation table.** The prototype's `status`/`stage`/response-stages strings are free text, per the **prototype extraction**'s "Actual status values observed" section: only `"pending callback"` and `"expired"` were ever structured, everything else is ad hoc. Every distinct value observed in the export maps to `010`'s structured `lead.stage` (REQ-CRM-02) and, where terminal, `lead.close_reason`:

| source value | source column | → `lead.stage` | → `lead.close_reason` |
| --- | --- | --- | --- |
| *(blank, `applied_date` set, nothing more advanced)* | — | `APPLIED` | — |
| `1.1 resume screening dark` | `open.stage` | `APPLIED` | — |
| `1.2 resume screening active` | `open.stage` | `APPLIED` | — |
| `02 interview preparation` | `open.stage` | `INTERVIEW` | — |
| `0 duplicate` | `open.stage` | `CLOSED` | `duplicate` |
| `pending callback`, `pending response` | `status` | `APPLIED` | — |
| `information requested` | `status` | `CALLBACK` | — |
| `offer accepted` | `status` | `CLOSED` | `offer_accepted` |
| `offer rejected` | `status` | `CLOSED` | `withdrawn` *(candidate declined — see note)* |
| `rejected` | `status` | `CLOSED` | `rejected` |
| `expired` | `status` | `CLOSED` | `expired` |
| `duplicate` | `status` | `CLOSED` | `duplicate` |
| `withdrawal` | `status` | `CLOSED` | `withdrawn` |
| `1 activated`, `2 screening introduction` | `response-stages.stage` | `CALLBACK` | — |
| `3 detailed assessment` | `response-stages.stage` | `INTERVIEW` | — |
| `4 offer` | `response-stages.stage` | `OFFER` | — |
| `4 offer accepted` | `response-stages.stage` | `CLOSED` | `offer_accepted` |
| `4 offer rejected` | `response-stages.stage` | `CLOSED` | `withdrawn` |
| `5 rejected` | `response-stages.stage` | `CLOSED` | `rejected` |
| `6 withdrawal` | `response-stages.stage` | `CLOSED` | `withdrawn` |

Note on `offer rejected`: `010`'s close-reason enum, REQ-CRM section, has no dedicated "candidate declined an offer" code. `withdrawn`, "user withdrew from consideration," is the closest fit and is used consistently for both this and explicit `withdrawal` rows. `cancelled` and `apply_failed` have **no real-data source at all**. Like `TESTDATA-GAP-02`/`03`, at least one of each must be synthesized to satisfy `STRAT-CASE-05`.

**Multi-signal precedence.** A lead may have signals from more than one source, for example both an `open.stage` code and a `response-stages.csv` history. Since these are cumulative, reaching `INTERVIEW` implies `CALLBACK` already happened, the generator takes the **highest-progress** mapped stage across all available sources, ranked `PROSPECT < TOAPPLY < APPLIED < CALLBACK < INTERVIEW < OFFER < CLOSED`. For the terminal `close_reason` specifically, `applied-leads.status`, the archived CRM tab's own recorded reason, takes precedence over a `response-stages.csv` terminal event when both exist, since it's the field the user actually treated as authoritative in the prototype.

**TESTDATA-MAP-05 duplicate jobid → retry, not discard.** The 47 jobids appearing twice in `applied-leads.csv` (`TESTDATA-SRC-03`) are genuine re-application history, not export noise. Rather than fabricating a synthetic apply retry for `STRAT-SILO-06`'s "each apply outcome reachable" goal, the generator uses these directly: one `lead` row, taking the later/more-advanced of the two source rows as canonical since `lead.post_id` must be unique, with **two** `application` rows attached (`TESTDATA-MAP-06`). This is a real, naturally-occurring example of REQ-APPLY-08's "a retried attempt is a new row, not an overwrite," at no synthesis cost.

Other field mappings, five groups.

01. `title_override`/`company_override` map to `NULL` for every migrated row, since the prototype has no equivalent concept, so nothing was ever overridden.
02. `deadline`/`applied_date`/`first_attempt_date`/`last_contact_date`/`notes` copy directly from `applied-leads.deadline`/`applied`/`1st attempt`/`last contact`/`notes` (shifted where a date).
03. `track_id` comes from the `track` column, a direct numeric FK into `track-cv.csv`'s `track_id`.
04. `created_at` comes from the earliest known activity date, `applied_date`, falling back to `posted_date` minus a small offset if even that's missing.
05. `updated_at` comes from the latest known activity date across the lead's own fields and any matched `response-stages.csv` events.

### `lead_event`

Primary source: `response-stages.csv` (jobid, date, stage, notes), a literal activity log covering 210 jobids directly. `callbacks.csv`/`interviews.csv`/`offers.csv` are 100%-redundant filtered views of the same 210 jobids (`TESTDATA-SRC` inventory) and are not read separately.

For the roughly 3268 leads with no `response-stages.csv` entry, the large majority, since most of the prototype's real activity logging was informal, living only in free-text `notes`/date columns, not the structured log, the generator synthesizes minimal `lead_event` rows from the lead's own populated date columns: `applied_date` produces one `stage_change` event (old→new: `PROSPECT`→`APPLIED`), `first_attempt_date`/`last_contact_date` produce `contact_logged` events, any terminal `close_reason` produces a final `stage_change` event to `CLOSED`. This is necessary, not optional. Without it, `lead.updated_at`, which REQ-CRM-05's 28-day auto-expiry keys off, per `ARCH-STO-05`, has no event backing it, and the UI's activity-history view would be empty for the majority of seeded leads.

`event_type` mapping: a `response-stages.stage` transition maps to `stage_change`, with `detail` set to the mapped target stage plus the source `notes` text, subject to the anonymization rule (`TESTDATA-GEN-05`). `occurred_at` is the source `date`, shifted.

### `application`

No real source data (`TESTDATA-GAP-02`). Two generation paths.

01. **Derived from real leads.** Every lead with a populated `applied_date` gets one `application(status='applied', attempted_at=applied_date [shifted], cv_id=track.default_cv_id)` row. The 47 retry pairs (`TESTDATA-MAP-05`) get two rows instead of one, `attempted_at` ordered per the two source rows' dates.
02. **Fabricated for enumeration completeness.** `STRAT-CASE-05`/`STRAT-SILO-06` require every one of REQ-APPLY-04's eight status codes to be reachable from seed data. Since real data only ever produces `'applied'`, the generator fabricates one `application` row per remaining code (`questionnaire_required`, `cv_selector_error`, `unable_to_apply`, `post_unavailable`, `cv_not_found`, `post_closed`, `invalid_input`) against small synthetic `post`/`lead` pairs created specifically for this purpose, not against real historical leads, so it's unambiguous in the generator's own labeling which rows are invented. REQ-APPLY-10 additionally requires that the `post_closed`/`post_unavailable` fabricated applications' *owning leads* are `CLOSED` with `close_reason='apply_failed'`. These two fabricated lead+application pairs are constructed together, not independently, so the requirement's linkage is actually exercised rather than each half being separately true by coincidence.

`run_id` FKs into a synthesized apply-type `run_log` row, grouped by shifted `attempted_at` date (`TESTDATA-MAP-07`).

### `run_log`

No source data (`TESTDATA-GAP-01`). Entirely synthesized, two `run_type`s:

- **`search`**: one row per (`track_id`, distinct posted-week) bucket found in the generated `post`/`post_track` rows. `outcome_counts = {"new_posts": <count in that bucket>}`, `status='success'`, `started_at`/`ended_at` a few minutes apart, anchored near that bucket's earliest `posted_date`.
- **`apply`**: one row per distinct shifted `attempted_at` day across all generated `application` rows. `status='success'` for days containing only `'applied'` outcomes, `'partial'` for a day the generator has deliberately placed one of the fabricated failure-outcome applications on, with `error_detail` populated.

`ARCH-STO-04` requires seed `run_log` rows in each status (`running`/`success`/`partial`/`failed`). Since no real run is ever mid-flight or fully failed in historical data, the generator adds one purely synthetic `run_log(status='running', ended_at=NULL)` and one `run_log(status='failed', error_detail=<placeholder>)`, both clearly synthetic and not linked to any real post/application.

### `session`

No source data. Real MCF session cookies are explicitly out of scope to ever hold, per CLAUDE.md's boundary. Seed emits a single singleton row with `status='missing'`, the safe default, since nothing in the seeded state implies apply automation can reach the live site. Any test needing `status='valid'` inserts its own row directly via `db_util.py` (`STRAT-SILO-01`) rather than relying on seed data implying a working session exists.

**TESTDATA-MAP-08 The global date-shift anchor.** `ARCH-STO-05` requires seed dates to be relative-to-load-time, not absolute. The source data's date columns already encode meaningful **day-count deltas** that later become test assertions. `callbacks.csv`'s `callback_days`, `interviews.csv`'s `call_int_days`/`app_int_days`, `offers.csv`'s `*_days` columns, and `open.csv`'s precomputed `age_days` are all differences between two dates in the same row. Shifting each date column independently, for example "make every `applied_date` 10 days ago" without correspondingly shifting `last_contact_date`, would destroy those deltas and could produce nonsensical rows, such as a callback dated before its lead was applied to. Instead, the generator computes **one** shift delta at generation time, `anchor = (today) - (latest date appearing anywhere in the source data)`, and applies that single delta to every date/timestamp field, in every table, uniformly. Relative gaps between dates are exactly preserved. Only the whole timeline's position relative to "now" moves. This is also what makes REQ-CRM-05's 28-day-expiry boundary cases (`STRAT-CASE-03`) land where the generator intends: a lead's real day-count gap since last activity is preserved by the shift, so picking source rows with the right historical gap is sufficient to seed both sides of the boundary without hand-computing dates.

## 5. Two output modes, one generator

**TESTDATA-GEN-01** The same generation logic produces two different outputs, selected by a `--mode` flag:

- **`--mode seed`** — the minimum enumeration `ARCH-STO-04` already specifies: two tracks including one archived, all `src_method` values, leads at every stage including `CLOSED` with every close reason, applications covering all eight REQ-APPLY-04 codes, `run_log` rows in every status. This is small, tens of rows, deterministic, fixed `--rand-seed`, and **committed** as `seed/*.sql`. This is what every test tier and `resetdb.py --seed` loads.
- **`--mode sample`** — a larger, realistic-volume dataset built from the full historical CSVs, hundreds of leads spanning years of real activity, for a developer manually exploring the UI/CRM screens at a scale closer to real use: pagination, list performance, a track with genuinely dozens of leads in flight. **Not committed** — see `TESTDATA-GEN-05`.

Both modes share every mapping rule in section 4. `seed` mode simply caps how many rows of each kind are emitted, enough to hit every enum value once or twice, where `sample` mode emits everything the source data supports.

**TESTDATA-GEN-02** Entry point: `scripts/gen_test_data.py`, with a thin bash wrapper `scripts/gen_test_data.sh`, matching the existing `scripts/initdb.py`/`scripts/resetdb.py` naming from the **architecture doc**'s repo layout, that activates `env` and invokes it. Per CLAUDE.md, generating database seed/sample data is an operational-lifecycle task, "DB init/seed," not a one-time/throwaway dev task, so it belongs in `env`, never an ad hoc venv.

```
scripts/gen_test_data.py --mode seed --out seed/ --rand-seed 42
scripts/gen_test_data.py --mode sample --out test-data/sample.sql --rand-seed 42 --anchor today
```

Flags: `--mode {seed,sample}`; `--out`, a directory for `seed`, one `.sql` file per table matching `ARCH-STO-04`'s "diffs and reviews like code," or a single file path for `sample`; `--rand-seed`, determinism for which rows get picked/fabricated when capping to `seed` mode's small counts, and for the synthetic-tier choices in `TESTDATA-GAP-01/02/03`; `--anchor`, defaulting to the current date, overridable so a test run can pin the shift for reproducing a specific boundary scenario.

**TESTDATA-GEN-03** Idempotent and non-incremental. Each run regenerates its full output from the source CSVs plus the current anchor date. There is no merge with a prior run's output. This matches `ARCH-STO-02`'s "recreate, don't migrate" philosophy applied one layer up.

**TESTDATA-GEN-04 Validate at generation time, not load time.** Before writing output, the generator applies the generated SQL against a scratch temp database, reusing `easymcf/db/schema.sql` + `scripts/db_util.py`'s connection handling (`STRAT-SILO-01`), and confirms it loads cleanly. FK violations, a `post_id` reused across two `lead` rows, the uniqueness rule in the **data model**'s `lead` section, or a duplicate PK surface here, at generation time with the offending row identified, rather than as an opaque failure the next time someone runs `resetdb.py --seed`. Every fabricated, non-source-derived, row from `TESTDATA-GAP-01/02/03` and `TESTDATA-MAP-04`'s `cancelled`/`apply_failed` cases is emitted with a SQL comment noting it's synthetic and which gap it fills, so a future reader of `seed/*.sql` can tell real-derived history from invented enumeration filler at a glance.

**TESTDATA-GEN-05 Privacy: source data is real personal history, seed data is not.** `test-data/*.csv` contains the user's actual job-search activity. `notes` free-text fields name real people, recruiters, hiring managers, by first name, for example "response from Giri invitation…", "interview with Tech lead co-founder Jane", and `response-stages.csv`'s `notes` similarly. This is different in kind from `post`'s company/title/salary fields, which are public job-posting facts. Two consequences follow.

01. `test-data/`, the source CSVs, must be added to `.gitignore`. It is currently untracked, `git status` shows `?? test-data/`, but that only means it hasn't been committed yet, not that it's safe to. It should never be committed.
02. The **committed** `seed/*.sql` never carries real free-text `notes`/`lead_event.detail` verbatim. The generator replaces any `notes`/`detail` field sourced from real rows with a genericized placeholder, for example "Interview scheduled with hiring manager" instead of a real name, while still preserving the *structural* signal, which stage, which date, that the field's presence/absence is meant to test. The uncommitted, gitignored `--mode sample` output is not subject to this rule. It's local-only, for a developer's own manual exploration, the same trust boundary as `test-data/` itself.

## 6. Open questions for milestone 08

- Whether `--mode sample`'s output is worth generating at all in `010`, or whether the `seed` set, already covering every enumeration, is sufficient and `sample` is deferred until someone actually hits a UI-scale limitation worth testing against. This is a product-manager call, not a data-modeling one.
- The `role.seniority`/`track` seniority placeholder (`TESTDATA-MAP` `track` section) is a guess with no source signal. If a future milestone wants seniority to matter for scoring or filtering, this seed value will need deliberate re-authoring, not just regeneration.
- Whether the `is_active=false` track flip, picking "lowest lead count," should instead be a fixed, named track chosen for narrative sense in demos, for example "Academic," clearly a track the user stopped pursuing. This is a cosmetic call for whoever builds the demo walkthrough.
</content>
