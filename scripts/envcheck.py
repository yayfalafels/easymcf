#!/usr/bin/env python3
"""ENV-SCRIPT-05 — preflight, run once per session (or after any
environment-affecting change) before any loop iteration in `010-development-env.md`
section 5, so an environment defect is never misdiagnosed as a code bug.

    python scripts/envcheck.py

Exits 0 with "all checks passed" on success; on failure, prints one
`[FAIL] <check> — <fix>` line per failed check and exits 1.
"""

from __future__ import annotations

import glob
import os
import socket
import sys

from dotenv import load_dotenv

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO_ROOT)
load_dotenv()  # before Config() is built — ENV-CFG-03/07.02.03

from easymcf import SCHEMA_VERSION  # noqa: E402
from easymcf.config import Config  # noqa: E402
from easymcf.db.connection import schema_version  # noqa: E402

# env/ (repo root), never ~/env — ENV-SETUP-01/07.02.04
_OPS_ENV = os.path.join(_REPO_ROOT, "env")
_PLAYWRIGHT_CACHE = os.path.expanduser("~/.cache/ms-playwright")


def check_python_version() -> str | None:
    if sys.version_info < (3, 11):
        return f"Python {sys.version_info.major}.{sys.version_info.minor} < 3.11 — run via env/bin/python"
    return None


def check_venv() -> str | None:
    actual = os.path.realpath(sys.prefix)
    expected = os.path.realpath(_OPS_ENV)
    if actual != expected:
        return f"sys.prefix is {actual}, not {_OPS_ENV} — invoke every command as env/bin/python"
    return None


def check_chromium() -> str | None:
    if not glob.glob(os.path.join(_PLAYWRIGHT_CACHE, "chromium-*")):
        return "playwright chromium missing — run: python -m playwright install chromium"
    return None


def check_frontend_vendor() -> str | None:
    missing = [
        f
        for f in ("angular.min.js", "angular-route.min.js")
        if not os.path.exists(os.path.join(_REPO_ROOT, "frontend", "vendor", f))
    ]
    if missing:
        return f"frontend/vendor/{{{', '.join(missing)}}} missing — re-fetch per ENV-SETUP-05, commit"
    return None


def check_schema_version(db_path: str) -> str | None:
    on_disk = schema_version(db_path)
    if on_disk is not None and on_disk != SCHEMA_VERSION:
        return (
            f"database is version {on_disk}, code expects {SCHEMA_VERSION} "
            "— run: python scripts/resetdb.py --seed"
        )
    return None


def check_port_free(port: int) -> str | None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", port))
    except OSError:
        return f"port {port} already in use — kill the leftover process, or set PORT"
    finally:
        sock.close()
    return None


def check_mcf_mode(mode: str) -> str | None:
    if mode == "live":
        return "MCF_MODE=live is set — stop, this must be an explicit human-confirmed request"
    return None


def check_google_secret(config: Config) -> str | None:
    """A Google client id in .env needs its secret file, at mode 0600 (ARCH-AUTH-06)."""
    if not config.gcp_client_id:
        return None
    path = config.gcp_secret_path
    if not os.path.exists(path):
        return f"GCP_OAUTH_CLIENT_ID is set but {path} is missing"
    if os.stat(path).st_mode & 0o077:
        return f"{path} must have mode 0600 (chmod 600 {path})"
    return None


def main() -> int:
    config = Config()
    checks = [
        ("python version", check_python_version()),
        ("ops venv (env/)", check_venv()),
        ("playwright chromium", check_chromium()),
        ("frontend vendor assets", check_frontend_vendor()),
        ("db schema_version", check_schema_version(config.db_path)),
        ("port free", check_port_free(config.port)),
        ("mcf mode", check_mcf_mode(config.mcf_mode)),
        ("google client secret file", check_google_secret(config)),
    ]

    failures = [(name, msg) for name, msg in checks if msg]
    if not failures:
        print("all checks passed")
        return 0

    for name, msg in failures:
        print(f"[FAIL] {name} — {msg}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
