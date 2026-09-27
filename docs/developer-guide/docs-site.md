# Docs site

## Contents

- [Local site build](#local-site-build)
- [Local preview](#local-preview)
- [Fix a failed build](#fix-a-failed-build)
- [Manual publish fallback](#manual-publish-fallback)

The site uses MkDocs with Material for MkDocs. Documentation dependencies live in `.dev/dev-env`; the build does not use the app's operational environment. Run all commands from the repository root.

## Local site build

```bash
./scripts/build_docs.sh
```

The strict build runs `scripts/sync_design_docs.py --check`, builds the `docs/` tree with `mkdocs build --strict`, and fails on warnings or links to excluded pages. Treat a successful command as the required docs validation result.

## Local preview

```bash
NO_MKDOCS_2_WARNING=1 .dev/dev-env/bin/mkdocs serve -a 127.0.0.1:8000
```

Open http://127.0.0.1:8000/easymcf/ to preview the site. Keep the command running while previewing and stop it with `Ctrl+C`. If port 8000 is already in use, choose another local port, such as `-a 127.0.0.1:8001`, and use that port in the URL.

## Fix a failed build

1. If the design-sync check reports stale pages, edit the source document under `docs/releases/<release>/design/`, then regenerate the published copies with `env/bin/python scripts/sync_design_docs.py`. Do not make the only copy of a design change in `docs/design/`.
2. If MkDocs reports a broken link, check the target path and anchor. Links must point to files included in the published site; repository files such as `.env.example` are not published docs pages.
3. If the `mkdocs` command is missing, install or sync the developer tools from `python-envs/dev-env/pyproject.toml` into `.dev/dev-env` as described in [Install](index.md).
4. Re-run `./scripts/build_docs.sh` and resolve every warning before publishing.

## Manual publish fallback

The normal release path is the GitHub Pages Actions workflow. Use the manual fallback only when that workflow is unavailable and you are authorized to publish. This command pushes generated documentation to the `gh-pages` branch:

```bash
NO_MKDOCS_2_WARNING=1 .dev/dev-env/bin/mkdocs gh-deploy --strict --force
```

Review the repository and worktree state before running the command. The repository's GitHub Pages setting should point to the Actions build for the release site; coordinate any manual fallback with the maintainer so the branch and Pages source do not conflict.
