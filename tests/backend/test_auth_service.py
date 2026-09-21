"""13.TC.01 to .06 and .29 to .32 - accounts, sessions, the password policy, and the sign-in rate limit.

Oracles with hard-coded expectations from the Design section. The service functions are called directly against
`fixed_clock` where a boundary depends on time, and the HTTP cases go through the real sign-in endpoint.
"""

from __future__ import annotations

import sqlite3

import pytest

from easymcf.api.db import get_db  # noqa: F401  (import check)
from easymcf.auth import passwords, ratelimit, sessions
from easymcf.config import Config
from easymcf.errors import TooManyAttempts

pytestmark = pytest.mark.backend

GOOD = "Abcdefgh1!xy"  # 12 characters, every character class, no identity


@pytest.fixture()
def config(isolated_db):
    return Config(db_path=isolated_db)


@pytest.fixture()
def anon(config):
    """A signed-out client on a private database, since these tests create accounts and sessions."""
    from easymcf import create_app

    return create_app(config).test_client()


@pytest.fixture()
def db(isolated_db):
    connection = sqlite3.connect(isolated_db)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    yield connection
    connection.close()


# 13.TC.29 - the password policy, each rule alone and both length boundaries
def test_password_length_boundaries():
    assert passwords.unmet_rules(GOOD, "z@example.test", "Q", 12) == []
    assert passwords.unmet_rules(GOOD[:-1], "z@example.test", "Q", 12) == ["too_short"]
    assert passwords.unmet_rules("Aa1!" + "x" * 124, "z@example.test", "Q", 12) == []
    assert passwords.unmet_rules("Aa1!" + "x" * 125, "z@example.test", "Q", 12) == ["too_long"]


@pytest.mark.parametrize("password, code", [
    ("ABCDEFGH1!XY", "no_lowercase"),
    ("abcdefgh1!xy", "no_uppercase"),
    ("Abcdefghi!xy", "no_digit"),
    ("Abcdefgh1234", "no_symbol"),
])
def test_each_character_class_alone(password, code):
    assert passwords.unmet_rules(password, "z@example.test", "Q", 12) == [code]


def test_identity_rule_and_its_length_threshold():
    assert passwords.unmet_rules("Xcasey.case1!Abc", "casey.case@example.test", "Q", 12) == ["contains_identity"]
    assert passwords.unmet_rules("Xcasey.CASE1!Abc", "casey.case@example.test", "Q", 12) == ["contains_identity"]
    assert passwords.unmet_rules("X-samsecond-9!", "z@example.test", "Sam Second", 12) == ["contains_identity"]
    assert passwords.unmet_rules("Xabc-Abcdef1!", "abc@example.test", "Q", 12) == []          # a 3 character local part is ignored


def test_several_unmet_rules_are_reported_together_in_table_order():
    assert passwords.unmet_rules("short", "z@example.test", "Q", 12) == ["too_short", "no_uppercase", "no_digit", "no_symbol"]


def test_hash_is_scrypt_and_salted():
    first, second = passwords.hash_password(GOOD), passwords.hash_password(GOOD)
    assert first.startswith("scrypt:") and first != second
    assert passwords.verify(first, GOOD) and not passwords.verify(first, "wrong")
    assert not passwords.verify(None, GOOD)


# 13.TC.30 and 13.TC.31 - the cookie and the session lifetime
def test_session_expires_on_the_boundary(db, config, fixed_clock):
    fixed_clock("2026-09-15T07:00:00")
    cookie = sessions.create(db, config, 1)
    db.commit()
    fixed_clock("2026-09-29T06:59:59")  # the lifetime is 336 hours
    assert sessions.resolve(db, config, cookie) == 1
    fixed_clock("2026-09-29T07:00:00")
    assert sessions.resolve(db, config, cookie) is None


def test_tampered_cookie_is_treated_as_none(db, config):
    cookie = sessions.create(db, config, 1)
    assert sessions.resolve(db, config, cookie[:-2] + "xx") is None
    assert sessions.resolve(db, config, "not-a-cookie") is None
    assert sessions.resolve(db, config, None) is None


def test_database_holds_a_digest_and_not_a_usable_cookie(db, config):
    cookie = sessions.create(db, config, 1)
    db.commit()
    token_hash = db.execute("SELECT token_hash FROM auth_session ORDER BY id DESC LIMIT 1").fetchone()[0]
    assert len(token_hash) == 64 and token_hash not in cookie
    assert sessions.resolve(db, config, token_hash) is None


def test_cookie_attributes(anon):
    response = anon.post("/api/v1/auth/signin", json={"email": "yayfalafels@gmail.com", "password": "Seed-Password-1!"})
    header = response.headers["Set-Cookie"]
    assert header.startswith("easymcf_session=") and "HttpOnly" in header and "SameSite=Lax" in header and "Path=/" in header


# 13.TC.32 - the rate limit, failures one to five give 401 and attempt six gives 429
def test_rate_limit_boundary(config, fixed_clock):
    fixed_clock("2026-09-15T07:00:00")
    for _ in range(5):
        ratelimit.check("a@example.test", config)
        ratelimit.record_failure("a@example.test", config)
    with pytest.raises(TooManyAttempts) as raised:
        ratelimit.check("a@example.test", config)
    assert raised.value.extra["retry_after"] == 901
    fixed_clock("2026-09-15T07:15:01")  # the oldest failure is now 901 seconds old
    ratelimit.check("a@example.test", config)


