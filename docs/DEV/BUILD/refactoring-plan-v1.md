# Refactoring Plan v1

## Context

`docs/DEV/BUILD/code-review.md` flagged seven issues after reviewing
`apps/todo/blueprint/main.graph.yaml` and the tooling around it. Four of them
turned out to be small, consistent design decisions rather than one-off
fixes:

1. Root-level graph attributes (`graph`, `version`, `domain_type`,
   `description`) duplicate fields already carried in the `blueprint:` block.
2. Ports (and other config) are hard-coded per file with no single source of
   truth, which already caused one real incident (see main.graph.yaml's
   `ports:` block comment, 2026-08-12: a stray second Vite instance silently
   moved to :5174 and broke CORS with no error pointing at the cause).
3. `spl/tech_profiles.py`'s `NODE_FILES` is a flat `dict[profile, dict[node_id,
   path]]`, which produces literal duplicate keys (`crud_operations` appears
   twice) and near-collisions (`auth_schema` vs `auth_schemas`) across
   unrelated apps that happen to share a tech profile.
4. Node ids are app-prefixed (`todo_schema`, `todo_orm_model`,
   `todo_item_component`, ...) even though the app is already the namespace
   (the directory / blueprint id) — this makes cross-app graph patterns
   harder to spot and prevents node-id reuse across apps.

A fifth, unrelated gap surfaced separately: `docs/DEV/BUILD/blueprint-schema-v2.2.md`
never actually documents cache control, even though a per-node `use_cache`
attribute is already implemented (`spl/tools.py::cache_get`,
`build_component.spl`) — and there's no equivalent control at the edge level
at all, even though a dependency changing is exactly the case where a
downstream node's cache should be invalidated.

We're in initial development with no backward-compatibility burden, so the
decision (confirmed with the user) is to fix the framework once and propagate
the pattern app-by-app, **todo app first as the reference implementation**.
This document is that reference: part 1 is the one-time framework/tooling
change, part 2 is the todo-app-specific migration to use as the template for
every other app under `apps/`, part 3 is cache control (documenting the
existing node-level mechanism and designing the missing edge-level one).

Two things intentionally do NOT change in this pass: `Blueprint.schema_version`
(the blueprint-provenance schema, e.g. "2.2") and the core graph schema
version (currently `version: "2.1"` at graph root) are kept as two distinct
concepts — they answer different questions ("how is this blueprint block
shaped" vs "how is the whole graph.yaml shaped") and collapsing them would
lose information, not just remove duplication.

---

## Part 1 — Framework changes

### 1.1 Blueprint block becomes the source of truth

**File:** `src/graph_code/loader.py`

- `Blueprint` dataclass gains one field: `graph_schema_version` (holds what is
  today the root `version:` key, e.g. `"2.1"`). `schema_version` keeps its
  current meaning (the blueprint block's own schema version, e.g. `"2.2"`).
- `GraphDomain.graph_id`, `.version`, `.domain_type` are still populated (lots
  of code depends on them — see `graph_lib.py:478,494`), but now sourced from
  `blueprint.id` / `blueprint.graph_schema_version` / `blueprint.domain_type`
  when a `blueprint:` block is present, falling back to the legacy root keys
  otherwise (keeps v1.0 flat / no-blueprint graphs working unmodified).
- `GraphDomain.description` field is dropped. `GraphDomain.comment` (already
  exists but was unused at the top level) becomes the one prose field:
  `comment = data.get("comment") or data.get("description", "")`. Existing
  apps that still say `description:` keep working with zero edits — only
  newly-migrated apps switch the yaml key to `comment:`.
- Net effect on an authored `graph.yaml`: `graph:`, `version:`, `domain_type:`,
  and `description:` at root become optional/legacy. The `blueprint:` block
  (`id`, `graph_schema_version`, `schema_version`, `domain_type`, provenance,
  parent_blueprint, lineage) plus a root `comment:` are the authored source of
  truth going forward.
- No other file reads `.description` today (`grep` confirms it's only
  produced/consumed inside `loader.py`), so this is safe to change without
  touching `graph_lib.py` or `spl/tools.py`.

### 1.2 App-scoped settings (`${{ settings.KEY }}`)

Settings are **app-scoped, not framework-global**. Each app owns exactly one
settings file, sitting next to that app's own graph.yaml files:

**New file per app:** `apps/<app>/blueprint/settings.yaml`

```yaml
settings:
  - key: BACKEND_FASTAPI_PORT
    value: 8000
    comment: FastAPI backend port
  - key: FRONTEND_VITE_PORT
    value: 5173
    comment: Vite dev server port
