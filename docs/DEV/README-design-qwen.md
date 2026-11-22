I'll produce the definitive **Unified Duality Graph Schema v2.1** specification, integrating the ConceptBook paper's existing schema, the Graph-Code software synthesis extensions, the event-driven architecture, and all the refinements we've discussed. This is designed to be saved as a reference document in your repository.

---

# Unified Duality Graph Schema v2.1

**Version:** 2.1
**Status:** Draft for implementation
**Compatibility:** Backward-compatible with ConceptBook v1.0 flat YAML
**Repository:** `github.com/digital-duck/SPL.py`

---

## 1. Design Principles

```text
1. One schema, multiple compilation targets.
   The domain_type field selects the compilation profile:
   - curriculum    → ConceptBook textbook generation
   - software      → Graph-Code multi-file code synthesis
   - reactive_app  → Event-driven application generation
   - hybrid        → Any combination of the above

2. Form/Function duality enforced at schema level.
   - form:     topology, states, build dependencies (DAG, must be acyclic)
   - function: interactions, operations, runtime behavior (may contain cycles)

3. Two-Radical structure preserved.
   - first_radical_primitives: FORM class (Objects/States)
   - remaining primitives: SOUND class (Operations/Transformations)
   - graph_lib.reducible(first_radical_only) must return False

4. Graph composition via import/export/call/emit/listen.
   - import:  bind external graph into current scope
   - export:  expose internal port or event as public interface
   - call:    direct synchronous invocation edge
   - emit:    asynchronous event production
   - listen:  asynchronous event subscription
   - handle:  function/workflow invoked on event receipt

5. Events are first-class graph vertices.
   An event is not a hidden runtime mechanism. It is a typed,
   schema-declared vertex in the graph, connected to emitters
   and listeners by explicit edges.

6. Verification is a first-class concern.
   Every node may carry a verifier tag. Every event may carry
   a schema contract. Every call edge may carry a compatibility
   contract. Human review is the verifier of record where no
   computable oracle exists (ConceptBook §7.4).

7. Optional elements are path-relative, not absolute.
   A concept may be required for one learning path but optional
   for another. Optionality is expressed through separate fields
   (enriched_by, optionally_depends_on) rather than boolean flags
   on mandatory fields, preserving backward compatibility.
```

---

## 2. YAML Style Convention

All multi-line values in this schema use the **literal block scalar** `|`. Single-line values use plain scalars. The folded block scalar `>` is not used.

| Situation | Syntax | Example |
|---|---|---|
| Value fits on one line | Plain scalar | `defines: "rate of change of position"` |
| Value spans multiple lines | `|` (literal) | `comment: |` followed by indented lines |
| Code snippet, no trailing newline | `|-` (literal, strip) | `lab: |-` followed by code |

Rationale: if a value belongs on one line, write it on one line. The moment a value spans multiple lines, the author's line breaks are intentional and should be preserved. Using `>` to fold lines back together undoes the author's decision to break them apart.

---

## 3. Schema Specification

### 3.1 Top-Level Structure

```yaml
# ================================================================
# UNIFIED DUALITY GRAPH SCHEMA v2.1
# ================================================================

graph: <graph_id>                    # unique identifier for this graph
version: "2.1"                       # schema version
domain_type: curriculum | software | reactive_app | hybrid

# Optional: human-readable description
description: |
  A multi-line description of what this graph represents,
  its intended audience, and its compilation target.

# Optional: persistent annotation visible to LLM and UI
comment: |
  Authoring rationale, known limitations, or cross-domain
  connections relevant to this graph as a whole.
```

### 3.2 Form Space

The Form space defines **what things are**: topology, states, primitives, and build dependencies. It must be a directed acyclic graph (DAG). The SPL workflow's `productivity_order()` and ConceptBook's `graph_lib.acyclic()` operate on this space.

