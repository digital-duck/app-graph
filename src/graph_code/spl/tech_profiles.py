"""Tech-stack profiles for GDW code generation.

Each profile is a style guide passed to the LLM as context, analogous to
style_profiles.py in concept-book. Profiles define language, framework,
conventions, and file-naming rules for a component.
"""
from __future__ import annotations

# ── Node → filename mapping per app ───────────────────────────────────────────
# Maps node_id to the relative path within the component output directory.
#
# Keyed by app_name (the apps/<app_name>/ path segment — see
# tools.py::_app_name_from_path), NOT by tech profile. It used to be keyed by
# profile, which meant every app sharing a profile shared one flat node-id
# namespace: a literal duplicate key (crud_operations, defined once for todo
# and again for fullstack, same value so silently harmless) and near-miss
# collisions (auth_schema vs auth_schemas) were only avoidable by luck. See
# docs/DEV/BUILD/refactoring-plan-v1.md §1.3.
#
# The "same relative path across apps" entries (readme, requirements,
# db_connection, crud_operations, api_routes for python_fastapi; readme,
# api_client, App_vue, main_ts for vue_typescript) are still genuinely
# shared — every app of that profile writes to the same conventional
# location — so they're composed from one baseline dict per profile instead
# of retyped per app.

_FASTAPI_DOC: dict[str, str] = {
    "readme": "README.md",
    "requirements": "requirements.txt",
}
_FASTAPI_COMMON: dict[str, str] = {
    **_FASTAPI_DOC,
    "db_connection": "app/database.py",
    "crud_operations": "app/crud.py",
    "api_routes": "app/main.py",
}
_VUE_COMMON: dict[str, str] = {
    "readme": "README.md",
    "api_client": "src/api.ts",
    "App_vue": "src/App.vue",
    "main_ts": "src/main.ts",
}
_LIBRARY_DOC: dict[str, str] = {
    "readme": "README.md",
    "requirements": "requirements.txt",
}

