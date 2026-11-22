"""
graph_lib.py — Unified Duality Graph Schema v2.1

All functions in the public API table from section 9 of the spec.
Validation failures raise ToolFailed before any LLM call.

Public API
----------
load_domain(yaml_path)                        -> GraphDomain
acyclic(graph)                                -> None        (raises ToolFailed)
reducible(graph, first_radical_only=False)    -> bool
productivity_order(graph, payoff_weight=1.0)  -> list[str]
learning_path(graph, known, target)           -> list[str]
gap(graph, known, target)                     -> list[str]
validate_events(graph)                        -> list[ValidationWarning]
event_cycles(graph)                           -> list[list[str]]
build_order(graph)                            -> list[str]
resolve_imports(graph)                        -> GraphDomain
check_call_contracts(graph)                   -> list[str]
enrichment_path(graph, known, target)         -> list[str]
validate_transitions(graph)                   -> list[ValidationWarning]
flow_cycles(graph)                            -> list[list[str]]
validate_full(graph)                          -> list[ValidationWarning]
structural_drift(graph_a, graph_b)            -> float
interface_drift(graph_a, graph_b)             -> float
behavior_drift(graph_a, graph_b)              -> float
implementation_drift(graph_a, graph_b)        -> float
intent_text(graph)                            -> str
intent_drift(graph_a, graph_b, judge=None)    -> float | None
drift_report(graph_a, graph_b, dims=None, judge=None) -> dict[str, float | None]
suggest_clusters(graph, seeds=None)           -> dict[str, object]
"""

from __future__ import annotations

import math
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Callable, Iterable

import networkx as nx
import zinet
from zinet import CycleError, UnknownNodeError

from .exceptions import ToolFailed, ValidationWarning
from .loader import Blueprint, GraphDomain, _flow_destinations, load_domain

__all__ = [
    "load_domain",
    "GraphDomain",
    "Blueprint",
    "ToolFailed",
    "ValidationWarning",
    "acyclic",
    "reducible",
    "productivity_order",
    "learning_path",
    "gap",
    "validate_events",
    "event_cycles",
    "build_order",
    "resolve_imports",
    "check_call_contracts",
    "enrichment_path",
    "validate_transitions",
    "flow_cycles",
    "validate_full",
    "structural_drift",
    "interface_drift",
    "behavior_drift",
    "implementation_drift",
    "intent_text",
    "intent_drift",
    "drift_report",
    "suggest_clusters",
]


# ---------------------------------------------------------------------------
# The graph algorithms are zinet's (zinet.algorithms); these adapt a GraphDomain to them
# ---------------------------------------------------------------------------

def _zinet_graph(graph: GraphDomain) -> nx.DiGraph:
    """The mandatory form graph (composed_of / depends_on edges) as zinet's algorithms expect it: nodes carry
    `kind` (primitive, concept, or none for a name that is only referenced). Node and edge order are kept, so orders match."""
    M = _mandatory_subgraph(graph)
    G: nx.DiGraph = nx.DiGraph()
    for n in M.nodes:
        G.add_node(n, kind="primitive" if n in graph.primitives else "concept" if n in graph.nodes else None)
    G.add_edges_from(M.edges())
    return G


def _in_zinet(call, graph: GraphDomain):
    """Run `call(zinet_graph)`, reporting zinet's errors the way graph_lib always has: as ToolFailed."""
    try:
        return call(_zinet_graph(graph))
    except UnknownNodeError as e:
        raise ToolFailed(f"Target {e.node!r} not in graph.") from None
    except CycleError as e:
        raise ToolFailed(f"Form graph contains a cycle among: {', '.join(e.members)}. The form space must be acyclic.") from None


# ---------------------------------------------------------------------------
# Form-space algorithms
# ---------------------------------------------------------------------------

def acyclic(graph: GraphDomain) -> None:
    """Assert that the form space is a DAG. Raises ToolFailed if it has a cycle (the message names the nodes on it)."""
    try:
        zinet.ensure_acyclic(graph.form_graph)
    except CycleError as e:
        raise ToolFailed(
            f"Form graph contains a cycle among: {', '.join(e.members)}. "
            "The form space must be acyclic."
        ) from None


def reducible(graph: GraphDomain, first_radical_only: bool = False) -> bool:
    """Return True if every non-primitive node traces back to the root primitives.

    first_radical_only=True  — checks Two-Radical Irreducibility: should return
    False for a properly structured graph (some nodes require second-radical
    primitives and therefore cannot be derived from the first radical alone).
    """
    return zinet.reducible(
        _zinet_graph(graph), primitives=graph.primitives,
        rule="primitive_ancestry", roots=graph.first_radical_primitives if first_radical_only else None,
    )


def productivity_order(
    graph: GraphDomain, payoff_weight: float = 1.0
) -> list[str]:
    """Reach-prioritized topological sort of form.nodes (primitives are left out of the result).

    Kahn's algorithm with a heap: among nodes that are ready, the one that unlocks the most others comes first
    (reach scaled by payoff_weight), then node_id order. Raises ToolFailed if the form graph has a cycle.
    """
    return _in_zinet(lambda G: zinet.productivity_order(G, payoff_weight), graph)


