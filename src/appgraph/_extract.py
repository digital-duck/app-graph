"""Analysis + draft-generation logic behind `appgraph extract`.

The *extraction* half (regex/AST scanning of an existing repo) is
schema-agnostic and ported verbatim from
graph-driven-workflow/scripts/extract_path_b.py. The *generation* half is
rewritten from scratch to target app-graph's actual v2.1 blueprint
convention (apps/<app>/blueprint/{settings,main,backend,frontend}.graph.yaml
with a blueprint: block and ${{ settings.KEY }} port interpolation) instead
of the old repo's system.yaml + components/<name>/graph.yaml v1.0 flat
format.
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from textwrap import indent


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class RouteInfo:
    method: str
    path: str
    response_model: str
    status_code: int
    source_file: str


@dataclass
class SchemaClass:
    name: str
    base: str
    source_file: str
    fields: list[str] = field(default_factory=list)


@dataclass
class OrmClass:
    name: str
    tablename: str
    source_file: str
    columns: list[str] = field(default_factory=list)


@dataclass
class ServiceClass:
    name: str
    source_file: str
    methods: list[str] = field(default_factory=list)


@dataclass
class VueComponent:
    name: str
    source_file: str
    has_fetch: bool = False
    has_props: bool = False
    has_emits: bool = False
    has_mounted: bool = False


@dataclass
class ApiFunction:
    name: str
    http_method: str
    source_file: str


# ── Backend analysis (ported verbatim — schema-agnostic) ──────────────────────

_ROUTER_RE = re.compile(
    r'@(?:router|app)\.(get|post|put|patch|delete|head|options)\s*\(\s*["\']([^"\']+)["\']'
    r'(?:[^)]*status_code\s*=\s*(\d+))?'
    r'(?:[^)]*response_model\s*=\s*([^\s,)]+))?',
    re.IGNORECASE,
)


def extract_routes(routes_dir: Path, scope: list[str]) -> list[RouteInfo]:
    routes: list[RouteInfo] = []
    for py_file in sorted(routes_dir.rglob("*.py")):
        if "__pycache__" in str(py_file):
            continue
        if scope and not any(s in str(py_file) for s in scope):
            continue
        text = py_file.read_text(errors="replace")
        for m in _ROUTER_RE.finditer(text):
            routes.append(RouteInfo(
                method=m.group(1).upper(),
                path=m.group(2),
                response_model=m.group(4) or "unknown",
                status_code=int(m.group(3) or 200),
                source_file=str(py_file),
            ))
    return routes


_PYDANTIC_BASES = {"BaseModel", "MealieModel", "SQLModel"}


def extract_schemas(schema_dir: Path, scope: list[str]) -> list[SchemaClass]:
    schemas: list[SchemaClass] = []
    for py_file in sorted(schema_dir.rglob("*.py")):
        if "__pycache__" in str(py_file) or py_file.name.startswith("_"):
            continue
        if scope and not any(s in str(py_file) for s in scope):
            continue
        try:
            tree = ast.parse(py_file.read_text(errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            bases = [_base_name(b) for b in node.bases]
            if any(b in _PYDANTIC_BASES for b in bases):
                fields = [
                    n.targets[0].id if isinstance(n, ast.Assign) and n.targets
                    else n.target.id if isinstance(n, ast.AnnAssign) else None
                    for n in node.body
                    if isinstance(n, (ast.Assign, ast.AnnAssign))
                ]
                schemas.append(SchemaClass(
                    name=node.name,
                    base=bases[0] if bases else "BaseModel",
                    source_file=str(py_file),
                    fields=[f for f in fields if f],
                ))
    return schemas


_ORM_BASES = {"SqlAlchemyBase", "DeclarativeBase", "Base", "BaseMixins"}


def extract_orm_models(models_dir: Path, scope: list[str]) -> list[OrmClass]:
    models: list[OrmClass] = []
    for py_file in sorted(models_dir.rglob("*.py")):
        if "__pycache__" in str(py_file) or py_file.name.startswith("_"):
            continue
        if scope and not any(s in str(py_file) for s in scope):
            continue
        try:
            tree = ast.parse(py_file.read_text(errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                bases = [_base_name(b) for b in node.bases]
                if any(b in _ORM_BASES for b in bases) or "Model" in node.name:
                    tn = ""
                    cols = []
                    for stmt in node.body:
                        if isinstance(stmt, ast.Assign):
                            for t in stmt.targets:
                                if isinstance(t, ast.Name) and t.id == "__tablename__":
                                    if isinstance(stmt.value, ast.Constant):
                                        tn = stmt.value.s
                        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                            cols.append(stmt.target.id)
                    if tn or "Model" in node.name:
                        models.append(OrmClass(
                            name=node.name,
                            tablename=tn,
                            source_file=str(py_file),
                            columns=cols,
                        ))
    return models


def extract_services(services_dir: Path, scope: list[str]) -> list[ServiceClass]:
    services: list[ServiceClass] = []
    for py_file in sorted(services_dir.rglob("*.py")):
        if "__pycache__" in str(py_file):
            continue
        if scope and not any(s in str(py_file) for s in scope):
            continue
        try:
            tree = ast.parse(py_file.read_text(errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and (
                "Service" in node.name or "Repository" in node.name or "Repo" in node.name
            ):
                methods = [
                    n.name for n in node.body
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and not n.name.startswith("_")
                ]
                services.append(ServiceClass(
                    name=node.name,
                    source_file=str(py_file),
                    methods=methods,
                ))
    return services


# ── Frontend analysis (ported verbatim) ────────────────────────────────────────

_DEFINE_PROPS = re.compile(r"defineProps\s*[<(]")
_DEFINE_EMITS = re.compile(r"defineEmits\s*[<(]")
_ON_MOUNTED = re.compile(r"\bonMounted\b|\buseAsyncData\b|\buseFetch\b")
_API_CALL = re.compile(r"\.(get|post|put|patch|delete)\s*\(|axios\.|fetch\(|api\.")

_TS_FUNC = re.compile(r"export\s+(?:async\s+)?function\s+(\w+)")
_HTTP_METHOD_IN_FUNC = re.compile(r"\.(?:get|post|put|patch|delete)\s*\(", re.IGNORECASE)


def extract_components(components_dir: Path, scope: list[str]) -> list[VueComponent]:
    components: list[VueComponent] = []
    for vue_file in sorted(components_dir.rglob("*.vue")):
        if scope and not any(s.lower() in str(vue_file).lower() for s in scope):
            continue
        text = vue_file.read_text(errors="replace")
        name = vue_file.stem
        components.append(VueComponent(
            name=name,
            source_file=str(vue_file),
            has_fetch=bool(_API_CALL.search(text)),
            has_props=bool(_DEFINE_PROPS.search(text)),
            has_emits=bool(_DEFINE_EMITS.search(text)),
            has_mounted=bool(_ON_MOUNTED.search(text)),
        ))
    return components


def extract_api_functions(api_dir: Path, scope: list[str]) -> list[ApiFunction]:
    funcs: list[ApiFunction] = []
    for ts_file in sorted(api_dir.rglob("*.ts")):
        if scope and not any(s in str(ts_file) for s in scope):
            continue
        text = ts_file.read_text(errors="replace")
        for m in _TS_FUNC.finditer(text):
            func_name = m.group(1)
            pos = m.end()
            snippet = text[pos:pos + 200]
            http_m = _HTTP_METHOD_IN_FUNC.search(snippet)
            method = http_m.group(0).strip(" .(").upper() if http_m else "GET"
            funcs.append(ApiFunction(
                name=func_name,
                http_method=method,
                source_file=str(ts_file),
            ))
    return funcs


# ── Stack detection (ported verbatim) ──────────────────────────────────────────

def detect_stack(repo_path: Path) -> dict:
    stack: dict = {"backend": {}, "frontend": {}}
    pyproject = repo_path / "pyproject.toml"
    requirements = repo_path / "requirements.txt"
    if pyproject.exists():
        text = pyproject.read_text()
        stack["backend"]["file"] = "pyproject.toml"
        for pkg in ["fastapi", "flask", "django", "sqlalchemy", "alembic", "pydantic"]:
            if pkg in text.lower():
                stack["backend"][pkg] = True
    elif requirements.exists():
        text = requirements.read_text()
        stack["backend"]["file"] = "requirements.txt"
        for pkg in ["fastapi", "flask", "django", "sqlalchemy", "alembic", "pydantic"]:
            if pkg in text.lower():
                stack["backend"][pkg] = True
    pkg_json = repo_path / "frontend" / "package.json"
    if not pkg_json.exists():
        pkg_json = repo_path / "package.json"
    if pkg_json.exists():
        try:
            d = json.loads(pkg_json.read_text())
            deps = {**d.get("dependencies", {}), **d.get("devDependencies", {})}
            stack["frontend"]["packages"] = list(deps.keys())[:20]
            for fw in ["nuxt", "vue", "react", "svelte", "angular", "vite", "vitest", "vuetify"]:
                stack["frontend"][fw] = any(fw in k.lower() for k in deps)
        except Exception:
            pass
    return stack


_SOURCE_CONTEXT_PER_FILE_CHARS = 4000
_SOURCE_CONTEXT_TOTAL_CHARS = 60_000


def build_source_context(
    repo_path: Path,
    routes: list[RouteInfo],
    schemas: list[SchemaClass],
    orm_models: list[OrmClass],
    services: list[ServiceClass],
    components: list[VueComponent],
    api_funcs: list[ApiFunction],
) -> str:
    """Concatenate representative source file contents for the LLM semantic
    pass (`appgraph extract --llm`), capped so the prompt stays a reasonable
    size. Each distinct file the AST pass already touched is included once
    (routes/schemas/orm_models/services/components/api_funcs all carry the
    file they came from in `.source_file`), truncated per-file and capped in
    total — the AST pass already picked out the files that matter, this just
    hands their real contents to the LLM instead of the AST pass's summary.
    """
    seen: dict[str, None] = {}
    for group in (routes, schemas, orm_models, services, components, api_funcs):
        for item in group:
            seen.setdefault(item.source_file, None)

    parts: list[str] = []
    total = 0
    for source_file in seen:
        if total >= _SOURCE_CONTEXT_TOTAL_CHARS:
            break
        path = Path(source_file)
        try:
            text = path.read_text(errors="replace")
        except OSError:
            continue
        if len(text) > _SOURCE_CONTEXT_PER_FILE_CHARS:
            text = text[:_SOURCE_CONTEXT_PER_FILE_CHARS] + "\n... (truncated)"
        try:
            rel = path.relative_to(repo_path)
        except ValueError:
            rel = path
        header = f"--- {rel} ---\n"
        remaining = _SOURCE_CONTEXT_TOTAL_CHARS - total
        chunk = (header + text + "\n")[:remaining]
        parts.append(chunk)
        total += len(chunk)

    return "".join(parts)


def _base_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _snake(name: str) -> str:
    """PascalCase or camelCase -> snake_case"""
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def _identifier(path_segment: str) -> str:
    """First path segment -> a YAML-safe identifier.

    Route path segments can be path params like `{id:uuid}`, which contain
    `{`, `}`, and `:` — unsafe when written unquoted into a YAML flow
    sequence (`[foo, {id:uuid}]` parses as a flow mapping, not a scalar).
    """
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", path_segment).strip("_")
    return cleaned or "root"


# ── Draft generators — target app-graph's actual blueprint/ convention ───────

def generate_settings_yaml(app_name: str, backend_port: int, frontend_port: int) -> str:
    return f"""\
