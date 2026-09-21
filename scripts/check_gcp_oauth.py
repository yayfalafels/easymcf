#!/usr/bin/env python3
"""Check the Google OAuth client setup without the app (task 13.04 step 11, task 13.11 early validation).

`env/bin/python scripts/check_gcp_oauth.py`

Reads GCP_OAUTH_CLIENT_ID and GOOGLE_REDIRECT_URI from .env and the client secret from the secret file, then
asks Google three questions. Only Google's own endpoints receive the values, and no secret is ever printed.

  01. are the client id, redirect URI, and secret file present, with the secret file at mode 0600?
  02. does Google's authorization endpoint accept the client id and the redirect URI?
  03. does Google's token endpoint accept the client id and the secret? A bogus authorization code answers
      `invalid_grant` when the credentials are right and `invalid_client` when they are wrong.
"""

from __future__ import annotations

import os
import sys

import requests
from dotenv import load_dotenv

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_SCRIPTS_DIR)
sys.path.insert(0, _REPO_ROOT)
load_dotenv()  # before Config() is built - ENV-CFG-03/07.02.03

from easymcf.config import Config  # noqa: E402

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"


def check_local(config: Config) -> list[tuple[bool, str]]:
    results = []
    client_id = config.gcp_client_id
    results.append((client_id.endswith(".apps.googleusercontent.com"), "GCP_OAUTH_CLIENT_ID is set and looks like a Google client id"))
    path = config.gcp_secret_path
    present = os.path.isfile(path) and bool(config.google_client_secret())
    results.append((present, f"client secret file {path} exists and is not empty"))
    if present:
        mode = os.stat(path).st_mode & 0o777
        results.append((mode & 0o077 == 0, f"client secret file mode is {oct(mode)}, expected 0600"))
    results.append((config.google_redirect_uri.startswith("http://127.0.0.1"), f"redirect URI is {config.google_redirect_uri}"))
    return results


def check_authorize(config: Config) -> tuple[bool, str]:
    """Google validates the redirect URI only after its first redirects, so the check follows them and reads the
    page it lands on: the sign-in page when the client id and redirect URI are registered, an error page otherwise."""
    params = {"client_id": config.gcp_client_id, "redirect_uri": config.google_redirect_uri, "response_type": "code",
              "scope": "openid email", "state": "check"}
    response = requests.get(AUTH_URL, params=params, allow_redirects=True, timeout=20)
    body = response.text.lower()
    if "redirect_uri_mismatch" in body:
        return False, "Google reports redirect_uri_mismatch, so the console redirect URI differs from GOOGLE_REDIRECT_URI"
    if "invalid_client" in body or "oauth client was not found" in body:
        return False, "Google reports the OAuth client was not found, so GCP_OAUTH_CLIENT_ID is wrong"
    if "/oauth/error" in response.url or response.status_code != 200:
        return False, f"Google shows an error page ({response.url.split('?')[0]}, HTTP {response.status_code})"
    return True, f"authorization endpoint accepts the client id and redirect URI (lands on {response.url.split('?')[0]})"


def check_token(config: Config) -> tuple[bool, str]:
    data = {"grant_type": "authorization_code", "code": "not-a-real-code", "client_id": config.gcp_client_id,
            "client_secret": config.google_client_secret(), "redirect_uri": config.google_redirect_uri}
    response = requests.post(TOKEN_URL, data=data, timeout=15)
    error = (response.json() if response.headers.get("content-type", "").startswith("application/json") else {}).get("error")
    if error == "invalid_grant":
        return True, "token endpoint accepts the client id and secret (bogus code answered invalid_grant)"
    if error == "invalid_client":
        return False, "Google reports invalid_client, so the client id or the secret is wrong"
    return False, f"unexpected token endpoint answer (HTTP {response.status_code}, error {error})"


def main() -> int:
    config = Config()
    results = check_local(config)
    if all(ok for ok, _ in results):
        for check in (check_authorize, check_token):
            try:
                results.append(check(config))
            except requests.RequestException as exc:
                results.append((False, f"{check.__name__} could not reach Google: {type(exc).__name__}"))
    failed = 0
    for ok, message in results:
        print(f"[{'PASS' if ok else 'FAIL'}] {message}")
        failed |= not ok
    return failed


if __name__ == "__main__":
    raise SystemExit(main())