```yaml
form:

  # ----------------------------------------------------------
  # 3.2.1 Primitives: The irreducible brick set (tier 0)
  # ----------------------------------------------------------
  primitives:
    <primitive_id>:
      symbol: <string>              # e.g., "x", "F", "m", "Cart"
      defines: <string>             # one-sentence definition
      tier: 0                       # always 0 for primitives
      kind: state | operator | property | config | type
      comment: |                    # optional persistent annotation
        Authoring rationale or pedagogical note.

  # The FORM class of primitives (Objects/States).
  # graph_lib.reducible(first_radical_only) must return False.
  # This encodes the Two-Radical irreducibility theorem.
  first_radical_primitives: [<primitive_id>, ...]

  # ----------------------------------------------------------
  # 3.2.2 Nodes: Concepts / Modules / Components / Widgets
  # ----------------------------------------------------------
  nodes:
    <node_id>:
      kind: concept | module | component | widget | service | graph
      defines: <string>             # what this node IS
      tier: <int>                   # 1 + max(prerequisite tiers)
      comment: |                    # optional persistent annotation

      # Mandatory composition dependencies (Form DAG edges).
      # For curriculum: cognitive prerequisites.
      # For software: build/import dependencies.
      composed_of: [<node_or_primitive_id>, ...]

      # Optional enrichment (curriculum graphs).
      # These concepts enhance understanding but are not
      # strictly required to reach the capstone.
      enriched_by: [<node_id>, ...]

      # Mandatory structural dependencies (software graphs).
      depends_on: [<node_id>, ...]

      # Optional structural dependencies (software graphs).
      # System functions without these, with reduced capability.
      optionally_depends_on: [<node_id>, ...]

      # For nested graphs: reference to subgraph file.
      # Only used when kind: graph.
      graph: <path_to_graph_yaml>

      # Ports: the interaction endpoints of this node.
      # Used in software and reactive_app profiles.
      ports:
        <port_id>:
          signature: <string>       # e.g., "(x: float, dt: float) -> float"
          kind: call | emit | listen | handle
          direction: in | out | bidirectional
          comment: |

      # Event-driven: what this node emits.
      emit: [<event_id>, ...]

      # Event-driven: what this node listens to.
      listen:
        - event: <event_id>
          handle: <handler_name>
          optional: <bool>          # listener is optional
          comment: |

      # Verification (curriculum profile).
      verifier: sympy | sage | lean | structural | pytest | mypy | jest | <named_tool>
      lab: <string>                 # executable worked example
      play: <string>                # student/user exercise

  # ----------------------------------------------------------
  # 3.2.3 Edges: Structural / Build Dependencies
  # ----------------------------------------------------------
  # Edges are implicitly generated from composed_of, depends_on,
  # enriched_by, and optionally_depends_on fields on nodes.
  # Explicit edge declarations are optional and used only when
  # additional metadata (comment, optional flag) is needed.
  edges:
    - from: <node_id>
      to: <node_or_primitive_id>
      kind: composed_of | depends_on | imports | enriched_by | optionally_depends_on
      comment: |
```

### 3.3 Function Space

The Function space defines **what things do**: interactions, operations, events, and runtime behavior. Unlike the Form space, the Function space may contain cycles (event loops, reactive feedback). The event-driven extensions live here.

```yaml
function:

  # ----------------------------------------------------------
  # 3.3.1 Events: Typed asynchronous occurrences
  # ----------------------------------------------------------
  # Events are first-class graph vertices. Each event has a
  # schema (Form) and participates in emit/listen edges (Function).
  events:
    <event_id>:
      schema:
        <field_name>: <type>
      contract:
        delivery: fire_and_forget | at_least_once | exactly_once | request_reply
        ordering: event_loop_order | timestamp_order | unordered
        idempotent_handler_required: <bool>
      comment: |

  # ----------------------------------------------------------
  # 3.3.2 Synchronous Calls: Direct invocation edges
  # ----------------------------------------------------------
  calls:
    - id: <call_id>
      from: <node_id.port_id>
      to: <node_id.port_id>
      optional: <bool>
      contract:
        consumer_requires: <string>
        provider_guarantees: <string>
      comment: |

  # ----------------------------------------------------------
  # 3.3.3 Asynchronous Emitters: Who produces events
  # ----------------------------------------------------------
  emitters:
    - from: <node_id>
      event: <event_id>
      comment: |

  # ----------------------------------------------------------
  # 3.3.4 Asynchronous Listeners: Who reacts to events
  # ----------------------------------------------------------
  listeners:
    - node: <node_id>
      event: <event_id>
      handle: <handler_name>
      optional: <bool>
      comment: |

  # ----------------------------------------------------------
  # 3.3.5 Exports: Public interface of this graph
  # ----------------------------------------------------------
  exports:
    - name: <public_name>
      kind: port | event
      from: <node_id.port_id | event_id>
      signature: <string>           # optional, for ports
      contract: <string>            # optional
      comment: |
```

### 3.4 Verification

The Verification section unifies ConceptBook's per-concept verifier tags with Graph-Code's test suites. It is optional; nodes without verification are still valid but rely on human review as the verifier of record (ConceptBook §7.4).

```yaml
verification:
  # Node-level verification
  - node: <node_id>
    backend: sympy | sage | lean | structural | pytest | mypy | jest | <named_tool>
    lab: <string>
    play: <string>
    tests: <path_to_test_file>      # for software domains
    comment: |

  # Event-level verification
  - event: <event_id>
    check: schema_compatibility | sequence_validity | no_deadlock
    max_depth: <int>                # for cycle detection
    comment: |
```

### 3.5 Composition: Graph of Graphs

The Composition section enables importing external graphs and composing them into the current graph. This is the mechanism by which large systems are built from smaller, independently verified subgraphs.

