"""Tests for appgraph.graph_lib — Unified Duality Graph Schema v2.1."""

from __future__ import annotations

import pytest

from appgraph import (
    ToolFailed,
    ValidationWarning,
    acyclic,
    behavior_drift,
    build_order,
    check_call_contracts,
    drift_report,
    enrichment_path,
    event_cycles,
    flow_cycles,
    gap,
    implementation_drift,
    intent_drift,
    intent_text,
    interface_drift,
    learning_path,
    productivity_order,
    reducible,
    structural_drift,
    suggest_clusters,
    validate_events,
    validate_full,
    validate_transitions,
)


# ===========================================================================
# Loader: flat v1.0 normalization
# ===========================================================================

class TestLoader:
    def test_flat_v1_graph_id(self, flat_graph):
        assert flat_graph.graph_id == "classical_mechanics"

    def test_flat_v1_domain_type(self, flat_graph):
        assert flat_graph.domain_type == "curriculum"

    def test_flat_v1_version(self, flat_graph):
        assert flat_graph.version == "2.1"

    def test_flat_v1_primitives_loaded(self, flat_graph):
        assert set(flat_graph.primitives) == {"position", "time", "mass", "force"}

    def test_flat_v1_nodes_loaded(self, flat_graph):
        assert "velocity" in flat_graph.nodes
        assert "momentum" in flat_graph.nodes
        assert "newtons_second_law" in flat_graph.nodes

    def test_flat_v1_verification_extracted(self, flat_graph):
        nodes_with_verification = {v["node"] for v in flat_graph.verification}
        assert "velocity" in nodes_with_verification

    def test_flat_v1_first_radical(self, flat_graph):
        assert set(flat_graph.first_radical_primitives) == {"position", "time"}

    def test_flat_v1_form_graph_has_edges(self, flat_graph):
        # velocity depends on position and time
        assert flat_graph.form_graph.has_edge("position", "velocity")
        assert flat_graph.form_graph.has_edge("time", "velocity")

    def test_unified_v21_graph_id(self, unified_graph):
        assert unified_graph.graph_id == "classical_mechanics"

    def test_unified_v21_nodes(self, unified_graph):
        assert "velocity" in unified_graph.nodes
        assert "newtons_second_law" in unified_graph.nodes

    def test_example_files_load(self, apps_dir):
        from appgraph.loader import load_domain
        # Recursive: every *.graph.yaml now lives under apps/<app>/blueprint/
        # (mandatory convention since 2026-08-13, see
        # docs/DEV/BUILD/blueprint-schema-v2.2.md's "blueprint/ subfolder" addendum),
        # not loose at the apps/ root.
        for yaml_file in apps_dir.glob("**/*.graph.yaml"):
            if yaml_file.name == "main.graph.yaml" and "physics_app" in str(yaml_file):
                continue  # requires sub-imports; skip in this test
            domain = load_domain(yaml_file)
            assert domain.graph_id, f"{yaml_file.name} missing graph_id"


# ===========================================================================
# Loader: blueprint provenance block (schema v2.2)
# ===========================================================================

