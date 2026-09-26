---
name: easymcf-jobs-pipeline
description: Domain knowledge for easymcf's search-by-keywords and match-scoring feature (REQ-SRCH-01..11) — tracks/search profiles, the scrape-dedup-detail-score pipeline, the swappable scoring-method constraint, and the scheduled-run mechanism. Use when implementing or reviewing track configuration, search runs, posting persistence, or match scoring.
---

# Jobs pipeline: search by keywords

Implements [010-01-requirements.md](../../../docs/releases/010/010-01-requirements.md)'s "Search by keywords" section (REQ-SRCH-01..09). For scrape mechanics and site markup, see [mycareerfutures](../mycareerfutures/SKILL.md) and [webscraping](../webscraping/SKILL.md); for the browser-automation layer, see [playwright](../playwright/SKILL.md).

## Core entities

- **track** — a user's role at a seniority level (e.g. "Data Engineer, Senior"), carrying exactly one search profile.
- **search profile** — a track's keyword(s), minimum salary, maximum posting age, employment type (defaults Full Time), and its scheduled-run configuration (REQ-SRCH-11): an on/off switch, a repeat interval, and the next run time.
- **posting** — source-of-truth listing (role/company/URL), not user-specific; found by search or entered manually.
- **match score** — 0–1 relevance score for the one (posting, track) pairing a posting carries, recorded with the *method* that produced it (REQ-SRCH-09), so an alternative method (e.g. BERT-based) can be added later without a schema change. This release's own method, `search_match_v1`/`manual_v1`, writes a fixed `1.0` on every pairing — a track's own keywords already are the whole of its relevance filter. See `mcfpipe`'s `track_score` table (`method` column) in [010-prototype.md](../../../docs/releases/010/010-prototype.md) for the reference shape a differentiating method would follow.

## Pipeline shape

1. **Search run** (REQ-SRCH-02/03): triggered on demand from the UI for one track, or automatically once that track's schedule comes due (REQ-SRCH-11) — an in-process tick thread, not an OS-level cron/scheduler; either trigger runs the same pipeline and writes the same `run_log` row, distinguished by `trigger_source`. Pages a keyword's search results until a page returns zero results (see [mycareerfutures](../mycareerfutures/SKILL.md) URL scheme), capturing title, company, reference/URL, posted date, salary-if-shown per card.
2. **Persist incrementally** (REQ-SRCH-04): write postings as found, not only at sweep end — this is the specific defect the prototype had; see [webscraping](../webscraping/SKILL.md).
3. **Dedup** (REQ-SRCH-05): stable identifier from source + posting reference + posted date.
4. **Detail fetch** (REQ-SRCH-06): distinct second pass over postings not yet detailed; a posting found closed during this pass is flagged `is_open=false` and kept, not removed or retained stale.
5. **Manual entry** (REQ-SRCH-07): same downstream schema as scraped postings, naming the one track it belongs to on the request — there is no auto-assignment against multiple tracks.
6. **Fixed scoring, no screen** (REQ-SRCH-09): every pairing, scraped or manual, writes the same fixed match score — a track's own search keywords, or the track named on a manual entry, already are the whole of relevance screening. Nothing is filtered out of promotion by score. A configurable max-age filter exists only for what the Posts screen displays.

## What not to fix here

The prototype's scoring approach (bigram title matching + salary-percentile bucket, see [010-prototype.md](../../../docs/releases/010/010-prototype.md)) is a *starting point* for a future differentiating method, milestone 16, not a fixed implementation to reproduce now — don't treat its exact math as a requirement. What must be preserved regardless of the eventual algorithm: the score is per (posting, track), stored with its method, and a post carries exactly one such pairing.

## Dependency note

The exact schema (track/search_profile/posting/job_track/track_score tables) is owned by the data-model milestone (milestone 05 in [010-release-milestones.md](../../../docs/releases/010/010-release-milestones.md)); `mcfpipe`'s reference data model in [010-prototype.md](../../../docs/releases/010/010-prototype.md) is a starting point, not a decided schema — confirm current schema state before assuming table/column names.
