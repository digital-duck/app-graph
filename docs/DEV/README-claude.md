# graph-code — Design Review, Implementation Plan, and Unification Story

**Author:** Claude Sonnet 4.6
**Date:** 2026-08-09
**Status:** Living document — updated as the repo evolves

---

## 0. Provenance

This project has an unusual and productive origin. The schema design (`README-design-qwen.md`)
was produced in collaboration with **Qwen-3.8-Max** while the author was traveling —
a strong demonstration of async, mobile-first design work with a capable LLM partner.
The initial implementation (library + tests) was then done here by Claude Sonnet 4.6.
The two-LLM pipeline — Qwen for design, Claude for implementation — worked cleanly
because the design doc was precise enough to drive code directly with minimal ambiguity.

A companion novelty assessment is in `docs/DEV/literature-review.md` — an independent
literature search by Claude Sonnet 4.6 across seven dimensions (graph-driven code generation,
form/function duality in computing, curriculum prerequisite graphs, unified multi-target
schemas, LLM repair loops, event graph models, and domain hierarchy/gap analysis). Key
finding: **Two-Radical Irreducibility** returned no prior art under any search formulation.
Closest prior art for the software profile is RPG (Microsoft Research, arXiv 2509.16198,
Sept 2025). A parallel search by Qwen is pending; the two searches will be consolidated
before paper submission.

