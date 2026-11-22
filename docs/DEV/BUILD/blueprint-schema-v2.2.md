# Blueprint Schema Addition (v2.1 → v2.2)

**Step 1 of** `README.md` (this directory). Extracted from `../../chats/qwen-2026-08-11.md` §6.1 and formalized against the existing schema documented in `../README-claude.md` §2 ("Schema Review: Unified Duality Graph v2.1").

**What this is**: a purely additive extension to the v2.1 schema. Every field below is optional; a v2.1 graph with no `blueprint:` block parses exactly as it does today. Nothing here changes `form`, `function`, `applications`, or `verification`.

**Why**: promotes the graph.yaml from "input to a build" to a first-class object with provenance and measurable fidelity — see the vision doc's §3 (`../../../../zinets/docs/publication/TMLR/Graph-Code/README.md`). This is what step 3 of the build plan parses into `GraphDomain`.

---

## 1. `blueprint:` — top-level metadata block

```yaml
blueprint:
  id: todo_app_backend             # matches the existing `graph:` id; kept separate so
                                    # blueprint identity can survive a `graph:` rename
  schema_version: "2.2"
  domain_type: software            # same enum as top-level domain_type: curriculum | software |
                                    # reactive_app | integrated | workflow
  provenance: authored             # authored | build | reverse | roundtrip — see §1.1
  parent_blueprint: null           # id of the blueprint this was derived from, if any
```

### 1.1 `provenance` — the four states

| Value | Meaning |
|---|---|
| `authored` | Hand-written by a human. The default state for every blueprint in `apps/` today. |
| `build` | Produced as the *input* side of a forward pass (i.e. this is the as-designed blueprint that a forward pass consumed) — used to distinguish a blueprint that fed `F` from one that came out of `R`. |
| `reverse` | Produced by the reverse pass — extracted from an artifact by the miner. This is the "as-built" blueprint, $\mathcal{B}' = R(\mathcal{A})$. |
| `roundtrip` | A `reverse`-provenance blueprint that has been compared back against its `parent_blueprint` and carries a populated `drift:` block (§3). |

`parent_blueprint` is required (non-null) whenever `provenance` is `reverse` or `roundtrip` — it names the blueprint id this one was derived from or is being compared against. Not enforced by the parser (see §4); a future `validate_full` check could raise `ToolFailed` if `provenance in {reverse, roundtrip}` and `parent_blueprint` is null.

## 2. `lineage:` — append-only provenance-per-pass log

```yaml
blueprint:
  # ...
  lineage:
    - pass: forward                # forward | reverse
      model: claude-sonnet-4-6
      adapter: claude_cli
      temperature: 0.2
      prompt_hash: "sha256:ab34…"
      engine: build_component.spl  # the .spl workflow or tool that ran this pass
      timestamp: "2026-08-11T14:02:11Z"
    - pass: reverse
      model: claude-sonnet-4-6
      adapter: claude_cli
      temperature: 0.0
      prompt_hash: "sha256:7f2c…"
      engine: graph-code-miner
      timestamp: "2026-08-11T14:31:47Z"
```

One entry per pass that touched this blueprint, **appended, never rewritten** — a blueprint that has gone through Build, then Reverse, then a second refinement carries all three entries in order. This is the mechanism that makes drift attributable to a specific model/config (vision doc §3.3, "model capability delta") rather than being an anonymous number.

| Field | Type | Required | Notes |
|---|---|---|---|
| `pass` | `forward \| reverse` | yes | Which of the two maps ($F$ or $R$) this entry records |
| `model` | string | yes | Model id, e.g. `claude-sonnet-4-6` |
| `adapter` | string | yes | Runtime/adapter used, e.g. `claude_cli` |
| `temperature` | float | yes | Generation temperature for this pass |
| `prompt_hash` | string | yes | `sha256:<hex>` of the exact prompt used — makes the pass reproducible/auditable |
| `engine` | string | yes | The concrete tool/workflow that executed the pass (an `.spl` file name, or a miner tool name) |
| `timestamp` | ISO 8601 string | yes | UTC timestamp of the pass |

