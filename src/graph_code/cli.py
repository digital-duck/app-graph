"""grafcode — developer CLI for graph-code blueprint files.

Installed as the `grafcode` console script (see pyproject.toml's
[project.scripts]). Run `grafcode --help` for the full command list.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from . import graph_lib
from .exceptions import ToolFailed
from .loader import GraphDomain, load_domain

# The graph_code package directory itself — in an editable/dev install this
# is src/graph_code/, in a real `pip install grafcode` it's the copy inside
# site-packages/graph_code/. spl/ and graph-ide/ are shipped as package data
# (see pyproject.toml's [tool.setuptools.package-data]) specifically so these
# paths resolve the same way in both cases — no dependency on a git checkout.
_PACKAGE_ROOT = Path(__file__).resolve().parent
_SPL_ROOT = _PACKAGE_ROOT / "spl"
_GRAPH_IDE_ROOT = _PACKAGE_ROOT / "graph-ide"


def _spl3_bin() -> str:
    """Path to the `spl3` binary sitting next to the Python interpreter
    actually running this process (sys.executable), not a bare "spl3"
    resolved via inherited PATH. Two environments can each have their own
    spl-llm install (e.g. one editable/current, one a stale frozen copy);
    a bare "spl3" picks whichever happens to be first on PATH for whatever
    shell/service launched `grafcode`, which silently diverges from the
    environment grafcode itself is running in. Falling back to the bare
    name only if no sibling binary exists (e.g. an unusual install layout)."""
    candidate = Path(sys.executable).parent / "spl3"
    return str(candidate) if candidate.exists() else "spl3"


def _fail(msg: str) -> None:
    click.echo(f"ERROR: {msg}", err=True)
    sys.exit(1)


def _workspace_root() -> Path:
    """~/graph-code — the default working area for a pip-installed grafcode.

    Commands that write files default here (in named subfolders) rather than
    into this repo's own apps/, so an end user who only `pip install`ed
    graph-code always has somewhere writable to work, and repeat runs don't
    silently collide with checked-in example apps. Pass the relevant
    --*-dir/--out option explicitly to use this repo's apps/ instead (that's
    what graph-code's own development does).
    """
    return Path.home() / "graph-code"


def _workspace_dir(name: str) -> Path:
    """A named subfolder of _workspace_root(), created on demand."""
    d = _workspace_root() / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_report(text: str, out: str | None) -> None:
    """Shared --out handling for report/compare/drift: stdout by default, or
    a file (bare filenames resolve under ~/graph-code/report/) when given."""
    if out is None:
        click.echo(text)
        return
    out_path = Path(out)
    if not out_path.is_absolute() and len(out_path.parts) == 1:
        out_path = _workspace_dir("report") / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text if text.endswith("\n") else text + "\n")
    click.echo(f"Wrote report to {out_path}")


@click.group()
def main() -> None:
    """grafcode — validate, extract, build, and inspect graph-code blueprint apps."""


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------

@main.command(short_help="Validate a graph.yaml, and its whole system if it has imports.")
@click.argument("graph_yaml", type=click.Path(exists=True, dir_okay=False))
def validate(graph_yaml: str) -> None:
    """Validate a graph.yaml, and its whole system if it has imports.

    A component graph (no imports:) just runs validate_full() on itself. A
    system graph (has imports:, e.g. main.graph.yaml) additionally validates
    every imported component and checks cross-component call contracts
    (function.calls consumer_requires vs provider_guarantees) — no separate
    command needed, the imports: block is the signal.
    """
    try:
        graph = load_domain(graph_yaml)
    except ToolFailed as e:
        _fail(f"{graph_yaml}: {e}")
        return

    if not graph.imports:
        try:
            warnings = graph_lib.validate_full(graph)
        except ToolFailed as e:
            _fail(str(e))
            return
        for w in warnings:
            click.echo(f"WARNING: {w}")
        click.echo(f"OK — {graph_yaml} is valid ({len(warnings)} warning(s))")
        return

    errors: list[str] = []
    warnings = []

    try:
        for w in graph_lib.validate_full(graph):
            warnings.append(f"main: {w}")
    except ToolFailed as e:
        errors.append(f"main: {e}")

    base = Path(graph_yaml).parent
    imported: dict[str, GraphDomain] = {}
    for imp in graph.imports:
        alias = imp.get("id", "?")
        optional = imp.get("optional", False)
        comp_path = base / imp.get("graph", "")
        if not comp_path.exists():
            if optional:
                warnings.append(f"import {alias!r}: optional graph not found at {comp_path} (skipped)")
                continue
            errors.append(f"import {alias!r}: graph not found at {comp_path}")
            continue
        try:
            comp = load_domain(comp_path)
            imported[alias] = comp
            for w in graph_lib.validate_full(comp):
                warnings.append(f"{alias}: {w}")
        except ToolFailed as e:
            errors.append(f"import {alias!r} ({comp_path}): {e}")

    for violation in graph_lib.validate_needs(graph, imported):
        errors.append(violation)

    try:
        merged = graph_lib.resolve_imports(graph)
        for violation in graph_lib.check_call_contracts(merged):
            errors.append(violation)
    except ToolFailed as e:
        errors.append(f"resolve_imports: {e}")

    for w in warnings:
        click.echo(f"WARNING: {w}")

    if errors:
        for e in errors:
            click.echo(f"ERROR: {e}")
        sys.exit(1)

    click.echo(f"OK — {graph_yaml} and its imports are valid ({len(warnings)} warning(s))")


# ---------------------------------------------------------------------------
# order
# ---------------------------------------------------------------------------

@main.command(short_help="Print the topological node build order for a graph.yaml.")
@click.argument("graph_yaml", type=click.Path(exists=True, dir_okay=False))
def order(graph_yaml: str) -> None:
    """Print the topological node build order for a graph.yaml.

    This is the order build_component.spl generates nodes in.
    """
    try:
        graph = load_domain(graph_yaml)
        nodes = graph_lib.build_order(graph)
    except ToolFailed as e:
        _fail(str(e))
        return

    for i, node in enumerate(nodes):
        click.echo(f"{i:3d}  {node}")


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

@main.command(short_help="Print node/edge counts for a graph.yaml.")
@click.argument("graph_yaml", type=click.Path(exists=True, dir_okay=False))
@click.option("--out", default=None, metavar="FILE",
              help="Write to FILE instead of stdout. A bare filename (no "
                   "directory component) resolves under ~/graph-code/report/.")
def report(graph_yaml: str, out: str | None) -> None:
    """Print node/edge counts for a graph.yaml."""
    try:
        graph = load_domain(graph_yaml)
    except ToolFailed as e:
        _fail(str(e))
        return

    lines = [
        f"Graph id:     {graph.graph_id}",
        f"Domain type:  {graph.domain_type}",
        f"Domain:       {graph.domain or '?'}",
        f"Capstone:     {graph.capstone or '?'}",
        f"Primitives:   {len(graph.primitives)}",
        f"Nodes:        {len(graph.nodes)}",
        f"Applications: {len(graph.applications)}",
        f"Form edges:   {graph.form_graph.number_of_edges()}",
        f"Imports:      {len(graph.imports)}",
        f"Events:       {len(graph.events)}",
        f"Calls:        {len(graph.calls)}",
    ]
    _write_report("\n".join(lines), out)


# ---------------------------------------------------------------------------
# prettify
# ---------------------------------------------------------------------------

def _prettify_node(node) -> None:
    """Recursively walk a loaded YAML structure, normalizing every scalar.

    CommentedMap/CommentedSeq.__setitem__ re-wraps a plain str assigned over
    an existing ScalarString-typed entry back into that same quoted type (to
    preserve style on round-trip) — which would silently undo our unquoting.
    Assigning via the base dict/list __setitem__ bypasses that.
    """
    from ruamel.yaml.scalarstring import LiteralScalarString

    from ._yaml_style import normalize_chomping, prettify_scalar

    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(value, str):
                if isinstance(value, LiteralScalarString):
                    dict.__setitem__(node, key, normalize_chomping(value))
                else:
                    dict.__setitem__(node, key, prettify_scalar(value, in_list=False))
            else:
                _prettify_node(value)
    elif isinstance(node, list):
        for i, item in enumerate(node):
            if isinstance(item, str):
                if isinstance(item, LiteralScalarString):
                    list.__setitem__(node, i, normalize_chomping(item))
                else:
                    list.__setitem__(node, i, prettify_scalar(item, in_list=True))
            else:
                _prettify_node(item)


def _make_ruamel_yaml():
    from ruamel.yaml import YAML

    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096  # avoid line-wrapping unrelated long scalars
    yaml.indent(mapping=2, sequence=4, offset=2)
    return yaml


def _prettify_file(path: Path, write: bool) -> bool:
    """Returns True if the file has (or would have) changes."""
    import difflib
    import re
    from io import StringIO

    yaml = _make_ruamel_yaml()
    original_text = path.read_text()
    data = yaml.load(original_text)

    _prettify_node(data)

    buf = StringIO()
    yaml.dump(data, buf)
    # ruamel's dumper occasionally emits an extra blank line after a literal
    # block scalar that sits at the end of a mapping; these files otherwise
    # never use more than one blank line as a section separator.
    new_text = re.sub(r"\n{3,}", "\n\n", buf.getvalue())

    if new_text == original_text:
        return False

    diff = difflib.unified_diff(
        original_text.splitlines(keepends=True),
        new_text.splitlines(keepends=True),
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
    )
    sys.stdout.writelines(diff)

    if write:
        path.write_text(new_text)

    return True


def _discover_graph_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    return sorted(root.rglob("*.graph.yaml"))


@main.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option("--write", is_flag=True, help="rewrite files in place (default: print diff only)")
def prettify(path: Path, write: bool) -> None:
    """Rewrite *.graph.yaml scalars into a consistent style.

    PATH is a single *.graph.yaml file, or a directory (e.g. apps/) searched
    recursively. Prose fields become `|` block literals, one bullet per
    "; "-separated clause; bare identifiers/paths are left unquoted.
    """
    files = _discover_graph_files(path)
    if not files:
        click.echo(f"no *.graph.yaml found under {path}", err=True)
        sys.exit(1)

    changed = 0
    for f in files:
        if _prettify_file(f, write):
            changed += 1

    verb = "rewrote" if write else "would change"
    click.echo(f"\n{verb} {changed}/{len(files)} file(s)", err=True)


# ---------------------------------------------------------------------------
# new-app
# ---------------------------------------------------------------------------

_SETTINGS_YAML_TMPL = """\
# ── App-scoped settings for {app_name} ─{dashes}
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