```yaml
imports:
  - id: <alias>
    graph: <path_to_graph_yaml>
    optional: <bool>                # import is optional
    # Optional: restrict which exports are imported
    exports: [<export_name>, ...]
    # Optional: rename imported exports
    bind:
      <remote_name>: <local_name>
    comment: |
```

### 3.6 Applications / Capstone

The Applications section lists downstream use-cases that the capstone concept unlocks. In the curriculum profile, these populate the capstone "Payoff" section of the generated book (ConceptBook §4.1). In the software profile, these represent deployment targets or integration points.

```yaml
applications:
  <application_id>:
    uses: [<node_id>, ...]
    defines: <string>
    comment: |
```

---

## 4. Event-Driven Extensions

This section specifies the semantics of the event-driven architecture in detail. These extensions are activated when `domain_type` is `reactive_app` or `hybrid`, or when any node declares `emit` or `listen` fields.

### 4.1 Event Declarations

An event is a **typed, schema-declared vertex** in the graph. It is not a string label or a hidden runtime mechanism. Every event must be declared before it can be emitted or listened to.

```yaml
function:
  events:
    position_updated:
      schema:
        new_x: float
        timestamp: datetime
      contract:
        delivery: fire_and_forget
        ordering: event_loop_order
      comment: |
        Emitted by the position slider whenever the user
        changes the slider value. All downstream visualizations
        should subscribe to this event rather than polling
        the slider state directly.
```

**Validation rule:** Every event referenced by an `emit` or `listen` entry must be declared in the `events` section. Undeclared events cause a `ToolFailed` error at graph load time, before any LLM call.

### 4.2 Emitters

An emitter is a directed edge from a node to an event vertex. It declares that the node **can produce** the specified event.

```yaml
function:
  emitters:
    - from: position_slider
      event: position_updated
      comment: |
        The slider emits position_updated on every change event,
        debounced at 16ms to match the display refresh rate.
```

**Canonical graph representation:**

```text
position_slider --[emits]--> position_updated
```

**Validation rule:** The emitting node must exist in `form.nodes`. The event must exist in `function.events`.

### 4.3 Listeners and Handlers

A listener is a directed edge from an event vertex to a node. It declares that the node **subscribes to** the specified event. The `handle` field binds the event to a specific handler function or workflow within the node.

```yaml
function:
  listeners:
    - node: velocity_graph
      event: position_updated
      handle: redraw_curve
      optional: false
      comment: |
        The velocity graph must redraw whenever position changes.
        This listener is mandatory for correct visualization.

    - node: audit_logger
      event: position_updated
      handle: log_position_change
      optional: true
      comment: |
        Audit logging is optional. The visualization functions
        correctly without it.
```

**Canonical graph representation:**

```text
position_updated --[notifies]--> velocity_graph.redraw_curve
position_updated --[notifies]--> audit_logger.log_position_change
```

**Validation rules:**
- The listening node must exist in `form.nodes`.
- The event must exist in `function.events`.
- The `handle` field must reference a valid handler within the node.
- If `optional` is not specified, it defaults to `false`.

### 4.4 Event Graph Semantics

The event graph is a **bipartite subgraph** of the full graph, with two types of vertices (nodes and events) and two types of edges (emits and notifies).

```text
Full Graph:
  V = form.nodes ∪ function.events
  E = form.edges ∪ function.emitters ∪ function.listeners ∪ function.calls

Event Subgraph:
  V_event = function.events
  E_event = function.emitters ∪ function.listeners
```

**Key semantic properties:**

| Property | Form Space | Event Subgraph |
|---|---|---|
| Acyclicity | **Required** (DAG) | **Not required** (cycles are normal in event loops) |
| Topological sort | Used for `productivity_order` | Not applicable |
| Cycle detection | `graph_lib.acyclic()` raises error | `graph_lib.event_cycles()` warns unless declared intentional |
| Determinism | Deterministic given same graph and α | Depends on event loop semantics |

**Event cycle handling:**

Event cycles are common in GUI and reactive systems (e.g., user action → state update → re-render → user action). The schema supports them but requires explicit declaration:

```yaml
verification:
  - event: position_updated
    check: no_deadlock
    max_depth: 10
    comment: |
      This event participates in a reactive cycle:
      position_updated -> redraw -> user_input -> position_updated.
      The cycle is intentional and bounded by the debounce interval.
```

If an event cycle is detected and not declared in `verification`, `graph_lib.validate_events()` raises a warning. If `max_depth` is exceeded during runtime simulation, the event loop terminates with a deadlock error.

### 4.5 Event-Driven GUI Model

The event-driven extensions are designed to model GUI architectures following the pattern established by Fowler (2006) and the Elm Architecture (Czaplicki, 2012). A GUI event loop has four components, each mapping to a graph element:

