"""Env-var configuration surface (ARCH-RUN-07).

No `.env` file is required for the app to run — every value below has a
default. Fields use `default_factory` deliberately, not a plain literal
default: a plain default would read `os.environ` once, at class-import
time, and never again — `tests/conftest.py`'s fixture sets `DB_PATH`
per session *after* this module is already imported, so each `Config()`
call must re-read the environment, not reuse a value baked in at import.

No project-specific prefix on these names (`ENV-CFG-03`/`07.02.03`): with
only two venvs and no other project sharing this shell (`CLAUDE.md`'s
two-venv rule), the collision risk a prefix would guard against is an
accepted, named tradeoff, not an oversight.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Config:
    db_path: str = field(default_factory=lambda: os.environ.get("DB_PATH", "data/easymcf.db"))
    port: int = field(default_factory=lambda: int(os.environ.get("PORT", "5000")))
    secrets_dir: str = field(default_factory=lambda: os.environ.get("SECRETS_DIR", ".secrets"))
    mcf_mode: str = field(default_factory=lambda: os.environ.get("MCF_MODE", "fixture"))
    headless: bool = field(default_factory=lambda: os.environ.get("HEADLESS", "1") != "0")
    apply_poll_retries: int = field(
        default_factory=lambda: int(os.environ.get("APPLY_POLL_RETRIES", "5"))
    )
    apply_poll_delay_s: float = field(
        default_factory=lambda: float(os.environ.get("APPLY_POLL_DELAY_S", "5"))
    )