# ── App-scoped settings for {app_name} ───────────────────────────────────────
# Referenced from any *.graph.yaml under this blueprint/ directory as
# ${{{{ settings.KEY }}}} (see docs/DEV/BUILD/refactoring-plan-v1.md §1.2).
settings:
  - key: BACKEND_FASTAPI_PORT
    value: {backend_port}
    comment: FastAPI backend port
  - key: FRONTEND_VITE_PORT
    value: {frontend_port}
    comment: Vite dev server port
"""


def generate_main_graph(app_name: str, routes: list[RouteInfo]) -> str:
    groups: dict[str, list[RouteInfo]] = {}
    for r in routes:
        parts = r.path.strip("/").split("/")
        prefix = _identifier(parts[0]) if parts else "root"
        groups.setdefault(prefix, []).append(r)

    capstone_candidates = list(groups.keys())[:5]
    app_ids = [
        f"manage_{g}s" if not g.endswith("s") else f"manage_{g}"
        for g in capstone_candidates
    ]

    apps_block = ""
    for group_name, app_id in zip(capstone_candidates, app_ids):
        apps_block += f"""
  {app_id}:
    defines: |
      TODO: describe the {group_name} management use case
    needs:
      backend: [api_routes]
      frontend: []  # TODO: list frontend component(s) this exercises
    tier: 1
    spec:
      user_story: |
        TODO: as a user I can...
      contract: |
        TODO: golden path steps ({', '.join(r.method + ' ' + r.path for r in groups[group_name][:4])})
    verification: |
      TODO: acceptance test description
    docs: |
      TODO: what this exercises
