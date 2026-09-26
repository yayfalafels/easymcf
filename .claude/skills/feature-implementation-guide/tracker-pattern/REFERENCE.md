# the feature-tracker document pattern

A single markdown file per feature that is simultaneously the spec, the design doc, the test plan, and the progress tracker. It is written mostly *before* code exists and then filled in section by section, in order, as work actually happens - so at any point in time the file's fill-state IS the project's state, not a stale plan next to the real work.

This is the generic pattern behind `docs/features/*.md` and `docs/assessments/*.md` in this repo. This pattern itself is portable to a feature in any project - an API endpoint, a fullstack feature, a migration, an infra change; a project without this skill defines its own equivalent for the concrete mechanics, matched to its own stack. `../implementation/REFERENCE.md` and `../validation/REFERENCE.md` are *this repo's* concrete mechanics for two of the seven stages below, not part of the portable shape.

**boilerplate:** `templates/feature-tracker.md` in this folder is a copy-paste starting file matching this repo's actual conventions (Contents block, References section, Guideline footer) - copy it to `docs/features/<NN>-<name>.md` or `docs/assessments/<NN>-<name>.md` when starting a new tracker.

## the seven sections, in fill order

Sections are written top to bottom in the file, but **filled in left to right in time** - a later section stays a stub until the stage before it is settled. This ordering is the whole point: it structurally prevents "write the code before the test cases exist" or "pick edit locations before the design is agreed."

| id | section                | question it answers                                          |
| -- | ----------------------- | -------------------------------------------------------------- |
| 01 | Tasks                   | what are the stages, and which are done?                      |
| 02 | Scope                   | what are we building, what are we explicitly not, how do we know it's done? |
| 03 | Design (high level)     | what are the key decisions, and why?                          |
| 04 | Test strategy + cases   | how will each claim be checked, independently of the code that makes the claim? |
| 05 | Design (detailed)       | exactly which files change, and in what order?                |
| 06 | Implement               | the work itself, one numbered step per design/edit-location item |
| 07 | Validate                | what actually broke, how it was found, what's left open       |

A short **Guideline** footer at the end names any other conventions this doc and its implementation must follow (formatting rules, coding conventions, deploy conventions) - keeps the tracker self-governing across many docs written over a long time.

### 01 Tasks

One row per stage/subtask, `id | seq | status | milestone`, status one of `pending / open / closed`. This table - plus a one-line status in the file's own header, e.g. `## 12 (open) add CSV export to reporting dashboard` - is the single glanceable answer to "is this done." Everything below it is the evidence trail backing that claim up.

### 02 Scope

Condensed from whatever prompted the feature (a ticket, a PRD, a user's verbal ask) into:

- a short plain-language statement of what's being built
- explicit **out of scope** / deferred items - as important as the in-scope list, because it's the cheapest point to redirect before anything is built
- a **closure** condition - the acceptance criteria, written before the design exists, not backfilled after

### 03 Design (high level)

One subsection per concern area - for an API: data model, endpoint contracts, auth/authz, error handling, idempotency, rate limits; for a fullstack feature: data model, API surface, client state, UI states (loading/empty/error). Each subsection states a decision and its rationale, not just the outcome.

Two callouts to use deliberately, because they're what a human reviewer should scan for instead of reading every line:

- **implementation decision** - flag any place the source ask was ambiguous and you resolved it by judgment rather than by an explicit instruction. State the decision and the alternative you didn't take.
- **deviation** - flag any place this design departs from an existing higher-level design doc, architecture doc, or established convention, and why.

### 04 Test strategy + test cases

Written **before** edit locations or implementation - test-first at the doc level, not just the code level.

_test strategy_ - name the independent verification layers, so no check grades its own homework. A layer is "independent" if it does not read anything the code under test also produced. Typical layers, pick what applies:

| id | layer                 | what it checks against                                    |
| -- | ---------------------- | ------------------------------------------------------------ |
| 01 | self-report            | the code's own pass/fail output (logs, exit codes) [01]   |
| 02 | black-box / client     | behavior from outside the system - HTTP response, UI      |
| 03 | direct inspection      | the underlying store queried directly, bypassing the app  |
| 04 | oracle / ground truth  | an expected value derived independently of the code [02]  |

01. weakest layer alone - a `[PASS]` log line only proves the code ran, not that it computed the right thing.
02. strongest layer - the value must be computed by a separate route than the code under test, or it isn't independent.

_test cases_ - a table, `id | scope-item | layer | check`, each row traceable by id back to a Scope/Design item, plus a **tools** code block of copy-pasteable commands so any layer can be re-run by hand, independent of whatever the implementation eventually automates.

### 05 Design (detailed): edit locations

A table, `id | path | change`, naming every file or module that will be touched, decided before any of them are opened. Footnote anything generated (never hand-edit) vs hand-authored, and state explicitly what's *not* expected to change (config, schema, public contracts) - a required change to one of those later is a defect raised where it's actually owned, not silently patched here.

This table is what lets work resume correctly in a new session or by a different person - re-read the table instead of re-deriving "which files does this touch" from scratch.

### 06 Implement

Numbered steps mirroring the edit-locations table, each opening with its own `edit locations: <ids>` line naming the subset it touches. A step not yet started stays a one-line stub (e.g. `_expand when this step starts_`) rather than being pre-written in full - so the file's fill-state tracks real progress instead of a plan made once and abandoned.

Carve out explicitly any step that structurally requires a human - a GUI-only tool, third-party auth, an account only a person holds. Don't leave these implicit; name them as a distinct line so they aren't silently skipped or silently assumed automatable.

Load `../implementation/REFERENCE.md` for this repo's concrete mechanics at this stage - re-runnable scripts, `.env` parameterization, error handling, logging.

### 07 Validate

- an **Issues** table, one row per first-out failure actually hit, each expanded into its own diagnostic section
- a first-out failure is logged as data, kept structurally separate from the diagnostic steps taken about it, and any root cause stays framed as a **hypothesis** until evidence confirms it
- a **user actions** line listing anything a human had to physically do (click through a Desktop app, approve a deploy, authenticate) - the explicit human-in-the-loop seam, kept separate from what the agent did on its own

Load `../validation/REFERENCE.md` for this repo's concrete issue-table columns, diagnostic-step fields, and log-file conventions at this stage (or a project's own equivalent, matched to its own stack) - not restated here, so there's one place that convention can change.

