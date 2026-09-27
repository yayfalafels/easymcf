# Install

## Contents

- [Create the required virtual environments](#1-create-the-required-virtual-environments)
- [Install the app runtime dependencies](#2-install-the-app-runtime-dependencies)
- [Install the docs and helper tooling](#3-install-the-docs-and-helper-tooling)
- [Install the Chromium browser used by Playwright](#4-install-the-chromium-browser-used-by-playwright)
- [Make sure the vendored AngularJS frontend assets are present](#5-make-sure-the-vendored-angularjs-frontend-assets-are-present)
- [Configure the local environment](#6-configure-the-local-environment)
- [Seed the database](#7-seed-the-database)
- [Start the app](#8-start-the-app)
- [Run the validation checks](#9-run-the-validation-checks)
- [If setup fails](#if-setup-fails)

This repo does not use `requirements.txt` files. The supported setup is the project’s two-venv layout, with one operational env for the app and one dev env for throwaway tooling. The authoritative manifests are:

- [python-envs/ops-env/pyproject.toml](https://github.com/yayfalafels/easymcf/blob/main/python-envs/ops-env/pyproject.toml)
- [python-envs/dev-env/pyproject.toml](https://github.com/yayfalafels/easymcf/blob/main/python-envs/dev-env/pyproject.toml)

You need Python 3.11 or later with `venv`, Git, and a supported Linux environment (including WSL2). There is no Node/npm frontend setup.

## 1. Create the required virtual environments

```bash
git clone https://github.com/yayfalafels/easymcf.git
cd easymcf
python3 -m venv env
python3 -m venv .dev/dev-env
```

The operational env is for the Flask app, database work, scraping, and apply automation. The `.dev/dev-env` env is for docs tooling, debugging probes, and one-off developer tasks.

The dev env is optional for running the app; create and sync it when you need the documentation or developer tools. The test suite belongs in the operational env because its backend and browser tests exercise the app runtime.

## 2. Install the app runtime dependencies

Sync the operational environment from the `ops-env` manifest:

```bash
env/bin/python -c "
import tomllib
path = 'python-envs/ops-env/pyproject.toml'
deps = tomllib.load(open(path, 'rb'))['project']['dependencies']
print('\n'.join(deps))
" | env/bin/pip install -r /dev/stdin
```

This installs the Python packages the app actually uses at runtime, including Flask, Playwright, requests, numpy/pandas, authlib, and the database/HTML tooling.

## 3. Install the docs and helper tooling

Sync the dev environment from the `dev-env` manifest:

```bash
.dev/dev-env/bin/python -c "
import tomllib
path = 'python-envs/dev-env/pyproject.toml'
deps = tomllib.load(open(path, 'rb'))['project']['dependencies']
print('\n'.join(deps))
" | .dev/dev-env/bin/pip install -r /dev/stdin
```

This installs the docs tooling (`mkdocs`, `mkdocs-material`, `pymdown-extensions`) and the support packages used for local investigation and mock-data work.

## 4. Install the Chromium browser used by Playwright

The app relies on Playwright’s bundled Chromium, not Selenium. Install the browser once per machine:

```bash
env/bin/python -m playwright install chromium
```

Do not use `--with-deps` by default. If Chromium fails to launch with a missing shared-library error, a human can install the required OS libraries with `sudo` or the system package manager; this is separate from the browser download and may require administrator access.

## 5. Make sure the vendored AngularJS frontend assets are present

This project does not use a Node/npm build step. The AngularJS frontend is vendored into the repo and served directly by Flask.

Check that these files exist:

```bash
ls frontend/vendor/angular.min.js frontend/vendor/angular-route.min.js
```

If they are missing, fetch the pinned AngularJS 1.8.3 assets once and commit them:

```bash
mkdir -p frontend/vendor
curl -sfL https://ajax.googleapis.com/ajax/libs/angularjs/1.8.3/angular.min.js -o frontend/vendor/angular.min.js
curl -sfL https://ajax.googleapis.com/ajax/libs/angularjs/1.8.3/angular-route.min.js -o frontend/vendor/angular-route.min.js
```

Do not add a separate frontend build toolchain or `npm install` step; that is not how this project works.

## 6. Configure the local environment

No `.env` file is required. Defaults are sufficient for local development. If you want machine-local overrides, copy the tracked example and edit only the values you need:

```bash
cp .env.example .env
```

The app loads `.env` for manual runs. Keep credentials and secret material in `.secrets/`, not in `.env`. The test suite does not load `.env`; it sets test configuration explicitly.

## 7. Seed the database

For a standalone reset, reset the schema and load the tracked seed data:

```bash
env/bin/python scripts/resetdb.py --seed
```

This is destructive: it deletes and recreates the configured SQLite database before loading the seed data. It creates the default dev database at `data/easymcf.db`; do not run it against a database whose contents you need to keep.

## 8. Start the app

For a manual run that does not rely on `.env`, start explicitly in fixture mode:

```bash
MCF_MODE=fixture env/bin/python -m easymcf
```

Setting fixture mode explicitly prevents a `MCF_MODE=live` value left in `.env` from making an unattended local run contact the real site. Then open http://127.0.0.1:5000 in a browser.

For repeatable human-operated restarts, use the helper script. It requires `.env` to set `MCF_MODE` to either `fixture` or `live`, preserves the database by default, and refuses to stop a listener it cannot identify as this repo's app:

```bash
./scripts/restart.sh                 # restart without changing the database
./scripts/restart.sh --reset-seed    # reset and seed the database, then start
```

`--reset-seed` is destructive: it deletes and recreates the configured database before starting. Use it only when the existing local data can be discarded. To use this helper for ordinary local development, set `MCF_MODE=fixture` in `.env` first. This combined command replaces the separate reset and startup steps when you want a clean seeded app.

## 9. Run the validation checks

Before trusting a local run, confirm the environment is healthy:

```bash
env/bin/python scripts/envcheck.py
```

Run this with the app stopped and the configured port free. It checks Python/venv selection, Chromium, vendored frontend assets, database schema, port availability, and that the selected mode is not `live`.

Run the test suite through the operational environment:

```bash
env/bin/python -m pytest
```

Pytest deselects live-site tests by default. Live runs are human-governed and should only be used when you are explicitly operating the application against the real MyCareersFuture site.

## If setup fails

- **The venv command is missing or reports an unsupported Python.** Install Python 3.11 or later with `venv`, then create only the repo's `env/` and `.dev/dev-env/` environments.
- **Dependency installation fails.** Confirm you are in the repository root, that the relevant venv exists, and that the manifest sync command completed. App and test packages belong to `env`; documentation packages belong to `.dev/dev-env`.
- **Playwright reports that Chromium is missing.** Run `env/bin/python -m playwright install chromium`. If it is present but cannot launch because a shared library is missing, ask a human with system package access to install the OS dependency.
- **The frontend opens blank or envcheck reports missing AngularJS files.** Confirm `frontend/vendor/angular.min.js` and `angular-route.min.js` exist. Follow the vendor recovery commands in step 5 only if the committed assets are actually missing.
- **Envcheck reports a busy port or live mode.** Stop the existing app before preflight, or choose a free port. Keep developer commands in fixture mode; do not use the live settings from the job-seeker workflow for tests.
- **The database schema is stale.** `scripts/resetdb.py --seed` deletes and recreates the database. Back up anything you need first, or use a separate scratch `DB_PATH`.
- **The docs build fails.** Follow [Fix a failed build](docs-site.md#fix-a-failed-build) and rerun `./scripts/build_docs.sh`.
