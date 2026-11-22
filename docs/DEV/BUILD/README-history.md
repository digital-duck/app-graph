# History: graph-driven-workflow → graph-code

A reference for how this repo relates to its precursor,
[`graph-driven-workflow`](../../../../graph-driven-workflow) (GDW), and what
actually changed along the way. Written 2026-08-14 after reviewing both
repos side by side.

## Lineage

```
SPL (Structured Prompt Language)      — formal intermediate representation between human intent and LLM output
  → SPL + SDLC ("Beyond Vibe Coding") — SPL applied across the software development lifecycle
    → GDW (graph-driven-workflow)     — a dependency graph added as SPL's orchestration backbone
      → graph-code (this repo)        — GDW's schema/algorithms extracted into an installable
                                         library, generalized past one domain_type, plus a
                                         blueprint-provenance/drift layer GDW never had
```

GDW proved the core idea for one shape: a `software` component built from a
`graph.yaml` DAG (`primitives → concepts → applications`), verified at every
node, assembled via a `system.yaml`. graph-code is what happened when that
idea was pushed to be a real, pip-installable library (`src/graph_code/`)
and generalized past the one case GDW ever actually built.

## What changed, concretely

### Blueprint layout and naming

| GDW | graph-code |
|---|---|
| `system.yaml` at component-tree root | `main.graph.yaml` — same role, renamed 2026-08-12 so `find apps -name main.graph.yaml` locates every app's entry point regardless of app name (`main()` as universal entry-point convention, applied to a graph tree) |
| `components/<role>/graph.yaml` | `<role>.graph.yaml` (`backend.graph.yaml`, `frontend.graph.yaml`, ...) |
| graph/system yaml loose alongside generated `app/`/`src/` code | every `*.graph.yaml` for an app lives under `apps/<app>/blueprint/` — mandatory subfolder, keeps FORM (blueprints) visibly separated from FUNCTION (generated code), adopted 2026-08-13 |
| App-prefixed node ids (`todo_schema`, `todo_orm_model`, ...) | De-prefixed (`data_schema`, `orm_model`, ...) — the app directory is already the namespace; propagated app-by-app per `refactoring-plan-v1.md` |

### Schema growth (v2.1 → v2.2)

GDW never had a `blueprint:` block — a `graph.yaml` was purely an input to a
build, nothing more. graph-code's v2.2 addition (see
`blueprint-schema-v2.2.md`) makes the blueprint itself a first-class object
with provenance:

- **`blueprint:` block** — `id`, `schema_version`, `graph_schema_version`,
  `domain_type`, `provenance` (`authored | build | reverse | roundtrip`),
  `parent_blueprint`.
- **`lineage:`** — append-only log of every forward/reverse pass that
  touched the blueprint (model, adapter, temperature, prompt hash, engine,
  timestamp) — makes drift attributable to a specific model/config instead
  of an anonymous number.
- **`drift:`** — a five-component vector (`structural`, `interface`,
  `intent`, `behavior`, `implementation`), each `[0,1]`, populated once a
  `reverse`-provenance blueprint is compared back against its parent. This
  round-trip fidelity measurement is graph-code's actual novel research
  contribution — nothing in GDW measures how well an artifact's structure
  survived a build/extract round trip.
- **AND/OR transition fan-out, exception-kind transitions, node-level
  `retry:`** — closed real gaps found while sketching SPL recipes as
  blueprint graphs (map-reduce fan-out, exception-routed recovery,
  retry-with-changed-params). None needed new YAML syntax — `to: [a, b]`
  (list) vs `to: {a, b}` (flow-mapping) was already distinguishable via
  plain `yaml.safe_load()`.
- **Node- and edge-level `use_cache`** — GDW cached per `(node, spec,
  tech_profile)` with only a global skip-cache flag. graph-code adds
  fine-grained invalidation: force one broken node to regenerate without
  discarding a whole component's cache, or mark one edge so its downstream
  node is forced to miss whenever that specific dependency changes.

### App-scoped settings

GDW hardcoded ports and similar values directly in each `graph.yaml` — this
caused a real incident (a stray second Vite instance silently moved to
`:5174` and broke CORS with no error pointing at the cause). graph-code
introduced `apps/<app>/blueprint/settings.yaml` + `${{ settings.KEY }}`
interpolation (`src/graph_code/settings.py`), plus a deterministic,
non-LLM `write_settings_config` step that emits `app/config.py`/
`src/config.ts` before the LLM build runs. Net effect, verified directly:
changing a setting and re-running only `write_settings_config` propagates
the change with zero LLM regeneration — the actual point of the mechanism,
not just single-sourcing the literal in YAML.

### Domain types proven