## id cross-reference scheme

Every row across every table shares one id shape: `<feature-id>.<category>.<seq>`. This is what lets "does test case 12.TC.04 pass" resolve unambiguously back to a design decision and an edit location without re-reading prose.

| code | meaning                          |
| ---- | ----------------------------------- |
| TK   | task / milestone row                |
| CK   | scope requirement / check item      |
| TC   | test case                           |
| EL   | edit location                       |
| IS   | issue, with `.<subtask>` for its diagnostic steps |

Add more categories only when a feature actually needs them (this repo's assessment trackers add `PR` for ordered prerequisites and `DM` for a task-to-deliverable map) - don't pre-add categories a feature won't use.

## who does what, per stage

| id | stage             | AI drafts / executes                      | human checkpoint                   |
| -- | ------------------ | -------------------------------------------- | --------------------------------------- |
| 01 | Scope               | scope + closure from the ask [01]          | approves the boundary [02]             |
| 02 | Design (high level) | decision + rationale per subsection [03]   | spot-checks flagged callouts only      |
| 03 | Test strategy/cases | independent layers, traceable cases        | checks layers are truly independent    |
| 04 | Design (detailed)   | every file to be touched, tagged [04]      | approves blast radius before opening   |
| 05 | Implement           | executes in order, fills each step in live | performs the carved-out user actions   |
| 06 | Validate            | reruns layers, logs issues as hypotheses   | reviews open issues, closes Tasks rows |

01. also states out-of-scope / deferred items - as load-bearing as what's in scope.
02. cheapest point to redirect the work, since nothing is built yet.
03. flags ambiguous calls as **implementation decision** and any departure from an existing design as **deviation**.
04. tagged generated-vs-hand-authored, plus what's explicitly not expected to change.

## how the document shapes the workflow

- **guides** - the skeleton exists, mostly empty, before work starts, so every stage has a named place to land before the first line of scope is even filled in.
- **mirrors** - at any point in time the fill-state (which sections are still stubs, which Tasks rows are pending/open/closed) is an accurate readout of the project's actual state, not a plan frozen at kickoff.
- **shapes** - because Test cases and Edit locations are only written after Design is settled, the order sections get filled in enforces the order decisions get made in - jumping to code before test cases exist is visibly premature, not just discouraged.
- **directs** - an agent resuming in a new session reads the file's current fill-state instead of the chat history, and knows exactly which stage to resume at.
- **reflects** - after the fact, Validate is a record of what actually broke, kept distinct from Design's stated intent, so the two can be diffed to catch drift between what was meant and what was built.

## scale the skeleton to the feature

Not every feature needs all seven sections at full weight. A one-file bugfix can collapse Design (high level) and Design (detailed) into one short Design section and skip the Guideline footer. Keep the order and the id scheme even when sections are thin - consistency of shape is what makes many trackers, written over a long time by different sessions, still cross-reference cleanly.

## generic minimal skeleton (any codebase)

For a project that doesn't have this repo's `templates/feature-tracker.md` conventions (Contents block, References section, Guideline footer), this bare skeleton keeps the same section order and id scheme:

```md
# <feature name> - Feature tracker

## <id> (pending) <feature name>

## Tasks

| id      | seq | status  | milestone      |
| ------- | --- | ------- | -------------- |
| <F>.01  | 01  | open    | design         |
| <F>.02  | 02  | pending | implement      |
| <F>.IS  | 03  | pending | validate       |

## Scope

<what's being built, in plain language>

- **out of scope** - <explicit exclusions>
- **closure** - <acceptance condition, written before design exists>

## Design

### <concern area>

<decision + rationale>

**implementation decision** - <where the ask was ambiguous, what you chose, what you didn't>

## Test cases

_test strategy_

1. **self-report** - <what the code's own output proves>
2. **<independent layer>** - <what it checks against, without reading the code's own output>

| id       | scope-item | layer | check                |
| -------- | ---------- | ----- | --------------------- |
| <F>.TC.01| <F>.CK.01  | ...   | <what passes/fails>   |

## Edit locations

| id       | path        | change            |
| -------- | ----------- | ----------------- |
| <F>.EL.01| <path>      | <what changes>     |

## Implement

### 1. <step name>

edit locations: `<F>.EL.01`

<work, or a one-line stub until this step starts>

## Validate

| id       | seq | status  | issue                  |
| -------- | --- | ------- | ------------------------ |
| <F>.IS.01| 01  | pending | \<first out exception\>  |

**user actions**

- <anything only a human can do>
```