NODE_FILES: dict[str, dict[str, str]] = {
    "todo": {
        **_FASTAPI_COMMON,
        "data_schema": "app/schemas.py",
        "orm_model": "app/models.py",
        **_VUE_COMMON,
        "item_component": "src/components/TodoItem.vue",
        "list_component": "src/components/TodoList.vue",
    },
    "expense": {
        **_FASTAPI_COMMON,
        "data_schema": "app/schemas.py",
        "orm_model": "app/models.py",
        "report_aggregator": "app/reports.py",
        **_VUE_COMMON,
        "ExpenseForm": "src/components/ExpenseForm.vue",
        "ExpenseItem": "src/components/ExpenseItem.vue",
        "CategoryFilter": "src/components/CategoryFilter.vue",
        "ExpenseList": "src/components/ExpenseList.vue",
        "SummaryView": "src/components/SummaryView.vue",
        "ExpenseDashboard": "src/components/ExpenseDashboard.vue",
    },
    "kanban": {
        **_FASTAPI_COMMON,
        "data_schema": "app/schemas.py",
        "orm_model": "app/models.py",
        "board_view": "app/board.py",
        **_VUE_COMMON,
        "CardForm": "src/components/CardForm.vue",
        "KanbanCard": "src/components/KanbanCard.vue",
        "StatusSelect": "src/components/StatusSelect.vue",
        "KanbanColumn": "src/components/KanbanColumn.vue",
        "KanbanBoard": "src/components/KanbanBoard.vue",
    },
    "mealie": {
        **_FASTAPI_COMMON,
        "organizer_schema": "app/schemas/organizers.py",
        "recipe_schema": "app/schemas/recipes.py",
        "organizer_orm_models": "app/models/organizers.py",
        "recipe_orm_model": "app/models/recipes.py",
        "organizer_crud": "app/crud/organizers.py",
        "recipe_crud": "app/crud/recipes.py",
        **_VUE_COMMON,
        "recipe_api_client": "src/api.ts",  # overrides api_client for mealie
        "RecipeCard": "src/components/RecipeCard.vue",
        "OrganizerFilter": "src/components/OrganizerFilter.vue",
        "RecipeIngredientList": "src/components/RecipeIngredientList.vue",
        "RecipeForm": "src/components/RecipeForm.vue",
        "RecipeDetailView": "src/components/RecipeDetailView.vue",
        "RecipeList": "src/components/RecipeList.vue",
        "RecipeDashboard": "src/components/RecipeDashboard.vue",
    },
    "fullstack": {
        **_FASTAPI_COMMON,
        "data_schema": "app/schemas.py",
        "security_module": "app/security.py",
        "orm_model": "app/models.py",
        "auth_deps": "app/deps.py",
        **_VUE_COMMON,
        "auth_store": "src/auth.ts",
        "LoginForm": "src/components/LoginForm.vue",
        "ItemForm": "src/components/ItemForm.vue",
        "ItemList": "src/components/ItemList.vue",
        "ItemDashboard": "src/components/ItemDashboard.vue",
    },
    "fastapi": {
        **_FASTAPI_COMMON,
        "data_schema": "app/schemas.py",
        "orm_model": "app/models.py",
    },
    "dispatch": {
        **_FASTAPI_COMMON,
        "data_schema": "app/schemas.py",
        "orm_model": "app/models.py",
        "reference_crud": "app/crud_reference.py",
        "incident_crud": "app/crud_incidents.py",
    },
    "conduit": {
        **_FASTAPI_COMMON,
        "data_schema": "app/schemas.py",
        "security_module": "app/security.py",
        "auth_deps": "app/deps.py",
        "user_orm_model": "app/models/users.py",
        "article_orm_model": "app/models/articles.py",
        "user_crud": "app/crud/users.py",
        "article_crud": "app/crud/articles.py",
        **_VUE_COMMON,
        "auth_store": "src/auth.ts",
        "LoginForm": "src/components/LoginForm.vue",
        "ArticleCard": "src/components/ArticleCard.vue",
        "TagSidebar": "src/components/TagSidebar.vue",
        "ArticleList": "src/components/ArticleList.vue",
        "ArticleDetail": "src/components/ArticleDetail.vue",
        "ArticleForm": "src/components/ArticleForm.vue",
        "ConduitApp": "src/components/ConduitApp.vue",
    },
    "jwt_provider": {
        **_LIBRARY_DOC,
        "jwt_schemas": "app/schemas.py",
        "jwt_core": "app/core.py",
    },
    "etl_workflow": {
        **_LIBRARY_DOC,
        # workflow domain_type: one file per step
        "pipeline_state": "app/schemas.py",
        "fetch_data": "app/fetch_data.py",
        "transform_data": "app/transform_data.py",
        "load_data": "app/load_data.py",
        "error_handler": "app/error_handler.py",
    },
    "physics_app": {
        # apps/physics_app/ holds two components — physics_simulator and
        # auth_middleware — sharing this one app_name key; their node ids
        # don't collide.
        **_LIBRARY_DOC,
        "position_event": "app/schemas.py",
        "position_slider": "app/slider.py",
        "velocity_calculator": "app/calculator.py",
        "velocity_graph": "app/velocity_graph.py",
        "audit_logger": "app/audit_logger.py",
        "middleware": "app/middleware.py",
        "auth_attempt_logger": "app/auth_attempt_logger.py",
    },
    "todo1": {
        "database_config": "app/database.py",
        "schemas": "app/schemas.py",
        "orm_models": "app/models.py",
        "crud": "app/crud.py",
        "task_routes": "app/main.py",
        **_VUE_COMMON,
        "api_types": "src/types.ts",
        "chart_data": "src/chartData.ts",
        "todo_charts": "src/components/ToDoCharts.vue",
        "todo_filter": "src/components/ToDoFilter.vue",
        "todo_list": "src/components/ToDoList.vue",
        "todo_form": "src/components/ToDoForm.vue",
        "todo_root": "src/components/ToDo.vue",
    },
    "classical_mechanics": {
        # ConceptBook nodes — one lesson section per concept node
        "velocity": "lessons/velocity.md",
        "acceleration": "lessons/acceleration.md",
        "momentum": "lessons/momentum.md",
        "newtons_second_law": "lessons/newtons_second_law.md",
        "normal_modes": "lessons/normal_modes.md",
        "readme": "README.md",
    },
    "todo2A": {
        # Backend (python_fastapi) node ids are already flat filenames
        # matching write_node_file's app/{node}.py fallback exactly — no
        # entries needed here. Only the frontend (vue_typescript) needs
        # explicit routing, since without an entry every node fell back to
        # the profile-agnostic app/{node}.py default (see write_node_file's
        # docstring on the jwt_provider incident this is the same bug class as).
        **_VUE_COMMON,
        "api_client": "src/api.ts",
        "types": "src/types.ts",
        "auth_api": "src/api/auth.ts",
        "user_api": "src/api/user.ts",
        "task_api": "src/api/task.ts",
        "auth_store": "src/stores/auth.ts",
        "router": "src/router.ts",
        "layout_components": "src/components/Layout.vue",
        # layout_components' own spec (blueprint/frontend.graph.yaml) actually
        # describes four components — TheHeader, TheFooter, TheSpinner, PostIt
        # — but this is one graph node, and write_node_file/NODE_FILES only
        # ever route a node to a single output path (Layout.vue above covers
        # TheHeader; TheFooter was never generated either). TheSpinner and
        # PostIt are trivial, static, framework-generic (no props, no script
        # block at all) and are byte-identical to the original source repo's
        # own components/layout/{TheSpinner,PostIt}.vue — hand-copied in
        # directly rather than spending an LLM generation on them (2026-08-16).
        # These two keys are NOT real graph node ids (no LLM generation will
        # ever look them up via get_node_file), documented here only so their
        # placement is discoverable; TaskList.vue imports them as
        # './TheSpinner.vue' / './PostIt.vue' (same directory).
        "TheSpinner": "src/components/TheSpinner.vue",
        "PostIt": "src/components/PostIt.vue",
        "task_item": "src/components/TaskItem.vue",
        "task_list": "src/components/TaskList.vue",
        "auth_views": "src/views/AuthViews.vue",
        "task_view": "src/views/TaskView.vue",
        "app_shell": "src/main.ts",
    },
}