def learning_path(
    graph: GraphDomain, known: list[str], target: str
) -> list[str]:
    """Minimal ordered sequence of concepts needed to reach target from known set."""
    return _in_zinet(lambda G: zinet.learning_path(G, target, known), graph)


def gap(graph: GraphDomain, known: list[str], target: str) -> list[str]:
    """Concepts still needed to reach target that are not yet in known."""
    return _in_zinet(lambda G: zinet.gap(G, target, known), graph)


def enrichment_path(
    graph: GraphDomain, known: list[str], target: str
) -> list[str]:
    """Optional enrichment concepts for the learning path to target.

    Collects enriched_by annotations on every mandatory node along the path,
    excluding concepts already in known.
    """
    mandatory = set(learning_path(graph, known, target))
    known_set = set(known)
    seen: set[str] = set()
    enrichments: list[str] = []

    for node_id in mandatory:
        ndata = graph.nodes.get(node_id) or {}
        for enrichment in ndata.get("enriched_by") or []:
            if enrichment not in seen and enrichment not in known_set:
                enrichments.append(enrichment)
                seen.add(enrichment)

    return enrichments


# ---------------------------------------------------------------------------
# Software build order
# ---------------------------------------------------------------------------

def build_order(graph: GraphDomain) -> list[str]:
    """Topological sort for software build. Returns form.nodes only (no primitives)."""
    return _in_zinet(zinet.build_order, graph)


# ---------------------------------------------------------------------------
# Event-space algorithms
# ---------------------------------------------------------------------------

def validate_events(graph: GraphDomain) -> list[ValidationWarning]:
    """Validate event declarations, emitter/listener consistency.

    Raises ToolFailed for hard errors (undeclared events, missing nodes).
    Returns list of ValidationWarnings for soft issues (unhandled, unemitted).
    """
    warnings: list[ValidationWarning] = []
    declared = set(graph.events)
    all_nodes = set(graph.nodes) | set(graph.primitives)

    # --- Hard validation ---

    for em in graph.emitters:
        ev = em.get("event")
        fn = em.get("from")
        if ev not in declared:
            raise ToolFailed(
                f"Emitter from {fn!r} references undeclared event {ev!r}. "
                "Declare it in function.events."
            )
        if fn not in all_nodes:
            raise ToolFailed(
                f"Emitter references non-existent node {fn!r}."
            )

    for lst in graph.listeners:
        ev = lst.get("event")
        nd = lst.get("node")
        if ev not in declared:
            raise ToolFailed(
                f"Listener on {nd!r} references undeclared event {ev!r}."
            )
        if nd not in graph.nodes:
            raise ToolFailed(
                f"Listener references non-existent node {nd!r}."
            )

    # Inline emit/listen on nodes
    for nid, ndata in graph.nodes.items():
        ndata = ndata or {}
        for ev in ndata.get("emit") or []:
            if ev not in declared:
                raise ToolFailed(
                    f"Node {nid!r} emits undeclared event {ev!r}."
                )
        for entry in ndata.get("listen") or []:
            ev = entry.get("event") if isinstance(entry, dict) else entry
            if ev not in declared:
                raise ToolFailed(
                    f"Node {nid!r} listens to undeclared event {ev!r}."
                )

    # --- Soft warnings ---

    emitted_events: set[str] = set()
    for em in graph.emitters:
        emitted_events.add(em.get("event", ""))
    for ndata in graph.nodes.values():
        for ev in (ndata or {}).get("emit") or []:
            emitted_events.add(ev)

    listened_events: set[str] = set()
    for lst in graph.listeners:
        listened_events.add(lst.get("event", ""))
    for ndata in graph.nodes.values():
        for entry in (ndata or {}).get("listen") or []:
            ev = entry.get("event") if isinstance(entry, dict) else entry
            if ev:
                listened_events.add(ev)

    for ev in declared:
        if ev not in listened_events:
            warnings.append(ValidationWarning(
                "UNHANDLED_EVENT",
                f"Event {ev!r} is declared but has no listeners.",
                {"event": ev},
            ))
        if ev not in emitted_events:
            warnings.append(ValidationWarning(
                "UNEMITTED_EVENT",
                f"Event {ev!r} is declared but has no emitters.",
                {"event": ev},
            ))

    return warnings


def event_cycles(graph: GraphDomain) -> list[list[str]]:
    """Detect cycles in the event subgraph. Returns list of cycles."""
    return list(nx.simple_cycles(graph.event_graph))


# ---------------------------------------------------------------------------
# Workflow-space algorithms (domain_type: workflow)
# ---------------------------------------------------------------------------

