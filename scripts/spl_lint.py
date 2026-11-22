#!/usr/bin/env python3
"""
spl_lint.py — find/fix unescaped single quotes inside CREATE FUNCTION
prompt bodies (AS $$ ... $$) in .spl files.

SPL dollar-quoted strings use SQL-style quote escaping: a literal
apostrophe must be written as '' (two single quotes), or it breaks
syntax highlighting / parsing for everything after it in the file.
It's easy to type a plain English apostrophe ("don't", "component's")
inside a CREATE FUNCTION prompt and forget to escape it.

Scope is deliberately narrow: only plain "AS $$ ... $$" blocks (LLM
prompt prose, e.g. CREATE FUNCTION bodies) are touched. "AS PYTHON
$$ ... $$" blocks (CREATE TOOL_API bodies) hold real executable Python,
where a single quote is a string delimiter, not an English apostrophe —
blanket-doubling those would corrupt the code (e.g. 'passed' would
become ''passed''). Those blocks are reported separately and never
auto-fixed; check them by eye.

Usage:
    scripts/spl_lint.py                # check spl/*.spl, report issues, exit 1 if any
    scripts/spl_lint.py file1.spl ...  # check specific files
    scripts/spl_lint.py --fix          # rewrite files in place with '' escaping applied
    scripts/spl_lint.py --fix file.spl
"""
from __future__ import annotations

import argparse
import glob
import re
import sys

# Only bare "AS $$" — "AS PYTHON $$" (real code) is deliberately excluded.
BLOCK_RE = re.compile(r"AS\s+\$\$(.*?)\$\$", re.DOTALL)
PYTHON_BLOCK_RE = re.compile(r"AS\s+PYTHON\s+\$\$(.*?)\$\$", re.DOTALL)


def escape_block(text: str) -> str:
    """Double up every lone single quote; leave already-escaped '' pairs alone."""
    out = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "'":
            if i + 1 < n and text[i + 1] == "'":
                out.append("''")
                i += 2
                continue
            out.append("''")
            i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def lines_touched(original: str, fixed: str, block_start_line: int) -> list[int]:
    orig_lines = original.split("\n")
    fixed_lines = fixed.split("\n")
    touched = []
    for idx, (o, f) in enumerate(zip(orig_lines, fixed_lines)):
        if o != f:
            touched.append(block_start_line + idx)
    return touched


def process(path: str, fix: bool) -> list[str]:
    with open(path, encoding="utf-8") as fh:
        content = fh.read()

    issues = []
    new_content_parts = []
    last_end = 0
    changed = False

    for m in BLOCK_RE.finditer(content):
        block = m.group(1)
        fixed_block = escape_block(block)
        block_start_line = content[: m.start(1)].count("\n") + 1

        if fixed_block != block:
            changed = True
            touched = lines_touched(block, fixed_block, block_start_line)
            for ln in touched:
                issues.append(f"{path}:{ln}: unescaped single quote in $$ block")

        new_content_parts.append(content[last_end : m.start(1)])
        new_content_parts.append(fixed_block)
        last_end = m.end(1)

    new_content_parts.append(content[last_end:])
    new_content = "".join(new_content_parts)

    if fix and changed:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(new_content)

    for m in PYTHON_BLOCK_RE.finditer(content):
        if "'" in m.group(1).replace("''", ""):
            start_line = content[: m.start(1)].count("\n") + 1
            issues.append(
                f"{path}:{start_line}: AS PYTHON $$ block contains a single quote "
                "— not auto-fixed (likely real Python syntax), check by hand"
            )

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="*", help="Files to check (default: spl/*.spl)")
    parser.add_argument("--fix", action="store_true", help="Rewrite files in place")
    args = parser.parse_args()

    files = args.files or sorted(glob.glob("spl/*.spl"))
    if not files:
        print("No .spl files found", file=sys.stderr)
        return 1

    all_issues = []
    for path in files:
        all_issues.extend(process(path, args.fix))

    if all_issues:
        for issue in all_issues:
            print(issue)
        if args.fix:
            print(f"\nFixed {len(all_issues)} unescaped quote(s).")
            return 0
        print(f"\n{len(all_issues)} unescaped quote(s) found. Run with --fix to auto-correct.")
        return 1

    print("OK — no unescaped single quotes in $$ blocks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
