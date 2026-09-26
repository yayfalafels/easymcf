"""REQ-AUTH-03 - the sign-in failure counter (ARCH-AUTH-09). Time comes from clock.now()."""

from __future__ import annotations

import threading
from datetime import timedelta

from .. import clock
from ..errors import TooManyAttempts

_failures: dict[str, list] = {}
_lock = threading.Lock()


def _live(email: str, config) -> list:
    cutoff = clock.now() - timedelta(seconds=config.signin_window_s)
    _failures[email] = [t for t in _failures.get(email, []) if t > cutoff]
    return _failures[email]


def check(email: str, config) -> None:
    with _lock:
        recent = _live(email, config)
        if len(recent) >= config.signin_max_failures:
            wait = int((recent[0] + timedelta(seconds=config.signin_window_s) - clock.now()).total_seconds()) + 1
            raise TooManyAttempts("Too many failed sign-in attempts. Try again later.", retry_after=max(wait, 1))


def record_failure(email: str, config) -> None:
    with _lock:
        _live(email, config).append(clock.now())


def clear(email: str) -> None:
    with _lock:
        _failures.pop(email, None)


def reset() -> None:
    with _lock:
        _failures.clear()
