# Graph IDE

A browser viewer for app-graph blueprint graphs (`apps/<app>/blueprint/*.graph.yaml`). Pick any app under `apps/`, see its full node/edge graph rendered as an SVG DAG, click a node to inspect its `spec`/`verification`/`docs` and see everything it transitively depends on, and rearrange the layout by dragging.

Ported from `graph-driven-workflow/tools/graph-ide` (2026-08-14) — same frontend, same API shape, but the backend now reads app-graph's actual schema via `appgraph.loader.load_domain()` instead of hand-rolling YAML parsing against the old GDW `system.yaml`/`primitives`/`concepts`/`applications` format. See `docs/DEV/BUILD/refactoring-plan-v1.md` for why duplicating schema-parsing logic outside the library is exactly the kind of drift this framework has repeatedly had to fix — this tool is now a real consumer of `appgraph`, not a second implementation of its parser.

```
tools/graph-ide/
  api/          FastAPI backend — discovers and merges a blueprint set into {nodes, edges, components}
  frontend/     Vite + vanilla JS — SVG renderer, no third-party graph library
```

## Quick start

Two terminals, from the repo root:

```bash
# once: appgraph itself must be installed editable (see repo CLAUDE.md)
pip install -e ".[dev]"

# Terminal 1 — API
cd tools/graph-ide
pip install -r requirements.txt   # first time only
uvicorn api.app:app --port 8880 --reload

# Terminal 2 — frontend
cd tools/graph-ide/frontend
npm install   # first time only
npm run dev
```

Or, once `appgraph` is installed, launch both with a single shortcut: `appgraph ide` (see below).

Open **http://localhost:8881** — the app-picker dropdown populates automatically from every `apps/<app>/blueprint/` directory containing at least one `*.graph.yaml`, and the first one loads.

To open a specific app directly, pass it in the URL: `http://localhost:8881/?root=apps/kanban`.

Ports are configurable via env vars if 8880/8881 are taken:

```bash
API_PORT=8300 DEV_PORT=5300 npm run dev   # frontend picks these up via vite.config.js
```
(run the `uvicorn` command with `--port 8300` to match).

## Using it

- **App picker** (top bar) — select which `apps/<app>` blueprint set to load, then **Load** to (re)fetch it. The dropdown label drops the common `apps/` prefix (e.g. shows `kanban`, not `apps/kanban`) since every app lives there by convention; the underlying value/query param is still the full repo-relative path. Deep-links via `?root=`.
- **Zoom Out / Re-Center / Zoom In** (top bar, center) — Zoom Out (`−`) and Zoom In (`+`) scale the graph canvas; **Re-Center**, between them, restores the auto-computed tiered layout at 100% zoom and clears any highlighting/dragging.
- **Click a node** — highlights that node plus every node it transitively depends on (walking `composed_of`/`depends_on`/`needs` edges backwards), dims everything else, and shows its `defines`/`spec.interface`/`spec.contract`/`verification`/`docs` in the right-hand detail panel.
- **Drag a node** — repositions it; edges connected to it redraw live. Useful for untangling a dense graph.
- **Splitter** (between the graph canvas and the detail panel) — drag to resize the two panes; the panel absorbs whatever space is left, so it stays correct if the browser window itself is resized.
- **Edit toggle** (top-right) — unchecked by default (view-only). Check it to turn the detail panel's fields into a form: edit a node's `defines`/`spec.interface`/`spec.contract`/`spec.user_story`/`verification.node`/`verification.edge`/`docs`, then **Save** to write straight back to the owning `graph.yaml`, or **Cancel** to discard. Structural fields (`composed_of`, `depends_on`, `needs`, `tier`, `capstone`) aren't editable yet.
- **⚙ Settings** (top-right) — a modal for UI/tool preferences, persisted to the browser's `localStorage` (not written to any file): a font-size slider (previews live as you drag it) and a placeholder LLM section (provider/model/API key) for future features. Nothing in the LLM section is wired to a feature yet.
- **ℹ About** (top-right) — a modal with the node-kind legend and, once a graph is loaded, its discovered files and components. There's no left sidebar anymore — this and the zoom/edit controls freed that column for the graph canvas and detail panel.

### Reading the graph

