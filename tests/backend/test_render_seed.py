"""18.EL.14 - oracle tests for scripts/render_seed.py (18.TC.41 to 18.TC.45).

Each test writes its own template files into a temp directory with the expected output typed here, so no test
reads the tracked seed/ or the repo's .env (strategy rule 06).
"""

from __future__ import annotations

import os
import sqlite3
import sys

import pytest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_REPO_ROOT, "scripts"))

import render_seed  # noqa: E402

pytestmark = pytest.mark.backend

VALUES = {"INITIAL_USER_NAME": "Probe Person", "INITIAL_USER_EMAIL": "probe@example.test"}


def _write(directory, name, text):
    (directory / name).write_text(text, encoding="utf-8")


def test_renders_every_token(tmp_path):
    """18.TC.41"""
    _write(tmp_path, "01_a.sql", "INSERT INTO t VALUES ('{{INITIAL_USER_NAME}}', '{{INITIAL_USER_EMAIL}}');\n")
    _write(tmp_path, "02_b.sql", "INSERT INTO s VALUES ('{{INITIAL_USER_EMAIL}}');\n")
    rendered = render_seed.render_seed(VALUES, seed_dir=str(tmp_path))
    assert rendered == [
        ("01_a.sql", "INSERT INTO t VALUES ('Probe Person', 'probe@example.test');\n"),
        ("02_b.sql", "INSERT INTO s VALUES ('probe@example.test');\n"),
    ]
    assert all("{{" not in text for _, text in rendered)


def test_unknown_token_raises_with_file(tmp_path):
    """18.TC.42"""
    _write(tmp_path, "03_other.sql", "INSERT INTO t VALUES ('{{OTHER}}');\n")
    with pytest.raises(ValueError, match=r"03_other\.sql.*OTHER"):
        render_seed.render_seed(VALUES, seed_dir=str(tmp_path))


def test_empty_value_raises(tmp_path, monkeypatch):
    """18.TC.43: validation runs before any file is read."""
    _write(tmp_path, "01_a.sql", "INSERT INTO t VALUES ('{{INITIAL_USER_NAME}}');\n")
    opened = []
    real_open = open
    monkeypatch.setattr("builtins.open", lambda *a, **k: opened.append(a[0]) or real_open(*a, **k))
    with pytest.raises(ValueError, match="INITIAL_USER_NAME"):
        render_seed.render_seed({**VALUES, "INITIAL_USER_NAME": "  "}, seed_dir=str(tmp_path))
    assert opened == []


def test_quote_is_doubled_and_loads(tmp_path):
    """18.TC.44"""
    _write(tmp_path, "01_user.sql", "INSERT INTO u (name, email) VALUES ('{{INITIAL_USER_NAME}}', '{{INITIAL_USER_EMAIL}}');\n")
    [(_, text)] = render_seed.render_seed({**VALUES, "INITIAL_USER_NAME": "O'Brien Test"}, seed_dir=str(tmp_path))
    assert "'O''Brien Test'" in text
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE u (name TEXT NOT NULL, email TEXT NOT NULL CHECK (email = lower(email)))")
    conn.executescript(text)
    assert conn.execute("SELECT name, email FROM u").fetchone() == ("O'Brien Test", "probe@example.test")


@pytest.mark.parametrize("name_value, email_value, expected, source", [
    (None, None, {"INITIAL_USER_NAME": "Demo User", "INITIAL_USER_EMAIL": "demo.user@example.test"}, "public default"),
    ("", "   ", {"INITIAL_USER_NAME": "Demo User", "INITIAL_USER_EMAIL": "demo.user@example.test"}, "public default"),
    ("%%INITIAL_USER_NAME%%", "%%INITIAL_USER_EMAIL%%",
     {"INITIAL_USER_NAME": "Demo User", "INITIAL_USER_EMAIL": "demo.user@example.test"}, "public default"),
    ("Probe Person", None, {"INITIAL_USER_NAME": "Probe Person", "INITIAL_USER_EMAIL": "demo.user@example.test"}, ".env"),
    (None, "Probe@Example.TEST", {"INITIAL_USER_NAME": "Demo User", "INITIAL_USER_EMAIL": "probe@example.test"}, ".env"),
])
def test_env_fallback_per_variable(monkeypatch, name_value, email_value, expected, source):
    """18.TC.45: each variable falls back on its own. The repo's .env is never loaded here."""
    monkeypatch.setattr(render_seed, "dotenv_values", lambda *a, **k: {})
    for key, value in (("INITIAL_USER_NAME", name_value), ("INITIAL_USER_EMAIL", email_value)):
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    assert render_seed.values_from_env() == (expected, source)


def test_values_from_env_leaves_the_environment_unchanged(monkeypatch, tmp_path):
    """18.TC.51, the 18.IS.03 regression: reading .env must not re-add keys the suite removed, such as MCF_MODE."""
    (tmp_path / ".env").write_text("MCF_MODE=live\nINITIAL_USER_NAME=File Person\n", encoding="utf-8")
    monkeypatch.setattr(render_seed, "_REPO_ROOT", str(tmp_path))
    monkeypatch.delenv("MCF_MODE", raising=False)
    monkeypatch.delenv("INITIAL_USER_NAME", raising=False)
    monkeypatch.delenv("INITIAL_USER_EMAIL", raising=False)
    before = dict(os.environ)
    values, source = render_seed.values_from_env()
    assert dict(os.environ) == before
    assert (values["INITIAL_USER_NAME"], source) == ("File Person", ".env")