class TestBlueprint:
    def test_absent_blueprint_is_none(self, unified_graph):
        assert unified_graph.blueprint is None

    def test_blueprint_fields_parsed(self, blueprint_graph):
        bp = blueprint_graph.blueprint
        assert bp is not None
        assert bp.id == "blueprint_test"
        assert bp.schema_version == "2.2"
        assert bp.provenance == "roundtrip"
        assert bp.parent_blueprint == "blueprint_test_v1"

    def test_lineage_entries_in_order(self, blueprint_graph):
        lineage = blueprint_graph.blueprint.lineage
        assert [entry["pass"] for entry in lineage] == ["forward", "reverse"]
        assert lineage[0]["model"] == "claude-sonnet-4-6"
        assert lineage[1]["engine"] == "graph-code-miner"

    def test_drift_vector_parsed(self, blueprint_graph):
        drift = blueprint_graph.blueprint.drift
        assert drift["reference_blueprint"] == "blueprint_test_v1"
        assert drift["vector"]["structural"] == 0.05
        assert drift["vector"]["interface"] == 0.0

    def test_default_provenance_is_authored(self):
        from appgraph.loader import load_domain
        import tempfile, os
        content = """
graph: no_provenance
version: "2.1"
domain_type: software
blueprint:
  id: no_provenance
  schema_version: "2.2"
  domain_type: software
form:
  nodes: {}
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as fh:
            fh.write(content)
            tmp = fh.name
        try:
            domain = load_domain(tmp)
            assert domain.blueprint.provenance == "authored"
            assert domain.blueprint.lineage == []
            assert domain.blueprint.drift is None
        finally:
            os.unlink(tmp)

    def test_todo_examples_carry_blueprint(self, apps_dir):
        from appgraph.loader import load_domain
        for name in ("todo/blueprint/main.graph.yaml", "todo/blueprint/backend.graph.yaml", "todo/blueprint/frontend.graph.yaml"):
            domain = load_domain(apps_dir / name)
            assert domain.blueprint is not None, f"{name} missing blueprint block"
            assert domain.blueprint.provenance == "authored"
            assert domain.blueprint.lineage == []


# ===========================================================================
# acyclic
# ===========================================================================

class TestAcyclic:
    def test_valid_dag_passes(self, flat_graph):
        acyclic(flat_graph)  # no exception

    def test_cyclic_graph_raises(self, cyclic_graph):
        with pytest.raises(ToolFailed, match="cycle"):
            acyclic(cyclic_graph)


# ===========================================================================
# reducible
# ===========================================================================

class TestReducible:
    def test_fully_reducible_from_all_primitives(self, flat_graph):
        assert reducible(flat_graph) is True

    def test_not_reducible_from_first_radical_only(self, flat_graph):
        # momentum requires mass (second radical) → not reducible from first radical only
        assert reducible(flat_graph, first_radical_only=True) is False

    def test_velocity_in_first_radical_path(self, flat_graph):
        # velocity only needs position + time (both first radical)
        # When we exclude momentum from the check, pure kinematics nodes are reducible
        # from first radical. But reducible() checks ALL nodes, so it returns False
        # because momentum requires mass.
        assert reducible(flat_graph, first_radical_only=True) is False

    def test_unified_reducible(self, unified_graph):
        assert reducible(unified_graph) is True


# ===========================================================================
# productivity_order
# ===========================================================================

class TestProductivityOrder:
    def test_returns_only_nodes_not_primitives(self, flat_graph):
        order = productivity_order(flat_graph)
        primitive_ids = set(flat_graph.primitives)
        assert not (set(order) & primitive_ids)

    def test_all_nodes_included(self, flat_graph):
        order = productivity_order(flat_graph)
        assert set(order) == set(flat_graph.nodes)

    def test_topological_constraint(self, flat_graph):
        order = productivity_order(flat_graph)
        idx = {n: i for i, n in enumerate(order)}
        # velocity must come before acceleration (velocity is its dep)
        assert idx["velocity"] < idx["acceleration"]
        # velocity and mass must precede momentum
        assert idx["velocity"] < idx["momentum"]

    def test_payoff_weight_zero_still_valid_order(self, flat_graph):
        order = productivity_order(flat_graph, payoff_weight=0.0)
        assert len(order) == len(flat_graph.nodes)


# ===========================================================================
# learning_path
# ===========================================================================

class TestLearningPath:
    def test_path_to_velocity(self, flat_graph):
        path = learning_path(flat_graph, known=[], target="velocity")
        assert "velocity" in path
        assert "position" not in path  # primitives are pre-existing, excluded from path
        assert "time" not in path
        assert "mass" not in path

    def test_path_to_newtons_second_law(self, flat_graph):
        path = learning_path(flat_graph, known=[], target="newtons_second_law")
        idx = {n: i for i, n in enumerate(path)}
        assert "velocity" in idx
        assert "acceleration" in idx
        assert idx["velocity"] < idx["acceleration"]

    def test_known_concepts_excluded(self, flat_graph):
        path = learning_path(flat_graph, known=["velocity", "acceleration"], target="newtons_second_law")
        assert "velocity" not in path
        assert "acceleration" not in path
        assert "newtons_second_law" in path

    def test_unknown_target_raises(self, flat_graph):
        with pytest.raises(ToolFailed, match="not in graph"):
            learning_path(flat_graph, known=[], target="nonexistent_concept")


# ===========================================================================
# gap
# ===========================================================================

class TestGap:
    def test_gap_nothing_known(self, flat_graph):
        g = gap(flat_graph, known=[], target="momentum")
        assert "momentum" in g
        assert "velocity" in g

    def test_gap_everything_known(self, flat_graph):
        all_nodes = list(flat_graph.nodes)
        g = gap(flat_graph, known=all_nodes, target="momentum")
        assert g == []

    def test_gap_partial_known(self, flat_graph):
        g = gap(flat_graph, known=["velocity"], target="momentum")
        assert "velocity" not in g
        assert "momentum" in g


# ===========================================================================
# enrichment_path
# ===========================================================================

class TestEnrichmentPath:
    def test_enrichment_for_newtons_second_law(self, unified_graph):
        enrichments = enrichment_path(unified_graph, known=[], target="newtons_second_law")
        # momentum is listed as enriched_by on newtons_second_law
        assert "momentum" in enrichments

    def test_no_enrichment_when_concept_not_on_path(self, unified_graph):
        # velocity has no enriched_by
        enrichments = enrichment_path(unified_graph, known=[], target="velocity")
        assert enrichments == []

    def test_known_enrichments_excluded(self, unified_graph):
        enrichments = enrichment_path(
            unified_graph, known=["momentum"], target="newtons_second_law"
        )
        assert "momentum" not in enrichments


# ===========================================================================
# build_order
# ===========================================================================

class TestBuildOrder:
    def test_returns_only_nodes(self, flat_graph):
        order = build_order(flat_graph)
        primitive_ids = set(flat_graph.primitives)
        assert not (set(order) & primitive_ids)

    def test_topological_order(self, flat_graph):
        order = build_order(flat_graph)
        idx = {n: i for i, n in enumerate(order)}
        assert idx["velocity"] < idx["acceleration"]
        assert idx["velocity"] < idx["momentum"]
        assert idx["acceleration"] < idx["newtons_second_law"]

    def test_reactive_build_order(self, reactive_graph):
        order = build_order(reactive_graph)
        idx = {n: i for i, n in enumerate(order)}
        # velocity_calculator must precede velocity_graph (depends_on)
        assert idx["velocity_calculator"] < idx["velocity_graph"]


# ===========================================================================
# validate_events
# ===========================================================================

class TestValidateEvents:
    def test_valid_reactive_graph(self, reactive_graph):
        warnings = validate_events(reactive_graph)
        # All events declared, all listeners/emitters valid
        # No warnings expected for this well-formed graph
        codes = [w.code for w in warnings]
        assert "UNHANDLED_EVENT" not in codes

    def test_undeclared_event_raises(self, undeclared_event_graph):
        with pytest.raises(ToolFailed, match="undeclared event"):
            validate_events(undeclared_event_graph)

    def test_warning_on_unemitted_event(self):
        """An event declared but never emitted → UNEMITTED_EVENT warning."""
        from tests.conftest import _load_yaml_str
        graph = _load_yaml_str("""