```

Every `*.graph.yaml` under `apps/<app>/blueprint/` (system, backend,
frontend, ...) can reference that one app's settings via
`${{ settings.KEY }}`. This is what makes the value single-source: to change
a port (or any other repeated literal) for an app, edit one key in that
app's `settings.yaml` — every graph.yaml referencing it picks up the new
value, no cross-file search-and-replace of the literal itself needed. Two
different apps' settings never share a namespace or a file.

**New module:** `src/graph_code/settings.py` — the *mechanism* lives in the
framework (so every app gets it for free), but the *data* it reads is always
resolved relative to the graph.yaml being loaded, never a fixed repo-root
path.

- `load_settings(graph_yaml_path: Path) -> dict[str, Any]` — walks up from
  `graph_yaml_path` to find the nearest `settings.yaml` (in practice: the
  same `blueprint/` directory the graph.yaml lives in — every `*.graph.yaml`
  is required to live under `apps/<app>/blueprint/`, so `settings.yaml` is
  always a sibling file there). Returns `{}` (not an error) if the app has no
  `settings.yaml` — settings are opt-in per app. Cached per-directory so
  loading three graph.yaml files from the same app's `blueprint/` only reads
  `settings.yaml` once.
- `interpolate(obj: Any, settings: dict) -> Any` — recursively walks
  dict/list/str, replacing every `${{ settings.KEY }}` token found in a
  string value. Regex: `\$\{\{\s*settings\.([A-Za-z0-9_]+)\s*\}\}`. Applies
  everywhere a string can appear — including prose (`spec.interface`,
  `contract`, `docs`, `comment`) per the user's explicit choice, not just
  structural fields like `port:`.
- A `${{ settings.X }}` reference with no matching key in that app's
  `settings.yaml` -> raise `ToolFailed` (loud failure — a typo'd key should
  never silently pass the literal string `${{ settings.X }}` through to
  generated code or an LLM prompt).

**Why interpolating into the graph.yaml is not sufficient on its own.**
Resolving `${{ settings.X }}` before a node's spec/contract text reaches the
LLM (as described above) makes the *authored yaml* single-source, but the
LLM still writes the resolved literal (e.g. `8000`, `"http://localhost:5173"`)
directly into generated code. Changing a setting afterwards would then still
require re-running LLM generation for every file that used it — exactly the
re-generation cost the user wants to avoid ("in case one wants to change any
setting key, one can do global search-and-replace" implies changing
`settings.yaml` alone should be enough, with no LLM call). So a second piece
is required:

- **A deterministic, non-LLM config artifact generated per component from
  that app's `settings.yaml`**, written *before* the LLM build step so
  dependent nodes can import it. `spl/tools.py` gets a new tool,
  `write_settings_config(app_name, output_dir, profile) -> str`, called once
  per component near the top of `build_component.spl` (same place
  `seed_component_scaffold` already runs — see `build_app.spl`'s loop):
  - `python_fastapi` / `python_library` -> `app/config.py`:
    ```python
    from __future__ import annotations
    BACKEND_FASTAPI_PORT = 8000
    FRONTEND_VITE_PORT = 5173
    ```
  - `vue_typescript` -> `src/config.ts`:
    ```typescript
    export const BACKEND_FASTAPI_PORT = 8000;
    export const FRONTEND_VITE_PORT = 5173;
    ```
    (The frontend already has a related convention worth keeping consistent:
    `integrate_system.spl`'s header notes `api_client` reads
    `VITE_API_BASE_URL` from the environment rather than a hardcoded URL —
    `src/config.ts` covers settings that aren't naturally env-vars, e.g. a
    port referenced in more than one place.)
  - Plain string templating from the already-resolved settings dict, no
    `GENERATE`/LLM call — so it can be regenerated any time `settings.yaml`
    changes without touching any LLM-authored file.
  - This file itself does **not** go through `write_node_file`/`NODE_FILES`
    (it's not a graph node) and is **not** subject to `verify_node` — it's
    infra, like `seed_component_scaffold`'s output.
- **Node specs must reference the config module, not the literal value.**
  Any `spec.interface`/`spec.contract` text that today would resolve to a
  bare number/string (e.g. api_routes' CORS `allow_origins`) must instead
  instruct the LLM to import from `app.config`/`src/config.ts` and use the
  named constant — e.g. "CORS allowed origin: import
  `FRONTEND_VITE_PORT` from `app.config` and build the origin URL from it"
  rather than "CORS enabled for :5173". This is a per-node authoring
  discipline, not something `interpolate()` can enforce automatically — flag
  it in node specs during the app-level migration (Part 2) wherever a
  setting-derived value would otherwise land in generated code.
- **Net effect:** changing a value in `apps/<app>/blueprint/settings.yaml`
  and re-running `write_settings_config` (a fast, deterministic,
  non-LLM step) is enough to propagate the change everywhere — no
  `build_component.spl`/LLM regeneration required unless the *set of nodes
  that need the config* changes, not the value itself.

**Call sites (both must interpolate — there are two independent YAML entry
points today, and both need the graph.yaml's own path to locate the right
app's settings.yaml):**

- `src/graph_code/loader.py::load_domain()` — call
  `interpolate(raw, load_settings(yaml_path))` immediately after
  `yaml.safe_load`, before `_is_flat_v1`/`_build_graph_domain`.
- `spl/tools.py::_load_yaml()` (line 777) — this is a *separate* raw-YAML
  reader used by `component_tech_profile`, `component_port`,
  `check_port_consistency`, `_system_imports`, etc., specifically because
  `tech_profile`/`port`/`ports` are orchestration metadata with no field on
  `GraphDomain` (see backend.graph.yaml's own comment on this). It must call
  the same `interpolate()`/`load_settings()` pair, keyed off `path` — every
  call site already has the component's or system's own graph.yaml path
  available — otherwise `component_port()` would return the literal string
  `${{ settings.BACKEND_FASTAPI_PORT }}` instead of `8000`.

### 1.3 `NODE_FILES` nested by app, not flat by profile

**File:** `spl/tech_profiles.py`

- Reshape `NODE_FILES` from `dict[profile, dict[node_id, path]]` to
  `dict[app_name, dict[node_id, path]]`. `profile` is dropped as the outer
  key — it's redundant (derivable from `component_tech_profile()`) and was
  the reason unrelated apps' node ids collided in the same namespace.
- `get_node_file(app_name: str, node_id: str) -> str | None` replaces
  `get_node_file(profile, node_id)`.
- `app_name` is derived from the `graph_yaml` path already available at every
  call site — `apps/<app_name>/...` — via a small helper (e.g.
  `_app_name_from_path(graph_yaml)` in `tools.py`), not a new schema field.
  No yaml changes needed for this part.
- Three call sites in `spl/tools.py` need the extra argument threaded
  through: `write_node_file()` (line 390), `node_context()` (line 338, the
  loop over `tech_profiles.NODE_FILES.items()` becomes a single dict lookup
  on `NODE_FILES[app_name]`), and anywhere else that calls
  `get_node_file`/reads `NODE_FILES` directly (`grep -n NODE_FILES
  spl/tools.py` to confirm full list before editing).
- `VERIFY_CMDS` and `PROFILES` (the style-guide strings) stay keyed by
  `profile` — those are genuinely profile-wide, not app-specific.

### 1.4 `spl/README.md`

- New file, hand-written, one-time. Short table: file name, one-line purpose,
  for `build_app.spl`, `build_component.spl`, `compile_blueprint.spl`,
  `integrate_system.spl`, `tech_profiles.py`, `tools.py`. Content mirrors what
  each file's own header comment already says — this just makes it
  discoverable without opening every file. Maintained by hand going forward
  (no generator).

---

## Part 2 — App-level refactoring: todo app (reference pattern)

Apply after Part 1 lands and `pytest` still passes for all existing apps
unmodified (Part 1 must be backward-compatible on its own — see verification
below).

### 2.1 New file: `apps/todo/blueprint/settings.yaml`

```yaml
settings:
  - key: BACKEND_FASTAPI_PORT
    value: 8000
    comment: FastAPI backend port
  - key: FRONTEND_VITE_PORT
    value: 5173
    comment: Vite dev server port