"""

    capstone_id = f"manage_{app_name}"
    return f"""\
# ── Unified Duality Graph Schema v2.1 — Integrated Profile (Graph of Graphs) ─
# Draft generated by `appgraph extract` from an existing repo — every
# # TODO: marker needs a human (or LLM prompted with EXTRACTION.md +
# analysis.json) decision before this is buildable. See apps/todo/blueprint/
# main.graph.yaml for a worked reference of this exact shape.
domain: software/apps/{app_name}
target_languages: [python, typescript]
comment: |
  TODO: one or two sentences describing what {app_name} does.
capstone: {capstone_id}

blueprint:
  id: {app_name}_app
  schema_version: "2.2"
  graph_schema_version: "2.1"
  domain_type: integrated
  provenance: reverse
  parent_blueprint: null
  lineage: []

imports:
  - id: backend
    graph: ./backend.graph.yaml
    comment: |
      FastAPI REST API. Mandatory — the frontend cannot function without it.
  - id: frontend
    graph: ./frontend.graph.yaml
    comment: |
      Vue.js SPA. Already imports backend.graph.yaml itself to verify
      api_client's call contracts.

ports:
  backend: ${{{{ settings.BACKEND_FASTAPI_PORT }}}}
  frontend: ${{{{ settings.FRONTEND_VITE_PORT }}}}