graph: orphan_event
version: "2.1"
domain_type: reactive_app

form:
  primitives:
    p:
      defines: p
      tier: 0
  nodes:
    listener_node:
      kind: widget
      defines: listens
      tier: 1
      composed_of: [p]

function:
  events:
    orphan:
      schema:
        data: str
  listeners:
    - node: listener_node
      event: orphan
      handle: handle_it
""")
        warnings = validate_events(graph)
        codes = [w.code for w in warnings]
        assert "UNEMITTED_EVENT" in codes


# ===========================================================================
# event_cycles
# ===========================================================================

class TestEventCycles:
    def test_no_cycles_in_simple_reactive(self, reactive_graph):
        # In this example the event graph is acyclic (slider → event → listeners)
        cycles = event_cycles(reactive_graph)
        assert cycles == []

    def test_cycle_detected(self):
        """Build a graph where a listener emits back to its own trigger event."""
        from tests.conftest import _load_yaml_str
        graph = _load_yaml_str("""
graph: cycle_test
version: "2.1"
domain_type: reactive_app

form:
  primitives:
    p:
      defines: p
      tier: 0
  nodes:
    node_a:
      kind: widget
      defines: a
      tier: 1
      composed_of: [p]
    node_b:
      kind: widget
      defines: b
      tier: 1
      composed_of: [p]

function:
  events:
    event_x:
      schema:
        data: str
    event_y:
      schema:
        data: str

  emitters:
    - from: node_a
      event: event_x
    - from: node_b
      event: event_y

  listeners:
    - node: node_b
      event: event_x
      handle: on_x
    - node: node_a
      event: event_y
      handle: on_y
""")
        cycles = event_cycles(graph)
        assert len(cycles) > 0


# ===========================================================================
# check_call_contracts
# ===========================================================================

class TestCheckCallContracts:
    def test_matching_contracts_no_violations(self, reactive_graph):
        violations = check_call_contracts(reactive_graph)
        assert violations == []

    def test_mismatched_contract_reported(self, contract_mismatch_graph):
        violations = check_call_contracts(contract_mismatch_graph)
        assert len(violations) == 1
        assert "bad_call" in violations[0]
        assert "mismatch" in violations[0].lower()


# ===========================================================================
# validate_transitions / flow_cycles (domain_type: workflow)
# ===========================================================================

class TestWorkflow:
    def test_flow_graph_built(self, workflow_graph):
        assert workflow_graph.flow_graph.has_edge("fetch", "transform")
        assert workflow_graph.flow_graph.has_edge("fetch", "fetch")

    def test_phases_carried_on_node_data(self, workflow_graph):
        phases = workflow_graph.nodes["fetch"]["phases"]
        assert "pre" in phases and "execute" in phases and "post" in phases
        assert "execute" in workflow_graph.nodes["transform"]["phases"]

    def test_form_graph_has_no_edges_among_steps(self, workflow_graph):
        # Steps aren't required to be reducible from primitives — no
        # composed_of/depends_on edges are declared between them.
        assert workflow_graph.form_graph.number_of_edges() == 0

    def test_valid_workflow_no_hard_errors(self, workflow_graph):
        warnings = validate_transitions(workflow_graph)
        assert all(isinstance(w, ValidationWarning) for w in warnings)

    def test_no_unreachable_steps(self, workflow_graph):
        warnings = validate_transitions(workflow_graph)
        codes = [w.code for w in warnings]
        assert "UNREACHABLE_STEP" not in codes

    def test_unreachable_step_warned(self):
        from tests.conftest import _load_yaml_str
        graph = _load_yaml_str("""
