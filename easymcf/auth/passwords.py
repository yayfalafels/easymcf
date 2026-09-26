"""REQ-AUTH-02, REQ-AUTH-09 - the password policy and scrypt hashing (ARCH-AUTH-01)."""

from __future__ import annotations

import re

from werkzeug.security import check_password_hash, generate_password_hash

MAX_LENGTH = 128
DUMMY_HASH = generate_password_hash("dummy-password-for-constant-time")


def unmet_rules(password: str, email: str, name: str, min_length: int) -> list[str]:
    """Every unmet rule code, in the order of the password policy table."""
    unmet = []
    if len(password) < min_length:
        unmet.append("too_short")
    if len(password) > MAX_LENGTH:
        unmet.append("too_long")
    if not any(c.islower() for c in password):
        unmet.append("no_lowercase")
    if not any(c.isupper() for c in password):
        unmet.append("no_uppercase")
    if not any(c.isdigit() for c in password):
        unmet.append("no_digit")
    if not any(not c.isalnum() and not c.isspace() for c in password):
        unmet.append("no_symbol")
    lowered, local = password.lower(), email.split("@")[0].lower()
    squashed = re.sub(r"\s+", "", name).lower()
    if (len(local) >= 4 and local in lowered) or (len(squashed) >= 4 and squashed in lowered):
        unmet.append("contains_identity")
    return unmet


def hash_password(password: str) -> str:
    return generate_password_hash(password)  # scrypt, stored with the "scrypt:" prefix


def verify(stored_hash: str | None, password: str) -> bool:
    """One hash verification in every case, so a missing account costs the same time as a wrong password."""
    ok = check_password_hash(stored_hash or DUMMY_HASH, password)
    return ok and stored_hash is not None
