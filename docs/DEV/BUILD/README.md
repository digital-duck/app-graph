# Build Plan: First Round-Trip Prototype (todo app)

**Status**: Steps 1–4 done, `examples/` renamed to `apps/`, spl123 test environment documented and verified end-to-end for both backend and frontend (2026-08-11). **First real results**: `spl3 run` generated the todo backend (22/22 reference tests pass, first try, no repair) and frontend (14/14 pass) from their blueprints via `claude_cli`. Frontend run also surfaced a real gap in `build_component.spl`'s test-gate logic, since fixed (§9). Both blueprints now also generate a `README.md` per component (§8) — required extending `write_node_file`/`verify_node`/`verify_edges` to handle non-code `kind: doc` nodes. The generation cache is now disk-backed and spec-sensitive, with a per-node `use_cache: false` override for fine-grained control (§10) — the old cache was in-memory-only and never actually skipped anything across separate `spl3 run` invocations. **Confirmed via a real re-run (§10.4)**: 2nd run against the same output dir, unchanged graph → 6/6 cache hits, 0 LLM calls, 33.6s → 1.1s. **A real defect was also found and mitigated** (§8.2): a generated frontend README contained a leaked chat-turn artifact (`Human: continue to generate: ...`) straight from the raw `GENERATE` output — doc nodes have no shape check to catch this, unlike code nodes; defensive stripping added. **Both generated components confirmed running together as a real system** (§7.4): found and fixed two integration bugs neither component's own test gate could catch — a missing `VITE_API_BASE_URL` (frontend was silently fetching `undefined/todos`) and a genuine interface-contract violation (`toggleTodo` generated as `PATCH`, backend and the frontend's own declared contract both say `PUT`) — a live example of exactly the cross-component drift the blueprint/drift vision exists to catch. See §6/§6.1/§6.2 for what's verified, §7 for how to run it, §11 for what's still deferred.
**Goal**: Get a real forward → reverse → drift round-trip running on the `apps/todo` blueprint, as the first concrete evidence point for the [blueprint/drift vision](../../../../zinets/docs/publication/TMLR/Graph-Code/README.md).
**This is step 1 of that vision's evidence bar**: no paper section gets written until this pipeline produces real numbers on at least one domain, with a baseline comparison.

---

## 1. What exists already (verified by reading the code, 2026-08-11)

| Piece | Location | State |
|---|---|---|
| Todo blueprints (backend/frontend/integrated) | `apps/todo/*.graph.yaml` | Well-formed v2.1, ready to extend |
| Graph library (`GraphDomain`, `load_domain`, `build_order`, `validate_full`) | `src/graph_code/{loader,graph_lib}.py` | Solid, v2.1-only, no blueprint/lineage/drift fields yet |
| Forward-build SPL workflow (`build_component.spl`, `build_app.spl`, `integrate_system.spl`) | `/home/gongai/projects/digital-duck/graph-driven-workflow/spl/` | Working, but built against an **old, incompatible** graph API |
| Old graph API (`load_graph`, `validate`, `build_order(data)`, dict-based) | `graph-driven-workflow/spl/graph_lib.py` (119 lines) | Superseded by `graph_code`'s `GraphDomain`-based API (517 lines) — **zero shared function signatures** |
| Reverse miner (artifact → blueprint extraction) | — | **Does not exist.** Net-new code. |
| Drift comparator (`drift_profile(b1, b2)`) | — | **Does not exist.** Net-new code. |

**Key finding**: `graph-driven-workflow/spl/tools.py` calls the old dict-based API throughout (`graph_lib.load_graph`, `graph_lib._all_nodes`, `graph_lib.node_spec`, `graph_lib.node_deps`, `graph_lib.build_order(data)`). None of these signatures exist in `graph_code`'s new library. **Copying the `.spl`/`tools.py` files verbatim will break immediately** — this is a rewrite of `tools.py`'s graph-facing calls, not a file migration. The `.spl` workflow files themselves (`build_component.spl` etc.) call `tools.py` functions by name, not the graph library directly, so they likely need few or no changes once `tools.py` is fixed underneath them.

## 2. What a real round-trip needs — three pieces, only one is a migration

1. **Forward pass** — build the todo app from the blueprint. Exists today in `graph-driven-workflow/spl/`, but wired to the old graph API. Fixing this is steps 3–4 below.
2. **Reverse pass** — extract a blueprint from the generated codebase (AST → DAG, port extraction, dependency inference). **Net-new**, not covered by this plan — a separate follow-on step once forward is working.
3. **Drift comparison** — compare as-designed vs. as-built blueprints and compute the drift vector. **Net-new**, same caveat.

This document's four steps get the **forward pass working on the new v2.1 schema plus blueprint/lineage metadata**. That is a necessary and useful milestone by itself (it's also what the SPL-for-Education / TMLR resubmission work already leans on), but it is half the round-trip, not the whole prototype. The miner and comparator are separate, later work.

## 3. The four steps

### Step 1 — Extract the blueprint schema
Source: `docs/chats/qwen-2026-08-11.md` (§6.1 of the drafted paper section). Produce a schema reference doc defining:
- `blueprint:` top-level block — `id`, `schema_version`, `domain_type`, `provenance` (`authored | build | reverse | roundtrip`), `parent_blueprint`
- `lineage:` — append-only list, one entry per pass (`pass: forward|reverse`, `model`, `adapter`, `temperature`, `prompt_hash`, `engine`, `timestamp`)
- `drift:` — populated after a round-trip comparison (`reference_blueprint`, `vector: {structural, interface, intent, behavior, implementation}`)

Low-risk, foundational — unblocks steps 2–3. **Do this first.**

### Step 2 — Revise `apps/todo/*.graph.yaml`
Add the `blueprint:`/`lineage:` metadata block to each of the three todo yamls. Metadata-only addition; doesn't require the miner or comparator to exist yet. Scaffolding for steps 3+.

### Step 3 — Extend `src/graph_code/{loader,graph_lib}.py`
Parse the new `blueprint:`/`lineage:`/`drift:` fields into `GraphDomain` (new fields, not a schema rewrite — additive, following the same pattern as `domain_type`/`target_languages`). No behavior change to existing v1.0/v2.1 parsing.

### Step 4 — Rewrite (not copy) `graph-driven-workflow/spl/tools.py` against the new API
Port every `graph_lib.*` call in `tools.py` from the old dict-based signatures to `graph_code`'s `GraphDomain`-based ones:

| Old call (dict-based) | New equivalent (GraphDomain-based) |
|---|---|
| `graph_lib.load_graph(yaml_path)` | `graph_code.load_domain(yaml_path)` |
| `graph_lib.validate(data)` | `graph_code.validate_full(graph)` |
| `graph_lib.build_order(data)` | `graph_code.build_order(graph)` |
| `graph_lib.node_spec(data, node_id)` | `graph.nodes[node_id].get("spec")` |
| `graph_lib.node_deps(data, node_id)` | walk `graph.form_graph` predecessors, or a small new helper |
| `graph_lib._all_nodes(data)` | `graph.nodes` (+ `graph.primitives` if primitives needed) |

Keep the `.spl` workflow files (`build_component.spl`, `build_app.spl`, `integrate_system.spl`) as-is initially — they call `tools.py` functions by name, so they shouldn't need edits unless a `tools.py` function's *return shape* changes. Copy/adapt the sibling files (`tech_profiles.py` unaffected, needs no changes) into `spl/` alongside the rewritten `tools.py`.

## 4. Evidence checkpoint

Once steps 1–4 land, the todo app should build end-to-end through the new `graph_code` library with blueprint/lineage metadata recorded per pass. That's the point to stop and confirm before starting the reverse miner: does the forward pipeline actually run clean on `apps/todo`, and does the recorded `lineage` look right, before investing in the harder net-new pieces (§2, items 2–3)?

## 5. References

- Vision doc: `../../../../zinets/docs/publication/TMLR/Graph-Code/README.md`
- Schema/theory source: `../../chats/qwen-2026-08-11.md`
- Existing forward-build workflow (pre-migration): `/home/gongai/projects/digital-duck/graph-driven-workflow/spl/`

## 6. What was actually done (2026-08-11)

