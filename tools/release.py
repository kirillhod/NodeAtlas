#!/usr/bin/env python3
"""Bump the release version, check the records and build the extension zip.

This is the mechanical part of ``docs/agent/release.md``. It does not run the
test matrix, commit, tag or publish anything: those steps need a person and
are listed at the end.

Usage:
    python tools/release.py --version 1.7.2 --blender C:/Blender/blender.exe
    python tools/release.py --version 1.7.2 --dry-run
    python tools/release.py --version 1.7.2 --blender ... --no-build

The dry run prints the planned file changes and the record checks; it never
writes. A real run refuses a dirty working tree unless ``--allow-dirty``.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "node_atlas" / "blender_manifest.toml"
INIT = ROOT / "node_atlas" / "__init__.py"
CHANGELOG = ROOT / "CHANGELOG.md"
NOTES = ROOT / "RELEASE_NOTES.md"
QA = ROOT / "QA_REPORT.md"
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def fail(message: str) -> int:
    print(f"release: {message}", file=sys.stderr)
    return 1


def bump(path: Path, pattern: str, replacement: str, dry_run: bool) -> bool:
    text = path.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if count != 1:
        raise SystemExit(f"release: {path} does not contain {pattern!r}")
    if updated == text:
        return False
    if not dry_run:
        path.write_text(updated, encoding="utf-8", newline="")
    return True


def check_records(version: str) -> list[str]:
    problems: list[str] = []
    changelog = CHANGELOG.read_text(encoding="utf-8")
    if not re.search(rf"^## {re.escape(version)}\s*$", changelog, re.MULTILINE):
        problems.append(f"CHANGELOG.md has no '## {version}' section")
    notes = NOTES.read_text(encoding="utf-8")
    if not re.search(
        rf"^# Node Atlas {re.escape(version)}\s*$", notes, re.MULTILINE
    ):
        problems.append(f"RELEASE_NOTES.md has no '# Node Atlas {version}' title")
    if "**Released:**" not in notes:
        problems.append("RELEASE_NOTES.md has no '**Released:**' line")
    qa = QA.read_text(encoding="utf-8")
    if "**Version:** " + version not in qa:
        problems.append(f"QA_REPORT.md does not name version {version}")
    return problems


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, text=True, capture_output=True)


def build(blender: str, version: str, output_dir: str) -> int:
    zip_name = f"node_atlas-{version}.zip"
    folder = Path(output_dir)
    if not folder.is_absolute():
        folder = ROOT / folder
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / zip_name
    steps = [
        [blender, "--command", "extension", "validate", "node_atlas"],
        [
            blender, "--command", "extension", "build",
            "--source-dir", "node_atlas", "--output-dir", str(folder),
        ],
        [blender, "--command", "extension", "validate", str(target)],
    ]
    for command in steps:
        result = run(command)
        if result.returncode != 0:
            print(result.stdout, end="")
            print(result.stderr, end="", file=sys.stderr)
            return fail(f"command failed: {' '.join(command)}")
    if not target.is_file():
        return fail(f"build did not create {target}")

    with zipfile.ZipFile(target) as archive:
        names = archive.namelist()
    broken = [name for name in names if "__pycache__" in name or name.endswith(".pyc")]
    if broken:
        return fail(f"zip contains build artifacts: {', '.join(broken)}")
    digest = hashlib.sha256(target.read_bytes()).hexdigest().upper()
    print(f"artifact: {target}")
    print(f"files: {len(names)}")
    for name in names:
        print(f"  {name}")
    print(f"size: {target.stat().st_size}")
    print(f"SHA256: {digest}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Bump NodeAtlas version fields, check records and build the zip.",
    )
    parser.add_argument("--version", required=True, help="target version, e.g. 1.7.2")
    parser.add_argument("--blender", default="", help="blender executable for build/validate")
    parser.add_argument("--output-dir", default="dist", help="zip output folder (default: dist)")
    parser.add_argument("--dry-run", action="store_true", help="print, do not write or build")
    parser.add_argument("--no-build", action="store_true", help="skip validate/build")
    parser.add_argument("--allow-dirty", action="store_true", help="allow uncommitted changes")
    args = parser.parse_args(argv)

    version = args.version.strip().lstrip("v")
    if not SEMVER.match(version):
        return fail(f"expected MAJOR.MINOR.PATCH, got {args.version!r}")
    major, minor, patch = version.split(".")

    status = run(["git", "status", "--porcelain"])
    dirty = bool(status.stdout.strip())
    if dirty and not args.dry_run and not args.allow_dirty:
        return fail("working tree is not clean; commit first or pass --allow-dirty")

    changed = []
    if bump(MANIFEST, r'^version = ".*"$', f'version = "{version}"', args.dry_run):
        changed.append(MANIFEST.relative_to(ROOT))
    if bump(INIT, r'^__version__ = ".*"$', f'__version__ = "{version}"', args.dry_run):
        changed.append(INIT.relative_to(ROOT))
    if bump(
        INIT,
        r'^\s*"version": \(\d+, \d+, \d+\),$',
        f'    "version": ({major}, {minor}, {patch}),',
        args.dry_run,
    ):
        if INIT.relative_to(ROOT) not in changed:
            changed.append(INIT.relative_to(ROOT))

    print("version fields:")
    print("  " + (", ".join(str(item) for item in changed) or "already current"))
    problems = check_records(version)
    if problems:
        for problem in problems:
            print(f"record: {problem}", file=sys.stderr)
        return fail("records are incomplete; update them before building")

    check = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "check_text.py")],
        cwd=ROOT,
    )
    if check.returncode != 0:
        return fail("text check failed; fix the reported files first")

    if args.dry_run:
        print("dry run: no files written, no build")
        return 0
    if args.no_build:
        print("build skipped")
        return 0
    if not args.blender:
        return fail("pass --blender to build the zip, or --no-build")
    result = build(args.blender, version, args.output_dir)
    if result:
        return result

    print()
    print("next steps (manual):")
    print("  1. run the unit suite and the full matrix with -RequireClean")
    print("  2. install the zip into an isolated profile and run test_artifact.py")
    print("  3. review the diff, commit the version bump and records")
    print(f"  4. tag the commit: git tag -a v{version} -m \"Node Atlas {version}\"")
    print("  5. publish only with explicit permission")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
