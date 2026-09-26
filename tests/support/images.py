"""Fixture image helpers (13.EL.07). The oversize image is built at test time so no 2 MiB binary is committed."""

from __future__ import annotations

import os

SUPPORT_DIR = os.path.dirname(os.path.abspath(__file__))


def path(name: str) -> str:
    return os.path.join(SUPPORT_DIR, name)


def make_oversize(limit_bytes: int, target: str) -> str:
    """Write a valid PNG padded with trailing zero bytes so its size is exactly limit_bytes + 1."""
    data = open(path("photo_ok.png"), "rb").read()
    with open(target, "wb") as handle:
        handle.write(data + b"\0" * (limit_bytes + 1 - len(data)))
    return target
