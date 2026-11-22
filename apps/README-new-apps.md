# Candidate apps for Path-B ingestion

Currently ingested (`apps/SPL/*`): todo, expense, fastapi, fullstack, kanban,
dispatch, conduit, mealie — all FastAPI + SQLAlchemy + Vue/Vite, CRUD-shaped.
The picks below were chosen to force *new* graph patterns rather than repeat
CRUD+auth, while staying close to what
`graph-driven-workflow/scripts/extract_path_b.py` already knows how to parse:
`@router.*` FastAPI routes, Pydantic schemas, SQLAlchemy ORM classes, Vue
`.vue` components + TS API client. Stack mismatches (e.g. Django instead of
FastAPI, React instead of Vue) are noted per app — same kind of TODO-driven
reconciliation the extractor already does for mealie's Nuxt→Vue mismatch.

## Recommended, in priority order

| # | App | URL | Backend | Frontend | Functionality | New pattern | Extraction fit |
|---|-----|-----|---------|----------|----------------|-------------|-----------------|
| 1 | Fief | https://github.com/fief-dev/fief | FastAPI | — (mgmt UI) | Self-hosted authentication/identity server — login, user management, OAuth2 for your own apps | OAuth2 auth-code flow, multi-tenant orgs, API keys | Near drop-in (FastAPI + Pydantic + SQLAlchemy) |
| 2 | LibrePhotos | https://github.com/LibrePhotos/librephotos | Django | React | Self-hosted photo library — auto-organizes photos by face, object, and location recognition | File/media upload, background job processing, search/filtering | Needs Django route/service regex adaptation |
| 3 | Tandoor Recipes | https://github.com/TandoorRecipes/recipes | Django | Vue | Recipe manager with meal planning and auto-generated shopping lists | Meal planning + shopping-list generation | Needs Django adaptation; extends mealie's excluded scope |
| 4 | Misago | https://github.com/rafalp/Misago | Django | — (forum SPA) | Discussion forum software — threads, categories, moderation, notifications | Threaded/nested comments, categories, websocket notifications | Needs Django adaptation |
| 5 | Wger | https://github.com/wger-project/wger | Django REST | React | Workout/fitness tracker — training plans, exercise logs, body-weight/progress charts | Scheduling/calendar entities, time-series progress logs | Needs Django adaptation |
| 6 | Papermerge DMS | https://github.com/papermerge/papermerge-core | FastAPI-based | React | Paperless document archive — scan/upload docs, OCR text extraction, tag and search them | OCR ingestion pipeline, full-text search, tagging/folders | Close to current stack assumptions |

