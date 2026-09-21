"""Stub OpenID Connect provider (13.EL.08, ARCH-AUTH-10). Fake credentials, a key generated at startup, no network.

Run standalone:   env/bin/python -m tests.support.stub_oidc --port 5556
In a fixture:     server, base_url = stub_oidc.serve()   ...   server.shutdown()

The local part prefix of the email entered on the consent page selects the scenario:
unverified, expired, badaud, badiss, badsig, badnonce, badstate. Any other prefix is a valid identity.
"""

from __future__ import annotations

import base64
import hashlib
import html
import secrets
import threading
import time
from urllib.parse import urlencode

from joserfc import jwt
from joserfc.jwk import RSAKey
from flask import Flask, jsonify, redirect, request
from werkzeug.serving import make_server

CLIENT_ID, CLIENT_SECRET = "stub-client-id", "stub-client-secret"
KEY = RSAKey.generate_key(2048, parameters={"kid": "stub"})
OTHER_KEY = RSAKey.generate_key(2048, parameters={"kid": "other"})
SCENARIOS = ("unverified", "expired", "badaud", "badiss", "badsig", "badnonce", "badstate")

# A fixed valid 1 by 1 PNG.
_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)
_codes: dict[str, dict] = {}


def _consent_page(args) -> str:
    hidden = "".join(
        f'<input type="hidden" name="{name}" value="{html.escape(args.get(name, ""))}">'
        for name in ("client_id", "redirect_uri", "state", "nonce", "code_challenge")
    )
    return (
        "<!doctype html><title>Stub consent</title><form method=\"post\">"
        f"{hidden}<label>Email <input name=\"email\" data-testid=\"stub-email\"></label>"
        "<button name=\"decision\" value=\"approve\" data-testid=\"stub-approve\">Approve</button>"
        "<button name=\"decision\" value=\"deny\" data-testid=\"stub-deny\">Deny</button></form>"
    )


def _id_token(base_url: str, email: str, nonce: str) -> str:
    scenario = email.split("@")[0].split(".")[0]
    now = int(time.time())
    claims = {
        "iss": "https://other.example.test" if scenario == "badiss" else base_url,
        "aud": "another-client" if scenario == "badaud" else CLIENT_ID,
        "sub": "stub-sub-" + hashlib.sha1(email.encode()).hexdigest()[:12],
        "iat": now,
        "exp": now - 3600 if scenario == "expired" else now + 3600,
        "nonce": "wrong-nonce" if scenario == "badnonce" else nonce,
        "email": email,
        "email_verified": scenario != "unverified",
        "name": email.split("@")[0].replace(".", " ").title(),
        "picture": f"{base_url}/picture/{scenario}.png",
    }
    key = OTHER_KEY if scenario == "badsig" else KEY
    return jwt.encode({"alg": "RS256", "kid": key.kid}, claims, key)


def register(app: Flask, base_url: str) -> None:
    @app.get("/.well-known/openid-configuration")
    def discovery():
        return jsonify(
            issuer=base_url, authorization_endpoint=f"{base_url}/authorize", token_endpoint=f"{base_url}/token",
            jwks_uri=f"{base_url}/jwks", response_types_supported=["code"], subject_types_supported=["public"],
            id_token_signing_alg_values_supported=["RS256"], code_challenge_methods_supported=["S256"],
            token_endpoint_auth_methods_supported=["client_secret_post", "client_secret_basic"],
        )

    @app.get("/jwks")
    def jwks():
        return jsonify({"keys": [KEY.as_dict(private=False) | {"alg": "RS256", "use": "sig"}]})

    @app.route("/authorize", methods=["GET", "POST"])
    def authorize():
        args = request.values
        if request.method == "GET":
            return _consent_page(args)
        if args.get("decision") == "deny":
            return redirect(f"{args['redirect_uri']}?{urlencode({'error': 'access_denied', 'state': args['state']})}")
        email = args["email"].strip().lower()
        code = secrets.token_urlsafe(16)
        _codes[code] = {"email": email, "nonce": args["nonce"], "challenge": args["code_challenge"]}
        state = args["state"] + "x" if email.startswith("badstate") else args["state"]
        return redirect(f"{args['redirect_uri']}?{urlencode({'code': code, 'state': state})}")

    @app.post("/token")
    def token():
        entry = _codes.pop(request.form.get("code", ""), None)
        digest = hashlib.sha256(request.form.get("code_verifier", "").encode()).digest()
        challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
        if entry is None or challenge != entry["challenge"]:
            return jsonify(error="invalid_grant"), 400
        return jsonify(
            access_token=secrets.token_urlsafe(8), token_type="Bearer", expires_in=3600,
            id_token=_id_token(base_url, entry["email"], entry["nonce"]),
        )

    @app.get("/picture/<name>.png")
    def picture(name):
        return _PNG, 200, {"Content-Type": "image/png"}


def serve(port: int = 0):
    """Start in a daemon thread. Returns (server, base_url). Call server.shutdown() to stop."""
    app = Flask(__name__)
    server = make_server("127.0.0.1", port, app)
    base_url = f"http://127.0.0.1:{server.server_port}"
    register(app, base_url)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, base_url


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=5556)
    server, url = serve(parser.parse_args().port)
    print(f"[PASS] stub provider at {url}/.well-known/openid-configuration", flush=True)
    threading.Event().wait()