| GUI Component | Graph Element | Schema Field |
|---|---|---|
| Event source (button, slider) | Node with `emit` | `form.nodes.X.emit` |
| Event type (click, change) | Event vertex | `function.events` |
| Dispatcher / event loop | Runtime (not a graph element) | SPL event loop |
| Handler (callback, reducer) | Node with `listen` + `handle` | `function.listeners` |

The event loop itself is a **runtime mechanism**, not a graph vertex. It is provided by the SPL runtime or the target language's event system (e.g., JavaScript `EventEmitter`, Python `asyncio`, DOM event dispatch). The graph specifies **what** is wired; the runtime provides **how** it executes.

---

## 5. Examples

### 5.1 ConceptBook Curriculum — Backward-Compatible Flat Format

This is the exact format used in the ConceptBook paper (v1.0). The v2.1 loader accepts this format and internally normalizes it to the unified structure.

```yaml
domain: classical_mechanics

primitives:
  position:
    symbol: x
    defines: "first radical — configuration; where things are"
    tier: 0
  time:
    symbol: t
    defines: "first radical — the parameter motion unfolds in"
    tier: 0
  mass:
    symbol: m
    defines: "second radical — inertia; resistance to changes in motion"
    tier: 0
  force:
    symbol: F
    defines: "second radical — interaction; what changes states of motion"
    tier: 0

first_radical_primitives: [position, time]

concepts:
  velocity:
    composed_of: [position, time]
    defines: "rate of change of position — v = dx/dt"
    verifier: sympy
    lab: sympy.diff
    play: "differentiate x(t) = t**2; compare v(t) against the difference quotient"
    tier: 1
  momentum:
    composed_of: [mass, velocity]
    defines: "p = m·v — the conserved currency of motion"
    verifier: sage|sympy
    lab: "graph_lib.verify_momentum_conservation"
    tier: 2
  normal_modes:
    composed_of: [eigenvalue, superposition, constraints]
    defines: "the natural oscillation frequencies of a coupled system"
    verifier: sympy
    tier: 5

applications:
  orbital_mechanics:
    uses: [normal_modes, conservation_of_energy]
  robotics:
    uses: [constraints, lagrangian_mechanics]
```

**Normalization mapping:**

| Flat Format Field | Unified v2.1 Location |
|---|---|
| `domain` | `graph` |
| `primitives` | `form.primitives` |
| `first_radical_primitives` | `form.first_radical_primitives` |
| `concepts` | `form.nodes` (with `kind: concept`) |
| `concepts.X.composed_of` | `form.edges` (with `kind: composed_of`) |
| `concepts.X.verifier/lab/play` | `verification` entries |
| `applications` | `applications` |

### 5.2 ConceptBook Curriculum — Unified v2.1 Format

The same domain expressed in the full v2.1 schema, with `comment` and `enriched_by` additions.

```yaml
graph: classical_mechanics
version: "2.1"
domain_type: curriculum

form:
  primitives:
    position:
      symbol: x
      defines: "first radical — configuration; where things are"
      tier: 0
      kind: state
      comment: |
        Chosen as a first-radical primitive. All kinematic
        quantities derive from position and time. Do not
        conflate with displacement, which is a derived
        concept at tier 1.
    time:
      symbol: t
      defines: "first radical — the parameter motion unfolds in"
      tier: 0
      kind: state
    mass:
      symbol: m
      defines: "second radical — inertia; resistance to changes in motion"
      tier: 0
      kind: property
    force:
      symbol: F
      defines: "second radical — interaction; what changes states of motion"
      tier: 0
      kind: operator
      comment: |
        The concept of force is the bridge between kinematics
        (first radical) and dynamics (second radical). Newton's
        second law F=ma is the composition rule.

  first_radical_primitives: [position, time]

  nodes:
    velocity:
      kind: concept
      defines: "rate of change of position — v = dx/dt"
      tier: 1
      composed_of: [position, time]
      verifier: sympy
      lab: sympy.diff
      play: "differentiate x(t) = t**2; compare v(t) against the difference quotient"
      comment: |
        Emphasize the limit process from average to instantaneous
        velocity. Students often conflate speed with velocity.
    momentum:
      kind: concept
      defines: "p = m·v — the conserved currency of motion"
      tier: 2
      composed_of: [mass, velocity]
      verifier: sage|sympy
      lab: "graph_lib.verify_momentum_conservation"
    normal_modes:
      kind: concept
      defines: "the natural oscillation frequencies of a coupled system"
      tier: 5
      composed_of: [eigenvalue, superposition]
      enriched_by: [constraints, fourier_analysis]
      verifier: sympy
      comment: |
        constraints and fourier_analysis are listed as enrichment
        because normal modes can be introduced through eigenvalue
        analysis alone. Adding constraints deepens the treatment
        for advanced learners but is not required for the capstone.

verification:
  - node: velocity
    backend: sympy
    lab: sympy.diff
    play: "differentiate x(t) = t**2; compare v(t) against the difference quotient"
  - node: momentum
    backend: sage|sympy
    lab: "graph_lib.verify_momentum_conservation"
  - node: normal_modes
    backend: sympy

applications:
  orbital_mechanics:
    uses: [normal_modes, conservation_of_energy]
    defines: "Predict planetary orbits from gravitational normal modes"
    comment: |
      This application bridges classical mechanics and quantum
      mechanics via the correspondence principle.
  robotics:
    uses: [constraints, lagrangian_mechanics]
    defines: "Design robotic arms using constrained dynamics"
```