form:
  nodes:
    {app_name}_app_shell:
      kind: component
      defines: "System integration shell: frontend consuming backend REST API via CORS"
      tier: 1
      depends_on: [backend, frontend]

    readme:
      kind: doc
      defines: "README.md: product-level overview, setup, and run instructions"
      composed_of: [{app_name}_app_shell]
      tier: 2
      spec:
        interface: |
          Output: README.md at the system root — plain Markdown, not code.
          CRITICAL: output ONLY the Markdown document itself.
        contract: |
          Must include: title + description, architecture, running the full
          system, and one line per application below.
        content_outline: |
          # <App name>
          One paragraph description.
          ## Architecture
          ## Running the full system
          ## Applications
      verification:
        node: |
          - README.md exists at the system root

function:
  exports:
    - name: {capstone_id}
      kind: port
      from: {app_name}_app_shell.main
      signature: "() -> void"
      comment: |
        Single entry point. Serves the frontend, starts the backend, and
        wires CORS between them. The system capstone.

applications:
{apps_block}
  {capstone_id}:
    defines: |
      TODO: full golden-path description — the user story every node above
      exists in service of.
    needs:
      applications: [{", ".join(app_ids)}]
    tier: 2
    capstone: true
    spec:
      user_story: |
        TODO: capstone user story
      contract: |
        TODO: golden path chaining the applications above
    verification: |
      TODO: full lifecycle test, state correct after reload
    docs: |
      The capstone — every node exists in service of this workflow

verification:
  - node: {app_name}_app_shell
    tool: appgraph build (build_app recipe, integration)
    checks:
      - CORS headers present on all backend responses
      - frontend loads without console errors
      - all system applications pass acceptance tests against live system
    docs: |
      - README.md (product-level) — see the `readme` node above
"""


def generate_backend_graph(
    app_name: str,
    schemas: list[SchemaClass],
    orm_models: list[OrmClass],
    services: list[ServiceClass],
    routes: list[RouteInfo],
) -> str:
    schema_files: dict[str, list[str]] = {}
    for s in schemas:
        key = Path(s.source_file).name
        schema_files.setdefault(key, []).append(s.name)

    model_files: dict[str, list[str]] = {}
    for m in orm_models:
        key = Path(m.source_file).name
        model_files.setdefault(key, []).append(m.name)

    route_lines = "\n".join(
        f"          {r.method:<6} {r.path:<40} -> {r.response_model}"
        for r in sorted(routes, key=lambda x: x.path)[:20]
    )

    schema_nodes = ""
    for fname, class_names in list(schema_files.items())[:4]:
        node_id = _snake(fname.replace(".py", ""))
        schema_nodes += f"""
    {node_id}:
      kind: concept
      defines: "Pydantic models from {fname}: {', '.join(class_names[:5])}{'...' if len(class_names) > 5 else ''}"
      composed_of: [pydantic, python]
      tier: 1
      spec:
        interface: |
          TODO: list key classes and their fields.
          Found: {', '.join(class_names)}
        contract: |
          TODO: document validation rules (field_validators, constraints, defaults).
          Key classes to contract: {', '.join(class_names[:3])}
      verification:
        node: |
          TODO: key correctness checks
        edge: |
          TODO: what downstream nodes depend on these types
      docs: |
        Source: {fname}