graph: unreachable_test
version: "2.1"
domain_type: workflow
entry: fetch

form:
  nodes:
    fetch:
      kind: step
      defines: fetch
      tier: 1
    transform:
      kind: step
      defines: transform
      tier: 1
    orphan_step:
      kind: step
      defines: never reached
      tier: 1

function:
  transitions:
    - from: fetch
      to: transform
      action: default
""")
        warnings = validate_transitions(graph)
        codes_and_nodes = [(w.code, w.context.get("node")) for w in warnings]
        assert ("UNREACHABLE_STEP", "orphan_step") in codes_and_nodes

    def test_undeclared_source_node_raises(self):
        from tests.conftest import _load_yaml_str
        graph = _load_yaml_str("""
graph: bad_transition_source
version: "2.1"
domain_type: workflow

form:
  nodes:
    transform:
      kind: step
      defines: transform
      tier: 1

function:
  transitions:
    - from: ghost_step
      to: transform
      action: default
""")
        with pytest.raises(ToolFailed, match="non-existent source node"):
            validate_transitions(graph)

    def test_undeclared_destination_node_raises(self):
        from tests.conftest import _load_yaml_str
        graph = _load_yaml_str("""
graph: bad_transition_dest
version: "2.1"
domain_type: workflow

form:
  nodes:
    fetch:
      kind: step
      defines: fetch
      tier: 1

function:
  transitions:
    - from: fetch
      to: ghost_step
      action: default
""")
        with pytest.raises(ToolFailed, match="non-existent destination node"):
            validate_transitions(graph)

    def test_ambiguous_routing_raises(self):
        from tests.conftest import _load_yaml_str
        graph = _load_yaml_str("""
graph: ambiguous_routing
version: "2.1"
domain_type: workflow

form:
  nodes:
    fetch:
      kind: step
      defines: fetch
      tier: 1
    transform:
      kind: step
      defines: transform
      tier: 1
    error_handler:
      kind: step
      defines: error_handler
      tier: 1

function:
  transitions:
    - from: fetch
      to: transform
      action: success
    - from: fetch
      to: error_handler
      action: success
""")
        with pytest.raises(ToolFailed, match="Ambiguous routing"):
            validate_transitions(graph)

    # -- schema v2.3: AND/OR fan-out on `to:`, exception-kind transitions,
    #    node-level `retry:` passthrough — see blueprint-schema-v2.2.md §7,
    #    added after sketching real SPL.py recipes as blueprint graphs
    #    surfaced these as concrete, scoped gaps (spl-recipe-blueprint-experiment.md).

    def test_and_fanout_list_to_adds_all_edges_no_ambiguity(self):
        from tests.conftest import _load_yaml_str
        graph = _load_yaml_str("""
graph: and_fanout
version: "2.1"
domain_type: workflow

form:
  nodes:
    fetch: {kind: step, defines: fetch, tier: 1}
    branch_a: {kind: step, defines: a, tier: 2}
    branch_b: {kind: step, defines: b, tier: 2}

function:
  transitions:
    - from: fetch
      to: [branch_a, branch_b]
      action: default
""")
        # Must not raise — one entry declaring both destinations is AND fan-out
        # by construction, not the "two separate entries disagree" case.
        validate_transitions(graph)
        assert graph.flow_graph.has_edge("fetch", "branch_a")
        assert graph.flow_graph.has_edge("fetch", "branch_b")
        assert graph.flow_graph["fetch"]["branch_a"]["branch_type"] == "and"
        assert graph.flow_graph["fetch"]["branch_b"]["branch_type"] == "and"

    def test_or_set_to_adds_all_edges_no_ambiguity(self):
        from tests.conftest import _load_yaml_str
        graph = _load_yaml_str("""
graph: or_branch
version: "2.1"
domain_type: workflow

form:
  nodes:
    urgency_router: {kind: step, defines: router, tier: 1}
    escalate: {kind: step, defines: escalate, tier: 2}
    draft: {kind: step, defines: draft, tier: 2}

function:
  transitions:
    - from: urgency_router
      to: {escalate, draft}
      action: default
      condition: "urgency > 8 -> escalate, else -> draft"
""")
        validate_transitions(graph)
        assert graph.flow_graph.has_edge("urgency_router", "escalate")
        assert graph.flow_graph.has_edge("urgency_router", "draft")
        assert graph.flow_graph["urgency_router"]["escalate"]["branch_type"] == "or"
        assert graph.flow_graph["urgency_router"]["draft"]["branch_type"] == "or"

    def test_single_string_to_still_branch_type_single(self, workflow_graph):
        assert workflow_graph.flow_graph["fetch"]["transform"]["branch_type"] == "single"

    def test_two_separate_entries_still_ambiguous_even_with_new_logic(self):
        # Regression guard: the ambiguity check must still fire for the
        # original failure mode (two independently-authored transitions that
        # accidentally disagree), not just get silently subsumed by the new
        # multi-destination-is-fine logic.
        from tests.conftest import _load_yaml_str
        graph = _load_yaml_str("""
