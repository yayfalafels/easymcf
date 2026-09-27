# Design orientation

## Contents

- [Architecture overview](#architecture-overview)
- [Find the code that owns a change](#find-the-code-that-owns-a-change)
- [Current design docs](#current-design-docs)

Easy MCF is a local Flask application backed by SQLite. Flask serves the AngularJS frontend and API from one origin. Search and apply automation use Playwright behind the MCF browser interface. The repository has no separate frontend build or cloud runtime.

## Architecture overview

1. `easymcf/api/`, `auth/`, `services/`, `db/`, and `automation/` contain the Flask routes, account handling, domain logic, SQLite access, and browser automation.
2. `frontend/app/` contains the AngularJS screens and services. `frontend/vendor/` contains the committed AngularJS runtime assets.
3. `seed/` contains generated SQL seed records. Change the generator in `scripts/gen_test_data.py`, not the generated SQL directly.
4. `scripts/` contains tracked operational tools for database setup, validation, test-data generation, and documentation builds.
5. `tests/backend/`, `tests/frontend/`, and `tests/e2e/` cover isolated backend behavior, the browser UI, and the full local stack. Live-site tests are human-gated.
6. `docs/releases/010/` contains the current source requirements, design, and feature trackers. The published `docs/design/` pages are generated copies.

The dev environment is `env/` for app, database, automation, and tests. `.dev/dev-env/` is for documentation and one-off developer tools. See [Install](index.md) for the setup procedure.

## Find the code that owns a change

1. Start with the relevant requirement or feature tracker under `docs/releases/010/`. Use `docs/releases/release-roadmap.md` in the repository to locate the feature and its status.
2. Check the design document for the owning contract before editing. The API, schema, workflows, UI inventory, and frontend structure are documented separately below.
3. Follow the request from the AngularJS screen through its service and API route to the domain service and database. Keep business rules in their owning backend service rather than duplicating them in a controller.
4. Add or update the narrowest corresponding test tier. Run the operational checks in [Test](test.md), then validate the full workflow when the change crosses components.
5. If you change a release design document, regenerate the published design copy with `.dev/dev-env/bin/python scripts/sync_design_docs.py` before building the site.

## Current design docs

The published design section is generated from the current release's docs in `docs/releases/<release>/design/`. Read the source document under `docs/releases/010/design/` when changing a decision; use these published pages for quick browsing:

- [Requirements](../design/requirements.md) defines what the release must do.
- [Architecture](../design/architecture.md) and [data model](../design/data-model.md) define runtime boundaries and storage.
- [API](../design/api.md), [workflows](../design/workflows.md), and [user interface](../design/user-interface.md) define cross-layer behavior and screens.
- [Frontend app](../design/frontend-app.md) and [development environment](../design/development-env.md) provide implementation and local-run detail.