# ── Verification commands per profile ────────────────────────────────────────

VERIFY_CMDS: dict[str, dict] = {
    "python_fastapi": {
        "node": "python -m pytest tests/ -x -q 2>&1 | tail -5",
        "type": "python -m mypy app/ --ignore-missing-imports -q 2>&1 | tail -5",
    },
    "vue_typescript": {
        "node": "npm test 2>&1 | tail -10",
        "type": "npx vue-tsc --noEmit 2>&1 | tail -5",
    },
    "python_library": {
        "node": "python -m pytest tests/ -x -q 2>&1 | tail -5",
        "type": "python -m mypy app/ --ignore-missing-imports -q 2>&1 | tail -5",
    },
    "curriculum": {
        "node": "python -m pytest tests/ -x -q 2>&1 | tail -5",
    },
}

# ── Profile style guides ──────────────────────────────────────────────────────

PROFILES: dict[str, str] = {

"python_fastapi": """\
TECH PROFILE: Python / FastAPI / SQLAlchemy 2.0 / Pydantic v2 / SQLite

Language & runtime:
- Python 3.11+, strict typing throughout
- Use `from __future__ import annotations` at the top of every file

Framework conventions:
- Cross-module imports within app/ are always relative (`from .database import
  ...`, `from . import auth`), never absolute (`from database import ...`) —
  an absolute import breaks the moment app/ is run as a package (e.g. via
  `uvicorn app.main:app` or pytest importing `app.foo`), which is how every
  node's dependents actually consume it. Match the exact function/class/
  method names each dependency module exports, verbatim, per its own spec —
  don't rename, don't call an alternate-sounding method.
- If a config/settings node's own spec defines a `Settings(BaseSettings)`
  class with a module-level `settings = Settings()` singleton (the standard
  pydantic-settings pattern), every other node MUST consume it as
  `from .config import settings` then `settings.FIELD_NAME` — never invent
  bare module-level constants (`from .config import FIELD_NAME`) that don't
  exist. The config node's spec.interface is the source of truth for what
  it actually exports; don't assume an alternate access pattern.
- FastAPI for HTTP layer; Pydantic v2 for schemas
- Pydantic v2 imports: `from pydantic import BaseModel, ConfigDict, field_validator`
  - `ConfigDict` is the import; `model_config = ConfigDict(...)` is a class attribute — do NOT import `model_config`
  - ORM-mode models: `model_config = ConfigDict(from_attributes=True)` inside the class body
- SQLAlchemy 2.0 declarative style: `Mapped[T]` / `mapped_column()` — NOT legacy `Column()`
- `DeclarativeBase` from `sqlalchemy.orm` (NOT `declarative_base()`)
- Sync vs async is a per-app choice, not fixed by this profile — follow
  whichever pattern THIS node's own spec.interface actually declares:
    - sync: `sessionmaker`, plain `Session`, `Depends(get_db)`,
      `from collections.abc import Generator`, `Base.metadata.create_all(bind=engine)`
    - async: `async_sessionmaker[AsyncSession]`, `AsyncSession`,
      `Depends(get_async_session)`, `from collections.abc import AsyncGenerator`,
      `async with engine.begin() as conn: await conn.run_sync(Base.metadata.create_all)`
  Every node in the same component must agree with whichever one the spec
  uses — a node whose own spec doesn't specify must match its dependencies'
  actual (already-generated) signatures, not default to sync.
- NEVER add a `ForeignKey`, `relationship()`, or any column/attribute not
  explicitly listed in the node's own spec — in particular, do NOT infer a
  relationship from another node's name or from this node's `composed_of`/
  dependency list. A dependency being present in context (e.g. a Pydantic
  schema module) does NOT mean it is a related database table. If the spec's
  column/field list doesn't mention a relationship, the model has none.

Code style:
- No comments explaining WHAT the code does — names must speak for themselves
- One short comment only when the WHY is non-obvious
- No docstrings unless the function is part of a public API
- Imports: stdlib → third-party → local, each group alphabetically sorted
- All functions and methods must have full type annotations
- NEVER use a dependency graph/blueprint node id (e.g. "orm_model",
  "data_schema") as a Python identifier, module-level alias, or comment —
  those are internal graph vocabulary, not names that belong in the
  generated code. Import and use the real class/function name directly
  (e.g. `TodoModel`, `Todo`), never `orm_model = TodoModel` or a comment
  like `# data_schema`.

File structure (one node per file):
- schemas.py  → Pydantic models only
- database.py → engine, SessionLocal, Base, get_db
- models.py   → SQLAlchemy ORM models only
- crud.py     → pure data functions, no FastAPI imports except HTTPException
- reports.py  → read-only aggregation using sqlalchemy func.sum/func.count/GROUP BY; returns Pydantic models
- main.py     → FastAPI app, middleware, routes; MUST import models then call
                 Base.metadata.create_all(bind=engine) at module level before app = FastAPI()
                 so DB tables are created on startup — omitting this causes OperationalError: no such table
""",

"vue_typescript": """\
TECH PROFILE: Vue.js 3 / TypeScript / Vite / Composition API

Language & runtime:
- TypeScript with strict mode; no `any` types
- Vue 3 Composition API with `<script setup lang="ts">` syntax

Framework conventions:
- `defineProps<T>()` and `defineEmits<T>()` with type-only generics
- Reactive state via `ref<T>()` and `computed()`
- Lifecycle: `onMounted` for data fetching
- No Vuex / Pinia — local state only for this app

Code style:
- No comments explaining WHAT the code does
- One short comment only when the WHY is non-obvious
- PascalCase for component names and files
- camelCase for functions and variables
- Scoped styles (`<style scoped>`) in every component
- NEVER use a dependency graph/blueprint node id (e.g. "item_component",
  "api_client") as a variable name or comment — those are internal graph
  vocabulary, not names that belong in the generated code. Reference the
  actual imported component/function name directly.

File structure (one node per file):
- api.ts              → fetch wrappers only; exports TypeScript interfaces
- components/
    *Item.vue         → purely presentational; no fetch calls; emits only
    *List.vue         → receives items as props; forwards events; no fetch calls
    *Filter.vue       → v-model compatible (modelValue prop + update:modelValue emit); no internal state
    *Dashboard.vue    → stateful root; owns all refs; calls api; coordinates children via props/emits
    *Form.vue         → form inputs; calls one create api function; emits created on success
    *View.vue         → read-only display; receives data as props; no fetch calls
- App.vue             → mounts root dashboard component only; no local state
- main.ts             → createApp().mount() only
""",

"python_library": """\
TECH PROFILE: Plain Python library (no web framework, no ORM, no database)

Language & runtime:
- Python 3.11+, strict typing throughout
- Use `from __future__ import annotations` at the top of every file
- Standard library and pinned third-party dependencies only — no FastAPI, no
  SQLAlchemy, no Pydantic unless a node's own spec explicitly calls for it

Code style:
- No comments explaining WHAT the code does — names must speak for themselves
- One short comment only when the WHY is non-obvious
- No docstrings unless the function/class is part of the library's public API
- Imports: stdlib -> third-party -> local, each group alphabetically sorted
- All functions and methods must have full type annotations
- NEVER use a dependency graph/blueprint node id as a Python identifier,
  module-level alias, or comment — those are internal graph vocabulary, not
  names that belong in the generated code. Import and use the real
  class/function name directly.
- Prefer dataclasses (`@dataclass`) or `TypedDict` over ad-hoc dicts for
  structured return values, unless a node's spec says otherwise

File structure (one node per file, under app/):
- schemas.py → data types (dataclasses/TypedDicts) shared across the library
- core.py    → the library's actual logic — pure functions, no side effects
               beyond what the node's own contract explicitly describes
- For a `workflow` domain_type graph, each `kind: step` node instead maps to its
  own file named after the node id (e.g. fetch_data.py) — one pure function per
  file, matching the node's `phases.execute` signature from the graph.yaml (the
  `pre`/`post` sub-phases, when present, are folded into the same function as
  leading/trailing logic, not split into separate files)
""",

"curriculum": """\
TECH PROFILE: ConceptBook lesson section (Markdown prose, not code)

This is a curriculum node, not a software node — the output is a teaching
document, not an implementation. Analogous to build_concept_book.spl in the
ConceptBook project (see build_component.spl's own header comment).

Content conventions:
- Plain Markdown, one `##`-level section per part named in the node's
  spec.interface (e.g. "## Definition", "## Common Misconception")
- Derive results, don't just assert them — a definition given as a limit or a
  derivation must show the limiting/derivation steps, not skip to the answer
- Every worked numeric/symbolic example must be independently checkable
  (e.g. by sympy.diff, or by direct arithmetic) — state the check inline
  so a reader (or a test) can verify it without re-deriving from scratch
- Build on already-generated dependency lessons by name (e.g.
  "continuing the x(t) = t**2 example from velocity.md") rather than
  re-introducing the same example from nothing — the surrounding context
  passed to you contains those dependency files for exactly this reason
- No LaTeX rendering assumptions — use plain-text math (v = dx/dt, not a LaTeX
  fraction) so the lesson reads correctly in plain Markdown viewers

Code style (when a worked example includes a snippet):
- No comments explaining WHAT the code does — names must speak for themselves
- Short, self-contained sympy snippets only when they directly verify a claim
  made in the surrounding prose

File structure (one node per file):
- lessons/<node_id>.md → the lesson section for that concept node
""",
}


def get_profile(name: str) -> str:
    if name not in PROFILES:
        raise ValueError(f"Unknown tech profile '{name}'. Available: {list(PROFILES)}")
    return PROFILES[name]


def get_node_file(app_name: str, node_id: str) -> str | None:
    return NODE_FILES.get(app_name, {}).get(node_id)


def get_verify_cmd(profile: str, kind: str = "node") -> str:
    return VERIFY_CMDS.get(profile, {}).get(kind, "")
