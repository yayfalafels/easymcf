# Test

## Contents

- [Validate the environment](#validate-the-environment)
- [Run pytest](#run-pytest)

The test suite covers backend, frontend, and full-stack behavior using isolated databases and fixture data. Tests belong in the operational environment because frontend and end-to-end tests start the real app process. Run commands from the repository root through `env/bin/python`; do not rely on whichever virtual environment happens to be activated in the terminal.

## Validate the environment

```bash
env/bin/python scripts/envcheck.py
```

Run the preflight with the app stopped and its configured port free. It checks Python version and venv, Chromium, vendored frontend assets, database schema, port availability, MCF mode, and Google secret-file permissions when Google OAuth is configured. Resolve every `[FAIL]` message before treating later test failures as code defects.

## Run pytest

```bash
env/bin/python -m pytest
```

The `live` marker is deselected by default because it targets the real MyCareersFuture site. Keep it deselected for ordinary development and automated validation.

Run a narrower tier when diagnosing a failure:

```bash
env/bin/python -m pytest -m backend
env/bin/python -m pytest -m frontend
env/bin/python -m pytest -m e2e
```

Backend tests use the Flask test client. Frontend tests drive the served AngularJS app with API calls mocked. End-to-end tests exercise the real local app with external MCF traffic replaced by fixtures. A live test requires an explicit human decision and must never be launched as a routine check.

If collection fails with an import error, confirm that the command uses `env/bin/python` and re-sync dependencies from `python-envs/ops-env/pyproject.toml`. If a browser test cannot launch Chromium, install the browser with `env/bin/python -m playwright install chromium`; missing operating-system libraries require a human-operated install step. For a schema mismatch, reset only a database whose contents can be discarded.
