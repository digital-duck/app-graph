# Experiment: sketching SPL.py recipes as blueprint graphs

**Action item 1a** from `README-TODO.md` §1. Not a claim that "~100 SPL.py recipes reduce to
blueprint graphs" is true or false — an experiment to find where the shape holds and where it
resists, per Wen's instruction (2026-08-12) to log this as something to test, not argue about.

**Method**: picked 5 recipes from `SPL.py/cookbook/` (94 total, per `cookbook_catalog.json`),
deliberately spanning different control-flow shapes rather than picking similar ones:

| # | Recipe | Category | Chosen because |
|---|---|---|---|
| 1 | `13_map_reduce` | application | Clean fan-out/fan-in — expected easy fit |
| 2 | `05_self_refine` | agentic | Bounded retry loop — closest to `build_component.spl`'s own repair pattern |
| 3 | `28_support_triage` | application | Data-dependent branching to two different terminal outcomes |
| 4 | `25_nested_procs` | agentic | Sub-workflow composition (`PROCEDURE` calling `PROCEDURE`) |
| 5 | `17_tree_of_thought` | reasoning | Deliberately picked as the one expected to resist most |

Each read in full from `SPL.py/cookbook/<dir>/*.spl` before sketching (not summarized from memory
or the catalog description alone).

---

## 1. Map-Reduce Summarizer (`13_map_reduce`) — mostly clean, one real gap

**Actual structure**: `chunk_plan` (deterministic tool) → **WHILE loop**, `chunk_count` times:
`extract_chunk` → `GENERATE summarize_chunk` → **`reduce_summaries`** (fan-in over every chunk
summary) → `quality_score` → `EVALUATE` (pass → done; fail → `improve_summary`) → two `EXCEPTION`
handlers (`ContextLengthExceeded`, `BudgetExceeded`) that both short-circuit straight to
`reduce_summaries` on whatever chunks completed so far.

**Sketch**:
```yaml
domain_type: workflow
form:
  nodes:
    chunk_planner:
      kind: module
      defines: "Deterministic chunk-count planner — no GENERATE, pure tool call"
      tier: 1
    chunk_summarizer:
      kind: concept
      defines: "Summarize one chunk — template node, not N discrete nodes (see gap below)"
      composed_of: [chunk_planner]
      tier: 2
    reduce_summaries:
      kind: module
      defines: "Fan-in: combine every chunk_summarizer output into one summary"
      composed_of: [chunk_summarizer]
      tier: 3
    quality_gate:
      kind: module
      defines: "Score final summary; below threshold triggers one improve_summary pass"
      composed_of: [reduce_summaries]
      tier: 4
```

**What fits cleanly**: the map→reduce shape itself is a textbook DAG. `quality_gate`'s
pass/improve-once branch is *exactly* `build_component.spl`'s own generate→verify→repair-once
pattern (§7 of `README.md`), just relocated from "verify code" to "verify a summary" — strong
positive signal that the pattern generalizes.

**What resists — real gap #1: variadic node count.** `chunk_summarizer` above is written as *one*
node, but the recipe actually runs it `chunk_count` times, and `chunk_count` is computed at
runtime from `len(@document)` — unknown when the graph.yaml is authored. `graph-code`'s
`form.nodes` are a fixed, authored set; there is no way today to declare "this node's *instance
count* is a runtime function of an input." The sketch above papers over this by treating
`chunk_summarizer` as a template (closer to how `crud_operations` in `backend.graph.yaml`
represents *four* CRUD functions as one node) — workable for generating the *code that does
map-reduce*, but not a literal model of *the N-times-repeated execution itself*. Those are
different things, and the schema currently only expresses the former.

**What resists — real gap #2: no exception/fault edge.** The two `EXCEPTION` handlers are not part
of the happy-path DAG at all — they're fault-recovery routes that short-circuit past
`quality_gate` straight to a degraded `reduce_summaries` output. `form.nodes`/`function.calls` have
no vocabulary for "if this fails at runtime, jump here instead" — every edge in the schema today
describes intended structure, not exceptional control flow.

---

## 2. Self-Refine (`05_self_refine`) — the cleanest fit, and it's already partially built

**Actual structure**: `draft` → **WHILE loop** (bounded by `max_iterations`): `critique` →
`EVALUATE` (`[APPROVED]` → done; else → `refine`, loop back to `critique`) → fallback commit if
the loop exhausts.