## 3. `drift:` — populated after a round-trip comparison

```yaml
blueprint:
  # ...
  drift:
    reference_blueprint: todo_app_backend_v1   # the as-designed blueprint this was compared against
    vector:
      intent: 0.08
      behavior: 0.00
      structural: 0.05
      interface: 0.00
      implementation: 0.01
```

`vector` is the five-component drift **vector** (never a summed scalar — see vision doc §3.2 and the additivity discussion in the Qwen transcript). Each component is normalized to `[0, 1]`, `0` = that aspect of the blueprint survived the round-trip intact, `1` = fully lost or replaced. Only present when `provenance: roundtrip`. Key order in the YAML mapping carries no parsing significance — it's listed here in the same order `grafcode drift`/Graph IDE report it in, which does have internal logic: top-down by abstraction level, why (`intent`, the human rationale) → what it should do (`behavior`/verification) → how it's shaped (`structural`, the graph topology) → how it's exposed (`interface`, signatures/contracts) → how it's built (`implementation`, tech-stack primitives). A "concept before mechanism" narrative.

| Component | Measures | Computed from |
|---|---|---|
| `intent` | Definition/rationale change | Embedding distance over `defines`/`comment` fields — **flagged as an unvalidated proxy, see vision doc §4 item 2** |
| `behavior` | Test/verifier change | `verification` diff |
| `structural` | Graph topology change | Reach-weighted graph-edit distance over `form.nodes`/`form.edges` (reuses the existing `R(v)` reach concept — see `productivity_order` in `graph_lib.py`) |
| `interface` | Signature/contract change | `function.ports`, `function.events`, `function.calls` diff |
| `implementation` | Constraint/dependency change | `depends_on`/constraint-set diff |

## 4. Parser behavior (what step 3 implements)

- `blueprint:` is optional. Absent → `GraphDomain.blueprint` is `None` (or an empty/default dataclass — implementation choice for step 3).
- No new hard validation in this pass. `provenance`/`parent_blueprint` consistency (§1.1) and `lineage` field completeness are **not** enforced yet — noting this now so it isn't silently assumed later; add as an opt-in check (mirroring `enforce_two_radical`'s pattern) if/when it's needed, not before.
- `lineage` and `drift.vector` are stored as-is (list of dicts / dict of floats) — no new graph structure required, unlike `form`/`function`, which build `nx.DiGraph` objects. This block is pure metadata.

## 5. Example: full `blueprint:` block on an existing todo yaml

Applying this to `apps/todo/blueprint/backend.graph.yaml` once it has been through one authored state (no passes yet):

```yaml
blueprint:
  id: todo_app_backend
  schema_version: "2.2"
  domain_type: software
  provenance: authored
  parent_blueprint: null
  lineage: []
```

This is the shape step 2 adds to each of the three todo yamls — empty `lineage`, `provenance: authored`, no `drift:` block yet (that only appears once a round-trip has actually run).

## 6. Naming convention: `main.graph.yaml` as the system-level entry point

**Not a schema field — a filename convention.** Component-level graphs are named `<role>.graph.yaml` (`backend.graph.yaml`, `frontend.graph.yaml`); the one file per app that sits above them, importing and composing the components into a whole, is named **`main.graph.yaml`** — same idea as `main()` as the universal entry-point convention across programming languages, applied to a graph.yaml tree instead of a call stack.

```
apps/todo/
└── blueprint/
    ├── main.graph.yaml       ← entry point: imports: [backend, frontend], applications:, capstone
    ├── backend.graph.yaml    ← component: domain_type: software
    └── frontend.graph.yaml   ← component: domain_type: software
```

