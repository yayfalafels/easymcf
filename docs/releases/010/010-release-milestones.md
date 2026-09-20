# Easy MCF Version 0.1.0 - Milestones

## Feature milestones

The `seq` column present in earlier drafts of this table is dropped (per [010-issues.md](010-issues.md) ISS-01): it asserted a build order that contradicted the documents' own stated dependencies (architecture was sequenced before data model despite architecture's References section naming data model as an input it reads from). Each document's own Purpose/References section already states what it derives from and what derives from it — that is the authoritative ordering; `id` here is a stable identifier, not a sequence.

| id | release | seq | status   |   feature                                |
| -- | ------- | --- | -------  | ---------------------------------------- |
| 01 | 010     | 01  | closed   | requirements                             |
| 02 | 010     | 02  | closed   | test strategy                            |
| 03 | 010     | 03  | closed   | test cases                               |
| 04 | 010     | 04  | closed   | data model                               |
| 05 | 010     | 05  | closed   | architecture                             |
| 06 | 010     | 06  | closed   | design                                   |
| 07 | 010     | 07  | closed   | local dev and test env                   |
| 08 | 010     | 08  | closed   | setup database seed data                 |
| 12 | 010     | 09  | closed   | validation utilities                     |
| 09 | 010     | 10  | open     | job leads tracking                       |
| 13 | 010     | 11  | open     | oauth login                              |
| 10 | 010     | 12  | pending  | search by keywords                       |
| 11 | 010     | 13  | pending  | apply automation                         |
| 14 | 010     | 14  | pending  | performance dashboard reports            |

Architecture (05), data model (04), and test strategy (02) are each independently sequenced and consumed by later milestones (test strategy builds on `ARCH-TEST-01..08`; architecture's storage section is concrete about data model's tables), so each gets its own top-level row. Test cases (03) is [010-test-cases.md](010-test-cases.md) — the concrete case set milestone 02 (test strategy) scopes, organized by the same silo breakdown, with `STRAT-CASE-01` traceability back to every functional `REQ-*`.

_06 (closed) design_

**scope**

The descriptive design layer between requirements and architecture/implementation: how the system behaves (workflows), what the user sees (user interface), what seed/test content is available and where it comes from (test data), the implementation-level detail carried over from `jobsearch`/`mcfpipe` for reuse (prototype), the Claude Code tooling scoped to support the build (claude agent), the elaborated backend API surface (api design), and the AngularJS app structure that implements the user-interface spec against that surface (frontend app). None of the documents below individually gates the others the way requirements → data model → architecture do (api design and frontend app are the two exceptions — frontend app depends on api design, both listed in dependency order), which is why they're grouped here as one milestone's subtasks rather than given separate top-level rows.

**completion criteria**

Every document below exists, is complete per its own Purpose section (no open `TBD` against the requirements it derives from), and is consistent with the documents that derive from it.

**tasks**

| id    | seq | status  | task                   |
| ----- | --- | ------  | ---------------------- |
| 06.01 | 01  | closed  | workflows              |
| 06.02 | 02  | closed  | user interface         |
| 06.03 | 03  | closed  | test data              |
| 06.04 | 04  | closed  | prototype reference    |
| 06.05 | 05  | closed  | claude agent           |
| 06.06 | 06  | closed  | api design             |
| 06.07 | 07  | closed  | frontend app           |
| 06.08 | 08  | closed  | development env        |

- **06.01 workflows** ([010-workflows.md](010-workflows.md)) — business logic and process flows derived from requirements, input to data model and user interface
- **06.02 user interface** ([010-user-interface.md](010-user-interface.md)) — page inventory and UX behavior, derived from workflows and mapped to data model entities
- **06.03 test data** ([010-test-data.md](010-test-data.md)) — seed/fixture data sourcing and transformation from the `jobsearch` prototype, input to milestones 04 and 08
- **06.04 prototype reference** ([010-prototype.md](010-prototype.md)) — `jobsearch`/`mcfpipe` implementation detail extracted for reuse across requirements/data-model/architecture/design
- **06.05 claude agent** ([010-claude-agent.md](010-claude-agent.md)) — Claude Code tooling scope (`CLAUDE.md`, skills, subagents) supporting the build
- **06.06 api design** ([010-api.md](010-api.md)) — elaborates `ARCH-RUN-10`/REQ-PLAT-01 into the per-entity generic/hook/named classification and named-endpoint catalog; resolves ISS-02
- **06.07 frontend app** ([010-frontend-app.md](010-frontend-app.md)) — AngularJS module/routing/API-client/async-run design elaborating 010-user-interface.md and 010-api.md into an implementable app structure
- **06.08 development env** ([010-development-env.md](010-development-env.md)) — elaborates `ARCH-RUN`/`STO`/`BOT`/`TEST` and `STRAT-SILO`/`LOOP` into the install/config/script/agent-loop runbook milestone 07 is implemented against