def validate_transitions(graph: GraphDomain) -> list[ValidationWarning]:
    """Validate action-routed step transitions (domain_type: workflow).

    Raises ToolFailed for hard errors:
      - a transition references a `from`/`to` node not in graph.nodes
      - `entry` is set but does not name a declared node
      - two *separate* transition entries leave the same node on the same
        `action` toward different single destinations (ambiguous routing —
        dispatch picks one edge per action, so this is a data-loss bug, not a
        style issue). A single transition entry whose `to:` is an AND-list or
        OR-set (schema v2.3, §7.1 of blueprint-schema-v2.2.md) legitimately
        produces multiple destinations for one `(src, action)` pair — that is
        multi-destination *by declaration*, not an accidental duplicate, so
        it is not flagged here; see `_flow_destinations()` in loader.py.

    Returns ValidationWarnings for soft issues:
      - a node unreachable from `entry` (dead step)
    """
    warnings: list[ValidationWarning] = []
    seen_actions: dict[tuple[str, str], set[str]] = {}

    for t in graph.transitions:
        src = t.get("from")
        destinations, _branch_type = _flow_destinations(t.get("to"))
        action = t.get("action", "default")

        if src not in graph.nodes:
            raise ToolFailed(
                f"Transition references non-existent source node {src!r}."
            )
        for dst in destinations:
            if dst not in graph.nodes:
                raise ToolFailed(
                    f"Transition references non-existent destination node {dst!r}."
                )

        key = (src, action)
        this_entry_dsts = set(destinations)
        prior_dsts = seen_actions.get(key)
        if prior_dsts is not None and prior_dsts != this_entry_dsts:
            raise ToolFailed(
                f"Ambiguous routing: node {src!r} has two separate transition "
                f"entries for action {action!r} naming different destinations "
                f"({sorted(prior_dsts)!r} and {sorted(this_entry_dsts)!r}). If "
                f"both destinations are intentional, declare them together in "
                f"one transition's `to:` as an AND-list or OR-set instead of "
                f"two separate entries."
            )
        seen_actions[key] = this_entry_dsts

    if graph.entry and graph.entry not in graph.nodes:
        raise ToolFailed(f"entry {graph.entry!r} is not a declared node.")

    if graph.entry and graph.transitions:
        reachable = (
            nx.descendants(graph.flow_graph, graph.entry) | {graph.entry}
            if graph.entry in graph.flow_graph
            else {graph.entry}
        )
        for nid in graph.nodes:
            if nid not in reachable:
                warnings.append(ValidationWarning(
                    "UNREACHABLE_STEP",
                    f"Step {nid!r} is not reachable from entry {graph.entry!r}.",
                    {"node": nid},
                ))

    return warnings


def flow_cycles(graph: GraphDomain) -> list[list[str]]:
    """Detect cycles in the workflow flow graph.

    Informational only — cycles (retry loops, iterative refinement) are
    expected in workflow control flow, unlike form_graph.
    """
    return list(nx.simple_cycles(graph.flow_graph))


# ---------------------------------------------------------------------------
# Import resolution
# ---------------------------------------------------------------------------

def resolve_imports(graph: GraphDomain) -> GraphDomain:
    """Load imported graphs and merge their exported symbols into this graph.

    Imported symbols are namespaced as <alias>.<export_name>.
    Returns a new GraphDomain with imports resolved; original is unmodified.
    """
    if not graph.path:
        raise ToolFailed("Cannot resolve imports: graph has no source path.")

    base_dir = Path(graph.path).parent
    merged = _clone(graph)

    for imp in graph.imports:
        alias = imp.get("id", "")
        optional = imp.get("optional", False)
        imp_path = base_dir / imp.get("graph", "")

        if not imp_path.exists():
            if optional:
                continue
            raise ToolFailed(
                f"Cannot resolve import {alias!r}: {imp_path} not found."
            )

        sub = load_domain(imp_path)
        requested = set(imp.get("exports") or [e.get("name") for e in sub.exports])
        bind: dict[str, str] = imp.get("bind") or {}

        for export in sub.exports:
            name = export.get("name", "")
            if name not in requested:
                continue
            local_name = bind.get(name, name)
            namespaced = f"{alias}.{local_name}"
            merged.nodes[namespaced] = {
                **export,
                "_imported_from": str(imp_path),
                "_alias": alias,
            }
            merged.form_graph.add_node(namespaced, _kind="imported")

    return merged


# ---------------------------------------------------------------------------
# Contract checking
# ---------------------------------------------------------------------------

def check_call_contracts(graph: GraphDomain) -> list[str]:
    """Verify consumer/provider signature compatibility for all call edges.

    Returns a list of violation descriptions (empty = all contracts satisfied).
    """
    violations: list[str] = []
    for call in graph.calls:
        contract = call.get("contract") or {}
        consumer_req = (contract.get("consumer_requires") or "").strip()
        provider_guar = (contract.get("provider_guarantees") or "").strip()
        if consumer_req and provider_guar and consumer_req != provider_guar:
            cid = call.get("id", "?")
            violations.append(
                f"Call {cid!r}: signature mismatch. "
                f"consumer_requires={consumer_req!r}, "
                f"provider_guarantees={provider_guar!r}"
            )
    return violations