GDW only ever built one shape: `software` (the `todo` app, in both a
hand-crafted `apps/Claude/` variant and an LLM-built `apps/SPL/` variant, as
a controlled comparison). graph-code has built four `domain_type`s for
real, same pipeline underneath, differing only in `tech_profile` and a few
domain-specific validators:

| `domain_type` | Proven by | What's different |
|---|---|---|
| `curriculum` | `classical_mechanics` | `enforce_two_radical` — Two-Radical reducibility check |
| `software` | `todo`, `expense`, `dispatch`, `fastapi`, `kanban`, `mealie`, `jwt_provider`, ... | the GDW baseline case |
| `reactive_app` | `physics_simulator` | `function.events`/emitters/listeners, `event_graph` may cycle |
| `integrated` | `physics_app`, every `main.graph.yaml`-rooted app | graph of graphs — `imports:`, cross-component `function.calls` contracts |
| `workflow` | `etl_workflow` | steps exempt from compositionality, `function.transitions` compiled into a `flow_graph` that may cycle (retries/iterative refinement) |

### Tooling

GDW's `scripts/` was six standalone Python CLIs
(`concept_graph.py`, `prettify_graph.py`, `extract_path_b.py`,
`compare_variants.py`, `graph_yaml_style.py`, `new_app.sh`). graph-code
consolidated all of their real functionality into one installable `click`
CLI, `grafcode` (`src/graph_code/cli.py`), as eight subcommands: `validate`,
`order`, `stats`, `validate-system`, `prettify`, `new-app`, `extract`,
`compare`. See `CLAUDE.md`'s `grafcode` table for the full reference.

### Package structure

GDW's graph algorithms/loader only ever lived inside `spl/` (`graph_lib.py`,
`tools.py`) — not installable, not independently testable outside the SPL
runner. graph-code split this into a proper library:

- `src/graph_code/` — `loader.py` (`GraphDomain`, `load_domain`),
  `graph_lib.py` (13 pure functions, no I/O), `exceptions.py`, `settings.py`,
  `cli.py`, `_extract.py`, `_yaml_style.py`. Installable via
  `pip install -e ".[dev]"`, registers the `grafcode` console script.
- `spl/` — stays as the SPL-orchestrated build layer (`build_app.spl`,
  `build_component.spl`, `integrate_system.spl`, `compile_blueprint.spl`,
  `tools.py`, `tech_profiles.py`) that calls into the library, same
  separation of concerns GDW's own `CLAUDE.md` already described
  (`graph-code is a schema + algorithms library only; the SPL runner,
  LLM adapters, and .spl scripts live in the sibling SPL.py repo` —
  now literally true of this repo too, one layer down).

Rough size, for calibration: GDW's `spl/` was ~1,468 lines total.
graph-code's `spl/` grew to ~2,724 lines absorbing curriculum/
reactive_app/workflow support and the settings/cache-control machinery,
*plus* a new ~3,198-line `src/graph_code/` library that didn't exist in GDW
at all.

## What stayed the same

- The core three-tier idea (`primitives → concepts → applications`,
  `composed_of`/`depends_on` edges, capstone as the payoff) is unchanged —
  every graph-code app is still recognizably the same shape GDW's
  `framework.md` describes.
- The `{ spec, implementation, verification, documentation }` blueprint set
  per node/edge/component/system — unchanged discipline.
- Prose-field YAML style (`|` block literals, one bullet per `; `-separated
  clause, never double-quoted one-liners) — `grafcode prettify` is GDW's
  `prettify_graph.py` ported, same rules (with one real bug fixed along the
  way — `sequence=2, offset=0` flattened list indentation, corrected to
  `sequence=4, offset=2`).
- Recipe-79-style test gate + repair loop in `build_component.spl` — same
  cache/verify/repair shape, `identify_broken_node()` still string-tables
  its way from a failing traceback to a source node, just with a fixed
  generic fallback (scan the traceback for any `NODE_FILES[app_name]` path
  and prefer the last match, since an import chain lists the innocent
  importer before the actually-broken importee).

## What the framework-shape review (2026-08-14) concluded

See `README-lesson-learned.md` for the full write-up. Short version: the
framework-shape risk is close to zero at this point — four domain types
built for real, curriculum and software sharing one pipeline, pre-LLM
validation catching real structural errors for free. The actual risk to
the vision is prompt-fidelity, not architecture: the same handful of
hallucination classes (node-id-as-symbol confusion, structural metadata
like `defines:`/`ports:` being invisible to the LLM, training-prior naming
conventions overriding explicit specs, contamination — leaked tool-call
transcripts landing in generated files) recur across nearly every app
built so far, in both repos. `apps/todo-v6/README.md`'s leaked
`<function_calls>` transcript (found and cleaned up 2026-08-14) is a live
instance of the contamination class — confirmation the pattern isn't
merely historical.