_MAIN_GRAPH_TMPL = """\
# ── Unified Duality Graph Schema v2.1 — Integrated Profile (Graph of Graphs) ─
# Scaffolded by `grafcode new-app`. Fill in the TODOs below, then author
# backend.graph.yaml / frontend.graph.yaml.
domain: software/apps/{app_name}
target_languages: [python, typescript]
comment: |
  TODO: one or two sentences describing what {app_name} does.
capstone: manage_{app_name}  # TODO: rename to this app's own capstone application id

blueprint:
  id: {app_name}_app
  schema_version: "2.2"
  graph_schema_version: "2.1"
  domain_type: integrated
  provenance: authored
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
          CRITICAL: output ONLY the Markdown document itself — no preamble
          narration, no tool-call syntax.
        contract: |
          Must include, as Markdown sections:
          - Title + one-paragraph description of the whole app
          - Architecture: frontend calls backend over REST, CORS enabled
          - Running the full system
          - Applications: one line per application from this graph's
            `applications:` block
        content_outline: |
          # <App name>
          One paragraph description.
          ## Architecture
          ## Running the full system
          ## Applications
      verification:
        node: |
          - README.md exists at the system root
          - contains headings for architecture, running the full system,
            and applications

function:
  exports:
    - name: manage_{app_name}  # TODO: rename to match capstone: above
      kind: port
      from: {app_name}_app_shell.main
      signature: "() -> void"
      comment: |
        Single entry point. Serves the frontend, starts the backend, and
        wires CORS between them. The system capstone.

# TODO: author one applications: entry per user-facing acceptance test,
# then a final capstone entry (capstone: true) chaining them into a golden
# path — see apps/todo/blueprint/main.graph.yaml for a worked example.
applications: {{}}

verification:
  - node: {app_name}_app_shell
    tool: integrate_system.spl
    checks:
      - CORS headers present on all backend responses
      - frontend loads without console errors
      - all system applications pass acceptance tests against live system
    docs: |
      - README.md (product-level) — see the `readme` node above
"""

_BACKEND_GRAPH_TMPL = """\
# ── Unified Duality Graph Schema v2.1 — Software Profile ────────────────────
# Scaffolded by `grafcode new-app`. Fill in the TODOs below — see
# apps/todo/blueprint/backend.graph.yaml for a worked example of this shape.
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
  provenance: authored
  parent_blueprint: null
  lineage: []

form:
  primitives:
    python:
      defines: "Python 3.x runtime and standard library"
      tier: 0
      kind: config
    fastapi:
      defines: "FastAPI web framework: routing, dependency injection, OpenAPI"
      tier: 0
      kind: config
    sqlalchemy:
      defines: "SQLAlchemy 2.0 ORM: declarative models, sessions"
      tier: 0
      kind: config
    pydantic:
      defines: "Pydantic v2: runtime data validation via type hints"
      tier: 0
      kind: config
    sqlite:
      defines: "SQLite embedded relational database"
      tier: 0
      kind: config

  nodes:
    requirements:
      kind: doc
      defines: "requirements.txt: pinned pip dependencies for this component"
      composed_of: [python, fastapi, sqlalchemy, pydantic]
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

    # TODO: author data_schema / db_connection / orm_model / crud_operations /
    # api_routes nodes here — see apps/todo/blueprint/backend.graph.yaml for
    # a worked 7-node example of this exact shape (schema -> db -> ORM ->
    # CRUD -> routes -> readme).

    readme:
      kind: doc
      defines: "README.md: what this component does, how to install it, and its public API"
      composed_of: [requirements]
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

_FRONTEND_GRAPH_TMPL = """\
# ── Unified Duality Graph Schema v2.1 — Software Profile ────────────────────
# Scaffolded by `grafcode new-app`. Fill in the TODOs below — see
# apps/todo/blueprint/frontend.graph.yaml for a worked example of this shape.
domain: software/frontend/vue
target_languages: [typescript]
comment: |
  TODO: one or two sentences describing this frontend's responsibility.
capstone: App_vue  # TODO: rename to this frontend's real top-level component

tech_profile: vue_typescript
port: ${{{{ settings.FRONTEND_VITE_PORT }}}}

blueprint:
  id: {app_name}_frontend
  schema_version: "2.2"
  graph_schema_version: "2.1"
  domain_type: software
  provenance: authored
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
    # TODO: author api_client / <feature> components / App_vue / main_ts /
    # readme nodes here — see apps/todo/blueprint/frontend.graph.yaml for a
    # worked example of this exact shape.
    readme:
      kind: doc
      defines: "README.md: what this component does, how to install it, and its public API"
      composed_of: [vuejs]
      tier: 5
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

_BACKEND_CONFTEST_TMPL = """\
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = "sqlite:///./test_{app_name}.db"

test_engine = create_engine(TEST_DATABASE_URL, connect_args={{"check_same_thread": False}})
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()
"""

_PACKAGE_JSON_TMPL = """\
{{
  "name": "{app_name}-frontend",
  "version": "0.1.0",
  "private": true,
  "scripts": {{
    "dev": "vite --port {frontend_port}",
    "build": "vue-tsc --noEmit && vite build",
    "test": "vitest run",
    "preview": "vite preview"
  }},
  "dependencies": {{
    "vue": "^3.4.0"
  }},
  "devDependencies": {{
    "@vitejs/plugin-vue": "^5.0.0",
    "@vue/test-utils": "^2.4.0",
    "typescript": "^5.3.0",
    "vite": "^5.0.0",
    "vitest": "^1.0.0",
    "vue-tsc": "^2.0.0",
    "jsdom": "^24.0.0"
  }}
}}
"""

_VITE_CONFIG_TMPL = """\
import {{ defineConfig }} from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({{
  plugins: [vue()],
  server: {{
    port: {frontend_port},
    proxy: {{
      // TODO: proxy paths matching this app's actual API routes
      "/api": "http://localhost:{backend_port}",
    }},
  }},
  test: {{
    environment: "jsdom",
    globals: true,
  }},
}});
"""

_TSCONFIG_TMPL = """\
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "jsx": "preserve",
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "skipLibCheck": true
  },
  "include": ["src/**/*", "tests/**/*"]
}
"""

_INDEX_HTML_TMPL = """\
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{title}</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.ts"></script>
  </body>
</html>
"""

_APP_README_TMPL = """\
# {app_name}

TODO: one-paragraph description of what this app does.

## Status

Scaffolded by `grafcode new-app` — blueprint/ contains stub graph.yaml
files with `# TODO:` markers. Nothing is buildable yet.

## Next steps

1. Fill in `blueprint/main.graph.yaml`'s `comment:`/`applications:`
2. Author `blueprint/backend.graph.yaml`'s data/db/orm/crud/routes nodes
3. Author `blueprint/frontend.graph.yaml`'s api_client/component nodes
4. Register node -> file mappings in `spl/tech_profiles.py`'s `NODE_FILES["{app_name}"]`
5. `grafcode validate blueprint/main.graph.yaml`
6. Author test files under `backend/tests/` and `frontend/tests/`
7. `spl3 run spl/build_app.spl --tools spl/tools.py -p system_yaml=apps/{app_name}/blueprint/main.graph.yaml --llm claude_cli`
"""


