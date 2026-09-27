# Debug

## Contents

- [Useful flags](#useful-flags)
- [Common issues](#common-issues)

The app includes helper scripts and environment switches that make local debugging easier.

## Useful flags

Run Python tools through the operational environment. These examples keep automation in fixture mode:

```bash
MCF_MODE=fixture HEADLESS=0 env/bin/python -m easymcf
env/bin/python scripts/db_util.py lead search '{}'
```

`HEADLESS=0` opens a visible Chromium window for a human debugging a browser step. Leave the default headless setting for ordinary runs. Set `FIXED_NOW=2026-09-15T07:00:00` inline when a spawned app process needs a deterministic clock; tests normally use the clock fixture instead. Validation utilities write per-run logs under `.dev/logs/`.

## Common issues

**Chromium is missing.** Install the browser binary into the Playwright user cache:

```bash
env/bin/python -m playwright install chromium
```

If Chromium is present but fails with a missing shared-library error, the host needs OS packages that the browser download does not include. A human can install those packages with the system package manager or run Playwright's `--with-deps` command with the required administrator access. Do not run that escalation by default.

**The port is busy.** Check whether the existing process is this repository's app. `scripts/restart.sh` refuses to stop an unrelated listener. Otherwise, use a free port for a manual developer process:

```bash
PORT=5051 MCF_MODE=fixture env/bin/python -m easymcf
```

**The database schema does not match.** Resetting is destructive. If the database can be discarded, run `env/bin/python scripts/resetdb.py --seed`, or run `./scripts/restart.sh --reset-seed` to reset and restart together. Preserve any data you need before resetting.

**The app appears to use the wrong MCF mode.** The restart helper reads `MCF_MODE` from `.env`. For an individual developer process, set `MCF_MODE=fixture` inline as shown above. Never rely on a leftover shell or `.env` value for an unattended run.

**An API, search, or apply run fails.** Read the run status and error detail on **Automation** before retrying. For apply failures, inspect every lead outcome on **Applications**; one lead's failure does not mean the whole batch failed. Use `env/bin/python scripts/db_util.py <table> search '{}'` only when direct read-only inspection of the local database is needed.

Keep debugging runs reproducible with seed data and fixture mode. Use live MCF only when a human explicitly intends to operate against the real site.
