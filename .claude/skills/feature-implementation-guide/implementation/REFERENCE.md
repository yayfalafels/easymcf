# implementation guide

This repo's concrete mechanics for `../tracker-pattern/REFERENCE.md`'s stage 06 (Implement).

Use standard git-tracked, re-runnable paths and scripts for build, deploy, and resource provisioning. Do **NOT** improvise ad-hoc or tmp Python virtual envs or Docker containers when implementing normal tasks. Tmp resources and environments are allowed only for issue-diagnostics purposes - see the diagnostic dir convention in `../validation/REFERENCE.md`.

## parameterization

- make use of parameterization and the `.env` file
- avoid hard-coded literals, especially repeated locations
- identify and set all parameters at the beginning of scripts

## error handling

- wrap risky or complex execution steps in safe runnable wrappers - functions or subscripts that ensure `exit 0`
- for wrapped scripts or functions: non-zero exit on failure, no silent failures
- anticipate, catch, and gracefully handle anticipatable failures and exceptions
- use descriptive error messages for classified failures

## logging

- write diagnostic log files for every runnable action
- echo diagnostic log lines for key steps to enable informative feedback
- use standard log file naming and save to the standard log file destination
- use standard notations `[PASS]` / `[FAIL]` in log lines for pass and fail

### log file naming

Use the standard log file naming convention:

```
<YYYYMMDDHHMMSS>-<feature_id>.<subfeature_id>.{...}-<short task name>.log
```

example:

```
20260822185612-02.04.-sql-create-generate.log
```

Parameterize the log file naming in scripts:

```bash
# .env
LOGS_DIR=.dev/logs
TIMEZONE='Asia/Singapore'
TIMESTAMP_FORMAT=%y%m%d%H%M%S

# source .env
FEATURE_ID=02.04
TASK_NAME=sql-create-generate
LOG_FILE=$(TZ=$TIMEZONE date +$TIMESTAMP_FORMAT)-$FEATURE_ID-$TASK_NAME.log
LOG_PATH=$LOGS_DIR/$LOG_FILE
```

### scripts directory convention

```
.dev/
└── features/
    └── <##>-<feature name>/           # ex "02-dev-env-setup-postgresql-db/"
        └── scripts/
            └── 01-read-container-logs.sh  # example adhoc script to read container logs
```