**Sketch**:
```yaml
domain_type: workflow
form:
  nodes:
    drafter:
      kind: concept
      defines: "Initial draft from the task description"
      tier: 1
    critic:
      kind: module
      defines: "Critiques current draft; APPROVED or feedback"
      composed_of: [drafter]
      tier: 2
    refiner:
      kind: module
      defines: "Improves draft given critic feedback"
      composed_of: [drafter, critic]
      tier: 2
function:
  transitions:
    - from: critic
      to: refiner
      when: "not approved"
    - from: refiner
      to: critic
      when: "always"   # the cycle — permitted because Function may cycle, Form may not
```

**What fits cleanly, and why it matters**: this is the strongest positive result of the five.
`form` stays a 3-node acyclic DAG (`drafter → critic → refiner`); the *iteration* lives entirely
in `function.transitions`' `critic ↔ refiner` cycle, which `domain_type: workflow`'s cyclic
`flow_graph` (§CLAUDE.md "Workflow space") was built to allow. This is direct confirmation that
the Form/Function split *as already designed* — not a hypothetical extension — is the right tool
for a bounded-retry recipe, and it matches `build_component.spl`'s own repair loop almost exactly
(that loop is just this same shape, hardcoded to exactly one retry instead of an authored
`max_iterations`).

**What still resists, more mildly than recipe 1**: `max_iterations` itself — the cycle's *bound* —
isn't a field either `form` or `function` has today. Less severe than gap #1 above (this doesn't
need a variable node count, just a declared bound on a cycle that already exists structurally),
but worth flagging as a small, well-scoped schema addition rather than a deep gap.

---

## 3. Support Triage (`28_support_triage`) — clean DAG, but branching has no native edge type

**Actual structure**: `extract_order_numbers` → `lookup_order` → `classify_ticket` →
`extract_ticket_details` → `detect_urgency` → **branch**: urgency > 8 → `escalation_alert`
(terminal); else → `draft_response` → `check_response_quality` → **branch**: quality < 6 →
`improve_response` (terminal); else → done (terminal).

**Sketch**:
```yaml
form:
  nodes:
    order_lookup:
      kind: module
      defines: "Deterministic: extract + look up order numbers referenced in the ticket"
      tier: 1
    classifier:
      kind: concept
      composed_of: [order_lookup]
      tier: 2
    urgency_router:
      kind: module
      defines: "Scores urgency; routes to escalation OR drafting — see branching gap below"
      composed_of: [classifier]
      tier: 3
    escalation_path:
      kind: module
      composed_of: [urgency_router]
      tier: 4
    draft_path:
      kind: module
      composed_of: [urgency_router]
      tier: 4
```

**What fits cleanly**: everything up through `urgency_router` is a textbook linear DAG — no
resistance at all, this is the same shape as `backend.graph.yaml`'s tiered node structure.

**What resists — real gap #3: no OR/branch edge, only AND-composition.** Both `escalation_path`
and `draft_path` are declared `composed_of: [urgency_router]`, but at runtime *only one of them
ever executes* — the schema has no way to say that. Every `composed_of`/`depends_on` edge in
`graph-code` today is an AND-edge: a node needs *all* its declared dependencies satisfied. There is
no XOR/OR-successor concept — no way to declare "`urgency_router` has two possible successors, the
graph picks exactly one based on a runtime condition." This is the same gap action item 2a
(explicit `trigger` node) partially addresses from the *inbound* side (what starts a graph) but
doesn't cover *outbound* branching mid-graph. `draft_path`'s own internal `quality < 6` branch is
the identical gap one level deeper.

---

## 4. Nested Procedures (`25_nested_procs`) — the closest fit of all five

**Actual structure**: `research_overview` → `CALL explain_layer` (a `PROCEDURE`) →
`CALL make_example` (a `PROCEDURE`) → `CALL calibrate_complexity` (a `PROCEDURE` with its own
internal branch) → `assemble_article`.

**Sketch**: this one doesn't need a single-file sketch — it maps directly onto the *system-level*
pattern this project already built for real, not a hypothetical:
```yaml
# main.graph.yaml — equivalent
imports:
  - id: explain_layer
    graph: ./explain_layer.graph.yaml
  - id: make_example
    graph: ./make_example.graph.yaml
  - id: calibrate_complexity
    graph: ./calibrate_complexity.graph.yaml
form:
  nodes:
    research: { kind: concept, tier: 1 }
    assembler:
      kind: module
      depends_on: [explain_layer, make_example, calibrate_complexity]
      tier: 2
```