**2026-08-10 addendum:** `README-design-qwen.md` lines 1011–1121 add a Qwen-side discussion
of computer science as a domain that *names and formalizes* the Form/Function duality
(Wirth's "Algorithms + Data Structures = Programs") rather than merely exhibiting it like
physics or biology. §1.1 below folds that discussion into the founding-principle narrative.

---

## 1. What Is This?

### 1.1 The Founding Principle

`graph-code` is not primarily a software tool. It is an attempt to **digitize a principle
from natural science** — the **Form/Function duality** — and then use that formalization
to assist humans in two initial tasks, with many more to follow.

In natural science, every system can be understood along two irreducible axes:

- **Form**: structure, composition, topology — _what a thing is and how it is built_.
  A crystal lattice, an organ's anatomy, a molecule's bonding structure, a proof's axioms.
  Form relationships are acyclic: a molecule is composed of atoms; atoms are not composed
  of molecules. The DAG is the natural mathematical model.

- **Function**: behavior, dynamics, interaction — _what a thing does and how it acts_.
  A protein's catalytic activity, a circuit's signal response, a market's price dynamics.
  Function relationships may be cyclic: feedback, homeostasis, resonance, recursion are
  normal in functioning systems.

This duality is not derived from software engineering. It is observed in physics
(spacetime geometry / equations of motion), biology (anatomy / physiology), chemistry
(molecular structure / chemical reactivity), computer science (data structures /
algorithms), mathematics (algebraic objects / morphisms), and language (nouns / verbs).
Its validity is **assumed** — the same way Newton's laws are assumed before building a
bridge. The schema does not prove the duality; it encodes it.

`graph-code` is the first attempt to give this principle a **machine-readable, executable
form** — a schema that an LLM can read, validate, and use as a generation target.

#### Computer science states it explicitly

Of the domains listed above, computer science earns its own callout: it is the one
discipline that already *named and formalized* the split, rather than merely exhibiting
it. Niklaus Wirth wrote the duality as a literal equation:

> **"Algorithms + Data Structures = Programs"** — Wirth (1976)

| Two-Radical Role | CS Instance | What it is |
|---|---|---|
| **Form** (Objects/States) | Data structures | Static organization — what things *are*, how they're laid out, the invariants they maintain |
| **Function** (Operations/Transformations) | Algorithms | Dynamic process — what *acts on* the structures, the transformations applied to them |

The irreducibility theorem follows immediately, in the same shape as classical mechanics
(§4.2): data structures alone cannot yield computation (organization with no
transformation does nothing), and algorithms alone cannot operate (transformation with
nothing to act on is undefined). Neither is sufficient alone; both are necessary.

This needs stating precisely, because it is easy to misread as circular — "the schema
encodes a software concept, and software confirms the schema." It does not. The axiom is
not derived from software *engineering practice*; Wirth's equation is a theoretical-CS
statement, in the same register as "spacetime geometry / equations of motion" is a
statement about physics, not about flight-simulator code. Computer science belongs in the
domain list above for the same reason biology and chemistry do: it is a place the
pre-existing duality shows up, stated with unusual precision.

The split recurs at every level of the CS stack, not only in the textbook "data
structures & algorithms" pairing:

| Level | Form (structure) | Function (operation) |
|---|---|---|
| Programming | Data structures | Algorithms |
| Type theory | Types / values | Functions / terms |
| Automata theory | States | Transitions |
| Databases | Relations / schema | Queries / transactions |
| Hardware | Memory / registers | Control unit / instructions |
| OOP | Fields / state | Methods / behavior |

**Already latent in the schema.** The `kind` field on primitives (`state \| operator \|
property \| config \| type`) already encodes this split — `kind: state` is the CS-Form
radical, `kind: operator` is the CS-Function radical. `reducible(graph,
first_radical_only=True)` therefore doubles as the CS irreducibility check: it verifies
that operators (algorithms) cannot be derived from state (data structures) alone. No
schema change was needed to support this reading — it was already there.

**Action item surfaced for the ConceptBook catalog (lives in `SPL.py`, not this repo):**
the catalog currently lists *Data Structures* and *Algorithms* as two separate domains in
Table B2 (Appendix B) — one two-radical domain artificially split into two single-radical
ones. Every other cataloged domain (physics, calculus, music, Chinese) keeps both radicals
inside a single domain. Merging them into one `data_structures_and_algorithms` domain
(first radical `[array, node, key_value]`, second radical `[access, mutate, traverse]`)
would make the CS entry consistent with the two-radical claim made everywhere else in the
catalog. Not actioned here — flagged for whoever next touches the ConceptBook catalog; see
`docs/DEV/README-design-qwen.md` lines 1011–1121 for the full worked-out domain YAML.

### 1.2 The Two Immediate Use-Cases

The first two use-cases are deliberate choices of domains where the duality is already
well-understood and the feedback loop is short:

1. **ConceptBook generation** (`domain_type: curriculum`): the form graph encodes what
   prerequisite concepts a learner must build; the function graph (currently minimal)
   encodes how concepts interact in worked examples and labs. The LLM generates textbook
   sections in topological order, verified by symbolic math engines.

2. **Application code generation** (`domain_type: software` / `reactive_app`): the form
   graph encodes module build dependencies; the function graph encodes runtime call
   contracts and event wiring. The LLM generates source files in dependency order,
   verified by type checkers and test suites.

These two use-cases are not the ceiling — they are the proof-of-concept. The same schema,
with the same form/function split, should extend to scientific simulation, instrument
control, knowledge graph construction, and any other domain where the duality holds.

### 1.3 The Three Repos

| Repo | Role | What it generates |
|------|------|-------------------|
| `SPL.py` (recipe 74, ConceptBook) | First expression of the principle | Curriculum textbooks |
| `graph-driven-workflow` | Second expression | Multi-file application code |
| **`graph-code`** (this repo) | Unified, language-agnostic schema | Curriculum + code + reactive apps + beyond |

Each repo independently arrived at the same three-tier node structure (primitives →
concepts → applications) because that structure reflects the form principle, not a
software convention. `graph-code` makes the shared foundation explicit.

---

## 2. Schema Review: Unified Duality Graph v2.1

### 2.1 What the Schema Gets Right

**Form/Function duality — the schema's axiom, not its conclusion.**
The split between the acyclic `form` space and the potentially-cyclic `function` space
does not originate in software engineering. It mirrors the fundamental duality in natural
science: anatomy vs physiology, molecular structure vs chemical reactivity, spacetime
geometry vs equations of motion, data structures vs algorithms (§1.1 — the CS instance,
uniquely, is stated as a literal equation by Wirth, not just observed). In every STEM
domain, the "what it is" relationships
are composable and acyclic (you can always trace a concept back to primitives); the
"what it does" relationships are dynamic and may feed back on themselves.

The schema encodes this principle directly and assumes its validity, rather than deriving
it from software requirements. This is why `form` is required to be a DAG and `function`
is permitted to contain cycles: not as a technical convenience, but because that is how
nature is structured. A schema that violated this — allowing cycles in form, or forbidding
feedback in function — would be modeling something other than a real system.

**Events as first-class vertices.** In every reactive framework I have seen (Redux, Elm,
FastAPI background tasks, Vue computed), events are either string labels or hidden callbacks.
Making them typed, schema-declared vertices with explicit emitter/listener edges means the
LLM sees the full wiring before generating any code. Event contract violations are caught
before any LLM call, not after runtime debugging.

**One schema, four compilation targets.** The `domain_type` field (`curriculum` |
`software` | `reactive_app` | `hybrid`) cleanly separates _what to produce_ from _how the
graph is structured_. The same `form.nodes` block can generate a textbook chapter for a
teacher and a Python module for a developer.

**Backward compatibility.** The v1.0 flat format from ConceptBook is accepted and
internally normalized. Existing `*_graph.yaml` files in SPL.py cookbook/74 require zero
changes to load under v2.1.

**Two-Radical Irreducibility enforced at schema level.** In natural science, no domain
is generated by a single type of primitive. Mechanics needs both position (a state) and
force (an operator); chemistry needs both atoms (form) and bonds (function); logic needs
both propositions (objects) and inference rules (operations). The `first_radical_primitives`
field and the `reducible(graph, first_radical_only=True) → False` invariant encode this
irreducibility: a well-formed graph cannot be collapsed to a single root class of
primitives. This is a scientific constraint on the schema, not a software design choice.

**`comment` as LLM-persistent annotation.** Authoring rationale that would otherwise live
in a PR description or be lost to history is kept inside the graph file, visible to every
future LLM call that reads the graph. This is good cognitive engineering.

**Optional vs mandatory edges distinguished.** `enriched_by` and `optionally_depends_on`
let you represent "recommended but not required" without polluting the mandatory build DAG.
`learning_path()` and `build_order()` ignore these; `enrichment_path()` surfaces them.

### 2.2 Weaknesses and Risks

**Schema complexity.**
A new user encountering `form.nodes.velocity_graph.listen[0].handle: redraw_curve` needs
mental overhead before writing their first graph. The flat v1.0 format is learnable in
five minutes. The v2.1 format requires understanding form/function split, port signatures,
event contracts, and optional semantics before the schema feels natural.
_Mitigation:_ Start from the flat format and introduce v2.1 sections incrementally, as
the migration guide in the spec already documents.

**The `tier` field is redundant.**
`tier` is fully computable as `1 + max(predecessor tiers)` from the DAG. Requiring authors
to write it manually introduces a maintenance burden — the tier will silently go stale when
edges change. The schema doc acknowledges this ("tier consistency" is a validation rule)
but there is no auto-recompute path yet.
_Recommendation:_ Make `tier` optional and auto-compute it on load in `loader.py`.

**Port signatures are free-form strings.**
`"(x: float, dt: float) -> float"` is a human-readable string, not a machine-parseable
type. `check_call_contracts()` currently does string equality — it will fire false positives
on whitespace differences and miss real type mismatches (e.g., `int` vs `float`).
_Recommendation:_ For Python targets, parse signatures with `ast` or `inspect`. For a
language-agnostic schema, define a minimal type expression grammar.

**`enriched_by` (curriculum) vs `optionally_depends_on` (software) are the same concept.**
Both mean "optional prerequisite." Two names for the same structural relationship based on
domain type adds unnecessary vocabulary.
_Recommendation:_ Consider consolidating to a single `optional_deps: []` field with the
same semantics, and let the compilation profile interpret it. Keep both in v2.1 for
backward compat; deprecate in v3.

**No support for parameterized (template) graphs.**
A `jwt_provider.graph.yaml` with a configurable `algorithm: HS256` has no way to express
that parameter in the current schema. Every variation requires a new YAML file.
_Recommendation:_ Add a top-level `parameters:` section (like Terraform variables) so
graphs can be instantiated with substitution.

**Import resolution requires filesystem paths.**
`imports` entries use relative file paths. There is no support for importing from a package
registry or an in-memory graph. Large systems composed of many subgraphs become a file
layout problem.
_Recommendation:_ Document a conventional directory layout for multi-graph systems as a
short-term convention. Add a `registry:` field as a long-term escape hatch.

**No serialization round-trip with comment preservation.**
`load_domain()` reads YAML and populates `GraphDomain`. There is no `save_domain()` that
writes a modified `GraphDomain` back to YAML while preserving `comment` fields and
literal-block scalar formatting. Without this, programmatic graph editing loses author
annotations.
_Recommendation:_ Implement `save_domain(domain, path)` using `ruamel.yaml` rather than
plain `pyyaml`.

**The `handle` field is unverified.**
`function.listeners[].handle: redraw_curve` declares that a handler exists, but the
current validator only checks that the node exists — not that `redraw_curve` is a real
method or port on that node.
_Recommendation:_ Add a `ports` → `handles` cross-reference check in `validate_events()`.

### 2.3 Potential Enhancements (Prioritized)

| Priority | Enhancement | Why |
|----------|-------------|-----|
| High | Auto-compute `tier` on load | Eliminates stale-tier maintenance burden |
| High | `save_domain()` with comment round-trip | Graph editing without losing annotations |
| High | CLI tool (`graph-code validate/order/path`) | Primary daily-use interface |
| Medium | Consolidate `enriched_by` + `optionally_depends_on` | Reduce vocabulary |
| Medium | Signature parsing (not string equality) | Real contract verification |
| Medium | `parameters:` section for template graphs | Reusable subgraph libraries |
| Medium | `to_mermaid()` / `to_dot()` export | Visualization without full IDE |
| Low | Registry-based imports | Large system composition |
| Low | JSON Schema for the YAML | Autocomplete and linting in editors |

---

## 3. Implementation Plan

### 3.1 What Has Been Done (2026-08-09)

```
src/graph_code/
├── exceptions.py    ToolFailed, ValidationWarning
├── loader.py        GraphDomain dataclass; load_domain(); flat v1.0 → v2.1 normalization
└── graph_lib.py     13 public functions (all of spec §9 + validate_full)

apps/                6 YAML files covering all four domain_type profiles
tests/               58 tests; 58 passing on Python 3.9
pyproject.toml       Python 3.9+ package; pytest configured
```

All 12 functions from spec §9 are implemented and tested:

| Function | Status | Notes |
|----------|--------|-------|
| `load_domain` | ✅ | v1.0 flat and v2.1 unified; auto-normalization |
| `acyclic` | ✅ | Raises ToolFailed with first cycle shown |
| `reducible` | ✅ | Full and first-radical-only modes |
| `productivity_order` | ✅ | Kahn's algorithm + reach-priority min-heap |
| `learning_path` | ✅ | Primitives excluded (pre-existing, not generated) |
| `gap` | ✅ | Delegates to learning_path |
| `enrichment_path` | ✅ | NEW in v2.1 — surfaces `enriched_by` field |
| `validate_events` | ✅ | NEW — ToolFailed on hard errors; warnings on soft |
| `event_cycles` | ✅ | NEW — simple_cycles on event subgraph |
| `build_order` | ✅ | NEW — mandatory edges only, form.nodes only |
| `resolve_imports` | ✅ | NEW — file-based; namespace as alias.name |
| `check_call_contracts` | ✅ | NEW — string equality for now |
| `validate_full` | ✅ | NEW — composite entry point; respects `enforce_two_radical` |

### 3.2 Sprints Ahead

#### Sprint 1 — Library hardening (1–2 days)

- [x] `validate_full(graph) -> list[ValidationWarning]` — single entry point (acyclic → Two-Radical opt-in → events → contracts)
- [x] `domain: path/string` field — hierarchical classification separate from `graph_id`
- [x] `target_languages: [...]` field — multi-language target list for SPL runner
- [x] `enforce_two_radical: bool` field — opt-in Two-Radical enforcement (default false)
- [x] `domain_type: integrated` — rename from `hybrid`; SPL runner parallelizes tasks
- [ ] Auto-compute `tier` in `loader.py` (optional on input, always set on output)
- [ ] `save_domain(domain, path)` using `ruamel.yaml` for comment-preserving round-trip
- [ ] `to_mermaid(graph) -> str` for quick form-graph visualization

#### Sprint 2 — CLI (2–3 days)

Build `src/graph_code/cli.py` installed as `graph-code`:

```
graph-code validate  <graph.yaml>           # run validate_full; print warnings/errors
graph-code order     <graph.yaml>           # print build_order or productivity_order
graph-code path      <graph.yaml> <target>  # print learning_path
graph-code gap       <graph.yaml> <target>  # print gap (--known a,b,c)
graph-code events    <graph.yaml>           # validate events; print event subgraph
graph-code normalize <graph.yaml>           # v1.0 → v2.1 normalization; print or write
graph-code mermaid   <graph.yaml>           # emit Mermaid diagram for form space
```

This replaces `scripts/concept_graph.py` from graph-driven-workflow with an installable
CLI declared in `pyproject.toml` `[project.scripts]`.

#### Sprint 3 — SPL workflow scripts (3–5 days)

Port and adapt the SPL scripts from `graph-driven-workflow/spl/`:

| New script | Based on | What changes |
|------------|----------|--------------|
| `spl/tools.py` | GDW `spl/tools.py` | Call `graph_code.load_domain` instead of `graph_lib.load_graph`; handle v2.1 form.nodes |
| `spl/tech_profiles.py` | GDW `spl/tech_profiles.py` | Node kinds: concept→module, application→service |
| `spl/build_concept_book.spl` | GDW `build_component.spl` + SPL.py recipe 74 | Use `productivity_order`; curriculum profile |
| `spl/build_app.spl` | GDW `build_app.spl` | Use `build_order`; `check_call_contracts` pre-check |
| `spl/build_reactive_app.spl` | New | `validate_events` + event-bus wiring generation |
| `spl/build_hybrid.spl` | New | Run concept-book + app build in sequence |

#### Sprint 4 — Graph IDE (3–5 days)

Port the browser IDE from `graph-driven-workflow/tools/graph-ide/` with:

- Form graph visualization with tier coloring (DAG layout)
- Event graph overlay (bipartite view, emit/listen edges highlighted)
- `domain_type` filter (show only curriculum / software / reactive edges)
- CRUD for nodes/edges backed by `save_domain()`
- Import graph tree viewer (show composition hierarchy)
- Round-trip save with `ruamel.yaml` comment preservation

#### Sprint 5 — Migration tooling (1 day)

```
graph-code migrate <v1.0.yaml> [-o <v2.1.yaml>] [--interactive]
```

Converts ConceptBook YAML from SPL.py cookbook/74 and GDW `graph.yaml` files to v2.1.
`--interactive` mode prompts for `comment` and `domain` fields while walking each node.

#### Sprint 6 — Domain registry, LLM ingestion, and authoring assistance (4–6 days)

The `domain` hierarchical path enables reasoning about a *collection* of graphs, not just
individual ones. This sprint has three parts.

**Part A — Core registry functions:**

```python
list_domains(registry_dir)              # scan dir tree → {domain_path: GraphDomain}
siblings(domain_path, registry)         # graphs at the same path level
subtree(domain_prefix, registry)        # all graphs under a path prefix
common_primitives(graphs)               # shared vs domain-specific primitives
domain_gaps(reference_tree, registry)   # paths expected but absent
suggest_imports(graph, registry)        # import candidates based on domain path
```

And CLI commands:

```
graph-code registry list     <dir>             # print all domain paths found
graph-code registry siblings <dir> <path>      # e.g. science/physics/*
graph-code registry gaps     <dir> <prefix>    # missing subdomains under prefix
graph-code registry common   <dir> <prefix>    # shared primitives across subtree
```

**Part B — Path-B: LLM-assisted ingestion of existing open-source repos**

Analogous to ConceptBook Path-B (ingesting existing textbooks/syllabi to extract a concept
graph), Path-B here means: **given an existing open-source repo, have the LLM extract its
graph schema** — identifying primitives, nodes, dependency edges, event wiring, and call
contracts — and register the resulting `*.graph.yaml` in the domain registry.

At scale, running Path-B across hundreds of repos in a domain (e.g., all PyPI packages
tagged `web-framework`, or all GitHub repos tagged `physics-simulation`) populates the
registry with real-world structural patterns that no single author could produce by hand.
This is the fast path to a large, diverse registry.

Planned function:

```python
ingest_repo(
    repo_path: str | Path,        # local clone or GitHub URL
    domain_hint: str = "",        # e.g. "software/backend/fastapi" — guides LLM
    registry_dir: Path = None,    # where to write the extracted .graph.yaml
    llm_client = None,            # injected LLM adapter (from SPL.py)
) -> GraphDomain
```

The LLM prompt uses the existing examples as few-shot context (form.nodes, function.events,
contracts) to extract the schema. The extracted graph is immediately validated with
`validate_full()` before being written to the registry. Nodes that cannot be resolved are
left with `tier: 0` and flagged for human review.

**Part C — Path-A: Registry-assisted new graph authoring**

Once the registry is populated (via Path-B or by hand), it becomes a *prior* that helps an
author create a new graph from scratch. Planned function:

```python
suggest_graph_stub(
    domain: str,                  # e.g. "science/physics/fluid_dynamics"
    registry: dict[str, GraphDomain],
) -> str  # YAML stub with suggested primitives, nodes, and imports
```

Given a target `domain` path, this function:
1. Finds sibling graphs (same path level) and looks up their `primitives` and `form.nodes`
2. Identifies common primitives across siblings (likely to apply here too)
3. Identifies missing sub-concepts relative to sibling graphs (potential gap to fill)
4. Returns a skeleton `.graph.yaml` pre-populated with likely candidates, marked with
   `# suggested` comments for the author to accept, rename, or reject

This is the Path-A assistance loop: author declares `domain:`, the system offers structure
derived from everything it already knows, the author refines, and the graph is validated
before being committed to the registry.

**Motivation:** At scale (SPL.py's 18 curriculum domains + GDW's 8 app graphs + many
scientific/engineering additions), these three parts together create a self-reinforcing
flywheel: Path-B ingests the world's open-source knowledge into graph form; the registry
accumulates patterns; Path-A uses those patterns to accelerate authoring of the next graph.

---

## 4. The Unification Story

### 4.1 Why the Three Repos Converge

The convergence of SPL.py (ConceptBook) and graph-driven-workflow is not accidental code
reuse. Both repos independently arrived at the same three-tier node structure because both
were modeling the same underlying principle:

```
Tier 0  Primitives   ←  form atoms; pre-existing; not generated
Tier 1+ Concepts     ←  composed from primitives; generated in topo order; verified
Capstone Applications ← what the domain unlocks; the payoff
```

This structure appears in the ConceptBook curriculum graphs (18 STEM domains), in the
application code graphs (todo, kanban, fullstack, …), and in the new reactive-app graphs
(physics simulator, auth middleware) — because in each domain, the same natural principle
applies: things are built from simpler things (form, DAG), and things interact with other
things (function, may cycle).

```
SPL.py (cookbook/74_concept_book)
  graph_lib.py  ─────────────────────────────────────────┐
  18 domain *_graph.yaml files                            │
  transpiler: YAML → curriculum textbook                  │  Different compilation
                                                          │  targets; same principle
graph-driven-workflow                                      │
  spl/graph_lib.py  ─────────────────────────────────────┤
  apps/*/graph.yaml (todo, kanban, fullstack, …)          │
  build_component.spl: YAML → application source code     │
                                                          │
              ▼  Digitized principle  ▼                  │
                                                          │
graph-code  (this repo)  ◄──────────────────────────────-┘
  One schema, one library, all targets
  domain_type: curriculum | software | reactive_app | hybrid
```

The important shift in framing: this is **not** a refactoring exercise (consolidating
two implementations of the same code). It is the first attempt to give the form/function
principle a single, machine-readable, language-agnostic encoding that an LLM can use
as a generation scaffold across any domain.

### 4.2 What the Two Initial Use-Cases Demonstrate

**Use-case 1: ConceptBook generation (`domain_type: curriculum`)**

The form graph encodes the cognitive dependency structure of a STEM domain — which
concepts must be understood before others can be introduced. `productivity_order()`
derives a teaching sequence that maximizes "reach" (each concept taught unlocks the
most future concepts). The LLM generates verified textbook sections in that order.

This works because STEM knowledge itself has form-structure: it is not a web of
arbitrarily connected ideas but a DAG rooted in a small set of irreducible primitives.
The schema is not imposing structure on knowledge — it is reading out structure that
was already there.

**Use-case 2: Application code generation (`domain_type: software` / `reactive_app`)**

The form graph encodes module build dependencies (what must be compiled before what).
The function graph encodes runtime behavior: synchronous call contracts between ports,
and asynchronous event wiring between emitters and listeners. `build_order()` derives
the code generation sequence; `check_call_contracts()` and `validate_events()` verify
the interfaces before any LLM call touches them.

This works for the same reason: real software systems have form-structure (imports,
dependencies) and function-structure (calls, events), and keeping them separate in the
schema prevents the LLM from generating code that confuses the two. This is Wirth's
"Algorithms + Data Structures = Programs" operationalized (§1.1): `form_graph` is the
data-structure/composition axis, the function space (`calls`, `events`) is the algorithm
axis.

**What they share:** In both use-cases, the generation is _ordered_, _local_, and
_verifiable_. Each node is generated using only the context of its direct predecessors
(already generated and verified). This localness is what makes LLM generation reliable
at scale — the model never needs to hold the entire system in context at once.

### 4.3 The Broader Vision: AI-Assisted Scientific Exploration and Engineering

The two use-cases above are a proof-of-concept. The same principle applies wherever
a domain has:
- **Irreducible primitives** (things that cannot be further decomposed within the domain)
- **Compositional structure** (complex things built from simpler ones, acyclically)
- **Behavioral interactions** (things acting on each other, potentially with feedback)

That description fits virtually every STEM domain and every engineering discipline:

| Domain | Form (DAG) | Function (may cycle) |
|--------|-----------|---------------------|
| Molecular biology | gene → protein → pathway composition | signaling networks, gene regulatory feedback |
| Materials science | atomic structure → crystal structure → microstructure | stress-strain response, phase transitions |
| Control systems | sensor → controller → actuator composition | feedback loops, stability analysis |
| Scientific simulation | mesh → solver → output pipeline | iterative solvers, time-stepping loops |
| Knowledge engineering | ontology concepts → compound classes | inference rules, query patterns |
| Instrument firmware | hardware driver → protocol → application layer | interrupt handlers, real-time event loops |

In each case, `graph-code` provides the scaffold: declare the nodes, declare the
dependencies, let `graph_lib` compute the order and validate the interfaces, then let
an LLM fill in the content — whether that content is a textbook section, a Python module,
a simulation step, or a knowledge base entry.

The longer-term goal is a **universal AI-assisted authoring loop** across STEM:

```
Domain expert declares graph (form + function)
        ↓
graph_lib validates structure (acyclicity, reducibility, event consistency)
        ↓
LLM generates content in topological order (one node at a time, local context only)
        ↓
Domain verifier checks each node (sympy, pytest, sage, instrument test, …)
        ↓
Graph IDE shows the evolving system; expert refines nodes and edges
        ↓
(loop)
```

The graph is the expert's cognitive model made executable. The LLM is the
generator. The verifier is the oracle. The IDE is the interface. None of these
requires that the underlying principle be anything other than what it already is
in natural science.

### 4.4 What Each Repo Still Separately Holds

| Asset | Where it stays | Reason |
|-------|---------------|--------|
| 18 domain curriculum YAML files | SPL.py cookbook/74 | Domain expertise; not framework code |
| SPL workflow runner (`.spl` DSL) | SPL.py spl/ | Runtime; graph-code is schema + algorithms |
| Reference apps (todo, kanban, etc.) | GDW apps/ | Working examples; not schema |
| Tech profiles (python_fastapi, vue_typescript) | GDW spl/ | To be ported in Sprint 3 |
| Browser Graph IDE | GDW tools/graph-ide/ | To be ported in Sprint 4 |

---

## 5. Design Decisions (Closed)

These were open questions; all are now resolved and implemented.

---

**1. Scope: `graph-code` vs SPL runtime**

`graph-code` is a prototype that validates the form-function duality concept in
AI-assisted creation. Its scope is schema definition, graph algorithms, and graph-driven
generation. Core framework infrastructure — the SPL runner, `.spl` workflow scripts,
LLM adapters, persistence — stays in `SPL.py`. `graph-code` is an application built on
top of SPL, not a replacement for it.

_Implication:_ The `spl/` directory planned for Sprint 3 contains workflow scripts that
call `graph_code` as a library. The SPL runner itself is not reproduced here.

---

**2. `domain_type: hybrid` → renamed to `integrated`; no sequential order**

There is no defined orchestration order between curriculum and code generation.
A person writing curriculum does not wait for the lab to be complete — they cross-reference
each other regardless of state. The word "hybrid" implied a mixture of two separate things;
"integrated" reflects that a single domain is expressed simultaneously as knowledge and as
working code, and the SPL runner parallelizes whatever tasks it can.

_Implemented:_ `domain_type: integrated` is the canonical term. `hybrid` remains
accepted for backward compatibility. `physics_app.graph.yaml` now uses `integrated`.

---

**3. Target languages: add `target_languages` graph attribute**

A single graph can span multiple runtimes — a backend in Python/FastAPI, a frontend in
JavaScript or Streamlit. The `target_languages` list communicates this to the SPL runner
so it can select the correct tech profiles for each node.

_Implemented:_ `target_languages: [python]` / `[python, javascript]` is a new top-level
field on `GraphDomain`. Parsed by `loader.py`; visible to the SPL runner at generation time.

Examples:
```yaml
target_languages: [python]              # auth_middleware, physics_simulator
target_languages: [python, javascript]  # physics_app (FastAPI backend + JS frontend)
```

---

**4. Verifier is open-ended**

There is no prescribed list of verifiers. `sympy`, `sage`, `pytest`, `mypy`, `jest` are
examples, not an enumeration. End-users specify whatever verification backend their domain
requires — the schema stores it as a string and the SPL runner dispatches to it.

_No schema change needed._

---

**5. Two-Radical Irreducibility: opt-in via `enforce_two_radical`**

Making Two-Radical Irreducibility a hard default would create an adoption barrier for
practical graphs (e.g., a simple `software/backend/fastapi` graph with only `config`
primitives). The check is scientifically valid for STEM curriculum domains but would be
unnecessarily restrictive for engineering graphs.

_Implemented:_ New graph attribute `enforce_two_radical: bool` (default `false`).
When `true`, `validate_full()` raises `ToolFailed` if the graph is fully reducible from
`first_radical_primitives` alone.

```yaml
# In a physics curriculum: opt in to strict checking
enforce_two_radical: true   # validate_full() will fail if mass/force are never needed
```

---

**6. `domain` as hierarchical path**

`domain_type` names the compilation target. `graph_id` is the unique identifier.
Neither describes what scientific or engineering domain the graph models.
A new `domain` field uses slash-separated path notation for hierarchical classification:

```yaml
domain: science/physics/classical_mechanics
domain: science/biology/molecular/protein_folding
domain: software/backend/fastapi
domain: software/frontend/vue
domain: engineering/control_systems/pid_controller
```

_Implemented:_ `GraphDomain.domain: str` populated from the top-level `domain:` key.
In flat v1.0 files, the existing `domain:` key is reused (e.g., `domain: classical_mechanics`
normalizes to `domain: classical_mechanics` in v2.1, with the user free to extend it to a
full path later). `graph_id` continues to hold the unique identifier from the `graph:` key.

**Why this matters at scale — domain registry and gap analysis**

The hierarchical path is not just a label. It is the index structure for a growing library
of domain graphs. As the collection grows beyond the current handful of examples toward
the 18 ConceptBook domains, 8+ GDW application graphs, and many future scientific and
engineering domains, the path enables two capabilities that flat tags cannot:

_Pattern discovery across siblings._ Graphs at the same path level share a common
structural context. If ten `software/backend/*` graphs all independently declare a
`db_connection` primitive, the hierarchy makes that convergence visible — it is a signal
that `db_connection` belongs in a shared `software/backend/common` base graph that others
import. Without the hierarchy, those ten graphs look unrelated. With it, they are siblings
in a subtree that can be compared programmatically.

_Gap detection._ A subtree view of `science/biology/*` that shows entries for
`molecular/dna_replication` and `molecular/protein_synthesis` but nothing under
`molecular/protein_folding` or `cellular/*` makes coverage gaps explicit. A researcher
or educator can see at a glance which domains exist, which are partial, and which have
not been started. Without a hierarchy, the collection is a flat list of names with no
structure to reason about.

**Planned `graph_lib` functions for registry operations** (Sprint 6):

```python
# Scan a directory tree for all graph YAML files; return {domain_path: GraphDomain}
list_domains(registry_dir) -> dict[str, GraphDomain]

# Find all graphs at the same depth level (siblings in the path tree)
siblings(domain_path, registry) -> list[GraphDomain]

# Find all graphs under a subtree prefix
subtree(domain_prefix, registry) -> list[GraphDomain]

# Compare primitives across multiple graphs; return shared and domain-specific sets
common_primitives(graphs) -> tuple[set[str], dict[str, set[str]]]

# Find paths present in one set of domains but absent in another (gap detection)
domain_gaps(reference_subtree, actual_registry) -> list[str]

# Given a graph's domain path, suggest known graphs it might want to import
suggest_imports(graph, registry) -> list[GraphDomain]
```

These functions make `graph-code` not just a single-graph validator and generator, but
a tool for reasoning about a collection of graphs as a structured knowledge space —
identifying what patterns exist, what patterns repeat (candidates for extraction), and
what patterns are missing (gaps to fill).

**How the registry gets populated — Path-B and Path-A**

The registry does not need to be hand-authored from scratch. It can be grown along two
complementary paths, mirroring the ConceptBook authoring model:

- **Path-B (ingestion):** The LLM is given an existing open-source repository and asked to
  extract its graph schema — identifying primitives, nodes, dependency edges, event wiring,
  and call contracts — and emit a `*.graph.yaml` registered under the correct `domain` path.
  Running Path-B across many repos in a domain (e.g., all Python web frameworks, or all
  physics simulation packages) populates the registry with real-world structural patterns
  at a speed no individual author can match. Each extracted graph is validated with
  `validate_full()` before being accepted into the registry.

- **Path-A (authoring with prior):** Once the registry is populated, an author declaring a
  new graph at `domain: science/physics/fluid_dynamics` can ask the system to suggest a
  skeleton: sibling graphs supply candidate primitives and common structural patterns;
  `domain_gaps()` highlights what concepts are missing relative to neighbors; `suggest_imports()`
  proposes which existing graphs to import rather than re-author. The author accepts, renames,
  or rejects each suggestion, then validates the result.

The two paths reinforce each other: Path-B seeds the registry; Path-A uses the registry to
accelerate new authoring; new authored graphs feed back into the registry for the next
Path-B or Path-A pass. The hierarchical `domain` path is the common index that makes this
flywheel work.

---

## 6. File Map

```
graph-code/
├── pyproject.toml                               # Python 3.9+; pytest with -p no:spark
├── src/
│   └── graph_code/
│       ├── __init__.py                          # Public API (all 13 + exceptions)
│       ├── exceptions.py                        # ToolFailed, ValidationWarning
│       ├── loader.py                            # GraphDomain; load_domain(); v1.0 normalization
│       └── graph_lib.py                         # 13 algorithms from spec §9
├── apps/
│   ├── classical_mechanics_flat.graph.yaml      # v1.0 backward-compat (curriculum)
│   ├── classical_mechanics.graph.yaml           # v2.1 curriculum profile
│   ├── jwt_provider.graph.yaml                  # v2.1 software (provides exports)
│   ├── auth_middleware.graph.yaml               # v2.1 software (imports jwt_provider)
│   ├── physics_simulator.graph.yaml             # v2.1 reactive_app (events + handlers)
│   └── physics_app.graph.yaml                   # v2.1 integrated (graph of graphs)
├── tests/
│   ├── conftest.py                              # Fixtures; inline YAML for test isolation
│   └── test_graph_lib.py                        # 58 tests; all passing on Python 3.9
└── docs/
    └── DEV/
        ├── README-design-qwen.md                # Unified Duality Graph Schema v2.1 spec (Qwen)
        ├── README-claude.md                     # This file (Claude)
        └── literature-review.md                 # Independent novelty assessment (Claude); Qwen search pending consolidation
```



## ToDo

```User
can you migrate C:\Users\p2p2l\projects\digital-duck\graph-driven-workflow\apps\SPL\todo to
  C:\Users\p2p2l\projects\digital-duck\graph-code\apps\todo by first authoring the graph.yaml, try to use "import"
  syntax, to avoid merging system / component .yaml graphs
```

```User
[2026-08-09] SPL runner as a generic interpreter over `domain_type: workflow` graphs

Idea surfaced while discussing the new `workflow` domain_type (schema locked the same
day — see `form.nodes.<id>.phases` and `function.transitions` in loader.py/graph_lib.py,
and apps/etl_workflow.graph.yaml): today SPL captures each workflow pattern as a
bespoke `.spl` recipe script with control flow written procedurally. If the pattern is
instead expressed as a `workflow` graph.yaml (steps as form.nodes with phases; branching,
retries, and loops as function.transitions), the SPL runner could collapse to ONE generic
interpreter loop shared by every recipe:

    run step.phases.execute (and pre/post if present)
        -> read the action post() returns
        -> look up the matching function.transitions edge from this step
        -> repeat, starting from `entry`

This keeps the graph-code / SPL.py boundary intact (design decision #1 above): graph-code
stays schema + algorithms only (parse phases/transitions, validate routing via
validate_transitions(), detect cycles via flow_cycles() — never execute anything); the
interpreter loop itself belongs in SPL.py's runner.

Cost to flag before committing to this: today's `.spl` recipes likely encode
branching/retry/human-in-loop procedurally, so each recipe needs a one-time translation
into phases + transitions, and the runner needs a domain_type dispatch — `workflow` graphs
get executed by the new interpreter loop; `software`/`curriculum`/`reactive_app`/
`integrated` graphs continue to only be validated/build-ordered, never executed.

Status: schema is locked (this session). The interpreter loop design itself is deferred —
sketch it in SPL.py when that repo's runner work is picked up next; use
apps/etl_workflow.graph.yaml as the reference graph to design against.
```