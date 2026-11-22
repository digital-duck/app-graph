# Refactoring graph-code into app-graph, with GraphLang (plan)

Date: 2026-11-22
Status: decisions answered (section 9, 2026-11-22); build started. Per-phase results are recorded under each phase.

Source: `graph-code` at commit `35a5393` (grafcode 0.1.1), which stays untouched. Target: this repo, `app-graph`. Engine: `graflang` (package `graphlang`, 0.2.1, editable at `../graflang`).
Sibling: `work-graph` is being refactored onto GraphLang in parallel (`../work-graph/docs/DEV/graflang-refactor.md`); this plan follows its shape and conventions where they apply, and section 7 lists what the two should share.

What was read: graph-code's `CLAUDE.md`, `README.md`, `pyproject.toml`, `CHANGELOG.md`, the five `.spl` workflows (`build_component`, `build_app` in full; `integrate_system`, `compile_blueprint` headers and control flow), the function lists of `spl/tools.py`, `graph_lib.py`, `cli.py`, `tech_profiles.py`, and one blueprint (`apps/todo/blueprint/backend.graph.yaml`). GraphLang: `CLAUDE.md`, `pyproject.toml`, the changelog head, `docs/DEV/DESIGN/graflang-use-cases.md`, `grafr/expand.py`, `grafr/runtime.py` (constructor, `execute`), `grafr/solver.py` (subprocess contract), `grafr/topology.py` (risky types), `formats.py`, and the recipes `cookbook_v2/code_gen`, `cookbook_v2/code_pipeline` (+ its `build` part), `cookbook_v2/expand_demo`. Not read: `_extract.py`, `graph-ide/` internals, `integrate_system.spl` and `compile_blueprint.spl` bodies in full, graph-code's `docs/DEV/BUILD/*`. **"Verify"** marks a step the plan depends on that nobody has checked yet.

## 1. What graph-code is today

A blueprint format plus tooling: `*.graph.yaml` (Unified Duality Graph Schema v2.1/v2.2) describes an app as a graph of typed nodes (form space: primitives and `composed_of`/`depends_on`; function space: events, calls, transitions), and an LLM pipeline turns a blueprint into tested code. About 7,400 lines of Python in `src/graph_code/` (plus ~650 in `graph-ide/api`) and 1,350 lines of `.spl`, 108 tests, `grafcode` 0.1.1 on PyPI.

| Piece | Lines | What it does | Model? |
|---|---|---|---|
| `loader.py`, `graph_lib.py`, `exceptions.py`, `settings.py` | 1,600 | parse a blueprint into `GraphDomain`; 22 pure functions (validate, build order on zinet, events, transitions, contracts, drift, clustering); `${{ settings.KEY }}` | no |
| `cli.py` (`grafcode`/`gfc`) | 2,126 | validate, order, report, prettify, new-app, extract, build, ide, drift, validate-all, diagram, tools | shells to `spl3` for `build`, `extract --llm`, `drift --llm` |
| `_extract.py`, `scaffolding.py`, `_yaml_style.py` | 1,430 | AST/regex scan of an existing repo into draft blueprints; app scaffolds | no (the `--llm` pass is `compile_blueprint.spl`) |
| `spl/build_component.spl` | 368 | per node in build order: cache check, spec (generated if missing), write, `verify_node` → refine, `verify_edges` → refine, cache, write the file; then a test gate loop (run tests, identify the broken node, repair) and an `ASSERT` | **yes** |
| `spl/build_app.spl` | 101 | per imported component: scaffold, settings, then **spawns `spl3 run build_component.spl` as a subprocess**; halts on the first failure; then spawns `integrate_system.spl` | via children |
| `spl/integrate_system.spl` | 248 | start the backend, wait for HTTP, per `applications:` entry generate and run an HTTP acceptance test, stop the server, write the system README | **yes** |
| `spl/compile_blueprint.spl` | 556 | intent → blueprint, or (`mode=extraction`) analysis → classify shape → 1 or 3 blueprints (+ a tech-profile draft); validate/repair loops | **yes** |
| `spl/compute_intent_drift.spl` | 83 | one LLM-as-judge call for the `intent` drift component | **yes**, one call |
| `spl/tools.py`, `spl/tech_profiles.py` | 2,130 | ~80 `@spl_tool` functions the `.spl` files `CALL` (graph access, file writing, cache, test runs, server control, scaffolds, blueprint validation, logs); tech-profile prompt text, `NODE_FILES`, `VERIFY_CMDS` | no |
| `graph-ide/` | ~650 Py + Vue/vanilla JS | FastAPI + browser viewer/editor of blueprints; its Build and Drift pages call the CLI | no |
| `apps/` | 1.4 GB | ~25 apps; each `apps/<app>/blueprint/` (KBs) plus generated code with `node_modules/` (~93 MB each) | – |

**Baseline (2026-11-22):** `PYTHONPATH=src python -m pytest -p no:cacheprovider` in the `graf` env: **108 passed** (graph-code is not installed there). The tests cover `loader`/`graph_lib` only; `spl/tools.py`, `cli.py`, `_extract.py` and `graph-ide` have **no tests**, so a port of them has no safety net until we write one (Phase 1).