**What fits, almost exactly**: `PROCEDURE`s calling `PROCEDURE`s is structurally identical to what
`apps/todo/blueprint/main.graph.yaml` already does — `imports:` composing independently-defined component
graphs (`backend.graph.yaml`, `frontend.graph.yaml`) into a system, verified for real via
`build_app.spl`/`integrate_system.spl` (`README.md` §12). This is the single closest match found
across all five recipes — not "would fit," but "the mechanism already exists and has run for
real." `calibrate_complexity`'s internal branch (simplify if reading level too high) is the same
gap #3 as recipe 3, one level deeper inside a component graph instead of at the top level.

---

## 5. Tree of Thought (`17_tree_of_thought`) — picked to resist, and it did

**Actual structure**: `WHILE` loop over `@models` (a caller-supplied **input list**, length
unknown at authoring time) — per model: `initial_approach` → `develop` → `evaluate_path`, stored
into a `@results` map keyed by model name → `select_best` (fan-in over *however many* paths were
explored) → `refine_solution` → `verify` → `EVALUATE` (`sound` → done; else → `synthesize_all`,
another fan-in over all paths) — plus an `EXCEPTION` handler with `RETRY WITH temperature = 0.1
LIMIT 3`.

**Attempted sketch** — and where it broke down:
```yaml
form:
  nodes:
    path_explorer:
      kind: concept
      defines: "Explore one reasoning path — but 'one' of HOW MANY? Not knowable from the graph."
      tier: 1
    path_selector:
      kind: module
      defines: "Fan-in over ALL explored paths — composed_of would need every path_explorer instance"
      composed_of: [path_explorer]   # true count unknown until @models is bound at invocation
      tier: 2
```
I stopped sketching past this point — every additional node (`select_best`, `refine_solution`,
`verify`, `synthesize_all`) inherits the same problem and adds nothing new to what's already
broken.

**What resists, and why this one is different in kind from recipes 1 and 2's gaps**:
- **Gap #1 again, but worse.** Recipe 1's `chunk_count` is at least a *deterministic function of
  an input* (document length) — knowable, in principle, before generation if you wanted to
  pre-compute it. Recipe 5's path count is the *literal length of a list the caller passes at
  invocation time* (`@models DEFAULT ['gemma3', 'phi4']` — could be 2 items or 20). There is no
  version of "author the graph once, in advance" that captures this; the graph's own shape is a
  function of a runtime argument, not just its generated content.