def _write_new(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


@main.command("new-app")
@click.argument("app_name")
@click.argument("backend_port", type=int)
@click.argument("frontend_port", type=int)
@click.option(
    "--apps-dir",
    default="apps",
    show_default=True,
    help="Root directory apps live under.",
)
def new_app(app_name: str, backend_port: int, frontend_port: int, apps_dir: str) -> None:
    """Scaffold a new integrated (backend+frontend) app skeleton.

    Creates apps/<app_name>/blueprint/{settings,main,backend,frontend}.graph.yaml
    stubs plus backend/frontend test dirs and the frontend's npm/vite project
    scaffold — the same convention every other app under apps/ follows (see
    apps/README.md). Exits with an error if the target directory already
    exists and is non-empty (no silent overwrites).
    """
    app_root = Path(apps_dir) / app_name
    if app_root.exists() and any(app_root.iterdir()):
        _fail(f"{app_root} already exists and is not empty")
        return

    blueprint = app_root / "blueprint"
    _write_new(
        blueprint / "settings.yaml",
        _SETTINGS_YAML_TMPL.format(
            app_name=app_name,
            dashes="─" * max(1, 40 - len(app_name)),
            backend_port=backend_port,
            frontend_port=frontend_port,
        ),
    )
    _write_new(blueprint / "main.graph.yaml", _MAIN_GRAPH_TMPL.format(app_name=app_name))
    _write_new(blueprint / "backend.graph.yaml", _BACKEND_GRAPH_TMPL.format(app_name=app_name))
    _write_new(blueprint / "frontend.graph.yaml", _FRONTEND_GRAPH_TMPL.format(app_name=app_name))

    _write_new(
        app_root / "backend" / "tests" / "conftest.py",
        _BACKEND_CONFTEST_TMPL.format(app_name=app_name),
    )
    _write_new(
        app_root / "frontend" / "package.json",
        _PACKAGE_JSON_TMPL.format(app_name=app_name, frontend_port=frontend_port),
    )
    _write_new(
        app_root / "frontend" / "vite.config.ts",
        _VITE_CONFIG_TMPL.format(frontend_port=frontend_port, backend_port=backend_port),
    )
    _write_new(app_root / "frontend" / "tsconfig.json", _TSCONFIG_TMPL)
    _write_new(
        app_root / "frontend" / "index.html",
        _INDEX_HTML_TMPL.format(title=app_name.replace("_", " ").title()),
    )
    _write_new(app_root / "frontend" / ".env", f"VITE_API_BASE_URL=http://localhost:{backend_port}\n")
    (app_root / "frontend" / "tests").mkdir(parents=True, exist_ok=True)
    (app_root / "frontend" / "src" / "components").mkdir(parents=True, exist_ok=True)

    _write_new(app_root / "README.md", _APP_README_TMPL.format(app_name=app_name))

    click.echo(f"Scaffolded {app_root}/")
    click.echo(f"  blueprint/settings.yaml   (ports {backend_port}/{frontend_port})")
    click.echo("  blueprint/main.graph.yaml")
    click.echo("  blueprint/backend.graph.yaml")
    click.echo("  blueprint/frontend.graph.yaml")
    click.echo("  backend/tests/conftest.py")
    click.echo("  frontend/{package.json,vite.config.ts,tsconfig.json,index.html,.env,tests/,src/components/}")
    click.echo("  README.md")
    click.echo()
    click.echo("Next steps (see README.md):")
    click.echo(f"  1. Fill in blueprint/main.graph.yaml's comment:/applications:")
    click.echo(f"  2. Author blueprint/backend.graph.yaml's data/db/orm/crud/routes nodes")
    click.echo(f"  3. Author blueprint/frontend.graph.yaml's api_client/component nodes")
    click.echo(f'  4. Register node -> file mappings in spl/tech_profiles.py\'s NODE_FILES["{app_name}"]')
    click.echo(f"  5. grafcode validate {blueprint}/main.graph.yaml")


# ---------------------------------------------------------------------------
# extract
# ---------------------------------------------------------------------------

@main.command(short_help="Analyze an existing repo and draft blueprint/ artifacts.")
@click.option("--repo-path", default=None, type=click.Path(exists=True, file_okay=False, path_type=Path),
              help="Local repo to analyze. Mutually exclusive with --repo-url.")
@click.option("--repo-url", default=None, help="Git URL to clone and analyze. Mutually exclusive with --repo-path.")
@click.option("--output-dir", default=None, type=click.Path(path_type=Path),
              help="Root to write into. Defaults to ~/graph-code/output/<app-name> "
                   "(created if missing) so a repeat extraction never silently "
                   "overwrites an existing app — pass an explicit path (e.g. this "
                   "repo's own apps/<app-name>) to write elsewhere.")
@click.option("--app-name", required=True)
@click.option("--scope", default="", help="Comma-separated filter tokens (e.g. 'recipe,organizer')")
@click.option("--backend-routes-dir", default="", help="Relative path to routes dir (auto-detected if unset)")
@click.option("--backend-schema-dir", default="", help="Relative path to schema dir")
@click.option("--backend-models-dir", default="", help="Relative path to ORM models dir")
@click.option("--backend-services-dir", default="", help="Relative path to services dir")
@click.option("--frontend-components-dir", default="", help="Relative path to Vue components dir")
@click.option("--frontend-api-dir", default="", help="Relative path to TS API client dir")
@click.option("--backend-port", type=int, default=8000)
@click.option("--frontend-port", type=int, default=5173)
@click.option("--llm", default="", help="ADAPTER:MODEL (e.g. claude_cli:claude-sonnet-4-6). "
              "If set, runs a semantic pass after the AST pass: classifies the app's shape "
              "(integrated / single-component / no fit) and calls compile_blueprint.spl to "
              "draft real spec.interface/spec.contract content instead of TODO: stubs. "
              "Omit for AST-only extraction (unchanged, no LLM calls, no cost).")
@click.option("--llm-timeout", type=int, default=None, metavar="SECONDS",
              help="Per-call timeout for the --llm semantic pass, forwarded to "
                   "`spl3 run --llm-timeout`. Adapters that don't accept a 'timeout' "
                   "kwarg ignore it. Default is the adapter's own default "
                   "(claude_cli: 300s, or 600s if it uses tools).")
@click.option("--skip-cache", is_flag=True,
              help="Don't reuse OUTPUT_DIR/.grafcode_cache content: always re-clone "
                   "(for --repo-url), re-scan the repo, and re-run the --llm pass instead "
                   "of trusting a previous run's cached clone/AST/marker. This run still "
                   "*writes* fresh cache entries as it goes (including --persistence "
                   "checkpoints), so a crash partway through remains resumable on retry — "
                   "it only skips reading stale content, it doesn't disable saving.")
@click.option("--persistence", default="sqlite", show_default=True,
              type=click.Choice(["sqlite", "postgres", "dbos", "none"]),
              help="Durable-execution backend forwarded to the --llm pass's `spl3 run "
                   "--persistence ... --workflow-id ...` (checkpoints every GENERATE/CALL "
                   "step). This is a *finer* granularity than the OUTPUT_DIR/.grafcode_cache "
                   "marker above: the marker skips re-running compile_blueprint.spl at all "
                   "once it has fully succeeded, while --persistence lets a run that died "
                   "partway through (e.g. attempt 3 of a repair loop, after attempts 0-1 "
                   "already succeeded) resume from its last checkpoint instead of redoing "
                   "every step. Active even with --skip-cache. 'none' disables it. Ignored "
                   "without --llm.")
def extract(
    repo_path: Path | None,
    repo_url: str | None,
    output_dir: Path,
    app_name: str,
    scope: str,
    backend_routes_dir: str,
    backend_schema_dir: str,
    backend_models_dir: str,
    backend_services_dir: str,
    frontend_components_dir: str,
    frontend_api_dir: str,
    backend_port: int,
    frontend_port: int,
    llm: str,
    llm_timeout: int | None,
    skip_cache: bool,
    persistence: str,
) -> None:
    """Analyze an existing repo and generate draft blueprint/ artifacts.

    Scans the repo (--repo-path or --repo-url) for FastAPI routes, Pydantic
    schemas, SQLAlchemy ORM models, service/repository classes, Vue
    components, and TS API functions, then writes analysis.json,
    EXTRACTION.md, and blueprint/{settings,main,backend,frontend}.graph.yaml
    stubs under OUTPUT_DIR.

    Without --llm: stubs carry `# TODO:`/`TODO:` markers where human or LLM
    judgment is required — nothing is buildable until those are resolved and
    `grafcode validate` passes clean. With --llm: after the same AST
    pass, a semantic pass reads representative source file contents,
    classifies the app's shape, and calls spl/compile_blueprint.spl to
    produce real spec content (still only structurally validated, not a
    claim of correctness — review before building either way).

    Resumable at two granularities. Coarse: OUTPUT_DIR/.grafcode_cache/
    persists the cloned repo (for --repo-url), the AST-extraction results,
    and a marker for a fully-completed --llm pass — a --repo-url clone that
    takes minutes, or a repeat `extract` invocation after the --llm pass
    already succeeded, isn't redone. Fine: the --llm pass itself runs as a
    durable spl3 workflow (see --persistence) that checkpoints every
    GENERATE/CALL step, so a run that dies partway through (e.g. attempt 3 of
    a repair loop, after attempts 0-1 already got real LLM responses) resumes
    from its last checkpoint instead of re-paying for every attempt. Pass
    --skip-cache to force a fresh run at both granularities — it still writes
    (and can resume from) fresh cache/checkpoints, it just won't read stale
    ones from a previous run.
    """
    from . import _extract as ex

    if bool(repo_path) == bool(repo_url):
        raise click.UsageError("Pass exactly one of --repo-path or --repo-url.")

    if output_dir is None:
        output_dir = _workspace_dir("output") / app_name
    out = output_dir if output_dir.is_absolute() else Path.cwd() / output_dir
    cache_dir = out / ".grafcode_cache"
    scope_list = [s.strip() for s in scope.split(",") if s.strip()]

    if repo_url:
        import shutil
        import subprocess

        clone_dir = cache_dir / "repo_clone"
        if not skip_cache and (clone_dir / ".git").exists():
            click.echo(f"[extract] using cached clone at {clone_dir} (--skip-cache to force a fresh clone)")
            repo = clone_dir
        else:
            shutil.rmtree(clone_dir, ignore_errors=True)
            clone_dir.parent.mkdir(parents=True, exist_ok=True)
            click.echo(f"[extract] cloning {repo_url} -> {clone_dir}")
            proc = subprocess.run(["git", "clone", "--depth", "1", repo_url, str(clone_dir)],
                                   capture_output=True, text=True, timeout=300)
            if proc.returncode != 0:
                raise click.ClickException(f"git clone failed: {proc.stderr.strip()}")
            repo = clone_dir
    else:
        repo = repo_path.expanduser().resolve()  # type: ignore[union-attr]

    click.echo(f"[extract] repo: {repo}")
    click.echo(f"[extract] output: {out}")
    click.echo(f"[extract] scope: {scope_list or '(all)'}")

    def _find_dir(candidates: list[str], override: str) -> Path | None:
        if override:
            p = repo / override
            return p if p.exists() else None
        for c in candidates:
            p = repo / c
            if p.exists():
                return p
        return None

    routes_dir = _find_dir(["routes", "api", "app/routes", "src/routes"], backend_routes_dir)
    schema_dir = _find_dir(["schema", "schemas", "app/schemas", "src/schemas"], backend_schema_dir)
    models_dir = _find_dir(["models", "db/models", "app/models"], backend_models_dir)
    services_dir = _find_dir(["services", "repos"], backend_services_dir)
    components_dir = _find_dir(
        ["frontend/app/components", "frontend/src/components", "src/components", "app/components"],
        frontend_components_dir,
    )
    api_dir = _find_dir(
        ["frontend/app/lib/api", "frontend/src/api", "src/api", "frontend/src/lib"],
        frontend_api_dir,
    )

    click.echo(f"[extract] routes_dir:     {routes_dir}")
    click.echo(f"[extract] schema_dir:     {schema_dir}")
    click.echo(f"[extract] models_dir:     {models_dir}")
    click.echo(f"[extract] services_dir:   {services_dir}")
    click.echo(f"[extract] components_dir: {components_dir}")
    click.echo(f"[extract] api_dir:        {api_dir}")

    ast_key = ex.cache_key(
        str(routes_dir), str(schema_dir), str(models_dir),
        str(services_dir), str(components_dir), str(api_dir),
        ex.dirs_signature([routes_dir, schema_dir, models_dir, services_dir, components_dir, api_dir]),
        ",".join(scope_list),
    )
    cached_ast = ex.load_ast_cache(cache_dir, ast_key) if not skip_cache else None

    if cached_ast:
        click.echo("[extract] AST cache hit — reusing previous scan (--skip-cache to force a re-scan)")
        stack, routes, schemas, orm_models, services, components, api_funcs = ex.ast_cache_to_objects(cached_ast)
    else:
        stack = ex.detect_stack(repo)
        routes = ex.extract_routes(routes_dir, scope_list) if routes_dir else []
        schemas = ex.extract_schemas(schema_dir, scope_list) if schema_dir else []
        orm_models = ex.extract_orm_models(models_dir, scope_list) if models_dir else []
        services = ex.extract_services(services_dir, scope_list) if services_dir else []
        components = ex.extract_components(components_dir, scope_list) if components_dir else []
        api_funcs = ex.extract_api_functions(api_dir, scope_list) if api_dir else []
        if ast_key:
            ex.save_ast_cache(cache_dir, ast_key, stack, routes, schemas, orm_models, services, components, api_funcs)

    click.echo(
        f"\n[extract] Found: {len(routes)} routes, {len(schemas)} schemas, "
        f"{len(orm_models)} ORM models, {len(services)} services, "
        f"{len(components)} Vue components, {len(api_funcs)} API functions"
    )

    blueprint = out / "blueprint"
    blueprint.mkdir(parents=True, exist_ok=True)

    analysis = {
        "stack": stack,
        "routes": [
            {"method": r.method, "path": r.path, "status_code": r.status_code,
             "response_model": r.response_model, "source": r.source_file}
            for r in routes
        ],
        "schemas": [
            {"name": s.name, "base": s.base, "source": s.source_file, "fields": s.fields}
            for s in schemas
        ],
        "orm_models": [
            {"name": m.name, "tablename": m.tablename, "source": m.source_file, "columns": m.columns}
            for m in orm_models
        ],
        "services": [
            {"name": s.name, "source": s.source_file, "methods": s.methods}
            for s in services
        ],
        "components": [
            {"name": c.name, "source": c.source_file, "has_fetch": c.has_fetch,
             "has_props": c.has_props, "has_emits": c.has_emits, "has_mounted": c.has_mounted}
            for c in components
        ],
        "api_functions": [
            {"name": f.name, "method": f.http_method, "source": f.source_file}
            for f in api_funcs
        ],
    }
    (out / "analysis.json").write_text(json.dumps(analysis, indent=2))
    click.echo(f"[extract] Wrote analysis.json ({len(routes)} routes)")

    notes = ex.generate_extraction_notes(
        app_name, repo, stack, routes, schemas, components, backend_port, frontend_port
    )
    (out / "EXTRACTION.md").write_text(notes)
    click.echo("[extract] Wrote EXTRACTION.md")

    (blueprint / "settings.yaml").write_text(
        ex.generate_settings_yaml(app_name, backend_port, frontend_port)
    )
    click.echo("[extract] Wrote blueprint/settings.yaml")

    (blueprint / "main.graph.yaml").write_text(ex.generate_main_graph(app_name, routes))
    click.echo("[extract] Wrote blueprint/main.graph.yaml")

    (blueprint / "backend.graph.yaml").write_text(
        ex.generate_backend_graph(app_name, schemas, orm_models, services, routes)
    )
    click.echo("[extract] Wrote blueprint/backend.graph.yaml")

    (blueprint / "frontend.graph.yaml").write_text(
        ex.generate_frontend_graph(app_name, components, api_funcs)
    )
    click.echo("[extract] Wrote blueprint/frontend.graph.yaml")

    click.echo(f"\n[extract] Done. Review {out}/ — resolve all # TODO:/TODO: markers before building.")
    click.echo("  Recommended next steps:")
    click.echo("    1. Review analysis.json to understand what was extracted")
    click.echo("    2. Fill EXTRACTION.md §2 (functional description) and §3 (use cases)")
    click.echo("    3. Author contracts in blueprint/*.graph.yaml (or prompt an LLM with EXTRACTION.md + analysis.json)")
    click.echo(f"    4. grafcode validate {blueprint}/main.graph.yaml")
    click.echo("    5. Register node -> file mappings in spl/tech_profiles.py, then spl3 build")

    if llm:
        source_context = ex.build_source_context(repo, routes, schemas, orm_models, services, components, api_funcs)
        (out / "source_context.txt").write_text(source_context)
        click.echo(f"[extract] Wrote source_context.txt ({len(source_context)} chars)")

        analysis_text = json.dumps(analysis)
        llm_key = ex.cache_key(llm, app_name, str(blueprint), analysis_text, source_context)
        cached_marker = ex.load_llm_marker(cache_dir, llm_key) if not skip_cache else None
        cached_files = cached_marker.get("output_files", []) if cached_marker else []

        if cached_files and all((out / f).exists() for f in cached_files):
            click.echo(
                "[extract] LLM pass cache hit — compile_blueprint.spl already produced "
                f"{', '.join(cached_files)} for these exact inputs (llm={llm}); skipping "
                "the LLM call. Pass --skip-cache to force a re-run."
            )
        else:
            import subprocess
            import uuid

            click.echo(f"\n[extract] --llm {llm}: running semantic pass (shape classification + compile_blueprint.spl)")
            cmd = [
                _spl3_bin(), "run", str(_SPL_ROOT / "compile_blueprint.spl"),
                "--tools", str(_SPL_ROOT / "tools.py"),
                "--llm", llm,
                "-p", "mode=extraction",
                "-p", f"analysis_json={analysis_text}",
                "-p", f"source_context={source_context}",
                "-p", f"app_name={app_name}",
                "-p", f"output_dir={blueprint}",
                "-p", f"output_path={blueprint}/component.graph.yaml",
                "-p", "log_dir=logs/spl",
            ]
            if llm_timeout is not None:
                cmd += ["--llm-timeout", str(llm_timeout)]
                click.echo(f"[extract] --llm-timeout {llm_timeout}s")
            if persistence != "none":
                # Reuse llm_key as the workflow-id: it's already a hash of
                # (llm, app_name, blueprint, analysis, source_context), so it
                # naturally rotates whenever those inputs change (never
                # resumes a checkpoint from stale/mismatched inputs) and
                # stays stable across identical reruns (so a crashed run
                # resumes instead of restarting at step 0). Under
                # --skip-cache, a stable ID would instead *resume* (and
                # silently reuse the LLM output of) a prior completed run
                # with these same inputs — the opposite of what the flag
                # asks for — so mint a one-off ID instead: persistence
                # (crash-resumability) stays on for this run, it just can't
                # collide with an earlier one.
                workflow_id = llm_key if not skip_cache else f"{llm_key}-{uuid.uuid4().hex[:8]}"
                cmd += ["--persistence", persistence, "--workflow-id", workflow_id]
                click.echo(f"[extract] --persistence {persistence} --workflow-id {workflow_id}")
            proc = subprocess.run(
                cmd,
                cwd=_workspace_root(), capture_output=True, text=True,
                timeout=max(1800, (llm_timeout or 0) + 300),
            )
            click.echo(proc.stdout[-4000:])
            if proc.returncode != 0:
                click.echo(proc.stderr[-2000:], err=True)
                raise click.ClickException(f"semantic pass failed (exit {proc.returncode}) — see output above")
            if "Output:  FAILED" in proc.stdout:
                raise click.ClickException(
                    "semantic pass ran to completion but compile_blueprint.spl reported "
                    "FAILED (structural validation did not pass) — see output above"
                )
            click.echo("[extract] Semantic pass complete — this OVERWRITES the AST-only "
                        "blueprint/*.graph.yaml stubs written above for shapes it produces "
                        "(single-component: blueprint/component.graph.yaml only, review and "
                        "rename/merge by hand; integrated: main/backend/frontend.graph.yaml). "
                        "Still only structurally validated, not a claim of correctness — "
                        "read the output before building. If a TECH_PROFILE_DRAFT.md was "
                        "written, it is a reviewable draft — never auto-merged into "
                        "spl/tech_profiles.py.")

            if llm_key:
                written = sorted(
                    str(p.relative_to(out))
                    for p in list(blueprint.glob("*.graph.yaml")) + list(blueprint.glob("TECH_PROFILE_DRAFT.md"))
                )
                ex.save_llm_marker(cache_dir, llm_key, written)


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------

@main.command(short_help="Generate code for an app or component from its blueprint.")
@click.argument("target")
@click.option("--input-dir", default=None, type=click.Path(path_type=Path),
              help="Root TARGET is resolved under when TARGET is an app name rather "
                   "than a direct .graph.yaml path (INPUT_DIR/TARGET/blueprint/"
                   "main.graph.yaml, or component.graph.yaml if there's no main). "
                   "Defaults to ~/graph-code/input (created if missing).")
@click.option("--output-dir", default=None, type=click.Path(path_type=Path),
              help="Where generated code is written. Defaults to next to each "
                   "component's own graph.yaml — pass this to write elsewhere "
                   "instead, e.g. to try a fresh generation without overwriting "
                   "an existing build.")
@click.option("--tech-profile", default=None,
              help="Tech profile for a single-component TARGET. Defaults to the "
                   "graph's own tech_profile: field; pass this to override it. "
                   "Ignored for a system TARGET (one with imports:) — build_app.spl "
                   "derives one per imported component automatically.")
@click.option("--llm", default="claude_cli", show_default=True, help="Adapter[:model] for node generation.")
@click.option("--llm-timeout", type=int, default=None, metavar="SECONDS",
              help="Per-call timeout, forwarded to `spl3 run --llm-timeout`.")
def build(target: str, input_dir: Path | None, output_dir: Path | None,
          tech_profile: str, llm: str, llm_timeout: int | None) -> None:
    """Generate code for an app or component from its blueprint.

    TARGET is either a direct path to a *.graph.yaml file, or an app name
    resolved under --input-dir. A target with an imports: block (e.g.
    main.graph.yaml) is built via build_app.spl — every imported component,
    then integration; a target with none is built directly via
    build_component.spl. Thin wrapper: shells out to `spl3 run` the same way
    `grafcode extract --llm` does.
    """
    import subprocess

    target_path = Path(target)
    if target_path.exists():
        graph_path = target_path
    else:
        root = input_dir if input_dir is not None else _workspace_dir("input")
        graph_path = root / target / "blueprint" / "main.graph.yaml"
        if not graph_path.exists():
            graph_path = root / target / "blueprint" / "component.graph.yaml"

    if not graph_path.exists():
        _fail(f"no graph.yaml found for {target!r} (looked at {graph_path})")
        return
    graph_path = graph_path.resolve()

    try:
        graph = load_domain(graph_path)
    except ToolFailed as e:
        _fail(f"{graph_path}: {e}")
        return

    if graph.imports:
        cmd = [
            _spl3_bin(), "run", str(_SPL_ROOT / "build_app.spl"),
            "--tools", str(_SPL_ROOT / "tools.py"),
            "--llm", llm,
            "-p", f"system_yaml={graph_path}",
        ]
    else:
        if tech_profile is not None:
            resolved_tech_profile = tech_profile
        else:
            import yaml as _yaml
            raw = _yaml.safe_load(graph_path.read_text()) or {}
            resolved_tech_profile = raw.get("tech_profile") or "python_fastapi"
        cmd = [
            _spl3_bin(), "run", str(_SPL_ROOT / "build_component.spl"),
            "--tools", str(_SPL_ROOT / "tools.py"),
            "--llm", llm,
            "-p", f"component_graph={graph_path}",
            "-p", f"tech_profile={resolved_tech_profile}",
        ]
        if output_dir is None:
            # build_component.spl's own @output_dir has a hardcoded
            # DEFAULT 'backend/' (relative to spl3's cwd, _workspace_root()
            # here) meant for build_app.spl's per-component callers, which
            # always pass an explicit output_dir. A direct single-component
            # TARGET (this branch) must compute the same default
            # _component_output_dir() uses in spl/tools.py — app_root/
            # component_id, one 'blueprint' segment stripped — or any
            # component whose id isn't literally "backend" (e.g. this app's
            # own frontend.graph.yaml) silently writes into
            # ~/graph-code/backend/ instead of next to its own blueprint.
            component_id = graph_path.name.removesuffix(".graph.yaml")
            app_root = graph_path.parent.parent if graph_path.parent.name == "blueprint" else graph_path.parent
            output_dir = app_root / component_id
    if output_dir is not None:
        cmd += ["-p", f"output_dir={output_dir.resolve()}"]
    if llm_timeout is not None:
        cmd += ["--llm-timeout", str(llm_timeout)]

    click.echo(f"[build] {'system' if graph.imports else 'component'}: {graph_path}")
    proc = subprocess.run(
        cmd, cwd=_workspace_root(), capture_output=True, text=True,
        timeout=max(1800, (llm_timeout or 0) + 300),
    )
    click.echo(proc.stdout[-4000:])
    if proc.returncode != 0:
        click.echo(proc.stderr[-2000:], err=True)
        raise click.ClickException(f"build failed (exit {proc.returncode}) — see output above")
    _BUILD_FAILURE_MARKERS = ("Output:  FAILED", "Output:  BUILD HALTED", "Output:  BUILD FAILED")
    if any(marker in proc.stdout for marker in _BUILD_FAILURE_MARKERS):
        raise click.ClickException("build ran to completion but reported failure — see output above")


# ---------------------------------------------------------------------------
# ide
# ---------------------------------------------------------------------------

@main.command(short_help="Launch Graph IDE to browse blueprint graphs.")
@click.option("--api-port", default=8880, show_default=True, help="Backend (uvicorn) port.")
@click.option("--dev-port", default=8881, show_default=True, help="Frontend (vite) dev-server port.")
@click.option("--no-frontend", is_flag=True, help="Only launch the API server, not the Vite dev server.")
@click.option("--apps-root", default=None, type=click.Path(path_type=Path),
              help="Root directory containing <app>/blueprint/ graphs to browse. "
                   "Defaults to ~/graph-code/ide (created if missing) — pass this "
                   "repo's apps/ to browse graph-code's own example apps instead.")
def ide(api_port: int, dev_port: int, no_frontend: bool, apps_root: Path | None) -> None:
    """Launch Graph IDE — browse <app>/blueprint/ graphs in the browser.

    Shortcut for the two-terminal `uvicorn` + `npm run dev` dance described in
    tools/graph-ide/README.md. Requires the graph-ide deps installed once
    (`pip install -r tools/graph-ide/requirements.txt` and `npm install` in
    tools/graph-ide/frontend/). Ctrl-C stops both servers.
    """
    import os
    import subprocess

    ide_root = _GRAPH_IDE_ROOT
    if not ide_root.is_dir():
        _fail(f"graph-ide tool not found at {ide_root}")
        return

    # Only force GRAFCODE_APPS_ROOT when the user explicitly passed
    # --apps-root — otherwise let the API's own precedence decide (saved
    # Settings-page choice > this checkout's own apps/ > ~/graph-code/ide),
    # instead of always short-circuiting straight to the ~/graph-code/ide
    # default.
    env = {**os.environ}
    if apps_root is not None:
        env["GRAFCODE_APPS_ROOT"] = str(apps_root)

    procs: list[subprocess.Popen] = []
    try:
        apps_desc = str(apps_root) if apps_root is not None else "saved Settings choice, or this checkout's apps/, or ~/graph-code/ide"
        click.echo(f"Starting Graph IDE API on :{api_port} (apps: {apps_desc}) ...")
        procs.append(
            subprocess.Popen(
                ["uvicorn", "api.app:app", "--port", str(api_port), "--reload"],
                cwd=ide_root, env=env,
            )
        )

        if not no_frontend:
            click.echo(f"Starting Graph IDE frontend on :{dev_port} ...")
            frontend_env = {**env, "API_PORT": str(api_port), "DEV_PORT": str(dev_port)}
            procs.append(
                subprocess.Popen(["npm", "run", "dev"], cwd=ide_root / "frontend", env=frontend_env)
            )

        click.echo(f"Graph IDE ready — open http://localhost:{dev_port}")
        for p in procs:
            p.wait()
    except FileNotFoundError as e:
        _fail(f"{e.filename} not found — is it installed? ({e})")
    except KeyboardInterrupt:
        click.echo("\nStopping Graph IDE...")
    finally:
        for p in procs:
            if p.poll() is None:
                p.terminate()
        for p in procs:
            p.wait()


# ---------------------------------------------------------------------------
# tools (clean-port, spl-lint)
# ---------------------------------------------------------------------------

@main.group()
def tools() -> None:
    """Small dev-utility commands (clean-port, spl-lint, scaffold-vue, scaffold-fastapi)."""


@tools.command("clean-port", short_help="Kill whatever process is listening on the given port(s).")
@click.argument("ports", nargs=-1, required=True, type=int)
def clean_port(ports: tuple[int, ...]) -> None:
    """Kill whatever process is listening on the given port(s).

    SIGTERM every PID found via `lsof -t -i :PORT`, wait a second, then
    SIGKILL anything still alive — the same two-pass behavior the old
    scripts/clean_port.sh used. Handy after a `grafcode ide`/dev-server that
    didn't exit cleanly and left its port stuck.
    """
    import os
    import signal
    import subprocess
    import time

    def _pids_on(port: int) -> list[int]:
        proc = subprocess.run(["lsof", "-t", "-i", f":{port}"], capture_output=True, text=True)
        return [int(pid) for pid in proc.stdout.split()]

    for port in ports:
        pids = _pids_on(port)
        if not pids:
            click.echo(f"Port {port}: nothing listening")
            continue
        for pid in pids:
            click.echo(f"Port {port}: killing PID {pid}")
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass

    time.sleep(1)

    for port in ports:
        for pid in _pids_on(port):
            click.echo(f"Port {port}: PID {pid} still alive, sending SIGKILL")
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


@tools.command("scaffold-vue", short_help="Bootstrap a vue_typescript project shell via npm create vue@latest.")
@click.argument("target_dir", type=click.Path(path_type=Path))
def scaffold_vue(target_dir: Path) -> None:
    """Bootstrap a brand-new vue_typescript project shell at TARGET_DIR.

    Wraps `npm create vue@latest` non-interactively (TypeScript + router +
    pinia + vitest), patches package.json's test script to `vitest run`
    (create-vue's own is watch-mode and would hang), and runs `npm install`.
    Merges into TARGET_DIR rather than replacing it — safe to run against a
    directory that already has real generated content (e.g. an in-progress
    grafcode build's output_dir); only files that don't already exist there
    are written. This is the same logic `grafcode build` uses automatically
    the first time a vue_typescript component has no scaffold yet — exposed
    here so it's re-usable by hand against any target, independent of the
    build pipeline.
    """
    from graph_code.scaffolding import bootstrap_vue_scaffold
    click.echo(bootstrap_vue_scaffold(target_dir.resolve()))


@tools.command("scaffold-fastapi", short_help="Bootstrap a python_fastapi project shell (async SQLAlchemy + pytest).")
@click.argument("target_dir", type=click.Path(path_type=Path))
def scaffold_fastapi(target_dir: Path) -> None:
    """Bootstrap a brand-new python_fastapi project shell at TARGET_DIR.

    FastAPI ships no official "create-fastapi-app" CLI to wrap (unlike
    vue_typescript's `npm create vue@latest`), so this writes a hand-rolled
    minimal skeleton instead: an async-SQLAlchemy app/database.py, a
    pydantic-settings app/config.py (the Settings-singleton convention
    documented in spl/tech_profiles.py's python_fastapi profile), an
    app/main_app.py with a lifespan-managed table-create and one /health
    route, and a real passing tests/test_health.py (pytest-asyncio) so a
    build's Stage 3 test gate has something genuine to run. Per-file
    skip-if-exists — safe to run against a directory that already has real
    generated content. Same logic `grafcode build` uses automatically the
    first time a python_fastapi component has no tests/ yet.
    """
    from graph_code.scaffolding import bootstrap_fastapi_scaffold
    click.echo(bootstrap_fastapi_scaffold(target_dir.resolve()))


@tools.command("spl-lint", short_help="Find/fix unescaped single quotes in .spl prompt bodies.")
@click.argument("files", nargs=-1, type=click.Path(exists=True, dir_okay=False))
@click.option("--fix", is_flag=True, help="Rewrite files in place with '' escaping applied.")
def spl_lint(files: tuple[str, ...], fix: bool) -> None:
    """Find/fix unescaped single quotes in .spl CREATE FUNCTION prompt bodies.

    SPL dollar-quoted strings (AS $$ ... $$) use SQL-style quote escaping —
    a literal apostrophe must be written as '' (two single quotes), or it
    breaks parsing for everything after it in the file. It's easy to type a
    plain English apostrophe ("don't", "component's") inside a CREATE
    FUNCTION prompt and forget to escape it.

    Scope is deliberately narrow: only plain "AS $$ ... $$" blocks (LLM
    prompt prose) are touched. "AS PYTHON $$ ... $$" blocks (CREATE TOOL_API
    bodies, real executable Python where a quote is a string delimiter, not
    an English apostrophe) are reported separately and never auto-fixed —
    check those by eye. Defaults to spl/*.spl in the current directory when
    no FILES are given.
    """
    import glob
    import re

    block_re = re.compile(r"AS\s+\$\$(.*?)\$\$", re.DOTALL)
    python_block_re = re.compile(r"AS\s+PYTHON\s+\$\$(.*?)\$\$", re.DOTALL)

    def escape_block(text: str) -> str:
        out = []
        i, n = 0, len(text)
        while i < n:
            ch = text[i]
            if ch == "'":
                if i + 1 < n and text[i + 1] == "'":
                    out.append("''")
                    i += 2
                    continue
                out.append("''")
                i += 1
                continue
            out.append(ch)
            i += 1
        return "".join(out)

    def lines_touched(original: str, fixed: str, block_start_line: int) -> list[int]:
        orig_lines = original.split("\n")
        fixed_lines = fixed.split("\n")
        touched = []
        for idx, (o, f) in enumerate(zip(orig_lines, fixed_lines)):
            if o != f:
                touched.append(block_start_line + idx)
        return touched

    def process(path: str) -> list[str]:
        content = Path(path).read_text(encoding="utf-8")
        issues: list[str] = []
        new_parts = []
        last_end = 0
        changed = False

        for m in block_re.finditer(content):
            block = m.group(1)
            fixed_block = escape_block(block)
            block_start_line = content[: m.start(1)].count("\n") + 1
            if fixed_block != block:
                changed = True
                for ln in lines_touched(block, fixed_block, block_start_line):
                    issues.append(f"{path}:{ln}: unescaped single quote in $$ block")
            new_parts.append(content[last_end : m.start(1)])
            new_parts.append(fixed_block)
            last_end = m.end(1)
        new_parts.append(content[last_end:])
        new_content = "".join(new_parts)

        if fix and changed:
            Path(path).write_text(new_content, encoding="utf-8")

        for m in python_block_re.finditer(content):
            if "'" in m.group(1).replace("''", ""):
                start_line = content[: m.start(1)].count("\n") + 1
                issues.append(
                    f"{path}:{start_line}: AS PYTHON $$ block contains a single quote "
                    "— not auto-fixed (likely real Python syntax), check by hand"
                )
        return issues

    target_files = list(files) or sorted(glob.glob("spl/*.spl"))
    if not target_files:
        _fail("no .spl files found (pass file paths, or run from a directory with spl/*.spl)")
        return

    all_issues: list[str] = []
    for path in target_files:
        all_issues.extend(process(path))

    if all_issues:
        for issue in all_issues:
            click.echo(issue)
        if fix:
            click.echo(f"\nFixed {len(all_issues)} unescaped quote(s).")
            return
        click.echo(f"\n{len(all_issues)} unescaped quote(s) found. Run with --fix to auto-correct.")
        sys.exit(1)

    click.echo("OK — no unescaped single quotes in $$ blocks.")


@tools.command("suggest-graph-clusters", short_help="Suggest how to split one monolithic graph into smaller sub-graphs.")
@click.argument("graph_path", type=click.Path(exists=True, dir_okay=False))
@click.option("--seed", "seeds", multiple=True, metavar="NODE_ID",
              help="Explicit seed node id(s) to cluster around, instead of the default "
                   "(every unique node referenced by function.exports[].from). Repeatable.")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text", show_default=True)
def suggest_graph_clusters(graph_path: str, seeds: tuple[str, ...], fmt: str) -> None:
    """Suggest a modular sub-component split for one monolithic graph.

    Ancestor-closure clustering: seeds default to every node referenced by
    function.exports[].from (a graph's public surface), deduped; each
    seed's cluster is everything upstream of it (nx.ancestors over the
    mandatory composed_of/depends_on subgraph) that isn't also upstream of
    another seed. Nodes upstream of every seed are genuinely shared
    infrastructure ("core"); nodes upstream of some but not all seeds are
    real cross-component dependencies worth a human's attention ("shared"),
    not silently folded into core. Deterministic, no LLM call, no
    modularity/community-detection library — a prototype for eventually
    teaching `grafcode extract` to auto-split a monolithic backend/frontend
    graph the way this reports it could be split by hand.
    """
    try:
        graph = load_domain(graph_path)
    except ToolFailed as e:
        _fail(str(e))
        return

    result = graph_lib.suggest_clusters(graph, seeds=seeds or None)

    if fmt == "json":
        click.echo(json.dumps(result, indent=2))
        return

    click.echo(f"seeds: {', '.join(result['seeds']) or '(none found — pass --seed explicitly)'}")
    click.echo()
    for seed, nodes in result["clusters"].items():
        click.echo(f"cluster: {seed}")
        for n in nodes:
            click.echo(f"  {n}")
        if not nodes:
            click.echo("  (empty — seed has no exclusive ancestors)")
        click.echo()
    click.echo(f"core (ancestor of every seed — shared infrastructure):")
    for n in result["core"]:
        click.echo(f"  {n}")
    click.echo()
    if result["shared"]:
        click.echo("shared (ancestor of some but not all seeds — real cross-component dependencies):")
        for combo, nodes in result["shared"].items():
            for n in nodes:
                click.echo(f"  {n}  (used by: {combo})")
        click.echo()
    if result["unclustered"]:
        click.echo("unclustered (no seed depends on these — e.g. the composition root):")
        for n in result["unclustered"]:
            click.echo(f"  {n}")


# ---------------------------------------------------------------------------
# drift
# ---------------------------------------------------------------------------

def _make_llm_judge(llm: str, llm_timeout: int | None, llm_max_output_tokens: int | None = None):
    """Build a (dimension, text_a, text_b) -> float callable that shells out
    to spl/compute_intent_drift.spl, for graph_lib.drift_report(judge=...)
    under mode="semantic" — dimension-aware since one judge callable is
    shared across all 5 drift dimensions in a single drift_report() call,
    not just intent (see that workflow's own docstring for why).

    `llm_max_output_tokens` matters for reasoning-style local models (e.g.
    ollama:gemma4): the judge prompt's real intent_a/intent_b text is long
    enough that a "thinking" model can burn spl3's 1000-token GENERATE
    default entirely on hidden reasoning before ever emitting the required
    single number, coming back with empty content that fails to parse.
    claude_cli doesn't hit this (short, terse answers fit in 1000 either
    way), but it's cheap insurance for any adapter/model that does."""
    def judge(dimension: str, text_a: str, text_b: str) -> float:
        import re
        import subprocess
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            score_path = f.name

        cmd = [
            _spl3_bin(), "run", str(_SPL_ROOT / "compute_intent_drift.spl"),
            "--tools", str(_SPL_ROOT / "tools.py"),
            "--llm", llm,
            "-p", f"dimension={dimension}",
            "-p", f"intent_a={text_a}",
            "-p", f"intent_b={text_b}",
            "-p", f"output_path={score_path}",
            "-p", "log_dir=logs/spl",
        ]
        if llm_timeout is not None:
            cmd += ["--llm-timeout", str(llm_timeout)]
        if llm_max_output_tokens is not None:
            cmd += ["--llm-max-output-tokens", str(llm_max_output_tokens)]
        proc = subprocess.run(
            cmd, cwd=_workspace_root(), capture_output=True, text=True,
            timeout=max(300, (llm_timeout or 0) + 60),
        )
        if proc.returncode != 0:
            click.echo(proc.stderr[-2000:], err=True)
            raise click.ClickException(f"{dimension} drift pass failed (exit {proc.returncode}) — see output above")

        score_file = Path(score_path)
        raw = score_file.read_text().strip() if score_file.exists() else proc.stdout.strip()
        match = re.search(r"\d*\.?\d+", raw)
        if not match:
            raise click.ClickException(f"could not parse a {dimension} drift score from spl3's output: {raw!r}")
        return float(match.group())

    return judge


_DRIFT_DIMS = ("intent", "behavior", "structural", "interface", "implementation")


def _parse_dims(_ctx, _param, value: str | None) -> tuple[str, ...] | None:
    if not value:
        return None
    dims = tuple(d.strip() for d in value.split(",") if d.strip())
    unknown = set(dims) - set(_DRIFT_DIMS)
    if unknown:
        raise click.BadParameter(
            f"unknown dimension(s) {sorted(unknown)} — choose from {', '.join(_DRIFT_DIMS)}"
        )
    return dims


@main.command(short_help="Compute the drift report between two blueprint graphs.")
@click.argument("graph_a", type=click.Path(exists=True, dir_okay=False))
@click.argument("graph_b", type=click.Path(exists=True, dir_okay=False))
@click.option("--mode", type=click.Choice(["semantic", "edit-dist", "jaccard"]),
              default="semantic", show_default=True,
              help="Comparison method applied uniformly to all 5 dimensions. "
                   "'semantic': LLM-as-judge (requires --llm) scoring substantive drift in "
                   "meaning, ignoring wording/formatting differences. 'edit-dist': "
                   "character-level Levenshtein distance over each dimension's text rendering, "
                   "normalized to [0, 1] — a one-word change scores close to 0, not the 1.0 "
                   "jaccard would give once even one field in a tuple changes. 'jaccard': "
                   "exact-match set-overlap distance (1 - |intersection|/|union|) — an entry "
                   "either matches exactly or counts as fully different, no partial credit for "
                   "a near-miss.")
@click.option("--llm", default="claude_cli:claude-sonnet-4-6", show_default=True,
              help="ADAPTER:MODEL (e.g. claude_cli:claude-sonnet-4-6, ollama:gemma4). "
              "Used for --mode semantic — without it (pass --llm ''), any dimension under "
              "semantic mode comes back None rather than raising, so callers can tell "
              "'unchanged' apart from 'not measured'. Ignored (but harmless) for --mode "
              "jaccard/edit-dist, which are always free and need no LLM call.")
@click.option("--llm-timeout", type=int, default=None, metavar="SECONDS",
              help="Per-call timeout for the --mode semantic pass, forwarded to "
                   "`spl3 run --llm-timeout`.")
@click.option("--llm-max-output-tokens", type=int, default=4096, show_default=True, metavar="N",
              help="Per-call output token budget for the --mode semantic pass, forwarded to "
                   "`spl3 run --llm-max-output-tokens` (spl3's own built-in default is 1000, "
                   "too little for reasoning-style local models like ollama:gemma3/gemma4 — "
                   "they can burn the whole budget on hidden chain-of-thought before ever "
                   "emitting the required single number, coming back empty and failing to "
                   "parse). Pass 0 to fall back to spl3's own default.")
@click.option("--dims", callback=_parse_dims, default=None, metavar="DIM,DIM,...",
              help=f"Restrict the report to specific dimensions (comma-separated, from "
                   f"{{{','.join(_DRIFT_DIMS)}}}). Default: all five. Dimensions not "
                   f"selected are skipped entirely (no computation, and under --mode "
                   f"semantic no LLM call), not just hidden from output.")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text", show_default=True)
@click.option("--out", default=None, metavar="FILE",
              help="Write to FILE instead of stdout. A bare filename (no "
                   "directory component) resolves under ~/graph-code/report/.")
def drift(graph_a: str, graph_b: str, mode: str, llm: str, llm_timeout: int | None,
          llm_max_output_tokens: int | None, dims: tuple[str, ...] | None, fmt: str,
          out: str | None) -> None:
    """Compute the drift report between two blueprint graphs.

    See docs/DEV/BUILD/blueprint-schema-v2.2.md §3 for the schema this
    reports against (Blueprint.drift) — GRAPH_A is conventionally the
    reference/as-designed blueprint, GRAPH_B the one being compared against
    it (e.g. one reverse-mined from GRAPH_A's own generated code), though
    all components are symmetric so the order doesn't change the result.

    Each of the 5 dimensions is one aspect of the graph schema
    (intent/behavior/structural/interface/implementation), compared via
    whichever --mode is selected, plus an `overall` aggregate — NOT a mean
    of the five (they're individually incommensurable), but a genuine
    two-vector comparison: 1 - cosine similarity between graph_a's and
    graph_b's combined text across every selected dimension. Report only —
    this command does not write into either file's blueprint.drift block.
    """
    try:
        a = load_domain(graph_a)
        b = load_domain(graph_b)
    except ToolFailed as e:
        _fail(str(e))
        return

    judge = _make_llm_judge(llm, llm_timeout, llm_max_output_tokens or None) if (llm and mode == "semantic") else None

    report = graph_lib.drift_report(a, b, dims=dims, mode=mode, judge=judge)

    if fmt == "json":
        payload = {"mode": mode, **report}
        text = json.dumps(payload, indent=2)
    else:
        width = 28
        lines = [f"{'mode':<{width}} {mode}"]
        for key, value in report.items():
            if value is None:
                shown = "null (pass --mode semantic --llm ... to compute)" if mode == "semantic" else "null"
            else:
                shown = value
            # overall is a genuine two-vector comparison (1 - cosine similarity
            # over combined dimension text), independent of --mode — unlike the
            # other rows, its number won't change between jaccard/edit-dist/semantic.
            label = "overall (cosine-distance)" if key == "overall" else key
            lines.append(f"{label:<{width}} {shown}")
        text = "\n".join(lines)
    _write_report(text, out)


# ---------------------------------------------------------------------------
# validate-all
# ---------------------------------------------------------------------------

def _discover_all_graphs(root: Path) -> list[Path]:
    """Find graph.yaml (conceptbook domains) and *.graph.yaml (graph-code
    blueprints) files under root, deduped and sorted.

    Conceptbook domains follow: public/domains/*/input/graph.yaml
    graph-code blueprints follow: apps/*/blueprint/*.graph.yaml
    Both are matched by simply collecting all graph.yaml and *.graph.yaml
    files, which is unambiguous because graph-code files always carry a
    non-graph.yaml basename (e.g. main.graph.yaml, backend.graph.yaml).

    Excludes lock files (*.lock), backup files (*~), and anything inside
    a node_modules or __pycache__ directory.
    """
    found: set[Path] = set()
    _SKIP_DIRS = {"node_modules", "__pycache__", ".git", ".spl"}
    for p in root.rglob("*"):
        if any(part in _SKIP_DIRS for part in p.parts):
            continue
        if p.name == "graph.yaml" or p.name.endswith(".graph.yaml"):
            if not p.name.endswith((".lock", "~")):
                found.add(p)
    return sorted(found)


@main.command("validate-all", short_help="Validate every graph.yaml under a directory tree.")
@click.argument("root", type=click.Path(exists=True, path_type=Path))
@click.option("--fail-fast", is_flag=True, help="Stop at the first failure.")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text",
              show_default=True)
