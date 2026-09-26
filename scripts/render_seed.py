#!/usr/bin/env python3
"""18.EL.03 - render the tracked seed's identity tokens from .env.

`env/bin/python scripts/render_seed.py --out <dir>`

`seed/*.sql` holds user 1's name and email as `{{INITIAL_USER_NAME}}` and `{{INITIAL_USER_EMAIL}}`, so no real
identity is tracked. `render_seed()` replaces each token with a value from `.env`, or with the public default
when the variable is unset, empty, or an unfilled `%%...%%` placeholder. `scripts/resetdb.py --seed` applies the
rendered text. Run as a script, it writes the rendered files to `--out` for inspection. The values themselves are
never printed.
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import sys

from dotenv import dotenv_values

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_SCRIPTS_DIR)
SEED_DIR = os.path.join(_REPO_ROOT, "seed")
TOKEN = re.compile(r"\{\{([A-Z_]+)\}\}")
PUBLIC_DEFAULTS = {"INITIAL_USER_NAME": "Demo User", "INITIAL_USER_EMAIL": "demo.user@example.test"}
ENV_SOURCE, DEFAULT_SOURCE = ".env", "public default"


def _normalize(name: str, value: str) -> str:
    """The email column requires lower case (schema CHECK), so an email value is stored lowercased."""
    return value.lower() if name.endswith("_EMAIL") else value


def values_from_env() -> tuple[dict[str, str], str]:
    """The identity values and their source label. An unset, empty, or `%%` value falls back per variable.

    `.env` is read with `dotenv_values`, which leaves `os.environ` untouched, and a variable already in the
    environment takes precedence over the file. `load_dotenv` here re-added keys the test suite removes on
    purpose, such as MCF_MODE, per 18.IS.03.
    """
    file_values = dotenv_values(os.path.join(_REPO_ROOT, ".env"))
    values, from_env = {}, False
    for name, default in PUBLIC_DEFAULTS.items():
        raw = os.environ.get(name, file_values.get(name) or "").strip()
        if raw and not raw.startswith("%%"):
            values[name], from_env = _normalize(name, raw), True
        else:
            values[name] = default
    return values, ENV_SOURCE if from_env else DEFAULT_SOURCE


def _escape(value: str) -> str:
    """Tokens sit inside single-quoted SQL literals, so a quote in a value is doubled."""
    return value.replace("'", "''")


def render_text(text: str, values: dict[str, str], label: str = "<text>") -> str:
    """Replace every `{{NAME}}` token in one seed text. Raises on a token with no value."""
    def replace(match: re.Match) -> str:
        name = match.group(1)
        if name not in values:
            raise ValueError(f"{label}: no value for token {{{{{name}}}}}")
        return _escape(_normalize(name, values[name]))
    return TOKEN.sub(replace, text)


def render_seed(values: dict[str, str], seed_dir: str = SEED_DIR) -> list[tuple[str, str]]:
    """(file name, rendered SQL) for every `*.sql` in `seed_dir`, sorted. Validates all values before rendering."""
    for name, value in values.items():
        if not value or not value.strip():
            raise ValueError(f"empty value for {name}")
    rendered = []
    for path in sorted(glob.glob(os.path.join(seed_dir, "*.sql"))):
        with open(path, encoding="utf-8") as handle:
            rendered.append((os.path.basename(path), render_text(handle.read(), values, os.path.basename(path))))
    return rendered


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", required=True, help="directory for the rendered files, outside the tracked tree")
    args = parser.parse_args()
    values, source = values_from_env()
    try:
        rendered = render_seed(values)
    except ValueError as exc:
        print(f"[FAIL] seed render: {exc}", file=sys.stderr)
        return 1
    os.makedirs(args.out, exist_ok=True)
    for name, text in rendered:
        with open(os.path.join(args.out, name), "w", encoding="utf-8") as handle:
            handle.write(text)
    print(f"[PASS] seed rendered - {len(rendered)} files, identity from {source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