- **Step 1**: `blueprint-schema-v2.2.md` in this directory — `blueprint:`/`lineage:`/`drift:` fields, formalized against the real v2.1 parser.
- **Step 2**: `apps/todo/{graph,backend.graph,frontend.graph}.yaml` each carry a `blueprint:` block (`provenance: authored`, empty `lineage`).
- **Step 3**: `src/graph_code/loader.py` gained a `Blueprint` dataclass and `GraphDomain.blueprint` (parses the new block; `None` when absent — verified against all pre-existing example files, no regressions). Also added `GraphDomain.capstone`, which the loader had silently dropped despite every example yaml declaring one — needed for `get_capstone`/`identify_broken_node` in step 4, not scope creep. 78/78 tests pass (72 original + 6 new, in `TestBlueprint`).
- **Step 4**: `spl/tools.py` rewritten (not copied) against `graph_code`'s `GraphDomain` API — old dict-based calls (`graph_lib.load_graph`, `_all_nodes`, `node_spec(data, id)`, `build_order(data)`) replaced with `graph_code.load_domain`/`build_order(graph)`/`graph.nodes[...]`/a new `_node_deps()` helper. `tech_profiles.py` and `build_component.spl` copied unchanged (no graph-API coupling). **Verified by smoke-testing the actual functions against `apps/todo/blueprint/backend.graph.yaml`** (stubbing only the `spl.tools` runtime import, which isn't installed in this environment): `setup_graph`, `order_bullets`, `get_capstone`, `node_spec`, `node_composed_of`, `identify_broken_node`, `verify_edges`, and `write_node_file` all produced correct output (5-node build order, correct capstone `api_routes`, correct dependency resolution, correct output path `app/main.py` from `graph.domain`).
- **Correction made mid-implementation (partial fix, later found insufficient — see §6.1)**: `spl/` was briefly given an `__init__.py` to make it a proper installed package, then reverted — `tools.py`'s own `from spl.tools import spl_tool` line imports the *external* spl3 runtime's `spl` package, so making our own directory an installable `spl` package would collide with that name.
- **`examples/` renamed to `apps/`** — matches the naming convention in `graph-driven-workflow/apps/SPL/`, which holds several reverse-mined reference apps (todo, expense, kanban, mealie, fullstack, dispatch, conduit) that still need testing (see §8). All internal references updated: `tests/conftest.py`'s `apps_dir` fixture (renamed from `examples_dir`), `CLAUDE.md`, `README-claude.md`, `blueprint-schema-v2.2.md`, and the PAPER doc. `git mv` used to preserve history. 78/78 tests still pass after the rename.

**Deliberately deferred, not done**: `build_app.spl` and `integrate_system.spl` were **not** migrated. Both call tool functions (`setup_system`, `component_order`, `system_components`, `component_dependencies`, `system_applications`, etc.) that were never implemented anywhere in `graph-driven-workflow` either — they're aspirational system-level orchestration, not working code today. Migrating them now would be porting non-functional code. `build_component.spl` (the workflow that actually generates one component — backend or frontend — from a blueprint) is fully functional against the new API and is what's needed to run the todo app's forward pass.