def validate_needs(graph: GraphDomain, imported: dict[str, GraphDomain]) -> list[str]:
    """Validate applications.*.needs.* references against the node set of
    the component they name.

    Each needs entry is written "<component-alias>.<node-id>" (e.g.
    "backend.task_routes") — a typo'd or stale node-id half silently
    resolves to zero matches everywhere it's used downstream (nothing
    raises), so this is the one place that catches it. `imported` maps
    each import alias to its already-loaded GraphDomain (the caller has
    already paid that I/O cost validating the imports themselves — see
    cli.py's `validate` command). `target == "applications"` is the one
    exception: it references a sibling entry in this graph's own
    `applications:` block, not an imported component's nodes.

    Returns a list of violation descriptions (empty = all needs resolve).
    """
    violations: list[str] = []
    apps = graph.applications or {}
    for app_id, attrs in apps.items():
        needs = (attrs or {}).get("needs") or {}
        for target, deps in needs.items():
            for dep in deps:
                bare = dep.split(".", 1)[-1] if "." in dep else dep
                if target == "applications":
                    if bare not in apps:
                        violations.append(
                            f"applications.{app_id}.needs.applications: "
                            f"{dep!r} does not match any application id"
                        )
                    continue
                comp = imported.get(target)
                if comp is None:
                    violations.append(
                        f"applications.{app_id}.needs.{target}: "
                        f"no imported component named {target!r}"
                    )
                    continue
                if bare not in comp.nodes and bare not in comp.primitives:
                    violations.append(
                        f"applications.{app_id}.needs.{target}: {dep!r} does not match "
                        f"any node in component {target!r}"
                    )
    return violations


def unreachable_applications(graph: GraphDomain) -> list[ValidationWarning]:
    """Warn about applications defined in `applications:` that are never
    reachable from the capstone application via `needs.applications` edges.

    Complements validate_needs(): that check catches edges pointing at
    nothing (a dangling reference); this one catches the mirror case —
    nodes nothing points at (an application defined but never required,
    directly or transitively, by the capstone). Same BFS-reachability
    pattern as validate_transitions()'s UNREACHABLE_STEP check for the
    workflow domain, generalized to the applications graph here.

    A no-op if there is no `applications.*.capstone: true` entry — without
    a declared entry point there is nothing to reach from.
    """
    apps = graph.applications or {}
    if not apps:
        return []
    capstone_id = next((aid for aid, attrs in apps.items() if (attrs or {}).get("capstone")), None)
    if capstone_id is None or capstone_id not in apps:
        return []

    app_graph = nx.DiGraph()
    app_graph.add_nodes_from(apps)
    for app_id, attrs in apps.items():
        needs = (attrs or {}).get("needs") or {}
        for dep in needs.get("applications") or []:
            bare = dep.split(".", 1)[-1] if "." in dep else dep
            if bare in apps:
                app_graph.add_edge(app_id, bare)

    reachable = nx.descendants(app_graph, capstone_id) | {capstone_id}
    return [
        ValidationWarning(
            "UNREACHABLE_APPLICATION",
            f"Application {aid!r} is never required (directly or transitively) "
            f"by capstone application {capstone_id!r}.",
            {"application": aid, "capstone": capstone_id},
        )
        for aid in apps
        if aid not in reachable
    ]


# ---------------------------------------------------------------------------
# Composite validation entry point
# ---------------------------------------------------------------------------

def validate_full(graph: GraphDomain) -> list[ValidationWarning]:
    """Run all validation checks in order. Returns all warnings.

    Hard errors raise ToolFailed and halt immediately.
    Soft issues are collected as ValidationWarnings and returned.

    Check order:
      1. Form space acyclicity (always hard error)
      2. Two-Radical Irreducibility (hard error only if graph.enforce_two_radical=True)
      3. Event space consistency (hard errors + warnings)
      4. Call contract compatibility (warnings)
      5. Workflow transitions (hard errors + warnings; only if transitions declared)
      6. Application reachability from the capstone (warnings; only if a
         capstone application is declared)
    """
    warnings: list[ValidationWarning] = []

    # 1. Form must be acyclic — always enforced
    acyclic(graph)

    # 2. Two-Radical Irreducibility — opt-in via graph attribute
    if graph.enforce_two_radical and graph.first_radical_primitives:
        if reducible(graph, first_radical_only=True):
            raise ToolFailed(
                f"Two-Radical Irreducibility violated in graph {graph.graph_id!r}: "
                "every node is derivable from first_radical_primitives alone, meaning "
                "the second-radical primitives are unused. Either add concepts that "
                "require second-radical primitives, or set enforce_two_radical: false."
            )

    # 3. Event space
    if graph.events or any(
        (n or {}).get("emit") or (n or {}).get("listen")
        for n in graph.nodes.values()
    ):
        warnings.extend(validate_events(graph))

    # 4. Call contracts
    for violation in check_call_contracts(graph):
        warnings.append(ValidationWarning(
            "CONTRACT_VIOLATION", violation, {"graph": graph.graph_id}
        ))

    # 5. Workflow transitions
    if graph.transitions:
        warnings.extend(validate_transitions(graph))

    # 6. Application reachability from the capstone
    warnings.extend(unreachable_applications(graph))

    return warnings


# ---------------------------------------------------------------------------
# Drift — round-trip fidelity between two versions of "the same" blueprint
# ---------------------------------------------------------------------------
# See docs/DEV/BUILD/blueprint-schema-v2.2.md §3 for the schema this vector
# populates (Blueprint.drift). Nodes/edges/exports/etc. are matched by their
# string id across the two graphs — correct for this codebase's actual use
# case (comparing two versions of a component that share the same node-id
# convention, e.g. an authored blueprint vs. one reverse-mined from its own
# generated code), not general unlabeled graph isomorphism (which
# nx.graph_edit_distance solves, at a cost this doesn't need to pay here).

