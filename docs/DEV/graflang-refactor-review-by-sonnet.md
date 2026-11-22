# Review of `graflang-refactor.md` (graph-code -> app-graph), by Sonnet 5.5

Date: 2026-11-22
Reviewed: `docs/DEV/graflang-refactor.md` as it stood on 2026-11-22 (235 lines, decisions answered, Phase 0/0b committed, Phase 1 in progress).
For: Opus 5.5, who is implementing the plan. Please reconcile each item below with the plan: accept, reject with a reason, or change; then say which in the plan (or in the table at the end).
The plan file was **not edited** by this review, to avoid edit conflicts.

**Verdict.** The plan is sound: the scope line in section 2 (recipes for the four LLM workflows, Python for the deterministic library, blueprints stay in their own schema), the order of phases, and "tests first for what has none" (Phase 1) are right. One decision (5, Docker for tests) does not work as written; the rest are smaller corrections and additions.

**How this was checked.** Against GraphLang's code (`grafr/solver.py`, `topology.py`, `nodes/guard.py`, `runtime.py::_run_loop`, `lifecycle.py`, `cedar_guard.py`) and against what was built in work-graph (`src/workgraph/recipes/__init__.py`, `processors.p_llm_items`). Nothing was run against app-graph or graph-code. "Verified" below means read in code or run in the `graf` env; "not verified" means inferred.

---

## 1. Serious: Docker for the component tests (decision 5) does not work as written

GraphLang's `container:` on a SOLVE (`solver.py`, `container_command`, line ~199) is narrower than the plan assumes:

| What the plan assumes | What `container:` does |
|---|---|
| the test step sees the generated code in `output_dir` | it mounts **only the recipe's own folder** (`base_dir`), read-only, at `/work`; `output_dir` cannot be mounted. `container.mount` is `ro`, `rw` or `none`, always of that folder |
| the tests can install their dependencies | `--network none` by default, so `npm install` / `pip install` cannot run inside it; the image would need every app's dependencies baked in, and `package.json` differs per app |
| a tool can write results | root is read-only, `/tmp` is a tmpfs |
| the tool is `python -m appgraph.build.tool` | `appgraph` is not installed in the image: the program has to be a self-contained script in the recipe folder (mounted at `/work`) |
| any folder works | on **Docker Desktop**, `check_mount_shared` refuses a mount outside `$HOME` (otherwise `docker run` hangs). That excludes the recipe folder of a system-wide install, and **every `/tmp` fixture the offline acceptance tests build into** |

What a containerized `run_component_tests` would need:

- the component's files passed **in on stdin** (JSON), written by a stdlib-only script into `/tmp` inside the container, tests run there, result printed as JSON;
- one image per profile with the test dependencies baked in; for Node/Vue, `network: bridge` (or a prebuilt `node_modules` layer), which weakens "no network";
- the offline tests running the host-subprocess path (a switch), since `/tmp` fixtures cannot use the container.

Python components could work this way. Vue/Node components are the hard case.

**Suggested change.**

1. Make a **one-hour spike the first step of Phase 3**: by hand, run one Python component and one Vue component through `solver.container_command` / a SOLVE with `container:`, from a folder under `$HOME`. Record what works.
2. If Vue fails: ship the host subprocess behind the GUARD (item 2) as the default, with `container:` as a per-profile option, Python first. The plan's "the component test run is a containerized SOLVE" becomes "may be".
3. Keep the host path for tests that build into a temp folder.

## 2. The GUARD is a coarser boundary than the plan says (decision 5)

Verified in `topology.py` and `nodes/guard.py`:

- A node is risky if its type is `EMIT`, `QUERY` or `RUN_CODE`, or it has `risky: true`. A SOLVE is **not** risky unless marked, so a writing or test-running SOLVE must carry `risky: true` to be guarded at all.
- A `LOOP` whose body holds a risky node is risky itself, and the guard must come **before the LOOP**, not before the node inside it. So one guard covers all blueprint nodes of a build; it cannot decide per file.
- A GUARD evaluates a Cedar policy over `context_mapping` (expressions over its `in_*` values). Cedar's `like` takes only literal patterns, so a policy cannot say "path starts with `output_dir`" for a variable `output_dir`.

So "a Cedar policy allowing writes only under `output_dir` and only the profile's test command" is realistic only as an **attestation**: the step before the guard computes `output_dir_ok` and `command_allowed` (booleans or fixed strings) and the policy permits only when they hold. That documents the trust boundary and makes `graf validate` refuse a recipe with an unguarded risky node, which is worth having, but it is not enforcement of paths. The plan should say so, so nobody reads the guard as a sandbox. For writes, an `EMIT` file node (risky by type, path confined to its `allow_dirs`) is an alternative to a `risky: true` SOLVE. **Not verified:** whether `allow_dirs` can be set per run from an input.

## 3. `python3` in `command:` may not be the environment's Python

The SOLVE environment is only `PATH` and `PYTHONUTF8` (`run_solver`). `python -I` does import editable installs (checked: `python -I -c "import workgraph"` works in the `graf` env), but `python3` is resolved from `PATH`, which can be a different interpreter (the `graf` env has `python3` first, conda base second).

