"""Discover and merge graph-code blueprint files under an app root into a
single node/edge graph for the viewer frontend.

Schema: Unified Duality Graph Schema v2.1+, read via graph_code.loader (not
hand-rolled YAML parsing — see docs/DEV/BUILD/refactoring-plan-v1.md for why
duplicating schema logic outside the library is exactly the kind of drift
this framework has repeatedly had to fix). An app root is apps/<app>/
containing a blueprint/ subfolder with either:

  - blueprint/main.graph.yaml — an `integrated` system file whose `imports:`
    names one or more component graph.yaml files (backend/frontend/...), or
  - a single blueprint/<name>.graph.yaml — a standalone component (e.g. a
    `workflow` app with no system-level composition, like etl_workflow).

Node ids are namespaced by component ("backend::api_routes") so the same
node name in two components never collides; system-level applications are
namespaced "system::<name>" — the same convention this tool's original
GDW-schema version used, kept unchanged so the frontend needs no id-format
changes, only a richer node-`kind` vocabulary (see DetailPanel.js).
"""

from __future__ import annotations

from pathlib import Path

from graph_code.loader import GraphDomain, load_domain

_PRIMITIVE_KIND = "primitive"
_APPLICATION_KIND = "application"


def _node_dict(node_id: str, kind: str, component: str | None, source_file: str, attrs: dict) -> dict:
    attrs = attrs or {}
    return {
        "id": node_id,
        "label": node_id.split("::", 1)[-1],
        "kind": kind,
        "tier": attrs.get("tier", 0),
        "component": component,
        "source_file": source_file,
        "defines": attrs.get("defines", ""),
        "spec": attrs.get("spec") or {},
        "verification": attrs.get("verification") or {},
        "docs": attrs.get("docs", ""),
    }


def _edge_style(kind: str) -> str:
    # composed_of/depends_on are the mandatory-edge kinds (see graph_code's
    # _MANDATORY_EDGE_KINDS); enriched_by/optionally_depends_on are optional.
    return "composed_of" if kind in ("composed_of", "depends_on") else "optional"


def _rel(path: Path, root: Path) -> str:
    return str(path.relative_to(root))


def _component_from_domain(component_id: str, rel_path: str, domain: GraphDomain) -> tuple[list[dict], list[dict]]:
    nodes: list[dict] = []

    for pid, pdata in domain.primitives.items():
        node_id = f"{component_id}::{pid}"
        nodes.append(_node_dict(node_id, _PRIMITIVE_KIND, component_id, rel_path, {**(pdata or {}), "tier": 0}))

    for nid, ndata in domain.nodes.items():
        ndata = ndata or {}
        node_id = f"{component_id}::{nid}"
        nodes.append(_node_dict(node_id, ndata.get("kind", "concept"), component_id, rel_path, ndata))

    edges = [
        {
            "from": f"{component_id}::{dep}",
            "to": f"{component_id}::{dst}",
            "type": _edge_style(data.get("kind", "composed_of")),
        }
        for dep, dst, data in domain.form_graph.edges(data=True)
    ]

    return nodes, edges


def _find_entry(root: Path) -> Path | None:
    blueprint_dir = root / "blueprint"
    if not blueprint_dir.is_dir():
        return None
    main_path = blueprint_dir / "main.graph.yaml"
    if main_path.exists():
        return main_path
    candidates = sorted(blueprint_dir.glob("*.graph.yaml"))
    return candidates[0] if candidates else None


def build_graph(root: Path) -> dict:
    entry = _find_entry(root)
    if entry is None:
        return {"root": str(root), "files": [], "components": {}, "nodes": [], "edges": []}

    domain = load_domain(entry)
    files: list[dict[str, str]] = [{"path": _rel(entry, root), "kind": "system" if domain.imports else "component"}]
    nodes: list[dict] = []
    edges: list[dict] = []
    components: dict[str, dict] = {}

    if domain.imports:
        for imp in domain.imports:
            comp_id = imp["id"]
            comp_path = (entry.parent / imp["graph"]).resolve()
            if not comp_path.exists():
                continue
            files.append({"path": _rel(comp_path, root), "kind": "component", "component": comp_id})
            comp_domain = load_domain(comp_path)
            n, e = _component_from_domain(comp_id, _rel(comp_path, root), comp_domain)
            nodes.extend(n)
            edges.extend(e)
            components[comp_id] = {
                "depends_on": [i["id"] for i in comp_domain.imports],
                "capstone": comp_domain.capstone,
            }

        for name, attrs in domain.applications.items():
            attrs = attrs or {}
            node_id = f"system::{name}"
            nodes.append(_node_dict(node_id, _APPLICATION_KIND, None, _rel(entry, root), {**attrs, "tier": "system"}))
            needs = attrs.get("needs") or {}
            for target, deps in needs.items():
                for dep in deps:
                    # dep is written as "<component>.<node>" (e.g.
                    # "backend.task_routes") in applications.*.needs.*, but
                    # node ids elsewhere are namespaced "<component>::<node>"
                    # with a bare node id — strip the redundant component
                    # prefix so this edge's endpoint actually resolves.
                    bare_dep = dep.split(".", 1)[-1] if "." in dep else dep
                    dep_id = f"system::{bare_dep}" if target == "applications" else f"{target}::{bare_dep}"
                    edges.append({"from": dep_id, "to": node_id, "type": "needs"})
    else:
        # Standalone component — no system-level main.graph.yaml (e.g. a
        # `workflow` app like etl_workflow, built directly via
        # build_component.spl with no other components to import).
        comp_id = domain.graph_id or entry.stem
        n, e = _component_from_domain(comp_id, _rel(entry, root), domain)
        nodes.extend(n)
        edges.extend(e)
        components[comp_id] = {"depends_on": [], "capstone": domain.capstone}

    return {"root": str(root), "files": files, "components": components, "nodes": nodes, "edges": edges}
