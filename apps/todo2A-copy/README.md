# todo2A

Extracted from [`Vue3FastAPI-To-Do`](https://github.com/notarious2/Vue3FastAPI-To-Do)
(simplified to SQLite, username/password-only auth), regenerated end-to-end
through `grafcode build` against `blueprint/main.graph.yaml`. See
`EXTRACTION.md` for extraction details and `../README-new-apps.md` for the
original extract/build commands.

Ports: backend `8020`, frontend `5190` (`blueprint/settings.yaml`).

## Status (2026-08-16)

| Component | Generated | Tests | Runs |
|---|---|---|---|
| Backend  | ✅ 13/13 nodes | ✅ 37/37 pytest | ✅ `uvicorn` starts, real endpoints |
| Frontend | ✅ 13/13 nodes | ✅ 1/1 vitest (scaffold placeholder only, not app coverage) | ❌ `npm run build`/`dev` fails — see Known gaps |

The frontend generation pipeline and its Stage-3 test gate both pass, but
the gate only runs the `npm create vue@latest` scaffold's own placeholder
test (`HelloWorld.spec.ts`) — it doesn't exercise the app's real components,
so a green gate here does not mean the app builds. It doesn't, currently
(see Known gaps below).

## Backend — setup & test

```bash
cd apps/todo2A/backend
conda activate spl123   # or any env with graph-code's [dev] extras installed

pip install -r <(python -c "import tomllib,sys; d=tomllib.load(open('../../../pyproject.toml','rb')); print('\n'.join(d['project']['optional-dependencies']['dev']))") 2>/dev/null || true
# simplest in practice: this repo's own `pip install -e ".[dev]"` at the repo
# root already gives you fastapi/sqlalchemy/pytest/httpx/etc.

python -m pytest -q
# 37 passed
```

Run the API:

```bash
cd apps/todo2A/backend
uvicorn app.main_app:app --reload --port 8020
```

Routes (see `app/*_router.py`): `POST /user/...` (auth), `/users/...` (user
CRUD), `/task/...` (task CRUD) — all under `http://localhost:8020`.
CORS is currently hardcoded to allow `http://localhost:5190`
(`app/main_app.py`) — the one frontend origin, not configurable via env yet.

Uses SQLite (`app/config.py`'s `DATABASE_URL` from `.env`); tests use their
own in-memory DB via `tests/conftest.py`'s `reset_db` fixture, independent
of whatever `.env` points the dev server at.

## Frontend — setup & test

```bash
# Node must be >= 22.18.0 (the vue_typescript scaffold's package.json
# engines field) — see "Node version" note in ../README-new-apps.md if
# `node --version` shows something older.
cd apps/todo2A/frontend
npm install
npm test
# 1 passed — the scaffold's own placeholder test, not real app coverage
```

`npm run dev` / `npm run build` do **not** currently work — see Known gaps.

## Known gaps (frontend only — not yet hand-fixed)

Generation produced real, individually-valid node files, but the app isn't
wired together yet:

1. **Missing npm dependencies.** `src/main.ts` and `src/components/TaskList.vue`
   import `vuetify`, `@mdi/font`, `vuedraggable`, and `@vuepic/vue-datepicker`,
   none of which are in `package.json` (the `npm create vue@latest` scaffold
   has no way to know about them). Add:
   ```bash
   npm install vuetify @mdi/font vuedraggable @vuepic/vue-datepicker
   ```
2. **Two files never got generated.** `layout_components`'s own spec
   (`blueprint/frontend.graph.yaml`) describes three output files —
   `Layout.vue`, `TheSpinner.vue`, `PostIt.vue` — but `tech_profiles.py`'s
   `NODE_FILES["todo2A"]` maps that node to a single path
   (`src/components/Layout.vue`), so the other two were dropped.
   `TaskList.vue` imports both (`./TheSpinner.vue`, `./PostIt.vue`) and will
   fail to resolve until they're authored (either add `NODE_FILES` entries
   and rebuild, or hand-write them).
3. **`App.vue` is still the create-vue placeholder** (the default "Welcome"
   page), never rewired to mount the real `router.ts`/views. A regeneration
   of the `app_shell` node's `**App.vue**` half was also lost — the LLM's
   response for that node bundled both `main.ts` and an `App.vue` body in
   one output, but the node only maps to `main.ts` (see `graph-code`'s
   `CLAUDE.md` / `spl/tools.py:write_node_file` — one node, one file — so
   the second file's content never had anywhere to land). `App.vue` needs
   hand-authoring (or a real second node) to import `TaskView`/`AuthViews`
   via `router.ts` and mount conditionally on auth state.
4. **Leftover scaffold cruft** not cleaned up: `src/components/HelloWorld.vue`,
   `TheWelcome.vue`, `WelcomeItem.vue`, `icons/`, `src/router/index.ts`
   (create-vue's own router, separate from the real generated `src/router.ts`),
   `src/stores/counter.ts`, `src/views/HomeView.vue`/`AboutView.vue`. Safe to
   delete once `App.vue`/`router.ts` are wired to the real views.
5. **`vite.config.ts` has no `server.port`** — `npm run dev` would default to
   Vite's `5173` instead of the declared `5190`. Add:
   ```ts
   export default defineConfig({
     server: { port: 5190 },
     // ...
   })
   ```

None of these are backend-side; the backend has no equivalent gaps.