## 2. Where GraphLang fits, and where it does not

GraphLang's own position (`graflang-use-cases.md`): it is for workflows where model steps and deterministic steps alternate and the shape, checks and budget matter; **not** for a script, one model call, or fewer than ~5 steps. A GraphLang port carries text and JSON between steps, not `GraphDomain` objects. So the line falls where it fell in work-graph:

| Area | Verdict | Why |
|---|---|---|
| Blueprint schema, `loader`, `graph_lib`, `settings`, drift (4 free components), clustering | **keep as Python, unchanged** | deterministic, object-heavy; already on zinet (the same algorithms GraphLang uses) |
| The blueprint format itself | **keep it; do not convert blueprints to GraphLang IR** | a blueprint describes *an app* (its parts and contracts); a GraphLang graph describes *a workflow*. They are different things that both happen to be `*.graph.yaml`. GraphLang already recognizes graph-code files and refuses them with a clear message (`graphlang/formats.py`) |
| `build_component.spl` | **GraphLang recipe** (Phase 3) | the core: model and exact steps alternating, two repair loops, a hard gate. Exactly GraphLang's case |
| `build_app.spl` + `integrate_system.spl` | **one recipe with parts** (Phase 4) | replaces "a workflow spawning `spl3` subprocesses" with composition: `build_component` becomes a part used in a loop over components; server start/stop gets a real failure path |
| `compile_blueprint.spl` | **GraphLang recipe** (Phase 5) | classify, branch, generate, validate/repair: a recipe; powers `extract --llm` |
| `compute_intent_drift.spl` | **plain Python, one dd-llm call** | one model call: below GraphLang's threshold. The prompt moves to a file |
| `spl/tools.py` (~80 tools) | **split**: pure logic → library modules (tested); a thin JSON-in/JSON-out entry point the recipes call as `SOLVE backend: subprocess` | the logic is good and battle-tested; only the calling convention (`@spl_tool`, everything a string) is SPL's |
| `tech_profiles.py` | **keep as data**; the prompt text may move to `recipes/*/prompts/` or profile files later | the recipes take the profile text as an input |
| LLM access (`spl3 run --llm claude_cli`) | **dd-llm through GraphLang** | the same adapters work-graph and GraphLang use; `spl-llm` stops being a dependency |
| `_extract.py` AST pass, `scaffolding.py`, `prettify`, `new-app`, `diagram`, `tools *` | **leave as Python** | no model |
| `graph-ide` | **leave**, re-point its Build/Drift calls (Phase 4/6) | blueprint-specific; GraphLang's Streamlit editor edits workflows, not blueprints |
| Recipes as artifacts | **new, cheap:** `graf vis`/`graf describe` on the build recipes, a picture in the docs | one of the payoffs: the build pipeline becomes something you can draw and validate |

## 3. Layout of app-graph

```
app-graph/
  src/appgraph/                 (name: decision 1)
    loader.py graph_lib.py exceptions.py settings.py     copied as they are
    cli.py                      the console script; build/extract/drift call recipes, not spl3
    extract.py scaffolding.py _yaml_style.py
    build/                      what spl/tools.py did, as tested library modules
      blueprint_access.py       node_spec, node_context, order, deps, components, applications ...
      files.py                  write_node_file, fence/chat stripping, NODE_FILES lookup
      verify.py                 verify_node, verify_edges, identify_broken_node, run_component_tests
      cache.py                  cache_get/put (same key and layout as .spl_cache today)
      server.py                 start_backend_server, wait_for_http, stop_process
      blueprint_yaml.py         validate_blueprint_yaml, ensure_component_metadata, write_blueprint_file
      tech_profiles.py
      tool.py                   `python -m appgraph.build.tool <name>`: JSON on stdin -> one function -> JSON on stdout
    recipes/                    package data; GraphLang recipes
      build_component/  build_component.graph.yaml, node/ (part), test_gate/ (part), prompts/, graflang.errors.yaml
      build_app/        build_app.graph.yaml, integrate/ (part), prompts/   (uses build_component as a part)
      compile_blueprint/ ...
    prompts/intent_drift.md
    run.py                      run_recipe(name, inputs, llm=..., limits=...) over graphlang's runtime (section 7)
    graph-ide/                  copied; Build/Drift routers re-pointed
  apps/                         blueprints only (decision 4)
  tests/                        the 108, plus new ones per phase
  docs/DEV/graflang-refactor.md this file
```

The recipes name their tools as `command: ["python3", "-I", "-m", "appgraph.build.tool", "node_context"]`. `-I` ignores `PYTHONPATH`, so **app-graph must be pip-installed (editable) in the env that runs recipes**, including the test env (unlike work-graph, app-graph has no heavy dependencies, so that is cheap).

## 4. Plan, in order

Each phase is one or more commits with the suite green before and after. Stop after any phase and the repo is consistent.

### Phase 0: bootstrap (copy, no behaviour change)