Papermerge DMS was picked over Paperless-ngx specifically because its
frontend is React (Paperless-ngx uses Angular, which would need a
`generate_frontend_graph` branch the extractor doesn't have yet).

## Skip for now

Non-Python backends (Go/Rust/Node/Ruby/PHP apps — e.g. Vikunja, Immich,
Firefly III, Rocket.Chat, Docuseal): `extract_path_b.py`'s route/schema/ORM
extraction is built entirely on Python's `ast` module, so these would need a
new extractor rather than reuse of the existing one.

## Next step

`extract_path_b.py`'s functionality is now available as `grafcode extract
--repo-path ... --output-dir ... --app-name ...` (see this repo's root
`CLAUDE.md`). Run it against Fief first — it slots straight into the
existing FastAPI/Pydantic/SQLAlchemy extraction path with zero adaptation
and validates a genuinely new pattern (OAuth flows + multi-tenancy).


### Extract "Todo"

see cloned apps locally at `$HOME/projects/wgong/graph-code-apps/`



#### Todo1
- cloned from `https://github.com/hvlds/todo` and strip off docker dependency

```bash
cd $HOME/projects/digital-duck/graph-code
conda activate spl123

export APP_NAME=todo1

grafcode extract \
  --repo-path $HOME/projects/wgong/graph-code-apps/$APP_NAME \
  --output-dir apps/$APP_NAME \
  --app-name $APP_NAME \
  --backend-routes-dir server \
  --backend-schema-dir server \
  --backend-models-dir server \
  --backend-services-dir server \
  --frontend-components-dir client/src/components \
  --backend-port 8010 --frontend-port 5180 \
  --llm claude_cli:claude-sonnet-4-6 \
  --llm-timeout 900 \
  --skip-cache


export APP_NAME=todo1 
grafcode extract --repo-path $HOME/projects/wgong/graph-code-apps/$APP_NAME --output-dir apps/$APP_NAME --app-name $APP_NAME --backend-routes-dir server --backend-schema-dir server --backend-models-dir server --backend-services-dir server --frontend-components-dir client/src/components --backend-port 8010 --frontend-port 5180 --llm claude_cli:claude-sonnet-4-6 --llm-timeout 900
```

**Build — DONE (2026-08-15/16), first `grafcode extract`-sourced app to complete the full
pipeline.** `apps/todo1/blueprint/main.graph.yaml` validates clean (`grafcode validate`):

```bash
cd $HOME/projects/digital-duck/graph-code
conda activate spl123

mkdir -p logs/console
spl3 run spl/build_app.spl \
    --tools spl/tools.py \
    -p system_yaml=apps/todo1/blueprint/main.graph.yaml \
    --llm claude_cli --llm-timeout 900 \
    2>&1 | tee "logs/console/build_app-todo1-$(date +%Y-%m-%d-%H-%M-%S).md"
```

Writes into `apps/todo1/backend/` and `apps/todo1/frontend/`, then runs `integrate_system.spl`
against the live system last. If the frontend step halts with `vitest: not found` (exit 127),
run `npm install` by hand in `apps/todo1/frontend/` once, then re-run the same command — already-
built nodes cache-hit, so it resumes rather than redoing everything.

Final clean run: backend 25/25 pytest, frontend 13/13 vitest, system 6/6 acceptance tests, 0 LLM
calls (full cache hit). Getting there needed real fixes to the extraction pipeline itself, not
just this app's blueprint — see `apps/README.md`'s todo1 row for the full list (dangling
`needs.backend` references silently resolving to zero endpoint context, `.spl_cache` staleness
after hand-patching generated files, a CORS port bug only caught by manual `curl` testing, and a
largely-fabricated auto-generated `README.md` since hand-corrected). Two new `grafcode validate`
checks (`validate_needs()`, `unreachable_applications()`) exist because of bugs this app's own
blueprint had. Two more bugs surfaced only by an actual manual browser test (nothing else loads a
real page): `vite.config.ts` missing `server.port` (defaulted to Vite's `5173` instead of the
real `5180`) and `index.html` missing a Bulma stylesheet link despite every generated component
using Bulma classes — both scaffold gaps (hand-authored, not LLM-generated), fixed. **Manually
confirmed working in a real browser by Wen** — add/list/complete/delete/filter/statistics all
functional. See `apps/todo1/README.md` for exact run commands (backend
`uvicorn app.main:app --port 8010`, frontend `npm run dev` on `:5180`).




#### Todo-2 (todo2A)
- cloned from `https://github.com/notarious2/Vue3FastAPI-To-Do` at
  `$HOME/projects/wgong/graph-code-apps/todo2A`, simplified to SQLite
  (dropped Postgres/asyncpg) and username/password-only auth (dropped
  Google OAuth2) — see `todo2A/README.md` in that clone for what changed.
  Layout is `backend/`/`frontend/`, not todo1's `server/`/`client/`, so the
  extractor's dir flags differ accordingly; ports 8020/5190 avoid colliding
  with todo1's 8010/5180.

```bash
cd $HOME/projects/digital-duck/graph-code
conda activate spl123

export APP_NAME=todo2A

grafcode extract \
  --repo-path $HOME/projects/wgong/graph-code-apps/$APP_NAME \
  --output-dir apps/$APP_NAME \
  --app-name $APP_NAME \
  --backend-routes-dir backend/routers \
  --backend-schema-dir backend \
  --backend-models-dir backend \
  --backend-services-dir backend/repositories \
  --frontend-components-dir frontend/src/components \
  --backend-port 8020 --frontend-port 5190 \
  --llm claude_cli:claude-sonnet-4-6 \
  --llm-timeout 900
```

Rerunning this exact command is safe/cheap once a prior run has already
succeeded (or gotten partway through) — see "If this dies partway
through" under Fief, below; the same two-layer resumability applies here.



##### Build

```bash
cd $HOME/projects/digital-duck/graph-code
conda activate spl123

mkdir -p logs/console

export APP_NAME=todo2A
spl3 run spl/build_app.spl \
    --tools spl/tools.py \
    -p system_yaml=apps/$APP_NAME/blueprint/main.graph.yaml \
    --llm claude_cli --llm-timeout 900 \
    2>&1 | tee "logs/console/build_app-$APP_NAME-$(date +%Y-%m-%d-%H-%M-%S).md"
```

##### Node version (frontend build blocker)

todo2A's frontend build hit a real environment gap, not a code bug: its
`vue_typescript` component has no pre-authored scaffold (unlike todo/todo1,
which had one hand-copied in once during earlier prototyping — see
`spl/tools.py`'s `seed_component_scaffold` docstring), so
`build_component.spl`'s scaffold step now bootstraps one automatically via
`npm create vue@latest` (added specifically to unblock this). That scaffold's
`package.json` declares `"engines": {"node": "^22.18.0 || >=24.11.0"}`, and
even pinning an older `create-vue` release doesn't help — `npm install`
still resolves current, unpinned `jsdom`/`@csstools` versions that assume
newer Node ESM/CJS interop. Confirmed failure on this machine's Node
`v22.9.0`: `npm test` crashes with `ERR_REQUIRE_ESM` inside jsdom's CSS
parser, before any tests can run.

**Fix: upgrade Node via `nvm`** (already installed here; only `v22.9.0` is
present, aliased as `default`):

```bash
# Pick up nvm in a fresh shell if it's not already loaded (usually sourced
# from ~/.bashrc automatically — this line is only needed if `nvm` isn't
# recognized as a command):
source "$HOME/.nvm/nvm.sh"

# Install the latest Node 22 LTS release (stays on the same major version
# as what's already here — avoids unrelated breakage elsewhere in the
# project from jumping to Node 24):
nvm install 22

# Make it the default for every new shell (otherwise `grafcode ide`/`spl3`
# subprocess calls that spawn a fresh shell keep picking v22.9.0):
nvm alias default 22

# Verify — must show >= 22.18.0:
node --version

# v22.23.2
```

Then re-run `npm install` in the affected frontend dir (stale
`node_modules/` built against the old Node version won't just start working):

```bash
cd apps/$APP_NAME/frontend
rm -rf node_modules package-lock.json
npm install
npm test
```

If `npm test` still fails afterward, it's no longer this Node-version gap —
worth re-checking `package.json`'s `engines` field against `node --version`
before digging further.

##### Design sketch: splitting todo2A's backend into auth/task/user sub-components

**Status: proposal only, not implemented.** Paused here per Wen (2026-08-16) to go validate
other already-built apps first. Motivated by two things found while testing the built `todo2A`
app: (1) the Graph IDE render of the whole app (`/home/gongai/Pictures/zinets/graph-todo2A.png`)
showed 45 nodes / 143 edges as one flat, hard-to-read mass with no visual separation between
backend/frontend or between auth/task/user concerns within backend; (2) several of the real build
bugs found that session (wrong import paths, mismatched filenames between sibling nodes — see
that session's findings) are the kind of cross-file inconsistency more likely when one generation
pass has to hold many unrelated-domain nodes in context at once. `backend.graph.yaml` today is a
single flat 12-node file (`config`, `database`, `models`, `schemas`, `utils`, `auth`, `user_repo`,
`task_repo`, `auth_router`, `user_router`, `task_router`, `main_app`) — everything the same
generation pass has to keep consistent.

**The mechanism already exists — no schema change needed.** `imports:` isn't special to
`main.graph.yaml`; any `graph.yaml` can declare it, and `resolve_imports()` works identically at
any nesting depth: it pulls in only the imported graph's `function.exports` (namespaced
`alias.export_name`), not its full internals. So `backend.graph.yaml` can become a thin
composition root the same way `main.graph.yaml` is today, one level deeper.

**Proposed split**, grouping today's 12 nodes by the domain boundary the source repo already has
(the router/repo files were already split this way before extraction):

| New file | Nodes (moved from today's flat `backend.graph.yaml`) | Imports from |
|---|---|---|
| `blueprint/backend/core.graph.yaml` | `config`, `database`, `models`, `schemas`, `utils` | (primitives only — the shared foundation every other sub-component depends on) |
| `blueprint/backend/user.graph.yaml` | `user_repo`, `user_router` | `core` |
| `blueprint/backend/auth.graph.yaml` | `auth`, `auth_router` | `core`, `user` (auth_router calls `UserRepository.authenticate_user`/`get_user_by_username_or_email` — a real cross-component edge in the current code, not an artifact of the split) |
| `blueprint/backend/task.graph.yaml` | `task_repo`, `task_router` | `core`, `auth` (task_router depends on `auth`'s `get_current_user` for every endpoint) |
| `blueprint/backend.graph.yaml` (becomes a composition root) | `main_app` only | `core`, `user`, `auth`, `task` — imports each sub-component's exported router ports and composes them, same shape `main.graph.yaml` already uses for `backend.graph.yaml`/`frontend.graph.yaml` today |

Import order forms a DAG among the sub-components themselves (`core → user → auth → task →
backend` root) — no cycles, consistent with the same acyclicity discipline `form_graph` already
enforces within one file. The two cross-component edges (`auth` importing `user`'s repo exports,
`task` importing `auth`'s `get_current_user`) are the interesting design decisions here, not
incidental — they're exactly the dependencies `check_call_contracts()` would need to verify once
imports cross a sub-component boundary instead of just a top-level component boundary.

**What this is not yet:** three real pieces of work, none started —

1. **`grafcode extract` has no clustering logic.** It emits one flat node list per component
   today. Clustering by which router/repo *file* a node came from (the AST scan already has this
   information — `routers/auth.py` vs `routers/task.py` vs `routers/user.py`) into separate
   sub-component graphs is new extraction logic, not a config flag.
2. **Graph IDE's merge-for-display doesn't distinguish nesting depth.** It would likely still
   render everything flattened with sub-components in place unless taught to show only a
   collapsed sub-component (its exported ports) with drill-down, rather than always fully
   expanding every import.
3. **Build pipeline untested at this nesting depth.** `spl/build_app.spl`/`build_component.spl`
   have been exercised against the two-level `main → backend/frontend` shape; arbitrary-depth
   nesting (`main → backend → auth/task/user`) needs verification, not assumed to just work.

**Next step, when this resumes:** hand-author this split for `todo2A` specifically (don't wait for
extractor clustering support) as apps/README-new-apps.md's Todo1/Todo-2 sections already do
plenty of hand-authoring — validates the `imports:`-at-any-depth mechanism and
`check_call_contracts()` across sub-component boundaries with a real app before investing in
extractor clustering logic.

##### Prototype: `grafcode tools suggest-graph-clusters` (2026-08-17)

Item 1 above ("`grafcode extract` has no clustering logic") now has a working, mechanical
prototype — `suggest_clusters()` in `graph_lib.py`, exposed as `grafcode tools
suggest-graph-clusters <graph.yaml> [--seed NODE_ID ...] [--format text|json]`. It's a graph
algorithm, not an LLM heuristic, consistent with graph-code's general preference for surfacing
mechanical facts over guessing (`docs/PAPER/subsection-cs-duality-and-vibe-coding.md` §5): no
modularity/community-detection library (Louvain, Leiden, spectral cut, METIS-style balanced
partitioning, core-periphery decomposition were all considered and set aside — they need
hyperparameters and, per the literature, handle hub/core nodes poorly), just `nx.ancestors()`
over the same mandatory `composed_of`/`depends_on` subgraph `reducible()`/`productivity_order()`
already use.

**The algorithm:**

1. Seed clusters from `function.exports[].from` (deduped; `node_id.port_name` is split on the
   first `.` to get the node id) — a graph's own declared public surface is a natural,
   already-present signal for "these are the entry points a split should be organized around,"
   with no new annotation required. `--seed` overrides this when a graph has no exports yet, or
   when the natural cluster boundary isn't the export surface.
2. Each seed's cluster starts as `nx.ancestors(seed) ∪ {seed}` — everything the seed is built
   from.
3. A node is exclusively that seed's if it's an ancestor of that seed and no other.
4. A node ancestor of **every** seed is `core` — genuinely shared infrastructure.
5. A node ancestor of **some but not all** seeds is `shared`, keyed by which seeds share it — a
   real cross-component dependency, not core. This is the rule this session's own worked example
   caught: a looser "ancestor of 2+ seeds ⇒ core" rule would have misclassified `auth` as core in
   the `todo2A` backend (it's upstream of both `auth_router` and `task_router`, 2 of 3 seeds) —
   the tool never force-assigns this bucket to one cluster or folds it into core; it reports the
   sharing explicitly and leaves the call to a human.
6. Nodes upstream of no seed (e.g. a composition root that only *consumes* the seeds) are
   `unclustered`.

**Run against the real `todo2A` blueprint** (`apps/todo2A-copy/blueprint/`, a copy kept separate
from `apps/todo2A/` so this prototyping doesn't disturb the app that's mid-build/mid-testing) —
`backend.graph.yaml`:

```
seeds: auth_router, task_router, user_router

cluster: auth_router          cluster: user_router      cluster: task_router
  auth_router                   user_router                task_repo
                                                              task_router

core (ancestor of every seed — shared infrastructure):
  config, database, fastapi, models, pydantic, python, schemas, sqlalchemy

shared (ancestor of some but not all seeds — real cross-component dependencies):
  auth       (used by: auth_router+task_router)
  pyjwt      (used by: auth_router+task_router)
  user_repo  (used by: auth_router+user_router)
  utils      (used by: auth_router+user_router)

unclustered (no seed depends on these — e.g. the composition root):
  main_app
```

This reproduces the proposed split's table above almost exactly, mechanically: `core` matches the
proposed `core.graph.yaml`; `auth`/`task_repo`+`task_router` match `auth.graph.yaml`/
`task.graph.yaml`; `user_repo` lands correctly in `shared` (used by both `auth_router` and
`user_router`) rather than in either cluster outright — the tool doesn't yet know `user_repo`
"belongs" with `user_router` (that's a naming/ownership judgment beyond what ancestor-closure
alone can decide), but it does correctly refuse to bury the fact that `auth_router` also depends
on it. `main_app` correctly falls out as `unclustered` — it's the composition root, downstream of
every seed, not upstream of any of them, so there's nothing for this ancestor-only algorithm to
say about it (expected, not a gap).

`frontend.graph.yaml` clusters just as cleanly: seeds `auth_store`, `auth_views`, `task_view`;
`core` = `api_client`, `auth_api`, `auth_store`, `axios`, `pinia`, `types`, `typescript`;
`auth_views`'s cluster picks up `user_api`; `task_view`'s cluster picks up `layout_components`,
`task_api`, `task_item`, `task_list`; `router`/`vue`/`vue_router`/`vuetify` land in `shared`
(used by `auth_views+task_view`); `app_shell` is `unclustered` (the composition root again).

**What this closes, and what it still doesn't:** this validates that the proposed split above is
mechanically discoverable, not just hand-drawn — a real signal that `grafcode extract` could
eventually run this over a freshly-extracted monolithic component graph and emit the sub-component
split automatically. It does **not** yet: (a) name the resulting clusters (it reports node sets,
not `auth.graph.yaml` vs `task.graph.yaml` — naming is still a human/LLM step), (b) decide where a
`shared` node's *file* should live (report only — same "report but don't decide" contract as
`grafcode drift`), or (c) wire into `grafcode extract` itself — it's a standalone `tools` command
today, not yet called from the extraction pipeline. Tests: `tests/test_graph_lib.py`'s
`TestSuggestClusters` (7 cases, including the `auth`-not-core regression case above).

### Extract "Fief"

```bash
cd $HOME/projects/digital-duck/graph-code
conda activate spl123

grafcode extract \
  --repo-path $HOME/projects/wgong/graph-code-apps/fief \
  --output-dir apps/fief \
  --app-name fief \
  --backend-routes-dir fief/apps/api/routers \
  --backend-schema-dir fief/schemas \
  --backend-models-dir fief/models \
  --backend-services-dir fief/services \
  --backend-port 8010 --frontend-port 5180 \
  --llm claude_cli:claude-sonnet-4-6 \
  --llm-timeout 900 \
  --skip-cache
```

**If this dies partway through** (this is what actually happened on the
first attempt — `ModelOverloaded` on the third repair-loop attempt of the
`--llm` pass, after attempts 0-1 had already gotten real responses): just
rerun the exact same command. No flags need to change — resumability is on
by default at two layers:

- `apps/fief/.grafcode_cache/` remembers the AST-extraction scan, so the
  rerun doesn't re-walk `fief/apps/api/routers` etc. from scratch.
- The `--llm` pass itself runs as a durable `spl3` workflow (`--persistence
  sqlite` is the default in both `grafcode extract` and `spl3 run` itself),
  checkpointing every `GENERATE`/`CALL` step under a `--workflow-id` derived
  from this command's own inputs — so the rerun resumes attempt 2 instead of
  re-paying for attempts 0-1.

Pass `--skip-cache` to force a fully clean run instead (e.g. if you've since
edited the source repo and want a genuine from-scratch re-extraction).