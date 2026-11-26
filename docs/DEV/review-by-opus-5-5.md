# app-graph code review (Opus 5.5)

Date: 2026-11-25 · Commit reviewed: `d931acf` (main, clean) · Scope: `src/appgraph/` (6,526 lines), the Graph IDE API, the tests.

**How I checked it.**

- I read the Graph IDE API (`app.py`, `graph_writer.py`, `graph_discovery.py`, `routers/*`), the CLI's `extract` clone,
  `ide` and `tools clean-port`, and what imports `appgraph.build`.
- `pytest` (the `appgraph-verify:py3.12` image is present): collection stops with **4 errors**. With `--continue-on-collection-errors`:
  **116 passed, 1 failed**. Both come from B1.
- `agr validate apps`: 45 / 45 files pass.
- Every bug marked **confirmed** was reproduced on this machine. The IDE findings were made by reading, because FastAPI is not
  installed in the `graf` environment, so I could not start the API.

## 1. Summary

The schema side is solid:

- `loader` and `graph_lib` are pure functions;
- the form-space algorithms are delegated to zinet, with a test that pins their behaviour;
- the recipes follow the GraphLang rules that CLAUDE.md lists.

But **the repository cannot build apps**. The `appgraph.build` package, the deterministic half of every build recipe, was never
committed: `.gitignore`'s `build/` rule hides it (B1). After that, the Graph IDE's API accepts writes and LLM-billed builds from any
web page (B2), and `tools clean-port` kills clients as well as the server (B3).

## 2. Strengths

| Area | What is good |
|---|---|
| Schema library | `graph_lib` is 22 pure functions over a `GraphDomain`; no I/O, no LLM. Errors before any model call are `ToolFailed`, as the recipes need. |
| zinet, not a copy | `acyclic`, `reducible`, `build_order` and the rest go through `zinet.algorithms`; `tests/test_zinet_algorithms.py` pins the order of ties, optional edges and the two-radical rule. |
| Safe IDE edits | `graph_writer.update_node` changes only prose fields, round-trips with ruamel, and refuses a write unless a trial copy (in the same folder, so settings resolve) still passes `validate_full` (`graph_writer.py:131-158`). The apps root is confined in `_resolve_root` (`routers/graphs.py:69-75`). |
| Sandboxed tests | Generated code is tested in the `appgraph-verify` container, and Vue in a per-lockfile node image, both with no network. |
| Recipes | Prompts are the `.spl` bodies with only parameters renamed (`scripts/spl_prompts.py`); `graflang.errors.yaml` agreement between parts is tested. |
| Drift report | Five components, ordered from intent down to implementation; four are free graph diffs, and only `intent` needs a judge, which is injected. |

## 3. Bugs

### B1 (Critical, confirmed): `appgraph.build` is missing from the repository

Only `src/appgraph/build/tech_profiles.py` is tracked: it was force-added in `9d0bce4`. `.gitignore:11` (`build/`, the
setuptools default) ignores everything else under `src/appgraph/build/`. CLAUDE.md describes those modules: `blueprint`, `cache`,
`files`, `verify`, `compile`, `text`, `server`, `node_image`, `steps.py` and `tool.py`. **None exists in git, in this working tree, or anywhere
else on this machine** (I searched for the files and for `.pyc` remains). The tree's identical mtimes (2026-11-22 19:27:49) suggest a fresh
clone, so they likely live only in the checkout where they were written.

```
$ python -c "import appgraph.builder"
ImportError: cannot import name 'blueprint' from 'appgraph.build' (unknown location)
$ pytest
ERROR tests/test_build_app.py, test_build_component.py, test_build_lib.py, test_compile_blueprint.py   (4 errors during collection)
FAILED tests/test_run_and_judge.py::TestRunRecipe::test_runs_a_recipe_with_a_scripted_model   (the SOLVE step `python3 -I -m appgraph.build.tool` exits non-zero)
```

So `agr build` and `agr extract --llm` (both recipes call `appgraph.build.tool`), and the IDE's Build button, cannot run from a clone.

**Fix:**
1. Find the checkout that has the files, and `git add -f src/appgraph/build/`.
2. Change the ignore rule to `/build/`, so only the top-level setuptools folder is ignored.
3. Add a test that imports every module CLAUDE.md names, so a missing file fails as one clear error.