_DRIFT_MODES = ("semantic", "edit-dist", "jaccard")


def _jaccard_distance(a: set, b: set) -> float:
    """1 - |intersection|/|union|; 0.0 for two empty sets (nothing to compare)."""
    union = a | b
    if not union:
        return 0.0
    return len(a ^ b) / len(union)


def _canonical(entries: list[dict], keys: tuple[str, ...]) -> set[tuple]:
    """Hashable, order-independent signature per dict entry, over given keys."""
    return {tuple((k, str(e.get(k, ""))) for k in keys) for e in entries}


def _levenshtein(a: str, b: str) -> int:
    """Classic O(len_a * len_b) edit-distance DP — insert/delete/substitute,
    unit cost each. Small inputs only (blueprint text, not whole codebases),
    so no need for a banded/linear-space variant."""
    if a == b:
        return 0
    la, lb = len(a), len(b)
    if la == 0:
        return lb
    if lb == 0:
        return la
    prev = list(range(lb + 1))
    for i, ca in enumerate(a, 1):
        curr = [i] + [0] * lb
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost)
        prev = curr
    return prev[lb]


def _edit_distance_ratio(text_a: str, text_b: str) -> float:
    """Normalized Levenshtein distance in [0, 1] — literal character-level
    edit distance divided by the longer text's length, unlike
    _jaccard_distance's all-or-nothing exact-tuple matching: two texts that
    differ by one word score close to 0, not the 1.0 a set-based comparison
    would give once even one token in a tuple changes."""
    if not text_a and not text_b:
        return 0.0
    return min(1.0, _levenshtein(text_a, text_b) / max(len(text_a), len(text_b)))


def _dim_dispatch(
    dimension: str,
    text_a: str,
    text_b: str,
    set_a: set,
    set_b: set,
    mode: str,
    judge: Callable[[str, str, str], float] | None,
) -> float | None:
    """Shared mode dispatch for the four graph-diffable drift dimensions —
    each supplies its own (text, set) representation pair; this picks the
    comparison. 'semantic' returns None without a judge (same "not measured,
    not zero" contract intent_drift already had) so callers can tell
    "unchanged" apart from "not computed". `judge(dimension, text_a, text_b)`
    is told which dimension it's scoring — the same judge callable is shared
    across all 5 dimensions in one drift_report() call, and without knowing
    which dimension it's currently judging it can't tell "structural node
    churn" from "interface signature churn" apart (see
    appgraph/prompts/intent_drift.md (the judge's prompt), which uses this to frame the
    question correctly per dimension)."""
    if mode == "jaccard":
        return _jaccard_distance(set_a, set_b)
    if mode == "edit-dist":
        return _edit_distance_ratio(text_a, text_b)
    if mode == "semantic":
        if judge is None:
            return None
        return round(max(0.0, min(1.0, judge(dimension, text_a, text_b))), 4)
    raise ValueError(f"unknown drift mode {mode!r}; choose one of {_DRIFT_MODES}")


def _structural_text(graph: GraphDomain) -> str:
    G = _mandatory_subgraph(graph)
    return (
        "nodes: " + ", ".join(sorted(G.nodes()))
        + "\nedges: " + ", ".join(f"{a}->{b}" for a, b in sorted(G.edges()))
    )


def _interface_signature(graph: GraphDomain) -> set[tuple]:
    return (
        _canonical(graph.exports, ("name", "kind", "from", "signature"))
        | _canonical(graph.calls, ("from", "to", "consumer_requires", "provider_guarantees"))
        | _canonical(graph.emitters, ("node", "event"))
        | _canonical(graph.listeners, ("node", "event"))
    )


def _set_text(items: set) -> str:
    return "\n".join(sorted(str(t) for t in items))