graph: still_ambiguous
version: "2.1"
domain_type: workflow

form:
  nodes:
    fetch: {kind: step, defines: fetch, tier: 1}
    a: {kind: step, defines: a, tier: 2}
    b: {kind: step, defines: b, tier: 2}

function:
  transitions:
    - from: fetch
      to: a
      action: success
    - from: fetch
      to: b
      action: success
""")
        with pytest.raises(ToolFailed, match="Ambiguous routing"):
            validate_transitions(graph)

    def test_exception_kind_transition_carried_on_edge(self):
        from tests.conftest import _load_yaml_str
        graph = _load_yaml_str("""
graph: exception_routing
version: "2.1"
domain_type: workflow

form:
  nodes:
    summarize: {kind: step, defines: summarize, tier: 1}
    degraded_output: {kind: step, defines: degraded, tier: 2}

function:
  transitions:
    - from: summarize
      to: degraded_output
      action: on_context_exceeded
      kind: exception
""")
        assert graph.flow_graph["summarize"]["degraded_output"]["kind"] == "exception"

    def test_normal_transition_kind_defaults_to_normal(self, workflow_graph):
        assert workflow_graph.flow_graph["fetch"]["transform"]["kind"] == "normal"

    def test_retry_node_attribute_round_trips_with_no_loader_change(self):
        # form.nodes stores the full raw dict (loader.py's _build_graph_domain:
        # `nodes: dict[str, Any] = form.get("nodes") or {}`), so any new
        # node-level attribute is already accessible with zero loader code —
        # confirms this holds for the proposed `retry:` attribute specifically.
        #
        # Field is `when:`, not `on:` — an earlier draft used `on:`, discovered
        # (by this test failing on first write) to be a YAML 1.1 boolean
        # keyword: PyYAML parses an unquoted `on:` key as the boolean True,
        # not the string "on" — the same footgun GitHub Actions' own `on:`
        # trigger field is notorious for. Renamed to `when:` instead of
        # requiring every author to remember to quote it — `when:` also isn't
        # a YAML reserved word and matches SPL's own `EVALUATE ... WHEN ...
        # THEN` vocabulary. See blueprint-schema-v2.2.md §7.3.
        from tests.conftest import _load_yaml_str
        graph = _load_yaml_str("""
graph: retry_attr_test
version: "2.1"
domain_type: workflow

form:
  nodes:
    risky_step:
      kind: step
      defines: risky
      tier: 1
      retry:
        limit: 3
        when: HallucinationDetected
        params:
          temperature: 0.1
""")
        retry = graph.nodes["risky_step"]["retry"]
        assert retry["limit"] == 3
        assert retry["when"] == "HallucinationDetected"
        assert retry["params"]["temperature"] == 0.1

    def test_unknown_entry_raises(self):
        from tests.conftest import _load_yaml_str
        graph = _load_yaml_str("""
graph: bad_entry
version: "2.1"
domain_type: workflow
entry: ghost_step

form:
  nodes:
    fetch:
      kind: step
      defines: fetch
      tier: 1
