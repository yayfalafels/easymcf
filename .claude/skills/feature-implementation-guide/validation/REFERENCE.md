# validation guide

This repo's concrete mechanics for `tracker-pattern/REFERENCE.md`'s stage 07 (Validate) - the issues/diagnostics workflow.

**boilerplate:** `templates/issue-diagnostic-section.md` in this folder is a copy-paste block for one issue (table row + full diagnostic section) - paste it into a tracker's `## Validate` section the moment a first-out exception happens, then fill it in as you diagnose.

- inventory all first-out exceptions and issues encountered in the issues table
- issue tasks and subtasks are identified by `{feature_id}.IS.{issue_id}.{subtask_id}...` - ex: `02.IS.01.01...`
- for each issue, create an issue section and use it to document diagnostics and resolution steps
- a first-out exception is NOT a diagnostic step
- diagnostic steps reveal information or apply a fix
- assume re-run and validation - these are not diagnostic steps
- keep the step description brief; use the diagnostic details section to elaborate actions and learnings for each step

## issue diagnostics sections

- problem description
- exception
- triggering actions
- hypothesis
- diagnostic steps
- diagnostic details

## issues table

| id       | seq | status  | issue                 |
| -------- | --- | ------- | ---------------------- |
| 02.IS.01 | 01  | pending | \<first out exception\> |

## issue section header

```
_02.IS.01 (pending) <first out exception>_
```

## diagnostic steps table

| id          | seq | status  | step                    |
| ----------- | --- | ------- | ------------------------ |
| 02.IS.01.01 | 01  | pending | \<diagnostic step 01\>  |

## diagnostic dir

Tmp resources and environments (ad-hoc scripts, throwaway containers, tmp files) are allowed only here, for issue-diagnostics purposes - not for normal implementation work (see `implementation/REFERENCE.md`).

```
.dev/
└── features/
    └── <##>-<feature name>/           # ex "02-dev-env-setup-postgresql-db/"
        └── scripts/
            └── 01-read-container-logs.sh  # example adhoc script to read container logs
```
