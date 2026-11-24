#!/usr/bin/env python3
"""Reject broken text encodings and build artifacts in the repository.

The usual damage is a UTF-8 file rewritten by a legacy Windows tool: a BOM at
the start, or UTF-8 bytes read as cp1251/Latin-1 (an em dash or a
multiplication sign turns into two Cyrillic letters). Those files still import,
so the mistake only shows up in a diff or a screenshot. This check turns it into
one line.

Usage:
    python tools/check_text.py
    python tools/check_text.py README.md node_atlas/

Without arguments it checks tracked files, so ``dist/`` and other ignored
outputs are skipped. Exit code 1 means at least one file needs attention.

The tool is development-only and uses the standard library only.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TEXT_SUFFIXES = {
    ".py", ".md", ".toml", ".ps1", ".psd1", ".json", ".yml", ".yaml",
    ".txt", ".cfg", ".ini", ".sh", ".bat", ".cmd", ".html", ".css", ".js",
}

MARKERS = {
    "\ufeff": "UTF-8 BOM",
    "\ufffd": "replacement character",
    "\u0432\u0402": "UTF-8 read as cp1251 (em dash)",
    "\u0413\u2014": "UTF-8 read as cp1251 (multiplication sign)",
    "\u00d0": "UTF-8 read as Latin-1",
    "\u00c2": "UTF-8 read as Latin-1",
}

ARTIFACTS = ("__pycache__/", ".pyc", ".blend1", ".tmp.png", "dist/")


def tracked_files() -> list[Path]:
    """Return tracked files, or every candidate below ROOT without git."""
    try:
        result = subprocess.run(
            ["git", "-C", str(ROOT), "ls-files", "-z", "--cached", "--others",
             "--exclude-standard"],
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return sorted(
            path for path in ROOT.rglob("*")
            if path.is_file()
            and ".git" not in path.parts
            and "dist" not in path.parts
        )
    names = [os.fsdecode(name) for name in result.stdout.split(b"\0") if name]
    return [ROOT / name for name in names]


def candidates(arguments: list[str]) -> list[Path]:
    if not arguments:
        return tracked_files()
    found: list[Path] = []
    for argument in arguments:
        path = Path(argument)
        if path.is_dir():
            found.extend(item for item in path.rglob("*") if item.is_file())
        else:
            found.append(path)
    return sorted(found)


def is_text(path: Path) -> bool:
    return path.suffix.lower() in TEXT_SUFFIXES or path.name in {
        ".gitignore", ".gitattributes", ".editorconfig",
    }


def check(path: Path) -> list[str]:
    problems: list[str] = []
    try:
        relative = path.resolve().relative_to(ROOT)
    except ValueError:
        relative = path
    for marker in ARTIFACTS:
        if marker in relative.as_posix():
            problems.append(f"{relative}: build artifact ({marker})")
            return problems
    if not is_text(path):
        return problems
    try:
        data = path.read_bytes()
    except OSError as exc:
        return [f"{relative}: cannot read: {exc}"]
    if b"\0" in data:
        return [f"{relative}: contains NUL bytes"]
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        return [f"{relative}: not UTF-8 at byte {exc.start}: {exc.reason}"]
    for number, line in enumerate(text.splitlines(), 1):
        for marker, reason in MARKERS.items():
            if marker in line:
                problems.append(f"{relative}:{number}: {reason}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check text files for BOM, broken UTF-8 and generated artifacts.",
    )
    parser.add_argument("paths", nargs="*", help="files or folders; default: git ls-files")
    args = parser.parse_args(argv)

    problems: list[str] = []
    files = candidates(args.paths)
    for path in files:
        problems.extend(check(path))
    if problems:
        for problem in problems:
            print(problem)
        print(f"{len(problems)} problem(s) in {len(files)} file(s)")
        return 1
    print(f"{len(files)} text file(s) clean")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