""")
        with pytest.raises(ToolFailed, match="entry"):
            validate_transitions(graph)

    def test_flow_cycles_detects_retry_loop(self, workflow_graph):
        cycles = flow_cycles(workflow_graph)
        assert any("fetch" in c for c in cycles)

    def test_validate_full_runs_transition_checks(self, workflow_graph):
        warnings = validate_full(workflow_graph)
        assert all(isinstance(w, ValidationWarning) for w in warnings)


# ===========================================================================
# Example file integration tests
# ===========================================================================

class TestExampleFiles:
    def test_classical_mechanics_flat_acyclic(self, apps_dir):
        from appgraph.loader import load_domain
        g = load_domain(apps_dir / "classical_mechanics/blueprint/classical_mechanics_flat.graph.yaml")
        acyclic(g)

    def test_classical_mechanics_flat_reducible(self, apps_dir):
        from appgraph.loader import load_domain
        g = load_domain(apps_dir / "classical_mechanics/blueprint/classical_mechanics_flat.graph.yaml")
        assert reducible(g) is True

    def test_classical_mechanics_two_radical(self, apps_dir):
        from appgraph.loader import load_domain
        g = load_domain(apps_dir / "classical_mechanics/blueprint/classical_mechanics_flat.graph.yaml")
        assert reducible(g, first_radical_only=True) is False

    def test_classical_mechanics_unified_productivity_order(self, apps_dir):
        from appgraph.loader import load_domain
        g = load_domain(apps_dir / "classical_mechanics/blueprint/classical_mechanics.graph.yaml")
        order = productivity_order(g)
        assert "velocity" in order
        assert "newtons_second_law" in order

    def test_physics_simulator_valid_events(self, apps_dir):
        from appgraph.loader import load_domain
        g = load_domain(apps_dir / "physics_app/blueprint/physics_simulator.graph.yaml")
        warnings = validate_events(g)
        # Should be no hard errors; warnings about cycles are expected
        assert all(isinstance(w, ValidationWarning) for w in warnings)

    def test_auth_middleware_contract_ok(self, apps_dir):
        from appgraph.loader import load_domain
        g = load_domain(apps_dir / "physics_app/blueprint/auth_middleware.graph.yaml")
        violations = check_call_contracts(g)
        assert violations == []

    def test_classical_mechanics_unified_validate_full(self, apps_dir):
        from appgraph.loader import load_domain
        g = load_domain(apps_dir / "classical_mechanics/blueprint/classical_mechanics.graph.yaml")
        # enforce_two_radical: true in this example; validate_full must pass
        warnings = validate_full(g)
        assert all(isinstance(w, ValidationWarning) for w in warnings)

    def test_physics_simulator_validate_full(self, apps_dir):
        from appgraph.loader import load_domain
        g = load_domain(apps_dir / "physics_app/blueprint/physics_simulator.graph.yaml")
        warnings = validate_full(g)
        assert all(isinstance(w, ValidationWarning) for w in warnings)

    def test_etl_workflow_validate_full(self, apps_dir):
        from appgraph.loader import load_domain
        g = load_domain(apps_dir / "etl_workflow/blueprint/etl_workflow.graph.yaml")
        warnings = validate_full(g)
        assert all(isinstance(w, ValidationWarning) for w in warnings)

    def test_etl_workflow_retry_loop_is_a_flow_cycle(self, apps_dir):
        from appgraph.loader import load_domain
        g = load_domain(apps_dir / "etl_workflow/blueprint/etl_workflow.graph.yaml")
        cycles = flow_cycles(g)
        assert any("fetch_data" in c for c in cycles)


# ===========================================================================
# New schema fields: domain, target_languages, enforce_two_radical
# ===========================================================================

class TestNewSchemaFields:
    def test_domain_path_parsed(self, apps_dir):
        from appgraph.loader import load_domain
        g = load_domain(apps_dir / "classical_mechanics/blueprint/classical_mechanics.graph.yaml")
        assert g.domain == "science/physics/classical_mechanics"

    def test_target_languages_parsed(self, apps_dir):
        from appgraph.loader import load_domain
        g = load_domain(apps_dir / "physics_app/blueprint/auth_middleware.graph.yaml")
        assert "python" in g.target_languages

    def test_target_languages_multi(self, apps_dir):
        from appgraph.loader import load_domain
        g = load_domain(apps_dir / "physics_app/blueprint/main.graph.yaml")
        assert "python" in g.target_languages
        assert "javascript" in g.target_languages

    def test_enforce_two_radical_true(self, apps_dir):
        from appgraph.loader import load_domain
        g = load_domain(apps_dir / "classical_mechanics/blueprint/classical_mechanics.graph.yaml")
        assert g.enforce_two_radical is True

    def test_enforce_two_radical_default_false(self, flat_graph):
        assert flat_graph.enforce_two_radical is False

    def test_domain_type_integrated(self, apps_dir):
        from appgraph.loader import load_domain
        g = load_domain(apps_dir / "physics_app/blueprint/main.graph.yaml")
        assert g.domain_type == "integrated"

    def test_domain_path_flat_v1_passthrough(self, flat_graph):
        # flat v1.0 'domain: classical_mechanics' maps to both graph_id and domain
        assert flat_graph.domain == "classical_mechanics"

    def test_enforce_two_radical_triggers_on_violation(self):
        from tests.conftest import _load_yaml_str
        # A graph with only first-radical primitives and enforce_two_radical: true
        # should raise ToolFailed if all nodes are reducible from first radical
        g = _load_yaml_str("""
graph: single_radical_test
version: "2.1"
domain_type: curriculum
enforce_two_radical: true

form:
  primitives:
    position:
      defines: "first radical — position"
      tier: 0
      kind: state
    time:
      defines: "first radical — time"
      tier: 0
      kind: state

  first_radical_primitives: [position, time]

  nodes:
    velocity:
      kind: concept
      defines: "v = dx/dt"
      tier: 1
      composed_of: [position, time]
""")
        # velocity only needs position + time (both first radical) → Two-Radical violated
        with pytest.raises(ToolFailed, match="Two-Radical"):
            validate_full(g)

    def test_enforce_two_radical_passes_when_satisfied(self, apps_dir):
        from appgraph.loader import load_domain
        # classical_mechanics.graph.yaml has enforce_two_radical: true and
        # momentum requires mass (second radical) → should pass validate_full
        g = load_domain(apps_dir / "classical_mechanics/blueprint/classical_mechanics.graph.yaml")
        validate_full(g)  # no exception


class TestDrift:
    """docs/DEV/BUILD/blueprint-schema-v2.2.md §3's 5-component drift vector
    (structural/interface/intent/behavior/implementation) — intent is
    intentionally out of scope here (needs an LLM judge, see `appgraph drift
    --llm`); these cover the four components computable from the graphs alone.
    """

    _BASE = """
