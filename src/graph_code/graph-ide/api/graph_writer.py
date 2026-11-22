"""Update a single node's editable prose fields in its owning graph.yaml, in
place, preserving formatting via ruamel.yaml round-trip.

Scope (ported from graph-driven-workflow/tools/graph-ide's docs/IDE/README.md
design): UPDATE only — the fields below never affect graph structure
(composed_of / depends_on / needs / capstone / tier), so this never needs to
touch edges, create nodes, or delete anything.

Schema difference from the original GDW-schema version: a node's owning
section is no longer a single top-level key shared by every node of that
kind (old: primitives/concepts/applications, flat) — form.primitives and
form.nodes are both nested under `form:`, and form.nodes holds every
`kind:` (concept/module/component/doc/step/...) in one dict. Which section
a node lives in is derived from its own `kind` (see _entry_keys), not from
where it was found in the merged viewer graph.
"""

from __future__ import annotations

import os
import tempfile
from io import StringIO
from pathlib import Path
from typing import Any

import yaml as pyyaml
from ruamel.yaml import YAML

from api.graph_discovery import build_graph
from api.graph_yaml_style import edited_text_to_scalar
from graph_code.exceptions import ToolFailed
from graph_code.graph_lib import validate_full
from graph_code.loader import load_domain

EDITABLE_FIELDS = {
    "defines",
    "docs",
    "spec.interface",
    "spec.contract",
    "spec.user_story",
    "verification.node",
    "verification.edge",
}


class NodeNotFound(Exception):
    pass


class InvalidField(Exception):
    pass


class WriteFailed(Exception):
    pass


def _flatten(fields: dict[str, Any]) -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for key, value in fields.items():
        if isinstance(value, dict):
            for subkey, subvalue in value.items():
                flat[f"{key}.{subkey}"] = subvalue
        else:
            flat[key] = value
    return flat


def _set_path(entry: dict, path: str, value: Any) -> None:
    parts = path.split(".")
    node = entry
    for part in parts[:-1]:
        if node.get(part) is None:
            node[part] = {}
        node = node[part]
    node[parts[-1]] = value


def _entry_keys(kind: str) -> list[str]:
    """Which nested keys hold this node's raw entry, based on its `kind`."""
    if kind == "primitive":
        return ["form", "primitives"]
    if kind == "application":
        return ["applications"]
    return ["form", "nodes"]


def _make_yaml() -> YAML:
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096
    yaml.indent(mapping=2, sequence=2, offset=0)
    return yaml


def update_node(root: Path, node_id: str, fields: dict[str, Any]) -> dict:
    """Apply `fields` (a partial {defines, docs, spec: {...}, verification: {...}}
    patch) to `node_id`'s entry in its source file, and return the node's
    refreshed representation (same shape as build_graph()'s `nodes` entries).
    """
    flat = _flatten(fields)
    unknown = sorted(set(flat) - EDITABLE_FIELDS)
    if unknown:
        raise InvalidField(f"not editable in this version: {', '.join(unknown)}")

    graph = build_graph(root)
    node = next((n for n in graph["nodes"] if n["id"] == node_id), None)
    if node is None:
        raise NodeNotFound(node_id)

    file_path = root / node["source_file"]
    bare_name = node_id.split("::", 1)[-1]

    yaml = _make_yaml()
    original_text = file_path.read_text()
    data = yaml.load(original_text)

    entry = data
    for key in _entry_keys(node["kind"]):
        entry = entry[key]
    entry = entry[bare_name]

    for path, value in flat.items():
        normalized = edited_text_to_scalar(value) if isinstance(value, str) else value
        _set_path(entry, path, normalized)

    buf = StringIO()
    yaml.dump(data, buf)
    new_text = buf.getvalue()

    # Safety net before touching disk: the rewritten file must still parse
    # AND still pass graph_code's own validate_full() — the same structural
    # gate build_app.spl runs before any LLM call (see ToolFailed's docstring:
    # "must be raised before any LLM call"). Edits here only ever touch prose
    # fields, so this should never actually trip; it's defense-in-depth for a
    # ruamel-dump edge case, and it's the hook a future phase (editable
    # composed_of/needs) would rely on.
    try:
        pyyaml.safe_load(new_text)
    except pyyaml.YAMLError as e:
        raise WriteFailed(f"edit would produce invalid YAML: {e}") from e

    # validate_full() needs a real GraphDomain, and load_domain() resolves
    # ${{ settings.KEY }} against a sibling settings.yaml by directory — so
    # the trial write must land in file_path's own directory, not /tmp.
    fd, tmp_name = tempfile.mkstemp(dir=file_path.parent, suffix=".graph.yaml")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(new_text)
        try:
            trial_domain = load_domain(tmp_name)
            validate_full(trial_domain)
        except ToolFailed as e:
            raise WriteFailed(f"edit would break graph validation: {e}") from e
    finally:
        os.unlink(tmp_name)

    file_path.write_text(new_text)

    updated_graph = build_graph(root)
    return next(n for n in updated_graph["nodes"] if n["id"] == node_id)
