# app-graph

Graph-driven code generation. You describe an app (or a curriculum) as a
`graph.yaml` **blueprint**, a graph of typed nodes and edges in the
*Unified Duality Graph Schema v2.1+*. app-graph checks the blueprint and
builds real, tested code from it with an LLM. The graph comes first and is
the source of the implementation; it is not a diagram drawn from code that
already exists.

app-graph continues [graph-code](https://github.com/digital-duck/graph-code)
(`grafcode` 0.1.1, which stays as it was). The difference is the engine:

- In graph-code, the LLM workflows were `.spl` scripts run by `spl3`.
- In app-graph they are **[GraphLang](https://github.com/digital-duck/graflang)
  recipes**. A recipe is a graph you can validate, draw, cap, checkpoint
  and log. Model calls go through `dd-llm`. Tests run in Docker.

The blueprint schema, the graph library and the CLI are unchanged. The
migration is recorded in `docs/DEV/graflang-refactor.md`.

## Quick start

```bash
pip install app-graph            # or: pip install -e ".[dev]" from a checkout

appgraph validate apps/todo/blueprint/main.graph.yaml      # the system and every import
appgraph build apps/jwt_provider/blueprint/component.graph.yaml --max-llm-calls 12
appgraph ide --apps-root apps                               # browse every app's graph
```

`agr` is a short alias for `appgraph`.

`build`, `extract --llm` and `drift --llm` call a model through a dd-llm
adapter (`--llm ADAPTER[:MODEL]`, default `claude_cli`). Building also needs
**Docker**:

- Python components are tested in the `appgraph-verify:py3.12` image. Build it once:

  ```bash
  docker build -t appgraph-verify:py3.12 -f src/appgraph/docker/python.Dockerfile src/appgraph/docker
  ```

- Vue components are tested in an image made from their lockfile. It is built automatically the first time.

The test containers have no network access.

Commands that write files default to folders under `~/app-graph/`:
`input`, `output`, `report`, `ide` and `logs`. Pass
`--output-dir`, `--input-dir`, `--out` or `--apps-root` to write somewhere
else.

The full command reference is in **`docs/GUIDE/User-Guide.md`**. The
condensed version for AI coding agents is in `CLAUDE.md`.

## What's in a `graph.yaml`

Every parsed graph becomes a `GraphDomain` that holds two graphs:

| Graph | Structure | Direction | May cycle? |
|---|---|---|---|
| `form_graph` | Primitives and `form.nodes`: the *what* (components, docs, steps) | `dep → node` (prerequisite → dependent) | No, always a DAG |
| `event_graph` | Bipartite graph of nodes and events: the *reactive* behaviour | `node → event`, `event → node` | Yes |

The fields of a node have these roles:

- `spec.interface`, `spec.contract` and `verification` are what a build reads to generate and test that node.
- `composed_of` and `depends_on` are mandatory edges; `enriched_by` and `optionally_depends_on` are optional ones.
- `needs` states an application-level dependency.

There are five `domain_type` profiles:

| Profile | Meaning |
|---|---|
| `curriculum` | a course or curriculum |
| `software` | one software component |
| `reactive_app` | event-driven |
| `integrated` | a graph of graphs: `main.graph.yaml` imports the component graphs |
| `workflow` | action-routed `function.transitions`, cycles allowed |

A `blueprint:` block (schema v2.2) records the graph's provenance
(`authored | build | reverse | roundtrip`) and a `lineage:` log of each LLM
pass. The schema is in `docs/DEV/BUILD/blueprint-schema-v2.2.md`.

## How a build runs

`appgraph build` runs one of the three recipes in `src/appgraph/recipes/`:

| Recipe | Used by | What it does |
|---|---|---|
| `build_component` | `build` on a component | For each node in build order: write its code, cache it, check the node and its edges, refine it once if needed. Then run the component's tests, and repair the node the failure points at, up to `--max-test-attempts` times. |
| `build_app` | `build` on a system (a graph with `imports:`) | Uses `build_component` once per component. Then writes an acceptance test per application, runs them against the live backend in a container, and writes the README. Stops at the first component that fails. |
| `compile_blueprint` | `extract --llm` | Classifies the repo's shape, then drafts one blueprint or three (backend, frontend, main). Each draft is validated and repaired, then written. If no tech profile fits, it also writes a `TECH_PROFILE_DRAFT.md` for you to review. |

All three follow the same rules:

- Each prompt is a file under the recipe's `prompts/`.
- Every step that writes files passes a Cedar policy first (`policies/*.cedar`). Writes are allowed only under your home folder or the temporary folder.
- Every run has a cap on model calls.
- Each run writes a log under `~/app-graph/logs/`.

Generated code is cached per node in `<output>/.spl_cache/`. That cache can
be read by both graph-code and app-graph. `extract --llm` keeps a checkpoint,
so a pass that died partway resumes where it stopped.

The deterministic work happens outside the recipes, in `appgraph.build`:
reading the blueprint, caching, writing, verifying and running tests. These
are plain Python functions. A recipe calls them as
`python -m appgraph.build.tool STEP`.

## Repository layout

```
app-graph/
  src/appgraph/
    loader.py         GraphDomain + load_domain() (v1.0 flat and v2.1+ YAML)
    graph_lib.py      pure functions over a GraphDomain (validate_full, build_order, drift, clusters, ...)
    exceptions.py     ToolFailed (hard failure, before any LLM call) / ValidationWarning
    settings.py       ${{ settings.KEY }} interpolation from an app's settings.yaml
    _extract.py       the AST/regex pass of `appgraph extract`
    cli.py            the `appgraph` / `agr` console script
    run.py            run_recipe(): a recipe on the GraphLang runtime, with a model, a call cap, logs, checkpoints
    builder.py        build_component() / build_app(): what `appgraph build` calls
    judge.py          the intent-drift judge (one dd-llm call)
    build/            the deterministic build steps (blueprint, cache, files, verify, tech_profiles, ...)
    recipes/          build_component/, build_app/, compile_blueprint/ (graph, prompts, policies, errors)
    prompts/          intent_drift.md
    docker/           the Python test image and its in-container runners
    graph-ide/        browser viewer and editor for blueprints (FastAPI + SVG)
  apps/               blueprints (apps/<app>/blueprint/*.graph.yaml), one example per domain_type
  tests/              pytest suite (Docker tests are skipped when Docker is absent)
  docs/GUIDE/User-Guide.md      command reference
  docs/DEV/                     plans, schema, the GraphLang refactor
```

## The `appgraph` CLI

| Command | Purpose |
|---|---|
| `appgraph validate <graph.yaml>` | `validate_full()` a component, or the whole system (every import + call contracts) if it has `imports:` |
| `appgraph validate-all <dir>` | Validate every `graph.yaml` under a folder |
| `appgraph order <graph.yaml>` | Print `build_order()` |
| `appgraph report <graph.yaml> [--out FILE]` | Node/edge/import counts |
| `appgraph prettify <path> [--write]` | Normalize prose scalars to `\|` block literals |
| `appgraph diagram ...` | Inspect and add diagram hints |
| `appgraph new-app <name> <backend_port> <frontend_port>` | Scaffold a new `apps/<name>/blueprint/` |
| `appgraph extract --repo-path/--repo-url ... --app-name ... [--llm ...]` | Draft blueprints from an existing repo; `--llm` adds the semantic pass (`compile_blueprint`) |
| `appgraph build TARGET [--llm ...] [--max-llm-calls N]` | Generate and test code for a component or a whole app |
| `appgraph drift <graph_a> <graph_b> [--dims ...] [--llm ...]` | The 5-component drift report; `--llm` adds `intent` |
| `appgraph ide [--apps-root ...]` | Launch Graph IDE |
| `appgraph tools clean-port / scaffold-fastapi / scaffold-vue / suggest-graph-clusters` | Small utilities |

## Testing

```bash
pytest                      # the full suite (about 2 minutes with Docker)
pytest -k "contract" -v     # by keyword
```

The recipe tests use a scripted model, so they make no real LLM calls.
They check the recipes against graph-code's own output. For example, the
todo backend comes out byte for byte the same, in 7 model calls, and in 0
calls when the cache has it.

## Status

The **forward pass** (blueprint → tested code) works for components and
for integrated apps. See `docs/DEV/BUILD/README.md` for the results per app.

The **reverse pass** (repo → blueprint) is `appgraph extract --llm`, and its
output is tagged `provenance: reverse`. `fief` is a real example.

**Drift** (`appgraph drift`) reports five components:

- `structural`, `interface`, `behavior` and `implementation` are graph diffs matched by node id.
- `intent` is judged by the model given with `--llm`.

The report is printed only; nothing is written back to a blueprint.

## License

Apache License 2.0. See `LICENSE`.
