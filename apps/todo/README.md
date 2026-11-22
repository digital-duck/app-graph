# Todo App

A full-stack task management application built with a Vue.js frontend and a FastAPI backend persisted to SQLite. The app lets users create, view, toggle, and delete todo items through a reactive single-page interface — no account or authentication required. It is designed as a reference implementation of an `integrated` graph-code domain, assembling independently deployable backend and frontend software components into one working product.

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

**1. Build** — generate and install both components from the graph:

```bash
spl3 run spl/build_app.spl \
    --tools spl/tools.py \
    -p system_yaml=apps/todo/blueprint/main.graph.yaml \
    --llm claude_cli
```

To generate a fresh copy of the app into a new directory instead of overwriting
`apps/todo/backend`/`apps/todo/frontend` in place, add `-p output_dir=...`:

```bash
mkdir -p logs/console
spl3 run spl/build_app.spl \
    --tools spl/tools.py \
    -p system_yaml=apps/todo/blueprint/main.graph.yaml \
    -p output_dir=apps/todo-v6 \
    --llm claude_cli \
    2>&1 | tee "logs/console/build_app-$(date +%Y-%m-%d-%H-%M-%S).md"
```

The `tee` keeps the console output live while also capturing it to a
timestamped file under `logs/console/` — useful since a failed build's real
error (e.g. a `pytest`/SQLAlchemy traceback) often scrolls past the terminal
buffer before you can read it, and `spl3`'s own log (path printed as `Log:`
at the end of the run) captures the workflow trace but not the raw stdout.

Each component is then written to `{output_dir}/{component_id}/` — i.e.
`apps/todo-v6/backend/` and `apps/todo-v6/frontend/` for the command above —
leaving the existing `apps/todo/backend`/`apps/todo/frontend` untouched.

See [docs/DEV/BUILD/README.md](../../docs/DEV/BUILD/README.md) §12.1 for full build options and §12.4 for `--output_dir` usage.

**Building to a redirected `-p output_dir=...` location** (e.g. to generate a fresh copy without
touching `apps/todo/backend`/`apps/todo/frontend`): the build seeds each component's pre-authored
scaffold (`tests/`, and for the frontend also `package.json`/`package-lock.json`/`vite.config.ts`/
`tsconfig.json`/`index.html`/`.env`) into the new location automatically, but **deliberately does
not copy `node_modules/`** (copying a dependency tree risks silent drift from `package.json` —
reinstalling is safer). If the frontend build halts with `vitest: not found` (exit 127), run
`npm install` by hand in the redirected frontend directory once, then re-run the same
`spl3 run spl/build_app.spl ...` command — it picks up where it left off (the backend and any
already-passing frontend nodes are cached, so only the remaining work re-runs). See
[docs/DEV/BUILD/README.md](../../docs/DEV/BUILD/README.md) §12.4 for the original incident this
was found and fixed from.

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