In work-graph this is fixed in the loader: `recipes.Recipe` replaces a leading `python3` in any `config.command` with `sys.executable`. **Suggestion:** put the rule in GraphLang once (for example a `${python}` token, or resolving `python3` to the run's interpreter), then neither package patches it. Until then, app-graph's `run_recipe` needs the same replacement, or the plan's "app-graph must be pip-installed in the env that runs recipes" is not enough.

## 4. LOOP wiring: no `over:` a list

Verified in `runtime.py::_run_loop`. A LOOP iterates by counter (`max_iterations`, which may be an expression such as `"@in_n"`, and the index `cycle`/`index_var`); it has no "for each item of a list". Phases 3 and 4 say "LOOP over the order / over the components". The wiring is: the order is a JSON list input; the body starts with a SOLVE `json_get(@in_order, cycle)`; `max_iterations` is the list's length (a SOLVE before the loop). State carried between rounds goes through `state:`. Worth one line in Phase 3, and a **verify** that a `use:` part works inside a LOOP body for something as large as `build_component` in `build_app` (it works for small ones in `cookbook_v2`).

## 5. Prompt substitution is positional

`GENERATE` replaces `{{in_name}}` for each input in the order of the `in:` mapping (`nodes/generate.py`). A substituted value that itself contains another `{{in_x}}` is substituted again by a later input. For build prompts the risky values are the long free-text ones (dependency code, the spec). Put them **last** in `in:`. This was tested in work-graph (`extract_items`, test "a document that mentions a placeholder is not expanded"). Vue templates' `{{ todo.title }}` are safe: only the exact `{{in_name}}` form is replaced. Prompt placeholders are `{{in_x}}`, not `{{x}}`, which the plan already says.

## 6. Phase 4: "stop the server on every path"

The plan wants `stop_process` on every path, including a failure inside the acceptance-test loop, via a `RECOVER` route. `RECOVER` is the node an `error` route of **one node** ends in (`lifecycle.py`: `fallback: {route: error}`). I found no try/finally equivalent for "any failure inside a LOOP body". The plan marks the start/stop path as the thing to fix (today a crash between start and stop leaks the server), so make it the **first check of Phase 4**: a test that forces a failure inside the loop and asserts the server process is gone. If the runtime cannot do it, options are a stop step on every exit of the loop (the loop's `exit` route and its error route) or having the server tool register an `atexit`/timeout kill. **Not verified** either way.

## 7. Smaller points

- **Call caps.** `max_llm_calls` is a stop, not a plan. Derive the cap from the node count *and* the two repair loops' bounds (per node: spec + write + up to N refine for each check; test gate: up to `max_test_attempts` repairs). Put the bounds in the recipe (`max_iterations`) so `graf validate`'s printed estimate is meaningful.
- **Step cap.** `DEFAULT_MAX_STEPS = 1000` is flagged correctly in the plan; pass `max_steps` from the node count.
- **SOLVE limits.** Defaults are 60 s and 2048 MB (`TIMEOUT`, `MEMORY_MB`); the plan has this. Under `container:` the address-space rlimit is not used (`limit = None`), Docker's `--memory` is, which removes the Node/Vite virtual-memory concern but not the time limit.
- **Logs and `node_output`.** Phase 2's "verify" items are answered by work-graph (section 8).

## 8. What work-graph already settled (closes plan section 7's open item)

The shared helper exists, in `work-graph/src/workgraph/recipes/__init__.py`:

- `Recipe(name, prompt=None)`: loads the graph once (`load_graph`), replaces `python3` by `sys.executable`, fingerprints the recipe folder (used as the cache key), then for each run: `GraphLangRuntime(copy.deepcopy(graph), llm=MeteredLLM(SeamLLM(backend), max_llm_calls), adapter=backend, verbose=False).execute(inputs)`.
- `SeamLLM`: an object with `generate(prompt, model=None, **opts)` that calls the package's own LLM function, so the package's backends, billing rules and error mapping apply to recipes too. A backend limit (`BackendLimitError`) raised there passes through the runtime unchanged.
- Verified answers to Phase 2's "verify": `node_output=None` writes **nothing** beside the recipe (no `.graf/`, no output folder); GraphLang's logging does nothing until `setup_logging` is called (so the caller routes logs); `verbose=False` silences the console.
- Customization: `<home>/custom/recipes/<name>/` overrides a shipped recipe, `prompt:` overrides a recipe's first prompt via `bind_graph`; `check_recipe` loads the recipe and checks its inputs and outputs.
- Measured: loading a small recipe 0.2 s once; a run on a loaded graph about 27 ms of overhead (plus the program subprocess).

**Suggestion:** move this into GraphLang as `graphlang.run_recipe` (together with item 3), and have `appgraph/run.py` and work-graph both call it. Work-graph's commits `ffe3f92` and `55150af` (Phases 2 and 3) are the reference.

## 9. Order in which to reconcile

1. Item 1 (the Docker spike) decides Phase 3's shape: do it first.
2. Item 2: reword decision 5's record so the guard is described as an attestation.
3. Item 3 (and 8): a GraphLang change; decide whether it is done there or locally.
4. Items 4, 5, 6, 7: notes into Phases 3 and 4 and "Must handle".

## Reconciliation (Opus 5.5 fills in)

| Item | Accept / reject / change | Where recorded |
|---|---|---|
| 1 Docker spike, container optional | | |
| 2 GUARD as attestation | | |
| 3 `python3` token / `sys.executable` | | |
| 4 LOOP wiring note | | |
| 5 prompt substitution order | | |
| 6 server stop on every path, first check of Phase 4 | | |
| 7 caps and limits | | |
| 8 shared helper into GraphLang | | |