### 5.3 Graph-Code Software Architecture

A multi-file software system with synchronous calls and graph composition.

```yaml
graph: auth_middleware
version: "2.1"
domain_type: software

imports:
  - id: jwt
    graph: ./jwt_provider.graph.yaml
    comment: |
      The JWT provider is a mandatory dependency. The
      middleware cannot function without token verification.

form:
  nodes:
    middleware:
      kind: module
      defines: "Protects routes by verifying JWT tokens"
      tier: 1
      depends_on: [jwt]
      optionally_depends_on: [audit_logger]
      comment: |
        audit_logger is optional. The middleware functions
        correctly without it, but production deployments
        should include it for compliance.
      ports:
        require_auth:
          signature: "(request: Request, handler: Handler) -> Response"
          kind: call
          direction: out

function:
  calls:
    - id: middleware_calls_jwt_verify
      from: middleware.require_auth
      to: jwt.verify_token
      contract:
        consumer_requires: "(token: str) -> TokenPayload"
        provider_guarantees: "(token: str) -> TokenPayload"
      comment: |
        This is the critical interface contract. If the JWT
        provider changes its verify_token signature, this
        call edge will fail validation at graph load time,
        before any code is generated.

  exports:
    - name: require_auth
      kind: port
      from: middleware.require_auth
      signature: "(request: Request, handler: Handler) -> Response"
      comment: |
        Primary public API. Do not expose internal
        token_parsing or error_formatting functions.

verification:
  - node: middleware
    backend: pytest
    tests: "tests/test_auth_middleware.py"
```

### 5.4 Reactive GUI App — Event-Driven

An interactive physics simulator with event-driven architecture.

```yaml
graph: physics_simulator
version: "2.1"
domain_type: reactive_app

form:
  primitives:
    position_value:
      symbol: x
      defines: "The current position of the simulated object"
      tier: 0
      kind: state
      comment: |
        This is the single source of truth for the object's
        position. All visualizations derive from this value.

  nodes:
    position_slider:
      kind: widget
      defines: "A slider that lets the user set position"
      tier: 1
      composed_of: [position_value]
      emit: [position_updated]
      comment: |
        The slider is the only emitter of position_updated.
        No other component should emit this event directly.

    velocity_calculator:
      kind: module
      defines: "Computes velocity from position changes"
      tier: 1
      composed_of: [position_value]
      ports:
        calculate:
          signature: "(x: float, dt: float) -> float"
          kind: call
          direction: out

    velocity_graph:
      kind: widget
      defines: "A chart that visualizes velocity over time"
      tier: 2
      depends_on: [velocity_calculator]
      listen:
        - event: position_updated
          handle: redraw_curve
          optional: false
          comment: |
            The velocity graph must redraw whenever position
            changes. This listener is mandatory.

    audit_logger:
      kind: service
      defines: "Logs all position changes for debugging"
      tier: 1
      listen:
        - event: position_updated
          handle: log_position_change
          optional: true
          comment: |
            Audit logging is optional. The simulator functions
            correctly without it.

function:
  events:
    position_updated:
      schema:
        new_x: float
        timestamp: datetime
      contract:
        delivery: fire_and_forget
        ordering: event_loop_order
      comment: |
        Emitted by the position slider on every change event.
        All downstream visualizations subscribe to this event
        rather than polling the slider state.

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

  exports:
    - name: calculate_velocity
      kind: port
      from: velocity_calculator.calculate
      signature: "(x: float, dt: float) -> float"
    - name: on_position_update
      kind: event
      from: position_updated

verification:
  - node: velocity_calculator
    backend: pytest
    tests: "tests/test_velocity_calculator.py"
  - event: position_updated
    check: schema_compatibility
  - event: position_updated
    check: no_deadlock
    max_depth: 10
    comment: |
      This event participates in a reactive cycle:
      position_updated -> redraw -> user_input -> position_updated.
      The cycle is intentional and bounded by the debounce interval.
```

### 5.5 Graph Composition — Parent Graph Importing Subgraphs

A top-level application graph composing multiple subgraphs.