@click.option("--out", default=None, metavar="FILE",
              help="Write report to FILE instead of stdout.")
def validate_all(root: Path, fail_fast: bool, fmt: str, out: str | None) -> None:
    """Validate every graph.yaml under ROOT and print a pass/fail table.

    Finds both conceptbook-style graph.yaml files (in */input/ directories)
    and graph-code-style *.graph.yaml blueprints. Exits 1 if any file fails.

    Useful for batch-checking a cb-* repo after bulk edits (e.g. adding
    diagram: hints) or after porting changes across multiple repos.

    Examples:
      grafcode validate-all ~/projects/digital-duck/cb-algorithms/public/domains/
      grafcode validate-all ~/projects/digital-duck/ --format json --out report.json
    """
    if root.is_file():
        # Convenience: accept a single file too
        files = [root]
    else:
        files = _discover_all_graphs(root)

    if not files:
        click.echo(f"no graph.yaml or *.graph.yaml found under {root}", err=True)
        sys.exit(1)

    results: list[dict] = []
    any_fail = False

    for path in files:
        try:
            rel = path.relative_to(root)
        except ValueError:
            rel = path

        try:
            graph = load_domain(path)
        except ToolFailed as e:
            results.append({"path": str(rel), "status": "FAIL", "nodes": None,
                            "warnings": [], "error": str(e)})
            any_fail = True
            if fail_fast:
                break
            continue

        try:
            warnings = graph_lib.validate_full(graph)
        except ToolFailed as e:
            results.append({"path": str(rel), "status": "FAIL",
                            "nodes": len(graph.nodes) + len(graph.primitives),
                            "warnings": [], "error": str(e)})
            any_fail = True
            if fail_fast:
                break
            continue

        results.append({
            "path": str(rel),
            "status": "OK",
            "nodes": len(graph.nodes) + len(graph.primitives),
            "warnings": [str(w) for w in warnings],
            "error": None,
        })

    if fmt == "json":
        text = json.dumps(results, indent=2)
    else:
        lines = []
        path_w = max((len(r["path"]) for r in results), default=20)
        for r in results:
            status = r["status"]
            n = f"{r['nodes']} nodes" if r["nodes"] is not None else "      "
            if status == "OK":
                w = f"  {len(r['warnings'])} warning(s)" if r["warnings"] else ""
                lines.append(f"OK   {r['path']:<{path_w}}  {n}{w}")
            else:
                lines.append(f"FAIL {r['path']:<{path_w}}  {r['error']}")

        pass_n = sum(1 for r in results if r["status"] == "OK")
        fail_n = sum(1 for r in results if r["status"] == "FAIL")
        warn_n = sum(len(r["warnings"]) for r in results)
        lines.append(f"\n{pass_n} passed, {fail_n} failed, {warn_n} warning(s) — {len(results)} files")
        text = "\n".join(lines)

    _write_report(text, out)

    if any_fail:
        sys.exit(1)