"""

    model_nodes = ""
    for fname, class_names in list(model_files.items())[:4]:
        node_id = _snake(fname.replace(".py", "").replace("_model", "")) + "_orm_model"
        model_nodes += f"""
    {node_id}:
      kind: module
      defines: "SQLAlchemy ORM model(s) from {fname}: {', '.join(class_names)}"
      composed_of: [sqlalchemy, db_connection]
      tier: 2
      spec:
        interface: |
          TODO: class name + __tablename__ + key columns.
          Found: {', '.join(class_names)}
        contract: |
          TODO: column types, relationships, constraints. MUST import Base
          from app.database — MUST NOT redefine it here. Never add a
          ForeignKey/relationship() not explicitly listed here.
      verification:
        node: |
          create_all() creates tables; roundtrip insert+select
        edge: |
          ORM column types match Pydantic schema field types
      docs: |
        Source: {fname}
"""

    services_note = ", ".join(s.name for s in services[:8]) or "(none detected)"

    return f"""\
# ── Unified Duality Graph Schema v2.1 — Software Profile ────────────────────
# Draft generated by `appgraph extract`. Every # TODO:/TODO: marker needs a
# human (or LLM) decision before this is buildable — see
# apps/todo/blueprint/backend.graph.yaml for a worked reference.
domain: software/backend/fastapi
target_languages: [python]
comment: |
  TODO: one or two sentences describing this backend's responsibility.

tech_profile: python_fastapi
port: ${{{{ settings.BACKEND_FASTAPI_PORT }}}}

blueprint:
  id: {app_name}_backend
  schema_version: "2.2"
  graph_schema_version: "2.1"
  domain_type: software
  provenance: reverse
  parent_blueprint: null
  lineage: []

form:
  primitives:
    python:
      defines: "Python 3.x runtime and standard library"
      tier: 0
      kind: config
    sqlite:
      defines: "SQLite embedded relational database"
      tier: 0
      kind: config
    fastapi:
      defines: "FastAPI web framework: routing, dependency injection, OpenAPI"
      tier: 0
      kind: config
    sqlalchemy:
      defines: "SQLAlchemy ORM: declarative models, session management"
      tier: 0
      kind: config
    pydantic:
      defines: "Pydantic v2: runtime data validation via type hints"
      tier: 0
      kind: config

  nodes:
    # ── Tier 1: Schemas ──────────────────────────────────────────────────
    # TODO: add one node per schema file (or group related schemas into one)
{schema_nodes}
    db_connection:
      kind: module
      defines: "SQLAlchemy engine and session factory"
      composed_of: [sqlalchemy, sqlite, python]
      tier: 1
      spec:
        interface: |
          get_db() -> Generator[Session, None, None]
        contract: |
          TODO: DATABASE_URL, engine args, session factory, Base, get_db().
      verification:
        node: |
          engine.connect() succeeds; session opens and closes
        edge: |
          SQLite file created at expected path
      docs: |
        FastAPI dependency — Depends(get_db)

    # ── Tier 2: ORM Models ───────────────────────────────────────────────
    # TODO: add one node per ORM model file or related model group
{model_nodes}
    # ── Tier 3: CRUD / repositories ─────────────────────────────────────
    # TODO: add one node per service/repo file; list all public methods in
    # spec.interface. Services/repos found in reference: {services_note}
    crud_operations:
      kind: module
      defines: |
        TODO: describe the CRUD layer — what entities, what operations
      composed_of: []  # TODO: list schema and ORM model nodes it depends on, db_connection
      tier: 3
      spec:
        interface: |
          TODO: function signatures for all CRUD operations
        contract: |
          TODO: slug-based vs id-based lookup? raises HTTPException(404)?
          pagination args? filter args?
      verification:
        node: |
          pytest with test DB: each function tested; 404 on unknown id
        edge: |
          returned models pass Pydantic validation

    # ── Tier 4: API routes (capstone) ───────────────────────────────────
    api_routes:
      kind: module
      defines: "FastAPI app exposing all {app_name} endpoints"
      composed_of: [fastapi, crud_operations]  # TODO: list other tier-3 nodes
      tier: 4
      spec:
        interface: |
          Routes extracted from reference:
{indent(route_lines, '')}
        contract: |
          CORS allowed origin built from FRONTEND_VITE_PORT, imported from
          app.config — do NOT hardcode the port or origin URL as a literal.
          MUST import the models module so SQLAlchemy registers every ORM
          model with Base BEFORE calling create_all(); MUST call
          Base.metadata.create_all(bind=engine) at module level. MUST import
          get_db from app.database — NEVER redefine locally.
          TODO: document route-specific contracts (status codes, response
          shapes, error cases).
      verification:
        node: |
          pytest TestClient: all endpoints return correct status + response shape
        edge: |
          CORS headers present; schema types match
      docs: |
        Public API surface — frontend api_client validated against this contract

    requirements:
      kind: doc
      defines: "requirements.txt: pinned pip dependencies for this component"
      composed_of: [python]
      tier: 1
      spec:
        interface: |
          Output: requirements.txt at the component root — plain pip
          requirements format, one package per line, not Python code.
        contract: |
          TODO: list the exact packages this backend needs, one per line,
          each with a minimum-version pin (>=).
      verification:
        node: |
          - requirements.txt exists at component root

    readme:
      kind: doc
      defines: "README.md: what this component does, how to install it, and its public API"
      composed_of: [api_routes]
      tier: 5
      spec:
        interface: |
          Output: README.md at the component root — plain Markdown, not code.
          CRITICAL: output ONLY the Markdown document itself.
        contract: |
          Must include: title + description, prerequisites, running the
          server, running tests, API summary.
      verification:
        node: |
          - README.md exists at component root