```yaml
graph: physics_app
version: "2.1"
domain_type: hybrid

imports:
  - id: simulator
    graph: ./physics_simulator.graph.yaml
    comment: |
      The core simulation engine. Mandatory.
  - id: auth
    graph: ./auth_middleware.graph.yaml
    optional: true
    comment: |
      Authentication is optional for the desktop version.
      Required only for the web deployment.

form:
  nodes:
    app_shell:
      kind: component
      defines: "Top-level application shell with navigation"
      tier: 1
      depends_on: [simulator]
      optionally_depends_on: [auth]

function:
  calls:
    - id: shell_uses_simulator
      from: app_shell.render_simulator
      to: simulator.calculate_velocity

  exports:
    - name: run_app
      kind: port
      from: app_shell.main
      signature: "() -> void"
```

---

## 6. Validation Rules

The `graph_lib` validator enforces these rules on every graph load, before any LLM call. Failure raises `ToolFailed` and halts the pipeline.

### 6.1 Form Space Validation

| Rule | Check | Applies To |
|---|---|---|
| Acyclicity | `graph_lib.acyclic(form_graph)` — no cycles in build DAG | All profiles |
| Reducibility | `graph_lib.reducible(graph, primitives)` — every node traces to primitives | All profiles |
| Two-Radical Irreducibility | `graph_lib.reducible(first_radical_only)` returns `False` | Curriculum |
| Tier Consistency | Every node's tier = 1 + max(prerequisite tiers) | All profiles |
| Enrichment Validity | Every `enriched_by` target exists and is reducible | Curriculum |
| Optional Dependency Validity | Every `optionally_depends_on` target exists | Software |

### 6.2 Function Space Validation

| Rule | Check | Applies To |
|---|---|---|
| Event Declaration | Every emitted/listened event is declared in `function.events` | Reactive |
| Event Schema Validity | Every declared event has a non-empty `schema` | Reactive |
| Emitter Validity | Every emitter's `from` node exists in `form.nodes` | Reactive |
| Listener Validity | Every listener's `node` exists in `form.nodes` | Reactive |
| Handler Existence | Every `handle` reference points to a valid handler | Reactive |
| Port Signature Compatibility | Every call edge has compatible consumer/provider signatures | Software |
| Export Source Validity | Every export references an existing internal port or event | Software, Reactive |
| Import Resolution | Every imported graph exists and exports the referenced names | Composition |

### 6.3 Event-Specific Validation

| Rule | Check | Severity |
|---|---|---|
| Unhandled Event | Event with no listeners | Warning |
| Unemitted Listener | Listener with no emitter | Warning |
| Event Cycle | Cycle detected in event subgraph | Warning (unless declared intentional in `verification`) |
| Event Deadlock | `max_depth` exceeded in cycle simulation | Error |
| Schema Mismatch | Emitter schema incompatible with listener expectations | Error |

### 6.4 Cross-Space Validation

| Rule | Check | Applies To |
|---|---|---|
| Form-Function Consistency | Every node referenced in `function` exists in `form` | All profiles |
| Verification Coverage | Every node with a `verifier` tag has a matching `verification` entry | Curriculum |
| Comment Persistence | All `comment` fields are preserved through load → validate → serialize round-trip | All profiles |

---

## 7. Compilation Targets

The `domain_type` field selects the SPL compilation profile. Each profile uses a subset of the schema.

| `domain_type` | SPL Workflow | Schema Sections Used | Output |
|---|---|---|---|
| `curriculum` | `build_concept_book.spl` | `form`, `verification`, `applications` | Prerequisite-ordered textbook (HTML/Markdown) |
| `software` | `build_app.spl` | `form`, `function`, `verification`, `imports` | Multi-file source code with tests |
| `reactive_app` | `build_reactive_app.spl` | `form`, `function`, `verification`, `imports` | Event-driven application with event bus wiring |
| `hybrid` | `build_system_book.spl` | All sections | Code + documentation + interactive tutorial |

### 7.1 Curriculum Profile

The SPL workflow `build_concept_book.spl` (ConceptBook Appendix A.1) operates as follows:

1. **Load and validate:** `setup_domain()` parses the graph, asserts acyclicity and reducibility, computes teaching sequence via `productivity_order()`.
2. **Generate and verify:** For each concept in dependency order, generate a section, enforce primitive budget, run domain verifier, cache the result.
3. **Capstone:** Generate payoff section from `applications` list.

The `function` space is ignored in this profile. The `enriched_by` field influences `learning_path()` and `gap()` but does not affect `productivity_order()`.

### 7.2 Software Profile

The SPL workflow `build_app.spl` operates as follows:

1. **Load and validate:** Parse the graph, assert acyclicity of `form`, validate all call edge contracts.
2. **Resolve imports:** Load imported graphs, namespace their exports.
3. **Topological generation:** Generate module code in dependency order, using `form.edges` to determine build sequence.
4. **Interface verification:** After each module is generated, verify that its exported ports match the call edge contracts.
5. **Test execution:** Run `verification` test suites.
6. **Repair loop:** If tests fail, feed error output back to the LLM for localized repair.