`apps/todo/blueprint/main.graph.yaml` (renamed 2026-08-12 from a bare `graph.yaml`, at Wen's suggestion — earlier candidates `blueprint.yaml` and `system.graph.yaml` were considered and dropped, the former because every graph.yaml in this schema already carries its own `blueprint:` block so the name would misleadingly single one file out) is the concrete instance: `domain_type: integrated`, `imports: [backend, frontend]`, no `spec:` of its own on `todo_app_shell` (§11 of `docs/DEV/BUILD/README.md` explains why it's never passed to `build_component.spl` directly), and the file every system-level tool takes as `system_yaml` — `spl3 run spl/build_app.spl -p system_yaml=apps/todo/blueprint/main.graph.yaml ...`.

**`blueprint/` subfolder convention (2026-08-13, per Wen)**: every `.graph.yaml` file for a given app — the `main.graph.yaml` entry point and every `<role>.graph.yaml` component under it — lives under a `blueprint/` subfolder inside the app's own directory (`apps/<app>/blueprint/*.graph.yaml`), never loose at `apps/<app>/`. Keeps the FORM (the blueprint graphs) visibly separated from the FUNCTION (the generated code the graphs produce, written to `apps/<app>/<component>/` by default, or wherever `-p output_dir=...` redirects it) — the two were siblings in the same directory before this convention, which got harder to scan for as each app accumulated real generated code alongside its `.graph.yaml` sources. `apps/todo/` was migrated to this layout on 2026-08-13 (`main.graph.yaml`/`backend.graph.yaml`/`frontend.graph.yaml` moved from `apps/todo/` to `apps/todo/blueprint/`, all relative `imports:` paths between them unaffected since they moved together). **Mandatory for every new app or ConceptBook going forward** — not just a `todo`-specific detail.

**Applies across both domains this schema serves, by the same logic**, even though only the software side (`domain_type: integrated`, "contract-application" — components with `function.calls` contracts between them, verified by `check_call_contracts()`) has adopted it in practice so far:
- **contract-application** (software/`integrated`): `main.graph.yaml` imports component graphs (`backend.graph.yaml`, `frontend.graph.yaml`, ...), each with real `function.exports`/`function.calls` — `apps/todo/` is the live example.
- **concept-book** (`curriculum`): the equivalent root would be a micro-textbook's top-level `main.graph.yaml` importing chapter/module-level component graphs, once curriculum work adopts an `imports:`-based composition pattern the way `apps/todo/` does today — not yet built, noted here so the convention is established before the first curriculum example needs it, rather than retrofitted after several inconsistent names accumulate.

