# app-graph

> **app-graph** continues [graph-code](https://github.com/digital-duck/graph-code) (`grafcode` 0.1.1, left as it was) and is being moved onto
> [GraphLang](https://github.com/digital-duck/graflang): the LLM build workflows become GraphLang recipes, the blueprint schema and the
> library stay. Plan and progress: `docs/DEV/graflang-refactor.md`. Until that is done, parts of this README still describe the `spl3` pipeline.

Graph-driven code and curriculum generation — the **Unified Duality Graph
Schema v2.1+**, a `graph.yaml` format that represents an app (or a
curriculum) as a graph of typed nodes and edges, plus a small pure-Python
library and CLI for validating, inspecting, and scaffolding those graphs.

An LLM-driven build pipeline (in the sibling `SPL.py` repo) reads a
`graph.yaml` and generates real, tested application code from it — the graph
is upstream of the implementation, a blueprint rather than a diagram of code
that already exists. This repo owns the schema, the graph algorithms, and
the tooling around them; it does not itself call an LLM or generate code.

## Quick start

```bash
pip install appgraph   # or: pip install -e ".[dev]" from a repo checkout

appgraph --help
appgraph validate apps/todo/blueprint/backend.graph.yaml    # single component
appgraph validate apps/todo/blueprint/main.graph.yaml       # system + every import
appgraph ide --apps-root apps   # browse every app's graph in the browser
```

`pip install appgraph` pulls in `spl-llm` (the `spl3` CLI) automatically,
so `extract --llm`/`build`/`drift --llm` work right after install — no
separate clone of the sibling `SPL.py` repo needed. `appgraph ide`'s Vue
frontend is the one piece that still needs a manual one-time `npm install`
(see its section in the User Guide), since `pip` can't install npm
packages. Commands that write files default into `~/app-graph/{input,
output, report, ide}` rather than into this repo's own `apps/` — pass
`--output-dir`/`--input-dir`/`--out`/`--apps-root` explicitly to use this
repo's `apps/` instead, as above.

See **`docs/GUIDE/User-Guide.md`** for the full `appgraph` command reference
and worked examples, and `CLAUDE.md` for the condensed command table and
architecture notes aimed at an AI coding agent working in this repo.

## What's in a `graph.yaml`

Every parsed graph produces a `GraphDomain` with two graphs:

| Graph | Structure | Direction | May cycle? |
|---|---|---|---|
| `form_graph` | Primitives + `form.nodes` — the *what*: components, docs, steps | `dep → node` (prerequisite → dependent) | No — always a DAG |
| `event_graph` | Bipartite nodes/events — the *reactive* behavior | `node → event`, `event → node` | Yes |

A node's `spec.interface`/`spec.contract`/`verification` fields are what a
build pipeline reads to generate and test that node's code; `composed_of`/
`depends_on` edges are mandatory structure, `enriched_by`/
`optionally_depends_on` are optional, and `needs` expresses an
application-level (not structural) dependency. Five `domain_type` profiles
share this one schema: `curriculum`, `software`, `reactive_app`,
`integrated` (a graph of graphs — `main.graph.yaml` importing component
graphs), and `workflow` (action-routed, cycle-permitting `function.transitions`
for PocketFlow-style step dispatch).

A `blueprint:` metadata block (schema v2.2, additive) tracks a graph's own
provenance — `authored | build | reverse | roundtrip` — plus an append-only
`lineage:` log of every LLM pass that touched it. See
`docs/DEV/BUILD/blueprint-schema-v2.2.md` for the full schema and the
"Status" section below for what's actually implemented today.

## Repository layout

```
app-graph/
  src/appgraph/     the library + CLI + packaged assets (all shipped in the wheel)
    loader.py            GraphDomain dataclass + load_domain() — parses v1.0 flat and v2.1+ YAML
    graph_lib.py          14 pure functions over a GraphDomain (validate_full, build_order, ...)
    exceptions.py        ToolFailed (hard validation failure) / ValidationWarning (soft)
    settings.py           ${{ settings.KEY }} interpolation from an app-scoped settings.yaml
    _extract.py            AST/regex analysis + draft-blueprint generation behind `appgraph extract`
    cli.py                  the `appgraph` console script (click group)
    spl/                    the forward-build .spl workflows (build_component/build_app/integrate_system)
    graph-ide/               browser viewer+editor for blueprint graphs (FastAPI + vanilla-JS SVG renderer)
  spl -> src/appgraph/spl                    repo-root symlink (dev convenience, e.g. `spl3 run spl/...`)
  tools/graph-ide -> ../src/appgraph/graph-ide   repo-root symlink (dev convenience)
  apps/               every app's blueprint (apps/<app>/blueprint/*.graph.yaml) + generated code
  tests/              pytest suite — fixtures in conftest.py, real apps/ files exercised too
  docs/
    GUIDE/User-Guide.md          appgraph command reference (this doc's companion)
    DEV/BUILD/                    build-plan history, schema spec, refactor notes, per-app logs
    DEV/PAPER/                    literature review / related-work notes for the TMLR submission
```

`spl/` and `tools/graph-ide/` are canonically `src/appgraph/spl/` and
`src/appgraph/graph-ide/` — package data shipped inside the `appgraph`
wheel (`pyproject.toml`'s `[tool.setuptools.package-data]`) so `appgraph
extract --llm`/`build`/`ide` work after a plain `pip install appgraph`,
not just from a git checkout. The repo-root `spl/`/`tools/graph-ide`
symlinks exist purely so every doc/script that types `spl/build_app.spl` or
`tools/graph-ide` from the repo root keeps working unchanged. The `spl3`
CLI and LLM adapters themselves live in the sibling `SPL.py` repo
(published as `spl-llm`, a real `app-graph` dependency) — this repo has no
LLM-calling code of its own, `appgraph extract --llm`/`build`/`drift --llm`
shell out to `spl3 run`.

## The `appgraph` CLI

Installed as a console script by `pip install appgraph` (or `pip install
-e ".[dev]"` from a checkout). Full reference, options, and examples:
`docs/GUIDE/User-Guide.md`.

| Command | Purpose |
|---|---|
| `appgraph validate <graph.yaml>` | `validate_full()` a component graph, or the whole system (every import + call contracts) if it has `imports:` |
| `appgraph order <graph.yaml>` | Print `build_order()` |
| `appgraph report <graph.yaml> [--out FILE]` | Node/edge/import counts |
| `appgraph prettify <path> [--write]` | Normalize prose scalars to `\|` block literals |
| `appgraph new-app <name> <backend_port> <frontend_port>` | Scaffold a new `apps/<name>/blueprint/` |
| `appgraph extract --repo-path/--repo-url ... [--output-dir ...] --app-name ...` | Analyze an existing repo and draft blueprint artifacts, with `--llm` for a semantic pass. Resumable — see the User Guide's caching section |
| `appgraph build TARGET [--input-dir ...] [--output-dir ...]` | Generate code for an app/component from its blueprint |
| `appgraph compare <dir_a> <dir_b> [--out FILE]` | Diff two build outputs of the same component |
| `appgraph ide [--apps-root ...]` | Launch Graph IDE (browser viewer/editor) |
| `appgraph drift <graph_a.graph.yaml> <graph_b.graph.yaml> [--dims ...] [--out FILE]` | Compute the drift report (5 components + overall) between two blueprints — `--llm` adds the `intent` component, `--dims` restricts which run |
| `appgraph tools clean-port <port> [port ...]` | Kill whatever's listening on the given port(s) |
| `appgraph tools spl-lint [FILES...] [--fix]` | Find/fix unescaped quotes in `.spl` prompt bodies |

## Apps

`apps/` holds one directory per app, each with an `apps/<app>/blueprint/`
containing its `*.graph.yaml` source and (once built) sibling generated-code
directories. Full status/history per app: `apps/README.md` and
`docs/DEV/BUILD/README-TODO.md`. One file per `domain_type` in
`apps/*.graph.yaml` demonstrates each schema profile
(`classical_mechanics.graph.yaml` — curriculum, `auth_middleware.graph.yaml`
— software, `physics_simulator.graph.yaml` — reactive_app,
`physics_app.graph.yaml` — integrated, `etl_workflow.graph.yaml` — workflow).

Currently ported/authored: `classical_mechanics`, `conduit`, `dispatch`,
`etl_workflow`, `expense`, `fastapi`, `fullstack`, `jwt_provider`, `kanban`,
`mealie`, `physics_app`, `todo` — plus `fief`, extracted from an external
repo via `appgraph extract --llm` and still under review (its blueprint has
`TODO:` markers and hasn't been fully authored/validated yet — see
`apps/README-new-apps.md`).

## Testing

```bash
pytest                                              # full suite
pytest tests/test_graph_lib.py::TestAcyclic -v      # one class
pytest -k "contract" -v                             # by keyword
```

`tests/conftest.py` defines inline-YAML fixtures for isolated unit tests,
plus a `TestExampleFiles`/`TestLoader` class that loads the real files under
`apps/`. Any `graph.yaml` committed under `apps/` is expected to load and
carry a non-empty `graph_id` — an in-progress extraction like `fief`'s can
transiently fail this until its blueprint is finished being authored.

## Status

**Forward pass** (blueprint → generated, tested code) is real and working —
`spl3 run spl/build_app.spl` builds a full app from its blueprint via an LLM
adapter, with disk-backed per-node caching. See `docs/DEV/BUILD/README.md`
for verified results across the apps above.

**Reverse pass** (artifact → blueprint extraction) exists informally via
`appgraph extract --llm` (`spl/compile_blueprint.spl`, which tags its output
`provenance: reverse`) — not yet the systematic, corpus-scale miner
envisioned in `docs/DEV/BUILD/README-TODO.md` §3, but real `reverse`-
provenance blueprints (e.g. `fief`, extracted 2026-08-15) now exist to
measure against.

**Drift** (§3 of `docs/DEV/BUILD/blueprint-schema-v2.2.md`) — `appgraph
drift <graph_a> <graph_b>` reports the 5-component drift vector plus an
`overall` aggregate, one pure function per component in `graph_lib.py`
(`structural_drift`/`interface_drift`/`intent_drift`/`behavior_drift`/
`implementation_drift`, combined by `drift_report()`), each partitioning a
distinct aspect of the schema. 4 components are free — pure graph-diffs
over two `GraphDomain`s, matched by node id. The 5th, `intent`
(`intent_drift()`, over `graph_lib.intent_text()` — each node's
`defines`/`comment`/`spec.user_story` **and** its `docs` field, since a
README-style description is exactly how a human expresses intent), needs
`--llm ADAPTER:MODEL`: rather than the schema doc's original "embedding
distance" (which would need a separate, hardcoded embeddings-API
dependency this repo otherwise has none of), it's computed by LLM-as-judge
— the same model named by `--llm` scores meaning drift directly
(`spl/compute_intent_drift.spl`), mirroring how `compile_blueprint.spl`
already uses `GENERATE` to draft rather than judge. `--dims
dim1,dim2,...` restricts the report to specific components, skipping
computation (and the LLM call) for the rest. Report-only for now — nothing
writes the result back into a blueprint's own `blueprint.drift` block yet.

## License

Apache License 2.0 — see `LICENSE`.