```

### 2.2 `apps/todo/blueprint/main.graph.yaml`

- Drop root `graph: todo_app`, `version: "2.1"`, `domain_type: integrated`
  (already duplicated under `blueprint:`).
- Rename `description:` -> `comment:` (same content).
- `blueprint:` block gains `graph_schema_version: "2.1"` alongside the
  existing `schema_version: "2.2"`.
- Replace the `ports:` block:
  ```yaml
  ports:
    backend: ${{ settings.BACKEND_FASTAPI_PORT }}
    frontend: ${{ settings.FRONTEND_VITE_PORT }}
  ```
  This directly closes the gap the file's own long comment describes (no
  single source of truth for "what port should each component be on") — this
  app's `settings.yaml` becomes that single source, and
  `check_port_consistency()` keeps working unmodified since it still just
  compares two resolved ints.

### 2.3 `apps/todo/blueprint/backend.graph.yaml`

- Same root/blueprint/comment consolidation as 2.1.
- `port: ${{ settings.BACKEND_FASTAPI_PORT }}`.
- Node id renames (drop the `todo_` prefix now that `todo` is already the
  app namespace):
  | old | new |
  |---|---|
  | `todo_schema` | `data_schema` |
  | `todo_orm_model` | `orm_model` |

  `db_connection`, `crud_operations`, `api_routes`, `requirements`, `readme`
  are already generic — unchanged.

  **Naming incident, worth carrying into every other app's migration:** the
  first choice here was `db_schema`, which passed `validate_full()` and
  looked reasonable on paper but broke on the first real `spl3` build —
  the LLM generating `orm_model` read the *node id* `db_schema` as if it
  named a related database table, and added a hallucinated
  `db_schema_id: Mapped[int | None] = mapped_column(ForeignKey("db_schema.id"))`
  column, which then failed at `create_all()` with
  `NoReferencedTableError: ... could not find table 'db_schema'`. Same
  node-id-vs-symbol confusion class already seen elsewhere (mealie's
  `pipeline_state`, physics_simulator's `position_event` — see
  `apps/README.md`). `sqlite_schema` was considered as a fix and rejected —
  it collides with SQLite's own reserved system-table alias (`sqlite_schema`
  = `sqlite_master` since SQLite 3.33). Settled on **`data_schema`**: neutral,
  doesn't contain "db"/"sqlite", and doesn't read as an entity/table name.
  Also fixed `orm_model`'s `spec.interface`/`spec.contract` to close the gap
  that let the hallucination through in the first place — "EXACTLY these
  three columns, no others" plus an explicit "`data_schema` is a Pydantic
  module, NOT a database table, do not add a ForeignKey referencing it."
  **Renaming to `data_schema` was not sufficient by itself** — a second real
  `spl3` build with the renamed node still hallucinated a ForeignKey (this
  time to a guessed-pluralized `"data_schemas"` table), confirming the root
  cause isn't really the specific word chosen: an LLM generating an ORM
  model tends to treat *any* dependency listed in `composed_of` as something
  requiring a relationship column, independent of its name. Fixed at two
  levels instead of a third naming attempt:
  - **Framework-wide** (`spl/tech_profiles.py`'s `python_fastapi` profile,
    applies to every app, not just todo): added an explicit rule — never add
    a `ForeignKey`/`relationship()`/any column not listed in the node's own
    spec, and never infer one from another node's name or from
    `composed_of`.
  - **Node-specific** (`orm_model`'s own spec): rewrote `interface` from a
    prose bullet to a literal class body ("these are the ONLY THREE
    columns") and strengthened `contract` to say explicitly that this
    component has one table and zero relationships, full stop.

  **Takeaway for propagating this pattern to other apps (§2.5):** a
  de-prefixed node id still needs a naming sanity check ("could an LLM read
  this as an entity/table/reserved word"), but for any node that's an ORM
  model, also check whether `tech_profiles.py`'s new "no inferred
  relationships" rule alone is enough, or whether that node's own spec needs
  the same explicit-column-list treatment `orm_model` got here — especially
  for apps that *do* have real relationships (mealie, kanban, dispatch),
  where the model needs to say precisely which relationships are real so the
  "don't invent others" rule doesn't read as "never write a relationship."
- Update every `composed_of`/`depends_on` reference to the renamed ids
  (`todo_orm_model: composed_of: [sqlalchemy, todo_schema, db_connection]` ->
  `orm_model: composed_of: [sqlalchemy, data_schema, db_connection]`, and
  `crud_operations: composed_of: [todo_orm_model, ...]` -> `[orm_model,
  ...]`), and any prose in `spec.interface`/`contract`/`docs` that names the
  old id.
- `tech_profiles.py`: move this app's entries into
  `NODE_FILES["todo"] = {"data_schema": "app/schemas.py", "orm_model":
  "app/models.py", "db_connection": "app/database.py", "crud_operations":
  "app/crud.py", "api_routes": "app/main.py", "requirements":
  "requirements.txt", "readme": "README.md"}`.
- `api_routes`' `spec.contract` currently hardcodes `CORS enabled for
  :5173`. Per §1.2's config-module rule, change it to: "CORS allowed origin
  built from `FRONTEND_VITE_PORT`, imported from `app.config` — do NOT
  hardcode the port or the origin URL as a string literal." This is the one
  place in the todo app where a setting-derived value reaches generated
  code, so it's the concrete test case for the whole config-artifact
  mechanism in §1.2.
- **A fourth real bug, same "prose ≠ enforced constraint" root cause as the
  `orm_model` incidents above**, found only by actually running the built
  server: `db_connection`'s `defines:` field says "bound to todos.db", but
  `defines:` is descriptive prose, never fed to the LLM as a hard
  requirement the way `spec.interface`/`spec.contract` are — the generated
  `app/database.py` used the generic literal `DATABASE_URL =
  "sqlite:///./app.db"` instead. (This is almost certainly also the origin
  of the stray root-level `app.db` cleaned up separately — several *other*
  apps' generated `database.py` have the identical `app.db` fallback.)
  Fixed by moving the literal filename into `db_connection`'s
  `spec.interface`/`spec.contract` (`DATABASE_URL = "sqlite:///./todos.db"`,
  explicitly, plus a contract line ruling out "app.db" or any other name) —
  same fix shape as `orm_model`'s. **General takeaway for every other app's
  migration (§2.5):** any file-defining detail stated only in a node's
  `defines:` (not `spec.interface`/`spec.contract`) is not reliably honored —
  audit each node being migrated for this gap, not just the ones already
  known to be risky (ORM/table-shaped nodes).
- **A fifth real bug, a different flavor from the first four**: `crud.py`
  consistently imported/used `TodoRead` instead of `Todo` for every function
  (`get_todos`, `create_todo`, `toggle_todo`, `delete_todo`), even though
  `crud_operations`' own `spec.interface` already said `-> Todo` four times
  and never mentioned `TodoRead` anywhere — this wasn't a spec-precision gap
  like the first four bugs, it's the LLM overriding an explicit, correct
  spec with a generic FastAPI Create/Read naming convention from its own
  training prior. Fixed by adding an explicit "Imports: ... EXACTLY these
  class names ... there is no TodoRead/TodoOut/TodoResponse/TodoDTO" line to
  both `crud_operations`' and `api_routes`' `spec.interface` (the latter
  fixed preemptively, same schema dependency, not yet exercised by a real
  build at the time). **Takeaway for propagating this pattern:** even a node
  whose spec is already fully explicit and internally consistent can still
  get a class name silently swapped for a more "idiomatic" one — for any
  node importing a Pydantic/schema class by name in another app's migration,
  consider adding this same "these are the only names, do not invent a
  Read/Out/Response/DTO variant" line preemptively rather than waiting for
  it to fail a real build first.
- **A sixth bug, this one in the framework itself, not the blueprint**: the
  `orm_model` "TodoSchema" ImportError (bug #2 above) recurred on a later
  fresh build despite the spec fix already being in place — not a spec
  problem this time. `spl/tools.py::identify_broken_node()`, which
  `build_component.spl`'s repair loop uses to decide *which* generated file
  to hand back to the LLM for repair, only matched a hardcoded table of
  `test_X.py` filename substrings. A collection-time `ImportError` raised
  while loading `conftest.py` (before any individual test file even runs)
  contains no `test_X` substring at all, so the table never matched, and
  every one of the 3 repair attempts silently fell back to repairing the
  *capstone* (`api_routes` -> `app/main.py`) instead of the actually-broken
  `orm_model` -> `app/models.py` — wasting all 3 attempts on a file that was
  never wrong. Separately, that table's own "Todo backend"/"Todo frontend"
  entries still referenced the pre-rename node ids (`todo_schema`,
  `todo_orm_model`, `todo_list_component`, `todo_item_component`), which
  could never match post-rename anyway (the lookup requires the mapped
  `node_id` to exist in the current graph). Fixed both: updated those four
  entries to the renamed ids, and added a generic fallback — before falling
  back to the capstone, scan the traceback for any of `NODE_FILES[app_name]`'s
  known source file paths (reversed rel_path -> node_id) and pick the
  *last* one that appears, since an import chain's traceback lists the
  innocent importer before the actually-broken importee. Verified directly
  against the real failing traceback: correctly resolves to `orm_model`.
  **This fix is framework-wide, not todo-specific** — every other app
  benefits immediately, no per-app migration work needed for this part.
- **A seventh and eighth issue**, found by inspecting the successful build's
  actual output rather than waiting for another failure — worth doing after
  any build that passes, not just ones that fail:
  - **Real functional bug**: `api_client`'s generated `toggleTodo` used
    `method: 'PATCH'`, but the backend only registers `PUT /todos/{id}`
    (`api_routes`' own spec is correct) — would 405 in a real browser.
    Root cause: the HTTP method lives in `api_client`'s `ports:` block
    (`signature: "PUT /todos/{id} ..."`), but `spl/tools.py::_fmt_spec()`
    only formats the `spec:` dict for the code-gen prompt — `ports:` is
    never included at all, so the method was never actually communicated to
    the LLM; it fell back to the more common REST convention (PATCH for
    partial update) and guessed wrong. Not caught by `integrate_system.spl`
    because its acceptance tests hit the backend directly, never through the
    frontend (documented scope decision, see `integrate_system.spl`'s own
    header comment) — this class of bug needs a real browser or an actual
    frontend↔backend e2e test to surface at all. Fixed by adding the literal
    HTTP method to `api_client`'s `spec.interface`/`spec.contract` directly,
    same "structural metadata ≠ enforced constraint" root cause as bugs #4
    and #6 above (`ports:`, like `defines:`, is real schema but not part of
    what `_fmt_spec()` sends to the LLM).
  - **Contamination pattern, framework-wide fix**: `crud.py` had gratuitous
    module-level aliases (`orm_model = TodoModel`, `data_schema = Todo`) and
    `TodoList.vue` had a stray `<!-- item_component -->` comment — both are
    literal `composed_of` dependency-list node ids leaking into generated
    code as Python/TS identifiers or comments. Rather than patch each
    affected node's spec individually, added a general rule to all three
    `spl/tech_profiles.py` profiles' "Code style" sections: never use a
    graph/blueprint node id as a generated identifier, alias, or comment —
    use the real imported name.
  **Takeaway for propagating this pattern:** after a build passes, still
  read the generated output before calling the migration done — a passing
  test suite doesn't mean the generated code is clean or even fully correct
  (the PATCH/PUT bug passed every automated gate that exists today).

### 2.4 `apps/todo/blueprint/frontend.graph.yaml`

- Same root/blueprint/comment consolidation.
- `port: ${{ settings.FRONTEND_VITE_PORT }}`.
- Node id renames:
  | old | new |
  |---|---|
  | `todo_item_component` | `item_component` |
  | `todo_list_component` | `list_component` |

  `api_client`, `App_vue`, `main_ts`, `readme` unchanged.
- Update `composed_of` references (`todo_list_component: composed_of:
  [vuejs, typescript, todo_item_component, api_client]` -> `[..., item_component,
  api_client]`, `App_vue: composed_of: [..., todo_list_component]` -> `[...,
  list_component]`) and any prose mentioning the old ids.
- `tech_profiles.py`: `NODE_FILES["todo"]` (shared with backend, since
  `NODE_FILES` is now keyed by app not by profile) gains `"item_component":
  "src/components/TodoItem.vue"`, `"list_component":
  "src/components/TodoList.vue"`, `"api_client": "src/api.ts"`, `"App_vue":
  "src/App.vue"`, `"main_ts": "src/main.ts"`.
  (Filenames themselves — `TodoItem.vue`, `TodoList.vue` — are left
  app-descriptive; only the graph *node id* namespace changes, not the
  generated file names, since the file names already live inside
  `apps/todo/...` and don't need a second layer of namespacing.)

### 2.5 Propagating to other apps

Once todo app builds and its tests pass end-to-end (see Verification below),
repeat 2.1–2.4 per app, one at a time, using this file as the checklist:
add that app's own `apps/<app>/blueprint/settings.yaml`, consolidate
root/blueprint fields, replace hard-coded ports (and any other config
candidate) with `${{ settings.* }}` referencing that app's own settings file,
move that app's `NODE_FILES` entries under its own key, drop the app-name
prefix from node ids and update all internal references. `apps/expense`, `apps/kanban`, `apps/mealie`,
`apps/fullstack`, `apps/conduit`, `apps/dispatch` all currently follow the
same app-prefixed convention (`expense_schema`, `card_orm_model`,
`dispatch_schemas`, ...) except `apps/fullstack`, which already uses
unprefixed `orm_models` — treat fullstack as a second, smaller reference
point for what the end state should look like.

---

## Part 3 — Cache control (node-level: document; edge-level: new)

Confirmed with the user: keep the existing `use_cache` name (not `skip_cache`)
everywhere — including the CLI flag, which today is inconsistently named
`--skip_cache`.

### 3.1 Node-level `use_cache` — already implemented, was never documented

- `spl/tools.py::cache_get()` already honors an optional `use_cache: false`
  (default `true`) attribute on any `form.nodes.<id>` entry: if set, that
  node always misses cache and regenerates, independent of every other
  node's cache state.
- **Doc fix:** add a "Cache control" section to
  `docs/DEV/BUILD/blueprint-schema-v2.2.md` describing this attribute, its
  default, and the "force one broken node to regenerate without discarding
  the whole build" use case (already stated as a code comment in
  `tools.py:728-732` — promote it to the schema doc, which currently has no
  mention of caching at all).
- **CLI flag rename**, for naming consistency with the node attribute:
  - `spl/build_component.spl:219` — `@skip_cache TEXT DEFAULT 'false'` ->
    `@use_cache TEXT DEFAULT 'true'`.
  - `spl/tools.py:716` — rename `apply_skip_cache(cached_value, skip_cache)`
    to `apply_use_cache(cached_value: str, use_cache: str) -> str`, body
    becomes `return "miss" if use_cache.strip().lower() == "false" else
    cached_value` (polarity flip to match).
  - `build_component.spl:271` — `CALL apply_skip_cache(@code, @skip_cache)`
    -> `CALL apply_use_cache(@code, @use_cache)`.
  - Update any usage docs/examples that pass `-p skip_cache=true` to
    `-p use_cache=false`.

### 3.2 Edge-level `use_cache` — new, needs design (not yet implemented)

**Problem:** the cache key is `(node, spec, tech_profile)` only — it has no
knowledge of a node's dependencies. If node `A` regenerates with materially
different content but node `B` (`depends_on: [A]`) has an unchanged spec,
`B`'s cache still hits and `B` never sees `A`'s new shape. There's currently
no way to say "treat this one dependency as changed" without either bumping
`B`'s own spec text (indirect, easy to forget) or disabling `B`'s cache
entirely with `use_cache: false` (over-broad — invalidates `B` on every
build, not just when `A` actually changed).

**Design:** extend the explicit edge-object schema
(`form.edges: [{from, to, kind, comment}]`, already parsed by
`loader.py::_build_form_graph`) with an optional `use_cache: false` field
(default `true`), e.g.:

```yaml
form:
  edges:
    - from: db_schema
      to: orm_model
      kind: depends_on
      use_cache: false
      comment: force orm_model to regenerate whenever db_schema's edge is touched