**Not yet run** (at the time §6 items above were written): the actual `spl3 run build_component.spl` end-to-end. Verification in step 4 was at the Python-function level (calling `tools.py`'s functions directly against the real blueprint, stubbing only the `spl.tools` import) because `spl3`/`graph_code` weren't confirmed available in the shell used for that work. See §6.1 — Wen ran it for real in `spl123` and hit a second, more fundamental packaging bug that the Python-level smoke test could not have caught.

### 6.1 Real-run bug (2026-08-11): `spl/` under `src/` collides with the real `spl` package

Running the exact command from §7.3 produced:

```
File ".../SPL.py/spl/executor.py", line 267, in __init__
    from spl.tools import get_global_tools
  File "/home/gongai/projects/digital-duck/graph-code/src/spl/tools.py", line 20, in <module>
    from spl.tools import spl_tool
ImportError: cannot import name 'spl_tool' from partially initialized module 'spl.tools'
  (most likely due to a circular import) (/home/gongai/projects/digital-duck/graph-code/src/spl/tools.py)
```

**Root cause**: `pip install -e ".[dev]"` (§7.1) adds `graph-code/src` to `sys.path` (confirmed via `__editable__.graph_code-0.1.0.pth`). `src/spl/` had no `__init__.py` (the §6 "correction" above), so Python's PEP 420 implicit-namespace-package mechanism let it merge with — and in this `sys.path` ordering, shadow — the *real* `spl` package from `SPL.py`. `spl3`'s own internal `from spl.tools import get_global_tools` (in `SPL.py/spl/executor.py`) resolved to **our** `graph-code/src/spl/tools.py` instead of the real one, which then tried to import `spl_tool` from itself — the circular import above.

The earlier "correction" (removing `__init__.py`, logged in §6) was necessary but not sufficient: it stopped `spl/` from being an *installable* package, but didn't stop it from becoming an implicit *namespace* package once its parent (`src/`) landed on `sys.path` via the editable install. `graph-driven-workflow/spl/` never had this problem because that repo's `spl/` directory was never nested under any `src/` that setuptools puts on `sys.path`.

**Fix**: moved `spl/` out of `src/` entirely, to `graph-code/spl/` (top-level, sibling to `src/`, `apps/`, `docs/`, `tests/`) — matching `graph-driven-workflow`'s own layout exactly. Only `src/` is registered in `pyproject.toml`'s `[tool.setuptools.packages.find] where = ["src"]`, so a top-level `spl/` is never added to `sys.path` by the editable install and can no longer collide with the real `spl` package. `tools.py`'s own sibling-loading path (`_SPL_DIR = Path(__file__).parent`) is relative, so the move required no code change — only doc paths (`src/spl/...` → `spl/...`, reflected throughout §7 below) and stale `__pycache__` (deleted).

**Re-verified 2026-08-11 — confirmed fixed, plus a real end-to-end result**: Wen re-ran the exact §7.3 command. The import error is gone. `spl3` generated all 5 backend nodes via `claude_cli` (`db_connection`, `todo_schema`, `todo_orm_model`, `crud_operations`, `api_routes`), each passing both node-level and edge-level verification, and wrote `apps/todo/backend/app/{database,schemas,models,crud,main}.py` — 24.0s total. The workflow then correctly **stopped** at the final test-gate `ASSERT`, because `apps/todo/backend/tests/` didn't exist yet: `run_component_tests` found no `tests/` directory (`no_tests: true`), and `build_component.spl`'s own design (§0 comment: "no_tests" halts the repair loop rather than looping pointlessly) correctly refused to fake a pass. This is `build_component.spl` **verifying against** a pre-existing test suite, not generating one — working as designed, not a bug.

**Fixture gap found and closed**: `graph-driven-workflow/apps/SPL/todo/components/backend/tests/` already has a complete, working suite (`conftest.py`, `test_routes.py`, `test_crud.py`, `test_schemas.py`) written against the identical `app.database`/`app.main`/etc. module layout — never copied over during the migration. Copied to `apps/todo/backend/tests/`, plus an empty `apps/todo/backend/app/__init__.py` (present in the original, harmless namespace-package marker). Ran directly against the **freshly LLM-generated code from this run** (no additional LLM call needed):

```
22 passed, 1 warning in 0.69s
```

All 22 tests green, first try, no repair loop triggered — `claude_cli`'s generated backend satisfied the exact contract declared in `backend.graph.yaml`'s `verification:` block on the first attempt. This is the first real evidence point for the vision doc's §5 checklist: the forward pass, on the new `graph_code` v2.2 API, produces correct working code from a blueprint. (Re-running `spl3 run` itself, now that `tests/` exists, would additionally confirm the in-workflow `ASSERT` passes — not yet done, since the pytest run above already confirms correctness without spending another LLM call.)

### 6.2 Frontend run (2026-08-11) — same result, plus a real bug found in the test-gate logic

Wen ran the frontend equivalent (`component_graph=apps/todo/blueprint/frontend.graph.yaml`, `tech_profile=vue_typescript`). All 5 nodes (`todo_item_component`, `api_client`, `todo_list_component`, `App_vue`, `main_ts`) generated and passed node-/edge-level verification — 22.0s total — but the test-gate stage failed differently than the backend case:

```
npm error enoent Could not read package.json: ... open '.../apps/todo/frontend/package.json'
```

**This is a real bug, not a repeat of the "no tests/ dir" case.** `build_component.spl`'s inline `run_component_tests` TOOL_API special-cases the `python_fastapi` branch (`os.path.isdir(workdir/tests)` check → `no_tests: true` before ever invoking pytest — this is what let the backend run above halt cleanly). The `vue_typescript` branch has no equivalent check — it runs `npm test` unconditionally. With no `package.json` yet (same fixture gap as the backend, just not yet closed for frontend), npm's ENOENT was misread by `get_test_status`/`identify_broken_node` as an ordinary test failure, not a "nothing to verify" state. The repair loop consequently burned **3 unnecessary `GENERATE repair_node` calls** against `todo_list_component`, each "fixing" a component that was never broken, in response to an error message about a missing `package.json` that has nothing to do with the component's code.

**Fixture gap closed the same way as §6.1**: copied `package.json`, `package-lock.json`, `vite.config.ts`, `tsconfig.json`, `index.html` from `graph-driven-workflow/apps/SPL/todo/components/frontend/` (not `src/` — that would have overwritten this run's freshly generated components — and not `node_modules/`, reinstalled fresh instead), plus the reference `tests/{TodoItem,TodoList}.spec.ts`. `npm install` (213 packages) then `npm test`:

```
Test Files  2 passed (2)
     Tests  14 passed (14)
```

14/14 pass — the 3 spurious repairs didn't corrupt `TodoList.vue` (inspected manually: still clean, idiomatic Composition API code; the repair LLM apparently just regenerated equivalent-quality code each time despite the misleading error context it was fed).

**Fixed 2026-08-11**: `run_component_tests`'s `vue_typescript` branch in `spl/build_component.spl` now has the same upfront existence check the `python_fastapi` branch already had — `os.path.isfile(workdir/"package.json")` → `no_tests: True` (returncode `254`, matching npm's real ENOENT exit code) before ever invoking `npm test`. Verified two ways: `spl3 explain spl/build_component.spl` still parses the workflow correctly after the edit (36 estimated LLM calls, unchanged), and the exact logic was extracted and run standalone against both a missing-`package.json` dir (short-circuits to `no_tests: true`, no `npm` invocation) and a present-`package.json` dir (falls through to `npm test` unchanged) — both behave as intended. Not yet re-verified via an actual `spl3 run` against a fresh (non-scaffolded) frontend output dir, since that would require another LLM run to reach the test-gate stage.

## 7. Testing — the `spl123` conda environment

`spl123` is the conda environment where this gets tested end-to-end (not the shell used for steps 1–4's verification above). Confirmed present on this machine:

| Tool | Status in `spl123` |
|---|---|
| `spl3` (v3.3.0) | Installed as a CLI (`spl3 run`, `spl3 explain`, etc.) |
| `spl.tools` (the `spl_tool` decorator) | Resolves to `/home/gongai/projects/digital-duck/SPL.py/spl/tools.py` — confirms `SPL.py` is the sibling runtime repo, per `CLAUDE.md`'s design constraint |
| `pytest`, `networkx`, `pyyaml` | All installed |
| `graph_code` (this repo, editable) | **Not yet installed** — needs `pip install -e ".[dev]"` from the repo root before either `pytest` or `tools.py`'s `import graph_code` will resolve in this env |

**Verified 2026-08-11**: `pip install -e ".[dev]"` succeeds in `spl123`; `pytest tests/ -v` then passes 78/78; `spl3 explain spl/build_component.spl` (no `--tools`, no LLM call) parses the workflow correctly — 36 estimated LLM calls, all `CALL`/`GENERATE`/`EVALUATE` steps recognized, confirming the `.spl` file itself is structurally sound under spl3. Note: `--tools` is a `spl3 run`-only flag — `spl3 explain --tools ...` errors with "No such option"; there is no tools-aware dry run.

### 7.1 One-time setup

```bash
conda activate spl123
cd /home/gongai/projects/digital-duck/graph-code
pip install -e ".[dev]"
```

### 7.2 Run the graph_code unit tests

```bash
pytest tests/ -v
```

Expect 78 passed (72 original + 6 `TestBlueprint` cases added in step 3). This was run successfully with `PYTHONPATH=src` in the verification shell (no install needed there); in `spl123`, the editable install from §7.1 makes `PYTHONPATH` unnecessary.

### 7.3 Run the forward pass for real — `build_component.spl` against the todo backend

This is the check flagged as "not yet run" in §6 — the actual SPL interpreter, not a Python-level smoke test.

```bash
conda activate spl123
cd /home/gongai/projects/digital-duck/graph-code
spl3 run spl/build_component.spl \
  --tools spl/tools.py \
  -p component_graph=apps/todo/blueprint/backend.graph.yaml \
  -p tech_profile=python_fastapi \
  -p output_dir=apps/todo/backend \
  --llm claude_cli
```

`--llm claude_cli` is the `ADAPTER:MODEL`-style shorthand and wins over separate `--adapter`/`-m` flags per `spl3 run --help`; use whichever LLM is configured in this environment. Success criteria: the workflow completes, `apps/todo/backend/` contains `app/{schemas,database,models,crud,main}.py`, and the final `ASSERT all_tests_passed(@test_result)` passes (pytest run against the generated code, up to 3 repair attempts per `build_component.spl`'s own retry loop).

Repeat with `component_graph=apps/todo/blueprint/frontend.graph.yaml`, `tech_profile=vue_typescript` for the frontend half.

```bash
conda activate spl123
cd /home/gongai/projects/digital-duck/graph-code
spl3 run spl/build_component.spl \
  --tools spl/tools.py \
  -p component_graph=apps/todo/blueprint/frontend.graph.yaml \
  -p tech_profile=vue_typescript \
  -p output_dir=apps/todo/frontend \
  --llm claude_cli
```

#### 7.3.1 build app

```bash
conda activate spl123
cd /home/gongai/projects/digital-duck/graph-code
spl3 run spl/build_app.spl \
  --tools spl/tools.py \
  -p system_yaml=apps/todo/blueprint/main.graph.yaml \
  -p output_dir=apps/todo-v4 \
  --llm claude_cli
```



### 7.4 Run the generated apps for real

This is beyond `build_component.spl`'s own test gate (§7.3, which runs pytest/vitest against the generated code) — actually starting both servers and confirming they work together as a running system.

**Backend** — needs its generated `requirements.txt` (§8.1) installed first:

```bash
conda activate spl123
cd /home/gongai/projects/digital-duck/graph-code/apps/todo/backend
pip install -r requirements.txt   # only needed once, or after requirements.txt regenerates
uvicorn app.main:app --reload --port 8000
```

Serves at `http://localhost:8000`; OpenAPI docs at `http://localhost:8000/docs`.

**Frontend** — needs `npm install` and a `.env` pointing at the backend:

```bash
cd /home/gongai/projects/digital-duck/graph-code/apps/todo/frontend
npm install       # only needed once, or after package.json changes
npm run dev
```

Serves at `http://localhost:5173`, and expects the backend already running at `http://localhost:8000` (§7.4.1 below covers the env var this depends on). Run both commands in separate terminals (or background one) to have the full app live — backend first, since the frontend fetches on mount.

#### 7.4.0 Killing a port already in use

`uvicorn ... --port 8000` fails with `ERROR: [Errno 98] Address already in use` when a previous server (often an earlier backgrounded `uvicorn --reload` from an earlier session) is still bound to that port. Use `scripts/clean_port.sh`:

```bash
scripts/clean_port.sh 8000
scripts/clean_port.sh 8000 5173   # backend + frontend in one call
```

It finds the PID(s) via `lsof -t -i :<port>`, sends `SIGTERM`, waits a second, and follows up with `SIGKILL` for anything still alive. Manual equivalent, if `lsof`/the script aren't available:

```bash
fuser -k 8000/tcp
# or:
kill -9 $(lsof -t -i :8000)
```

Same approach applies to the frontend's port (`5173`) if `npm run dev` hits the same error. `uvicorn --reload` in particular can leave an orphaned reloader/worker process behind if the parent shell was closed rather than interrupted with Ctrl-C — check for stragglers with `lsof -i :8000` before assuming the port is free.

#### 7.4.1 Two real bugs found and fixed while verifying this (2026-08-12)

Documented here because they were only caught by actually running the two generated components together — `build_component.spl`'s per-component test gate (§7.3) can't catch either, since both components pass their own unit tests in isolation.

**1. Missing `VITE_API_BASE_URL` — the frontend silently talked to nowhere.** `src/api.ts` reads `const BASE_URL = import.meta.env.VITE_API_BASE_URL as string;` with no fallback. No `.env` file was ever generated or scaffolded, so `BASE_URL` was `undefined` and every fetch call would have targeted the literal URL `undefined/todos`. Fixed by creating `apps/todo/frontend/.env` with `VITE_API_BASE_URL=http://localhost:8000`. Not yet promoted into the blueprint as a generated node (unlike `requirements`, §8.1) — worth doing the same way if this component gets rebuilt from scratch, since right now it's a manually-added file that a `rm -rf apps/todo/frontend && spl3 run ...` from clean would not recreate.

**2. `toggleTodo` used `PATCH`, the backend only exposes `PUT` — genuine interface drift between two independently generated components.** `frontend.graph.yaml` itself declares the contract correctly (`toggle_todo: signature: "PUT /todos/{id} ..."`, matching `backend.graph.yaml`'s own declared port exactly — confirmed by grepping both files), and the backend's generated `app/main.py` correctly implements `@app.put("/todos/{id}", ...)`. But the generated `src/api.ts` used `method: "PATCH"` — the LLM didn't follow its own component's declared contract. `check_call_contracts()` (in `graph_code`) exists and could have caught this — `function.calls` in `frontend.graph.yaml` declares `consumer_requires: "PUT /todos/{id}..."` for exactly this call — but it's not invoked as a runtime gate anywhere in `build_component.spl`'s Stage 2 loop, only available as a library function. Fixed by editing `src/api.ts` directly (`PATCH` → `PUT`) and correcting the matching `.spl_cache/` entry so a future cache hit doesn't re-serve the bug.

**Why this matters beyond just fixing two bugs**: this is a live, concrete instance of exactly the failure mode the whole blueprint/drift vision (`../../../../zinets/docs/publication/TMLR/Graph-Code/README.md`) exists to catch systematically — two components, each independently verified and passing their own tests, silently violating a contract *between* them. `check_call_contracts()` already exists and already would have caught bug #2 specifically. Wiring it into `build_component.spl`'s per-node loop (or, better, `integrate_system.spl` once that workflow is real — see §6's "Deliberately deferred" note) is a concrete, well-scoped next step, not speculative future work.

**Confirmed working end-to-end** (2026-08-12): both servers started together, frontend reachable (200), backend reachable, created a todo via `POST`, toggled it via `PUT` (the fixed method) — round-trip confirmed correct. No stray processes left running afterward.

## 8. Auto-generated README.md per component (2026-08-11)

**What**: both `apps/todo/blueprint/backend.graph.yaml` and `apps/todo/blueprint/frontend.graph.yaml` now declare a `readme` node (`kind: doc`) that depends on the component's actual last node in build order (`api_routes` for backend, `main_ts` for frontend — not necessarily the same as the declared `capstone:` field, which for the frontend is `todo_list_component`, an earlier node; verified via `build_order()` directly rather than assumed). `readme`'s `spec` instructs the LLM to produce a Markdown README (prerequisites, run command, test command, API/component summary) at the component root — explicitly overriding the tech profile's code-style conventions, since those don't apply to prose. Confirmed both blueprints still `validate_full()` cleanly and `readme` sorts last in `build_order()` for both.

**Why this needed code changes, not just YAML**: the existing pipeline assumed every node is source code. Three functions in `spl/tools.py` would have rejected or mis-verified a Markdown README:
- `write_node_file`'s `_looks_like_code()` gate — for `python_fastapi` it calls `compile(text, ...)`, which raises `SyntaxError` on Markdown, causing a silent "SKIP WRITE: does not look like code."
- `verify_node` — same `compile()` check, would report `fail: syntax error` on every README.
- `verify_edges` — checks that dependency symbols appear literally in the code; meaningless for prose.

**Fix**: all three now check `graph.nodes[node].get("kind") == "doc"` and skip the code-specific logic when true (write raw content; skip compile-check; skip symbol-check). `verify_node`'s signature changed from `(code, spec, tech_profile)` to `(node, code, spec, graph_yaml, tech_profile)` to make the kind lookup possible — its one call site in `spl/build_component.spl` updated accordingly. `tech_profiles.py`'s `NODE_FILES` gained a `"readme": "README.md"` entry in both profile dicts.

**Verified** (Python-level smoke test against `apps/todo/blueprint/backend.graph.yaml`, no LLM call — same stubbing approach as §6's original verification): `verify_node`/`verify_edges` both return `"ok"` for a doc-kind node regardless of content shape; `write_node_file` writes the raw Markdown to `README.md` at the component root, content byte-identical modulo the existing `.strip()`. Confirmed the change didn't break the normal path: `verify_node` on a real code node (`api_routes`) with deliberately broken syntax still correctly returns `fail: syntax error`. `spl3 explain spl/build_component.spl` still parses cleanly after the signature change (36 estimated LLM calls, unchanged — `readme` adds a 6th node per component, but `explain`'s call-count estimate is evidently per-workflow-step, not per-node-in-a-loop, so it didn't change with 5→6 nodes).

**Confirmed via a real `spl3 run`**: the backend re-run in §10.4 generated `apps/todo/backend/README.md` as its 6th node, passed node/edge verification, and the in-workflow test-gate `ASSERT` passed (22/22) on the same run — full end-to-end confirmation, not just the function-level wiring check above.

## 8.1 Auto-generated requirements.txt (2026-08-12)

**What**: `apps/todo/blueprint/backend.graph.yaml` gained a second `kind: doc` node, `requirements`, generating `requirements.txt` at the component root — discovered missing when Wen inspected the generated backend after §8's README landed. Unlike `readme` (depends on the last code node, generated last), `requirements` is `composed_of` the backend's primitives (`python`, `sqlite`, `fastapi`, `sqlalchemy`, `pydantic`) and generated early (tier 1) — it's a static manifest of the tech stack, not something that needs the implementation to exist first.

**Spec had to name deps beyond the primitives explicitly**: `fastapi`/`sqlalchemy`/`pydantic` map directly to primitives, but `uvicorn` (needed to actually run the server), `pytest`, and `httpx` (needed for FastAPI's `TestClient`) are never imported in generated code and aren't primitives in the graph — the spec's `contract` field lists them by name so the LLM doesn't omit them just because they're not in `composed_of`.

**No new code changes needed** — reused the exact `kind: doc` bypass mechanism built for `readme` in §8 (`write_node_file`/`verify_node`/`verify_edges` already check `kind == "doc"` generically, not by node id). Only addition: `"requirements": "requirements.txt"` in `tech_profiles.py`'s `NODE_FILES["python_fastapi"]` (backend-only; the frontend's `package.json` is separately hand-scaffolded, not generated by this pipeline).

**Verified** (same function-level smoke test pattern as §8, no LLM call): `build_order()` includes `requirements`, `readme` still sorts last; `verify_node`/`verify_edges` return `"ok"`; `write_node_file` writes correctly to `requirements.txt`. Full 78-test suite and `spl3 explain` both still pass. Not yet run through an actual `spl3 run` — natural to check on the next real backend build (it will regenerate under the current disk cache, since `requirements` is a brand-new node with no existing cache entry, while the other 6 nodes should still hit cache — a good live test of §10's per-node cache granularity in practice, not just the deliberate `use_cache: false` test).

## 8.2 Real bug found in frontend README generation: leaked chat-turn artifact (2026-08-12)

**What happened**: the frontend build (all 6 nodes, 14/14 tests passing, otherwise a clean run) produced a `README.md` whose last line was `Human: continue to generate: TodoItem` — not part of the README's actual content. Confirmed via the raw cached generation (`.spl_cache/b932f379b13e2c4f.json`) that this text was present **before** any of graph-code's own post-processing touched it — i.e. it came straight out of the `GENERATE` call itself, not something `write_node_file`/`_strip_fences` introduced.

**Why nothing caught it**: `kind: doc` nodes deliberately skip `verify_node`'s compile-check and `verify_edges`' symbol-check (§8) — necessary, since Markdown can't be `compile()`-checked the way Python can, but it also means doc nodes have **no shape verification at all**. A code node with the same trailing artifact would have failed `compile()` immediately and triggered the refine loop; a doc node sailed through untouched.

**Likely root cause** (not fixed here — out of scope for `graph-code`): the log line `GENERATE segment 1 (write_node)` suggests `SPL.py`'s executor chains/segments generation internally; `"Human: continue to generate: {next_node}"` reads like a fragment of that chaining mechanism's own internal continuation prompt, leaked into the visible output rather than consumed internally. Worth investigating in the sibling `SPL.py` repo separately.

**Mitigation added here**: `spl/tools.py` gained `_strip_chat_artifacts()` — strips a trailing `\n(Human|Assistant|User|System):\s...` pattern from doc-node content, applied in both `write_node_file` and `verify_node` right after the existing `_strip_fences()`. Defensive, not a root-cause fix: catches this specific leak pattern regardless of where it originates. Verified against the exact observed artifact (strips cleanly) and against legitimate prose that happens to contain the words "Human"/"Assistant" mid-sentence (e.g. "Human resources data") — confirmed no false-positive strip, since the regex requires the marker at the start of a line immediately followed by a colon.

**Cleanup**: manually stripped the artifact from both the already-written `apps/todo/frontend/README.md` and its `.spl_cache/` entry, so a future cache hit doesn't re-serve the corrupted version. Full 78-test suite and `spl3 explain` still pass after the fix. Not yet re-verified via a fresh `spl3 run` producing a new README from scratch (would need a fresh, uncached node to trigger a real `GENERATE` call and confirm the strip fires on genuinely new output, not just the already-captured artifact).

## 9. Test-gate fix: vue_typescript missing-scaffold check (2026-08-11)

Companion fix to §6.2's discovered bug. `run_component_tests` in `spl/build_component.spl` now checks `os.path.isfile(workdir/"package.json")` before running `npm test`, mirroring the `python_fastapi` branch's pre-existing `tests/` directory check — returns `no_tests: True` (returncode `254`, npm's real ENOENT code) immediately rather than letting `npm`'s ENOENT get misread as a test failure and burn repair-loop `GENERATE` calls against working code. Verified: `spl3 explain` still parses; the exact logic extracted and run standalone against both a missing-`package.json` dir (short-circuits, no `npm` call) and a present-`package.json` dir (falls through unchanged) — both correct. Not yet re-verified via a real `spl3 run` against a fresh, non-scaffolded frontend output dir.

### 9.1 Wired `contract_warnings` into `build_component.spl`'s generation loop (2026-08-12)

New `contract_warnings(graph_yaml)` tool in `spl/tools.py` calls `graph_code.check_call_contracts()` and joins any violations one per line (`""` if none). `build_component.spl` now calls it once, right after `setup_graph`/`get_tech_profile`/`order_length`/`order_bullets`, and logs the result — `LEVEL INFO` with "No declared call-contract mismatches" when clean, `LEVEL WARN` plus an appended log-file section when not.

**Scope, stated plainly** (also in the tool's own docstring): `check_call_contracts()` compares two strings *declared in the yaml itself* — a `function.calls` entry's `consumer_requires` against its `provider_guarantees` — against each other. It does **not** inspect generated code. It catches yaml *authoring* drift (editing one side of a declared contract without the other); it does not catch code-vs-contract drift, i.e. a case where both declared sides already agree but the LLM generated code that follows neither. Concretely: the `toggleTodo` PATCH-vs-PUT bug found and fixed during §7.4.1 testing would **not** have been caught by this check, because `frontend.graph.yaml`'s `function.calls` entry already declared `PUT` on both `consumer_requires` and `provider_guarantees` — the yaml was never wrong, only the generated `api.ts` was. An earlier draft of this doc claimed this check "would have caught" that bug; that claim was wrong and is corrected here.

Verified without any LLM call: ran `contract_warnings()` directly against `apps/todo/blueprint/frontend.graph.yaml` (real file) → `""`. Ran it against a deliberately-mismatched test yaml (one side of a `function.calls` contract edited to `PATCH`, the other left as `PUT`) → correctly reported one violation line. `spl3 explain spl/build_component.spl` now reports 37 estimated LLM calls (up from 36 before this change), with `CALL contract_warnings(...)` visible as a new step.

## 10. Disk-backed, per-node cache with fine-grained `use_cache` override (2026-08-11)

**Motivation**: confirmed by reading the code (per Wen's question before this work) that the pre-existing cache (`_CODE_CACHE` in `spl/tools.py`) was a **plain in-memory Python dict** — scoped to one `spl3` process. Since every `spl3 run` is a fresh CLI invocation, that dict started empty every time; `cache_get` always returned `"miss"`, and every node regenerated on every run regardless of what was already on disk from a previous run (visible in both the backend and frontend runs above — every node logged `cache MISS`). Not useful for iterative development or for controlling LLM cost on a larger app.

### 10.1 Disk-backed cache

`cache_get`/`cache_put` in `spl/tools.py` now read/write JSON files under `{output_dir}/.spl_cache/{key}.json` (added to `.gitignore` — build artifact, not source). The cache key is `sha256({node, spec, tech_profile})[:16]`, **not** just the node id — so editing a node's `spec` in the graph.yaml correctly misses and regenerates, rather than serving stale code for a changed spec. Colocated with `output_dir` rather than global, matching the existing "`rm -rf output_dir` = clean slate" mental model — building the same graph into two different output dirs does not share cache, by design.

`build_component.spl`'s Stage 2 loop was reordered: `node_spec`/`node_context` now run *before* `cache_get` (previously after), since the spec text is part of the cache key. `cache_get`'s and `cache_put`'s call sites and the tool signatures changed together: `cache_get(node, spec, tech_profile, output_dir, graph_yaml)`, `cache_put(node, code, spec, tech_profile, output_dir)`.

### 10.2 Per-node `use_cache` override (Wen's addition)

A node's own `use_cache` attribute in graph.yaml (default `true` when absent, following the same "absent = default" convention as the `blueprint:` block — see `blueprint-schema-v2.2.md` §4) is checked inside `cache_get` *before* touching disk. Setting `use_cache: false` on one specific node forces that node to always miss and regenerate — independent of every other node's cache state, and independent of the workflow's global `--use_cache` (`@use_cache`, default `true`) flag, which when set to `false` forces *all* nodes to miss. This is the fine-grained, per-node control the graph.yaml schema exists to enable: force one broken or actively-being-iterated-on node to regenerate without discarding the whole build's cache. As of `blueprint-schema-v2.2.md` §8.2, `use_cache: false` can also be set on an explicit `form.edges:` entry, forcing the edge's `to` node to miss whenever that specific dependency is marked as changed.

```yaml
form:
  nodes:
    api_routes:
      kind: module
      use_cache: false   # always regenerate this node; every other node still hits cache
      ...
```

Remove the attribute (or set it back to `true`, or omit it) once satisfied with the node, to let it start hitting cache again on future runs.

### 10.3 Verified (no LLM call — direct function-level smoke test)

1. Fresh cache dir → `cache_get` returns `"miss"`.
2. `cache_put` then `cache_get` with the same `(node, spec, tech_profile)` → hit, returns the exact cached code.
3. Same node, **different** spec text → miss (confirms spec-sensitivity, not just node-id keying).
4. `apply_use_cache` still overrides a real hit to `"miss"` when `use_cache="false"`, passes it through unchanged when `"true"`.
5. **Cross-process persistence**: cached a value via one Python module instance, read it back via a second, freshly-loaded instance of `tools.py` pointed at the same `output_dir` — hit. This is the property the old in-memory dict never had, and the entire point of this change.
6. `use_cache: false` on a node with a valid, matching cache entry on disk → still returns `"miss"`. A sibling node without the attribute, same cache state → hits normally.

All confirmed via inline test scripts (not committed — same throwaway-verification pattern as §6/§8's earlier checks). Full 78-test suite and `spl3 explain spl/build_component.spl` both still pass/parse after the rewrite.

**Known limitations, not fixed here** (documented inline in `tools.py` as well):
- Cache key does not include a node's *dependencies'* generated content — if a dependency's code changes but this node's own spec text doesn't, this node's cache entry is not invalidated even though `node_context()` would now feed it different context. Full dependency-aware invalidation would need to hash the dependency chain too; related to, but not solved by, the blueprint lineage/drift work this project is building toward.
- `cache_put` is called after `verify_node`/`verify_edges` run (with at most one `refine_node` attempt each) but **without re-verifying the refined code** — a pre-existing gap in the Stage 2 loop, not introduced by this change. Previously self-limiting (every process started with an empty cache, so a bad cached entry only lived for one run); now that the cache persists, a node that failed verification, got "refined" once, and still isn't clean can be cached and served as a hit indefinitely. Worth fixing if this becomes a real problem in practice — flagged rather than silently left undocumented.
### 10.4 Confirmed via a real `spl3 run` (2026-08-11)

Wen re-ran the backend build twice against the same `output_dir` (`apps/todo/backend`):

| Run | Result |
|---|---|
| 1st (cache empty) | 6/6 `cache MISS`, 6 LLM calls, 33.6s total, `.spl_cache/` populated with 6 entries |
| 2nd (cache warm, same command, unchanged graph) | 6/6 `cache HIT` — including the new `readme` node — **0 LLM calls**, 0.0s per node, 1085ms total latency (process + pytest overhead only) |

Test suite still passed 22/22 on the cache-hit run, confirming the reused code is correct, not just present. This is the real-world confirmation §10.3's function-level tests predicted but didn't themselves prove — cache persistence across separate `spl3` process invocations, and per-node hit/miss reporting, both work as designed.

## 11. Reference apps not yet ported (context for future work, not this step)

`graph-driven-workflow/apps/SPL/` holds several already-scaffolded apps beyond todo — `expense`, `kanban`, `mealie`, `fullstack`, `dispatch`, `conduit` — each with its own `system.yaml`, `components/`, `scripts/`, and (for `conduit`, `fastapi`, `fullstack`, `mealie`) an `analysis.json` suggesting some were reverse-mined rather than hand-authored. None of these have been brought into `graph-code/apps/` yet, and per Wen (2026-08-11) they still need testing even in their current location. Out of scope for this step — noted here so it isn't rediscovered from scratch later. Bringing one over would be a good real second data point once the todo app's forward pass (§7.3) is confirmed working, and *before* it, a natural candidate to point the reverse miner at once that exists (§2, item 2).

**Would `spl3 run` against `apps/todo/blueprint/main.graph.yaml` (the top-level system graph) build the complete todo app, as-is, before §12 below?** No. Confirmed empirically, not by inspection alone: `graph_code.build_order()` on `apps/todo/blueprint/main.graph.yaml` returns exactly one node, `['todo_app_shell']` — `backend`/`frontend` are declared under `imports:`, not `form.nodes`, so they never enter this graph's own node set; they only appear as phantom `form_graph` entries pulled in by `todo_app_shell`'s `depends_on: [backend, frontend]` edge. And `todo_app_shell` itself has no `spec:` block — nothing for a `GENERATE` call to work from. `build_component.spl` is built to walk one component's node graph and generate real code per node; pointed at the system graph, it would generate essentially nothing meaningful for that one placeholder node. The system graph was never meant to be a `build_component.spl` target — it's the input to §12's `build_app.spl` instead, which builds each *imported* component graph (the thing `build_component.spl` is actually designed for) and only then integrates them.

## 12. System-level orchestration: `build_app.spl` and `integrate_system.spl` (2026-08-12)

Ported (not copied) from `graph-driven-workflow/spl/{build_app,integrate_system}.spl`, adapted to graph-code's schema and to a mechanism that actually exists — see below.

**The `run_workflow` primitive the originals assumed does not exist.** Both original files called `CALL run_workflow("build_component", component_graph=..., ...) INTO @manifest` to invoke one workflow from inside another. Searched `SPL.py/spl3/cli.py` and the wider `SPL.py` source for any CALL-able `run_workflow`: none exists. The only `run_workflow`-named thing found is `_run_workflow`, an internal `asyncio` helper used by the CLI's own `run`/`resume` commands — not something a `.spl` script can `CALL`. The graph-driven-workflow originals were never actually runnable end-to-end as written; this was previously unnoticed because nobody had tried running `build_app.spl` for real.

**What this version does instead**: `spl/tools.py` gained `run_build_component(...)` and `run_integrate_system(...)`, both thin wrappers around a `_run_spl_subprocess()` helper that shells out to `spl3 run spl/<workflow>.spl --tools spl/tools.py --llm <llm> -p k=v ...` — literally the same command a person would type by hand (as documented throughout §7). Success/failure is read from the subprocess's exit code; on failure the returned string is prefixed `FAILED (exit N):` so the caller's `EVALUATE ... WHEN contains("FAILED")` branches work unchanged from the original design.

**Component ordering**: rather than a `depends_on` graph between components (which the schema doesn't declare — there's no cross-component dependency edge, only the single `todo_app_shell.depends_on: [backend, frontend]` inside the *system* graph's own node set), component build order is just the system graph's authored `imports:` list order (`system_components()`/`component_count()`/`component_item()`/`component_id()`/`component_graph()` in `spl/tools.py`). `apps/todo/blueprint/main.graph.yaml` declares `imports: [backend, frontend]` in that order, which is also the correct dependency order (frontend's `api_client` is verified against backend's exports at frontend's own load time — see `frontend.graph.yaml`'s `imports:`).

**New orchestration-only yaml fields**: `backend.graph.yaml`/`frontend.graph.yaml` each gained `tech_profile:` and `port:` at the top level (e.g. `tech_profile: python_fastapi`, `port: 8000`). These are read directly with `yaml.safe_load` by the new system-level tools, not routed through `graph_code`'s `GraphDomain` — `build_order`/`validate_full`/`check_call_contracts` have no need to know how or where a component runs, only the orchestration layer does, so this stays out of the core schema library by design.

**No integration-glue generation step**, unlike the original `integrate_system.spl` (which had a `write_integration_glue` `CREATE FUNCTION` generating CORS/env-var wiring per component pair via an LLM call). For this app the wiring already exists in the generated code (backend's CORS middleware, frontend's `VITE_API_BASE_URL`) and is already checked by `contract_warnings()` at each component's own build time (§9.1) — spending an LLM call to regenerate glue that's already correct and already declared-consistent would be pure waste. Dropped rather than faithfully ported; noted here in case a future multi-service app genuinely needs generated glue.

**Acceptance tests are HTTP-level against the live backend only**, not full browser E2E against the frontend. `integrate_system.spl` starts the generated backend with `uvicorn` (`start_backend_server`), polls `/docs` until it responds (`wait_for_http`), then for each non-capstone application in `apps/todo/blueprint/main.graph.yaml`'s `applications:` block (`create_todo`, `list_todos`, `toggle_todo`, `delete_todo` — `manage_todo_list` is excluded via its `capstone: true` flag, since it composes the other four rather than adding an independent contract) generates a self-contained stdlib-only Python acceptance test against `spec.user_story`/`spec.contract`, runs it, and reports PASS/FAIL. The backend is stopped (`stop_process`) unconditionally afterward. This validates the API contract every application's spec actually describes (status codes, response shapes, persistence) — it does not click checkboxes or submit forms in a real browser, which would need Playwright or similar infra not yet set up in this repo. A real scope reduction, stated here rather than left implicit.

**Verified without any LLM call, before the first real run**:
- `spl3 explain spl/build_app.spl` and `spl3 explain spl/integrate_system.spl` both parse cleanly.
- Every new `spl/tools.py` function (`system_components`, `component_count/item/id/graph`, `component_tech_profile/port/output_dir`, `check_components_verified`, `system_applications`, `app_count/item/spec_text/backend_endpoints`, `write_test_file`, `run_acceptance_test`) run directly against the real `apps/todo/blueprint/main.graph.yaml` — correct component list, correct tech profiles/ports, `check_components_verified` correctly reports `"ready"` against the already-built `apps/todo/{backend,frontend}` output dirs from §7.4's testing, correct 4-application list with `manage_todo_list` correctly excluded, correct per-application backend endpoint text.
- `start_backend_server`/`wait_for_http`/`stop_process` exercised against a throwaway `python -m http.server` process (not the real backend, to avoid an unnecessary real-server round-trip in this check): reports `"ready"` while the server is up, `"timeout"` after it's stopped, `stop_process` returns `"stopped"`/`"not_running"` correctly in both cases.
- `run_acceptance_test` exercised against a canned pass-case (`print("PASS")` → `"PASS"`) and fail-case (`assert False` → `"FAIL: <traceback tail>"`) script.
- `run_build_component`/`run_integrate_system`'s subprocess command construction verified with `subprocess.run` mocked (no real `spl3` invocation, no LLM cost) — confirmed the exact `spl3 run <path> --tools <path> --llm claude_cli -p k=v ...` command and correct `cwd`.

### 12.1 Running it for real

```bash
conda activate spl123
cd /home/gongai/projects/digital-duck/graph-code

spl3 run spl/build_app.spl \
  --tools spl/tools.py \
  -p system_yaml=apps/todo/blueprint/main.graph.yaml \
  --llm claude_cli
```

By default, no `-p output_dir=...` is needed — each component's output directory is derived automatically from its own `imports:` path (`component_output_dir()` in `spl/tools.py` strips `.graph.yaml` off e.g. `apps/todo/blueprint/backend.graph.yaml` → `apps/todo/backend`). **`@output_dir` is now a real workflow input** (added 2026-08-12, in response to Wen wanting to save a full generated app somewhere other than next to its blueprint, to test a fresh generation without overwriting an existing one) — pass it to redirect every component into `{output_dir}/{component_id}/` instead:

```bash
spl3 run spl/build_app.spl \
  --tools spl/tools.py \
  -p system_yaml=apps/todo/blueprint/main.graph.yaml \
  -p output_dir=apps/todo-v3 \
  --llm claude_cli
```

This writes `apps/todo-v2/backend/` and `apps/todo-v2/frontend/` — the blueprint files themselves (`apps/todo/*.graph.yaml`) stay where they are and are only read, never moved. `output_dir` threads through `run_build_component` (per-component `output_dir` param) and `run_integrate_system` → `integrate_system.spl` (so `check_components_verified` and the live backend server both look in the same redirected location) — see `component_output_dir(component_graph_path, output_dir="")` in `spl/tools.py`, which returns the default sibling-dir path when `output_dir` is empty and `{output_dir}/{component_id}` otherwise. An empty/omitted `-p output_dir=...` is fully backward compatible with every example in this section before 2026-08-12.

A fresh `output_dir` means an empty `.spl_cache` too, so the first run there is a real full generation (real LLM calls for every node), not a cache-hit replay of `apps/todo/{backend,frontend}`. Both components (`apps/todo/backend`, `apps/todo/frontend`) are already built from §7.4's testing, so §10's disk cache should make the two `run_build_component` sub-invocations near-instant (`cache HIT` on every node) rather than re-spending LLM calls on unchanged code when *not* using `output_dir` — only `integrate_system.spl`'s 4 acceptance-test `GENERATE` calls and the live backend start/stop are new spend in that case. To force a clean end-to-end run against the *default* location instead (real component regeneration, not cache hits), delete the cache first:

```bash
rm -rf apps/todo/backend/.spl_cache apps/todo/frontend/.spl_cache
```

`uvicorn` must be on `PATH` inside the `spl123` env (`start_backend_server` in `spl/tools.py` shells out to it directly) — confirm with `conda run -n spl123 which uvicorn` if the integration phase fails immediately with a `FileNotFoundError`. Build logs land under `logs/spl/build_*.md`; generated acceptance-test scripts land under the same `--log_dir` (default `logs/spl/`) as `test_acceptance_<app>.py`, and are safe to leave in place or delete after inspecting a failure.

### 12.2 Confirmed via a real `spl3 run` (2026-08-12) — one real bug found and fixed along the way

Wen ran §12.1's command for real. First attempt **falsely reported the backend as failed** even though its own subprocess log showed a clean pass (22/22 tests, exit 0, `ASSERT passed`). Root cause: `spl3 explain` marks `build_app.spl`'s `EVALUATE @comp_manifest WHEN contains("FAILED")` `(semantic)` — spl3 judges that branch with an LLM call rather than a literal substring match — and `@comp_manifest` at the time held up to 4000 raw characters of the sub-invocation's own log output, including the substring `"0 failed"` among other noisy phrases. The semantic classifier misread the dump as a failure. **Fixed**: `_run_spl_subprocess()` in `spl/tools.py` no longer returns the raw transcript for branching — it returns one short, unambiguous line (`"ok — full log: <path>"` or `"FAILED (exit N): <last line> — full log: <path>"`) and writes the full transcript to `logs/spl/<workflow>.subprocess.log` for debugging instead.

Second attempt, after the fix, completed cleanly end to end:

| Phase | Result |
|---|---|
| backend build | cache HIT × 7, 0 LLM calls |
| frontend build | cache HIT × 6, 0 LLM calls |
| integration: backend server | started on :8000, ready in <1s |
| acceptance test: `create_todo` | GENERATE (534 tokens) → PASS (10.1s) |
| acceptance test: `list_todos` | GENERATE (800 tokens) → PASS (16.8s) |
| acceptance test: `toggle_todo` | GENERATE (867 tokens) → PASS (14.8s) |
| acceptance test: `delete_todo` | GENERATE (515 tokens) → **FAIL** (11.4s) |
| total | 57.1s, 4 real LLM calls |

`delete_todo`'s generated acceptance test asserted `DELETE /todos/nonexistent-id-000` (a string) returns `404`, but got `422` — a genuine artifact in the *generated test*, not a backend defect: the route's `id` path param is typed `int` (per `backend.graph.yaml`'s spec), so FastAPI's own path-param validation rejects a non-integer id with `422` before the handler's declared "404 if not found" logic ever runs. The right edge-case id would have been a syntactically valid, merely nonexistent integer (e.g. `999999`).

**Fixed two places**: (1) the specific generated test at `logs/spl/test_acceptance_delete_todo.py` — the id changed to `999999`, re-run directly against a live backend → `PASS`; (2) the durable source — `write_acceptance_test`'s prompt in `spl/integrate_system.spl` now explicitly calls this out (item 4: use "a syntactically valid id of the correct type that simply does not exist," with this exact failure mode spelled out as the reason), so future acceptance-test generations for any app don't repeat it.

### 12.3 A second real run exposed a second, more serious bug: exit code alone isn't a reliable failure signal (2026-08-12)

Wen re-ran §12.1's command a third time. `integrate_system.spl`'s prompt fix worked — the freshly-generated `delete_todo` test independently chose `999999` on its own, no hand-editing needed. But this run's `toggle_todo` acceptance test failed for an unrelated reason, and **`build_app.spl` still reported "System build complete" as if nothing had gone wrong** — a second false negative, caught by Wen inspecting the pasted terminal output rather than trusting the summary line.

**Root cause**: `Status:  complete` in spl3's own CLI output only means the workflow ran to completion without an engine-level crash (an uncaught exception or a hard `ASSERT` failure) — it says nothing about the *content* of the workflow's `RETURN` value. `integrate_system.spl` correctly executes `RETURN f"FAILED:{@report}"` when an acceptance test fails, but that's just a string return, not an `ASSERT` — so the subprocess still exits `0`. `_run_spl_subprocess()`'s exit-code-only check (added in §12.2's fix) had no way to see this: it reported `"ok"` back to `build_app.spl`, which then logged "System build complete" over an integration that had actually failed.

**Fixed**: `_run_spl_subprocess()` now also parses the `Output:  ...` block spl3 prints (the workflow's own `RETURN` value, echoed verbatim) via a new `_extract_return_value()` helper, and treats a literal `FAILED`/`BLOCKED`/`BUILD HALTED` prefix there as a failure too, independent of exit code. Verified against the actual captured `toggle_todo`-failure log from this run — `_extract_return_value()` correctly recovers `"FAILED:\n- PASS create_todo...\n- FAIL toggle_todo: ..."` and flags it — and against the earlier all-green backend build log, which correctly still reports no failure (no false positive introduced).

**Re-ran a fourth time after the fix**: `build_app.spl` now correctly reported `"Integration failed"` / `"BUILD FAILED at integration"` instead of a false "complete" — the failure-detection bug is confirmed fixed. This run's actual acceptance-test failures (`create_todo`, `list_todos` both crashed on `json.loads()` against an empty `204 No Content` body from a `DELETE` call — the generated tests didn't reliably reuse the empty-body-safe `request()` helper pattern) are a separate, generated-*test*-quality issue, not an orchestration bug. Tightened `write_acceptance_test`'s prompt once more — it now embeds the exact `request()` helper as required boilerplate to copy verbatim, with an explicit note about the `204`/`json.loads()` failure mode — rather than continuing to spend real LLM calls chasing generation-quality convergence unprompted. `spl3 explain spl/integrate_system.spl` still parses cleanly after this change. Not yet re-verified with another real run — left for Wen to decide whether/when to spend the next real LLM call on it.

**Net effect of §12.2 + §12.3**: the framework-level bugs (semantic-EVALUATE misread, exit-code-only failure detection) are both found and fixed, each confirmed against real captured logs from real runs. What's left failing is generated-test quality (edge-case id typing, empty-body handling) — exactly the kind of drift the blueprint/drift vision this project is building toward (§5 references) is meant to surface and eventually close the loop on, not a wiring defect in `build_app.spl`/`integrate_system.spl` themselves.

### 12.4 `-p output_dir=...` wired for real, plus two more scaffold-gap bugs found and fixed (2026-08-12)

Wen wanted to save a full generated app somewhere other than next to its blueprint, to test a fresh generation without overwriting `apps/todo/{backend,frontend}`. `@output_dir` is now a real workflow input on both `build_app.spl` and `integrate_system.spl`, threaded through `component_output_dir(component_graph_path, output_dir="")` in `spl/tools.py` — empty/omitted keeps the existing sibling-dir default, non-empty redirects each component to `{output_dir}/{component_id}/`.

First real run with `-p output_dir=apps/todo-v2` immediately surfaced a real gap: the backend build **correctly** halted at Stage 3 with "No tests/ directory ... nothing to verify" (exit 4). This is not an orchestration bug — `tests/` was never generated by any blueprint node; it's pre-authored reference fixture content that was manually copied into `apps/todo/backend/tests/` once during §7.4's earlier prototyping. A brand-new `output_dir` legitimately has none. **Fixed**: new `seed_component_scaffold(component_graph_path, tech_profile, output_dir)` tool copies each profile's known pre-authored scaffold — `tests/` for both, plus `package.json`/`package-lock.json`/`vite.config.ts`/`tsconfig.json`/`index.html`/`.env` for `vue_typescript` — from the default location into the redirected one before the build runs, called from `build_app.spl` right before each `run_build_component`. Deliberately does **not** copy `node_modules/` (large, and copying a dependency tree instead of installing it risks silent drift from `package.json`) — `npm install` still has to be run by hand in a redirected frontend dir once, which is exactly what the second real run then hit (`vitest: not found`, exit 127) and Wen resolved directly (`npm install` in `apps/todo-v2/frontend`, 213 packages).

**Third real run with the scaffold seed + `npm install` in place completed genuinely cleanly**: backend and frontend both built, all 4 acceptance tests actually passed (checked against the raw `integrate_system.subprocess.log` transcript directly, not just the summary line, per the lesson from §12.3). `apps/todo-v2/{backend,frontend}` now holds a complete, independently-generated todo app, separate from `apps/todo/{backend,frontend}`, ready for Wen to test there. `apps/todo/*.graph.yaml` were only read throughout, never modified or moved.

### 12.5 System-level `readme` node (2026-08-12)

`apps/todo/blueprint/main.graph.yaml`'s `form.nodes` gained a `readme` node — `kind: doc`, `composed_of: [todo_app_shell]`, tier 2 — matching the convention already used per-component (`backend.graph.yaml`/`frontend.graph.yaml`'s own `readme` nodes, §8). `graph_code.build_order()` on the system graph now returns `['todo_app_shell', 'readme']` (previously just `['todo_app_shell']`, confirmed via a direct Python check — no regression to the 78-test suite).

Declaring the node alone would be a dead end, though — no orchestration step ever passes the *system* graph to `build_component.spl` (§11 explains why: `todo_app_shell` has no `spec:`, and the system graph's own node set was never meant to be walked that way). So generation is wired directly into `integrate_system.spl` instead, as its final step (§4.5, after the backend is torn down): a new `write_system_readme(spec, results)` `CREATE FUNCTION` GENERATEs the product-level README from the node's own `spec:` block *plus* the just-completed acceptance-test results (`@report`) — so the README's "Status" section reflects what was actually just verified, not just declared intent — and `write_system_readme_file()` writes it to `{output_dir or dirname(system_yaml)}/README.md` (honoring §12.4's `output_dir` redirection). Generated unconditionally, pass or fail, on the theory that a failing run still deserves an accurate status write-up rather than no README at all.

Verified without any LLM call: `system_readme_spec_text()` correctly extracts the node's spec; `write_system_readme_file()` correctly writes to the default location (next to `graph.yaml`) and correctly redirects under `output_dir` when set (tested against both `apps/todo/` and `apps/todo-v2/` directly). `spl3 explain spl/integrate_system.spl` parses cleanly, now showing 5 real `GENERATE` calls per run (4 acceptance tests + 1 system README, up from 4). Not yet confirmed with a real `spl3 run` — the next real run of `build_app.spl`/`integrate_system.spl` (§12.1/§12.4) will produce the first actual generated system-level README.

### 12.6 System-level `ports:` declaration + consistency check (2026-08-12)

Motivated by a real, manually-debugged incident while Wen tested `apps/todo-v2` in a browser: the generated backend's CORS middleware hardcodes `allow_origins=["http://localhost:5173"]`, and running two frontend dev-server instances at once (the original `apps/todo/frontend` and the new `apps/todo-v2/frontend`) caused Vite to silently fall back to `:5174` for the second one — `POST http://localhost:8000/todos` then failed with a CORS preflight error and no indication of the actual cause (a live port collision, resolved by killing the stray process holding `:5173` and restarting the intended one there).

That specific incident is a *runtime* condition (two processes racing for one port) — no yaml change prevents it. But it prompted adding what yaml *can* check: `apps/todo/blueprint/main.graph.yaml` gained a top-level `ports:` block (`backend: 8000`, `frontend: 5173`) as the system's declared single source of truth, alongside each component's own existing `port:` field (`backend.graph.yaml`/`frontend.graph.yaml`, §12.4). New `check_port_consistency(system_yaml)` in `spl/tools.py` compares the two and reports any component whose own declared port disagrees with what the system graph declares — same class of check as `contract_warnings()` (§9.1), same limitation stated the same way: it catches yaml *authoring* drift (editing one side without the other), not the live collision that actually happened here. Wired into `integrate_system.spl` right after the existing readiness check, `LOGGING ... LEVEL WARN` plus a log-file entry on mismatch, `LEVEL INFO` "No port declaration mismatches" when clean — same pattern as §9.1's `contract_warnings` wiring.

Verified without any LLM call: clean case against the real `apps/todo/blueprint/main.graph.yaml` → `""`; a deliberately mismatched copy (`ports.backend` set to `9999`) → correctly reports `"backend: system declares port 9999, ... declares port 8000"`. `spl3 explain spl/integrate_system.spl` still parses (39 estimated calls, up from 38). 78/78 tests still pass — the new `ports:` block doesn't affect `graph_code.build_order()`/`validate_full()` (confirmed: `build_order()` on the system graph is unchanged, `['todo_app_shell', 'readme']`).
