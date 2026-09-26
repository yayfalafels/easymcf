---
name: documentation-style
description: Direct, concise prose rules for descriptive documentation in this repo. Covers requirements, design docs, feature trackers, and skill and agent instructions. Rules cover hard-wrap avoidance, negation comparisons, parenthesis, semicolon and hyphen overuse, list enumeration style, and top-loaded page structure. Applies only to narrative *.md prose, never to source code or other formally structured syntax. Use before writing new prose documentation, or when reviewing or editing existing docs for style.
---

## Contents

- [Guidelines](#guidelines)
- [Case examples](#case-examples)
  - [01 hard-wrapped line breaks](#hard-wrapped-line-breaks)
  - [02 negation comparisons](#negation-comparisons)
  - [03 avoid parenthesis](#avoid-parenthesis)
  - [04 use fullstops limit semicolons and hyphens](#use-fullstops-limit-semicolons-and-hyphens)
  - [05 numeric enumerated lists](#numeric-enumerated-lists-never-lettered)
  - [06 lead with the point](#lead-with-the-point)
  - [07 table of contents](#table-of-contents)
  - [08 alias references](#alias-references)

## Guidelines

Apply all six rules to descriptive markdown prose. They do not apply to source code, config syntax, or literal command/log output inside a fenced block.

01. no hard-wrapped line breaks. write each paragraph as one unwrapped line in the raw source, and let the editor soft-wrap it for display.
02. direct, concise language. avoid negation comparisons such as "this, not that". state the fact plainly instead.
03. avoid parenthesis. the one exception is the first introduction of an acronym, e.g. Central Provident Fund (CPF). rewrite other parenthetical fragments into the sentence itself, or split them into a new sentence.
04. use fullstops. limit semicolons and hyphens wherever the two joined expressions could instead be two separate sentences.
05. use enumerated lists for anything longer than two or three items. prefer numbered lists over bullets. always enumerate with numbers, 01, 02, 03, never letters, a, b, c.
06. lead with the point. put the summary, conclusions, and commonly-needed material near the top, so a reader gets the gist without reading to the bottom. never place a "wrap-up", "references", or "checklist" section near the bottom of a page. that material belongs at the top, or should be removed.
07. add a table of contents once a doc grows past roughly 50 lines. place it directly below the frontmatter, ahead of every other section, so a reader can jump straight to the part they need.

## Case examples

Each example below is a real excerpt audited from this repo's documentation, paired with a revision that satisfies the rule. Use these as a calibration reference, not an exhaustive list of every violation in the repo.

### hard-wrapped line breaks

Source: `.claude/skills/feature-implementation-guide/tracker-pattern/templates/feature-tracker.md`, inside the top comment block.

Before:

```
<F>  = this feature's two-digit id, e.g. 12
fill sections top-to-bottom, but only as far as the current stage - a later
section stays a one-line stub until the stage before it is settled (see
tracker-pattern/REFERENCE.md, "the seven sections, in fill order").
```

After:

```
<F> = this feature's two-digit id, e.g. 12. Fill sections top-to-bottom, but only as far as the current stage. A later section stays a one-line stub until the stage before it is settled, per tracker-pattern/REFERENCE.md's "the seven sections, in fill order".
```

The revision also removes the mid-sentence hyphen and the parenthetical "see ..." aside, per rules 03 and 04.

### negation comparisons

Source: `docs/releases/010/features/010.08-db-schema-seed-data.md:95`.

Before:

```
the **data model**'s field lists are conceptual, not DDL (its own Purpose section says so), so concrete SQLite types are resolved here:
```

After:

```
the **data model**'s field lists are conceptual. Its own Purpose section says so. Concrete SQLite types are resolved here:
```

Source: `docs/releases/010/design/010-data-model.md:87`.

Before:

```
The actual file lives on MCF's own profile — 010 only needs to remember the label the apply run matches against MCF's resume-selector options by substring (see [010-prototype.md](010-prototype.md) `cv_select()`), so this table is a small label catalog, not file storage.
```

After:

```
The actual file lives on MCF's own profile. 010 only needs to remember the label the apply run matches against MCF's resume-selector options by substring, per [010-prototype.md](010-prototype.md)'s `cv_select()`. This table is a small label catalog.
```

### avoid parenthesis

Source: `docs/wsl-memory.md:5`.

Before:

```
WSL2 (running VS Code's Remote-WSL server) was crashing/freezing intermittently during normal dev work (VS Code + extensions + a Docker Compose stack + one or more Claude Code CLI sessions).
```

After:

```
WSL2, running VS Code's Remote-WSL server, was crashing and freezing intermittently during normal dev work. The dev workload included VS Code with extensions, a Docker Compose stack, and one or more Claude Code CLI sessions.
```

### use fullstops limit semicolons and hyphens

Source: `docs/releases/010/design/010-data-model.md:197`.

Before:

```
A search run is always track-scoped; an apply run can span leads queued across multiple tracks, so `track_id` may be null there.
```

After:

```
A search run is always track-scoped. An apply run can span leads queued across multiple tracks, so `track_id` may be null there.
```

### numeric enumerated lists

Source: `docs/releases/010/design/010-architecture.md:134`, ARCH-STO-05.

Before:

```
Two rules: (a) the seed loader writes date/timestamp columns **relative to load time** (e.g. a lead 27 days stale and one 29 days stale, computed at load); (b) all application code reads current time through a single `easymcf/clock.py::now()` indirection so a test can substitute a fixed clock instead of sleeping or waiting for wall-clock drift. Without (b), REQ-CRM-05 is not deterministically testable.
```

After:

```
Two rules apply.

01. the seed loader writes date and timestamp columns **relative to load time**. For example, a lead 27 days stale and one 29 days stale, both computed at load.
02. all application code reads current time through a single `easymcf/clock.py::now()` indirection, so a test can substitute a fixed clock instead of sleeping or waiting for wall-clock drift.

Without rule 02, REQ-CRM-05 is not deterministically testable.
```

Source: `docs/releases/010/design/010-architecture.md:160`, ARCH-BOT-01.

Before:

```
Rationale: (a) it removes the chromedriver/Chrome version-matching failure mode, a named `jobsearch` local-env pain point; (b) `page.route()` interception is what makes the mock-e2e tier possible without a stub that bypasses the real scraping code (ARCH-TEST-04); (c) one browser dependency instead of two, installed by `playwright install --with-deps chromium` into a user cache — nothing system-wide, nothing in the repo.
```

After:

```
Rationale:

01. it removes the chromedriver/Chrome version-matching failure mode, a named `jobsearch` local-env pain point.
02. `page.route()` interception is what makes the mock-e2e tier possible without a stub that bypasses the real scraping code, per ARCH-TEST-04.
03. one browser dependency instead of two, installed by `playwright install --with-deps chromium` into a user cache. Nothing system-wide, nothing in the repo.
```

### lead with the point

Source: the feature-tracker template's section order, `.claude/skills/feature-implementation-guide/tracker-pattern/templates/feature-tracker.md`, and every doc built from it, e.g. `docs/releases/010/features/010.07-local-dev-env.md` and `010.08-db-schema-seed-data.md`.

Before: the template orders its sections Tasks, Scope, References, Design, Test cases, Edit locations, Implement, Validate, Guideline. Guideline is the section that tells a reader which skills govern the document and must be followed. It sits last, after every implementation log entry, so a reader or an agent opening a long tracker doc scrolls past the full work history before reaching the governing instructions. The title line already gestures at this, `>Review the guidelines before performing any actions including edits on the document`, but the actual Guideline content lives far below it.

After: move Guideline directly under the title, ahead of Contents and Tasks, so the governing instructions and the pointer to them sit together at the top:

```
# <feature name, title case> - Feature tracker

## Guideline

review and strictly follow these relevant skills when performing tasks for this feature implementation and working with this document

- markdown-tables
- feature-implementation-guide

## <F> (pending) <feature name, lower case>

## Contents
...
```

This finding belongs to the feature-implementation-guide skill's tracker-pattern template, so a repo-wide fix is out of scope here. It is recorded as the case example for rule 06 because it is the clearest real instance of the pattern this rule forbids.

For contrast, `docs/releases/010/010-issues.md` places its `## Summary` section at roughly 13% into the document, ahead of the detailed per-issue sections. That placement already satisfies rule 06 and needs no revision.

### table of contents

Source: this skill file itself, at its first draft.

Before: the file opened straight from the frontmatter into `## Guidelines`, with no table of contents, despite already running past 150 lines across seven rules and their case examples. A reader had to scroll the whole page to find a specific rule.

After: a `## Contents` section sits directly below the frontmatter, listing every top-level and case-example heading as a link, matching the structure at the top of this file.

### alias references

consolidate all exact path references to files, external references, urls into a single `## references` section, and then refer to them by their alias throughout the document. This enables clear tracing and easier maintenance in case of future file path updates.

correct pattern

```md

## references

- **architecture design**: `010-architecture.md`
- **data model design**: `010-data-model.md`

neither the **architecture design** nor the **data model design** mandates DB-level ...
```

wrong pattern

```md
neither `010-architecture.md` nor `010-data-model.md` mandates DB-level ...
```

