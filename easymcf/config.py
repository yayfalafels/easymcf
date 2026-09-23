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


def _client_id() -> str:
    value = os.environ.get("GCP_OAUTH_CLIENT_ID", "").strip()
    return "" if value.startswith("%%") else value  # an unfilled .env.example placeholder never enables Google


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
    session_lifetime_h: int = field(default_factory=lambda: int(os.environ.get("SESSION_LIFETIME_H", "336")))
    cookie_secure: bool = field(default_factory=lambda: os.environ.get("COOKIE_SECURE", "0") == "1")
    signin_max_failures: int = field(default_factory=lambda: int(os.environ.get("SIGNIN_MAX_FAILURES", "5")))
    signin_window_s: int = field(default_factory=lambda: int(os.environ.get("SIGNIN_WINDOW_S", "900")))
    password_min_length: int = field(default_factory=lambda: int(os.environ.get("PASSWORD_MIN_LENGTH", "12")))
    photo_dir: str = field(default_factory=lambda: os.environ.get("PHOTO_DIR", "data/photos"))
    photo_max_bytes: int = field(default_factory=lambda: int(os.environ.get("PHOTO_MAX_BYTES", "2097152")))
    gcp_client_id: str = field(default_factory=lambda: _client_id())
    google_discovery_url: str = field(
        default_factory=lambda: os.environ.get("GOOGLE_DISCOVERY_URL", "https://accounts.google.com/.well-known/openid-configuration")
    )

    def __post_init__(self) -> None:
        if self.mcf_mode not in {"fixture", "live"}:
            raise ValueError("MCF_MODE must be 'fixture' or 'live'")

    @property
    def gcp_secret_path(self) -> str:
        return os.environ.get("GCP_OAUTH_SECRET_FILE") or os.path.join(self.secrets_dir, "gcp_oauth_client_secret")

    @property
    def google_redirect_uri(self) -> str:
        return os.environ.get("GOOGLE_REDIRECT_URI") or f"http://127.0.0.1:{self.port}/api/v1/auth/google/callback"

    def google_client_secret(self) -> str:
        try:
            with open(self.gcp_secret_path, encoding="utf-8") as handle:
                return handle.read().strip()
        except OSError:
            return ""

    @property
    def google_enabled(self) -> bool:
        return bool(self.gcp_client_id and self.google_client_secret())
