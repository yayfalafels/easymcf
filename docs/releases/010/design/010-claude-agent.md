# Easy MCF POC Local - Claude Agent Customization

## Contents

- [Purpose](#purpose)
- [References](#references)
- [End user](#end-user)
- [Glossary](#glossary)
- [Out of scope](#out-of-scope)
- [Decisions](#decisions)
- [Status](#status)
- [Functional requirements](#functional-requirements)
  - [`CLAUDE.md`](#claudemd)
  - [Skills — generic, reusable beyond `easymcf`](#skills--generic-reusable-beyond-easymcf)
  - [Skills/commands — project domain-specific](#skillscommands--project-domain-specific)
  - [Agent / subagent instructions](#agent--subagent-instructions)
  - [`.claude/*` settings and other customizations](#claude-settings-and-other-customizations)

## Purpose

This document defines *what* Claude Code customization is needed to act as an effective pair programmer through the poc build. It does not write that content, it scopes it, so the actual files can be authored and iterated incrementally as each functional milestone starts, rather than upfront in one pass. Where a customization's exact shape depends on a decision owned by another milestone, data model, architecture, or design, this document names the dependency rather than pre-deciding it. The scope covers the following.

01. `CLAUDE.md` content.
02. skills.
03. commands.
04. subagent instructions.
05. `.claude/*` settings.

## References

- **requirements**: [010-01-requirements.md](010-01-requirements.md) — functional requirements this tooling exists to support. Domain skills below are organized around its REQ-SRCH/REQ-CRM/REQ-APPLY/REQ-PLAT/REQ-FE/REQ-DEV groupings.
- **prototype extraction**: [010-prototype.md](010-prototype.md) — implementation detail (scrape mechanics, apply state machine, CRM defects) that domain skills should encode so it isn't re-derived from `jobsearch`/`mcfpipe` source on every session.
- **mcfpipe agent scoping**: `mcfpipe/AGENTS.md` — prior-art agent scoping doc from the reference repo, covering scope, dev environment, whitelisted domains, secrets, and a current-focus pointer. Useful as a shape reference, though not carried forward as-is since it targets `mcfpipe`'s cloud/AWS environment, out of scope for `010`.
- **release roadmap**: [release-roadmap.md](../release-roadmap.md) — release scope and the current-release pointer that `CLAUDE.md` links to (REQ-AGENT-01).
- `CLAUDE.md`, `.claude/settings.local.json` (repo root) — currently empty/minimal. This document scopes what they need to contain.

## End user

Same as the **requirements**: a single local developer (Taylor) using Claude Code as pair programmer across the full `010` build — backend, frontend, jobs pipeline, and apply automation.

## Glossary

- **CLAUDE.md:** Project-level instructions file Claude Code loads automatically at session start.
- **skill:** A packaged, invokable set of instructions/reference material for a recurring kind of task, loaded on demand rather than always-on like `CLAUDE.md`.
- **command:** A user-invoked slash command (`/name`) that triggers a specific documented workflow.
- **subagent:** A separately-scoped agent (via the `Agent` tool) with its own tool access and instructions, used to delegate a bounded task.
- **`.claude/*` settings:** Project-scoped configuration (`settings.json`, `settings.local.json`) controlling permissions, hooks, and other harness behavior.

## Out of scope

- Cloud-specific agent tooling, such as AWS CLI skills, IaC/CloudFormation skills, or deployment-pipeline commands. Mirrors the **requirements**' cloud exclusions. Revisit at `020`.
- CI/CD-triggered Claude runs (e.g. GitHub Actions invoking Claude) — no CI/CD exists in `010` (REQ-PLAT-04 scope).
- Multi-developer or team-shared Claude configuration (org-level skill distribution, shared MCP servers) — single local user, per the `010` end-user scope.
- MCP server integrations beyond what ships with Claude Code by default — add only if a concrete `010` need arises; none identified yet.
- Automating Claude's own use of the browser against the *real* MyCareerFutures site — any skill/command that exercises MCF must run against seed/local data (REQ-DEV-03), never live, unless the user explicitly runs it interactively themselves.

## Decisions

- Skills and commands are project-scoped (`.claude/skills/`, `.claude/commands/`), versioned with the repo, rather than personal or user-scoped. They travel with the repo's own history and are reviewable alongside the code they describe.
- Skills/commands/subagents were originally planned to be built incrementally alongside the milestone that needs them: milestone 07 for dev-env/local-infra tooling, milestones 09 through 11 for jobs-pipeline/CRM/apply domain skills. Superseded: all generic and domain skills, six functional-role subagents, and `.claude/settings.json` were front-loaded in one pass so the tooling is available from the start of implementation, rather than waiting for each owning milestone. The two skills whose content depends on infrastructure that doesn't exist yet, `local-infra-navigation` and `deploy-and-validation-cycle`, are written as scaffolds that name what's missing and where to fill it in once milestone 07/08 lands, rather than left unwritten.
- Project-scoped `.claude/settings.json` (committed) holds the standing permission policy. `.claude/settings.local.json` (gitignored, added to `.gitignore` alongside this work) is reserved for personal/machine-specific overrides only.

## Status

Implemented as of this writing:

- `CLAUDE.md` — REQ-AGENT-01 through 05.
- Skills (`.claude/skills/`) — REQ-AGENT-10 through 19. Generic: `mycareerfutures`, `webscraping`, `playwright`. Domain:
  01. `easymcf-jobs-pipeline`.
  02. `easymcf-crm`.
  03. `easymcf-apply`.
  04. `easymcf-backend-api`.
  05. `easymcf-frontend`.
  06. `local-infra-navigation`.
  07. `deploy-and-validation-cycle`.
- Subagents (`.claude/agents/`) — REQ-AGENT-20/21 (superseded — see that section).
  01. `product-manager`.
  02. `architect`.
  03. `backend-api-developer`.
  04. `frontend-ui-developer`.
  05. `automation-engineer`.
  06. `testing-validation`.
- `.claude/settings.json` — REQ-AGENT-30 through 32 (superseded — see that section).

Not yet implemented: commands (`.claude/commands/`). No specific slash-command need has been identified yet. The directory exists but is empty.

## Functional requirements

### `CLAUDE.md`

The root `CLAUDE.md` is currently empty. It is the one file loaded unconditionally, so it should stay short and orienting, offering pointers rather than domain detail. Domain detail belongs in skills, loaded on demand.

- **REQ-AGENT-01** States the project in one paragraph (what easymcf is, current release `010` and its local-only scope) and links to the **release roadmap** and the **requirements** as the source of truth for current requirements.
- **REQ-AGENT-02** Documents the repo layout: `easymcf/`, this release's build, and the two sibling reference repos `jobsearch/`, the prototype to re-platform, and `mcfpipe/`, reference data model and API design and a cautionary example on cloud-first scope creep. The instruction is to read from them but never modify them.
- **REQ-AGENT-03** Documents local run commands once they exist: backend start, frontend serve, test run, and db seed/reset. These are added incrementally as milestone 07 (local dev/test env) lands, never stubbed out ahead of it.
- **REQ-AGENT-04** States explicit boundaries on autonomous action: no live requests against `mycareersfuture.gov.sg`, no reading or committing session/credential files such as a `cookies_mcf.json`-equivalent, `.env`, or `.secrets`, and no `git push`, consistent with the project's general confirm-before-risky-action norms.
- **REQ-AGENT-05** Points to available skills/commands and when to reach for each (see below), so Claude's own future sessions know what exists without re-discovering it via `find`/`grep`.

### Skills — generic, reusable beyond `easymcf`

These capture domain knowledge that isn't specific to this codebase's current implementation and stays useful even if the implementation is rewritten.

- **REQ-AGENT-10** `mycareerfutures` skill: site structure knowledge, covering search URL scheme, job-card and profile-page markup/selectors as of the prototype, posting lifecycle (open → closed), and the observation that markup drifts over time, which is the reason `jobsearch/recommission.py` exists. Page-structure assumptions are named as fragile rather than hardcoded silently.
- **REQ-AGENT-11** `webscraping` skill: general patterns this project must apply — incremental/per-page persistence instead of end-of-run-only writes (the defect REQ-SRCH-04 fixes), stable dedup-id construction, and separating discovery (list page) from detail (profile page) fetch passes.
- **REQ-AGENT-12** `playwright`/browser-automation skill: headless browser setup, explicit-wait patterns as the replacement for `jobsearch`'s fixed `sleep(15)`/`sleep(4)` calls, and resilient element selection, preferring stable `data-testid`/`data-cy` attributes, as the prototype already does, over positional selectors.

### Skills/commands — project domain-specific

Each maps to a functional area of the **requirements** and should be authored when that area's milestone starts, never earlier. Early authorship would guess at decisions owned by the data model/architecture/design milestones.

- **REQ-AGENT-13** `easymcf-jobs-pipeline` — search-by-keywords and match scoring (REQ-SRCH-\*): track/search-profile config, the scrape → dedup → detail-fetch → score pipeline, and the scoring-method-is-swappable constraint (REQ-SRCH-09).
- **REQ-AGENT-14** `easymcf-crm` — lead/pipeline tracking (REQ-CRM-\*): status state machine, the pipeline-status-vs-apply-status distinction, and the `updateOpenExpired()` unconditional-overwrite defect (REQ-CRM-05) as a named regression to guard against.
- **REQ-AGENT-15** `easymcf-apply` — automated apply (REQ-APPLY-\*): the per-lead state machine and full outcome vocabulary from the **prototype extraction**, the questionnaire-detection non-goal, and the local/seed-data-only constraint for any test run of this skill.
- **REQ-AGENT-16** `easymcf-backend-api` — backend/data platform (REQ-PLAT-\*): the generic schema-validated CRUD endpoint pattern (`GET/PUT/DELETE /{table}/{id}`, batch/search/delete), SQLite as the only store, and run-logging expectations (REQ-PLAT-03).
- **REQ-AGENT-17** `easymcf-frontend` — AngularJS UI (REQ-FE-\*): screen-to-requirement mapping (track config, posting/results browsing, pipeline management, apply-queue review) and the constraint that this release commits to AngularJS rather than a framework migration.
- **REQ-AGENT-18** local-infrastructure-navigation skill/command: how to start backend, frontend, and SQLite locally. Where seed data lives and how to reset it (REQ-DEV-01, REQ-DEV-02). Authored alongside milestone 07/08, never before those exist to document.
- **REQ-AGENT-19** deploy-and-validation-cycle command: the local equivalent of a deploy/verify loop for this release — run backend+frontend, load seed data, exercise the golden path per functional area, matching this project's general practice of verifying UI/behavior changes before reporting completion. No cloud deploy step exists in `010` (REQ-PLAT-04).

### Agent / subagent instructions

- ~~**REQ-AGENT-20** Default general-purpose/Explore subagents are sufficient for `010`; no custom subagent is required unless a specific recurring bounded task emerges...~~ **Superseded.** Six functional-role subagents (`.claude/agents/`) were authored to match the development-cycle roles the user identified: `product-manager` (requirements/milestones/scope/sequencing/QA — REQ-AGENT-01-class ownership), `architect` (data model/architecture/design milestones 04–06), `backend-api-developer` (REQ-PLAT-\*), `frontend-ui-developer` (REQ-FE-\*), `automation-engineer` (REQ-SRCH-\*/REQ-APPLY-\* browser automation), `testing-validation` (test strategy/cases, milestones 02–03, and requirement-vs-implementation validation). Each preloads its relevant skill(s) via the subagent `skills` field and inherits the live-site/secrets boundaries below.
- **REQ-AGENT-21** Any subagent or skill that touches the live MCF site or a real session cookie inherits the same live-site and secrets restrictions as REQ-AGENT-04. Restrictions are stated once in `CLAUDE.md` and referenced, rather than duplicated in full, from each domain skill and the `automation-engineer` subagent.

### `.claude/*` settings and other customizations

- ~~**REQ-AGENT-30** `.claude/settings.local.json` allowlists the routine local-dev commands...~~ **Superseded.** Per the user's explicit request for maximal delegation, `.claude/settings.json` (project-scoped, committed) grants blanket `Bash`, `Edit`, and `Write` approval rather than an incrementally-grown allowlist, with an `ask` list carving out destructive git operations (`push`, `reset --hard`, `clean`, `branch -D`) and secrets access (`.env`, `.secrets`, `cookies_mcf.json`-pattern files) via both direct tool rules and best-effort `Bash(cat ...)` pattern matches. **Caveat the user should be aware of:** a blanket `Bash` allow cannot be fully closed against secrets access — any shell command can read a file by means other than `cat` (e.g. a one-line Python/`sed` command), so the `ask` patterns reduce accidental exposure but are not a hard boundary. The real protection is that `.env`/`.secrets` are git-ignored and should never hold live credentials while this permissive mode is active. Tighten `.claude/settings.json`, for example by setting `defaultMode: default` or dropping the blanket `Bash`/`Write` allow, before handling real MCF session material if that becomes a concern.
- **REQ-AGENT-31** Session/credential material, such as an MCF cookie export or any future service credentials, is never covered by an automatic Read/allow rule. `.env`, `.secrets`, and any cookie-export file follow the same exclusion already established in `.gitignore`, which now also covers `.claude/settings.local.json` itself, since it holds personal/machine-specific permission overrides and should not be committed.
- **REQ-AGENT-32** No cloud-provider permissions (AWS CLI, credentials) are added to settings for `010`, consistent with REQ-PLAT-04's no-cloud-dependency requirement.