def structural_drift(
    graph_a: GraphDomain, graph_b: GraphDomain,
    mode: str = "jaccard", judge: Callable[[str, str, str], float] | None = None,
) -> float | None:
    """Structural difference over form.nodes/form.edges.

    `mode="jaccard"` (default) is reach-weighted, not a plain set diff: each
    node present on only one side is weighted by its `reach` (descendant
    count — the same measure productivity_order() uses) in the graph it
    came from, plus 1 so a leaf node still counts — losing a foundational
    node should cost more than losing a leaf doc node. Node and edge
    components are each normalized to [0, 1] against the union's total
    weighted mass / edge count, then averaged. `mode="edit-dist"`/
    `"semantic"` instead compare a flat sorted node/edge-id text rendering
    (see _structural_text) — they lose the reach-weighting, trading it for
    (edit-dist) partial credit on near-identical id spelling, or (semantic)
    an LLM judgment of the rendered structure.
    """
    if mode == "jaccard":
        Ga = _mandatory_subgraph(graph_a)
        Gb = _mandatory_subgraph(graph_b)

        ids_a, ids_b = set(Ga.nodes()), set(Gb.nodes())
        reach_a = {n: len(nx.descendants(Ga, n)) + 1 for n in ids_a}
        reach_b = {n: len(nx.descendants(Gb, n)) + 1 for n in ids_b}

        node_cost = sum(reach_a[n] for n in ids_a - ids_b) + sum(reach_b[n] for n in ids_b - ids_a)
        total_mass = sum(reach_a.values()) + sum(reach_b.values())
        node_component = node_cost / total_mass if total_mass else 0.0

        edges_a, edges_b = set(Ga.edges()), set(Gb.edges())
        total_edges = len(edges_a) + len(edges_b)
        edge_component = len(edges_a ^ edges_b) / total_edges if total_edges else 0.0

        return min(1.0, (node_component + edge_component) / 2)

    text_a, text_b = _structural_text(graph_a), _structural_text(graph_b)
    if mode == "edit-dist":
        return _edit_distance_ratio(text_a, text_b)
    if mode == "semantic":
        if judge is None:
            return None
        return round(max(0.0, min(1.0, judge("structural", text_a, text_b))), 4)
    raise ValueError(f"unknown drift mode {mode!r}; choose one of {_DRIFT_MODES}")


def interface_drift(
    graph_a: GraphDomain, graph_b: GraphDomain,
    mode: str = "jaccard", judge: Callable[[str, str, str], float] | None = None,
) -> float | None:
    """Drift over function.exports/calls/emitters/listeners signatures.
    `mode="jaccard"` (default): distance over the exact-match signature set.
    `"edit-dist"`/`"semantic"`: compare the same signatures rendered as text."""
    sig_a, sig_b = _interface_signature(graph_a), _interface_signature(graph_b)
    return _dim_dispatch("interface", _set_text(sig_a), _set_text(sig_b), sig_a, sig_b, mode, judge)


def behavior_drift(
    graph_a: GraphDomain, graph_b: GraphDomain,
    mode: str = "jaccard", judge: Callable[[str, str, str], float] | None = None,
) -> float | None:
    """Drift over the top-level verification: list's entries.
    `mode="jaccard"` (default): distance over the exact-match entry set.
    `"edit-dist"`/`"semantic"`: compare the same entries rendered as text."""
    keys = ("node", "tool", "checks", "backend", "tests")
    set_a = _canonical(graph_a.verification, keys)
    set_b = _canonical(graph_b.verification, keys)
    return _dim_dispatch("behavior", _set_text(set_a), _set_text(set_b), set_a, set_b, mode, judge)


def implementation_drift(
    graph_a: GraphDomain, graph_b: GraphDomain,
    mode: str = "jaccard", judge: Callable[[str, str, str], float] | None = None,
) -> float | None:
    """Drift over the primitive (tech-stack constraint) sets each graph
    composes from — distinct from structural_drift's node/edge diff, this
    isolates "did the underlying dependency stack change" (e.g. sqlite ->
    postgres, a different ORM), independent of node-count churn.
    `mode="jaccard"` (default): distance over the exact-match primitive-id
    set. `"edit-dist"`/`"semantic"`: compare the same set rendered as text."""
    set_a, set_b = set(graph_a.primitives), set(graph_b.primitives)
    return _dim_dispatch("implementation", _set_text(set_a), _set_text(set_b), set_a, set_b, mode, judge)


def intent_text(graph: GraphDomain) -> str:
    """Free-text rationale for a graph — the "why", not the "what"/"how"
    already covered by interface_drift/behavior_drift/implementation_drift.
    Humans express intent by writing prose, not by filling in
    spec.interface, so this pulls every node's `defines`/`comment`/
    `spec.user_story` *and* its `docs` field verbatim — `docs` is where a
    node's README-style description lives (see tools/graph-ide's node-kind
    legend: `doc`-kind nodes are exactly this), and is the richest signal of
    intent this schema has. Fed to intent_drift()'s judge as one side of the
    comparison.
    """
    lines = [f"graph: {graph.graph_id}  comment: {graph.comment}"]
    for node_id, data in sorted(graph.nodes.items()):
        data = data or {}
        user_story = (data.get("spec") or {}).get("user_story", "")
        lines.append(
            f"- {node_id} (kind={data.get('kind', '')}): defines={data.get('defines', '')!r} "
            f"comment={data.get('comment', '')!r} user_story={user_story!r}"
        )
        docs = data.get("docs", "")
        if docs:
            lines.append(f"  docs: {docs!r}")
    for name, app in sorted((graph.applications or {}).items()):
        app = app or {}
        lines.append(
            f"- application {name}: defines={app.get('defines', '')!r} "
            f"user_story={app.get('user_story', '')!r}"
        )
    return "\n".join(lines)