function:
  exports: []
  # TODO: one export per route the frontend consumes, e.g.:
  # - name: list_items
  #   kind: port
  #   from: api_routes.list_items
  #   signature: "GET /items -> Item[]"

verification: []
# TODO: one entry per code node, e.g.:
# - node: api_routes
#   backend: pytest
#   tests: tests/test_routes.py
"""


def generate_frontend_graph(
    app_name: str,
    components: list[VueComponent],
    api_funcs: list[ApiFunction],
) -> str:
    presentational = [c for c in components if not c.has_fetch and c.has_props]
    stateful = [c for c in components if c.has_fetch or c.has_mounted]

    pres_names = ", ".join(c.name for c in presentational[:8]) or "(none detected)"
    stat_names = ", ".join(c.name for c in stateful[:8]) or "(none detected)"
    api_func_names = ", ".join(f.name for f in api_funcs[:20]) or "(none detected)"

    return f"""\
# ── Unified Duality Graph Schema v2.1 — Software Profile ────────────────────
# Draft generated by `appgraph extract`. Every # TODO:/TODO: marker needs a
# human (or LLM) decision before this is buildable — see
# apps/todo/blueprint/frontend.graph.yaml for a worked reference.
#
# NOTE: if the reference repo uses a different frontend framework (Nuxt,
# React, ...), each node below must be re-specified against this stack —
# describe WHAT the reference component does, not HOW the reference code
# does it.
domain: software/frontend/vue
target_languages: [typescript]
comment: |
  TODO: one or two sentences describing this frontend's responsibility.
capstone: App_vue  # TODO: rename to this frontend's real stateful root component

tech_profile: vue_typescript
port: ${{{{ settings.FRONTEND_VITE_PORT }}}}

blueprint:
  id: {app_name}_frontend
  schema_version: "2.2"
  graph_schema_version: "2.1"
  domain_type: software
  provenance: reverse
  parent_blueprint: null
  lineage: []

imports:
  - id: backend
    graph: ./backend.graph.yaml
    comment: |
      The backend REST API is a mandatory dependency. api_client's calls
      are verified against backend's exported endpoint contracts.

form:
  primitives:
    vuejs:
      defines: "Vue 3 Composition API"
      tier: 0
      kind: config
    typescript:
      defines: "TypeScript language and compiler"
      tier: 0
      kind: config
    vite:
      defines: "Vite dev server and build tool"
      tier: 0
      kind: config

  nodes:
    # ── Tier 1: API client ───────────────────────────────────────────────
    api_client:
      kind: module
      defines: "TypeScript fetch wrappers for the {app_name} API"
      composed_of: [typescript]
      tier: 1
      spec:
        interface: |
          TODO: list all exported functions with types.
          API functions found in reference: {api_func_names}
        contract: |
          TODO: HTTP method + path for each function. Reads
          VITE_API_BASE_URL from the environment (see .env), not a
          hardcoded URL. All functions: if (!response.ok) throw new
          Error(`HTTP ${{response.status}}`).
      verification:
        node: |
          all functions exported; response types match backend schema
        edge: |
          HTTP methods and paths match backend api_routes contract
      docs: |
        Single HTTP coupling point

    # ── Tier 2: Presentational components ───────────────────────────────
    # TODO: add one node per presentational component.
    # Presentational candidates (no fetch, have props): {pres_names}

    # ── Tier 3: Stateful components ─────────────────────────────────────
    # TODO: add one node per stateful component (owns data refs, calls api).
    # Stateful candidates (has fetch/mounted): {stat_names}

    # ── Tier 4: App shell ───────────────────────────────────────────────
    App_vue:
      kind: component
      defines: "Root Vue component — mounts the top-level dashboard"
      composed_of: [vuejs, typescript]  # TODO: add capstone component
      tier: 4
      spec:
        interface: |
          template contains only the capstone component
        contract: |
          TODO: import the capstone component from './components/...'.
          No local state; no props.
      verification:
        node: |
          mount App; verify capstone rendered
        edge: |
          capstone is the only child; App passes no props
      docs: |
        Minimal shell

    main_ts:
      kind: module
      defines: "Vue application entry point"
      composed_of: [vuejs, typescript, App_vue]
      tier: 5
      spec:
        interface: |
          calls createApp(App).mount('#app')
        contract: |
          import {{ createApp }} from 'vue'
          import App from './App.vue'
          createApp(App).mount('#app')
      verification:
        node: |
          file imports from 'vue' and './App.vue'; calls createApp
        edge: |
          App exported from App.vue is the component passed to createApp
      docs: |
        Standard Vue 3 entry point — identical across every app under apps/

    readme:
      kind: doc
      defines: "README.md: what this component does, how to install it, and its public API"
      composed_of: [App_vue]
      tier: 6
      spec:
        interface: |
          Output: README.md at the component root — plain Markdown, not code.
          CRITICAL: output ONLY the Markdown document itself.
        contract: |
          Must include: title + description, prerequisites, running the
          dev server, running tests, component summary.
      verification:
        node: |
          - README.md exists at component root

