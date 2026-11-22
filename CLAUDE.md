# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install (editable, with dev deps)
pip install -e ".[dev]"

# Run all tests
pytest

# Run a single test class
pytest tests/test_graph_lib.py::TestAcyclic -v

# Run a single test
pytest tests/test_graph_lib.py::TestAcyclic::test_cyclic_graph_raises -v

# Run tests matching a keyword
pytest -k "contract" -v
```

`pytest` is pre-configured in `pyproject.toml` (`testpaths = ["tests"]`, `-p no:spark` to suppress a global pytest-spark plugin that would otherwise crash on a missing SPARK_HOME, `norecursedirs = ["fixtures"]`). The recipe tests (`tests/test_build_component.py`, `test_build_app.py`, `test_compile_blueprint.py`) use a scripted model: no real LLM calls. The build ones need Docker and the `appgraph-verify:py3.12` image (`docker build -t appgraph-verify:py3.12 -f src/appgraph/docker/python.Dockerfile src/appgraph/docker`) and are skipped without it. Don't run GraphLang's own full test suite from here: it overwrites tracked files in the graflang repo.

### `appgraph` — developer CLI

`pip install -e .` also registers the `appgraph` console script (alias `agr`) (`src/appgraph/cli.py`, a `click` group). Commands:

| Command | Purpose |
|---|---|
| `appgraph validate <graph.yaml>` | `validate_full()` a component graph, or the whole system (every `imports:` entry + cross-component call contracts) if the graph has `imports:` — one command, no separate system-level variant |
| `appgraph order <graph.yaml>` | Print `build_order()` — the order the `build_component` recipe generates nodes |
| `appgraph validate-all <dir>` | Validate every `graph.yaml` under a folder |
| `appgraph report <graph.yaml> [--out FILE]` | Node/edge/import counts. `--out` writes to a file (bare filename resolves under `~/app-graph/report/`) instead of stdout |
| `appgraph prettify <path> [--write]` | Normalize `*.graph.yaml` prose scalars to `\|` block literals with `; `-split bullets |
| `appgraph new-app <name> <backend_port> <frontend_port>` | Scaffold a new `apps/<name>/blueprint/` skeleton (settings.yaml + three graph.yaml stubs + frontend npm/vite scaffold) |
| `appgraph extract --repo-path ... [--output-dir ...] --app-name ... [--llm ...]` | AST/regex-analyze an existing repo (FastAPI routes, Pydantic schemas, SQLAlchemy models, Vue components, ...) and write draft blueprint/ artifacts with `TODO:` markers. `--output-dir` defaults to `~/app-graph/output/<app-name>`. `--llm` adds the semantic pass: the `compile_blueprint` recipe (classify the shape, then one or three blueprints, each validated and repaired up to `max_repair_attempts`, default 2). Resumable twice over: `<output-dir>/.appgraph_cache/` holds the clone, the AST scan and a marker of a finished `--llm` pass; while the pass runs, a GraphLang checkpoint (`--persistence checkpoint`, the default; `llm-<key>.checkpoint.json`) lets a run that died resume after its last top-level step (a repair loop that died midway restarts that loop). `--skip-cache` ignores both and starts afresh. `--max-llm-calls` caps the pass (default 20) |
| `appgraph build TARGET [--input-dir ...] [--output-dir ...] [--tech-profile ...] [--llm ...] [--max-llm-calls N] [--max-test-attempts N] [--no-cache]` | Generate and test code from a blueprint: `builder.build_app()` (the `build_app` recipe) when TARGET has `imports:`, else `builder.build_component()` (the `build_component` recipe). TARGET is a `.graph.yaml` path or an app name resolved under `--input-dir` (default `~/app-graph/input`). Python tests run in the `appgraph-verify:py3.12` container, Vue tests in a per-lockfile node image (`build/node_image.py`); both without network |
| `appgraph ide [--apps-root ...]` | Launch Graph IDE (`src/appgraph/graph-ide`) — starts the `uvicorn` backend (`:8880`) and `npm run dev` frontend (`:8881`); `--api-port`/`--dev-port` to override, `--no-frontend` for API only, `--apps-root` for which `<app>/blueprint/` tree to browse (default `~/app-graph/ide`) |
| `appgraph tools clean-port <port> [port ...]` | Kill whatever process is listening on the given port(s) — SIGTERM then SIGKILL |
| `appgraph tools scaffold-fastapi` / `scaffold-vue` | Bootstrap a python_fastapi / vue_typescript project shell |
| `appgraph tools suggest-graph-clusters <graph.yaml> [--seed NODE_ID ...] [--format text\|json]` | Prototype extractor-clustering: ancestor-closure split of one graph into sub-graph candidates, seeded by `function.exports[].from` (or explicit `--seed`) — see `graph_lib.py`'s `suggest_clusters()` and `apps/README-new-apps.md`'s "Prototype: appgraph tools suggest-graph-clusters" section |
| `appgraph drift <graph_a.graph.yaml> <graph_b.graph.yaml> [--dims ...]` | Compute the drift report (`docs/DEV/BUILD/blueprint-schema-v2.2.md` §3, 5 components + `overall` aggregate) between two blueprints. `structural`/`interface`/`behavior`/`implementation` are free graph-diffs (`graph_lib.py`'s `*_drift`/`drift_report`); `intent` (`intent_drift`, over `intent_text()` — rationale text + `docs` field) needs `--llm ADAPTER:MODEL` (LLM-as-judge: `judge.py`, one dd-llm call with `prompts/intent_drift.md`; default `claude_cli:claude-sonnet-5-5`) or is absent. `--dims dim1,dim2,...` restricts which components run. Report-only — does not write into either file's `blueprint.drift` block. The 5 components are reported in order `intent, behavior, structural, interface, implementation` — top-down by abstraction level, why (`intent`, the human rationale) → what it should do (`behavior`/verification) → how it's shaped (`structural`, the graph topology) → how it's exposed (`interface`, signatures/contracts) → how it's built (`implementation`, tech-stack primitives); a "concept before mechanism" narrative |

Ported and adapted from `graph-driven-workflow/scripts/` (see that repo's `scripts/README.md` for the originals) — `extract`/`new-app` target this repo's actual `apps/<app>/blueprint/` + `blueprint:`-block + `${{ settings.KEY }}` convention, not the old flat `system.yaml`/`components/` layout.

## Architecture

The package lives in `src/appgraph/`. The schema library is three files:

- **`exceptions.py`** — `ToolFailed` (raised before any LLM call on hard validation failure) and `ValidationWarning` (non-fatal; has `code`, `message`, `context` fields).
- **`loader.py`** — `GraphDomain` dataclass + `load_domain(yaml_path)`. Accepts two YAML formats and normalizes them into one representation.
- **`graph_lib.py`** — 22 pure functions that operate on a `GraphDomain`. No I/O; no LLM calls. The form-space algorithms (`acyclic`, `reducible`, `productivity_order`, `learning_path`, `gap`, `build_order`) are the sibling **zinet** library's (`zinet.algorithms`), reached through `_zinet_graph()` / `_in_zinet()` (which turn zinet's errors back into `ToolFailed`); `tests/test_zinet_algorithms.py` pins the behaviour that must not change (order of ties, optional edges, two-radical rule). Events, transitions, call contracts, drift and clustering stay here. Includes the drift report: `structural_drift`/`interface_drift`/`behavior_drift`/`implementation_drift` (graph-diff, matched by node id), `intent_text()`/`intent_drift()` (rationale text — `defines`/`comment`/`spec.user_story`/`docs` — scored via an injected `judge` callable, `None` without one), and `drift_report()` combining whichever components `dims` selects into a report plus an `overall` mean — see `docs/DEV/BUILD/blueprint-schema-v2.2.md` §3. Also `suggest_clusters()` — deterministic ancestor-closure clustering (seeded by `function.exports`) that suggests how to split one monolithic graph into modular sub-graphs; a prototype toward eventually teaching `appgraph extract` to auto-split extracted components, exposed as `appgraph tools suggest-graph-clusters`.

The build side (GraphLang, `docs/DEV/graflang-refactor.md`):

- **`recipes/<name>/`** — `build_component`, `build_app`, `compile_blueprint`: each a GraphLang `<name>.graph.yaml` (compact `steps:` form) with `prompts/*.md`, `policies/*.cedar` and `graflang.errors.yaml` (beside the top graph; it must list the codes of every part used — `build_app` repeats `build_component`'s, and a test checks they agree). `compile_blueprint/validate_repair/` and `build_component` are used as parts. `graf validate recipes/<name>/<name>.graph.yaml` checks one. Prompts are graph-code's `.spl` bodies with only each function's own parameters renamed to `{{in_x}}` (`scripts/spl_prompts.py`; spl3 had no brace escape, so `{{`/`${{ settings.X }}` in them are literal and must stay).
- **`run.py`** — `run_recipe(name|path, inputs, *, llm, max_llm_calls, max_steps, checkpoint, resume, record, replay, log_dir=~/app-graph/logs, llm_timeout, max_tokens)` → `RecipeRun(outputs, summary, log_path, llm_calls, exit, error_code)`; raises `RecipeError`. A thin layer over GraphLang's `graphlang.recipes` (graflang ≥ 0.3, shared with work-graph): recipe lookup by name, the `claude_cli` default and the log folder are app-graph's; one-pass prompt filling, `python3` as this interpreter, the output budget and adapter timeout are GraphLang's. `llm` is a dd-llm `ADAPTER[:MODEL]` string or an object with `generate(prompt, model=None, **opts)` (what tests pass).
- **`builder.py`** — `build_component()` / `build_app()`: inputs, call cap and step cap for a run, and a `BuildResult`/`AppBuildResult` the CLI prints.
- **`build/`** — the deterministic half, plain functions with no LLM: `blueprint` (order, specs, context, components, applications), `cache` (`<output>/.spl_cache/`, same keys as graph-code), `files`, `verify`, `compile`, `text`, `server`, `tech_profiles`, `node_image`; `steps.py` holds the recipe steps, which a recipe calls as `python3 -I -m appgraph.build.tool STEP` (JSON on stdin, keys are the port names without `in_`; JSON out).
- **`judge.py`** — the intent-drift judge. **`docker/`** — the Python test image, with `run_tests.py` and `integrate.py` baked in.

GraphLang rules that bit during the port (keep them in mind when editing a recipe): prompts are filled in one pass (graflang ≥ 0.3; inputs are still listed identifiers first, free text last); `on: [a, b]` fires once per arriving token (use it only for exclusive branches; `in: {x: [a, b]}` takes whichever ran); a loop variable `$loop.X` must be read under the same name `X`, and a part's inputs can't come straight from `$loop`; the expression language has no `a if c else b`; `'\n'` in a double-quoted YAML expression breaks parsing; a SOLVE subprocess runs in the recipe folder with only `PATH`/`PYTHONUTF8` (+ `env_passthrough`) set, so pass absolute paths (its `python3` is the interpreter running the recipe); inside a part, commands resolve relative to the *using* graph; a `risky: true` step must be reachable only through a GUARD's `allow` port.

### The two graph objects inside `GraphDomain`

Every parsed domain contains two NetworkX digraphs:

| Field | Structure | Direction | May cycle? |
|---|---|---|---|
| `form_graph` | All form nodes (primitives + `form.nodes`) | `dep → node` (prerequisite → dependent) | No — always a DAG |
| `event_graph` | Bipartite: nodes and events | `node → event` (emit), `event → node` (notify) | Yes |

Edge direction convention: **prerequisite points toward dependent**. `nx.topological_sort(form_graph)` therefore returns primitives before the concepts that depend on them, which is the correct generation order.

### Mandatory vs optional edges

`form_graph` carries both edge kinds. Most algorithms should operate only on mandatory edges (`composed_of`, `depends_on`). Use the internal helper:

```python
G = _mandatory_subgraph(graph)   # strips enriched_by / optionally_depends_on
```

`learning_path`, `build_order`, `reducible`, and `productivity_order` all call this. `enrichment_path` is the one function that uses optional edges intentionally.

### Workflow space (`domain_type: workflow`)

Steps are `form.nodes` that are exempt from compositionality — `reducible()`/Two-Radical
checks don't apply, since a workflow step doesn't need to trace back to primitives. The
behavior lives in two new pieces:

- **`node.phases`** — optional `{pre, execute, post}` sub-dict on a node (ETL-style: `pre`
  for state prep/validation, `execute` for the step body, `post` for formatting/routing).
  Only `execute` is meaningful; `phases` rides through as ordinary node data, same as
  `spec`/`verification`/`docs` — no dedicated parsing.
- **`function.transitions`** — a specialized edge type for action-routed step dispatch
  (PocketFlow-style): `{from, to, action, condition, comment}`, one entry per possible
  routing outcome. Compiled into `GraphDomain.flow_graph`. Unlike `form_graph`, this graph
  **may cycle** — retries and iterative refinement belong here, not in `form_graph`.

A top-level `entry: <node_id>` names the starting step. `validate_transitions(graph)`
raises `ToolFailed` for transitions referencing undeclared nodes, an undeclared `entry`,
or two transitions leaving the same node on the same `action` toward different
destinations (ambiguous routing); it returns `ValidationWarning("UNREACHABLE_STEP", ...)`
for steps unreachable from `entry`. `flow_cycles(graph)` is purely informational — cycles
are expected, not a defect. `validate_full()` runs `validate_transitions()` whenever
`graph.transitions` is non-empty. See `apps/etl_workflow.graph.yaml`.

### v1.0 flat format

`load_domain()` auto-detects and normalizes the legacy ConceptBook YAML format (top-level `primitives:` / `concepts:` keys, no `form:` / `function:` wrapper). Detection is by absence of the `form` key. The result is identical to a v2.1 parse — callers never need to distinguish.

### Key schema fields

| Field | Type | Purpose |
|---|---|---|
| `domain_type` | `curriculum \| software \| reactive_app \| integrated \| workflow` | Compilation profile |
| `domain` | `str` (slash-separated path) | Hierarchical classification for registry/gap analysis |
| `target_languages` | `list[str]` | Guides SPL runner tech-profile selection |
| `enforce_two_radical` | `bool` (default `false`) | Opt-in: `validate_full()` raises if graph is reducible from `first_radical_primitives` alone |
| `first_radical_primitives` | `list[str]` | Subset of primitives; used by `reducible(first_radical_only=True)` |

### validate_full vs individual checks

`validate_full(graph)` is the single composite entry point: it runs `acyclic()` (always), the Two-Radical check (if `enforce_two_radical`), `validate_events()` (if function space is non-empty), `check_call_contracts()`, and `validate_transitions()` (if `function.transitions` is non-empty). Individual functions can be called directly when only a targeted check is needed.

## Apps

`apps/` has one file per `domain_type`:

| File | Profile |
|---|---|
| `classical_mechanics_flat.graph.yaml` | v1.0 flat (backward-compat) |
| `classical_mechanics.graph.yaml` | `curriculum` with `enforce_two_radical: true` |
| `auth_middleware.graph.yaml` | `software` — imports `jwt_provider` |
| `physics_simulator.graph.yaml` | `reactive_app` — declares events/emitters/listeners |
| `physics_app.graph.yaml` | `integrated` — graph of graphs |
| `etl_workflow.graph.yaml` | `workflow` — phases + action-routed transitions with a retry loop |
| `todo/*.graph.yaml` | `integrated` app assembled from imported `software` components (backend/frontend) |

## Tests

`tests/conftest.py` defines six fixtures using inline YAML strings (no file I/O, so tests are fully isolated from the `apps/` files). The helper `_load_yaml_str(yaml)` writes to a tempfile and calls `load_domain()` — use it in any test that needs a custom one-off graph.

`tests/test_graph_lib.py` tests the public API via the fixtures, plus a `TestExampleFiles` class that loads real files from `apps/`.

## Design constraints

- `ToolFailed` must be raised **before** any LLM call. It is the signal to the SPL runner to abort generation rather than spend tokens on a broken graph.
- `app-graph` is a schema + algorithms library plus the GraphLang recipes that build from it. LLM calls happen only inside recipe runs (through dd-llm, via `run.py`) and the drift judge; the library (`loader`, `graph_lib`, `build/`) never calls a model. Nothing uses `spl3`/`spl-llm` any more.
- Every recipe step that writes files is `risky: true` behind a Cedar GUARD (`write_root_ok`: absolute, under home or the temp folder). Keep it that way when adding a writing step.
- All source files use `from __future__ import annotations` for Python 3.9 compatibility with modern type-hint syntax.
