"""Shared YAML scalar-styling rules for graph-code blueprint files.

Prose fields are `|` block literals, one bullet per "; "-separated clause;
bare identifiers/paths stay unquoted plain scalars. Used by `grafcode
prettify` (whole-file normalization).

Ported from graph-driven-workflow/scripts/graph_yaml_style.py — logic is
schema-agnostic (pure YAML scalar formatting), so no changes were needed.
"""

from __future__ import annotations

from ruamel.yaml.scalarstring import LiteralScalarString

SPLIT_SEP = "; "


def to_bullets(text: str) -> LiteralScalarString:
    clauses = [c.strip().rstrip(".") for c in text.split(SPLIT_SEP)]
    body = "\n".join(f"- {c}" for c in clauses if c) + "\n"
    return LiteralScalarString(body)


def normalize_chomping(value: LiteralScalarString) -> LiteralScalarString:
    """Force clip chomping (a single trailing newline, i.e. `|` not `|-`)."""
    normalized = str(value).rstrip("\n") + "\n"
    return value if normalized == str(value) else LiteralScalarString(normalized)


def prettify_scalar(value: str, in_list: bool) -> str:
    text = str(value).strip()
    if not text:
        return value
    if in_list:
        return text  # already itemized by YAML's own "-"; just drop quotes
    if " " in text:
        return to_bullets(text)
    return text  # bare identifier/path — unquote, ruamel re-quotes if unsafe