graph: widget_backend
version: "2.1"
domain_type: software

form:
  primitives:
    python:
      defines: "Python runtime"
      tier: 0
      kind: config
  nodes:
    data_schema:
      kind: concept
      defines: "Pydantic models"
      composed_of: [python]
      tier: 1
    api_routes:
      kind: module
      defines: "FastAPI routes"
      composed_of: [data_schema]
      tier: 2

function:
  exports:
    - name: list_widgets
      kind: port
      from: api_routes.list_widgets
      signature: "GET /widgets -> Widget[]"

verification:
  - node: api_routes
    backend: pytest
    tests: tests/test_routes.py
"""

    def test_identical_graphs_have_zero_drift(self):
        # mode="jaccard" is drift_report's default and now applies uniformly
        # to all 5 dims including intent (previously intent was always None
        # without a judge) — see drift_report()'s docstring.
        from tests.conftest import _load_yaml_str
        a = _load_yaml_str(self._BASE)
        b = _load_yaml_str(self._BASE)
        assert drift_report(a, b) == {
            "structural": 0.0,
            "interface": 0.0,
            "intent": 0.0,
            "behavior": 0.0,
            "implementation": 0.0,
            "overall": 0.0,
        }

    def test_intent_absent_without_judge_present_with_judge(self):
        # This tests mode="semantic" specifically — the one mode where
        # intent has no free approximation and genuinely needs a judge.
        from tests.conftest import _load_yaml_str
        a = _load_yaml_str(self._BASE)
        b = _load_yaml_str(self._BASE)
        assert intent_drift(a, b, mode="semantic") is None
        assert drift_report(a, b, mode="semantic")["intent"] is None
        judge = lambda dimension, text_a, text_b: 0.42
        assert intent_drift(a, b, mode="semantic", judge=judge) == 0.42
        assert drift_report(a, b, mode="semantic", judge=judge)["intent"] == 0.42

    def test_intent_text_includes_docs_field(self):
        from tests.conftest import _load_yaml_str
        a = _load_yaml_str(self._BASE.replace(
            'defines: "FastAPI routes"',
            'defines: "FastAPI routes"\n      docs: "README: this is the widgets API"',
        ))
        assert "README: this is the widgets API" in intent_text(a)

    def test_drift_report_dims_restricts_computation_and_output(self):
        # behavior (exact-tuple Jaccard) is maximal here since one field of
        # the verification entry changed, making the whole tuple mismatch —
        # but overall (cosine similarity over the *rendered text* of the
        # same entries) gives partial credit for the mostly-identical text,
        # so it's deliberately NOT equal to behavior's own 1.0 — see
        # drift_report()'s docstring on why overall != mean(selected dims).
        from tests.conftest import _load_yaml_str
        a = _load_yaml_str(self._BASE)
        b = _load_yaml_str(self._BASE.replace("tests/test_routes.py", "tests/test_routes_v2.py"))
        report = drift_report(a, b, dims=("behavior",))
        assert set(report) == {"behavior", "overall"}
        assert report["behavior"] == pytest.approx(1.0)
        assert 0.0 < report["overall"] < 1.0

    def test_drift_report_unknown_dim_raises(self):
        from tests.conftest import _load_yaml_str
        a = _load_yaml_str(self._BASE)
        b = _load_yaml_str(self._BASE)
        with pytest.raises(ValueError):
            drift_report(a, b, dims=("nonsense",))

    def test_structural_drift_detects_added_node_and_primitive(self):
        from tests.conftest import _load_yaml_str
        a = _load_yaml_str(self._BASE)
        b = _load_yaml_str(self._BASE.replace(
            "function:",
            """    extra_node:
      kind: doc
      defines: "readme"
      composed_of: [api_routes]
      tier: 3

