# graph-code — Follow-up TODO

Tracks ideas and action items raised during development that are worth following up but are
**not yet scoped, scheduled, or committed to**. Distinct from `docs/DEV/BUILD/README.md` (which
documents what was actually built and verified) — this file is the holding area for what's next.
Per Wen (2026-08-12): capture ideas here as they come up, not only in conversation/memory, so
they survive independent of any one chat session.

Each item: dated, sourced, with a concrete next step — not just a restated idea. When an item is
picked up, move its outcome into `README.md` (or wherever it actually lands) and either delete it
here or mark it done with a pointer.

---

## 1. SPL's own dual structure: blueprint graph as FORM, `.spl` script as FUNCTION (2026-08-12)

**Wen's insight**, in his own words: "now blueprint graph is the IR for SPL (in my NeurIPS
submission, I stress that mermaid visual artifact as one IR for review/approval, SPL as the
pseudo-logic IR for workflow), now with blueprint graph as the new IR, our SPL script can be
simplified enormously. In SPL.py codebase, we have close to 100 recipes, but they can now all be
expressed as different blueprint graphs (FORM); now SPL framework itself has a dual-structure:
blueprint graph to define the workflow structure, SPL script can be a specific recipe, but more
appropriately a meta-language to interpret blueprint dynamically (FUNCTION). In short, graph-code
has elevated the NeurIPS paper conceptually."

**Why this isn't just theory** — it's already partially true of code that exists today, not
speculative: `build_component.spl` and `build_app.spl` are not todo-app-specific recipes. Both
take a graph.yaml path as a parameter (`@component_graph`, `@system_yaml`) and walk whatever
`build_order()`/`imports:` returns generically — node spec text, dependencies, tech profile, all
read from the graph, nothing hardcoded to `todo`. That's the FUNCTION-interprets-FORM pattern
already built, twice, in `docs/DEV/BUILD/README.md` §7/§12 — not a proposal, a fact about the
current codebase.

**The follow-on claim needing a check, not an argument**: "all ~100 SPL.py recipes reduce to
blueprint graphs." Plausible given the above, but not yet verified, and premature generalization
before verification is the exact failure mode that cost both the NeurIPS and TMLR submissions
(see memory `project_graph_code_blueprint_drift.md` and `project_spl_dual_ir_neurips.md`) — so
this is logged here **as an experiment to run, not a claim to defend or an argument to win**.

### Action item 1a — sample-and-sketch experiment — **done (2026-08-12), see `spl-recipe-blueprint-experiment.md`**
Sketched 5 recipes from `SPL.py/cookbook/` (94 total): `13_map_reduce`, `05_self_refine`,
`28_support_triage`, `25_nested_procs`, `17_tree_of_thought` — deliberately spanning a clean DAG,
a repair loop, data-dependent branching, sub-workflow composition, and (picked specifically to
stress-test) dynamic tree search. Full sketches, YAML snippets, and reasoning in
`docs/DEV/BUILD/spl-recipe-blueprint-experiment.md`.

**Result, in brief**: 3 of 5 held up well — self-refine's bounded retry loop maps almost exactly
onto the existing `workflow` profile's cyclic `function.transitions` (the Form/Function split *as
already designed*, no extension needed); nested-procedure composition maps directly onto the
`imports:` mechanism `apps/todo/blueprint/main.graph.yaml` already runs for real. Four concrete, distinct
schema gaps found, not vague ones: **(1)** variadic node count — a node's instance count as a
runtime function of an input (map-reduce's chunk count, tree-of-thought's caller-supplied model
list); **(2)** no exception/fault-recovery edge type — every edge today describes intended
structure, not fault routing; **(3)** no OR/branch edge — every `composed_of`/`depends_on` is
AND-only, no way to declare "exactly one of these successors runs"; **(4)** no
retry-with-different-generation-parameters primitive (distinct from both the cycle mechanism and
exception routing). The claim "~100 recipes reduce to blueprint graphs" is **not settled** by 5
samples, but the boundary is now sharp: fixed-pipeline-with-bounded-retry and hierarchical
composition fit today with no schema changes; data-dependent fan-out and multi-way branching
would need gaps #1/#3 addressed first. Recommendation logged in the experiment doc: extend the
sample specifically into `agentic`/`reasoning` categories (46 of 94 recipes) if this continues,
since both extremes found here came from there.

### Follow-up to 1a — schema v2.3 implemented (2026-08-12), see `blueprint-schema-v2.2.md` §7
Wen reviewed the 4 gap findings and pushed back on all of them — correctly, on 3 of the 4. Full
correction and re-analysis in `spl-recipe-blueprint-experiment.md`'s Addendum. Net result:
- Gap #1 (variadic node count) was a scoping mistake, not a real gap — resolved by re-reading, no
  schema change.
- Gap #3 (OR/branch) was half a scoping mistake (branching was already expressible via
  `workflow`'s existing `action`-routed transitions) and half real (true parallel AND fan-out
  genuinely had no representation, and was actively rejected as "ambiguous routing").
- Gaps #2 (exception routing) and #4 (retry-with-params) were real, and — per Wen's "why not
  implement it now, if they're low-lift" — **implemented**, not just documented: `to:` now accepts
  an AND-list or OR-set (`_flow_destinations()` in `loader.py`), transitions carry a `kind:`
  field (`exception` vs default `normal`), and node-level `retry:` needed zero loader code since
  nodes already store their full raw dict. 7 new tests, 85/85 passing. Also surfaced, independently
  of the GitHub Actions comparison in item 2: bare `on:` is a YAML 1.1 boolean keyword — same
  footgun as GH Actions' own `on:` field, hit by a test failing on first write. Fixed by renaming
  `retry:`'s exception-name field to `when:` (Wen: quoting `"on":` is "ugly, error prone to human")
  rather than requiring authors to quote it.

### Action item 1b — name the third transformation distinctly — **largely resolved (2026-08-12)**
"LLM decomposes a user's natural-language prompt into a blueprint graph.yaml" (Wen's proposed path
to make blueprint-authoring tractable) is a **third** map, not `reverse`: `reverse` is
artifact→blueprint (§2 of `README.md`); this is intent→blueprint. Working name: **`compile`**
(NL "source" → IR, standard compiler-front-end vocabulary; "plan" was the other candidate,
dropped as less precise) — not yet written into `blueprint-schema-v2.2.md`'s `provenance:` enum,
since this whole item is still deferred work (see sequencing note below), just decided in
principle so it doesn't get silently folded into `reverse` by a future reader.

