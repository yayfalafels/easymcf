---
name: mycareerfutures
description: Site-structure knowledge for mycareersfuture.gov.sg (MCF) — search URL scheme, job-card and profile-page markup, posting lifecycle, and the apply-flow DOM. Use when writing, reading, or debugging any code that scrapes, parses, or automates MCF pages, or when a scraper/apply run starts producing unexpected empty results (possible markup drift).
---

# MyCareersFuture (MCF) site structure

Domain knowledge about the target site, extracted from the `jobsearch` prototype (`agent.py`, `mcf_profile.py`, `apply.py`). This is knowledge about the *site*, independent of easymcf's own implementation — see [easymcf-jobs-pipeline](../easymcf-jobs-pipeline/SKILL.md) and [easymcf-apply](../easymcf-apply/SKILL.md) for how this project uses it.

## Hard rule

Never issue a request against the live `mycareersfuture.gov.sg` domain from an automated dev/test session. Development and tests run against seed/local fixture data (REQ-DEV-03). Only run live against MCF when the user explicitly asks to do so interactively, and never write live responses into fixture/seed data as if they were synthetic.

## Search results page

URL scheme (`JobSearchWebsite.jobsearch_URLquery()`):

```
search?search={keyword}&salary={level}&employmentType=Full%20Time&sort=new_posting_date&page={n}
```

Paginate `page=0,1,2,...` until a page returns zero matching cards — there is no total-count field to read instead.

Per-card fields and selectors (`get_jobRecord_fromcard`):

| field | selector |
| --- | --- |
| `position_title` | `span[data-testid="job-card__job-title"]` |
| `company_name` | `p[data-testid="company-hire-info"]` |
| `posted_date` | `span[data-cy="job-card-date-info"]` — text like "Posted today/yesterday/N days ago"; parse to an actual date, don't store the raw string |
| `salaryHigh` | top figure from a `$`-containing span under `[data-testid="salary-range"]` |
| `urlid` | slug from the card's `<a href>`, with the `/job/` prefix and any query string stripped |
| card container | elements whose `id` starts with `job-card-` |

Cards render client-side — a plain HTTP GET without JS execution will not see them; a real (or headless) browser render is required, which is why this project uses Playwright (see [playwright](../playwright/SKILL.md)) rather than `requests` alone for this page.

## Deterministic posting id

`jobid = f"{source}-{urlid[-32:]}-{posted_date}"`, source hardcoded `"MyCareerFutures"`. This is the identifier used for de-duplication — never a database auto-increment. See [webscraping](../webscraping/SKILL.md) for why a stable, content-derived id matters more generally.

## Posting detail page

Fetched as a distinct second pass, one page load per posting (`update_job_profiles`). Fields (`FIELD_CONFIG`, a declarative tag/attribute/keyword lookup — brittle to markup changes by design, hence the drift risk below):

- `is_open` — checked first. The expiry-date field containing the word "Closed" means the posting is closed; if closed, stop here and treat the posting as inactive rather than scraping the remaining fields.
- `mcf_ref` — MCF's own reference code for the posting.
- `closing_date` — format `%d %b %Y`.
- `applicants` — integer count.
- `industry_classification`.
- `description` — full text body.
- `years_experience` exists in the prototype's field config but was never populated — do not treat its presence in old code as evidence the field is reliably scrapable.

## Apply flow (single-step "1-click")

Selectors from `apply.py`, used against an already-authenticated session (a loaded cookie jar) — this project never automates login:

| step | selector / signal |
| --- | --- |
| apply button | `button#job-details-apply-button` |
| already-applied / closed detection | status text in `p[data-testid="job-apply-error"]` — "already"/"applied" → treat as success; "closed"/"no longer" → posting closed |
| resume/CV cards | `div[data-testid="resume-card"]` → `a.resume-link` (title text) → its radio input |
| advance after CV select | `button#application-details-save-button` |
| final submit | `button#job-application-review__submit-button` |

A failed final submit is *inferred* (not confirmed by an explicit questionnaire indicator) to mean the posting requires a multi-step questionnaire — see [easymcf-apply](../easymcf-apply/SKILL.md) for the full outcome state machine this feeds into.

## Markup drift is the normal failure mode

MCF's page markup changes over time without notice; the prototype's `recommission.py` exists purely to catch this (six sequential smoke checks: load browser → load search page → find cards → parse a card → parse a profile page → run screening). If a scraper or apply run starts returning zero/empty results where seed-data tests still pass, suspect drift against the selectors above before suspecting the scraping logic itself — check the *current* live DOM (manually, or via a user-run one-off session) against this table rather than guessing.