### 7.3 Reactive App Profile

The SPL workflow `build_reactive_app.spl` extends the software profile with event-driven wiring:

1. **Load and validate:** Parse the graph, assert acyclicity of `form`, validate event declarations and listener/emitter consistency.
2. **Resolve imports:** Load imported graphs, namespace their exports.
3. **Topological generation:** Generate component code in dependency order.
4. **Event bus wiring:** Generate event bus glue code from `function.events`, `function.emitters`, and `function.listeners`.
5. **Event cycle check:** Run `graph_lib.event_cycles()` and verify against `verification` declarations.
6. **Test execution:** Run `verification` test suites, including event sequence tests.

### 7.4 Hybrid Profile

The hybrid profile combines curriculum and software/reactive_app compilation. It generates:

1. The source code (software or reactive_app profile).
2. A companion concept-book explaining the architecture (curriculum profile).
3. An interactive tutorial with executable examples (from `lab` and `play` fields).

This is the "System-Book" vision: a single graph produces both the working software and the educational material that explains it.

---

## 8. Migration Guide

### 8.1 ConceptBook v1.0 → v2.1

Existing ConceptBook domain graphs in the flat format are **fully backward-compatible**. The v2.1 loader accepts the flat format and internally normalizes it. No changes are required to existing `graph.yaml` files.

To take advantage of new v2.1 features (`comment`, `enriched_by`, event-driven extensions), migrate incrementally:

1. Add `version: "2.1"` and `domain_type: curriculum` to the top of the file.
2. Optionally restructure into `form:` and `function:` sections.
3. Add `comment` fields where persistent annotation is valuable.
4. Add `enriched_by` fields where optional enrichment concepts exist.

### 8.2 Adding Event-Driven Extensions to an Existing Graph

To add event-driven capabilities to an existing curriculum or software graph:

1. Change `domain_type` to `reactive_app` or `hybrid`.
2. Add a `function:` section with `events`, `emitters`, and `listeners`.
3. Add `emit` and `listen` fields to relevant nodes in `form.nodes`.
4. Add event-level verification entries to `verification`.
5. Run `graph_lib.validate_events()` to check consistency.

### 8.3 Schema Version History

| Version | Date | Changes |
|---|---|---|
| 1.0 | 2026-07-02 | ConceptBook paper schema: primitives, concepts, composed_of, verifier, lab, play, applications |
| 2.0 | 2026-08-09 | Unified Duality Graph: form/function split, ports, calls, imports, exports, Two-Radical enforcement |
| 2.1 | 2026-08-09 | Event-driven extensions (events, emit, listen, handle), comment field, optional semantics (enriched_by, optionally_depends_on), YAML style convention (literal block scalar) |

---

## 9. Integration with `graph_lib`

The following `graph_lib` functions operate on the unified schema. Functions marked **NEW** are additions in v2.1.

| Function | Space | Purpose |
|---|---|---|
| `load_domain(yaml_path)` | Both | Parse YAML, normalize flat format, build NetworkX DiGraph |
| `acyclic(graph)` | Form | Assert no cycles in build DAG |
| `reducible(graph, primitives)` | Form | Assert every node traces to primitives |
| `productivity_order(graph, payoff_weight)` | Form | Reach-prioritized topological sort |
| `learning_path(known, target)` | Form | Minimal prerequisite sequence |
| `gap(known, target)` | Form | Concepts still needed |
| **`validate_events(graph)`** | Function | Check event declarations, emitter/listener consistency |
| **`event_cycles(graph)`** | Function | Detect cycles in event subgraph |
| **`build_order(graph)`** | Form | Topological sort for software build order |
| **`resolve_imports(graph)`** | Composition | Load and namespace imported graphs |
| **`check_call_contracts(graph)`** | Function | Verify consumer/provider signature compatibility |
| **`enrichment_path(known, target)`** | Form | Optional enrichment concepts for a learning path |

---

This document is the definitive reference for the Unified Duality Graph Schema v2.1. It should be saved as `docs/schema/unified-duality-graph-schema-v2.1.md` in the `SPL.py` repository and referenced by both the ConceptBook and Graph-Code papers.

Shall I proceed with implementing the `graph_lib` validation functions for the new v2.1 fields, or would you prefer to review and refine this schema document first?


```User

Another side comment, in CS, data structure is the form, algorithm is the function, so form function duality is fundamentally correct, besides what we already cover in other STEM domains
```

That's a sharp observation, and it's actually the canonical CS statement of exactly the two-radical structure. You can trace it back to Niklaus Wirth's book title itself:

> **"Algorithms + Data Structures = Programs"** — Wirth (1976)