**Fidelity question, answered (Wen, 2026-08-12)**: this map does *not* need its own fidelity
metric the way round-trip drift does. A bad NL→blueprint translation just produces a blueprint
whose generated code fails the existing forward-pass verification (`build_component.spl`'s
per-node test gates, `integrate_system.spl`'s acceptance tests) — the user iterates on the
graph.yaml the same way they'd fix any other authoring mistake. This is a real difference from
round-trip drift, which needs its own metric precisely because there's no pass/fail oracle for
"are these two blueprints similar." `compile` is explicitly a **convenience step**, not a
rigorously-verified one — correctness is checked transitively by machinery that already exists,
not by anything new.

**New connection surfaced**: the *reverse* pass's corpus (mined artifact→blueprint pairs, once
that pass exists — still not started, see §3 below) isn't only useful for round-trip drift
measurement — it's also training/few-shot data that directly strengthens `compile` (Wen: "once we
ingest enough existing open-sourced GitHub repos, the problem translation step will be much
strengthened"). Two action items that looked independent (1a's reverse pass, 1b's naming) turn out
to feed each other — worth remembering when reverse-pass work actually starts, not treating it as
purely a drift-measurement tool.

**A fourth direction was considered and explicitly scoped out, not forgotten**: "blueprint → NL"
(summarize a graph.yaml back into prose) is tempting to also call some flavor of `reverse`, but
that would collide with the *existing* `reverse` (artifact→blueprint, i.e. code→graph — a
different direction entirely). Wen's call: this doesn't need a formal pass, provenance tracking,
or a name at all — "one can just ask an LLM to summarize the graph.yaml." Recorded here so a
future session doesn't propose building machinery for it without knowing this was already
discussed and deliberately declined.

**Recurring thesis point, restated concretely here**: the fine-grained graph structure speeds up
*this* iteration loop too, not just the original code-generation one — when an NL→blueprint guess
is wrong, verification failure localizes to specific nodes/edges (the same per-node
`verify_node`/`verify_edges` + cache/repair machinery already built, §10/§12 of `README.md`), so
fixing a bad translation means regenerating the failed piece, not redoing the whole graph.

**Sequencing note**: this whole item is explicitly deferred, not scoped work — per Wen's 2026-08-11
decision (SPL4Ed paper first, Sept deadline, no scope creep; graph-code stays prototype-only until
real round-trip numbers exist on at least one domain). Logged here so it isn't lost, not so it gets
picked up next.

### `compile` step — implemented, function-level-verified, not yet LLM-run (2026-08-12)
Per Wen's "let's start action item 1b's compile step next," `spl/compile_blueprint.spl` now exists:
`decompose_intent(intent, domain_type, tech_profile)` (a `CREATE FUNCTION` prompt teaching the
schema shape via a complete counter-API example) → `validate_blueprint_yaml()` (new tool in
`spl/tools.py`, wraps `graph_code.load_domain()` + `validate_full()`) → repair loop (up to
`@max_repair_attempts`, default 2, via `repair_blueprint(candidate, validation_error)`) → on
success, `write_blueprint_file()` writes the YAML; on exhausted repairs, `RETURN "FAILED: ..."`.
Mirrors the reject-before-generate/repair-loop pattern already used in `build_component.spl`.

