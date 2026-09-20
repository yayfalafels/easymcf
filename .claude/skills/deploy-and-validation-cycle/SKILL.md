---
name: deploy-and-validation-cycle
description: The local run-and-verify loop for easymcf — how to exercise a change end-to-end before reporting it complete. No cloud deploy exists in 010; this is the local equivalent. Use before reporting any nontrivial backend, frontend, or automation change as done.
---

# Deploy and validation cycle (local)

`010` has no cloud deploy step (REQ-PLAT-04) — "deploy" here means running the local backend/frontend/database and exercising the change, matching this project's general practice of verifying behavior rather than only relying on type checks or unit tests (see the top-level `verify` skill for the general version of this practice).

Run backend/scraping/apply/DB commands through the `env` operational venv, nested in the repo (`env/bin/python`, never a throwaway one-off env) — see [local-infra-navigation](../local-infra-navigation/SKILL.md#python-virtual-environments--hard-rule).

## Start → reset → run → stop

```bash
env/bin/python scripts/envcheck.py                          # preflight — catches an environment defect before it's misread as a code bug
env/bin/python scripts/resetdb.py --seed                    # clean, seeded db every time — never carry state between checks
env/bin/python -m easymcf &                                   # start
curl -sf http://127.0.0.1:5000/api/v1/health                  # confirm it's up
# ... exercise the golden path below, via the browser and/or scripts/api_tester.py ...
kill %1                                                        # stop
```

Before reporting *any* nontrivial change done, also run the closed automated loop — `env/bin/python scripts/envcheck.py && env/bin/python -m pytest` — which covers all three non-live tiers (backend, frontend, e2e) in one command.

## Golden-path validation per functional area

Once the local stack is runnable, before reporting a change in a given area as complete, exercise its golden path against seed data (never the live MCF site — see [mycareerfutures](../mycareerfutures/SKILL.md)'s hard rule):

- **[easymcf-jobs-pipeline](../easymcf-jobs-pipeline/SKILL.md) changes** — run a search for a seeded track, confirm postings persist incrementally (kill the run partway and confirm no data loss), confirm dedup on a re-run, confirm match scores appear with their method recorded.
- **[easymcf-crm](../easymcf-crm/SKILL.md) changes** — take a seeded `TOAPPLY` lead through `APPLIED`, `CALLBACK`, and `INTERVIEW`, move it to `OFFER` through an offer, confirm `CLOSED` is reachable from every stage (a lead at `OFFER` through its offer status), confirm an `APPLIED`/`INTERVIEW`/`CLOSED` lead past its deadline does *not* flip to `EXPIRED`.
- **[easymcf-apply](../easymcf-apply/SKILL.md) changes** — run the apply queue against seed/fixture postings (mocked or fixture-driven browser automation, not live MCF), confirm each outcome code in the vocabulary is reachable and one lead's failure doesn't block or overwrite others.
- **[easymcf-backend-api](../easymcf-backend-api/SKILL.md) changes** — hit the affected CRUD endpoint(s) directly (`scripts/api_tester.py --case FILE`, batch or single-named-case — see `local-infra-navigation`'s Validation utilities section — or `curl`/httpie for a true one-off), confirm schema validation errors return the documented 400/404 shape, confirm the run-history log entry is written.
- **[easymcf-frontend](../easymcf-frontend/SKILL.md) changes** — load the affected screen in a browser, or replay it via `scripts/ui_tester.py --case FILE` for a structured PASS/FAIL/ERROR verdict plus a failure screenshot, confirm the golden path and at least one error path (e.g. a failed run) surface in the UI, not just the console.

## Reporting completion

Don't report a nontrivial change as done based on type-checks or a passing unit test suite alone if it has a runtime surface to drive — state explicitly if you were unable to exercise it end-to-end (e.g. no local stack running yet) rather than implying it was verified.
