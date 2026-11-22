"""YAML scalar-styling for a hand-edited prose field, ported verbatim from
graph-driven-workflow/scripts/graph_yaml_style.py (its edited_text_to_scalar
has no schema dependency — it only decides plain-scalar vs. block-literal
based on the text's own shape, so it needed no changes for app-graph's
schema).
"""

from __future__ import annotations

from ruamel.yaml.scalarstring import LiteralScalarString


def edited_text_to_scalar(text: str):
    """Store a hand-edited field verbatim: block literal if it has any
    structure (spaces/newlines — i.e. it's prose, already-bulleted or not),
    plain scalar if it's a bare identifier/path. Never re-splits or
    re-bullets — the caller typed exactly what they want stored.
    """
    text = text.strip("\n")
    if not text:
        return ""
    if " " in text or "\n" in text:
        return LiteralScalarString(text + "\n")
    return text