# ---------------------------------------------------------------------------
# diagram  (list / check / add)
# ---------------------------------------------------------------------------

_VALID_DIAGRAM_TYPES = frozenset({
    "flowchart LR", "flowchart TD", "flowchart RL", "flowchart BT",
    "graph LR", "graph TD", "graph RL", "graph BT",
    "sequenceDiagram", "image", "auto",
})

_FLAT_SECTIONS = ("primitives", "concepts", "applications")


def _raw_nodes_flat(data: dict) -> dict[str, tuple[str, dict]]:
    """Return {node_id: (section, node_dict)} for every node in a v1.0 flat YAML."""
    result: dict[str, tuple[str, dict]] = {}
    for section in _FLAT_SECTIONS:
        for node_id, attrs in (data.get(section) or {}).items():
            if isinstance(attrs, dict):
                result[node_id] = (section, attrs)
    return result


@main.group()
def diagram() -> None:
    """Inspect and add diagram hints in graph.yaml files."""


@diagram.command("list", short_help="List nodes that have diagram hints.")
@click.argument("graph_yaml", type=click.Path(exists=True, dir_okay=False))
def diagram_list(graph_yaml: str) -> None:
    """List all nodes in GRAPH_YAML that carry a diagram: hint.

    Shows node id, section (primitives/concepts/applications), diagram type,
    and the first 60 characters of the hint text.
    """
    import yaml as _yaml
    data = _yaml.safe_load(Path(graph_yaml).read_text())
    if not isinstance(data, dict):
        _fail("not a valid YAML mapping")
        return

    nodes = _raw_nodes_flat(data)
    hits = [(nid, sec, attrs["diagram"]) for nid, (sec, attrs) in nodes.items()
            if isinstance(attrs.get("diagram"), dict)]

    if not hits:
        click.echo("no diagram: hints found")
        return

    id_w = max(len(nid) for nid, *_ in hits)
    sec_w = max(len(sec) for _, sec, _ in hits)
    for nid, sec, d in hits:
        dtype = d.get("type", "—")
        hint = (d.get("hint") or "")[:60].replace("\n", " ")
        hint_str = f'"{hint}…"' if len(d.get("hint", "")) > 60 else f'"{hint}"'
        click.echo(f"  {nid:<{id_w}}  {sec:<{sec_w}}  {dtype:<20}  {hint_str}")

    click.echo(f"\n{len(hits)} node(s) with diagram hints")


