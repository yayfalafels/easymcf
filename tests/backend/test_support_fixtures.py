"""13.EL.07, .09, .10 - the shared test support: seeded credentials, stub provider fixture, spawn_app parameters."""

from __future__ import annotations

import json
import os
import sqlite3

import pytest
import requests
from werkzeug.security import check_password_hash

from tests._browser_support import _free_port, spawn_app, terminate_app
from tests.support import images

pytestmark = pytest.mark.backend

SUPPORT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "support")


def test_users_json_matches_the_seeded_hashes(db_path):
    users = json.load(open(os.path.join(SUPPORT, "users.json"), encoding="utf-8"))
    conn = sqlite3.connect(db_path)
    hashes = {email: h for email, h in conn.execute("SELECT email, password_hash FROM user")}
    for name, creds in users.items():
        assert check_password_hash(hashes[creds["email"]], creds["password"]), name


def test_stub_provider_fixture_serves_discovery(stub_provider):
    doc = requests.get(stub_provider + "/.well-known/openid-configuration").json()
    assert doc["issuer"] == stub_provider


def test_spawn_app_pins_the_port_and_passes_extra_env(db_path):
    port = _free_port()
    proc, base_url = spawn_app(db_path, port=port, extra_env={"GOOGLE_REDIRECT_URI": f"http://127.0.0.1:{port}/cb"})
    try:
        assert base_url == f"http://127.0.0.1:{port}"
        assert requests.get(base_url + "/api/v1/health").json() == {"status": "ok"}
    finally:
        terminate_app(proc)


def test_fixture_images_have_the_declared_shapes(tmp_path):
    from PIL import Image

    assert Image.open(images.path("photo_ok.png")).size == (64, 64)
    assert Image.open(images.path("photo_wide.jpg")).format == "JPEG"
    assert open(images.path("photo_fake.png"), "rb").read().startswith(b"this is not an image")
    big = images.make_oversize(2097152, str(tmp_path / "big.png"))
    assert os.path.getsize(big) == 2097153
    assert Image.open(big).format == "PNG"