### B2 (High, by reading): the Graph IDE API accepts writes and builds from any web page

`api/app.py:8-13` installs `CORSMiddleware(allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])`, and nothing checks
`Host` or `Origin`. uvicorn binds 127.0.0.1, but the user's browser is on that machine. Any page they visit can therefore send the
preflighted JSON requests, and read the answers:

- `PUT /api/settings/apps-root`: point the root at **any** existing folder (`routers/settings.py:34-43`, no confinement), which is
  also saved to `~/app-graph/.ide_settings.json` for later launches;
- `PATCH /api/graphs/nodes/{id}`: rewrite the prose of any blueprint under that root. That prose is what the build recipe prompts
  with, so this is a prompt injection into the next build;
- `POST /api/build`: start an `appgraph build`, which spends LLM calls and writes code to any `output_dir` (an absolute path is used
  as is, `routers/build.py:23-24`);
- `POST /api/drift`: run `appgraph drift` on any two paths, with any `--llm`.

A DNS-rebinding page gets the same reach, even without CORS. This is the same exposure book-graph's `serve` closes: bind 127.0.0.1,
check `Host`, and require a same-origin `Origin` on every `/api` call.

**Fix:** keep the Vite dev server's proxy (`vite.config.js`), which already makes the API same-origin. Then:
- drop the CORS middleware, or list only `http://localhost:<dev-port>`;
- reject a `Host` other than `localhost`/`127.0.0.1:<port>`;
- confine `apps-root` and `output_dir` to the workspace (`~/app-graph`), unless the CLI's `--apps-root` says otherwise.

### B3 (Medium, confirmed): `tools clean-port` kills clients of the port, not only its server

`clean-port` finds PIDs with `lsof -t -i :PORT` (`cli.py:1377`), which lists every process with a socket on that port, both ends.
Measured with a listener and one connected client:

```
server pid 1560233, client pid 1560234
lsof -t -i :PORT -> ['1560233', '1560234']    | with -sTCP:LISTEN -> ['1560233']
```

It then sends SIGTERM to each, and SIGKILL to any survivors. So running `agr tools clean-port 8880` while a browser tab has the IDE
open kills the browser (or the Vite dev server that proxies to it).

**Fix:** `lsof -t -iTCP:PORT -sTCP:LISTEN`. It is one flag; add a test with a connected client.

### B4 (Low): `git clone` takes the URL without a `--` separator

`extract --repo-url` runs `git clone --depth 1 <url> <dir>` (`cli.py:955`). A value that starts with `-` is parsed as an option
(`--upload-pack=…` runs a command). The URL is typed by the user, so this matters only when a URL is pasted from elsewhere, or when
the IDE someday calls `extract`. **Fix:** `["git", "clone", "--depth", "1", "--", repo_url, str(clone_dir)]`, and reject a URL that starts with `-`.

## 4. Weaknesses and smaller notes

- **`routers/drift.py` passes user strings straight to the CLI.** `graph_a` and `graph_b` cannot be confined, and a value like `--llm`
  becomes an option. Resolve both under the apps root, as `graphs` does.
- **The IDE's build state is global** (`routers/build.py:13`): one build at a time, kept in memory, and lost on `--reload`. That is
  fine for a single user, but a reload during a build leaves an orphaned `appgraph build` process.
- **`graph_discovery` silently skips a missing import** (`graph_discovery.py:108`). The viewer then shows a system without that
  component and no message; a `files` entry with `missing: true` would say so.
- **`cli.py` is 1,983 lines.** Splitting it by command group (`extract`, `build`, `ide`, `tools`) would make reviews like this one
  cheaper. That is not a bug.

## 5. Gaps

- **B1 blocks a fresh clone.** Until the build package is committed, the build tests are not merely skipped: they fail to collect.
- **The IDE API has no tests.** A `TestClient` test for the cross-origin refusal (B2), and for `_resolve_root` refusing `..`, would
  hold the line.
- **FastAPI is not installed in `graf`**, so the IDE cannot start there. The graph-ide README's `requirements.txt` step is the only
  place it is mentioned; an `[ide]` extra in `pyproject.toml` would make it one install.

## 6. Suggested order

1. **B1:** recover and commit `src/appgraph/build/`, then fix the ignore rule.
2. **B2:** same-origin and Host checks, and confine the apps root.
3. **B3:** one flag.
4. **B4**, and the drift path confinement.
