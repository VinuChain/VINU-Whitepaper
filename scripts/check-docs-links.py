#!/usr/bin/env python3
"""Validate local Markdown links for the GitBook whitepaper."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse


ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
IMAGE_LINK_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
GITBOOK_EMBED_RE = re.compile(r'{%\s*embed\s+url="([^"]+)"\s*%}')
HTML_SRC_RE = re.compile(r'<(?:img|source)\b[^>]*\bsrc="([^"]+)"')


def is_external(target: str) -> bool:
    parsed = urlparse(target)
    return bool(parsed.scheme) or target.startswith(("mailto:", "tel:", "#"))


def strip_fragment_and_query(target: str) -> str:
    parsed = urlparse(target)
    return unquote(parsed.path)


def resolve_local_path(source: Path, target: str) -> Path:
    path_text = strip_fragment_and_query(target)
    if not path_text:
        return source

    candidate = (source.parent / path_text).resolve()
    try:
        candidate.relative_to(ROOT)
    except ValueError:
        raise ValueError(f"{target} resolves outside the repository")
    return candidate


def iter_markdown_files() -> list[Path]:
    return sorted(
        path
        for path in ROOT.rglob("*.md")
        if ".git" not in path.relative_to(ROOT).parts
    )


def check_links() -> list[str]:
    errors: list[str] = []
    markdown_files = iter_markdown_files()

    for source in markdown_files:
        text = source.read_text(encoding="utf-8")
        for pattern in (MARKDOWN_LINK_RE, IMAGE_LINK_RE, GITBOOK_EMBED_RE, HTML_SRC_RE):
            for match in pattern.finditer(text):
                target = match.group(1).strip()
                if is_external(target):
                    continue

                try:
                    resolved = resolve_local_path(source, target)
                except ValueError as exc:
                    errors.append(f"{source.relative_to(ROOT)}: {exc}")
                    continue

                if not resolved.exists():
                    errors.append(
                        f"{source.relative_to(ROOT)}: missing local target {target}"
                    )

    summary = ROOT / "SUMMARY.md"
    if summary.exists():
        linked_docs = set()
        for match in MARKDOWN_LINK_RE.finditer(summary.read_text(encoding="utf-8")):
            target = match.group(1).strip()
            if is_external(target):
                continue

            try:
                linked_docs.add(resolve_local_path(summary, target))
            except ValueError as exc:
                errors.append(f"{summary.relative_to(ROOT)}: {exc}")

        unlisted_docs = [
            path.relative_to(ROOT).as_posix()
            for path in markdown_files
            if path.name != "SUMMARY.md" and path.resolve() not in linked_docs
        ]
        if unlisted_docs:
            errors.append(
                "SUMMARY.md does not list: " + ", ".join(sorted(unlisted_docs))
            )

    return errors


def main() -> int:
    os.chdir(ROOT)
    errors = check_links()
    if errors:
        print("Docs link check failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("Docs link check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
