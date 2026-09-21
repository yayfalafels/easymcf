"""Shared support for tests/frontend/ (tier 1b, ARCH-TEST-09) and tests/e2e/
(tier 2, ARCH-TEST-04): spawning the real `python -m easymcf` process on an
ephemeral port and polling `/api/v1/health` until ready (ARCH-TEST-04), plus
a shared Playwright browser/page fixture pair. Both tiers spawn the app the
same way (ARCH-TEST-09: "spawns python -m easymcf the same way") — this
module is the one implementation of that instead of two copies.

conftest.py in each tier imports the fixtures it needs from here rather than
redefining them — pytest picks up a fixture by name in whichever module a
conftest.py makes it visible in, so `from tests._browser_support import
browser, page` in a conftest.py registers them exactly as if defined there.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time

import pytest
import requests
from playwright.sync_api import sync_playwright

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def spawn_app(db_path: str, timeout_s: float = 15.0, extra_env: dict | None = None, port: int | None = None):
    """Start `python -m easymcf` on an ephemeral port against db_path, in
    fixture MCF mode, headless. Polls /api/v1/health until ready (ARCH-TEST-04)
    — this polling happens over plain `requests`, never through a Playwright
    page, so it is unaffected by any page.route() interception a caller sets
    up afterward. extra_env adds or overrides environment variables, and port pins the port when the caller must know it
    before the app starts (a redirect URI built from it). Returns (process, base_url); caller must terminate_app() it.
    """
    port = port or _free_port()
    env = os.environ.copy()
    env["DB_PATH"] = db_path
    env["PORT"] = str(port)
    env.setdefault("MCF_MODE", "fixture")
    env.setdefault("HEADLESS", "1")
    env.update(extra_env or {})

    proc = subprocess.Popen(
        [sys.executable, "-m", "easymcf"],
        cwd=_REPO_ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base_url = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError("app process exited before becoming ready")
        try:
            resp = requests.get(f"{base_url}/api/v1/health", timeout=1)
            if resp.status_code == 200:
                return proc, base_url
        except requests.RequestException:
            pass
        time.sleep(0.2)
    proc.terminate()
    proc.wait(timeout=5)
    raise TimeoutError(f"app did not become ready within {timeout_s}s")


def terminate_app(proc: subprocess.Popen) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=os.environ.get("HEADLESS", "1") != "0")
        yield b
        b.close()


@pytest.fixture()
def page(browser):
    pg = browser.new_page()
    yield pg
    pg.close()
