# Easy MCF Version 0.1.0 - Milestones

## Feature milestones

The `seq` column present in earlier drafts of this table is dropped (per [010-issues.md](010-issues.md) ISS-01): it asserted a build order that contradicted the documents' own stated dependencies (architecture was sequenced before data model despite architecture's References section naming data model as an input it reads from). Each document's own Purpose/References section already states what it derives from and what derives from it — that is the authoritative ordering; `id` here is a stable identifier, not a sequence.

| id | release | status   |   feature                                |
| -- | ------- | -------  | ---------------------------------------- |
| 01 | 010     | closed   | requirements                             |
| 02 | 010     | closed   | test strategy                            |
| 03 | 010     | open     | test cases                               |
| 04 | 010     | closed   | data model                               |
| 05 | 010     | closed   | architecture                             |
| 06 | 010     | closed   | design                                   |
| 07 | 010     | pending  | local dev and test env                   |
| 08 | 010     | pending  | setup database seed data                 |
| 09 | 010     | pending  | job leads tracking                       |
| 10 | 010     | pending  | search by keywords                       |
| 11 | 010     | pending  | apply automation                         |

Architecture (05), data model (04), and test strategy (02) are each independently sequenced and consumed by later milestones (test strategy builds on `ARCH-TEST-01..08`; architecture's storage section is concrete about data model's tables), so each gets its own top-level row. Test cases (03) has no document yet (`010-test-cases.md` does not exist) — it stays `open` as the concrete case set milestone 02 (test strategy) scopes but has not yet been instantiated into.

_06 (closed) design_

**scope**

The descriptive design layer between requirements and architecture/implementation: how the system behaves (workflows), what the user sees (user interface), what seed/test content is available and where it comes from (test data), the implementation-level detail carried over from `jobsearch`/`mcfpipe` for reuse (prototype), the Claude Code tooling scoped to support the build (claude agent), the elaborated backend API surface (api design), and the AngularJS app structure that implements the user-interface spec against that surface (frontend app). None of the documents below individually gates the others the way requirements → data model → architecture do (api design and frontend app are the two exceptions — frontend app depends on api design, both listed in dependency order), which is why they're grouped here as one milestone's subtasks rather than given separate top-level rows.

**completion criteria**

Every document below exists, is complete per its own Purpose section (no open `TBD` against the requirements it derives from), and is consistent with the documents that derive from it.

**tasks**

| id    | seq | status  |   subtask                                                                                                  |
| ----- | --- | ------  | ----------------------------------------------------------------------------------------------------------- |
| 06.01 | 01  | closed  | workflows ([010-workflows.md](010-workflows.md)) — business logic and process flows derived from requirements, input to data model and user interface |
| 06.02 | 02  | closed  | user interface ([010-user-interface.md](010-user-interface.md)) — page inventory and UX behavior, derived from workflows and mapped to data model entities |
| 06.03 | 03  | closed  | test data ([010-test-data.md](010-test-data.md)) — seed/fixture data sourcing and transformation from the `jobsearch` prototype, input to milestones 04 and 08 |
| 06.04 | 04  | closed  | prototype reference ([010-prototype.md](010-prototype.md)) — `jobsearch`/`mcfpipe` implementation detail extracted for reuse across requirements/data-model/architecture/design |
| 06.05 | 05  | closed  | claude agent ([010-claude-agent.md](010-claude-agent.md)) — Claude Code tooling scope (`CLAUDE.md`, skills, subagents) supporting the build |
| 06.06 | 06  | closed  | api design ([010-api.md](010-api.md)) — elaborates `ARCH-RUN-10`/REQ-PLAT-01 into the per-entity generic/hook/named classification and named-endpoint catalog; resolves ISS-02 |
| 06.07 | 07  | closed  | frontend app ([010-frontend-app.md](010-frontend-app.md)) — AngularJS module/routing/API-client/async-run design elaborating 010-user-interface.md and 010-api.md into an implementable app structure |