function:
  calls: []
  # TODO: one call per backend endpoint api_client consumes, e.g.:
  # - id: client_calls_list_items
  #   from: api_client.listItems
  #   to: backend.list_items
  #   contract:
  #     consumer_requires: "GET /items -> Item[]"
  #     provider_guarantees: "GET /items -> Item[]"

verification: []
# TODO: one entry per code node, e.g.:
# - node: App_vue
#   frontend: vitest
#   tests: tests/App.spec.ts
"""


def generate_extraction_notes(
    app_name: str,
    repo_path: Path,
    stack: dict,
    routes: list[RouteInfo],
    schemas: list[SchemaClass],
    components: list[VueComponent],
    backend_port: int,
    frontend_port: int,
) -> str:
    """Companion planning doc to analysis.json — not a app-graph convention
    on its own (no BRIEF.md exists elsewhere in this repo), just a structured
    place to answer the open questions before authoring the blueprint for
    real. Delete once the blueprint is fully authored."""
    today = date.today().isoformat()

    fe = stack.get("frontend", {})
    if fe.get("nuxt"):
        fe_note = "Nuxt 3 (reference) -> this repo's target: Vue 3 + Vite (stack mismatch — reimplement against reference spec, not reference code)"
    elif fe.get("react"):
        fe_note = "React (reference) -> this repo's target: Vue 3 + Vite (stack mismatch — reimplement against reference spec, not reference code)"
    elif fe.get("vue"):
        fe_note = "Vue 3 + Vite (matched)"
    else:
        fe_note = "TODO: identify frontend framework"

    be = stack.get("backend", {})
    be_orm = "SQLAlchemy" if be.get("sqlalchemy") else "TODO: identify ORM"
    be_migrations = "Alembic" if be.get("alembic") else "create_all() at startup"

    route_groups: dict[str, list[RouteInfo]] = {}
    for r in routes:
        parts = r.path.strip("/").split("/")
        prefix = f"/{parts[0]}" if parts else "/"
        route_groups.setdefault(prefix, []).append(r)

    route_table = "| Method | Path | Status | Notes |\n|--------|------|--------|-------|\n"
    for r in sorted(routes, key=lambda x: x.path)[:30]:
        route_table += f"| {r.method} | `{r.path}` | {r.status_code} | |\n"
    if len(routes) > 30:
        route_table += f"| ... | +{len(routes) - 30} more routes | | |\n"

    schema_names = ", ".join(s.name for s in schemas[:20]) or "(none detected)"
    component_lines = "\n".join(
        f"  - {c.name} (tier {'3' if c.has_fetch else '2'})" for c in components[:15]
    ) or "  (none detected)"

    return f"""\
# Extraction notes — {app_name}

Generated by `appgraph extract` on {today} from `{repo_path}`. This is a
planning aid, not part of the buildable blueprint — delete it once
`blueprint/{{main,backend,frontend}}.graph.yaml` are fully authored (no more
`# TODO:` markers) and `appgraph validate-system` passes clean.

Companion to `analysis.json` in this same directory (raw extraction: every
route/schema/ORM model/service/component/API function found, with source
file paths).