- Copy from graph-code `35a5393`: `src/graph_code/` (without `.spl/`, `logs/`, `__pycache__`, egg-info), `tests/`, `scripts/`, `pyproject.toml`, `CHANGELOG.md`, `CLAUDE.md`, `README.md`, `docs/GUIDE/`, `docs/DEV/` (not `docs/PAPER/`, `docs/chats/`: decision 4), and `apps/*/blueprint/` + `apps/*.md` + `apps/*/README.md` + the per-profile example graphs, **no generated code, no `node_modules`, no databases, no logs**. The commit message names the source commit.
- Suite: the same 108 pass. `graf` env: `pip install -e .`.
- Second commit: the rename (decision 1): package, imports, console script, `pyproject.toml` name, docs. The `grafcode`/`gfc` scripts must **not** be kept: graph-code may be installed in the same env and two packages owning one console script overwrite each other. Search for the old names afterwards (case-insensitive, code, tests, docs, YAML) and read what is left.
- Dependencies: add `graflang>=0.2.1`; keep `networkx`, `pyyaml`, `click`, `ruamel.yaml`, `zinet`; `spl-llm` stays until Phase 5 ends, then goes. **Verify:** graflang 0.2.1 needs `zinet>=0.2.2`, the `graf` env has zinet 0.2.1 metadata (editable; the source may be newer) and graflang's installed metadata says 0.1.1 (stale editable install): reinstall both editables first.

### Phase 1: `spl/tools.py` becomes tested library code

- Move each `@spl_tool` into `appgraph/build/*` (section 3) with real types (an `int` index, a `dict` result) instead of strings; keep the old behaviour exactly, including the hard-won details (absolute test cwd, `sys.executable`, `no_tests` vs failed, ImportError counts as a failure, `npm` without `package.json` is "no tests").
- `appgraph.build.tool`: one entry point, `python -m appgraph.build.tool NAME`, reads the node's inputs as JSON on stdin, writes one JSON line. The GraphLang SOLVE subprocess contract (`grafr/solver.py`).
- **Tests first for what has none:** cache key and hit/miss, `node_context` on the todo backend, `write_node_file` paths from `NODE_FILES`, fence stripping, `identify_broken_node` on recorded pytest output, `get_test_status`, `validate_blueprint_yaml` good/bad, `tool.py` round trip. Fixtures from `apps/todo/blueprint/`.
- The `.spl` files keep working against the moved functions through a shim `spl/tools.py` (imports and re-exports) until their recipe replaces them, so `build` never breaks mid-refactor.

**Result of Phase 0, 0b and 1** (2026-11-22, commits `442c6da`, `c0fb772` and the Phase 1 commit):

- Copied from graph-code `35a5393`: library, CLI, `spl/`, `graph-ide/`, tests, scripts, `docs/GUIDE`, `docs/DEV`, every blueprint (97 files under `apps/`, 1.7 MB). `tests/fixtures/todo_backend/`: the todo backend's `.spl_cache` and generated files (the parity fixture). Renamed to `appgraph` / `app-graph` 0.2.0, commands `appgraph` and `agr`; `docs/DEV/BUILD` keeps its old names (history).
- `appgraph/build/`: `text` (fences, chat artifacts, code shape), `blueprint` (order, specs, context, broken-node, components, applications), `cache`, `files`, `verify`, `server`, `compile`, `tech_profiles` (moved; `spl/tech_profiles.py` re-exports it), `tool` + `steps` (the recipe entry point). The test runner kept is the `.spl` file's inline version (absolute cwd, `sys.executable`, `no_tests`), not the older copy in `tools.py`. One behaviour change: the server is started as `python -m uvicorn` of this interpreter in its own session (was a bare `uvicorn` from PATH).
- **Checked:** the cache key is unchanged (the new code finds graph-code's entries for all 7 todo-backend nodes) and each cached entry, cleaned, equals the file graph-code wrote. `appgraph-verify:py3.12` (`src/appgraph/docker/python.Dockerfile`: the libraries graph-code's generated backends list) runs the fixture's suite in a container with no network and a read-only root, the project passed as JSON on stdin: **22 passed**, as graph-code recorded. 32 new tests; suite 140 passed.
- **Deviation from the plan:** `spl/tools.py` is **not** turned into a shim; it stays as copied (legacy, deleted in Phase 5). Re-wrapping ~80 string-typed functions to be deleted two phases later buys nothing; the library is tested on its own.
- **Found on the way:** the `graf` env has no FastAPI, so the generated backends cannot be tested on the host at all; the container is the only working test path here. GraphLang's own suite writes into tracked files of the graflang repo (mock outputs over `cookbook_pocketflow/*`); I restored them and will not run that suite from here.

### Phase 2: the LLM seam, and intent drift

