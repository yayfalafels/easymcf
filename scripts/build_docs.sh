#!/usr/bin/env bash
# 18.EL.17 - the single docs build entry point, for developers and the Pages workflow.
#
#   scripts/build_docs.sh
#
# Checks docs/design/ is in sync with the release design docs, then runs a strict MkDocs build into site/.
# The build fails on any WARNING line, and on a link to an excluded page, which MkDocs logs only at INFO
# level (Design probe finding 02). MKDOCS and PYTHON default to the .dev/dev-env tools; the workflow sets
# MKDOCS=mkdocs and PYTHON=python.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

MKDOCS="${MKDOCS:-.dev/dev-env/bin/mkdocs}"
PYTHON="${PYTHON:-.dev/dev-env/bin/python}"
LOGS_DIR="${LOGS_DIR:-.dev/logs}"
FEATURE_ID=18.05
TASK_NAME=docs-build
mkdir -p "$LOGS_DIR"
LOG_PATH="$LOGS_DIR/$(TZ=Asia/Singapore date +%Y%m%d%H%M%S)-$FEATURE_ID-$TASK_NAME.log"

fail() {
    echo "[FAIL] docs build: $1" | tee -a "$LOG_PATH"
    exit 1
}

if ! "$PYTHON" scripts/sync_design_docs.py --check 2>&1 | tee "$LOG_PATH"; then
    fail "docs/design/ is out of sync with the release design docs"
fi

export NO_MKDOCS_2_WARNING=1
set +e
"$MKDOCS" build --strict --clean 2>&1 | tee -a "$LOG_PATH"
status=${PIPESTATUS[0]}
set -e

[ "$status" -eq 0 ] || fail "mkdocs build --strict exited $status"
if grep -E "WARNING|excluded from the built site" "$LOG_PATH"; then
    fail "the build log holds a warning or a link to an excluded page"
fi
echo "[PASS] docs build" | tee -a "$LOG_PATH"
