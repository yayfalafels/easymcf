---
name: webscraping
description: General web-scraping engineering patterns — incremental persistence, stable dedup identifiers, separating discovery/list passes from detail passes, and defensive HTML parsing with BeautifulSoup. Use when implementing or reviewing any scraper in this project, independent of which site it targets. Pair with the mycareerfutures skill for MCF-specific markup.
---

# Web scraping engineering patterns

Site-independent lessons learned from the `jobsearch` prototype's scraper (`agent.py`, `mcf_profile.py`) and the enhancements `mcfpipe` flagged but never shipped. See [mycareerfutures](../mycareerfutures/SKILL.md) for the MCF-specific selectors these patterns apply to in this project.

## Persist incrementally, not at the end of a run

`jobsearch`'s `update_jobRecords()` accumulated an entire multi-keyword, multi-page sweep into one in-memory DataFrame and wrote to the database only once at the end — a crash partway through a run lost everything scraped in that run. This project fixes that (REQ-SRCH-04): write each newly-found record (per page, or per keyword/salary combination scraped) as soon as it's captured, so a failure partway through preserves everything captured up to that point. When implementing a scrape loop, structure it so the persistence call sits inside the innermost loop that produces a complete, storable unit — not after the outer sweep finishes.

## Build dedup identifiers from content, not sequence

Don't rely on a database auto-increment or scrape order to detect "have I seen this before." Derive a stable id from fields that identify the *thing itself* — source + a stable reference/slug + a date, per [mycareerfutures](../mycareerfutures/SKILL.md)'s `jobid` scheme — so re-running the same scrape against the same content produces the same id and a straightforward set-difference against already-known ids tells you what's actually new.

## Separate discovery from detail

Treat "find out what postings exist" (search/list pages, cheap, high volume) as a distinct pass from "get the full detail for one posting" (profile page, one request per item, more expensive). Run detail-fetch as a second pass over the set difference (`known_postings - already_detailed`), capped by a configurable batch limit per run, rather than fetching full detail inline while paginating search results. This keeps a single slow/failing detail fetch from blocking discovery of the rest of the current page, and lets a capped detail-fetch run be safely re-invoked to pick up where it left off.

## Parse defensively

Site markup will contain cards/fields that don't match the expected shape (missing salary, unusual date phrasing, a field element absent entirely). A single malformed card must not abort the whole page's extraction — skip/log the field or the card and continue. Don't let one bad record turn into a bare `except: pass` either (`jobsearch`'s biggest logging gap, per [010-prototype.md](../../../docs/releases/010/010-prototype.md)) — record what happened somewhere durable (see [easymcf-backend-api](../easymcf-backend-api/SKILL.md)'s run-logging requirement) so a partial-failure run is diagnosable without re-running it.

## Be a polite scraper

Space out requests against the same host (the prototype used fixed sleeps for this, which this project replaces with explicit waits for *rendering readiness* — see [playwright](../playwright/SKILL.md) — while still keeping reasonable spacing between page loads to avoid hammering the target site). Never parallelize requests against a single external site beyond what the site can reasonably absorb, and never run scraping code against the live site in an automated/unattended context — see the hard rule in [mycareerfutures](../mycareerfutures/SKILL.md).
