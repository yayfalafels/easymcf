---
name: selenium
description: Selenium/Playwright browser-automation patterns for headless Chrome — explicit waits (WebDriverWait + expected_conditions) in place of fixed sleep() calls, resilient element locators, and bounded retry loops. Use when writing or reviewing any Selenium or Playwright code in this project.
---

# Browser automation patterns

## Replace fixed sleeps with explicit waits

The `jobsearch` prototype used fixed sleeps (15s after each page load, 4s between pages) with no adaptive/explicit waits — the single biggest reason its full sweeps ran to 15+ minutes (`mcfpipe/docs/enhancements.md` #06). This project does not repeat that. Use `WebDriverWait` with `expected_conditions`, which polls every 500ms up to a timeout rather than blocking for a fixed duration regardless of how fast the page actually rendered:

```python
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

wait = WebDriverWait(driver, 10)
element = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button#job-details-apply-button")))
```

Use a short or zero implicit wait if any is set at all — mixing a long implicit wait with explicit waits produces confusing, additive timing. Prefer condition-specific waits (`visibility_of_element_located`, `element_to_be_clickable`, `presence_of_element_located`) over a generic "wait N seconds and hope." Reference: [Selenium — Waiting Strategies](https://www.selenium.dev/documentation/webdriver/waits/).

## Prefer stable, semantic locators

The prototype already does this well for MCF — use `data-testid`/`data-cy` attributes (see [mycareerfutures](../mycareerfutures/SKILL.md) for the specific selectors) over positional/structural selectors (`div > div:nth-child(3)`), IDs that look auto-generated, or text-content matches that could shift with copy changes. A `data-testid` is far less likely to change than markup structure or wording, and its absence is itself a signal worth surfacing (see markup-drift note below) rather than silently falling back to a fragile alternative.

## Bounded retry, not infinite or single-shot

REQ-APPLY-07 requires the apply-button detection step to retry a bounded number of times with a delay between attempts, rather than failing on the first miss (a single slow page load must not immediately fail the job) or retrying forever. Mirror the prototype's shape (`MAX_RETRY` attempts, fixed `RETRY_DELAY_MS` between them, terminal status if exhausted) — see [easymcf-apply](../easymcf-apply/SKILL.md) for where this plugs into the outcome state machine. Keep the retry bound and delay as named, overridable constants, not inlined magic numbers — the exact values are an open design-milestone question (see [010-01-requirements.md](../../../docs/releases/010/010-01-requirements.md) open questions), not this skill's to fix.

## Headless setup

Run headless Chrome for automated/test contexts; a visible browser is only for interactive debugging the user runs themselves. Keep browser/driver setup in one place (a fixture or factory function) rather than repeated inline per script, so headless vs. visible mode is a single toggle.

## When a locator stops matching

Don't assume the automation logic is wrong before checking whether the target site's markup changed — see [mycareerfutures](../mycareerfutures/SKILL.md)'s note on markup drift as the normal failure mode for this project's scrapers and apply automation.