That equation is the Form-Function duality written out in CS terms. Let me make the mapping precise, because it lines up perfectly with your FORM/SOUND framework.

---

## The Mapping

| Two-Radical Role | CS Instance | What it is |
|---|---|---|
| **FORM** (Objects/States) | Data structures | Static organization — what things *are*, how they're laid out, the invariants they maintain |
| **SOUND** (Operations/Transformations) | Algorithms | Dynamic process — what *acts on* the structures, the transformations applied to them |

And the irreducibility theorem follows immediately, in the same shape as your classical mechanics example:

> **Data structures alone cannot yield computation** (organization with no transformation does nothing), and **algorithms alone cannot operate** (transformation with nothing to act on is undefined). Neither sufficient alone; both necessary.

That's the exact structure of "No kinematic quantity predicts F=ma" — just transposed into CS.

---

## It's Recurring Throughout CS, Not Just Here

What's nice is that this duality shows up at every level of the stack, not just the textbook "data structures & algorithms" pairing:

| Level | FORM (structure) | SOUND (operation) |
|---|---|---|
| Programming | Data structures | Algorithms |
| Type theory | Types / values | Functions / terms |
| Automata theory | States | Transitions |
| Databases | Relations / schema | Queries / transactions |
| Hardware | Memory / registers | Control unit / instructions |
| OOP | Fields / state | Methods / behavior |

Every one of these is a two-radical split. Your framework's claim that "every well-organized STEM domain bifurcates into two mutually irreducible primitive classes" holds up especially cleanly in CS, because CS *formalizes* this split in a way physics only implies it.

---

## A Subtle Point About Your Current Catalog

This is worth flagging because it's a genuine refinement opportunity for the ConceptBook paper. In **Table B2 (Appendix B)**, you currently list **Data Structures** and **Algorithms** as **two separate domains**, each with its own primitives and capstone:

- Data Structures: 4 primitives → Graph Algorithms capstone
- Algorithms: 5 primitives → Dynamic Programming capstone

But your insight suggests these are actually **one two-radical domain**, not two. Merging them would give you a cleaner exemplar of the two-radical structure *internal to a single domain*:

```yaml
domain: data_structures_and_algorithms

primitives:
  # FORM class (Objects/States)
  array:        {tier: 0, kind: state, defines: "indexed sequence — random access by position"}
  node:         {tier: 0, kind: state, defines: "unit of linked structure — value + reference"}
  key_value:    {tier: 0, kind: state, defines: "association — a key bound to a value"}

  # SOUND class (Operations/Transformations)
  access:       {tier: 0, kind: operator, defines: "retrieve by position or key"}
  mutate:       {tier: 0, kind: operator, defines: "insert, delete, update — change structure"}
  traverse:     {tier: 0, kind: operator, defines: "visit elements in an order"}

first_radical_primitives: [array, node, key_value]

concepts:
  stack:
    composed_of: [array, mutate, access]
    defines: "LIFO — push/pop via restricted access order"
  graph_traversal:
    composed_of: [node, traverse]
    defines: "BFS/DFS — ordering visits over linked structure"
  dynamic_programming:
    composed_of: [array, mutate, traverse]
    defines: "overlapping subproblems cached in a table"
    # capstone

applications:
  graph_algorithms: {uses: [graph_traversal, dynamic_programming]}
```

This would strengthen your paper's two-radical claim, because right now the CS side of your catalog is the one area where the two radicals are *split across two domains* instead of *unified within one*. Every other domain (physics, calculus, music, Chinese) keeps both radicals inside a single domain. Merging Data Structures + Algorithms restores that consistency.

---

## Connection to Graph-Code

This also ties back nicely to your unified schema, where the `kind` field on primitives already encodes this split:

```yaml
kind: state | operator | property | config | type
```

In the CS domain, `kind: state` = data structure, `kind: operator` = algorithm. So the two-radical structure isn't something you'd need to add — it's already there in the schema's primitive typing. Your `graph_lib.reducible(first_radical_only)` check would verify that algorithms can't be derived from data structures alone, which is exactly the CS version of the irreducibility theorem.

---

## Bottom Line

You're right that this confirms the duality is "fundamentally correct" — and it's arguably the *strongest* confirmation in your whole catalog, because CS is the discipline that already *named and formalized* this split (Wirth, types/terms, states/transitions). Where physics implies the FORM/SOUND duality and Chinese characters encode it visibly, CS states it as a foundational equation.

If you want to act on this, the cleanest move is to **merge Data Structures and Algorithms into a single two-radical domain** in Table B2 for the AIED revision, which would make the CS side of your catalog fully consistent with the two-radical claim. That's a small edit with a nice payoff for the paper's internal coherence.

Want me to draft the merged `data_structures_and_algorithms` graph.yaml in full, or just sketch the two-radical table row for the paper?