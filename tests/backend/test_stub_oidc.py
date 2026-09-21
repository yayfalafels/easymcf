"""13.EL.08 self-test - the stub provider behaves as ARCH-AUTH-10 describes, checked with plain HTTP and Authlib's own decoder."""

from __future__ import annotations

import base64
import hashlib
import time
from urllib.parse import parse_qs, urlparse

import pytest
import requests
from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import KeySet

from tests.support import stub_oidc

pytestmark = pytest.mark.backend


@pytest.fixture(scope="module")
def stub():
    server, base_url = stub_oidc.serve()
    yield base_url
    server.shutdown()


def _code_flow(base_url: str, email: str, decision: str = "approve"):
    verifier = "v" * 43
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    params = {"client_id": stub_oidc.CLIENT_ID, "redirect_uri": "http://app.test/cb", "state": "st", "nonce": "no", "code_challenge": challenge}
    consent = requests.get(base_url + "/authorize", params=params)
    assert consent.status_code == 200 and 'data-testid="stub-approve"' in consent.text
    approve = requests.post(base_url + "/authorize", data={**params, "email": email, "decision": decision}, allow_redirects=False)
    return approve, verifier


def _claims(base_url: str, token: str):
    keys = KeySet.import_key_set(requests.get(base_url + "/jwks").json())
    return jwt.decode(token, keys).claims


def test_discovery_lists_the_endpoints(stub):
    doc = requests.get(stub + "/.well-known/openid-configuration").json()
    assert doc["issuer"] == stub and doc["token_endpoint"] == stub + "/token" and doc["jwks_uri"] == stub + "/jwks"
    assert doc["code_challenge_methods_supported"] == ["S256"]


def test_valid_identity_round_trip_with_pkce(stub):
    approve, verifier = _code_flow(stub, "casey.case@example.test")
    query = parse_qs(urlparse(approve.headers["Location"]).query)
    assert approve.status_code == 302 and query["state"] == ["st"]
    token = requests.post(stub + "/token", data={"code": query["code"][0], "code_verifier": verifier}).json()
    claims = _claims(stub, token["id_token"])
    assert claims["iat"] <= int(time.time()) < claims["exp"]
    assert claims["iss"] == stub and claims["aud"] == stub_oidc.CLIENT_ID and claims["nonce"] == "no"
    assert claims["email"] == "casey.case@example.test" and claims["email_verified"] is True
    assert requests.get(claims["picture"]).headers["Content-Type"] == "image/png"


def test_wrong_verifier_is_refused_and_a_code_is_single_use(stub):
    approve, verifier = _code_flow(stub, "casey.case@example.test")
    code = parse_qs(urlparse(approve.headers["Location"]).query)["code"][0]
    assert requests.post(stub + "/token", data={"code": code, "code_verifier": "x" * 43}).status_code == 400
    assert requests.post(stub + "/token", data={"code": code, "code_verifier": verifier}).status_code == 400


def test_denied_consent_redirects_with_access_denied(stub):
    approve, _ = _code_flow(stub, "casey.case@example.test", decision="deny")
    assert parse_qs(urlparse(approve.headers["Location"]).query) == {"error": ["access_denied"], "state": ["st"]}


@pytest.mark.parametrize("prefix, check", [
    ("unverified", lambda c, b: c["email_verified"] is False),
    ("expired", lambda c, b: c["exp"] < int(time.time()) - 600),
    ("badaud", lambda c, b: c["aud"] == "another-client"),
    ("badiss", lambda c, b: c["iss"] != b),
    ("badnonce", lambda c, b: c["nonce"] == "wrong-nonce"),
])
def test_claim_scenarios(stub, prefix, check):
    approve, verifier = _code_flow(stub, f"{prefix}.user@example.test")
    code = parse_qs(urlparse(approve.headers["Location"]).query)["code"][0]
    token = requests.post(stub + "/token", data={"code": code, "code_verifier": verifier}).json()["id_token"]
    assert check(_claims(stub, token), stub)


def test_badsig_token_fails_signature_verification(stub):
    approve, verifier = _code_flow(stub, "badsig.user@example.test")
    code = parse_qs(urlparse(approve.headers["Location"]).query)["code"][0]
    token = requests.post(stub + "/token", data={"code": code, "code_verifier": verifier}).json()["id_token"]
    with pytest.raises(JoseError):
        _claims(stub, token)


def test_badstate_returns_a_different_state(stub):
    approve, _ = _code_flow(stub, "badstate.user@example.test")
    assert parse_qs(urlparse(approve.headers["Location"]).query)["state"] == ["stx"]
