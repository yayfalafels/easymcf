---
name: feature-implementation-guide
description: spec-first feature-tracker document pattern (scope -> design -> test strategy/cases -> edit locations -> implement -> validate) plus this repo's concrete implementation/validation conventions - git-tracked rerunnable scripts, .env parameterization, error handling, logging file naming, and the issues/diagnostics workflow used in docs/features/*.md and docs/assessments/*.md. Load before drafting a new feature/assessment tracker doc, or before implementing or validating a feature.
---

## relevant skills

- markdown-tables - apply it to every table produced anywhere in this guide (Tasks, Test cases, Edit locations, issues table, diagnostic steps table, etc.)

## subskills - load the one(s) the current stage needs

This skill is split into three subskills, one per concern. Don't load all three for a small task - jump straight to the one the current stage needs.

| subskill | load it when... | file |
| --- | --- | --- |
| tracker-pattern | starting a new feature/assessment tracker doc, or deciding which section to fill in next | `tracker-pattern/REFERENCE.md` |
| implementation | writing or editing scripts for a feature - parameterization, error handling, logging | `implementation/REFERENCE.md` |
| validation | validating a feature, or a first-out exception just happened | `validation/REFERENCE.md` |

**boilerplate files** (copy-paste starting points, not narrative docs):

- `tracker-pattern/templates/feature-tracker.md` - full tracker doc scaffold matching this repo's conventions
- `validation/templates/issue-diagnostic-section.md` - one issue's table row + diagnostic section

## how the three fit together

`tracker-pattern/REFERENCE.md` defines the document *shape* - seven sections, filled in order, one markdown file that is simultaneously the spec/design/test-plan/progress-tracker for one feature. `implementation/REFERENCE.md` and `validation/REFERENCE.md` are this repo's concrete mechanics for two of those seven sections (stage 06 Implement, stage 07 Validate) - a project without this repo's conventions defines its own equivalent, matched to its own stack, without changing the document shape.
