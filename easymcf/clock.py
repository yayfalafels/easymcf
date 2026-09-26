"""ARCH-STO-05 — every application read of the current time goes through now()."""

from __future__ import annotations

import os
from datetime import date, datetime

_fixed: datetime | None = None


def now() -> datetime:
    if _fixed is not None:
        return _fixed
    pinned = os.environ.get("FIXED_NOW")
    if pinned:
        return datetime.fromisoformat(pinned)
    return datetime.now().replace(microsecond=0)


def today() -> date:
    return now().date()


def stamp(value: datetime | None = None) -> str:
    return (value or now()).strftime("%Y-%m-%d %H:%M:%S")


def set_fixed(value: datetime | None) -> None:
    global _fixed
    _fixed = value