- `appgraph/run.py`: `run_recipe(name, inputs, *, llm="claude_cli:claude-sonnet-5-5", max_llm_calls, max_steps, checkpoint=None, record=None, replay=None)`: `load_graph(recipe) -> GraphLangRuntime(data, adapter, model, node_output=None, ...).execute(inputs)`, logging through GraphLang's dd-logging setup. `--llm ADAPTER[:MODEL]` keeps today's CLI spelling; graph-code's defaults name `claude-sonnet-4-6`, the new default follows GraphLang's (`claude-sonnet-5-5`).
- **Verify:** that `node_output=None` really writes nothing beside the recipe (the recipe folder is inside an installed package, possibly read-only); that a `FILES` output and `.graf/` are not written; where logs go (`~/.graflang/logs` default; app-graph may want `~/app-graph/logs`).
- `drift --llm`: one `dd_llm` call with `prompts/intent_drift.md` (today's prompt), the same JSON score parse. Test with the stub adapter. `compute_intent_drift.spl` is deleted.

**Result of Phase 2** (2026-11-22):

- `appgraph/run.py`: `run_recipe(name|path, inputs, llm=ADAPTER[:MODEL] or an object with generate(), max_llm_calls, max_steps, workers, checkpoint, resume, record, replay, log_dir)` -> `RecipeRun(outputs, summary, log_path)`; a stop (call cap, step cap, failed node, refused graph) raises `RecipeError` with the summary. It mirrors `graf run`'s assembly (`parse_llm_spec`, `make_llm`, `MeteredLLM`, cassettes, `capability_errors`, dd-logging), which lives in GraphLang's CLI function, not in a library call: the case for section 7's proposal.
- **Checked:** with `node_output=None` nothing is written beside the recipe (no `.graf/`; asserted). A SOLVE step runs **in the recipe's own folder** (`resolver.base_dir`), so every path a recipe hands its tools must be absolute; `run_recipe` callers resolve them.
- `drift --mode semantic` is one dd-llm call per dimension (`appgraph/judge.py`, prompt `prompts/intent_drift.md`, unchanged text); `compute_intent_drift.spl` is deleted. `--llm` default is now `claude_cli:claude-sonnet-5-5` (was `...-4-6`); `--llm-timeout` and `--llm-max-output-tokens` go to the dd-llm adapter. Tests: a stub adapter end to end through the CLI. Suite: 149 passed.

### Phase 3: `build_component` as a recipe

The shape (long form decided by `graf compact`/`expand` as usual):

```
inputs: component_graph, tech_profile, output_dir, use_cache, max_test_attempts
prepare   SOLVE  setup_graph + contract_warnings + profile text + build order (JSON list)
nodes     LOOP over the order, one round per blueprint node            (decision 3: LOOP or expand:)
  context   SOLVE  spec, context of already-written deps, cache lookup
  cached?   EVALUATE hit -> write ; miss -> spec?
  spec      GENERATE write_node_spec   (only when the blueprint has no spec), save_spec
  write     GENERATE write_node
  check     SOLVE verify_node  -> EVALUATE fail -> GENERATE refine_node
  edges     SOLVE verify_edges -> EVALUATE fail -> GENERATE refine_node
  store     SOLVE cache_put + write_node_file           (risky: writes outside the recipe folder; decision 5)
test_gate LOOP up to max_test_attempts
  run       SOLVE run_component_tests                    (risky: runs generated code)
  status    EVALUATE passed / no_tests / failed
  repair    SOLVE identify_broken_node + context -> GENERATE repair_node -> SOLVE write_node_file
gate      ASSERT all passed      error exits: `no_tests`, `tests_failed` (codes in graflang.errors.yaml)
outputs:  manifest, test_summary
```

- The four prompts (`write_node_spec`, `write_node`, `refine_node`, `repair_node`) move verbatim to `prompts/*.md` (GraphLang placeholders `{{in_x}}`); the tech-profile text is an input. Do not improve prompts in this phase: parity first.
- `cli build` for a component graph calls `run_recipe("build_component", ...)` with a call cap derived from the node count (`graf validate` prints the graph's own count).
- **Must handle (verify each):**
  - `DEFAULT_MAX_STEPS = 1000` node firings: a 15-node blueprint at ~10 firings per node plus the gate is near it; pass `max_steps` from the node count.
  - SOLVE subprocesses get an environment of `PATH` and `PYTHONUTF8` only: `npm` wants `HOME` (cache), pytest may want more. Use `env_passthrough` (it is a code key, so a MUTATE cannot add it, which is fine).
  - SOLVE's default memory limit is 2048 MB and a 60 s timeout: Node/Vite reserve far more virtual memory than they use, so a frontend `npm test` may die under an address-space limit. Measure; raise `memory_mb`/`timeout` on the test node.
  - The old run-log markdown (`make_log_path`, `write_file`) is replaced by GraphLang's JSONL log and `graf trace`; the manifest stays an output. Say so in the CHANGELOG.
- **Acceptance (offline, the parity guard):** a stub model that answers each `write_node` prompt with the code in graph-code's `apps/todo/backend/.spl_cache/` for that node (verified code from a real run), and a scripted reply for refine/repair. Build `apps/todo/blueprint/backend.graph.yaml` into a temp folder: the same files as graph-code's generated backend, and its tests pass. Plus: a failing-test case reaching `repair_node` and then `tests_failed`; a cache-hit run with **zero** model calls; a missing-tests case ending in `no_tests`. GraphLang's `--record`/`--replay` cassettes are the other way to pin this. Then **one real capped run** on a small component (`apps/jwt_provider` or `apps/build/counter`).

**Result of Phase 3** (2026-11-22):

- `src/appgraph/recipes/build_component/`: `build_component.graph.yaml` (validates; the risky steps, `store`, `run`, `write_fix`, `summary`, are all behind the `allowed` GUARD, which `graf validate` checks), the four prompts (text unchanged; placeholders renamed, `{{in_guide}}` for the profile's style guide), `policies/build.cedar`, `graflang.errors.yaml` (`E_TESTS_FAILED`, `E_NO_TESTS`, `E_BUILD_REFUSED`), `tools/run_tests.py` (in the container). Steps in `appgraph/build/steps.py`. `appgraph/builder.py`: `build_component(...) -> BuildResult(status, tests, manifest, summary_path, llm_calls)`; `appgraph build` uses it for a component target (a system target still goes through spl3 until Phase 4). New options: `--max-llm-calls` (default 4 per node + one per test attempt + 2), `--max-test-attempts`, `--no-cache`.
- **Behaviour changes:** (1) tests run in the `appgraph-verify:py3.12` container (decision 5), not on the host; (2) a node whose spec had to be generated is cached under its lookup key (graph-code cached it under the generated text, so it never hit); (3) the markdown run log becomes a short summary in `~/app-graph/logs/build_component-<name>-<time>.md` plus GraphLang's JSONL/text log (decision 7); (4) the outcome is a status (`passed`, `no_tests`, `failed`, `refused`) instead of a string the caller searched for "FAILED"; (5) a refused output folder (not under home or the temp folder) stops before any model call.
- **Checked** (`tests/test_build_component.py`, 6 tests, Docker): with a scripted model answering graph-code's verified code, the todo backend is built with **byte-identical files** and **22 tests pass**, with exactly 7 model calls; a second run is served from the cache with **0 calls**; a broken `crud_operations` is found by the failing tests and repaired; a repair that changes nothing ends in `failed` after `max_test_attempts` repairs with the test output in the summary; a node that does not compile is refined once; no `tests/` ends in `no_tests`; `/etc/...` is refused. `appgraph build` on a cached copy: 0 calls, 22 passed. **One real run** (`claude_cli`, claude-sonnet-5-5, cap 12) of `jwt_provider` into a fresh folder with graph-code's tests: 4 model calls, **10 passed**, 21 s. Suite: 155 passed.
- **Found:** `on: [a, b]` fires once per arriving token, so it is right only where a and b are exclusive branches; a guard on two steps that both run fired twice and ran the whole node loop twice (caught by the parity test's call count). A top-level run reports no exit name, only the outputs, so `tests` carries the status. ~123 node firings for 7 blueprint nodes; `max_steps` is set to 300 + 30 per node. `--llm-timeout` needed a reach into GraphLang's `DDLLM._adapters` (no public option): an upstream item.

### Phase 4: `build_app` + `integrate_system` as one recipe

- Top graph: `components` SOLVE (imports in authored order, port consistency) → LOOP over components using **`build_component` as a part** (no more `spl3` subprocesses, one call budget for the whole app) → on a failed component, error exit `component_failed` naming it (today: `RETURN "BUILD HALTED ..."`, a string) → `integrate` part.
- `integrate` part: `start_backend_server` (risky) → `wait_for_http` → LOOP over `applications:` (GENERATE the acceptance test, write it, run it) → **`stop_process` on every path**, including a failure in the loop (a `RECOVER` route that stops the server before halting; today a crash between start and stop leaks the server) → GENERATE the system README from the real results.
- `cli build` with an `imports:` graph calls `run_recipe("build_app", ...)`; `graph-ide`'s Build router calls the same function instead of the CLI.
- Acceptance: the todo app (backend + frontend + integrate) built offline with the stub model from cached code; the acceptance-test step with scripted test code against the real generated backend; a forced component failure halts before integration with the component named.

**Result of Phase 4** (2026-11-22):

- `src/appgraph/recipes/build_app/`: `build_app.graph.yaml` (validates; uses `build_component` as a part inside the component LOOP), prompts `write_acceptance_test.md`, `write_system_readme.md` (text unchanged), `policies/build_app.cedar`, `graflang.errors.yaml` (`E_COMPONENT_FAILED`, `E_INTEGRATION_FAILED` and build_component's codes, which GraphLang reads only beside the top graph; a test keeps the two files equal). `appgraph.builder.build_app(...) -> AppBuildResult(status: passed | component_failed | integration_failed | refused)`; `appgraph build main.graph.yaml` uses it; **`build` no longer calls spl3 at all**. The IDE's Build page runs `appgraph build`, so it is on the recipes already (its router is unchanged).
- **Integration in a container, not on the host:** `appgraph-integrate` (`src/appgraph/docker/integrate.py`, baked into `appgraph-verify:py3.12`) writes the backend to `/tmp`, starts uvicorn on the container's loopback (no network otherwise), runs every acceptance script against it with a time limit and reports per application. The server dies with the container, so the leak the plan worried about (a crash between start and stop) cannot happen; there is no host server and no PID. The acceptance scripts are generated first (a LOOP, one call per application) and kept under `log_dir/acceptance-<time>/`.
- **Vue tests in Docker** (decision 5): `appgraph/build/node_image.py` builds `appgraph-verify-node:<lockfile hash>` once per lockfile (`node:22`, `npm ci` from the scaffold's package files only, the only step with a network) and runs `npm test` in it with GraphLang's isolation flags, the project on stdin, `node_modules` a writable folder of links (Vitest writes its cache there). GraphLang's `container:` takes a fixed image, so this step calls docker itself (an upstream wish: an image chosen at run time). The Python runner moved into the image too (`/usr/local/bin/appgraph-run-tests`, `mount: none`): a part's subprocess command is read relative to the *using* graph, so a mounted `tools/run_tests.py` was not found when build_component ran inside build_app.
- **Checked** (`tests/test_build_app.py`, `test_build_component.py`, Docker): the todo frontend rebuilt byte for byte, **14 tests pass**; the whole todo app offline (backend 22 + frontend 14, the settings config modules, the acceptance scripts against the live backend, README, summary) **passes** in about 25 s; a backend whose repair changes nothing halts the app with `component_failed: backend` and the frontend and acceptance prompts are never sent; a failing acceptance script ends in `integration_failed` with the assertion in the report, and the README is still written. Suite: 160 passed.
- **Found:** a part's inputs cannot be fed from `$loop.x` directly (validate: "input not bound"); an ordinary step in between does it. `'\n'` inside a double-quoted YAML expression is a real line break and the expression parser refuses it: text with line breaks is built by a tool step. Under Docker Desktop a bind mount from outside the home folder hangs `docker run` (GraphLang warns about it); the test steps mount nothing. Graph-code's DEP_SYMBOLS knows `TodoItem` only under the id `todo_item_component`, so the todo frontend's `list_component` always gets one no-op refine (as in graph-code); left as is.

### Phase 5: `compile_blueprint` as a recipe; `extract --llm` on it

- Modes `intent` and `extraction` as one recipe with a branch on `mode`; `extraction` classifies the shape (`INTEGRATED` → three generate/validate/repair passes as one part used three times; `SINGLE`; `NO_FIT` → tech-profile draft, then `SINGLE`). `validate_blueprint_yaml` is a SOLVE; `max_repair_attempts` stays 0 by default (fail-fast, as decided in graph-code).
- `extract`'s resumability: today the `--llm` pass is a durable spl3 workflow (`--persistence sqlite`, `--workflow-id` from the inputs, resumes mid-repair). GraphLang has `--checkpoint`/`--resume` on the runtime (`runtime.checkpoint_path`). **Verify** it resumes after the last finished node the way spl3 did; keep `--skip-cache` semantics (fresh run, still writes the checkpoint). The `.grafcode_cache/` AST cache is Python and stays (renamed with the package).
- Acceptance: extraction of `apps/fief`'s recorded `analysis.json` + `source_context.txt` with a stub model returning fief's current blueprints: same files written; an invalid reply ends in `FAILED` with the validation message.
- Then remove `spl/`, `_spl3_bin`, `_run_spl_subprocess`, `spl-lint`, and the `spl-llm` dependency.

**Result of Phase 5** (2026-11-22):

- `src/appgraph/recipes/compile_blueprint/`: `compile_blueprint.graph.yaml` (modes `intent` and `extraction`; classify, a tech-profile draft when no profile fits, then one or three blueprints), the part `validate_repair/` (validate, repair while invalid up to `max_repair_attempts`, write; error exit `invalid`, `E_BLUEPRINT_INVALID`), the five prompts, `policies/compile.cedar`. `max_repair_attempts` default stays **2** (the `.spl` file's value; graph-code's CLAUDE.md said 0, the code said 2). `run_recipe(max_tokens=16000)` restores spl3's `WITH OUTPUT BUDGET 16000 TOKENS` (GraphLang's GENERATE has no such setting: an upstream item).
- `extract --llm` runs the recipe. `--persistence checkpoint` (default; `sqlite` accepted as the old name; `postgres`/`dbos` dropped) keeps a GraphLang checkpoint in `.appgraph_cache/llm-<key>.checkpoint.json`, resumed on the next run unless `--skip-cache`, removed when the pass finishes. New `--max-llm-calls` (default 20). **Coarser than spl3:** GraphLang checkpoints after top-level steps only, so a run that dies inside a repair loop restarts that loop (the drafts, the expensive calls, are top-level and are not paid for twice).
- **Removed:** `src/appgraph/spl/` (the five `.spl` files, `tools.py`, the `tech_profiles.py` re-export), `appgraph tools spl-lint`, `scripts/spl_lint.py`, the `spl-llm` dependency (decision 6). Nothing in the code calls `spl3` any more.
- **Prompts:** spl3 fills `{param}` by plain replacement with no brace escape, so the prompt files are the `.spl` bodies with only each function's own parameters renamed (`scripts/spl_prompts.py`). The first conversion of Phase 4 had turned `{{` into `{` in `write_acceptance_test`, changing its text; fixed (`a7a7066`). The prompts still name `build_component.spl`, `spl/tech_profiles.py`, `integrate_system.spl`: kept verbatim for parity, a Phase 6 prompt edit.
- **Checked** (`tests/test_compile_blueprint.py`, 10 tests, no Docker): intent mode valid at once (one call, the 16000 budget passed), repaired once, still invalid after 2 repairs (error exit, nothing written), 0 repairs fails fast, a refused folder makes no call; extraction on fief's real `analysis.json`: INTEGRATED writes three valid blueprints, SINGLE with an unknown profile writes `TECH_PROFILE_DRAFT.md` and decomposes against it, NO_FIT falls back to one; `appgraph extract --llm` through the CLI, a run that dies at the decompose call is resumed from its checkpoint without classifying again. Suite: 170 passed.

### Phase 6: what the graph form buys (optional, after parity)

- `expand:` form of `build_component` (decision 3): the app's blueprint graph *is* the build workflow's graph; independent nodes build side by side with `--workers`; `graf vis` of a build shows the app.
- Docs: a picture of each recipe (`graf vis`), `graf describe` output in `docs/`.
- `graph-ide`: a "recipe" view (link to `graf vis --edit` on the build recipe), and run progress through the runtime's `on_node` callback instead of tailing a subprocess.
- Prompt work (now measurable, since each prompt is a file and each run is logged).

### Phase 7: release

- Version: app-graph starts at **0.2.0** (continuing grafcode's line) or **0.1.0** as a new project (decision 1). CHANGELOG: new name, GraphLang/dd-llm instead of spl-llm, `--llm` unchanged, logs moved, what `build` now reports.
- README and `CLAUDE.md` rewritten for the new layout; `docs/GUIDE/User-Guide.md` updated per command.

**Result of Phase 7** (2026-11-22, docs; version stays 0.2.0, unreleased):

- `README.md`, `CLAUDE.md` and `docs/GUIDE/User-Guide.md` are rewritten for the recipes. They cover install with Docker, what each recipe does, `build`'s outcomes and options, `extract --llm`'s checkpoint, and the GraphLang rules that bit during the port (in CLAUDE.md). `spl-lint`, `compare` and the `tools/`/`spl` symlinks are gone from the docs.
- `apps/README.md` and `apps/README-new-apps.md` are history of graph-code runs. Each now starts with a note, and their spl3 commands are kept as they were run. The one how-to block now says `appgraph build`.
- Correction found while documenting: graph-code's docs said `extract --llm` was fail-fast with `max_repair_attempts: 0`, but its `.spl` default was 2 and the CLI never overrode it. app-graph keeps 2 and the docs now say so.
- Removed `APPGRAPH_WRITE_ROOTS`: the error catalogues suggested it, but a recipe's SOLVE step never receives that variable, so it could not work.
- **Phase 6 is not done.** It covers the `expand:` form, `graf vis` pictures, IDE progress and prompt work. All of it is optional and left for a decision.

## 5. What does not change

The blueprint schema (v2.1/v2.2) and every blueprint file; `validate`, `order`, `report`, `prettify`, `new-app`, `validate-all`, `diagram`, `drift` (without `--llm`), `ide`, `tools clean-port`/`scaffold-*`/`suggest-graph-clusters` behave as today under the new command name; the generated code layout (`NODE_FILES`, `{output_dir}/{component}`); the `.spl_cache` key (so a cache from graph-code can be reused: verify); the default work folders (`~/graph-code/{input,output,report,ide}` → renamed with the package, decision 1).

## 6. Risks and what is not known

- **Untested surface.** ~5,000 lines (`tools.py`, `cli.py`, `_extract.py`) have no tests; Phase 1 writes them before anything moves. This is the biggest risk, larger than GraphLang.
- **Parity of a long LLM pipeline.** Moving prompts into files and loops into a graph must not change what a build produces. The cached-code stub model (Phase 3) is the guard; prompt changes are out of scope until Phase 6.
- **Runtime limits** sized for small recipes: step cap, SOLVE environment, memory limit, timeouts (Phase 3 "must handle").
- **Running generated code** (tests, a live server) is what GraphLang marks risky. Decision 5.
- **Resume semantics** of `extract --llm` (Phase 5).
- **Cost.** Every real run gets `max_llm_calls`; defaults in the CLI derived from the blueprint's node count.
- **Coupling to an evolving GraphLang.** Pin `graflang>=0.2.1,<0.3`; anything app-graph needs from the runtime goes into GraphLang (with a test there), not into a local patch.

## 7. Shared with work-graph (keep the two refactors aligned)

- Both need "run a shipped recipe from library code, nothing written beside it, logs routed by the caller, a call cap". **Proposal:** put that helper in GraphLang once (`graphlang.run_recipe` or similar) instead of `appgraph/run.py` and `workgraph/...` each writing one. Until it exists, app-graph's `run.py` mirrors whatever work-graph's Phase 2 settles on.
- Same conventions: recipes under `src/<pkg>/recipes/<name>/` as package data; `--llm ADAPTER:MODEL`; dd-llm adapter names (`claude_cli` subscription-safe); scripted-model tests in GraphLang's style; error exits with codes in `graflang.errors.yaml`; "a GraphLang *layer* is a level of composites" (do not use the word for anything else).
- work-graph's Phase 4 (GraphLang files as knowledge-graph artifacts) would index app-graph's recipes too.

## 8. Words

| Word | Means here |
|---|---|
| **blueprint** | an app's `*.graph.yaml` (graph-code schema): what to build |
| **recipe** | a GraphLang workflow (`*.graph.yaml` with `workflow:`): how to build it |
| **part** | a GraphLang sub-workflow used inside a recipe (`build_component` inside `build_app`) |
| **node** | ambiguous: a blueprint node (a module to generate) or a recipe node (a step). Code and docs say *blueprint node* / *step* where both are near |

Both file kinds end in `.graph.yaml` (GraphLang's naming rule: semantic infix + format extension). They live in different folders (`apps/*/blueprint/` vs `src/appgraph/recipes/`) and the loaders already tell them apart by their keys; no rename proposed.

## 9. Decisions (please answer inline, `[WEN] ...`)

1. **Name.** Package `appgraph`, console script `appgraph` (short alias?), PyPI `app-graph` (**verify** it is free), work folders `~/app-graph/...`. Version 0.1.0 as a new project, or 0.2.0 continuing grafcode? Recommended: `appgraph` / `app-graph`, alias `agr`, **0.2.0**, and a note in grafcode's README pointing here once released.

[WEN] OK

**Recorded:** package `appgraph`, scripts `appgraph` and `agr`, PyPI `app-graph` (checked: no such distribution on PyPI, 2026-11-22), version 0.2.0, work folders `~/app-graph/`.

2. **Scope of "use GraphLang".** Recommended (section 2): the four LLM workflows become GraphLang recipes, intent drift a plain dd-llm call, the blueprint schema and the deterministic library stay. The alternative, also turning blueprints into GraphLang IR, mixes "what the app is" with "how to build it" and I do not recommend it. Confirm.

[WEN] YES

**Recorded:** blueprints stay graph-code's schema; the LLM workflows become recipes.

3. **Per-node loop: `LOOP` (Phase 3) or `expand:` (Phase 6)?** `LOOP` over the build order is a faithful port of today's sequential loop and easy to compare. `expand:` makes one part use per blueprint node, wired by the blueprint's own edges (parallel where independent; the run's graph is the app's graph) but needs the blueprint turned into a things file before load, and is a bigger behaviour change. Recommended: `LOOP` first for parity, `expand:` as Phase 6.

[WEN] go with your recommend

**Recorded:** `LOOP` in Phase 3, `expand:` in Phase 6.

4. **What to copy from graph-code.** Recommended: blueprints, READMEs, the per-profile example graphs, `docs/GUIDE`, `docs/DEV`; **not** the generated code (1.4 GB, mostly `node_modules`), logs, databases, `docs/PAPER`, `docs/chats`. Generated code is rebuilt by `appgraph build` when needed; the parity tests read graph-code's `.spl_cache` from a fixture copied for the purpose (a few files).

[WEN] YES

**Recorded.**

5. **Guards on risky steps.** Writing generated files outside the recipe folder, running generated tests, and starting a server are what GraphLang treats as risky. Options: (a) mark them `risky: true` behind a Cedar `GUARD` (a policy allowing writes only under `output_dir` and only the profile's test command), which `graf validate` then enforces; (b) leave them unguarded, as graph-code does today. Recommended: (a), with the policy shipped in the recipe; it costs one node per recipe and documents the trust boundary. Optional on top: run tests in GraphLang's container (`container:` on the SOLVE), off by default because it needs Docker.

[WEN] go with your recommend, use docker to test

**Recorded:** risky steps behind a Cedar `GUARD`; the component test run is a containerized SOLVE (Docker; Docker Desktop 24.0.7 is on this machine), not a host subprocess. The image per profile is a build input (python: a `python:3.12` image with the profile's test deps; vue: a Node image).

6. **spl-llm.** Dropped entirely at the end of Phase 5 (recommended), or kept as an extra so someone can still run the old `.spl` workflows from app-graph? graph-code itself keeps them either way.

[WEN] drop spl-llm

**Recorded:** removed at the end of Phase 5.

7. **Logs.** The hand-written markdown build log goes; GraphLang's JSONL run log and `graf trace` replace it. Do you want a markdown summary kept (written by a last step from the run summary)? Recommended: yes, a short one, since the build log is what people read after a long build.

[WEN] Yes

**Recorded:** a short markdown summary written by the last step.