def test_sixth_attempt_over_http_is_429_even_with_the_right_password(anon):
    creds = {"email": "yayfalafels@gmail.com", "password": "Wrong-Password-1!"}
    for _ in range(5):
        assert anon.post("/api/v1/auth/signin", json=creds).status_code == 401
    refused = anon.post("/api/v1/auth/signin", json={**creds, "password": "Seed-Password-1!"})
    assert refused.status_code == 429 and int(refused.headers["Retry-After"]) > 0
    assert refused.get_json()["error"] == "too_many_attempts"


# 13.TC.01 to .06 - the account round trip
SIGNUP = {"name": "Casey Case", "email": "casey@example.test", "password": "Correct-Horse-9!"}


def test_sign_up_sign_out_sign_in_round_trip(anon, db):
    created = anon.post("/api/v1/auth/signup", json=SIGNUP)
    body = created.get_json()
    assert created.status_code == 201 and "password_hash" not in body and body["auth_methods"] == ["password"]
    assert "easymcf_session" in created.headers["Set-Cookie"]
    assert anon.get("/api/v1/auth/me").get_json()["email"] == "casey@example.test"
    stored = db.execute("SELECT password_hash FROM user WHERE email = 'casey@example.test'").fetchone()[0]
    assert stored.startswith("scrypt:") and SIGNUP["password"] not in stored
    assert db.execute("SELECT status FROM mcf_session WHERE user_id = ?", (body["id"],)).fetchone()[0] == "missing"
    assert anon.post("/api/v1/auth/signout").status_code == 204
    assert anon.get("/api/v1/auth/me").status_code == 401
    assert anon.post("/api/v1/auth/signin", json={"email": "CASEY@example.test", "password": SIGNUP["password"]}).status_code == 200
    assert anon.get("/api/v1/auth/me").status_code == 200


def test_duplicate_email_ignores_case(anon):
    assert anon.post("/api/v1/auth/signup", json={**SIGNUP, "email": "YAYFALAFELS@gmail.com"}).status_code == 409
    assert anon.post("/api/v1/auth/signup", json={**SIGNUP, "email": "yayfalafels@gmail.com"}).get_json()["field"] == "email"


def test_sign_up_validation(anon):
    assert anon.post("/api/v1/auth/signup", json={**SIGNUP, "email": "not-an-email"}).get_json()["field"] == "email"
    weak = anon.post("/api/v1/auth/signup", json={**SIGNUP, "password": "short"})
    assert weak.status_code == 400 and weak.get_json()["rules"] == ["too_short", "no_uppercase", "no_digit", "no_symbol"]
    assert anon.post("/api/v1/auth/signup", json={**SIGNUP, "name": "   "}).get_json()["field"] == "name"
    assert anon.post("/api/v1/auth/signup", json={**SIGNUP, "user_id": 3}).status_code == 400


def test_failures_share_one_status_and_body(anon):
    wrong = anon.post("/api/v1/auth/signin", json={"email": "yayfalafels@gmail.com", "password": "Wrong-Password-1!"})
    unknown = anon.post("/api/v1/auth/signin", json={"email": "nobody@example.test", "password": "Wrong-Password-1!"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.get_json() == unknown.get_json() == {"error": "invalid_credentials", "message": "Email or password is incorrect."}


def test_google_only_account_gets_the_same_failure(anon, isolated_db):
    conn = sqlite3.connect(isolated_db)
    conn.execute("INSERT INTO user (name, email, status, google_sub, created_at) VALUES ('G', 'g-only@example.test', 'active', 'sub-x', '2026-01-01 00:00:00')")
    conn.commit()
    conn.close()
    failure = anon.post("/api/v1/auth/signin", json={"email": "g-only@example.test", "password": "Correct-Horse-9!"})
    assert failure.status_code == 401 and failure.get_json()["error"] == "invalid_credentials"


def test_protected_routes_need_a_session_and_public_routes_do_not(anon):
    from easymcf.api.generic import REGISTRY

    for table in REGISTRY:
        assert anon.get(f"/api/v1/{table}/search").status_code == 401, table
    assert anon.get("/api/v1/no-such-route").status_code == 401
    assert anon.get("/api/v1/health").status_code == 200
    assert anon.get("/api/v1/auth/config").status_code == 200
    assert anon.post("/api/v1/auth/signout").status_code == 204


def test_cross_site_write_is_refused(anon):
    anon.post("/api/v1/auth/signin", json={"email": "yayfalafels@gmail.com", "password": "Seed-Password-1!"})
    client = anon
    refused = client.post("/api/v1/auth/signout", headers={"Origin": "http://evil.example"})
    assert refused.status_code == 403 and refused.get_json()["error"] == "forbidden_origin"
    assert client.post("/api/v1/auth/signout", headers={"Origin": "http://localhost"}).status_code == 204


def test_disabled_account_cannot_sign_in(anon, isolated_db):
    conn = sqlite3.connect(isolated_db)
    conn.execute("UPDATE user SET status = 'disabled' WHERE id = 2")
    conn.commit()
    try:
        failure = anon.post("/api/v1/auth/signin", json={"email": "second.user@example.test", "password": "Seed-Password-2!"})
        assert failure.status_code == 401
    finally:
        conn.execute("UPDATE user SET status = 'active' WHERE id = 2")
        conn.commit()
        conn.close()