Two real parser bugs found and fixed while getting this to parse (spl3's `WHILE` grammar is
stricter than `EVALUATE`'s): `WHILE` conditions only support `>`,`<`,`>=`,`<=`,`=`,`!=`,`IN` — the
semantic `contains` keyword (valid in `EVALUATE`/`WHEN`) is not, so the loop guard uses
`@validation != "ok"` instead (safe since `validate_blueprint_yaml()` returns exactly `"ok"` on
success). Separately, `EVALUATE ... WHEN contains "error"` also failed to parse — semantic
`contains` needs call syntax, `contains("error")`, not bare-string form. `@max_repair_attempts`
retyped `TEXT DEFAULT '2'` → `INTEGER DEFAULT 2` to avoid string/int comparison ambiguity against
`@attempt`. `spl3 explain spl/compile_blueprint.spl` now parses cleanly (18 estimated LLM calls,
~2000 tokens).

Function-level verification done without spending any LLM calls (calling `graph_code.load_domain()`
+ `validate_full()` directly, the same logic `validate_blueprint_yaml()` wraps): the counter-API
example embedded in the `decompose_intent` prompt is itself schema-valid (`ok`); a real hard-error
case (a `composed_of` cycle) is correctly caught and reported. One pre-existing library gap
surfaced along the way, out of scope for this item: `validate_full()` does not currently treat a
dangling `composed_of` reference (pointing at a node/primitive that was never declared) as a hard
error — `networkx.add_edge()` silently creates a stub node for it, so `acyclic()` finds nothing
wrong. Rule 1 in `decompose_intent`'s prompt ("every `composed_of` entry must reference a node or
primitive declared earlier") is therefore currently enforced only by the LLM following instructions,
not by `validate_blueprint_yaml()`'s hard-error path — worth tightening if `compile` sees real use
and this turns out to matter in practice.

**Real runs, done (2026-08-12)**: two `spl3 run spl/compile_blueprint.spl` invocations, real LLM
calls, real cost.

Run 1 — counter API, `domain_type: software`, intent phrased almost identically to the worked
example in `decompose_intent`'s prompt. 1 LLM call, 12.1s, 0 repair attempts, `ok`. Output
(`apps/build/counter/backend.graph.yaml`) closely mirrors the example — a useful plumbing check
(proves the full GENERATE → validate → write path works for real) but not a generalization test,
since the intent was close enough to the example to mostly be pattern-matched.

Run 2 — login API with lockout, `domain_type: workflow`, an intent deliberately chosen to be
structurally novel (nothing like it appears in the prompt's example) and to require v2.3's
branch/exception features. 1 LLM call, 217.8s, 0 repair attempts, `ok`. Output
(`apps/build/login/workflow.graph.yaml`) is a genuinely different, well-formed 9-node/4-tier
graph: a data layer (`user_store`, `attempt_store`, `session_store`, tier 1) under a workflow-step
layer (`check_lockout`, `validate_credentials`, `handle_failure`, `issue_token`, `admin_unlock`,
tier 2-3) under the HTTP layer (`login_routes`, tier 4, `capstone`). It correctly used
`kind: exception` on both lockout short-circuit transitions and action-routed branching
(`check_lockout` → `open`/`locked`, `validate_credentials` → `valid`/`invalid`,
`handle_failure` → `still_open`/`locked_now`) with zero hand-holding beyond the intent text.
Independently reconfirmed valid via `graph_code.load_domain()` + `validate_full()` outside the
compile workflow: passes, with only expected soft `UNREACHABLE_STEP` warnings on the data-layer
and route-composing nodes (correct — they're not part of `function.transitions`, same as the
counter example's un-transitioned nodes).

One real gap surfaced by run 2, not run 1: `decompose_intent`'s only worked example (the counter
API) never demonstrates `retry:` syntax, so when the LLM needed it, it invented plausible-looking
but non-matching sub-field names (`max`, `backoff_seconds`, `comment`) instead of the documented
`limit`/`when`/`params` shape from `blueprint-schema-v2.2.md` §7.3. Harmless today — `retry:` isn't
schema-validated, nodes just store the raw dict — but means `compile`-generated retry blocks won't
reliably match hand-authored ones. Not fixed yet; the fix is adding a second, retry-using worked
example to the prompt, same technique already used for the base shape.

Full test suite reconfirmed 85/85 passing after these additions (no regressions).

---

## 2. GitHub Actions comparison — three schema-evolution ideas (2026-08-12)

Surfaced by Wen while debugging a Node.js upgrade and independently noticing `.github/workflows/`
YAML's structural resemblance to `graph-code`'s `workflow` profile — documented in depth in
`docs/DEV/PAPER/related-work.md` §9. Three concrete ideas from that discussion, not yet implemented:

### Action item 2a — `trigger` node kind
`reactive_app`/`workflow` graphs have `function.events`/`function.transitions` as edges, but
nothing marks "this is where the graph starts, from outside the graph" as a first-class node — the
way GitHub Actions' `on:` is explicit and distinct from `jobs:`. Proposed: a `kind: trigger` node —
leaf (no `composed_of`), a `fires: [...]` edge out to whatever it kicks off. Would make external
entry points explicit and checkable rather than implicit in whatever the first event happens to be.
Not started — needs a design pass on how it interacts with `validate_events()`/`flow_graph`
construction before it's added to the schema.

### Action item 2b — `${{ }}`-style symbolic substitution in graph.yaml
Borrow GitHub Actions' `${{ matrix.python-version }}` interpolation notation, but for a sharper
purpose than syntax-borrowing: eliminate hand-duplicated contract strings. Right now
`backend.graph.yaml`'s `api_routes.ports.toggle_todo.signature` and `frontend.graph.yaml`'s
`function.calls[...].contract.consumer_requires` are two independently hand-typed copies of the
same string — `contract_warnings()` (§9.1 of `README.md`) only catches them *disagreeing* after the
fact, it can't stop the duplication itself. A reference like
`${{ imports.backend.exports.toggle_todo.signature }}` would let one side point at the other
instead of retyping it, removing the drift source structurally instead of catching it post-hoc —
directly relevant given the real PATCH/PUT bug this project already hit and fixed (§7.4.1). Not
started — needs a resolution-time design (parsed at `load_domain()`? at prompt-assembly time in
`spl/tools.py`?) before implementation.

### Action item 2c — language-agnostic, LLM-generated-per-step CI nodes
Positioning insight, not yet a build target: GitHub Actions' `steps:` mostly pin versioned,
pre-built marketplace actions — deterministic but locked to whatever the action author wrote for
that language/tool. A `workflow`-typed graph.yaml node with a `spec:` instead of a pinned action
version could have an LLM generate the actual runner glue code per node, adapting to whatever
`tech_profile` is declared — the same mechanism that already builds application code today (§7 of
`README.md`), just pointed at CI steps instead. Logged in `related-work.md` §9.2 as a positioning
claim; would need a real prototype (e.g. a `domain_type: workflow` graph.yaml that actually
generates and runs a CI pipeline) before it's anything more than an argument.

---

## 3. Carried over from `README.md` §11 — not new, just tracked here now

- **Reverse pass** (artifact → blueprint extraction) — net-new, not started. The natural next
  milestone after the forward pass (§12 of `README.md`) per the project's own three-piece plan
  (§2 of `README.md`).
- **Literature search follow-up** (`related-work.md` §11 item 4, §9.2): GitLab CI/CD, CircleCI,
  and the Airflow/Prefect/Temporal cluster — GitHub Actions is one instance of the CI/CD-DAG
  family, not a full survey of it. Needed before any novelty claim about the `workflow` profile
  ships in a paper, not urgent otherwise.
- **Reference apps not yet ported**: `expense`, `kanban`, `mealie`, `fullstack`, `conduit` from
  `graph-driven-workflow/apps/SPL/` — not yet brought into `graph-code/apps/` (§11 of `README.md`).
  `dispatch` is done, see below.

## 4. `dispatch` ported and built end-to-end (2026-08-13) — second real app, distinct domain shape

Second app ported into `graph-code/apps/`, chosen deliberately for a different shape than
`apps/todo/`: backend-only (no frontend), 4 related entities (priorities/severities/incident-types/
incidents), 3 foreign-key relationships, status-enum filtering — stress-tests a wider/deeper
`form.nodes` DAG (8 nodes vs todo's 5) and FK-validation logic todo never exercised. Also the app
that surfaced the `blueprint/` subfolder convention's first real bug (see below) and confirmed
schema v2.3's `imports:`/`applications:` machinery generalizes past the 2-component todo case to a
1-component system.

Files: `apps/dispatch/blueprint/{main,backend}.graph.yaml` (hand-authored, `provenance: authored`,
migrated from `graph-driven-workflow/apps/SPL/dispatch/`'s v1 primitives/concepts schema).
Schema-validated with zero LLM cost before any build: `validate_full()` clean, correct 8-node build
order, `imports:`/`resolve_imports()` correctly namespaces all 9 backend exports.

**Real bug found and fixed (framework, not blueprint-specific)**: `_component_output_dir()` in
`spl/tools.py` resolved a component's default output as a sibling of its `.graph.yaml` file's
*immediate* parent directory — correct before the `blueprint/` subfolder convention (§3 above /
`blueprint-schema-v2.2.md`'s §6 addendum) existed, but after it, this put generated code *inside*
`apps/dispatch/blueprint/backend/` — nesting FUNCTION output inside the FORM folder the whole
convention exists to keep separate. Fixed to strip one `blueprint` path segment when present, so
default output is `apps/dispatch/backend/` (sibling of `blueprint/`, at the app root) — verified
against both `apps/todo/` (unaffected — still resolves to the pre-existing `apps/todo/backend`) and
`apps/dispatch/` (now correctly resolves to `apps/dispatch/backend`), plus the `output_dir`-override
path (unaffected either way).

**Real generation-fidelity bugs found and fixed (blueprint-specific, same category as todo's §7.4.1
PATCH/PUT bug)** — all found via real `spl3 run` attempts, not inspection:
1. `dispatch_models` listed `dispatch_schemas` as a `composed_of` dependency with no explicit
   "don't import it" instruction — the LLM inferred a wrong import path
   (`from app.dispatch_schemas import ...`, guessed from the *node id*, not the actual generated
   filename `app/schemas.py`) and pulled in unused Pydantic imports into the pure-SQLAlchemy models
   file. Fixed by dropping the unneeded `composed_of` edge and adding an explicit "do NOT import
   from app.schemas here" contract line.
2. Two of six system-level acceptance tests failed on first real integration run: `browse_incidents`
   and `update_incident`'s generated test fixtures used a fabricated field name
   (`incident_type_id`) instead of the real one (`type_id`) — because their `applications:` spec
   text never restated the exact `POST /api/v1/incidents` body shape, only `create_incident`'s spec
   did, and the test-writer LLM had to invent one for its own setup fixture. Fixed by adding the
   same "exact field names" contract line to both applications' specs.
3. Same class of bug, second round: `browse_incidents`' regenerated test then fabricated a status
   value ("Resolved") that isn't in the 3-value `IncidentStatus` enum (Active/Stable/Closed). Fixed
   by adding the exact enum value list to `browse_incidents`' contract.
4. Not a generation bug: a later run failed on `json.loads()` of an empty response body — root
   cause was leftover `dispatch.db` state from an earlier interrupted run colliding with a test
   fixture's hardcoded unique name (`reference_crud`'s contract deliberately has no
   uniqueness-pre-check, so the DB-level `IntegrityError` propagates as an unhandled 500). Fixed by
   deleting the stale db file, not a blueprint/prompt change — but flags a real gap worth revisiting
   if `dispatch` (or any app with unique-constrained fixtures) gets rebuilt repeatedly: acceptance
   test fixtures use hardcoded names, not randomized/unique-per-run ones, so DB state must be reset
   between runs by hand. Not fixed — noted for later.

**Real bug #5, found after the build was already reported green (2026-08-13)**: `apps/dispatch/backend/README.md` (the `readme` `kind: doc` node's output) was malformed — the LLM's generation leaked raw tool-call XML wrapper syntax (`<function_calls><invoke name="Write">...`) around the actual Markdown content, duplicated twice, and even named the wrong target path inside that leaked wrapper (`apps/dispatch/README.md`, the app root, not the component root `apps/dispatch/backend/README.md` it was actually written to). This slipped through both the pytest test gate (doesn't touch README.md at all) and completion, because `kind: doc` nodes deliberately skip compile/edge-symbol verification — correct for prose that isn't code, but means malformed doc output currently has no safety net at all, unlike code nodes. Fixed by hand-extracting the real content and rewriting the file directly (the intended Markdown was fully present, just wrapped). Not fixed at the framework level — worth considering a minimal doc-node sanity check (e.g. reject output containing `<function_calls>`/`<invoke` literal strings) if this recurs, but not done here since it's a single observed instance so far, not a pattern.

**Final result**: backend component 70/70 pytest tests pass; all 6 system-level acceptance tests
pass (`manage_priorities`, `manage_severities`, `manage_incident_types`, `browse_incidents`,
`create_incident`, `update_incident`); system README auto-generated with the real pass/fail table.
Full `graph_code` test suite reconfirmed 85/85 passing after the `_component_output_dir()` fix (no
regressions to `apps/todo/`).

## 5. Migrate `graph-driven-workflow/tools/graph-ide` into `graph-code` (2026-08-13, per Wen)

**Wen's reasoning**: as `graph-code` ingests/reverses existing open-source apps or builds new ones
from scratch, having a visual graph renderer will help validate the result at a glance instead of
reading raw `.graph.yaml` by eye — same motivation as the mermaid-IR argument in the NeurIPS
submission (see [[project_spl_dual_ir_neurips]]), but for the blueprint graph itself, not the SPL
script.

**What it is** (`graph-driven-workflow/tools/graph-ide/README.md`): a browser viewer for blueprint
graphs — `api/` (FastAPI backend, discovers and merges a blueprint set into `{nodes, edges,
components}`) + `frontend/` (Vite + vanilla JS, SVG DAG renderer, no third-party graph library,
click a node to inspect spec/contract/verification, drag to rearrange). Runs on ports 8210 (API) /
5180 (frontend). App-picker dropdown currently populates from every `apps/*/system.yaml` — this is
the **old** schema's system-file convention (`graph-driven-workflow`'s own), not `graph-code`'s
`main.graph.yaml` under `apps/<app>/blueprint/` — porting will need updating that discovery logic
to the new location/naming, not just a straight copy.

**Not started.** Action items, in likely order:
1. Copy `api/`+`frontend/` into `graph-code/tools/graph-ide/` (or wherever this repo's convention
   ends up putting tooling — check for an existing `tools/` dir first).
2. Update the API's blueprint-discovery logic: `apps/*/system.yaml` -> `apps/*/blueprint/main.graph.yaml`,
   and component resolution from the old `components:` registry -> the new `imports:` mechanism
   (`resolve_imports()` in `graph_code`, already does exactly this merge server-side — the IDE's
   API layer may be able to delegate to it directly instead of re-implementing merge logic).
3. Verify it renders `apps/todo/` and `apps/dispatch/` (both real, both currently correct) as a
   smoke test before trusting it against anything less certain (a `compile`-generated or
   reverse-mined blueprint).
4. Decide whether schema v2.3's new edge types (AND/OR `to:` fan-out, `kind: exception`
   transitions) need any renderer changes, or whether the existing edge-drawing code already
   handles arbitrary edge attributes generically.

## 6. `expense` ported and built end-to-end (2026-08-13, unsupervised) — third real app

Third app ported into `graph-code/apps/`, migrated and built **unsupervised** per Wen's explicit
approval ("getting started with 'expense' app, you have my approval to migrate unsupervised, we
will verify it tomorrow") before signing off for the night. Distinct pattern from `todo`
(single-entity CRUD) and `dispatch` (FK relationships, no aggregation): `expense` is the first app
exercising SQL `GROUP BY` aggregation (`report_aggregator`/`SummaryView`) and multi-parameter
filtering (category + date range together). 2-component (backend+frontend), same shape as `todo`.

Files: `apps/expense/blueprint/{main,backend,frontend}.graph.yaml` (hand-authored, `provenance:
authored`, migrated from `graph-driven-workflow/apps/SPL/expense/`). Schema-validated with zero
LLM cost before any build (`validate_full()` clean on all three, correct build orders).

**Real bugs found and fixed, all via actual `spl3 run` output, not inspection:**

1. **Pydantic v2 serializes `Decimal` fields as JSON strings, not numbers, by default.** The
   ported blueprint's `expense_schema` node omitted the `@field_serializer` decorators the
   *original* source app's `schemas.py` actually had (present in the real `.py` file, absent from
   the source `graph.yaml`'s own `spec.interface` — a gap in the source blueprint I ported from,
   not something I introduced). First real build: 4/48 backend pytest tests failed with
   `TypeError: unsupported operand type(s) for -: 'str' and 'float'` (comparing `body["amount"]`,
   a string, against a float). Fixed by adding explicit `@field_serializer` methods converting
   `Decimal` -> `float` on every *output* field (`Expense.amount`, `CategorySummary.total`,
   `ExpenseSummary.total` — `ExpenseCreate.amount` doesn't need one, input-only model) plus a
   CRITICAL contract line spelling out the rule generally, not just patching the three call sites.

2. **Same class of bug as `dispatch`'s (README-TODO.md §4, gap #2/#3): a fabricated acceptance-test
   response shape.** `view_summary`'s application spec said "SummaryView renders total and
   by_category table" — true but not shape-precise. The test-writer LLM guessed `by_category` was
   a dict keyed by category name; the real shape (per `expense_schema`) is a *list* of
   `{category, total, count}` objects. 1/5 acceptance tests failed:
   `AssertionError: 'by_category' must be a dict/object, got: <class 'list'>`. Fixed by adding the
   exact JSON shape to the application spec, same fix pattern as `dispatch`'s.

3. **Real framework bug, found by inspection after the build was already reported green** (same
   discovery pattern as `dispatch`'s bug #5): `apps/expense/blueprint/README.md` (system-level
   readme) leaked the same raw tool-call XML artifact dispatch's backend README did — despite an
   explicit "output ONLY the Markdown, no tool-call syntax" instruction added to *this app's own*
   `readme` node spec in anticipation of exactly this. The instruction did not prevent a second
   occurrence — confirming it's not a reliable fix. Root cause investigated further this time: the
   README also contained a giveaway — the LLM's own leaked reasoning said *"despite the spec
   mentioning 'todo app'"* — and `spl/integrate_system.spl`'s `write_system_readme` prompt turned
   out to have **`"...a Vue.js frontend + FastAPI backend + SQLite todo app"` hardcoded into its
   instruction text**, a leftover from when this workflow was written/tested against `apps/todo/`
   specifically and never generalized. This is the first `integrate_system.spl`/`build_app.spl`
   bug found that isn't blueprint-specific — every prior app's system README could have been
   silently influenced by this same hardcoded string; `expense` is just the first case where the
   mismatch was large enough (a completely different domain) for the model to visibly notice and
   comment on it instead of silently complying. **Fixed for real, not just patched for this app**:
   the prompt now reads the spec and explicitly instructs against defaulting to "todo app" or any
   other specific example. Separately, `apps/expense/frontend/README.md` (a different generation
   call, `build_component.spl`'s own `readme` node, not `write_system_readme`) also came back
   describing a "Todo Frontend" with fabricated `TodoDashboard`/`TodoList`/`TodoItem`/`TodoForm`
   component names — wrong content bleeding in from nowhere traceable to a hardcoded string this
   time (no similar literal found in `build_component.spl`), so left as an unexplained instance,
   not a confirmed root cause; both malformed files were hand-corrected with real content.
   **Also hardened `_strip_chat_artifacts()` in `spl/tools.py` as an actual safety net**: it now
   detects `<function_calls>`/`<invoke` in generated content and extracts the real payload from
   inside the first `<parameter name="content">...</parameter>` block, rather than relying solely
   on prompt wording (which has now failed to prevent this leak twice).

**Final result**: backend component 48/48 pytest tests pass; all 5 system-level acceptance tests
pass (`add_expense`, `list_expenses`, `filter_by_category`, `delete_expense`, `view_summary`);
system README auto-generated (and, after the doc-node fixes above, correct). Full `graph_code`
test suite reconfirmed 85/85 passing throughout (no regressions from any of the tooling changes).

**Not yet done**: manual browser verification by Wen (per the original plan — "we will verify it
tomorrow"), and confirming the `write_system_readme` prompt fix doesn't need a similar audit of
`build_component.spl`'s own prompts for other stale hardcoded assumptions.

## 7. `jwt_provider` migrated and built end-to-end (2026-08-13, per Wen) — first standalone-library
   component (no HTTP server, no `main.graph.yaml`)

Migrated `apps/jwt_provider/blueprint/jwt_provider.graph.yaml` from a minimal 1-node placeholder
fixture into a real 4-node blueprint (`requirements`, `jwt_schemas`, `jwt_core`, `readme`) and
built it for real via `build_component.spl` directly (no `build_app.spl`/`main.graph.yaml` — a
single standalone component has nothing to compose). No source app existed to port tests from, so
`tests/test_schemas.py` and `tests/test_jwt_core.py` were hand-authored against the declared
contract (frozen `TokenPayload` dataclass; `issue_token`/`verify_token` round-trip; expired/wrong-
secret/garbage-token exceptions; zero/negative `expires_in` rejection; no caller-payload mutation).
Also added a new `python_library` tech profile (`spl/tech_profiles.py`: `NODE_FILES`,
`VERIFY_CMDS`, `PROFILES` style guide — plain Python, no web framework/ORM, dataclasses/TypedDict
preferred) and extended `_SCAFFOLD_PATHS` in `spl/tools.py`.

**Two real framework bugs found and fixed, both pre-existing and generic (not `jwt_provider`-
specific), both because this was the first non-`python_fastapi`/`vue_typescript` profile ever
exercised end-to-end:**

1. `build_component.spl` has its own inline `CREATE TOOL_API run_component_tests(...)` (lines
   ~87-135) that **takes precedence over the same-named function in `tools.py`** passed via
   `--tools` — a `CREATE TOOL_API` block shadows an identically-named Python tool rather than being
   overridden by it. The inline copy's profile check only recognized `python_fastapi` and
   `vue_typescript`; `python_library` fell through to `"Unknown profile"` even though `tools.py`'s
   own (dead, shadowed) copy had already been correctly extended. Fixed by adding
   `"python_library"` to the inline check's tuple. **Lesson for future profile additions**: any new
   tech profile must be added in both places, or better, only in the inline `.spl` copy since that's
   the one that actually runs.

2. `write_node_file()` in `spl/tools.py` never received the workflow's actual `@tech_profile`
   variable at all — `build_component.spl`'s two `CALL write_node_file(...)` sites (lines 318, 359)
   only passed `node, code, component_graph, output_dir`. The function instead **guessed** the
   profile via `profile = "python_fastapi" if "backend" in domain else "vue_typescript"`. This
   happened to work by coincidence for every prior app (`todo`, `dispatch`, `expense` — whose
   `domain:` fields either contain "backend" or clearly aren't it) but broke silently for
   `jwt_provider` (`domain: software/security/jwt`, matches neither branch meaningfully → guessed
   `"vue_typescript"` → `get_node_file()` returned `None` → fell back to a generic `app/{node}.py`
   default). Result: files were generated correctly but written to `app/jwt_schemas.py` /
   `app/jwt_core.py` instead of the declared `app/schemas.py` / `app/core.py`, so the hand-authored
   tests failed with `ModuleNotFoundError`. Fixed by adding `tech_profile: str = ""` as a real
   parameter to `write_node_file()` and wiring it through both call sites in `build_component.spl`;
   the empty-string default is deliberate — it fails loud on a future missing argument instead of
   silently guessing wrong again.

**Final result**: 10/10 pytest tests pass on first successful run after both fixes. Full
`graph_code` test suite reconfirmed 85/85 passing (no regressions). This is the first component
in the migration where correctness depended on `tech_profile` actually reaching `write_node_file`
— worth keeping in mind that any future non-`python_fastapi`/`vue_typescript` profile is untested
territory until it's exercised the same way.

## 8. `fastapi` (Item CRUD API) migrated — backend built, system integration blocked on rate limit
   (2026-08-13, per Wen: "please migrate fastapi app from GDW codebase")

Migrated `apps/fastapi/blueprint/{main,backend}.graph.yaml` from
`graph-driven-workflow/apps/SPL/fastapi/` (`system.yaml` + `components/backend/graph.yaml`) —
backend-only per the source's own `BRIEF.md` scope decision (no frontend in the reference repo).
7-node backend DAG (`requirements`, `item_schemas`, `db_connection`, `orm_models`,
`crud_operations`, `api_routes`, `readme`) — smallest ported app so far, chosen specifically for
low generation-fidelity risk (single entity) while still being structurally distinct: first app
with an `Integer` autoincrement PK (`todo`/`dispatch`/`expense` all use UUID or don't expose PK)
and a DB-level UNIQUE constraint on `name` with a second lookup axis (`get_item_by_name`,
`GET /by-name/{name}`) and 409-on-conflict checks on both create and update. Source repo shipped
real, reusable test fixtures (`test_crud_items.py`, `test_routes_items.py`, `conftest.py`) — seeded
directly rather than hand-authored. Zero `tech_profiles.py` changes needed: `item_schemas`,
`db_connection`, `orm_models`, `crud_operations`, `api_routes` were all already mapped in
`NODE_FILES` from prior app migrations (`db_connection`/`crud_operations`/`api_routes` reused
verbatim across `todo`/`dispatch`/`expense`/`fullstack`; `item_schemas` and `orm_models` had
already been anticipated).

**Backend component build: 34/34 pytest tests pass.** System integration
(`integrate_system.spl` — acceptance tests + system-level README) started (6/6 system acceptance
test *files* generated correctly under `logs/spl/`, all referencing `/api/v1/items/` correctly)
but **failed partway through with `spl.executor.ModelOverloaded: Claude CLI limit reached: You've
hit your session limit · resets 12pm (America/New_York)`** — an external rate limit, not a code
bug. `apps/README.md`'s status/next-step will need a rerun of
`spl3 run spl/build_app.spl --tools spl/tools.py -p system_yaml=apps/fastapi/blueprint/main.graph.yaml
--llm claude_cli` once the limit resets; the backend component itself is cached and will not be
regenerated (see caveat below).

**One real content-contamination bug found, distinct from anything seen in `dispatch`/`expense`**:
the `readme` doc node for this backend came back describing a completely different, unrelated API
— "CRUD APIs for todos, expenses, and kanban cards" — with a full Markdown table of
`/api/v1/todos`, `/api/v1/expenses`, `/api/v1/cards` routes, none of which exist in this app or
its spec. The generated *code* (`app/main.py`) was unaffected — correct `/api/v1/items/*` routes,
verified by node-level pytest (34/34 pass) — but the doc node has no test-backed verification gate,
so the wrong content sailed straight through to disk uncaught. Root-caused by inspecting
`.spl_cache/`: the `api_routes` node's *first* generation attempt (before its own pytest-triggered
repair pass corrected it) was cached with the exact same wrong todos/expenses/cards content as the
`readme` node — i.e. the contamination happened once, upstream of both nodes, and only the node
with an automated test gate (`api_routes`) self-corrected; the doc node had nothing to catch it.
This reads as session/context bleed from other apps built earlier in the same working session
(`todo`, `expense`, and the still-unbuilt `kanban` fixture referenced in `tech_profiles.py`'s
`NODE_FILES` comments) rather than a spec-authoring mistake on this app's blueprint — worth
watching for on any future app built in the same long-running session. **Hand-corrected**
`apps/fastapi/backend/README.md` with real content, and **deleted the two stale `.spl_cache/*.json`
entries** for `api_routes` and `readme` (the wrong-content cache for `api_routes` was never
overwritten by its repair pass — leaving it in place would have silently reintroduced the wrong
code into `app/main.py` on any future cache-hit rerun, since the repair-corrected version was
written to disk but not back into the cache).

**Update (2026-08-13, session resumed after rate-limit reset): system integration completed, two
more real bugs found and fixed.**

First rerun attempt hit the rate limit again immediately (`resets 12:30pm`); a second rerun after
the user re-authenticated (`/login`) got past the backend rebuild (which correctly regenerated
`api_routes` and `readme` with the right content this time — confirming the content-contamination
above was a one-off, not a persistent spec problem) but surfaced two genuine acceptance-test
generation-fidelity bugs, plus a third bug in `write_acceptance_test`'s own instructions that
manifested first:

1. **Missing-trailing-slash 307 redirect, framework-level, generic fix.** The very first rerun's
   two failures (`user_reads_item_by_name`, `user_deletes_item`) were both
   `AssertionError: Expected 201 on create, got 307: None` — the generated acceptance test POSTed
   to `/api/v1/items` (no trailing slash) against a route declared at `/api/v1/items/`; FastAPI's
   `redirect_slashes` middleware 307-redirects, and the acceptance test's own `request()` helper
   (embedded verbatim in every `write_acceptance_test` prompt, see `spl/integrate_system.spl`)
   uses plain `urllib.request.urlopen`, which does not reliably re-POST a body across a redirect.
   Not a `fastapi` app-specific fix — `write_acceptance_test`'s prompt in `spl/integrate_system.spl`
   never previously told the model to match the contract's path exactly including trailing slashes,
   so any future ported app with a route ending in `/` (i.e. most of them, per FastAPI convention)
   was equally exposed; this is only the first time it actually manifested. Fixed generically by
   adding a numbered rule to the prompt spelling out the exact failure mode (see the prompt's rule
   5 in `spl/integrate_system.spl`).

2. **Two fabricated-field / wrong-status acceptance-test bugs**, same family as `dispatch`'s
   `incident_type_id` bug: `user_lists_items`'s pagination test POSTed
   `{"title": ..., "description": ...}` instead of `{"name": ..., "description": ...}` (422); and
   `user_updates_item`'s setup fixture asserted `status == 200` on its own setup POST instead of
   201 (POST creates return 201 in this app's contract; the test author conflated it with the
   *update*'s own 200). Fixed the same way as `dispatch`/`expense`: added exact-shape contract
   text to the two `applications:` entries in `apps/fastapi/blueprint/main.graph.yaml` naming the
   field and status code explicitly, then reran — both passed clean on the next attempt.

3. **System README generation produced YAML instead of Markdown** — a new failure mode, not seen
   on `dispatch`/`expense`/`todo`. `write_system_readme`'s output for this app was a `domain:
   apps/fastapi` / `applications:` / `integrate:` YAML-shaped document (structurally resembling a
   `graph.yaml` manifest), not the Markdown doc the `readme` node's own `spec.content_outline`
   describes (Title/Architecture/Running the full system/Applications, with acceptance-test
   pass/fail embedded in a Status table — the shape every prior app's system README has taken).
   No prompt-text or root-cause fix attempted yet (unlike the leaked-tool-call-XML bug, which had
   two independent occurrences and a clear mechanism); hand-corrected
   `apps/fastapi/blueprint/README.md` to the correct Markdown shape, following `dispatch`'s
   established Status-table format with the real per-application PASS/duration results from this
   run. Worth watching for a recurrence before concluding whether this needs a framework fix or
   was a one-off.

**Final result**: backend component 34/34 pytest tests pass; all 6 system-level acceptance tests
pass (`user_creates_item`, `user_lists_items`, `user_reads_item_by_id`, `user_reads_item_by_name`,
`user_updates_item`, `user_deletes_item`); system README hand-corrected to the right shape and
content.

**Not yet done**: manual browser/curl verification by Wen.

## 9. `kanban` ported and built end-to-end (2026-08-13, per Wen: "can you migrate kanban app from
   GDW codebase")

Migrated `apps/kanban/blueprint/{main,backend,frontend}.graph.yaml` from
`graph-driven-workflow/apps/SPL/kanban/{system.yaml,components/backend/graph.yaml,
components/frontend/graph.yaml}`, following the `todo` pattern exactly. Structurally close to
`todo` (CRUD + one extra operation) but the first ported app with a string enum
(`KanbanStatus: backlog | in_progress | done`) and a sub-resource move route
(`PUT /cards/{id}/move`) — confirmed low-risk as expected, but not risk-free (see below). Backend:
7 nodes, 5 exported endpoints. Frontend: 8 nodes (first ported app whose component tree is 5 deep:
`api_client`→`CardForm`/`StatusSelect`→`KanbanCard`→`KanbanColumn`→`KanbanBoard`→`App_vue`→
`main_ts`). Validated with zero LLM cost before any build (`load_domain()` + `validate_full()`,
zero warnings on all three files including `check_call_contracts()` on the 5 frontend↔backend
call contracts). Source repo shipped real test fixtures for both components
(`components/backend/tests/*.py`, `components/frontend/tests/*.spec.ts`) plus a working
`package.json`/`vite.config.ts`/`tsconfig.json`/`index.html` for the frontend — all seeded
directly, `npm install` run manually once (`build_component.spl`/`integrate_system.spl` never run
`npm install` themselves — same manual step `todo` needed, see `apps/todo/README.md`).

**Backend: 54/54 pytest pass. Frontend: 22/22 vitest pass. System: 4/4 acceptance tests pass**
after two rounds of fixing a real generation-fidelity bug — the same class of bug noted for
`dispatch`/`expense`/`fastapi` (LLM invents plausible-but-wrong values when a contract
under-specifies them), but the first time it hit an *enum* specifically:

- The first `integrate_system.spl` run generated acceptance tests for `view_board` and
  `move_card` that POSTed `{"status": "todo"}` — a value that doesn't exist in this app's
  `KanbanStatus` enum (`backlog | in_progress | done`), causing Pydantic to reject with 422. The
  model defaulted to the generic "todo" convention because `app_backend_endpoints()` (in
  `spl/tools.py`) only surfaces `status?: KanbanStatus` — the type name, not its members — and
  neither application's `spec.contract` spelled out the valid values either. **Fixed by adding an
  explicit "Valid KanbanStatus values are exactly ..." line to every affected application's
  `contract:` text** (`create_card`, `view_board`, `move_card`, `delete_card` in
  `main.graph.yaml`) rather than touching the shared `app_backend_endpoints()` tool — this is the
  first blueprint with an enum in its API, so the general case (surfacing enum members
  automatically for any future app) is a candidate framework improvement, not yet made.
- Same root cause recurred once more for `delete_card` alone (the first fix touched only
  `create_card`/`view_board`/`move_card`) — fixed identically, second rerun caught it.
- One additional single-run failure was pure LLM noise, unrelated to the blueprint: a generated
  `view_board` test asserted `status == 200` right next to an error message reading "Expected
  201/200" — self-contradictory given `POST /cards` correctly returns 201 per contract. Retried
  `integrate_system.spl` with no blueprint change and it passed clean.
- Each `integrate_system.spl` rerun only regenerates the acceptance tests + system README —
  `build_app.spl`'s per-component cache meant the backend/frontend themselves were never
  regenerated across any of these iterations, so the whole fix-and-retry loop cost 4 short
  `integrate_system.spl` runs (~5 LLM calls each) rather than 4 full `build_app.spl` runs.

**One doc-fidelity issue, hand-corrected** — same family as §8's system-README bug: the generated
system-level `README.md` called the first column "To Do" (should be "Backlog" — this app never
uses "todo" anywhere in its actual schema, same wrong-default-value instinct as the
acceptance-test bug above), gave the wrong uvicorn invocation (`uvicorn main:app` instead of
`uvicorn app.main:app`, matching the actual module layout), and described `manage_board` as
unrelated "administrative operations (rename columns, clear cards, reset state)" instead of what
the blueprint actually specifies (the full create/view/move/delete lifecycle, capstone). All
three hand-corrected directly in `apps/kanban/blueprint/README.md`; no test gate catches doc-node
content, so this class of bug will keep surfacing until doc nodes get some form of consistency
check — worth folding into whatever fix eventually comes out of §8's identical open question.

**Not yet done**: manual browser verification by Wen. `apps/README.md`'s kanban row updated to
"Built" status.

## 10. `fullstack` ported and built end-to-end (2026-08-13/14, per Wen: "refactor and migrate
    /home/gongai/projects/digital-duck/graph-driven-workflow/apps/SPL/fullstack")

Migrated `apps/fullstack/blueprint/{main,backend,frontend}.graph.yaml` from
`graph-driven-workflow/apps/SPL/fullstack/{system.yaml,components/backend/graph.yaml,
components/frontend/graph.yaml}` — the first ported app with authentication: JWT bearer auth,
bcrypt password hashing, RBAC via `is_superuser`, owner-scoped items, and a stateless
password-reset flow. Backend: 9 nodes, 20 total routes under `/api/v1` (6 exported to/consumed by
the frontend — login, get-me, item CRUD; the other 14 — superuser user-management, password
recovery/reset — are backend-only, exercised by pytest and two backend-only `applications:`
entries with no frontend caller). Frontend: 9 nodes, first ported frontend with its own auth state
(`auth_store`'s `useAuth()` composable, JWT in `localStorage`, singleton-ref pattern). Deliberately
does **not** import `apps/jwt_provider/blueprint/jwt_provider.graph.yaml` or
`apps/physics_app/blueprint/auth_middleware.graph.yaml` — the source app's own `security_module`
bundles JWT + bcrypt + password-reset tokens into one self-contained node with a different shape
than jwt_provider's standalone library; restructuring during migration risked diverging from the
source's own tested contract, so the reuse comparison is left for later. Validated with zero LLM
cost first (`load_domain()` + `validate_full()`, zero warnings, `check_call_contracts()` passing
on all 6 frontend↔backend call contracts). Source repo's test fixtures seeded directly
(`test_security.py`, `test_auth_schemas.py`, `test_login_routes.py`, `test_users_routes.py`,
`test_items_routes.py`, `conftest.py`; frontend `LoginForm`/`ItemForm`/`ItemList`/`ItemDashboard`
spec files), plus frontend `package.json`/`vite.config.ts`/`tsconfig.json`/`index.html`, `npm
install` run manually.

**Final result: backend 81/81 pytest pass, frontend 22/22 vitest pass, system 5/5 acceptance
tests pass** (`user_registers`, `user_logs_in`, `user_manages_items`, `superuser_manages_users`,
`user_resets_password`). This was the most iteration-heavy migration so far — largest app,
first with auth — spanning two sessions (build started 2026-08-13 evening, resumed 2026-08-14
after a Claude CLI session-limit reset) and several real bugs on top of three separate external
rate-limit/timeout stalls (not code issues, just retried after each):

1. **Content-contamination bug, third occurrence of the pattern already seen in `fastapi`'s §8
   incident 3 and `dispatch`'s framework note.** The very first `build_app.spl` attempt's
   `api_routes` node (the largest node — 20 routes) got contaminated on its first generation with
   "The app needs routes for todos, expenses, and cards" — session bleed from other apps built
   earlier in the same long-running session. Unlike `fastapi`'s case, the contamination here never
   reached disk: `build_component.spl`'s `_looks_like_code` guard correctly rejected it (and every
   subsequent repair attempt, which came back as chat preamble — "Looking at the test failure, I
   need to create `app/main.py`. Let me write it now." — instead of pure code), so the file was
   never overwritten with garbage. But the *cache* still stored the rejected content (caching
   happens right after generation, before the write-guard check), and after 3 repair attempts the
   retry budget was exhausted and the whole component build failed. Fixed by deleting the stale
   `.spl_cache/*.json` entry for `api_routes` and rebuilding — the second attempt generated it
   cleanly on the first try. Same class of fix as `fastapi`'s §8 point, now confirmed on a second,
   independent app — worth turning into a generic framework fix (don't cache content that failed
   the code-detection guard) rather than something to keep hand-fixing per app.
2. **Two generation-fidelity bugs, "invents a plausible default instead of using this app's own
   value" — same family as `kanban`'s `"todo"` enum guess, `dispatch`'s `incident_type_id`, and
   `fastapi`'s two fabricated-field bugs, but this time on *credentials* rather than field names
   or status codes.** `superuser_manages_users`'s acceptance test tried to log in as
   `admin@example.com` / `"changethis"` — a real default password from the actual upstream
   `fastapi/full-stack-fastapi-template` reference project this app was scoped from, not this
   app's own `adminpassword` constant (declared in `security_module`'s `spec.contract` but never
   surfaced to the acceptance-test generator, which only sees `app_backend_endpoints()`'s
   signature text, not arbitrary constants from other nodes). Then, separately,
   `user_manages_items`'s test assumed a *pre-existing* regular user `user@example.com` /
   `"changethis"` — again the reference project's convention — instead of registering a fresh
   user via signup first, since the application's own contract never said to. Fixed both by
   adding explicit setup-flow text to each application's `contract:` in `main.graph.yaml`: naming
   the exact superuser credentials for one, and spelling out "register first with a unique email,
   then log in with those same credentials — do NOT assume any specific account already exists"
   for the other. Both passed clean on the next `integrate_system.spl` rerun.
3. **One doc-fidelity issue, hand-corrected, a new variant of the doc-node problem tracked since
   §8: a leaked tool-call transcript, not just wrong content.** The generated system-level
   `README.md` had ~80 lines of narrated tool-call transcript prepended before the real README
   ("Let me read the relevant graph files... **Tool call: Read** `apps/fullstack/blueprint/
   main.graph.yaml`..."), including a fabricated YAML block describing routes and components that
   don't exist anywhere in this app (`POST /auth/register`, `POST /auth/login`, an `AdminPanel`
   frontend component, a `RegistrationForm`, a `ForgotPasswordForm`/`ResetPasswordForm`) — this
   app's real routes are all under `/api/v1/*` with no such component names. The actual correct
   README content followed immediately after, starting at "# Fullstack App", and was itself
   accurate (correct Status table with real per-application pass/fail results, correct
   Architecture/Running/Default-login/Applications sections matching the real blueprint) — so this
   wasn't a contamination-of-content bug like `fastapi`'s or `kanban`'s, but a
   contamination-of-*framing*: the model's own exploratory tool-call narration (reading
   `main.graph.yaml` and the existing placeholder `README.md` before writing the real one) leaked
   into the generated text instead of being stripped or discarded. `_strip_fences()`/
   `_strip_chat_artifacts()` don't catch this shape since there's no code fence anywhere in it —
   the whole thing is prose-formatted Markdown, valid enough to pass a "does this look like
   Markdown" check even with the leaked preamble on top. Hand-corrected by deleting the leaked
   preamble and keeping only the real README from its actual title onward. No test gate catches
   doc-node content (same open gap as §8/§9); this specific leaked-transcript shape is worth a
   dedicated detection heuristic (e.g. reject doc output containing "**Tool call:**" or similar
   narration markers) the next time this surfaces.

`apps/README.md`'s fullstack row updated to "Built" status. **Not yet done**: manual browser
verification by Wen — this is the first app with a login flow to actually click through.
