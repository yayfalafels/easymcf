---
name: easymcf-jobs-pipeline
description: Domain knowledge for easymcf's search-by-keywords and match-scoring feature (REQ-SRCH-01..09) — tracks/search profiles, the scrape-dedup-detail-score pipeline, and the swappable scoring-method constraint. Use when implementing or reviewing track configuration, search runs, posting persistence, or match scoring.
---

# Jobs pipeline: search by keywords

Implements [010-01-requirements.md](../../../docs/releases/010/010-01-requirements.md)'s "Search by keywords" section (REQ-SRCH-01..09). For scrape mechanics and site markup, see [mycareerfutures](../mycareerfutures/SKILL.md) and [webscraping](../webscraping/SKILL.md); for the browser-automation layer, see [playwright](../playwright/SKILL.md).

## Core entities

- **track** — a user's role at a seniority level (e.g. "Data Engineer, Senior"), carrying exactly one search profile.
- **search profile** — a track's keyword(s), minimum salary, maximum posting age, employment type (defaults Full Time).
- **posting** — source-of-truth listing (role/company/URL), not user-specific; found by search or entered manually.
- **match score** — 0–1 relevance score per (posting, track) pair, recorded with the *method* that produced it (REQ-SRCH-09), so an alternative method (e.g. BERT-based) can be added later without a schema change. See `mcfpipe`'s `track_score` table (`method` column) in [010-prototype.md](../../../docs/releases/010/010-prototype.md) for the reference shape.

## Pipeline shape

1. **Search run** (REQ-SRCH-02/03): triggered on demand from the UI for one track. Pages a keyword's search results until a page returns zero results (see [mycareerfutures](../mycareerfutures/SKILL.md) URL scheme), capturing title, company, reference/URL, posted date, salary-if-shown per card.
2. **Persist incrementally** (REQ-SRCH-04): write postings as found, not only at sweep end — this is the specific defect the prototype had; see [webscraping](../webscraping/SKILL.md).
3. **Dedup** (REQ-SRCH-05): stable identifier from source + posting reference + posted date.
4. **Detail fetch** (REQ-SRCH-06): distinct second pass over postings not yet detailed; a posting found closed during this pass is removed from the active set, not retained stale.
5. **Manual entry** (REQ-SRCH-07): same downstream schema as scraped postings; bypasses the match-score filter below.
6. **Scoring & screening** (REQ-SRCH-09): compute per-track match score; screen by configurable max age and min score, except manual entries.

## What not to fix here

The prototype's scoring approach (bigram title matching + salary-percentile bucket, see [010-prototype.md](../../../docs/releases/010/010-prototype.md)) is a *starting point* for the design milestone, not a fixed implementation to reproduce — don't treat its exact math as a requirement. What must be preserved regardless of the eventual algorithm: the score is per (posting, track), stored with its method, and manual entries bypass filtering.

## Dependency note

The exact schema (track/search_profile/posting/job_track/track_score tables) is owned by the data-model milestone (milestone 05 in [010-release-milestones.md](../../../docs/releases/010/010-release-milestones.md)); `mcfpipe`'s reference data model in [010-prototype.md](../../../docs/releases/010/010-prototype.md) is a starting point, not a decided schema — confirm current schema state before assuming table/column names.
