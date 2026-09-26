#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$ROOT/env/bin/python"
RESET_SEED=0

usage() {
    echo "Usage: scripts/restart.sh [--reset-seed]"
}

fail() {
    echo "[FAIL] $*" >&2
    exit 1
}

if [[ ${1:-} == "--reset-seed" ]]; then
    RESET_SEED=1
    shift
fi
[[ $# -eq 0 ]] || { usage >&2; exit 2; }
[[ -x "$PYTHON" ]] || fail "operational interpreter not found: $PYTHON"

MCF_MODE="$(cd "$ROOT" && "$PYTHON" -c 'from dotenv import dotenv_values; print(dotenv_values(".env").get("MCF_MODE", ""))')"
[[ "$MCF_MODE" == "live" || "$MCF_MODE" == "fixture" ]] || fail "MCF_MODE in .env must be 'fixture' or 'live'"
export MCF_MODE

PORT="$(cd "$ROOT" && "$PYTHON" -c 'from dotenv import load_dotenv; load_dotenv(); from easymcf.config import Config; print(Config().port)')"
mapfile -t LISTENERS < <(fuser -n tcp "$PORT" 2>/dev/null | tr ' ' '\n' | sed '/^$/d' | sort -u)

for pid in "${LISTENERS[@]}"; do
    [[ -r "/proc/$pid/cmdline" ]] || fail "cannot inspect process $pid listening on port $PORT"
    cmdline="$(tr '\0' ' ' < "/proc/$pid/cmdline")"
    cwd="$(readlink -f "/proc/$pid/cwd" 2>/dev/null || true)"
    if [[ "$cwd" != "$ROOT" || "$cmdline" != *"-m easymcf"* ]]; then
        fail "port $PORT belongs to another process: pid=$pid cwd=$cwd command=$cmdline"
    fi
    echo "[PASS] stopping EasyMCF pid $pid on port $PORT"
    kill -TERM "$pid"
    for _ in {1..50}; do
        kill -0 "$pid" 2>/dev/null || break
        sleep 0.1
    done
    if kill -0 "$pid" 2>/dev/null; then
        echo "[PASS] forcing EasyMCF pid $pid to stop"
        kill -KILL "$pid"
    fi
done

if [[ $RESET_SEED -eq 1 ]]; then
    echo "[PASS] resetting and seeding database"
    (cd "$ROOT" && "$PYTHON" scripts/resetdb.py --seed)
fi

echo "[PASS] starting EasyMCF on port $PORT with MCF_MODE=$MCF_MODE from .env"
cd "$ROOT"
exec "$PYTHON" -m easymcf