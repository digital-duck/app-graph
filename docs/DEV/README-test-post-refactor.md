# Verifying the GraphLang refactor: zinet, graflang, work-graph, app-graph

Written 2026-11-22, at the end of the refactor, for a manual pass the next day. It checks that each repo
**works** (new behaviour) and **has not regressed** (old behaviour, compared with the pre-refactor code
where it still exists: graph-code for app-graph, the in-code Python path for work-graph's `llm_items`).

Work through the parts in order: each repo depends on the one before it (zinet ← graflang ← work-graph and app-graph). Every step says what to run and what you should see. Steps marked **[LLM]** make real, billed model calls (all capped). Steps marked **[Docker]** need Docker Desktop running.

Record results in the checklist at the end.

---

## 0. Setup (5 min)

```bash
conda activate graf
cd ~/projects/digital-duck

# every repo installed editable in this env
pip show zinet graflang workgraph app-graph dd-llm | grep -E "^(Name|Version|Editable project location)"
```

Expected versions:

| Package | Version | Editable location | CLI |
|---|---|---|---|
| zinet | 0.2.2 | `zinet` | *zinet* |
| graflang | **0.3.0** | `graflang` | *graf* |
| workgraph | 0.2.0 | `work-graph` | *workgraph* |
| app-graph | 0.2.0 | `app-graph` | *appgraph* |
| dd-llm | 0.2.0 | `dd-llm` |  |

All four were reinstalled editable after the version change, so `pip check` should say nothing about them. If graflang still shows 0.2.1, or app-graph still asks for `graflang<0.3`, run `pip install -e graflang -e app-graph -e work-graph --no-deps`. app-graph and work-graph now require `graflang>=0.3.0`.

```bash
pip check                      # no "requires graflang>=0.3.0, but you have 0.2.1" lines
which graf appgraph agr workgraph zinet
docker info --format '{{.OperatingSystem}}'                  # Docker Desktop
docker image ls | grep appgraph-verify                       # appgraph-verify:py3.12 (and a node image)
git -C graflang status --short; git -C work-graph status --short; git -C app-graph status --short; git -C zinet status --short
```

All four trees should be clean (the refactor's work is committed). If graflang shows modified
`cookbook_pocketflow*/…/output/*`, `*.db` or `*_trace.md` files, a test run rewrote them; restore them with
`git -C graflang checkout -- cookbook_pocketflow cookbook_pocketflow_v2`.

`graph-code` must still be untouched: `git -C graph-code status --short` is empty, and its last commit is unchanged.

---

## 1. zinet (10 min)

zinet was not changed by the refactor. These checks guard what graflang, work-graph and app-graph use:
`zinet.algorithms` (build order, acyclic, reducible), `zinet.vis` (every drawing), `zinet.roundtrip` and `zinet.formats`.

```bash
cd ~/projects/digital-duck/zinet
python -m pytest -q                                   # expected: 202 passed
zinet --help
```

Regression checks through the users (these are the ones that matter):

```bash
cd ~/projects/digital-duck/app-graph
python -m pytest -q -p no:spark tests/test_zinet_algorithms.py   # app-graph's pin on zinet's behaviour: all pass
appgraph order apps/todo/blueprint/backend.graph.yaml             # 0 db_connection, 1 requirements, 2 data_schema, 3 orm_model, ...
graf vis src/appgraph/recipes/build_component/build_component.graph.yaml -o /tmp/bc.html   # opens; LOOPs drawn as boxes
```

- [x] zinet suite passes (202)
- [x] build order of the todo backend is unchanged (as above)
- [x] `graf vis` draws a recipe

---

## 2. graflang 0.3.0 (40 min)

### 2.1 What changed

Six items, collected from app-graph's port and the Sonnet review, all done in this release:

| # | Change | Where |
|---|---|---|
| 1 | `graphlang.recipes`: `Recipe` (load once, run many), `run_recipe`, `RecipeRun` (`outputs`, `exit`, `error_code`, `llm_calls`), `RecipeError`, `passthrough=` | `graphlang/recipes.py` |
| 2 | a SOLVE command's leading `python3`/`python` is the interpreter running the graph (not under `container:`) | `grafr/solver.py::own_python` |
| 3 | prompts filled in one pass: a value containing `{{in_x}}` is not expanded again | `grafr/nodes/generate.py::fill_prompt` |
| 4 | `max_tokens:` on a GENERATE; a run-wide default through `DefaultsLLM` | `generate.py`, `adapters.py` |
| 5 | adapter options: `make_llm(adapter, model, timeout=900)` | `adapters.py` |
| 6 | the error exit a run ended at: `runtime.exit`, `summary()["exit"]`, `["error_code"]` | `grafr/runtime.py` |

### 2.2 Automated

```bash
cd ~/projects/digital-duck/graflang
python -m pytest -q tests/test_recipes_api.py         # the new API: 15 passed
python -m pytest -q                                   # the whole suite (offline; about 19 min)
git status --short                                    # then restore the rewritten cookbook outputs (see Setup)
```

Expected: **GL_COUNT, no failures**. Before the follow-up of 2026-11-22 there were 3 failures for folders that did not exist; `cookbook_v2/stock_copy` is now named `cookbook_v2/stock_report` in the tests (its original is still `cookbook/stock_copy`), and the `cookbook_v2/pocketflow` port was dropped (the three graphs stay in `cookbook/pocketflow/`). Any *other* failure is a regression;
the likeliest suspects are items 2 and 3 (a cookbook recipe whose prompt relied on a value being expanded twice,
or a command that needed a different `python3`).

### 2.3 By hand

**One-pass prompt filling (item 3).** Make a two-step probe:

```bash
mkdir -p /tmp/gl-probe && cd /tmp/gl-probe
printf 'A=[{{in_a}}] B=[{{in_b}}]\n' > p.md
cat > probe.graph.yaml <<'EOF'
version: "1.0-graph"
workflow:
  name: probe
  description: probe
  inputs: [{name: a, type: TEXT}, {name: b, type: TEXT}]
  outputs: [{name: r, type: TEXT}]
resources: {prompts: {p: ./p.md}}
steps:
  - g:    {generate: prompts.p, in: {a: $in.a, b: $in.b}, out: r, max_tokens: 50}
  - done: {output: {r: g.r}}
EOF
graf validate probe.graph.yaml                         # valid (max_tokens is accepted)
graf run probe.graph.yaml --adapter mock --param 'a=has {{in_b}}' --param 'b=two' --no-output --no-log
```

Expected: `Output: {'r': '[Mock LLM response from mock for prompt: A=[has {{in_b}}] B=[two]...]'}` (the mock echoes the prompt; the line may wrap). With 0.2.1 it showed `A=[has two] B=[two]`.

**`python3` (item 2).** With another Python first on PATH:

```bash
PATH=/usr/bin:$PATH python - <<'EOF'
import sys, json, tempfile, pathlib, yaml
from graphlang.recipes import run_recipe
d = pathlib.Path(tempfile.mkdtemp())
(d / "w.graph.yaml").write_text(yaml.safe_dump({"version": "1.0-graph",
  "workflow": {"name": "w", "description": "w", "inputs": [], "outputs": [{"name": "r", "type": "TEXT"}]},
  "steps": [{"s": {"node": "SOLVE", "ports": ["trigger", "complete", "out_r"], "out": "r", "backend": "subprocess", "out_type": "JSON",
                   "command": ["python3", "-c", "import json,sys; print(json.dumps({'exe': sys.executable}))"]}},
            {"done": {"output": "s"}}]}))
print(run_recipe(d / "w.graph.yaml", {}).outputs["r"]["exe"] == sys.executable)
EOF
```

Expected: `True`.

**Exits and errors (items 1 and 6), on a real recipe.** app-graph's `compile_blueprint` refuses a folder outside home:

```bash
cd ~/projects/digital-duck/app-graph
python -c "
from appgraph.run import run_recipe
r = run_recipe('compile_blueprint', {'mode': 'intent', 'intent': 'x', 'output_path': '/etc/x.graph.yaml'}, llm='mock', log_dir=None)
print(r.exit, r.error_code, r.llm_calls, r.outputs['result'][:40])"
```

Expected: `refused E_BUILD_REFUSED 0 refused by policies/compile.cedar: the ou`.

**Regression: `graf run` and the app.**

```bash
cd ~/projects/digital-duck/graflang
graf run cookbook/self_refine/self_refine.graph.yaml --adapter mock      # runs to the end, writes its output folder
graf vis --edit        # the app opens; Browse lists recipes; open one, Edit shows it; close
```

- [ ] `test_recipes_api.py` 15 passed
- [ ] full suite: only the known pocketflow failure
- [ ] probe: placeholder in a value is not expanded
- [ ] probe: `python3` is this interpreter
- [ ] `exit`/`error_code` reported for an error exit
- [ ] `graf run` (mock) and `graf vis --edit` work as before
- [ ] **[LLM]** `graf run cookbook/self_refine/self_refine.graph.yaml --llm claude_cli:claude-haiku-5-5` works (one real run, a few calls)
- [ ] **[LLM]** the renamed port runs: `graf run cookbook_v2/stock_report/stock_report.graph.yaml --bind cookbook_v2/cap.bind.yaml --llm claude_cli:claude-haiku-5-5 --param tickers=AAPL --param days=5` (2 calls; the fetch needs the network)

---

## 3. work-graph (30 min)

### 3.1 What changed

`workgraph.recipes.Recipe` (used by `llm_items` and `workgraph ask`) now wraps `graphlang.recipes.Recipe`. Its
interface is the same (`Recipe(name, prompt=)`, `.fingerprint`, `.run(inputs, backend=..., max_llm_calls=...)`);
it no longer patches `python3` itself; `Recipe.graph` replaces the private `_graph`; a capped run raises
`graphlang.recipes.RecipeError` (a `RuntimeError`, as before); `BackendLimitError` passes through unchanged.

### 3.2 Automated

```bash
cd ~/projects/digital-duck/work-graph
python -m pytest -q                       # expected: 125 passed
python -m pytest -q tests/test_recipes.py tests/test_ask.py    # 17 passed: prompt byte for byte, placeholder not expanded, cap, limit passthrough, custom recipe/prompt
```

### 3.3 By hand

```bash
workgraph utils doctor                    # every line [ok]
workgraph utils areas                     # sdlc, research, publishing
workgraph utils validate-pack sdlc research publishing     # no errors (recipe and prompt names checked)
workgraph build                           # the default workspace builds (no model calls without --semantic)
workgraph status
workgraph search "recipe"                 # hits
```

**Regression: recipe path = Python path** for `llm_items` **[LLM]**. Use one small project (zinet: a handful of docs,
so a handful of calls); the reply cache is keyed on the recipe's fingerprint, so the first semantic run extracts afresh:

```bash
Z=~/projects/digital-duck/zinet
WORKGRAPH_CACHE=/tmp/wg-cache-recipe workgraph open --semantic --src $Z -o /tmp/wg-out-recipe > /tmp/items-recipe.txt
WORKGRAPH_CACHE=/tmp/wg-cache-python WORKGRAPH_LLM_ITEMS=python workgraph open --semantic --src $Z -o /tmp/wg-out-python > /tmp/items-python.txt
diff /tmp/items-recipe.txt /tmp/items-python.txt
WORKGRAPH_CACHE=/tmp/wg-cache-recipe workgraph open --semantic --src $Z -o /tmp/wg-out-recipe | head -3    # again: from the cache
```

Expected: the same items. The two runs make separate model calls, so a summary may be worded differently; the titles,
kinds and stages should agree, and any difference should be explainable by the model's replies, not by the prompt
(`tests/test_recipes.py` checks the two prompts are byte for byte the same). The third run prints no `LLM n/m` progress lines.

**`workgraph ask` [LLM]** (at most 3 calls):

```bash
workgraph ask "which requirements have no test?"
```

Expected: a report ending in `[grounded]` with node ids that `workgraph show <id>` finds, or `[ungrounded]`/`[empty]`
with the reason. Try `--max-calls 1`: it stops with "the question was not answered: … max_llm_calls" (exit non-zero).

- [ ] suite 125 passed
- [ ] doctor ok, build, status, search work
- [ ] **[LLM]** recipe and Python paths give the same items; rerun hits the cache
- [ ] **[LLM]** `ask` grounded (or a correct ungrounded/empty), `--max-calls 1` stops cleanly

---

## 4. app-graph (60–90 min)

### 4.1 What changed (from graph-code 0.1.1)

The three LLM workflows are GraphLang recipes (`src/appgraph/recipes/`: `build_component`, `build_app`,
`compile_blueprint`), run through `appgraph/run.py` over `graphlang.recipes`; `spl3`/`spl-llm` are gone; tests run in Docker;
`extract --llm` resumes from a checkpoint; writes are policy-guarded and confined to the output folder. Since the last
review two more fixes: a component built on its own now writes its settings config (`app/config.py`), which graph-code
wrote only for a whole app (so `appgraph build apps/todo/blueprint/backend.graph.yaml` failed its tests in both tools);
and the recipes' GENERATE inputs list free text last.

### 4.2 Automated

```bash
cd ~/projects/digital-duck/app-graph
python -m pytest -q -p no:spark          # expected: 173 passed (about 2 min; the Docker ones skip without the image)
appgraph validate-all apps                # expected: 47 passed, 0 failed, 10 warning(s)
for r in build_component build_app compile_blueprint; do graf validate src/appgraph/recipes/$r/$r.graph.yaml; done   # all valid
```

The recipe tests use a scripted model, offline: parity with graph-code (todo backend byte for byte in 7 calls, 0 from
the cache; todo frontend; the whole todo app with integration), repair, failure exits, refusal, `extract --llm` on fief's
real inputs, and a crashed `extract --llm` resuming.

### 4.3 Every command, offline

```bash
appgraph --help; agr --help                                       # same CLI
appgraph validate apps/todo/blueprint/main.graph.yaml             # system + imports: OK
appgraph order apps/todo/blueprint/backend.graph.yaml
appgraph report apps/todo/blueprint/main.graph.yaml               # todo_app, integrated, capstone manage_todo_list
appgraph prettify apps/todo/blueprint                             # dry run: lists what it would change (do not --write)
appgraph drift apps/todo/blueprint/backend.graph.yaml apps/fief/blueprint/backend.graph.yaml \
    --dims structural,interface,behavior,implementation         # structural 0.68, interface 1.0, behavior 1.0, implementation 0.0
appgraph new-app verify_app 8100 5200 --apps-dir /tmp/agv-apps   # scaffold; then: appgraph validate /tmp/agv-apps/verify_app/blueprint/main.graph.yaml (TODO warnings expected)
appgraph extract --repo-path ~/projects/digital-duck/graph-code --app-name gc_probe --output-dir ~/app-graph/verify/gc_probe   # AST only, no LLM
appgraph tools suggest-graph-clusters apps/todo/blueprint/backend.graph.yaml
appgraph ide --apps-root apps             # browser opens at :8881; pick todo; the graph draws; Ctrl-C stops both servers
appgraph tools clean-port 8880 8881
```

### 4.4 Regression against graph-code's own output **[Docker]**, no model calls

graph-code's per-node cache is read as is. A component rebuilt from it must give graph-code's files and pass:

```bash
V=~/app-graph/verify; rm -rf $V/todo_backend; mkdir -p $V/todo_backend/app
F=tests/fixtures/todo_backend          # graph-code's generated backend, with its .spl_cache
cp -r $F/.spl_cache $F/tests $V/todo_backend/; cp $F/app/__init__.py $V/todo_backend/app/
appgraph build apps/todo/blueprint/backend.graph.yaml --output-dir $V/todo_backend --max-llm-calls 0
diff -r $F/app $V/todo_backend/app && echo IDENTICAL
```

Expected: every node `(cached)`, `tests: passed: 22 passed, 0 failed`, `model calls: 0`, then `IDENTICAL`.
(Verified once on 2026-11-22 after the settings-config fix; before it, the tests failed on `No module named 'app.config'`.)

Optional, same idea with graph-code itself (it is in conda base: `/home/gongai/anaconda3/bin/grafcode`): build the same
blueprint into another folder with `grafcode build ... --output-dir`, then `diff -r` the two `app/` folders.

### 4.5 Real model runs **[LLM] [Docker]**

Each is capped; together about 30–60 calls.

1. **A small component, fresh** (≈ 4–12 calls, ~30 s):
   ```bash
   appgraph build apps/jwt_provider/blueprint/component.graph.yaml --output-dir ~/app-graph/verify/jwt --no-cache --max-llm-calls 12
   ```
   Expected: `tests: passed: 10 passed` (or a repair, then passed), a summary path under `~/app-graph/logs/`.
   Rerun without `--no-cache`: `model calls: 0`.

2. **A whole app** (todo: backend + frontend + integration; ≈ 20–30 calls, a few minutes):
   ```bash
   cp -r apps/todo ~/app-graph/verify/todo_app      # blueprints only; the build writes code beside them
   appgraph build ~/app-graph/verify/todo_app/blueprint/main.graph.yaml --max-llm-calls 40
   ```
   Expected: each component `passed`, integration `- PASS <application>` lines, `README.md` written in the app folder, status `passed`.
   A frontend needs its `package-lock.json` (seeded by the build); the first run builds an `appgraph-verify-node:<hash>` image (needs the network once).

3. **`extract --llm`, and resume** (≈ 5 calls without repairs):
   ```bash
   appgraph extract --repo-url https://github.com/fief-dev/fief --app-name fief_v --output-dir ~/app-graph/verify/fief_v \
       --llm claude_cli:claude-sonnet-5-5 --max-llm-calls 20
   ```
   Expected: `shape: INTEGRATED` (or SINGLE), `blueprint/{backend,frontend,main}.graph.yaml`, and
   `appgraph validate ~/app-graph/verify/fief_v/blueprint/main.graph.yaml` passes. Compare with `apps/fief/blueprint/` (by eye, or with `appgraph drift`).
   **Resume:** run it again with `--skip-cache`, press Ctrl-C after the "Classify" step is logged, then run the same command
   without `--skip-cache`: it prints `resuming the semantic pass from …checkpoint.json` and does not classify again.
   A third run prints "LLM pass cache hit" and makes no calls.

4. **Drift with the judge** (1 call):
   ```bash
   appgraph drift apps/fief/blueprint/backend.graph.yaml ~/app-graph/verify/fief_v/blueprint/backend.graph.yaml --llm claude_cli:claude-sonnet-5-5
   ```
   Expected: an `intent` line with a number in [0, 1], plus the four graph-diff lines.

5. **Refusals** (0 calls): `appgraph build apps/jwt_provider/blueprint/component.graph.yaml --output-dir /etc/agv` ends `refused`
   with no model call.

### 4.6 Safety

- A node file path that leaves the output folder is refused: `python -m pytest -q -p no:spark tests/test_build_lib.py -k inside`.
- The test containers have no network: during step 4.5.1, `docker ps` shows the `appgraph-test-…`/`graf-…` container with `--network none`
  (`docker inspect <id> --format '{{.HostConfig.NetworkMode}}'` → `none`).
- Nothing is written beside the recipes: after the runs, `git -C ~/projects/digital-duck/app-graph status --short src/` is empty.

- [ ] suite 173 passed; validate-all 47/0; recipes valid
- [ ] every offline command in 4.3 works
- [ ] **[Docker]** cache rebuild IDENTICAL, 22 passed, 0 calls
- [ ] **[LLM]** jwt_provider builds and passes; rerun 0 calls
- [ ] **[LLM]** todo app builds, integrates, README written
- [ ] **[LLM]** extract fief: valid blueprints; resume works; marker hit on the third run
- [ ] **[LLM]** drift intent score
- [ ] refusal makes no call; containers have no network; no files beside the recipes

---

## 5. Cross-repo checks (10 min)

- **One helper, two users.** `grep -n "graphlang.recipes" app-graph/src/appgraph/run.py work-graph/src/workgraph/recipes/__init__.py` shows both import it, and neither still has its own `python3` patch (`grep -rn "sys.executable" app-graph/src/appgraph/run.py work-graph/src/workgraph/recipes/` finds nothing).
- **Pins.** `grep -n graflang app-graph/pyproject.toml work-graph/pyproject.toml` → `>=0.3.0` in both.
- **Docs agree.** graflang `docs/GUIDE/USER-GUIDE.md` has "From Python: `graphlang.recipes`"; graflang `CHANGELOG.md` has 0.3.0; app-graph `docs/DEV/graflang-refactor.md` marks the six upstream items done; work-graph's `docs/DEV/graflang-refactor.md` has "After Phase 5: the shared helper".
- **Python floor.** All of graflang, app-graph and work-graph say `requires-python >=3.11` (work-graph's was 3.10 until 2026-11-22); `workgraph utils doctor` shows `[!!] python` on an older one.

## 6. Clean-up afterwards

```bash
rm -rf ~/app-graph/verify /tmp/gl-probe /tmp/agv-apps /tmp/wg-cache-* /tmp/wg-out-*
docker image rm appgraph-verify-node:probe        # left from a probe during the build
git -C ~/projects/digital-duck/graflang checkout -- cookbook_pocketflow cookbook_pocketflow_v2   # if a test run rewrote them
```

## Checklist summary

| Repo | Automated | By hand | LLM | Notes |
|---|---|---|---|---|
| zinet | ☐ 202 | ☐ | — | |
| graflang | ☐ api 15, full suite clean | ☐ probes | ☐ self_refine, stock_report | |
| work-graph | ☐ 125 | ☐ | ☐ items parity, ask | |
| app-graph | ☐ 173, validate-all | ☐ commands, cache rebuild | ☐ jwt, todo app, fief, drift | |
| cross-repo | | ☐ | | |

## Numbers recorded at hand-over (2026-11-22)

- zinet: 202 passed.
- graflang `tests/test_recipes_api.py`: 15 passed. graflang full suite: GL_COUNT (before the stock_report/pocketflow follow-up: 1956 passed, 3 failed on folders that did not exist).
- work-graph: 125 passed.
- app-graph: 173 passed; `validate-all apps`: 47 passed, 0 failed, 10 warnings; todo backend from graph-code's cache: 22 passed, 0 calls, identical.
