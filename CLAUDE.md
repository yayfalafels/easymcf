# Easy MCF

Easy MCF streamlines the job search and application process for job seekers in Singapore using [MyCareersFuture](https://www.mycareersfuture.gov.sg/). Current release: `010` (POC local) — a locally-run Python (Flask) backend + SQLite database + AngularJS frontend, re-platforming the `jobsearch` prototype's search/CRM/apply-automation workflow without repeating `mcfpipe`'s premature cloud-infrastructure investment. Source of truth for current scope: [docs/releases/release-roadmap.md](docs/releases/release-roadmap.md) and [docs/releases/010/010-01-requirements.md](docs/releases/010/010-01-requirements.md) — read the relevant requirements before implementing anything, don't infer scope from code alone.

## Repo layout

- `easymcf/` (this repo) — the `010` build.
- `docs/releases/` — roadmap, per-release requirements, milestones, and design docs.
- `../jobsearch/` (sibling repo) — the prototype being re-platformed. Read-only reference (`agent.py`, `mcf_profile.py`, `match.py`/`text.py`, `apply.py`, `gsheet/applicationtrackingapp.gs`). Do not modify.
- `../mcfpipe/` (sibling repo) — reference data model/API design and a cautionary example of cloud-first scope creep this release avoids (`docs/data_model.md`, `docs/database_api.md`, `docs/architecture.md`). Do not modify.

[docs/releases/010/010-prototype.md](docs/releases/010/010-prototype.md) already extracts the implementation-level detail from both sibling repos that most work needs — check there before reading `jobsearch/`/`mcfpipe/` source directly.

## Claude Code tooling for this project

Scoped in [docs/releases/010/010-claude-agent.md](docs/releases/010/010-claude-agent.md).

**Skills** (`.claude/skills/`) — load on demand, don't need to be manually invoked:
- Generic: `mycareerfutures` (site markup), `webscraping` (persistence/dedup patterns), `selenium` (wait/locator patterns).
- Domain: `easymcf-jobs-pipeline`, `easymcf-crm`, `easymcf-apply`, `easymcf-backend-api`, `easymcf-frontend` (one per functional area of the requirements), `local-infra-navigation`, `deploy-and-validation-cycle`.

**Subagents** (`.claude/agents/`) — delegate to these for role-scoped work: `product-manager` (requirements/milestones/scope/QA), `architect` (data model/architecture/design), `backend-api-developer` (Flask/SQLite), `frontend-ui-developer` (AngularJS), `automation-engineer` (scraping/apply browser automation), `testing-validation` (test strategy, test runs, requirement validation).

## Boundaries

- Never issue requests against the live `mycareersfuture.gov.sg` site, or read/commit a real session cookie export, `.env`, or `.secrets`, in an automated/unattended context — only when the user explicitly asks to run something live in that turn. Development and tests run against seed/fixture data (REQ-DEV-03).
- Don't `git push` or take other high-blast-radius git actions without the user's explicit confirmation in that turn, even though `.claude/settings.json` pre-approves routine local Bash/file-write operations.
- Cloud deployment, multi-user support, and CI/CD are out of scope for `010` — don't introduce AWS/cloud SDKs, credentials, or infrastructure as part of this release's work.
- Only two Python virtual environments exist for this project — `~/.dev/dev-env` (one-time/throwaway dev tasks) and `~/env` (anything in the app's operational lifecycle: running the app, DB init/seed, CRUD, maintenance/data-patching, scraping and apply automation). **Never create an ad hoc/disposable venv for any operation, ever** — always run Python work through one of these two. See [local-infra-navigation](.claude/skills/local-infra-navigation/SKILL.md) for which env a given task belongs in and how to sync dependencies.

## Verifying changes

Before reporting a nontrivial backend, frontend, or automation change as done, exercise it end to end against local/seed data (see `deploy-and-validation-cycle` skill) rather than relying on type-checks or unit tests alone.
