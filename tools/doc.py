#!/usr/bin/env python3
"""Print one Markdown section by heading number, so agents do not read whole docs.

NodeGraph_Export_Report.md is about 27k tokens and IMPLEMENTATION_PLAN.md about 8k.
Reading either end to end pushes the code, test output and the user's actual request out
of the context window. This helper loads only the section that answers the question.

Usage:
    python tools/doc.py --list NodeGraph_Export_Report.md
    python tools/doc.py NodeGraph_Export_Report.md 4.6
    python tools/doc.py NodeGraph_Export_Report.md 5.26
    python tools/doc.py IMPLEMENTATION_PLAN.md M7
    python tools/doc.py NodeGraph_Export_Report.md 11.15 --max-lines 80

A numeric query matches the exact heading number: ``4`` selects chapter 4, ``4.3``
selects section 4.3, and ``11`` does not sweep 11.1-11.16. When no heading has that
number, a two-part query selects one numbered item inside the chapter, so ``5.26``
prints item 26 of section 5 instead of the whole section. A text query matches a
case-insensitive heading prefix. Ambiguous queries list the candidates instead of
guessing. The section ends at the next heading of the same or a higher level.

The tool is development-only: it is not part of the Blender add-on and needs no
third-party packages. If ``python`` is unavailable outside Blender, run it through
Blender's bundled interpreter:

    blender --background --factory-startup --python tools/doc.py -- <file> <query>
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
NUMBER = re.compile(r"^(?:§\s*)?(\d+(?:\.\d+)*)\.?(?=\s|$)")
ITEM = re.compile(r"^(\s*)(\d+)\.\s+")
ITEM_QUERY = re.compile(r"^(\d+)\.(\d+)$")


@dataclass(frozen=True)
class Heading:
    line: int
    level: int
    title: str

    @property
    def number(self) -> str | None:
        match = NUMBER.match(self.title)
        return match.group(1) if match else None


def read_headings(path: Path) -> tuple[list[str], list[Heading]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    headings: list[Heading] = []
    in_fence = False
    for number, line in enumerate(lines, 1):
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = HEADING.match(line)
        if match:
            headings.append(Heading(number, len(match.group(1)), match.group(2)))
    return lines, headings


def matches(heading: Heading, query: str) -> bool:
    if heading.number is not None and query[0].isdigit():
        return heading.number == query
    return heading.title.casefold().startswith(query.casefold())


def section_end(headings: list[Heading], index: int, total: int) -> int:
    """Return the last line of the section, before the next same-or-higher heading."""
    level = headings[index].level
    for following in headings[index + 1:]:
        if following.level <= level:
            return following.line - 1
    return total


def print_list(path: Path, headings: list[Heading]) -> None:
    print(f"{path} ({len(headings)} headings)")
    for heading in headings:
        marks = "#" * heading.level
        print(f"{heading.line:>6}  {marks:<6}  {heading.title}")


def find_item(
    lines: list[str], headings: list[Heading], index: int, number: int
) -> tuple[int, int] | None:
    """Return the 0-based ``[start, end)`` slice of top-level item ``number``."""
    start = headings[index].line
    last = section_end(headings, index, len(lines))
    indent = None
    starts: list[tuple[int, int]] = []
    for line_index in range(start, last):
        match = ITEM.match(lines[line_index])
        if match is None:
            continue
        if indent is None:
            indent = len(match.group(1))
        if len(match.group(1)) == indent:
            starts.append((int(match.group(2)), line_index))
    for position, (item_number, line_index) in enumerate(starts):
        if item_number != number:
            continue
        end = starts[position + 1][1] if position + 1 < len(starts) else last
        while end > line_index and not lines[end - 1].strip():
            end -= 1
        return line_index, end
    return None


def emit(
    path: Path, label: str, first_line: int, section: list[str], max_lines: int
) -> None:
    last_line = first_line + len(section) - 1
    print(
        f"<!-- {path.name} {label} "
        f"(lines {first_line}-{last_line}, {len(section)} lines) -->"
    )
    if max_lines and len(section) > max_lines:
        print("\n".join(section[:max_lines]))
        print(f"... [truncated at {max_lines} lines of the section]")
    else:
        print("\n".join(section))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Print one Markdown section by heading number or prefix.",
    )
    parser.add_argument("path", type=Path, help="Markdown file to read")
    parser.add_argument(
        "query",
        nargs="?",
        help="Heading number (4.6) or title prefix (M7); omit with --list",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List headings with line numbers and stop",
    )
    parser.add_argument(
        "--max-lines",
        type=int,
        default=0,
        metavar="N",
        help="Truncate each printed section after N lines (0 = no limit)",
    )
    args = parser.parse_args(argv)

    if not args.path.is_file():
        parser.error(f"not a file: {args.path}")
    if args.max_lines < 0:
        parser.error("--max-lines must be 0 or greater")
    if not args.list and not args.query:
        parser.error("provide a query or use --list")

    lines, headings = read_headings(args.path)
    if args.list:
        print_list(args.path, headings)
        return 0

    query = args.query.strip().lstrip("#").strip()
    if not query:
        parser.error("query is empty")
    found = [index for index, heading in enumerate(headings) if matches(heading, query)]
    if not found:
        item = ITEM_QUERY.match(query)
        if item is not None:
            major, minor = item.group(1), int(item.group(2))
            chapters = [
                index for index, heading in enumerate(headings)
                if heading.number == major
            ]
            if len(chapters) == 1:
                span = find_item(lines, headings, chapters[0], minor)
                if span is not None:
                    first, end = span
                    emit(
                        args.path,
                        f"§{major} item {minor}",
                        first + 1,
                        lines[first:end],
                        args.max_lines,
                    )
                    return 0
            print(
                f"no item {minor} in section {major} of {args.path}",
                file=sys.stderr,
            )
            return 1
        print(f"no heading matches {query!r} in {args.path}", file=sys.stderr)
        print("use --list to see the headings", file=sys.stderr)
        return 1
    if len(found) > 1:
        print(f"{query!r} is ambiguous in {args.path}; choose one:", file=sys.stderr)
        for index in found:
            heading = headings[index]
            print(f"  {heading.line:>6}  {heading.title}", file=sys.stderr)
        return 2

    index = found[0]
    heading = headings[index]
    last = section_end(headings, index, len(lines))
    emit(
        args.path,
        f"§{heading.title}",
        heading.line,
        lines[heading.line - 1:last],
        args.max_lines,
    )
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    arguments = sys.argv[1:]
    if "--" in arguments:
        arguments = arguments[arguments.index("--") + 1:]
    status = main(arguments)
    if status:
        raise SystemExit(status)
