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

`pytest` is pre-configured in `pyproject.toml` (`testpaths = ["tests"]`, `-p no:spark` to suppress a global pytest-spark plugin that would otherwise crash on a missing SPARK_HOME).

### `grafcode` — developer CLI

`pip install -e .` also registers a `grafcode` console script (`src/graph_code/cli.py`, a `click` group). Commands:

| Command | Purpose |
|---|---|
| `grafcode validate <graph.yaml>` | `validate_full()` a component graph, or the whole system (every `imports:` entry + cross-component call contracts) if the graph has `imports:` — one command, no separate system-level variant |
| `grafcode order <graph.yaml>` | Print `build_order()` — the order `build_component.spl` generates nodes |
| `grafcode report <graph.yaml> [--out FILE]` | Node/edge/import counts. `--out` writes to a file (bare filename resolves under `~/graph-code/report/`) instead of stdout |
| `grafcode prettify <path> [--write]` | Normalize `*.graph.yaml` prose scalars to `\|` block literals with `; `-split bullets |
| `grafcode new-app <name> <backend_port> <frontend_port>` | Scaffold a new `apps/<name>/blueprint/` skeleton (settings.yaml + three graph.yaml stubs + frontend npm/vite scaffold) |
| `grafcode extract --repo-path ... [--output-dir ...] --app-name ...` | AST/regex-analyze an existing repo (FastAPI routes, Pydantic schemas, SQLAlchemy models, Vue components, ...) and generate draft blueprint/ artifacts with `TODO:` markers. `--output-dir` defaults to `~/graph-code/output/<app-name>` if omitted. Resumable at two granularities: `<output-dir>/.grafcode_cache/` caches the clone/AST-scan and a completed-`--llm`-pass marker (skip whole stages on rerun); the `--llm` pass itself runs as a durable spl3 workflow (`--persistence sqlite` by default, `--workflow-id` derived from the run's inputs, active even under `--skip-cache`) that checkpoints every GENERATE/CALL step, so a run that dies mid-repair-loop resumes from its last step instead of redoing every attempt — `--skip-cache` forces a fresh run (skips reading stale clone/AST/marker content, mints a one-off workflow-id so it can't resume a stale completed run) while still writing fresh cache/checkpoints as it goes. The semantic pass is fail-fast by default (`max_repair_attempts: 0` in `compile_blueprint.spl`) — an invalid-YAML generation reports `FAILED` immediately rather than self-repairing |
| `grafcode build TARGET [--input-dir ...] [--output-dir ...] [--tech-profile ...]` | Generate code for an app/component from its blueprint — thin `spl3 run` wrapper around `build_app.spl` (TARGET has `imports:`) or `build_component.spl` (it doesn't). TARGET is a direct `.graph.yaml` path or an app name resolved under `--input-dir` (default `~/graph-code/input`) |
| `grafcode ide [--apps-root ...]` | Launch Graph IDE (`tools/graph-ide`, canonically `src/graph_code/graph-ide`) — starts the `uvicorn` backend (`:8880`) and `npm run dev` frontend (`:8881`); `--api-port`/`--dev-port` to override, `--no-frontend` for API only, `--apps-root` for which `<app>/blueprint/` tree to browse (default `~/graph-code/ide`) |
| `grafcode drift <graph_a> <graph_b> [--dims ...] [--out FILE]` | Compute the 5-component drift vector (+ overall) between two blueprints — `--llm` adds the `intent` component, `--dims` restricts which run |
| `grafcode tools clean-port <port> [port ...]` | Kill whatever process is listening on the given port(s) — SIGTERM then SIGKILL |
| `grafcode tools spl-lint [FILES...] [--fix]` | Find/fix unescaped single quotes inside `.spl` `CREATE FUNCTION` prompt bodies (`AS $$ ... $$`) |
| `grafcode tools suggest-graph-clusters <graph.yaml> [--seed NODE_ID ...] [--format text\|json]` | Prototype extractor-clustering: ancestor-closure split of one graph into sub-graph candidates, seeded by `function.exports[].from` (or explicit `--seed`) — see `graph_lib.py`'s `suggest_clusters()` and `apps/README-new-apps.md`'s "Prototype: grafcode tools suggest-graph-clusters" section |
| `grafcode drift <graph_a.graph.yaml> <graph_b.graph.yaml> [--dims ...]` | Compute the drift report (`docs/DEV/BUILD/blueprint-schema-v2.2.md` §3, 5 components + `overall` aggregate) between two blueprints. `structural`/`interface`/`behavior`/`implementation` are free graph-diffs (`graph_lib.py`'s `*_drift`/`drift_report`); `intent` (`intent_drift`, over `intent_text()` — rationale text + `docs` field) needs `--llm ADAPTER:MODEL` (LLM-as-judge via `spl/compute_intent_drift.spl`, not embeddings) or is absent. `--dims dim1,dim2,...` restricts which components run. Report-only — does not write into either file's `blueprint.drift` block. The 5 components are reported in order `intent, behavior, structural, interface, implementation` — top-down by abstraction level, why (`intent`, the human rationale) → what it should do (`behavior`/verification) → how it's shaped (`structural`, the graph topology) → how it's exposed (`interface`, signatures/contracts) → how it's built (`implementation`, tech-stack primitives); a "concept before mechanism" narrative |

Ported and adapted from `graph-driven-workflow/scripts/` (see that repo's `scripts/README.md` for the originals) — `extract`/`new-app`/`compare` target this repo's actual `apps/<app>/blueprint/` + `blueprint:`-block + `${{ settings.KEY }}` convention, not the old flat `system.yaml`/`components/` layout.

## Architecture

The package lives in `src/graph_code/` and has three files:

- **`exceptions.py`** — `ToolFailed` (raised before any LLM call on hard validation failure) and `ValidationWarning` (non-fatal; has `code`, `message`, `context` fields).
- **`loader.py`** — `GraphDomain` dataclass + `load_domain(yaml_path)`. Accepts two YAML formats and normalizes them into one representation.
- **`graph_lib.py`** — 22 pure functions that operate on a `GraphDomain`. No I/O; no LLM calls. The form-space algorithms (`acyclic`, `reducible`, `productivity_order`, `learning_path`, `gap`, `build_order`) are the sibling **zinet** library's (`zinet.algorithms`), reached through `_zinet_graph()` / `_in_zinet()` (which turn zinet's errors back into `ToolFailed`); `tests/test_zinet_algorithms.py` pins the behaviour that must not change (order of ties, optional edges, two-radical rule). Events, transitions, call contracts, drift and clustering stay here. Includes the drift report: `structural_drift`/`interface_drift`/`behavior_drift`/`implementation_drift` (graph-diff, matched by node id), `intent_text()`/`intent_drift()` (rationale text — `defines`/`comment`/`spec.user_story`/`docs` — scored via an injected `judge` callable, `None` without one), and `drift_report()` combining whichever components `dims` selects into a report plus an `overall` mean — see `docs/DEV/BUILD/blueprint-schema-v2.2.md` §3. Also `suggest_clusters()` — deterministic ancestor-closure clustering (seeded by `function.exports`) that suggests how to split one monolithic graph into modular sub-graphs; a prototype toward eventually teaching `grafcode extract` to auto-split extracted components, exposed as `grafcode tools suggest-graph-clusters`.

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
- `graph-code` is a schema + algorithms library, plus this repo's own forward/reverse `.spl` workflows (`src/graph_code/spl/`, symlinked at repo root as `spl/`) — it has no LLM-calling code of its own, though. The `spl3` runner and LLM adapters themselves live in the sibling `SPL.py` repo (published as `spl-llm`, a real `graph-code` dependency); `grafcode extract --llm`/`build`/`drift --llm` shell out to `spl3 run` against this repo's own `.spl` files.
- All source files use `from __future__ import annotations` for Python 3.9 compatibility with modern type-hint syntax.
