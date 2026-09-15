<!--
boilerplate feature-tracker doc, matching this repo's actual conventions
(see docs/features/*.md and docs/assessments/*.md for real examples).

copy to docs/features/<NN>-<short-name>.md or docs/assessments/<NN>-<short-name>.md,
fill in <angle-bracket> placeholders, then delete this comment block.

<F>  = this feature's two-digit id, e.g. 12
fill sections top-to-bottom, but only as far as the current stage - a later
section stays a one-line stub until the stage before it is settled (see
tracker-pattern/REFERENCE.md, "the seven sections, in fill order").
-->
# <feature name, title case> - Feature tracker
>Review the guidelines before performing any actions including edits on the document

## <F> (pending) <feature name, lower case>

## Contents

- [Tasks](#tasks)
- [Scope](#scope)
- [References](#references)
- [Design](#design)
  - [<concern area>](#concern-area)
- [Test cases](#test-cases)
- [Edit locations](#edit-locations)
- [Implement](#implement)
- [Validate](#validate)
- [Guideline](#guideline)

## Tasks

| id      | seq | status  | milestone      |
| ------- | --- | ------- | -------------- |
| <F>.01  | 01  | open    | design         |
| <F>.02  | 02  | pending | implement      |
| <F>.IS  | 03  | pending | validate       |

## Scope

<short plain-language statement of what's being built and why>

- all steps can be executed by an autonomous claude ai agent with access to terminal using re-runnable idempotent scripts
- **out of scope** - <explicit exclusions / deferred items>
- **closure** - <acceptance condition, written before design exists>

## References

- **<name>** `<path/to/related/doc/or/script>`

## Design

### <concern area>

<decision + rationale>

**implementation decision** - <where the ask was ambiguous, what you chose, what you didn't>

**deviation** - <where this departs from an existing design doc or convention, and why>

## Test cases

_test strategy_

1. **self-report** - <what the code's own [PASS]/[FAIL] log output proves>
2. **<independent layer>** - <what it checks against, without reading the code's own output>

| id        | scope-item | layer | check                |
| --------- | ---------- | ----- | --------------------- |
| <F>.TC.01 | <F>.CK.01  | ...   | <what passes/fails>   |

**tools** - reproduce independently:

```bash
<copy-pasteable command to re-run this check by hand>
```

## Edit locations

| id        | path        | change            |
| --------- | ----------- | ----------------- |
| <F>.EL.01 | <path>      | <what changes>     |

## Implement

### 1. <step name>

edit locations: `<F>.EL.01`

_expand when this step starts_

## Validate

<what was actually run, against what evidence, once implementation is done>

Log artifacts (`.dev/logs/`, gitignored - see commands below to inspect or reproduce):

| id | log file             | exit | evidence            |
| -- | --------------------- | ---- | --------------------- |
| 01 | `<ts>-<F>.<n>-<task>.log` | 0    | <what it shows>     |

**secondary validation** - reproduce independently:

```bash
<copy-pasteable command bypassing the feature's own scripts>
```

**Issues**

- inventory all first out exceptions and issues encountered in this table
- for each issue, create an issue section and use it to document diagnostics and resolution steps - see
  `validation/REFERENCE.md` and its `templates/issue-diagnostic-section.md` boilerplate

| id       | seq | status  | issue                    |
| -------- | --- | ------- | -------------------------- |
| <F>.IS.01| 01  | pending | \<first out exception\>    |

<!-- paste one templates/issue-diagnostic-section.md block per row above, in place of this comment -->

**user actions**

- <anything only a human had to do - GUI-only tool, third-party auth, an account only a person holds>

## Guideline

### instructions

review and strictly follow these relevant skills when performing tasks for this feature implementation and working with this document

### relevant skills

- markdown-tables
- feature-implementation-guide