@diagram.command("check", short_help="Validate diagram hint structure in a graph.yaml.")
@click.argument("graph_yaml", type=click.Path(exists=True, dir_okay=False))
def diagram_check(graph_yaml: str) -> None:
    """Check every diagram: block in GRAPH_YAML for structural correctness.

    Reports: missing `type` or `hint` sub-keys, unrecognised `type` values,
    and `hint` text that is suspiciously short (< 10 chars). Exits 1 if any
    issue is found.
    """
    import yaml as _yaml
    data = _yaml.safe_load(Path(graph_yaml).read_text())
    if not isinstance(data, dict):
        _fail("not a valid YAML mapping")
        return

    nodes = _raw_nodes_flat(data)
    issues: list[str] = []
    checked = 0

    for nid, (sec, attrs) in nodes.items():
        d = attrs.get("diagram")
        if d is None:
            continue
        checked += 1
        if not isinstance(d, dict):
            issues.append(f"{nid}: diagram: must be a mapping, got {type(d).__name__}")
            continue
        dtype = d.get("type")
        hint = d.get("hint")
        if not dtype:
            issues.append(f"{nid}: diagram.type is missing")
        elif dtype not in _VALID_DIAGRAM_TYPES:
            issues.append(f"{nid}: diagram.type {dtype!r} is not a known type "
                          f"(valid: {', '.join(sorted(_VALID_DIAGRAM_TYPES))})")
        if not hint:
            issues.append(f"{nid}: diagram.hint is missing")
        elif len(str(hint).strip()) < 10:
            issues.append(f"{nid}: diagram.hint is very short ({len(str(hint).strip())} chars) — "
                          "add more detail to guide the LLM")

    if issues:
        for issue in issues:
            click.echo(f"ISSUE  {issue}")
        click.echo(f"\n{len(issues)} issue(s) found in {checked} diagram hint(s)")
        sys.exit(1)

    click.echo(f"OK — {checked} diagram hint(s) checked, no issues")