- **Real gap #4, new: no retry-with-different-parameters primitive.** `RETRY WITH temperature =
  0.1 LIMIT 3` changes the *generation parameters* of a failed step and re-runs it — not a
  transition to a different node (which `function.transitions`' cycles could express, per recipe
  2), and not exception routing to a different node (gap #2) — a third, distinct kind of dynamism:
  same node, different sampling config, bounded retry count. Nothing in the current schema
  represents this.
- Structurally, this recipe reads less like an authored DAG and more like a **higher-order
  function** — "map an unknown-length list through a fixed 3-step pipeline, then reduce" — where
  the *pipeline* (3 steps) is graph-shaped and stable, but the *fan-out width* is not part of the
  graph at all, it's a runtime parameter. That distinction — pipeline-shape-is-static vs.
  fan-out-width-is-dynamic — is probably the real boundary this experiment was looking for.

---

## Synthesis: where the shape holds, where it doesn't, and what that implies

**Held up well** (3 of 5): map-reduce's linear map→reduce backbone, self-refine's bounded cycle
(recipe 2 is genuinely the strongest positive result — the Form/Function split as *already
designed*, not extended, is exactly the right tool for it), and nested-procedure composition
(recipe 4 — this is not a hypothetical fit, it's the same mechanism `apps/todo/` already runs for
real).

**Four concrete, distinct gaps found**, none of them vague:

| Gap | Recipes it showed up in | Nature |
|---|---|---|
| **#1 — variadic node count**: a node's *instance count* is a runtime function of an input (deterministic in recipe 1, arbitrary-length caller-supplied list in recipe 5) | 1, 5 | Schema has no "this node repeats N times, N computed at/after runtime" declaration |
| **#2 — no exception/fault edge**: `EXCEPTION` handlers reroute around the happy-path DAG entirely | 1 | Every edge today describes intended structure, none describe fault recovery |
| **#3 — no OR/branch edge**: every `composed_of`/`depends_on` edge is AND-only; there's no way to declare "exactly one of these successors runs, chosen at runtime" | 3, 4 (nested) | Directly relevant to action item 2a (`trigger` node) — that covers graph *entry*, this covers *branching mid-graph*, a related but distinct gap |
| **#4 — no retry-with-different-params**: same node, re-run with changed generation config (temperature, model), bounded count | 5 | Distinct from both the cycle mechanism (recipe 2) and exception routing (gap #2) |

**What this means for the "~100 recipes" claim**: not settled, and shouldn't be treated as settled
by this sample of 5. But the boundary is now sharper than "some might not fit" — it's specifically
*dynamic fan-out width* (gap #1) and *runtime branching* (gap #3) that resist, not the general
idea of expressing a recipe's structure as a graph. Recipes whose control flow is a fixed pipeline
with a bounded retry loop (recipe 2's shape) or hierarchical composition (recipe 4's shape) look
like strong fits *today*, with no schema changes needed. Recipes with data-dependent fan-out
(recipe 5's shape) or multi-way branching (recipe 3's shape) would need real schema extensions —
gaps #1/#3 specifically — before they'd fit cleanly, not just a different sketch.

---

## Addendum (2026-08-12): three of the four gaps corrected or closed after Wen's review

Wen pushed back on all four findings above; the pushback held up on three of them. Recorded here
rather than silently rewritten into the sections above, so the original reasoning (including where
it was wrong) stays visible.

- **Gap #1 (variadic node count) was a scoping mistake, not a schema gap.** It conflated two
  different senses of "map a recipe to a blueprint graph": (A) the graph describes *the program to
  generate* — what `graph-code` already does for `apps/todo`, where a node like `crud_operations`
  bundles four functions into one node with no need to know at authoring time how many todos exist
  at runtime — versus (B) the graph directly represents *the recipe's own execution trace*, one
  node per literal runtime step. Gap #1 only exists under reading (B), which was never actually the
  target — FORM describes structure, and *iterating over runtime data* is an execution-time
  concern that belongs to the `.spl` interpreter (FUNCTION), not something FORM needs to represent.
  Not a limitation; a category error in how the sketch was framed.

- **Gap #3 (OR/branch) was also a category error, for a different reason** — analyzed through
  `software` domain_type's AND-only `composed_of` instead of `workflow`'s `function.transitions`,
  which already supports routing to different destinations via distinct `action` values on the
  same `from` node, with zero schema changes needed. What *was* a genuine, previously-unaddressed
  gap turned out to be the opposite case: true parallel fan-out (multiple destinations that all
  fire), which `validate_transitions()` explicitly rejected as "ambiguous routing." **Implemented**
  2026-08-12 — `to:` now accepts an AND-list `[a, b]` or an OR-set `{a, b}` (the OR form added as a
  convenience once the analysis was corrected, not because it was structurally missing). Full
  detail: `blueprint-schema-v2.2.md` §7.1.

- **Gaps #2 (exception routing) and #4 (retry-with-params) were correctly identified as real
  gaps**, and Wen's framing correction on both was simpler than mine: these aren't limits of
  graph-based representation at all, just schema decisions `graph-code` hadn't made yet — and
  since `graph-code` is our own schema, "why not implement it now, if they're low-lift" is a
  reasonable question, not a rhetorical one. Both **implemented** 2026-08-12: exception routing as
  a `kind: exception` field on a transition (§7.2); retry-with-params as a node-level `retry:`
  attribute, which needed *zero* loader code at all since nodes already store their full raw dict
  (§7.3) — confirmed by a test, not assumed. §7.3 also surfaced a real, independently-discovered
  YAML footgun: bare `on:` is a YAML 1.1 boolean keyword, silently parsing to `True` — the same
  gotcha GitHub Actions' own `on:` field is notorious for, hit here by a test failing on first
  write, not anticipated in advance. Fixed by renaming the field to `when:` (not a reserved word,
  matches SPL's own `EVALUATE ... WHEN ... THEN` vocabulary) rather than requiring every author to
  remember to quote `"on":` — Wen's call, quoting is "ugly, error prone to human."

Net effect: 3 of 4 original findings needed correction (1 was purely a framing mistake, 1 was half
framing/half real, 2 were real gaps now closed) — worth stating plainly rather than treating the
first pass as more solid than it was. All three schema additions verified via 7 new tests in
`tests/test_graph_lib.py` (85/85 passing) against real, constructed edge cases — not just described.

**Recommendation, not a decision**: if this experiment is extended, sample more recipes from the
`agentic`/`multi-agent`/`reasoning` categories specifically (§ counts in the catalog: 18 + 5 + 23 =
46 of the 94) since recipes 2 and 5 — the two extremes found here — both came from `agentic`/
`reasoning`. That's where the interesting boundary cases are likely concentrated; `basics` and
`application`-category recipes (like 1, 3, 4) are more likely to look like ordinary DAGs.
