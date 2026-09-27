# Configure

## Contents

- [Required settings](#required-settings)
- [Google OAuth](#google-oauth)
- [Local database reset](#local-database-reset)
- [Configuration problems](#configuration-problems)

All settings have defaults, so `.env` is optional for a normal development run. The app and CLI scripts load `.env` when it exists. Keep private credentials in `.secrets/`, which is excluded from git.

## Required settings

For developer work and unattended validation, use fixture mode:

```dotenv
MCF_MODE=fixture
```

Job seekers use live mode for real MyCareersFuture searches. An apply run that submits real applications additionally requires `APPLY_LIVE_SUBMIT=1`. Treat both settings as a deliberate human choice. Review `.env` before starting the app, especially if the file was copied from `.env.example`, which contains the explicit apply-submit setting.

`INITIAL_USER_NAME` and `INITIAL_USER_EMAIL` change the identity used by the next seeded database reset. They do not rename an account in an existing database. See [Local database reset](#local-database-reset) before changing them.

The tracked `.env.example` lists the complete configuration surface. Copy it only when you need overrides, then edit the values you intend to change.

## Google OAuth

Google sign-in is optional. It appears on the sign-in page only when both the client ID and secret file are present.

1. Register a Google OAuth client for the loopback app and add its client ID as `GCP_OAUTH_CLIENT_ID` in `.env`.
2. Set `GOOGLE_REDIRECT_URI` to the callback URL registered with Google. By default it is `http://127.0.0.1:5000/api/v1/auth/google/callback`; change the port in both places if the app uses a different port.
3. Store the client secret in `.secrets/gcp_oauth_client_secret`, not in `.env` or a tracked file. Restrict it with `chmod 600 .secrets/gcp_oauth_client_secret`.
4. Run `env/bin/python scripts/envcheck.py`. It reports a missing client secret or unsafe file permissions.

If the Google button does not appear, confirm both the client ID and secret file are configured, then reload the sign-in page. If Google returns an OAuth error, check that its registered redirect URI exactly matches `GOOGLE_REDIRECT_URI`, including scheme, host, port, and path. Email/password sign-in remains available without Google OAuth.

## Local database reset

```bash
env/bin/python scripts/resetdb.py --seed
```

This command deletes and recreates the configured database, then applies the schema and seed records. It is destructive; use it only when you can discard the current data. The initial account identity is rendered from `INITIAL_USER_NAME` and `INITIAL_USER_EMAIL` at reset time. Seeded MCF session records are examples and do not establish a real MCF connection.

To reset and restart in one step, set `MCF_MODE=fixture` in `.env` and run `./scripts/restart.sh --reset-seed`. The helper reads the mode from `.env`, stops only a verified Easy MCF process on the configured port, resets the database, and starts the app. Use `./scripts/restart.sh` without the flag to restart while preserving the database.

## Configuration problems

- **The app refuses to start with an invalid MCF mode.** Set `MCF_MODE` to `fixture` for developer work or to `live` only for a deliberate human-run.
- **A live apply run is refused.** Live submission needs both `MCF_MODE=live` and `APPLY_LIVE_SUBMIT=1`. Confirm that live submission is intended before enabling it.
- **The seeded name or email did not change.** Those values are applied only by `scripts/resetdb.py --seed`; changing them does not modify the existing user record.
- **The restart helper refuses to start.** It requires `.env` to contain exactly `MCF_MODE=fixture` or `MCF_MODE=live`. If the port belongs to another process, choose a free port instead of terminating an unrelated service.