- Node color = kind: `primitive` (yellow), `concept` (green), `module` (teal), `doc` (gray), `step` (purple), `component` (orange, e.g. a system's `<app>_app_shell`), `application` (pink) — see the **About** modal's legend. This is app-graph's actual `form.nodes.<id>.kind` vocabulary, richer than the old GDW schema's fixed primitive/concept/application set.
- Edge style: solid gray = `composed_of`/`depends_on` (mandatory structural), dotted purple = `enriched_by`/`optionally_depends_on` (optional structural), dashed blue = `needs` (functional/application-level).
- Selected node and its dependency path are highlighted in amber (nodes) / blue (edges); everything else dims.
- Node ids are namespaced by component (`backend::api_routes`) so identically-named nodes in different components never collide (this session's de-prefixing convention — see `docs/DEV/BUILD/refactoring-plan-v1.md` §1.4 — means many apps now share generic node ids like `data_schema`/`orm_model` across components, which is exactly what this namespacing exists to disambiguate); system-level applications are namespaced `system::<name>`.

## App discovery

An app is discoverable if it has an `apps/<app>/blueprint/` directory containing at least one `*.graph.yaml`. Generated-target dirs like `todo-v2`/`expense-v2` (build *output*, not blueprint source) have no `blueprint/` and are correctly excluded — there's nothing for graph-ide to render for them.

- **`blueprint/main.graph.yaml` present** — treated as the system-level entry; its `imports:` list names one or more component graph.yaml files (e.g. `backend.graph.yaml`, `frontend.graph.yaml`), each loaded and merged in. System-level `applications:` (if any) are rendered as `system::<name>` nodes.
- **No `main.graph.yaml`, exactly one `*.graph.yaml`** — treated as a standalone component (e.g. `etl_workflow`, a `workflow`-profile app with no system-level composition).

## API reference

| Endpoint | Description |
|---|---|
| `GET /api/graphs/roots` | Every app under `apps/` with a `blueprint/` subfolder containing at least one `*.graph.yaml`, as repo-relative paths — powers the dropdown. |
| `GET /api/graphs?root=<path>` | Merged `{root, files, components, nodes, edges}` for one app (`root` relative to the repo root, e.g. `apps/todo`). |
| `PATCH /api/graphs/nodes/{node_id}?root=<path>` | Update one node's editable prose fields (a partial `{defines, docs, spec: {...}, verification: {...}}` patch); writes straight to the owning `graph.yaml` via `ruamel.yaml` round-trip, gated by `appgraph.graph_lib.validate_full()` on a trial write before touching the real file. `404` if the node/root doesn't exist, `422` for a non-editable field or a failed validation check. |

Requires `fastapi`, `uvicorn`, `pyyaml`, `ruamel.yaml`, and `appgraph` itself (installed editable from the repo root).

## Current limitations

**UPDATE only** — the Edit toggle lets you rewrite an existing node's prose fields. Create/delete for nodes or edges, and editing structural fields (`composed_of`, `depends_on`, `needs`, `tier`, `capstone`), aren't implemented.

## ROADMAP

Ideas floated for future work, not yet designed or scheduled:

- **Clone an app** — duplicate `apps/<app>/blueprint/` (and settings.yaml) under a new app name as a starting point for a variant, instead of hand-copying directories.
- **Build from the IDE** — trigger a blueprint build (the SPL runner in the sibling `SPL.py` repo) for the currently-loaded app without leaving the browser, and surface build status/output.
- **Compare blueprints between two apps** — a visual diff view over two apps' `*.graph.yaml` (nodes/edges/spec text) in the browser, distinct from `appgraph compare` (diffs two *build outputs*) and now `appgraph drift` (computes the 5-component drift vector between two blueprints on the CLI, no visualization) — this item would surface `appgraph drift`'s numbers as an in-browser side-by-side view instead.
- **LLM-assisted editing** — use the Settings page's LLM provider/model/key (currently just stored, unused) to draft or refine a node's `spec`/`docs` text from within the edit form.

## Troubleshooting

- **"error loading app list"** — usually a stale `uvicorn` process serving old code after a pull; restart it (`Ctrl-C` then re-run the `uvicorn` command above).
- **`vite: not found` / build fails** — `node_modules` is out of date or missing; `cd frontend && npm install`.
- **`ModuleNotFoundError: appgraph`** — `appgraph` needs to be installed editable from the repo root first: `pip install -e ".[dev]"`.
- **A specific app doesn't show up in the dropdown** — it needs at least one `*.graph.yaml` directly under `apps/<app>/blueprint/`.
