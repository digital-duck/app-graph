# Conduit App

A Conduit ("RealWorld"-spec-inspired) social blogging clone: JWT auth, social articles (CRUD + tags + favorites + comments), and follow/unfollow profiles, built with a Vue.js frontend and a FastAPI backend persisted to SQLite. It's the most structurally complex app in this family — two self-referential/junction-table many-to-many relationships (`follows`, `favorites`), a string-tag pattern (`articles_to_tags`), and per-request computed fields (`following`, `favorited`, `favoritesCount`) on almost every response.

**Note:** this backend deliberately does not match the canonical RealWorld API's exact wire format — no `/api` prefix, flat (non-enveloped) request/response bodies, and `Authorization: Bearer <token>` instead of `Authorization: Token <token>`. See `blueprint/main.graph.yaml`'s `applications:` header comment for the full list of intentional deviations.

## Status

See [apps/README.md](../README.md)'s `conduit` row for build/test history. This README's build/run instructions reflect the 2026-08-14 framework refactor (`docs/DEV/BUILD/refactoring-plan-v1.md`) — app-scoped `settings.yaml`, de-prefixed backend node id (`auth_schema`→`data_schema`), and the `app/config.py`/`src/config.ts`-based CORS/BASE_URL wiring — which has not yet been verified against a real `spl3` build for this app.

## Architecture

The Vue.js frontend (port **5178**) communicates with the FastAPI backend (port **8007**) over REST, with CORS enabled and JWT bearer auth on the backend; see [backend/README.md](backend/README.md) and [frontend/README.md](frontend/README.md) for each component's own setup, run, and test instructions. Ports are defined once in [blueprint/settings.yaml](blueprint/settings.yaml) and referenced from every `*.graph.yaml` as `${{ settings.KEY }}`.

## Running the full system

**1. Build** — generate and install both components from the graph:

```bash
spl3 run spl/build_app.spl \
    --tools spl/tools.py \
    -p system_yaml=apps/conduit/blueprint/main.graph.yaml \
    --llm claude_cli
```

To generate a fresh copy of the app into a new directory instead of overwriting
`apps/conduit/backend`/`apps/conduit/frontend` in place, add `-p output_dir=...`:

```bash
mkdir -p logs/console
spl3 run spl/build_app.spl \
    --tools spl/tools.py \
    -p system_yaml=apps/conduit/blueprint/main.graph.yaml \
    -p output_dir=apps/conduit-v2 \
    --llm claude_cli \
    2>&1 | tee "logs/console/build_app-$(date +%Y-%m-%d-%H-%M-%S).md"
```

The `tee` keeps the console output live while also capturing it to a
timestamped file under `logs/console/` — useful since a failed build's real
error (e.g. a `pytest`/SQLAlchemy traceback) often scrolls past the terminal
buffer before you can read it, and `spl3`'s own log (path printed as `Log:`
at the end of the run) captures the workflow trace but not the raw stdout.

Each component is then written to `{output_dir}/{component_id}/` — i.e.
`apps/conduit-v2/backend/` and `apps/conduit-v2/frontend/` for the command above —
leaving the existing `apps/conduit/backend`/`apps/conduit/frontend` untouched.

See [docs/DEV/BUILD/README.md](../../docs/DEV/BUILD/README.md) §12.1 for full build options and §12.4 for `--output_dir` usage.

**Building to a redirected `-p output_dir=...` location**: the build seeds each component's pre-authored
scaffold (`tests/`, and for the frontend also `package.json`/`package-lock.json`/`vite.config.ts`/
`tsconfig.json`/`index.html`/`.env`) into the new location automatically, but **deliberately does
not copy `node_modules/`** (copying a dependency tree risks silent drift from `package.json` —
reinstalling is safer). If the frontend build halts with `vitest: not found` (exit 127), run
`npm install` by hand in the redirected frontend directory once, then re-run the same
`spl3 run spl/build_app.spl ...` command — it picks up where it left off (already-passing nodes
are cached, so only the remaining work re-runs).

**If a rebuild is needed after editing the blueprint** (e.g. iterating on a spec fix), clear that
component's cache and any stale runtime SQLite files first, so the fix is guaranteed to actually
regenerate rather than serve a stale cache hit:

```bash
rm -rf apps/conduit-v2/backend/.spl_cache apps/conduit-v2/frontend/.spl_cache
rm -f apps/conduit-v2/backend/*.db
```

**2. Start the backend:**

```bash
cd backend
uvicorn app.main:app --reload --port 8007
```

**3. Start the frontend** (separate terminal):

```bash
cd frontend
npm run dev
```

The app is then available at <http://localhost:5178>.

## Applications

- **register_and_login** — a new user registers and logs in, receiving a JWT token
- **browse_articles** — anyone browses the global article feed, no auth required
- **filter_by_tag** — the article list filters to a single tag
- **create_and_view_article** — an authenticated user publishes an article, identified by a slug
- **favorite_article** — an authenticated user favorites an article; `favoritesCount` increments
- **comment_on_article** — an authenticated user adds a comment; anyone can read comments
- **follow_and_feed** — a user follows an author and sees that author's articles in a personal feed
- **publish_and_engage** — the capstone: full golden path — register, publish, follow, favorite, comment
