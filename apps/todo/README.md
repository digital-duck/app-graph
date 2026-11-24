# Todo App

A full-stack task management application built with a Vue.js frontend and a FastAPI backend persisted to SQLite. The app lets users create, view, toggle, and delete todo items through a reactive single-page interface — no account or authentication required. It is designed as a reference implementation of an `integrated` app-graph blueprint, assembling independently deployable backend and frontend software components into one working product.

## Status

| Application | Result |
|---|---|
| create_todo | PASS (10.7 s) |
| list_todos | FAIL — `SyntaxError: unterminated string literal` in generated acceptance test (`test_acceptance_list_todos.py`, line 33) |
| toggle_todo | PASS (9.8 s) |
| delete_todo | PASS (11.8 s) |

## Architecture

The Vue.js frontend (port **5173**) communicates with the FastAPI backend (port **8000**) over REST, with CORS enabled on the backend; see [backend/README.md](backend/README.md) and [frontend/README.md](frontend/README.md) for each component's own setup, run, and test instructions.

## Running the full system

**1. Build** — generate and test both components from the blueprint with `appgraph build` (the `build_app` recipe: every component in order, stopping at the first that fails, then the acceptance tests against the live backend). Python tests run in the `appgraph-verify:py3.12` Docker image and Vue tests in a per-lockfile node image, both without network; see the build notes in [CLAUDE.md](../../CLAUDE.md).

```bash
appgraph build apps/todo/blueprint/main.graph.yaml --llm claude_cli
```

To generate a fresh copy of the app into a new directory instead of overwriting
`apps/todo/backend`/`apps/todo/frontend` in place, add `--output-dir`:

```bash
appgraph build apps/todo/blueprint/main.graph.yaml \
    --output-dir apps/todo-v6 \
    --llm claude_cli \
    2>&1 | tee "build-$(date +%Y-%m-%d-%H-%M-%S).log"
```

The `tee` keeps the console output live while also capturing it to a timestamped
file — useful since a failed build's real error (e.g. a `pytest`/SQLAlchemy
traceback) often scrolls past the terminal buffer before you can read it. The run's
own log (path printed as `[build] log:` at the end) captures the recipe trace but not
the raw stdout.

Each component is written to `{output_dir}/{component_id}/` — i.e.
`apps/todo-v6/backend/` and `apps/todo-v6/frontend/` for the command above —
leaving the existing `apps/todo/backend`/`apps/todo/frontend` untouched. Useful flags:
`--max-llm-calls N` (cap on model calls), `--max-test-attempts N` (test runs, each
failure gets one repair; default 3), `--no-cache` (regenerate every node instead of
reusing `<output>/.agr_cache`), `--tech-profile` (single component only). Run
`appgraph build -h` for all of them. To build one component, pass its graph, e.g.
`appgraph build apps/todo/blueprint/backend.graph.yaml`.

**Building to a redirected `--output-dir`** (e.g. to generate a fresh copy without
touching `apps/todo/backend`/`apps/todo/frontend`): the build seeds each component's pre-authored
scaffold (`tests/`, and for the frontend also `package.json`/`package-lock.json`/`vite.config.ts`/
`tsconfig.json`/`index.html`/`.env`) into the new location automatically, but **deliberately does
not copy `node_modules/`** (copying a dependency tree risks silent drift from `package.json` —
reinstalling is safer). If the frontend build halts with `vitest: not found` (exit 127), run
`npm install` by hand in the redirected frontend directory once, then re-run the same
`appgraph build ...` command — it picks up where it left off (the backend and any
already-passing frontend nodes are cached, so only the remaining work re-runs).

You can check the blueprints before spending model calls: `appgraph validate apps/todo/blueprint/main.graph.yaml`
(the system and every import) and `appgraph order apps/todo/blueprint/backend.graph.yaml` (the order nodes are generated in).

**2. Start the backend:**

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

**3. Start the frontend** (separate terminal):

```bash
cd frontend
npm run dev
```

The app is then available at <http://localhost:5173>.

## Applications

- **create_todo** — add a new named task to the list
- **list_todos** — retrieve and display all current todo items
- **toggle_todo** — mark a todo as complete or revert it to incomplete
- **delete_todo** — permanently remove a todo item from the list
- **manage_todo_list** — full lifecycle management: create, view, toggle, and delete todos from a single unified interface