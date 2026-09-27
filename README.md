# Easy MCF

Easy MCF helps job seekers in Singapore track MyCareersFuture roles, manage their lead pipeline, and automate batch follow-up from a local app. The project keeps all data on the user's own machine, with a Flask API, SQLite store, and AngularJS frontend served from the same origin.

Current version: `0.1.0`

## Documentation site

- Site: https://yayfalafels.github.io/easymcf/
- Release notes: [docs/releases/010/010-release.md](docs/releases/010/010-release.md)

## Quick start

1. Follow the install steps in [docs/developer-guide/index.md](docs/developer-guide/index.md).
2. Create the local environment and seed database with `scripts/resetdb.py --seed`.
3. Start the app with `python -m easymcf` and open http://127.0.0.1:5000.
4. Use the user guide under [docs/user-guide/index.md](docs/user-guide/index.md) for searching, leads, and applying.

## Scope in release 010

This release covers the local development environment, seeded schema data, validation tooling, lead tracking, OAuth login, MCF session handling, keyword search, and automated apply flows.