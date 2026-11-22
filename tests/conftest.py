"""Shared pytest fixtures for graph_code tests."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from graph_code.loader import load_domain, GraphDomain

APPS_DIR = Path(__file__).parent.parent / "apps"


# ---------------------------------------------------------------------------
# Inline graph definitions (test isolation — no file I/O dependency)
# ---------------------------------------------------------------------------

FLAT_V1_YAML = """
domain: classical_mechanics

primitives:
  position:
    symbol: x
    defines: "first radical — where things are"
    tier: 0
  time:
    symbol: t
    defines: "first radical — the parameter"
    tier: 0
  mass:
    symbol: m
    defines: "second radical — inertia"
    tier: 0
  force:
    symbol: F
    defines: "second radical — interaction"
    tier: 0

first_radical_primitives: [position, time]

concepts:
  velocity:
    composed_of: [position, time]
    defines: "v = dx/dt"
    verifier: sympy
    lab: sympy.diff
    play: "differentiate x(t) = t**2"
    tier: 1
  acceleration:
    composed_of: [velocity, time]
    defines: "a = dv/dt"
    tier: 2
  momentum:
    composed_of: [mass, velocity]
    defines: "p = m*v"
    tier: 2
  newtons_second_law:
    composed_of: [force, mass, acceleration]
    defines: "F = m*a"
    tier: 3

applications:
  orbital_mechanics:
    uses: [newtons_second_law]
    defines: "Planetary orbit prediction"
"""

UNIFIED_V21_YAML = """
graph: classical_mechanics
version: "2.1"
domain_type: curriculum

form:
  primitives:
    position:
      symbol: x
      defines: "first radical — where things are"
      tier: 0
      kind: state
    time:
      symbol: t
      defines: "first radical — the parameter"
      tier: 0
      kind: state
    mass:
      symbol: m
      defines: "second radical — inertia"
      tier: 0
      kind: property
    force:
      symbol: F
      defines: "second radical — interaction"
      tier: 0
      kind: operator

  first_radical_primitives: [position, time]

  nodes:
    velocity:
      kind: concept
      defines: "v = dx/dt"
      tier: 1
      composed_of: [position, time]
    acceleration:
      kind: concept
      defines: "a = dv/dt"
      tier: 2
      composed_of: [velocity, time]
    momentum:
      kind: concept
      defines: "p = m*v"
      tier: 2
      composed_of: [mass, velocity]
    newtons_second_law:
      kind: concept
      defines: "F = m*a"
      tier: 3
      composed_of: [force, mass, acceleration]
      enriched_by: [momentum]

verification:
  - node: velocity
    backend: sympy
    lab: sympy.diff

applications:
  orbital_mechanics:
    uses: [newtons_second_law]
    defines: "Planetary orbit prediction"
"""

REACTIVE_YAML = """
graph: physics_simulator
version: "2.1"
domain_type: reactive_app

form:
  primitives:
    position_value:
      symbol: x
      defines: "current position"
      tier: 0
      kind: state

  nodes:
    position_slider:
      kind: widget
      defines: "slider that sets position"
      tier: 1
      composed_of: [position_value]
      emit: [position_updated]

    velocity_calculator:
      kind: module
      defines: "computes velocity"
      tier: 1
      composed_of: [position_value]

    velocity_graph:
      kind: widget
      defines: "chart of velocity over time"
      tier: 2
      depends_on: [velocity_calculator]
      listen:
        - event: position_updated
          handle: redraw_curve
          optional: false

    audit_logger:
      kind: service
      defines: "logs position changes"
      tier: 1
      listen:
        - event: position_updated
          handle: log_position_change
          optional: true

function:
  events:
    position_updated:
      schema:
        new_x: float
        timestamp: datetime
      contract:
        delivery: fire_and_forget
        ordering: event_loop_order

  emitters:
    - from: position_slider
      event: position_updated

  listeners:
    - node: velocity_graph
      event: position_updated
      handle: redraw_curve
      optional: false
    - node: audit_logger
      event: position_updated
      handle: log_position_change
      optional: true

  calls:
    - id: graph_uses_calculator
      from: velocity_graph.redraw_curve
      to: velocity_calculator.calculate
      contract:
        consumer_requires: "(x: float, dt: float) -> float"
        provider_guarantees: "(x: float, dt: float) -> float"
"""

CYCLIC_FORM_YAML = """
graph: cyclic_test
version: "2.1"
domain_type: curriculum

form:
  primitives:
    p:
      defines: "primitive"
      tier: 0

  nodes:
    a:
      kind: concept
      defines: "a"
      tier: 1
      composed_of: [b]
    b:
      kind: concept
      defines: "b"
      tier: 1
      composed_of: [a]