@diagram.command("add", short_help="Add or update a diagram hint on a node.")
@click.argument("graph_yaml", type=click.Path(exists=True, dir_okay=False))
@click.argument("node_id")
@click.option("--type", "dtype", required=True,
              help=f"Mermaid diagram type or 'image'. One of: {', '.join(sorted(_VALID_DIAGRAM_TYPES))}")
@click.option("--hint", required=True, help="Free-text hint describing what the diagram should show.")
@click.option("--overwrite", is_flag=True, help="Replace an existing diagram: block (default: error if one exists).")
def diagram_add(graph_yaml: str, node_id: str, dtype: str, hint: str, overwrite: bool) -> None:
    """Add a diagram: hint to NODE_ID in GRAPH_YAML.

    Uses a ruamel.yaml round-trip write so all formatting, comments, and
    indentation in the file are preserved. The diagram: block is inserted
    as the first key in the node's entry (before defines:). A validate gate
    (load_domain + validate_full) runs on a temp copy before touching disk —
    if structural validation fails the file is left untouched.

    Example:
      grafcode diagram add cb-calculus/public/domains/calculus_ch03/input/graph.yaml \\
        derivative_at_a_point \\
        --type "flowchart LR" \\
        --hint "secant → h→0 → tangent; label slope formula"
    """
    import os
    import tempfile

    import yaml as _pyyaml
    from ruamel.yaml import YAML
    from ruamel.yaml.comments import CommentedMap

    if dtype not in _VALID_DIAGRAM_TYPES:
        _fail(f"unknown diagram type {dtype!r}. Valid: {', '.join(sorted(_VALID_DIAGRAM_TYPES))}")
        return

    path = Path(graph_yaml)
    ry = YAML()
    ry.preserve_quotes = True
    ry.width = 4096
    ry.indent(mapping=2, sequence=4, offset=2)
    data = ry.load(path.read_text())

    if not isinstance(data, dict):
        _fail("not a valid YAML mapping")
        return

    # Find the node entry in primitives / concepts / applications
    entry = None
    for section in _FLAT_SECTIONS:
        sec_data = data.get(section)
        if isinstance(sec_data, dict) and node_id in sec_data:
            entry = sec_data[node_id]
            break

    if entry is None:
        _fail(f"node {node_id!r} not found in primitives/concepts/applications")
        return

    if not isinstance(entry, dict):
        _fail(f"node {node_id!r} entry is not a mapping")
        return

    if "diagram" in entry:
        if not overwrite:
            _fail(f"node {node_id!r} already has a diagram: block. Pass --overwrite to replace it.")
            return
        del entry["diagram"]

    # Build the diagram block and insert at position 0 (before defines:)
    diag = CommentedMap()
    diag["type"] = dtype
    diag["hint"] = hint
    entry.insert(0, "diagram", diag)

    from io import StringIO
    buf = StringIO()
    ry.dump(data, buf)
    new_text = buf.getvalue()

    # Validate before writing to disk
    try:
        _pyyaml.safe_load(new_text)
    except _pyyaml.YAMLError as e:
        _fail(f"edit would produce invalid YAML: {e}")
        return

    fd, tmp_name = tempfile.mkstemp(dir=path.parent, suffix=".graph.yaml")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(new_text)
        try:
            trial = load_domain(tmp_name)
            graph_lib.validate_full(trial)
        except ToolFailed as e:
            _fail(f"edit would break graph validation: {e}")
            return
    finally:
        if Path(tmp_name).exists():
            Path(tmp_name).unlink()

    path.write_text(new_text)
    click.echo(f"OK — diagram hint added to {node_id!r} in {path}")