def intent_drift(
    graph_a: GraphDomain,
    graph_b: GraphDomain,
    mode: str = "semantic",
    judge: Callable[[str, str, str], float] | None = None,
) -> float | None:
    """Drift between two graphs' intent_text() — free-text rationale, not a
    structured field, so `mode="semantic"` (default) is the natural fit:
    meaning-drift needs an LLM, since graph_lib.py deliberately has no LLM
    access of its own (see the section docstring above). Pass `judge`, a
    callable `(dimension, text_a, text_b) -> float` scoring drift in [0, 1]
    (told which dimension it's judging — see _dim_dispatch); `appgraph
    drift --llm` supplies one backed by appgraph/judge.py (one dd-llm call).
    Returns None — not 0.0 — when no judge is given in semantic mode, so
    callers can tell "unchanged" apart from "not measured".

    `mode="jaccard"`/`"edit-dist"` are also available as free (no-LLM)
    approximations: jaccard treats intent_text() as a bag of words (word-set
    overlap), edit-dist as one long string (character-level edit distance)
    — cruder than an LLM judge's actual reading of meaning, but still a
    useful zero-cost signal.
    """
    text_a, text_b = intent_text(graph_a), intent_text(graph_b)
    if mode == "jaccard":
        return _jaccard_distance(set(text_a.split()), set(text_b.split()))
    if mode == "edit-dist":
        return _edit_distance_ratio(text_a, text_b)
    if mode == "semantic":
        if judge is None:
            return None
        return round(max(0.0, min(1.0, judge("intent", text_a, text_b))), 4)
    raise ValueError(f"unknown drift mode {mode!r}; choose one of {_DRIFT_MODES}")


_DRIFT_DIMS = ("intent", "behavior", "structural", "interface", "implementation")

_DIM_TEXT_BUILDERS: dict[str, Callable[[GraphDomain], str]] = {
    "structural": _structural_text,
    "interface": lambda g: _set_text(_interface_signature(g)),
    "behavior": lambda g: _set_text(
        _canonical(g.verification, ("node", "tool", "checks", "backend", "tests"))
    ),
    "implementation": lambda g: _set_text(set(g.primitives)),
    "intent": intent_text,
}


def _cosine_distance(text_a: str, text_b: str) -> float:
    """1 - cosine similarity between two bag-of-words term-frequency
    vectors built from whitespace-split tokens; 0.0 if both texts are
    empty, 1.0 if exactly one is (no shared vocabulary possible)."""
    vec_a, vec_b = Counter(text_a.split()), Counter(text_b.split())
    if not vec_a and not vec_b:
        return 0.0
    if not vec_a or not vec_b:
        return 1.0
    shared = set(vec_a) & set(vec_b)
    dot = sum(vec_a[t] * vec_b[t] for t in shared)
    norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
    norm_b = math.sqrt(sum(v * v for v in vec_b.values()))
    similarity = dot / (norm_a * norm_b) if norm_a and norm_b else 0.0
    return round(max(0.0, min(1.0, 1 - similarity)), 4)


def drift_report(
    graph_a: GraphDomain,
    graph_b: GraphDomain,
    dims: Iterable[str] | None = None,
    mode: str = "jaccard",
    judge: Callable[[str, str, str], float] | None = None,
) -> dict[str, float | None]:
    """The drift vector (docs/DEV/BUILD/blueprint-schema-v2.2.md §3) — each
    of the 5 components independently, one aspect of the schema per
    function above — plus an `overall` aggregate.

    `mode` (`"jaccard"` default, or `"edit-dist"`/`"semantic"`) applies
    uniformly to all 5 dimensions, `intent` included — previously `intent`
    could only ever be computed via an LLM judge (or was left `None`);
    under `mode="jaccard"`/`"edit-dist"` it now gets a free, zero-LLM-cost
    approximation too (bag-of-words overlap / character edit distance over
    its free-text rationale), consistent with how the other four
    dimensions were already free by default. `mode="semantic"` routes every
    dimension through `judge` instead (an LLM-as-judge call per dimension,
    same contract as intent's previous sole mode) — `None` for a dimension
    without a `judge`, so callers can tell "unchanged" apart from "not
    measured".

    `overall` is **not** a mean of the five dimension scores — deliberately
    a different computation, since those scores are individually
    incommensurable (structural churn and intent drift mean different
    things) and a plain mean would blur that. Instead it's a genuine
    two-vector comparison: 1 - cosine similarity between graph_a's and
    graph_b's *combined* text (every selected dimension's own text
    rendering, concatenated, as one bag-of-words vector per graph) —
    independent of `mode`, since cosine similarity needs the raw
    representations, not the already-reduced per-dimension scores. One
    consequence worth knowing: with only one dimension selected, `overall`
    is no longer guaranteed to equal that dimension's own jaccard/edit-dist
    score — cosine similarity gives partial credit for shared vocabulary
    that a set-based or LLM score doesn't.

    `dims` restricts which components run — default is all five. Unknown
    dimension names raise ValueError.
    """
    selected = set(dims) if dims else set(_DRIFT_DIMS)
    unknown = selected - set(_DRIFT_DIMS)
    if unknown:
        raise ValueError(f"unknown drift dimension(s): {sorted(unknown)}")
    if mode not in _DRIFT_MODES:
        raise ValueError(f"unknown drift mode {mode!r}; choose one of {_DRIFT_MODES}")

    def _r(v: float | None) -> float | None:
        return round(v, 4) if v is not None else None

    result: dict[str, float | None] = {}
    if "intent" in selected:
        result["intent"] = _r(intent_drift(graph_a, graph_b, mode=mode, judge=judge))
    if "behavior" in selected:
        result["behavior"] = _r(behavior_drift(graph_a, graph_b, mode=mode, judge=judge))
    if "structural" in selected:
        result["structural"] = _r(structural_drift(graph_a, graph_b, mode=mode, judge=judge))
    if "interface" in selected:
        result["interface"] = _r(interface_drift(graph_a, graph_b, mode=mode, judge=judge))
    if "implementation" in selected:
        result["implementation"] = _r(implementation_drift(graph_a, graph_b, mode=mode, judge=judge))

    combined_a = "\n".join(_DIM_TEXT_BUILDERS[d](graph_a) for d in sorted(selected))
    combined_b = "\n".join(_DIM_TEXT_BUILDERS[d](graph_b) for d in sorted(selected))
    result["overall"] = _cosine_distance(combined_a, combined_b) if selected else None
    return result


