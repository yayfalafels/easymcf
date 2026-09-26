---
name: playwright
description: Playwright (Python, sync API) browser-automation patterns for headless Chromium — auto-waiting/explicit waits in place of fixed sleep() calls, resilient element locators, and bounded retry loops. Use when writing or reviewing any Playwright code in this project.
---

# Browser automation patterns

`ARCH-BOT-01` fixes Playwright (Python) with its bundled Chromium as the single browser dependency for search scraping, apply automation, and end-to-end tests alike — there is no Selenium anywhere in this project.

## Replace fixed sleeps with (auto-)waits

The `jobsearch` prototype used fixed sleeps (15s after each page load, 4s between pages) with no adaptive/explicit waits — the single biggest reason its full sweeps ran to 15+ minutes (`mcfpipe/docs/enhancements.md` #06). This project does not repeat that. Playwright's actionability checks (`click()`, `fill()`, etc.) auto-wait for the target element by default, so most of the prototype's manual wait logic simply disappears; where a condition needs to be waited on explicitly (e.g. before reading page content, or when polling for something that isn't itself an action), use `page.wait_for_selector` / `locator.wait_for` with a bounded `timeout`, which polls rather than blocking for a fixed duration regardless of how fast the page actually rendered:

```python
from playwright.sync_api import Page

def apply_button(page: Page):
    button = page.locator("button#job-details-apply-button")
    button.wait_for(state="visible", timeout=10_000)
    return button
```

Set a per-call `timeout` rather than relying only on the global default — a slow page load and a genuinely-missing element should surface differently. Reference: [Playwright — Auto-waiting](https://playwright.dev/python/docs/actionability).

## Prefer stable, semantic locators

The prototype already does this well for MCF — use `page.get_by_test_id(...)` (or `page.locator("[data-testid=...]")` where the attribute is `data-cy`; see [mycareerfutures](../mycareerfutures/SKILL.md) for the specific selectors) over positional/structural selectors (`div > div:nth-child(3)`), IDs that look auto-generated, or text-content matches that could shift with copy changes. A `data-testid` is far less likely to change than markup structure or wording, and its absence is itself a signal worth surfacing (see markup-drift note below) rather than silently falling back to a fragile alternative.

## Bounded retry, not infinite or single-shot

REQ-APPLY-07 requires the apply-button detection step to retry a bounded number of times with a delay between attempts, rather than failing on the first miss (a single slow page load must not immediately fail the job) or retrying forever. Mirror the prototype's shape (`MAX_RETRY` attempts, fixed `RETRY_DELAY_MS` between them, terminal status if exhausted) — see [easymcf-apply](../easymcf-apply/SKILL.md) for where this plugs into the outcome state machine. Keep the retry bound and delay as named, overridable constants, not inlined magic numbers — the exact values are an open design-milestone question (see [010-01-requirements.md](../../../docs/releases/010/010-01-requirements.md) open questions), not this skill's to fix.

## Headless setup

Run headless Chromium (`playwright.chromium.launch(headless=True)`) for automated/test contexts; a visible browser (`headless=False`) is only for interactive debugging the user runs themselves. Keep browser/context setup in one place (a fixture or factory function) rather than repeated inline per script, so headless vs. visible mode is a single toggle. `page.route()` interception on this same browser/context is also what makes the mock-e2e test tier possible without a stub that bypasses the real scraping code (`ARCH-TEST-04`).

## When a locator stops matching

Don't assume the automation logic is wrong before checking whether the target site's markup changed — see [mycareerfutures](../mycareerfutures/SKILL.md)'s note on markup drift as the normal failure mode for this project's scrapers and apply automation.