```

- When `false`, the node at the edge's `to` end is forced to a cache miss —
  same effect as that node's own `use_cache: false`, but scoped to "this one
  upstream dependency changed," so an author can invalidate just the
  downstream nodes of one changed dependency instead of every node.
- **Caveat to document:** this only applies to edges authored via the
  explicit `form.edges:` list. The common shorthand
  (`node.composed_of: [a, b]` / `node.depends_on: [a, b]`) has no place to
  attach a per-edge attribute — a dependency that needs `use_cache: false`
  must be (also) declared as an explicit edge entry instead of relying on
  the shorthand list alone.
- **Implementation** (separate follow-up pass, not bundled with Part 1/2):
  `cache_get()` in `tools.py` gains a check over
  `graph.form_graph.in_edges(node, data=True)` — if any incoming edge has
  `data.get("use_cache") is False`, force a miss, in addition to the
  existing node-attribute check.
- **Scope note:** this is new functionality (§ heading says so on purpose) —
  it should land in `docs/DEV/BUILD/blueprint-schema-v2.2.md` as a schema
  addition alongside the node-level doc fix in §3.1, but the `tools.py`
  implementation is a separate, later change, not required before Parts 1–2
  can proceed.

---

## Verification

1. **Framework changes alone must not break existing apps.** After Part 1,
   before touching any app yaml:
   `pytest` (all tests, including `TestExampleFiles` in
   `tests/test_graph_lib.py`, which loads every real file under `apps/`) must
   still pass unmodified — this is the backward-compatibility check for the
   root-vs-blueprint fallback and the description/comment fallback.
2. **Settings interpolation.** Add a small unit test (or extend
   `tests/conftest.py`'s inline-YAML fixtures) that writes a temp
   `<tmpdir>/blueprint/settings.yaml` plus a sibling graph.yaml containing
   `${{ settings.BACKEND_FASTAPI_PORT }}`, loads it, and asserts the resolved
   value; also assert `ToolFailed` on an unresolvable key, and assert a
   graph.yaml with no sibling `settings.yaml` loads fine (settings are
   opt-in per app).
3. **Todo app end-to-end**, after 2.1–2.4:
   - `python -c "from graph_code import load_domain; load_domain('apps/todo/blueprint/main.graph.yaml')"`
     succeeds (imports resolve, no dangling node-id references).
   - `spl3 run spl/build_app.spl --tools spl/tools.py -p
     system_yaml=apps/todo/blueprint/main.graph.yaml --llm claude_cli
     -p output_dir=<scratch dir>` completes: both components build, and
     `integrate_system.spl`'s acceptance tests pass — this is the real proof
     that `NODE_FILES["todo"]` paths, the renamed node ids, and the
     `${{ settings.* }}` port substitution all resolved correctly end to end.
   - `check_port_consistency()` reports no drift between the system
     `ports:` block and each component's own `port:` (both now resolve
     through the same settings keys, so they can no longer silently diverge).
4. **No-regeneration property (the actual point of settings.yaml).** After
   the build above passes, change `FRONTEND_VITE_PORT` in
   `apps/todo/blueprint/settings.yaml` to a different value (e.g. `5174`)
   and re-run **only** `write_settings_config` (not `build_app.spl`, not any
   `GENERATE` call) to regenerate `backend/app/config.py`. Restart the
   backend and confirm CORS now allows the new origin — without any file
   under `backend/app/` other than `config.py` having changed. If this
   requires re-running the LLM build to take effect, §1.2's config-module
   design didn't get followed correctly in `api_routes`.
5. **Node-level `use_cache` rename (§3.1).** Run `build_component.spl` twice
   in a row for the same component with no yaml changes — second run should
   hit cache for every node (fast, no LLM calls). Then set `use_cache: false`
   on one node (e.g. `db_schema`) and re-run — only that node should miss and
   regenerate. Then run with `-p use_cache=false` (global) — every node
   should miss, confirming the renamed flag/function (`apply_use_cache`)
   wired correctly end to end.