---

## 1. App identity

**Name:** {app_name}
**Target layout:** `apps/{app_name}/blueprint/` (see docs/DEV/BUILD/refactoring-plan-v1.md)
**Reference repo:** `{repo_path}`
**Ports:** Backend `:{backend_port}`  Frontend `:{frontend_port}`

---

## 2. What the app does — functional description

TODO: Summarise the app's purpose in 2-3 paragraphs. Describe the primary
entities, the core workflow, and what makes this app's domain non-trivial
relative to prior apps under `apps/`.

---

## 3. User stories / use cases

| # | Use case name | User action | Backend response | Frontend response |
|---|--------------|-------------|-----------------|------------------|

TODO: one row per `applications:` entry in main.graph.yaml, derived from the
route groups below. Prioritise the 4-6 capstone use cases.

**System capstone:** TODO: name of the golden-path application

---

## 4. Data model

TODO: fill in from schema extraction. Key Pydantic models found:
{schema_names}

---

## 5. Backend stack

- ORM: {be_orm}
- Migrations: {be_migrations}
- Detected packages: {', '.join(k for k, v in be.items() if v is True and k != 'file') or 'TODO: none auto-detected'}

## 6. Frontend stack

{fe_note}

## 7. Routes found ({len(routes)} total)

{route_table}

## 8. Components found ({len(components)} total)

{component_lines}
"""


# ── Extraction caching ──────────────────────────────────────────────────────
# `appgraph extract --llm` runs a real LLM call over a subprocess and can take
# minutes — exactly the kind of step that dies to an agent/session timeout or
# a Ctrl-C. Without caching, rerunning `extract` after an interruption
# re-clones the repo, re-parses every source file, and re-pays for a fresh
# LLM call even though nothing about the repo or inputs changed. These
# helpers let `cli.extract` skip stages whose inputs are unchanged from a
# previous run — not a generic file cache, just enough that "rerun after
# interruption" resumes instead of restarting from scratch.

def dirs_signature(dirs: list[Path | None]) -> str:
    """Content fingerprint of the directories `extract` actually scans (not
    the whole repo — these are usually a handful of small subtrees), used to
    invalidate the AST-extraction cache when the source repo changes."""
    import hashlib

    h = hashlib.sha256()
    for d in sorted({d for d in dirs if d is not None}, key=str):
        if not d.exists():
            continue
        for p in sorted(d.rglob("*")):
            if not p.is_file():
                continue
            try:
                st = p.stat()
            except OSError:
                continue
            h.update(f"{p}:{st.st_size}:{st.st_mtime_ns}\n".encode())
    return h.hexdigest()[:16]


def cache_key(*parts: str) -> str:
    import hashlib

    h = hashlib.sha256()
    for part in parts:
        h.update(part.encode())
        h.update(b"\x00")
    return h.hexdigest()[:16]


def load_ast_cache(cache_dir: Path, key: str) -> dict | None:
    path = cache_dir / f"ast_{key}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def save_ast_cache(
    cache_dir: Path,
    key: str,
    stack: dict,
    routes: list[RouteInfo],
    schemas: list[SchemaClass],
    orm_models: list[OrmClass],
    services: list[ServiceClass],
    components: list[VueComponent],
    api_funcs: list[ApiFunction],
) -> None:
    from dataclasses import asdict

    cache_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "stack": stack,
        "routes": [asdict(r) for r in routes],
        "schemas": [asdict(s) for s in schemas],
        "orm_models": [asdict(m) for m in orm_models],
        "services": [asdict(s) for s in services],
        "components": [asdict(c) for c in components],
        "api_funcs": [asdict(f) for f in api_funcs],
    }
    (cache_dir / f"ast_{key}.json").write_text(json.dumps(data))


def ast_cache_to_objects(data: dict):
    """Reconstruct the extract_*() return types from load_ast_cache() output."""
    return (
        data["stack"],
        [RouteInfo(**d) for d in data["routes"]],
        [SchemaClass(**d) for d in data["schemas"]],
        [OrmClass(**d) for d in data["orm_models"]],
        [ServiceClass(**d) for d in data["services"]],
        [VueComponent(**d) for d in data["components"]],
        [ApiFunction(**d) for d in data["api_funcs"]],
    )


def load_llm_marker(cache_dir: Path, key: str) -> dict | None:
    path = cache_dir / f"llm_{key}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def save_llm_marker(cache_dir: Path, key: str, output_files: list[str]) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / f"llm_{key}.json").write_text(json.dumps({"output_files": output_files}))
