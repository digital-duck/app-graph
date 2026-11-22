"""
loader.py — YAML loading and normalization for Unified Duality Graph Schema v2.1

Handles two formats:
  v1.0 flat  (ConceptBook paper): primitives/concepts/applications at top level
  v2.1 unified: form/function split with events, calls, imports, exports
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import networkx as nx
import yaml

from .exceptions import ToolFailed
from .settings import interpolate, load_settings


@dataclass
class Blueprint:
    """Provenance metadata for a graph (schema v2.2 addition, additive-only).

    Absent from a graph.yaml -> GraphDomain.blueprint is None; existing v1.0/v2.1
    graphs are unaffected. See docs/DEV/BUILD/blueprint-schema-v2.2.md.

    Since docs/DEV/BUILD/refactoring-plan-v1.md §1.1, the blueprint block is
    the source of truth for a graph's identity: GraphDomain.graph_id/version/
    domain_type are sourced from id/graph_schema_version/domain_type below
    when a blueprint: block is present, falling back to the legacy root-level
    graph:/version:/domain_type: keys only when it is absent.
    """

    id: str
    schema_version: str            # the blueprint block's OWN schema version, e.g. "2.2"
    graph_schema_version: str      # the core Unified Duality Graph Schema version, e.g. "2.1"
    domain_type: str
    provenance: str                # authored | build | reverse | roundtrip
    parent_blueprint: str | None
    lineage: list[dict]            # one entry per pass: {pass, model, adapter,
                                    # temperature, prompt_hash, engine, timestamp}
    drift: dict | None             # {reference_blueprint, vector: {...}} once roundtripped


@dataclass
class GraphDomain:
    """Fully parsed and normalized representation of a v2.1 graph."""

    # Identity — sourced from blueprint: when present (see Blueprint's own
    # docstring), else from the legacy root-level graph:/version:/domain_type:
    # keys. `comment` is the one prose field (root `comment:`, falling back to
    # the legacy `description:` key so untouched apps keep working).
    graph_id: str
    version: str
    domain_type: str              # curriculum | software | reactive_app | integrated
    comment: str
    path: str | None

    # Hierarchical domain classification (slash-separated path)
    # e.g. "physics/classical_mechanics" or "software/backend/fastapi"
    # Separate from domain_type (compilation target) and graph_id (unique identifier).
    domain: str

    # Target languages for code-generation profiles; guides the SPL runner.
    # e.g. ["python"] or ["python", "javascript"]
    target_languages: list

    # If True, validate_full() enforces Two-Radical Irreducibility as a hard error.
    # Default False — opt-in because many practical graphs have a single primitive class.
    enforce_two_radical: bool

    # Form space
    primitives: dict[str, Any]
    first_radical_primitives: list[str]
    nodes: dict[str, Any]     # concepts / modules / components / widgets / services
    form_graph: nx.DiGraph    # DAG: dep → node (prereqs point to dependents)

    # Function space
    events: dict[str, Any]
    calls: list[dict]
    emitters: list[dict]
    listeners: list[dict]
    exports: list[dict]
    event_graph: nx.DiGraph   # bipartite: node→event (emit), event→node (notify)

    # Workflow space (domain_type: workflow) — action-routed step transitions.
    # Nodes may declare optional form.nodes.<id>.phases: {pre, execute, post}
    # (ETL-style: pre for state prep/validation, post for formatting/routing);
    # phases are carried verbatim on node data, no dedicated parsing needed.
    transitions: list[dict]
    flow_graph: nx.DiGraph    # step → step; may cycle (retries, iterative refinement)
    entry: str | None

    # Top-level
    imports: list[dict]
    applications: dict[str, Any]
    verification: list[dict]
    capstone: str | None          # declared capstone node id, if any

    # Blueprint provenance (schema v2.2 addition) — None for v1.0/v2.1 graphs
    # that carry no blueprint: block.
    blueprint: Blueprint | None


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def load_domain(yaml_path: str | Path) -> GraphDomain:
    """Parse a graph YAML file (v1.0 flat or v2.1 unified) and return a GraphDomain.

    Raises ToolFailed for empty/invalid YAML.
    """
    yaml_path = Path(yaml_path)
    with yaml_path.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    if not isinstance(raw, dict):
        raise ToolFailed(f"Empty or non-dict YAML: {yaml_path}")

    raw = interpolate(raw, load_settings(yaml_path))

    data = _normalize_flat_v1(raw) if _is_flat_v1(raw) else raw
    return _build_graph_domain(data, path=str(yaml_path))


# ---------------------------------------------------------------------------
# Format detection and normalization
# ---------------------------------------------------------------------------

def _is_flat_v1(data: dict) -> bool:
    """Detect ConceptBook v1.0 flat format (primitives/concepts at top level)."""
    return (
        "form" not in data
        and ("primitives" in data or "concepts" in data or "domain" in data)
    )


def _normalize_flat_v1(data: dict) -> dict:
    """Convert flat v1.0 to v2.1 unified structure."""
    raw_domain = data.get("domain", "unknown")
    normalized: dict[str, Any] = {
        "graph": raw_domain,
        "domain": raw_domain,          # carry domain path through
        "version": "2.1",
        "domain_type": "curriculum",
        "description": data.get("description", ""),
        "comment": data.get("comment", ""),
        "form": {
            "primitives": data.get("primitives", {}),
            "first_radical_primitives": data.get("first_radical_primitives", []),
            "nodes": {},
        },
        "function": {},
        "verification": list(data.get("verification", [])),
        "applications": data.get("applications", {}),
    }

    for concept_id, cdata in (data.get("concepts") or {}).items():
        cdata = cdata or {}
        node: dict[str, Any] = {
            "kind": "concept",
            "defines": cdata.get("defines", ""),
            "tier": cdata.get("tier", 1),
        }
        # Carry over all fields except the ones lifted to verification
        for key, val in cdata.items():
            if key not in ("verifier", "lab", "play"):
                node[key] = val

        normalized["form"]["nodes"][concept_id] = node

        if any(k in cdata for k in ("verifier", "lab", "play")):
            normalized["verification"].append({
                "node": concept_id,
                "backend": cdata.get("verifier", ""),
                "lab": cdata.get("lab", ""),
                "play": cdata.get("play", ""),
            })

    return normalized


# ---------------------------------------------------------------------------
# GraphDomain construction
# ---------------------------------------------------------------------------

def _build_graph_domain(data: dict, path: str | None = None) -> GraphDomain:
    form = data.get("form") or {}
    function = data.get("function") or {}

    primitives: dict[str, Any] = form.get("primitives") or {}
    first_radical: list[str] = form.get("first_radical_primitives") or []
    nodes: dict[str, Any] = form.get("nodes") or {}

    events: dict[str, Any] = function.get("events") or {}
    calls: list[dict] = function.get("calls") or []
    emitters: list[dict] = function.get("emitters") or []
    listeners: list[dict] = function.get("listeners") or []
    exports: list[dict] = function.get("exports") or []
    transitions: list[dict] = function.get("transitions") or []

    form_graph = _build_form_graph(primitives, nodes, form.get("edges") or [])
    event_graph = _build_event_graph(nodes, events, emitters, listeners)
    flow_graph = _build_flow_graph(transitions)
    blueprint = _build_blueprint(data.get("blueprint"))

    graph_id = (blueprint.id if blueprint and blueprint.id else data.get("graph", ""))
    version = (
        blueprint.graph_schema_version
        if blueprint and blueprint.graph_schema_version
        else data.get("version", "2.1")
    )
    domain_type = (
        blueprint.domain_type if blueprint and blueprint.domain_type else data.get("domain_type", "curriculum")
    )
    comment = data.get("comment") or data.get("description", "")

    return GraphDomain(
        graph_id=graph_id,
        version=version,
        domain_type=domain_type,
        comment=comment,
        path=path,
        domain=data.get("domain", ""),
        target_languages=list(data.get("target_languages") or []),
        enforce_two_radical=bool(data.get("enforce_two_radical", False)),
        primitives=primitives,
        first_radical_primitives=first_radical,
        nodes=nodes,
        form_graph=form_graph,
        events=events,
        calls=calls,
        emitters=emitters,
        listeners=listeners,
        exports=exports,
        event_graph=event_graph,
        transitions=transitions,
        flow_graph=flow_graph,
        entry=data.get("entry"),
        imports=data.get("imports") or [],
        applications=data.get("applications") or {},
        verification=data.get("verification") or [],
        capstone=data.get("capstone"),
        blueprint=blueprint,
    )


# ---------------------------------------------------------------------------
# Graph builders
# ---------------------------------------------------------------------------

_MANDATORY_EDGE_KINDS = frozenset({"composed_of", "depends_on", None, ""})
_OPTIONAL_EDGE_KINDS = frozenset({"enriched_by", "optionally_depends_on"})


def _build_form_graph(
    primitives: dict, nodes: dict, explicit_edges: list
) -> nx.DiGraph:
    """Build the form-space DAG.

    Edge direction: dep → node  (prerequisites point toward their dependents).
    This matches nx.topological_sort returning primitives before concepts.
    """
    G: nx.DiGraph = nx.DiGraph()

    for pid, pdata in primitives.items():
        G.add_node(pid, _kind="primitive", **(pdata or {}))

    for nid, ndata in nodes.items():
        ndata = ndata or {}
        G.add_node(nid, _kind="node", **ndata)

        for dep in ndata.get("composed_of") or []:
            G.add_edge(dep, nid, kind="composed_of")
        for dep in ndata.get("depends_on") or []:
            G.add_edge(dep, nid, kind="depends_on")
        for dep in ndata.get("optionally_depends_on") or []:
            G.add_edge(dep, nid, kind="optionally_depends_on")
        for dep in ndata.get("enriched_by") or []:
            G.add_edge(dep, nid, kind="enriched_by")

    for edge in explicit_edges:
        G.add_edge(
            edge["from"], edge["to"],
            kind=edge.get("kind", ""),
            comment=edge.get("comment", ""),
            # Optional cache-invalidation control (schema v2.2 §8.2, see
            # docs/DEV/BUILD/blueprint-schema-v2.2.md): use_cache: false on an
            # explicit edge forces the `to` node to miss cache — carried as an
            # edge attribute (only present when authored) rather than
            # defaulted here, so tools.py::cache_get can distinguish "not set"
            # from "set true" via `data.get("use_cache") is False`.
            **({"use_cache": edge["use_cache"]} if "use_cache" in edge else {}),
        )

    return G


def _build_event_graph(
    nodes: dict, events: dict, emitters: list, listeners: list
) -> nx.DiGraph:
    """Build the event subgraph (bipartite: nodes ↔ events).

    node --[emits]--> event --[notifies]--> node
    """
    G: nx.DiGraph = nx.DiGraph()

    for nid in nodes:
        G.add_node(nid, vertex_type="node")
    for eid in events:
        G.add_node(eid, vertex_type="event")

    # Explicit emitters list
    for emitter in emitters:
        fn = emitter.get("from")
        ev = emitter.get("event")
        if fn and ev:
            G.add_edge(fn, ev, kind="emits")

    # Inline emit fields on nodes
    for nid, ndata in nodes.items():
        for ev in (ndata or {}).get("emit") or []:
            if ev not in G:
                G.add_node(ev, vertex_type="event")
            G.add_edge(nid, ev, kind="emits")

    # Explicit listeners list
    for lst in listeners:
        nd = lst.get("node")
        ev = lst.get("event")
        if nd and ev:
            G.add_edge(
                ev, nd,
                kind="notifies",
                handle=lst.get("handle", ""),
                optional=lst.get("optional", False),
            )

    # Inline listen fields on nodes
    for nid, ndata in nodes.items():
        for entry in (ndata or {}).get("listen") or []:
            if isinstance(entry, dict):
                ev = entry.get("event")
                if ev:
                    G.add_edge(
                        ev, nid,
                        kind="notifies",
                        handle=entry.get("handle", ""),
                        optional=entry.get("optional", False),
                    )

    return G


def _build_blueprint(raw: dict | None) -> Blueprint | None:
    """Parse the optional blueprint: block (schema v2.2). No hard validation yet —
    provenance/parent_blueprint consistency is left to a future opt-in check,
    mirroring enforce_two_radical's pattern (see blueprint-schema-v2.2.md §4).
    """
    if not raw:
        return None

    return Blueprint(
        id=raw.get("id", ""),
        schema_version=raw.get("schema_version", ""),
        graph_schema_version=raw.get("graph_schema_version", ""),
        domain_type=raw.get("domain_type", ""),
        provenance=raw.get("provenance", "authored"),
        parent_blueprint=raw.get("parent_blueprint"),
        lineage=list(raw.get("lineage") or []),
        drift=raw.get("drift"),
    )


def _flow_destinations(dst: Any) -> tuple[list[str], str]:
    """Normalize a transition's `to:` field to (destination list, branch_type).

    `to:` accepts three shapes, added in schema v2.3 (see
    docs/DEV/BUILD/blueprint-schema-v2.2.md §7) after sketching real SPL.py
    recipes as blueprint graphs surfaced that plain-string `to:` couldn't
    express genuine parallel fan-out (`spl-recipe-blueprint-experiment.md`,
    recipe 3's branching turned out to already be expressible via multiple
    `action`-keyed transitions — no schema change needed for that case — but
    true "both of these fire" fan-out had no representation at all):

    - a single string  → one edge, branch_type "single" (v2.1 behavior, unchanged)
    - a YAML list `[a, b]` → AND fan-out, every destination fires — branch_type "and"
    - a YAML flow-mapping `{a, b}` → parsed by yaml.safe_load as {'a': None, 'b': None}
      with no custom tag needed — treated as an OR set, branch_type "or". Still just a
      *declared possibility space*; which one actually fires at runtime is resolved by
      the interpreter's own condition/action logic, same as it already is for a plain
      action-routed transition — this only makes "these are alternatives to each other"
      explicit in the graph instead of implicit across separate transition entries.
    """
    if isinstance(dst, str):
        return [dst], "single"
    if isinstance(dst, list):
        return list(dst), "and"
    if isinstance(dst, dict):
        return list(dst.keys()), "or"
    return [], "single"


def _build_flow_graph(transitions: list[dict]) -> nx.DiGraph:
    """Build the workflow step-transition graph (domain_type: workflow).

    Edge direction: from → to, keyed by `action` (default "default") — the
    value a step's `post` phase returns to select its next step. Unlike
    form_graph, this graph is allowed to contain cycles: retries and
    iterative refinement are normal in workflow control flow.

    `to:` may name one destination, an AND-list, or an OR-set (`_flow_destinations`
    above) — each resolved destination becomes its own edge, tagged with the
    transition's `branch_type` so multi-destination transitions are
    distinguishable from an accidental duplicate later in `validate_transitions()`.
    A transition's `kind` (e.g. `exception`) is also carried onto every edge it
    produces — schema v2.3, §7.2 of blueprint-schema-v2.2.md.
    """
    G: nx.DiGraph = nx.DiGraph()

    for t in transitions:
        src = t.get("from")
        destinations, branch_type = _flow_destinations(t.get("to"))
        if not src:
            continue
        for dst in destinations:
            G.add_edge(
                src, dst,
                action=t.get("action", "default"),
                condition=t.get("condition", ""),
                comment=t.get("comment", ""),
                branch_type=branch_type,
                kind=t.get("kind", "normal"),
            )

    return G