function:""",
        ))
        assert structural_drift(a, b) > 0
        assert 0 < structural_drift(a, b) <= 1

    def test_interface_drift_detects_new_export(self):
        from tests.conftest import _load_yaml_str
        a = _load_yaml_str(self._BASE)
        b = _load_yaml_str(self._BASE.replace(
            'signature: "GET /widgets -> Widget[]"',
            'signature: "GET /widgets -> Widget[]"\n    - name: create_widget\n      kind: port\n'
            "      from: api_routes.create_widget\n"
            '      signature: "POST /widgets -> Widget"',
        ))
        assert interface_drift(a, b) == pytest.approx(0.5)

    def test_behavior_drift_detects_verification_change(self):
        from tests.conftest import _load_yaml_str
        a = _load_yaml_str(self._BASE)
        b = _load_yaml_str(self._BASE.replace("tests/test_routes.py", "tests/test_routes_v2.py"))
        assert behavior_drift(a, b) == pytest.approx(1.0)

    def test_implementation_drift_detects_primitive_change(self):
        from tests.conftest import _load_yaml_str
        a = _load_yaml_str(self._BASE)
        b = _load_yaml_str(self._BASE.replace(
            "    python:\n      defines: \"Python runtime\"\n      tier: 0\n      kind: config",
            "    python:\n      defines: \"Python runtime\"\n      tier: 0\n      kind: config\n"
            "    postgres:\n      defines: \"Postgres\"\n      tier: 0\n      kind: config",
        ))
        assert implementation_drift(a, b) == pytest.approx(0.5)

    def test_empty_verification_on_both_sides_is_zero_drift(self):
        from tests.conftest import _load_yaml_str
        no_verif = self._BASE.replace(
            'verification:\n  - node: api_routes\n    backend: pytest\n    tests: tests/test_routes.py\n',
            "",
        )
        a = _load_yaml_str(no_verif)
        b = _load_yaml_str(no_verif)
        assert behavior_drift(a, b) == 0.0


# ===========================================================================
# suggest_clusters: ancestor-closure clustering
# ===========================================================================

class TestSuggestClusters:
    """Mirrors the todo2A backend shape closely enough to catch the case
    that motivated the "ancestor of ALL seeds, not 2+" rule: `auth` is
    upstream of both auth_router and task_router (2 of 3 seeds) but must
    land in "shared", not "core", since it isn't upstream of user_router.
    """

    _GRAPH = """
graph: mini_backend
version: "2.1"
domain_type: software

form:
  primitives:
    python:
      defines: "Python runtime"
      tier: 0
      kind: config
  nodes:
    config:
      kind: concept
      defines: "App settings"
      composed_of: [python]
      tier: 1
    models:
      kind: concept
      defines: "ORM models"
      composed_of: [config]
      tier: 1
    auth:
      kind: module
      defines: "JWT auth helpers"
      composed_of: [models]
      tier: 2
    user_repo:
      kind: module
      defines: "User data access"
      composed_of: [models]
      tier: 2
    auth_router:
      kind: module
      defines: "Auth HTTP routes"
      composed_of: [auth, user_repo]
      tier: 3
    user_router:
      kind: module
      defines: "User HTTP routes"
      composed_of: [user_repo]
      tier: 3
    task_router:
      kind: module
      defines: "Task HTTP routes"
      composed_of: [auth]
      tier: 3
    main_app:
      kind: module
      defines: "App composition root"
      composed_of: [auth_router, user_router, task_router]
      tier: 4

function:
  exports:
    - name: login
      kind: port
      from: auth_router.login
    - name: register
      kind: port
      from: user_router.register
    - name: list_tasks
      kind: port
      from: task_router.list_tasks
"""

    def test_seeds_default_from_exports_deduped_and_port_stripped(self):
        from tests.conftest import _load_yaml_str
        graph = _load_yaml_str(self._GRAPH)
        result = suggest_clusters(graph)
        assert result["seeds"] == ["auth_router", "task_router", "user_router"]

    def test_core_is_ancestor_of_every_seed(self):
        from tests.conftest import _load_yaml_str
        graph = _load_yaml_str(self._GRAPH)
        result = suggest_clusters(graph)
        assert result["core"] == ["config", "models", "python"]

    def test_shared_dependency_not_folded_into_core(self):
        # auth is upstream of auth_router and task_router (2 of 3 seeds) but
        # not user_router — must be "shared", never "core".
        from tests.conftest import _load_yaml_str
        graph = _load_yaml_str(self._GRAPH)
        result = suggest_clusters(graph)
        assert "auth" not in result["core"]
        assert result["shared"]["auth_router+task_router"] == ["auth"]

    def test_user_repo_shared_between_auth_and_user_routers(self):
        from tests.conftest import _load_yaml_str
        graph = _load_yaml_str(self._GRAPH)
        result = suggest_clusters(graph)
        assert result["shared"]["auth_router+user_router"] == ["user_repo"]

    def test_exclusive_cluster_membership(self):
        from tests.conftest import _load_yaml_str
        graph = _load_yaml_str(self._GRAPH)
        result = suggest_clusters(graph)
        assert result["clusters"] == {
            "auth_router": ["auth_router"],
            "task_router": ["task_router"],
            "user_router": ["user_router"],
        }

    def test_composition_root_is_unclustered(self):
        from tests.conftest import _load_yaml_str
        graph = _load_yaml_str(self._GRAPH)
        result = suggest_clusters(graph)
        assert result["unclustered"] == ["main_app"]

    def test_explicit_seeds_override_exports(self):
        from tests.conftest import _load_yaml_str
        graph = _load_yaml_str(self._GRAPH)
        result = suggest_clusters(graph, seeds=["auth_router", "user_router"])
        assert result["seeds"] == ["auth_router", "user_router"]
        # task_router is no longer a seed, so its own subtree (task_router
        # itself) is now unclustered rather than its own cluster.
        assert "task_router" not in result["clusters"]
        assert "task_router" in result["unclustered"]
