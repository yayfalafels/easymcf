# Run the app

## Contents

- [Start and stop](#start-and-stop)
- [Health checks](#health-checks)
- [Live mode](#live-mode)

Use the app from the repository root and run it through the operational environment. Developer and validation runs use fixture mode. Job seekers use live mode for current MCF data; see [Getting started](../user-guide/index.md).

## Start and stop

```bash
MCF_MODE=fixture env/bin/python -m easymcf
```

Open http://127.0.0.1:5000 after the server starts. Stop it with `Ctrl+C` in the terminal where it is running. This explicit fixture setting overrides any live value in `.env` for this invocation.

For a repeatable human-operated restart, use the helper script. It reads `MCF_MODE` from `.env`, preserves the database, and refuses to stop a listener unless it verifies that the process belongs to this repository:

```bash
./scripts/restart.sh
```

Set `MCF_MODE=fixture` in `.env` before using the helper for developer work. To discard and recreate the configured database before restarting, use `./scripts/restart.sh --reset-seed`. That option is destructive.

## Health checks

Check the API readiness endpoint and the user interface independently:

```bash
curl -sf http://127.0.0.1:5000/api/v1/health
```

Then open http://127.0.0.1:5000 in a browser and confirm the expected page and seeded data appear. The endpoint is `/api/v1/health`; `/health` is not the app's readiness route.

If the curl fails, inspect the server terminal for startup errors and confirm the configured port. If the UI is blank while the health endpoint succeeds, check that both vendored AngularJS files exist under `frontend/vendor/` and review the browser console.

## Live mode

Live mode is for a human-operated user workflow against the real MCF site. Configure these values in `.env` before starting with `scripts/restart.sh`:

```bash
MCF_MODE=live
APPLY_LIVE_SUBMIT=1
```

This setting allows apply automation to submit real applications. Enable it only when a human is actively reviewing and operating the app. For a single live search without applying, `MCF_MODE=live` is sufficient; do not enable live apply submission unless real applications are intended. Return to `MCF_MODE=fixture` before developer or unattended validation runs.