"""

UNDECLARED_EVENT_YAML = """
graph: bad_events
version: "2.1"
domain_type: reactive_app

form:
  primitives:
    p:
      defines: "p"
      tier: 0
  nodes:
    src:
      kind: widget
      defines: "source"
      tier: 1
      composed_of: [p]
      emit: [ghost_event]

function:
  events: {}
"""

CONTRACT_MISMATCH_YAML = """
graph: contract_mismatch
version: "2.1"
domain_type: software

form:
  primitives:
    p:
      defines: "p"
      tier: 0
  nodes:
    caller:
      kind: module
      defines: "caller"
      tier: 1
      depends_on: [p]
    callee:
      kind: module
      defines: "callee"
      tier: 1
      depends_on: [p]

function:
  calls:
    - id: bad_call
      from: caller.do_thing
      to: callee.do_thing
      contract:
        consumer_requires: "(x: int) -> str"
        provider_guarantees: "(x: str) -> int"
"""


WORKFLOW_YAML = """
graph: etl_test
version: "2.1"
domain_type: workflow
entry: fetch

form:
  nodes:
    fetch:
      kind: step
      defines: "fetch raw records"
      tier: 1
      phases:
        pre:
          defines: "validate query params"
          signature: "(shared: State) -> State"
        execute:
          defines: "call the API"
          signature: "(shared: State) -> ExecResult"
        post:
          defines: "merge into shared state; pick next action"
          signature: "(shared: State, exec_res: ExecResult) -> Action"
    transform:
      kind: step
      defines: "normalize records"
      tier: 1
      phases:
        execute:
          signature: "(shared: State) -> ExecResult"
    load:
      kind: step
      defines: "write to warehouse"
      tier: 1
      phases:
        execute:
          signature: "(shared: State) -> ExecResult"

function:
  transitions:
    - from: fetch
      to: transform
      action: success
    - from: fetch
      to: fetch
      action: retry
      condition: "attempts < 3"
    - from: transform
      to: load
      action: default
"""


BLUEPRINT_YAML = """
graph: blueprint_test
version: "2.1"
domain_type: software

blueprint:
  id: blueprint_test
  schema_version: "2.2"
  domain_type: software
  provenance: roundtrip
  parent_blueprint: blueprint_test_v1
  lineage:
    - pass: forward
      model: claude-sonnet-4-6
      adapter: claude_cli
      temperature: 0.2
      prompt_hash: "sha256:ab34"
      engine: build_component.spl
      timestamp: "2026-08-11T14:02:11Z"
    - pass: reverse
      model: claude-sonnet-4-6
      adapter: claude_cli
      temperature: 0.0
      prompt_hash: "sha256:7f2c"
      engine: graph-code-miner
      timestamp: "2026-08-11T14:31:47Z"
  drift:
    reference_blueprint: blueprint_test_v1
    vector:
      structural: 0.05
      interface: 0.0
      intent: 0.08
      behavior: 0.0
      implementation: 0.01

form:
  primitives:
    p:
      defines: "p"
      tier: 0
  nodes:
    n:
      kind: module
      defines: "n"
      tier: 1
      composed_of: [p]
"""


def _load_yaml_str(content: str) -> GraphDomain:
    import tempfile, os
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, encoding="utf-8"
    ) as fh:
        fh.write(content)
        tmp = fh.name
    try:
        return load_domain(tmp)
    finally:
        os.unlink(tmp)


@pytest.fixture
def flat_graph() -> GraphDomain:
    return _load_yaml_str(FLAT_V1_YAML)


@pytest.fixture
def unified_graph() -> GraphDomain:
    return _load_yaml_str(UNIFIED_V21_YAML)


@pytest.fixture
def reactive_graph() -> GraphDomain:
    return _load_yaml_str(REACTIVE_YAML)


@pytest.fixture
def cyclic_graph() -> GraphDomain:
    return _load_yaml_str(CYCLIC_FORM_YAML)


@pytest.fixture
def undeclared_event_graph() -> GraphDomain:
    return _load_yaml_str(UNDECLARED_EVENT_YAML)


@pytest.fixture
def contract_mismatch_graph() -> GraphDomain:
    return _load_yaml_str(CONTRACT_MISMATCH_YAML)


@pytest.fixture
def workflow_graph() -> GraphDomain:
    return _load_yaml_str(WORKFLOW_YAML)


@pytest.fixture
def blueprint_graph() -> GraphDomain:
    return _load_yaml_str(BLUEPRINT_YAML)


@pytest.fixture
def apps_dir() -> Path:
    return APPS_DIR
