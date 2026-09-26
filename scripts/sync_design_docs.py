#!/usr/bin/env python3
"""18.EL.27 - generate docs/design/ from the current release's design docs.

`.dev/dev-env/bin/python scripts/sync_design_docs.py [--check]`

The release is `extra.design_release` in mkdocs.yml. Each doc in DESIGN_DOCS is copied from
`docs/releases/<release>/design/<release>-<source>.md` to `docs/design/<name>.md`, so the published design
section keeps no release prefix and no link back to the release folder. Relative links are rewritten: a link to
another synced doc points at its published name, with a release file name in its link text renamed to match, and
a link to anything else becomes its plain link text. A relative link whose target does not exist fails the sync.
The default mode writes the pages and removes any other .md file in docs/design/. `--check` compares instead,
and fails when docs/design/ is stale, which scripts/build_docs.sh runs before every build.
"""

from __future__ import annotations

import argparse
import glob
import os
import re

import yaml

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(_SCRIPTS_DIR)
DESIGN_DIR = os.path.join(REPO_ROOT, "docs", "design")
# published name -> source file suffix, after the `<release>-` prefix
DESIGN_DOCS = {
    "requirements": "01-requirements", "architecture": "architecture", "data-model": "data-model", "api": "api",
    "workflows": "workflows", "user-interface": "user-interface", "frontend-app": "frontend-app",
    "development-env": "development-env", "prototype": "prototype",
}
LINK = re.compile(r"\[([^\]]*)\]\(([^)\s]+)\)")
EXTERNAL = re.compile(r"^(#|[a-z][a-z0-9+.-]*:|/)", re.I)


class _ConfigLoader(yaml.SafeLoader):
    """mkdocs.yml holds `!!python/...` tags for MkDocs itself. They are read here as plain data, never executed."""


_ConfigLoader.add_multi_constructor("tag:yaml.org,2002:python/", lambda loader, suffix, node: None)


def current_release() -> str:
    with open(os.path.join(REPO_ROOT, "mkdocs.yml"), encoding="utf-8") as handle:
        return str(yaml.load(handle, Loader=_ConfigLoader)["extra"]["design_release"])


def source_path(release: str, name: str) -> str:
    return os.path.join(REPO_ROOT, "docs", "releases", release, "design", f"{release}-{DESIGN_DOCS[name]}.md")


def rewrite_link(match: re.Match, source: str, published: dict[str, str], release: str, errors: list[str]) -> str:
    text, target = match.group(1), match.group(2)
    if EXTERNAL.match(target):
        return match.group(0)
    path, _, anchor = target.partition("#")
    resolved = os.path.normpath(os.path.join(os.path.dirname(source), path))
    if not os.path.exists(resolved):
        errors.append(f"{os.path.relpath(source, REPO_ROOT)}: link target not found: {target}")
        return match.group(0)
    if resolved not in published:
        return text  # outside the design section: the reference name stays, the link goes
    name = published[resolved]
    for suffix in DESIGN_DOCS.values():  # a release file name in the link text takes the published name
        text = text.replace(f"{release}-{suffix}.md", DESIGN_DOCS_BY_SUFFIX[suffix] + ".md")
    return f"[{text}]({name}{'#' + anchor if anchor else ''})"


DESIGN_DOCS_BY_SUFFIX = {suffix: name for name, suffix in DESIGN_DOCS.items()}


def build_page(release: str, name: str, published: dict[str, str], errors: list[str]) -> str:
    source = source_path(release, name)
    with open(source, encoding="utf-8") as handle:
        lines = handle.read().split("\n")
    out, in_fence = [], False
    for line in lines:
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        if not in_fence:
            line = LINK.sub(lambda m: rewrite_link(m, source, published, release, errors), line)
        out.append(line)
    return "\n".join(out)


def build_pages(release: str) -> tuple[dict[str, str], list[str]]:
    published = {os.path.normpath(source_path(release, name)): f"{name}.md" for name in DESIGN_DOCS}
    errors = [f"missing source: {os.path.relpath(p, REPO_ROOT)}" for p in published if not os.path.isfile(p)]
    if errors:
        return {}, errors
    return {f"{name}.md": build_page(release, name, published, errors) for name in DESIGN_DOCS}, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="compare with docs/design/ instead of writing")
    args = parser.parse_args()
    release = current_release()
    pages, errors = build_pages(release)
    if errors:
        for error in errors:
            print(f"[FAIL] {error}")
        return 1
    existing = {os.path.basename(p) for p in glob.glob(os.path.join(DESIGN_DIR, "*.md"))}
    if args.check:
        problems = [f"extra: {n}" for n in sorted(existing - pages.keys())]
        for name, text in pages.items():
            path = os.path.join(DESIGN_DIR, name)
            if name not in existing:
                problems.append(f"missing: {name}")
            elif open(path, encoding="utf-8").read() != text:
                problems.append(f"stale: {name}")
        for problem in problems:
            print(f"[FAIL] design docs {problem}")
        if problems:
            print("[FAIL] design docs out of sync, run scripts/sync_design_docs.py")
            return 1
        print(f"[PASS] design docs in sync with release {release}")
        return 0
    os.makedirs(DESIGN_DIR, exist_ok=True)
    for name in sorted(existing - pages.keys()):
        os.remove(os.path.join(DESIGN_DIR, name))
    for name, text in pages.items():
        with open(os.path.join(DESIGN_DIR, name), "w", encoding="utf-8") as handle:
            handle.write(text)
    print(f"[PASS] design docs synced from {release} - {len(pages)} pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