**Why the name matters beyond taste**: it's what `build_app.spl` and `integrate_system.spl` operate on as a pair — the exact duality Wen flagged on reviewing both files (2026-08-12): `build_app.spl` walks `main.graph.yaml`'s `imports:` and calls `build_component.spl` once per component (create the parts), then `integrate_system.spl` takes the same `main.graph.yaml` and assembles the built parts into a running, acceptance-tested system (assemble the whole) — see `docs/DEV/BUILD/README.md` §12 for the full implementation, real bugs found, and real run results. A fixed, greppable name for the file both workflows key off of (`find apps -name main.graph.yaml` locates every app's entry point regardless of app name) is what makes that pairing legible as a repo grows past one app.

## 7. Schema v2.3 additions: AND/OR fan-out, exception-kind transitions, node-level `retry:`

**Origin**: action item 1a (`README-TODO.md` §1) — sketching 5 real `SPL.py` recipes as blueprint graphs (`spl-recipe-blueprint-experiment.md`) surfaced concrete gaps in `function.transitions` (schema v2.1's `workflow` profile). Wen's response (2026-08-12) to those findings: two of the four are just schema-design decisions we control, not limits of graph-based representation — implement them, don't just note them. All three below are **implemented** as of 2026-08-12 (`src/graph_code/loader.py`, `graph_lib.py`, 7 new tests in `tests/test_graph_lib.py`, all 85 tests passing), not proposals.

### 7.1 `to:` accepts AND-list or OR-set, not just a single string

A transition's `to:` field now accepts three shapes:

```yaml
function:
  transitions:
    - from: fetch
      to: transform          # single string — one edge (v2.1 behavior, unchanged)
      action: default

    - from: dispatcher
      to: [notify, archive]  # YAML list — AND fan-out: both fire
      action: default

    - from: urgency_router
      to: {escalate, draft}  # YAML flow-mapping — OR set: exactly one fires
      action: default
      condition: "urgency > 8 -> escalate, else -> draft"
```

**Why this needed no new YAML syntax at all**: under plain `yaml.safe_load()` — no custom tags — a flow-mapping `{escalate, draft}` already parses to `{'escalate': None, 'draft': None}`, a `dict`. That's trivially distinguishable in Python from a `list` (`isinstance(dst, list)` vs `isinstance(dst, dict)`), so "list = AND, set-braces = OR" was directly implementable as a loader convention with zero YAML extension — see `_flow_destinations()` in `loader.py`.

**Where this maps to which recipe finding**: the AND case (`_flow_destinations` → `branch_type: "and"`) addresses the real gap found in `13_map_reduce`/`17_tree_of_thought` — genuine parallel fan-out (multiple destinations that *all* fire) had no representation before this; `validate_transitions()`'s ambiguous-routing check previously rejected any transition with two destinations for the same `(src, action)` outright, with no way to say "actually, both are intentional."

**The OR case turned out to be less novel than first thought.** Re-examining `28_support_triage`'s branching (`urgency_router` → escalate *or* draft) after Wen's pushback: that case was *already* expressible in schema v2.1 with zero changes, via two separate transitions with distinct `action` values on the same `from` — `validate_transitions()`'s ambiguity check only fires when the *same* `(src, action)` pair disagrees, so different actions were never actually a problem. The original "gap #3" finding was a category error — the recipe was analyzed through `software` domain_type's AND-only `composed_of` lens instead of `workflow`'s existing action-routed `function.transitions`. The OR-set `to:` syntax above is added anyway as a convenience — it lets an author declare "these are alternatives to each other" in one place, under one `action`, instead of scattering the same intent across several `action`-differentiated transition entries — but it is not filling a hole that had no other solution.

**`validate_transitions()`'s ambiguity check still fires** for the case it was originally built for: two *separately authored* transitions that name the same `(src, action)` but disagree on destination (an authoring accident, not an intentional fan-out) — `test_two_separate_entries_still_ambiguous_even_with_new_logic` guards this explicitly, so the new multi-destination support doesn't silently swallow real bugs.

### 7.2 Exception-kind transitions

```yaml
function:
  transitions:
    - from: summarize
      to: degraded_output
      action: on_context_exceeded
      kind: exception       # default "normal" if omitted — every existing graph.yaml unaffected
```

Addresses `13_map_reduce`'s `EXCEPTION` handlers, which reroute around the happy-path DAG entirely on `ContextLengthExceeded`/`BudgetExceeded` — previously nothing distinguished a fault-recovery edge from a normal one. `kind` is carried onto the built `flow_graph` edge (`graph.flow_graph[src][dst]["kind"]`) so tooling can filter exception routes out of (or specifically into) whatever it's doing — e.g. a future `validate_transitions()` enhancement could treat exception-only reachability differently from normal-path reachability, though that isn't implemented yet, just now representable.

### 7.3 Node-level `retry:` attribute

```yaml
form:
  nodes:
    risky_step:
      kind: step
      retry:
        limit: 3
        when: HallucinationDetected
        params:
          temperature: 0.1
```

Addresses `17_tree_of_thought`'s `RETRY WITH temperature = 0.1 LIMIT 3` — same node, re-run with changed generation parameters, bounded count; distinct from both the cycle mechanism (§7.1's transitions) and exception routing (§7.2). **No loader code change was needed for this one at all** — `_build_graph_domain()` already stores each node's *entire* raw dict (`nodes: dict[str, Any] = form.get("nodes") or {}`, no field whitelist), so any new node-level key, including `retry:`, already round-trips and is accessible as `graph.nodes[node_id]["retry"]`. Confirmed by `test_retry_node_attribute_round_trips_with_no_loader_change` rather than assumed.

**Field is `when:`, not `on:` — avoided a YAML footgun outright rather than working around it.** The first draft used `on:` (as in "retry **on** which exception") and hit a real bug immediately: `on` is a YAML 1.1 boolean keyword, so PyYAML parses an unquoted `on:` key as the boolean `True`, not the string `"on"` — the test failed with `KeyError: 'on'` on first write, the key had silently become `True`. This is the *exact same* gotcha GitHub Actions' own top-level `on:` trigger field is notorious for (§9 of `related-work.md`). The fix considered first — require authors to quote the key (`"on":`) — was rejected (Wen, 2026-08-12) as ugly and error-prone to expect of every human author. Renamed to `when:` instead: not a YAML reserved word, and matches SPL's own `EVALUATE ... WHEN ... THEN` vocabulary already used throughout this project, so it reads naturally rather than as a workaround.

## 8. Cache control: `use_cache` (node-level and edge-level)

See `docs/DEV/BUILD/refactoring-plan-v1.md` §3 for the full design discussion.
`build_component.spl` caches each node's generated code, keyed on
`(node, spec, tech_profile)`, so re-running a build with no yaml changes is
fast and makes no LLM calls. `use_cache` is the escape hatch: it forces one
specific node — or, as of this section, everything downstream of one
specific dependency — to always miss and regenerate, without discarding the
whole build's cache.

### 8.1 Node-level `use_cache: false` (default `true`)

```yaml
form:
  nodes:
    db_schema:
      kind: concept
      use_cache: false
      defines: "..."
```

Set on any `form.nodes.<id>` entry. `spl/tools.py::cache_get()` checks this
attribute before consulting the cache store; if `false`, that node always
misses, independent of every other node's cache state and independent of
the global `--use_cache` flag below. Use case: one node's generated code is
wrong and needs a fresh generation, without forcing a full rebuild of a
component that otherwise builds cleanly.

**Global flag**, `spl/build_component.spl`'s `@use_cache` workflow input
(default `'true'`): pass `-p use_cache=false` to force every node in that
build to miss, i.e. rebuild the whole component from scratch. Independent
of any node's own `use_cache` attribute — the more restrictive of the two
always wins (either one saying "miss" forces a miss).

### 8.2 Edge-level `use_cache: false` (default `true`) — invalidates downstream nodes

The node-level attribute above only knows about the node itself — it can't
express "node A changed, so node B (which depends on A) should regenerate
too, even though B's own spec text didn't change." That gap is what
edge-level `use_cache` closes. It's authored on an *explicit* edge entry
under `form.edges:` (`{from, to, kind, comment, use_cache}` —
`loader.py::_build_form_graph` already parses this list; `use_cache` is the
one addition):

```yaml
form:
  edges:
    - from: db_schema
      to: orm_model
      kind: depends_on
      use_cache: false
      comment: force orm_model to regenerate whenever db_schema changes
```

When `false`, the node at the edge's `to` end is forced to a cache miss —
same effect as that node's own `use_cache: false`, but scoped to "this one
upstream dependency changed" rather than "always regenerate this node."

**Caveat:** this only applies to edges authored via the explicit
`form.edges:` list. The common shorthand (`node.composed_of: [a, b]` /
`node.depends_on: [a, b]`) has no place to attach a per-edge attribute — a
dependency that needs `use_cache: false` must also be declared as an
explicit `form.edges:` entry, in addition to (not instead of) the shorthand
list if the shorthand is still wanted for readability.

`cache_get()` checks `graph.form_graph.in_edges(node, data=True)`: if any
incoming edge has `data.get("use_cache") is False`, the node misses, in
addition to the existing node-attribute check.