# ---------------------------------------------------------------------------
# Structural analysis
# ---------------------------------------------------------------------------

def suggest_clusters(
    graph: GraphDomain, seeds: Iterable[str] | None = None
) -> dict[str, object]:
    """Ancestor-closure clustering: suggest how to split one monolithic
    graph into smaller, logically modular sub-graphs.

    Deterministic and parameter-free — no community-detection/modularity
    library involved. Seeds default to `graph.exports[].from` (a node id, or
    `node_id.port_name` — the part before the first `.` is taken), deduped;
    pass `seeds` explicitly to override. For each seed, its cluster is
    `nx.ancestors()` over the mandatory subgraph (same helper `reducible()`/
    `productivity_order()` use) plus the seed itself — the set of nodes the
    seed is built from.

    A node ancestor of every seed is genuinely shared infrastructure and is
    reported under `"core"` — deliberately *every*, not "2 or more": a node
    that's upstream of some seeds but not all (e.g. one component calling
    another's helper) is a real cross-component dependency, not shared
    infrastructure, so folding it into core on a looser "2+" rule would hide
    exactly the design decision worth surfacing. Such nodes are reported
    under `"shared"`, keyed by the sorted tuple of seed names that reach
    them, so a human can decide whether that's an intentional cross-import
    or a sign the split needs rethinking — this function never guesses.

    Returns:
        {
          "seeds": sorted list of seed node ids actually used,
          "clusters": {seed: sorted node ids reachable from only that seed},
          "core": sorted node ids that are ancestors of every seed,
          "shared": {sorted seed-name tuple (as "a+b"): sorted node ids},
          "unclustered": sorted node ids that are ancestors of no seed
                         (e.g. the composition root, or disconnected nodes),
        }
    """
    G = _mandatory_subgraph(graph)

    if seeds is None:
        seed_ids: list[str] = []
        for export in graph.exports:
            src = export.get("from")
            if not src:
                continue
            node_id = src.split(".", 1)[0]
            if node_id not in seed_ids:
                seed_ids.append(node_id)
    else:
        seed_ids = list(dict.fromkeys(seeds))

    seed_ids = [s for s in seed_ids if s in G]
    ancestors_of: dict[str, set[str]] = {
        s: nx.ancestors(G, s) | {s} for s in seed_ids
    }

    clusters: dict[str, list[str]] = {s: [] for s in seed_ids}
    core: list[str] = []
    shared: dict[str, list[str]] = {}
    unclustered: list[str] = []

    for node_id in G.nodes:
        covering = sorted(s for s in seed_ids if node_id in ancestors_of[s])
        if not covering:
            unclustered.append(node_id)
        elif len(covering) == len(seed_ids):
            core.append(node_id)
        elif len(covering) == 1:
            clusters[covering[0]].append(node_id)
        else:
            shared.setdefault("+".join(covering), []).append(node_id)

    return {
        "seeds": sorted(seed_ids),
        "clusters": {s: sorted(nodes) for s, nodes in clusters.items()},
        "core": sorted(core),
        "shared": {k: sorted(v) for k, v in shared.items()},
        "unclustered": sorted(unclustered),
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _mandatory_subgraph(graph: GraphDomain) -> nx.DiGraph:
    """Form graph restricted to mandatory edges (composed_of, depends_on)."""
    G: nx.DiGraph = nx.DiGraph()
    G.add_nodes_from(graph.form_graph.nodes(data=True))
    for u, v, data in graph.form_graph.edges(data=True):
        kind = data.get("kind") or ""
        if kind in ("composed_of", "depends_on", ""):
            G.add_edge(u, v, **data)
    return G


def _clone(graph: GraphDomain) -> GraphDomain:
    """Shallow clone of GraphDomain with independent mutable collections."""
    clone = GraphDomain.__new__(GraphDomain)
    clone.__dict__.update(graph.__dict__)
    clone.nodes = dict(graph.nodes)
    clone.primitives = dict(graph.primitives)
    clone.exports = list(graph.exports)
    clone.imports = list(graph.imports)
    clone.transitions = list(graph.transitions)
    clone.form_graph = graph.form_graph.copy()
    clone.event_graph = graph.event_graph.copy()
    clone.flow_graph = graph.flow_graph.copy()
    return clone
