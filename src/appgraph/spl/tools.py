"""app-graph SPL tool functions — callable from .spl scripts via CALL.

Rewritten (not copied) from graph-driven-workflow/spl/tools.py to call
appgraph's GraphDomain-based API instead of the old dict-based
graph_lib.load_graph/validate/build_order(data) API — see
docs/DEV/BUILD/README.md §2/§3.4 for the old->new call mapping.

Every function decorated with @spl_tool takes and returns strings
(SPL variables are untyped strings at runtime).
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import appgraph
from appgraph.settings import interpolate as _interpolate_settings
from appgraph.settings import load_settings as _load_app_settings
from spl.tools import spl_tool

# tech_profiles.py is a true sibling in this directory, loaded as a standalone
# file by spl3 (no package context) — the _load_sibling pattern is still
# needed for it. appgraph itself is an installed package, so it is
# imported normally above, not via this hack.
_SPL_DIR = Path(__file__).parent


def _spl3_bin() -> str:
    """Path to the `spl3` binary next to the Python interpreter actually
    running this process (sys.executable), not a bare "spl3" resolved via
    inherited PATH — see cli.py's identical helper for why: two envs can
    each have their own spl-llm install, and a bare name silently picks
    whichever is first on the *outer* process's PATH rather than the one
    matching the interpreter this tools.py module is actually loaded into."""
    candidate = Path(sys.executable).parent / "spl3"
    return str(candidate) if candidate.exists() else "spl3"


def _load_sibling(name: str):
    spec = importlib.util.spec_from_file_location(name, _SPL_DIR / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


tech_profiles = _load_sibling("tech_profiles")


def _strip_fences(code: str, is_doc: bool = True) -> str:
    """Strip a markdown code fence that wraps the *entire* generated output.

    Finds the first fence marker in the text and, if everything before it
    looks like leaked preamble narration rather than real content, keeps only
    what's after it — e.g. "Looking at the spec, this just needs a
    requirements.txt with pytest pinned.\\n```\\npytest>=7.0.0" (no closing
    fence either, found on apps/etl_workflow's requirements.txt, 2026-08-13),
    or a whole document wrapped in one outer ```markdown ... ``` fence (the
    fence sits at position 0, so the "prefix" is empty).

    When `is_doc` (the default, matching every pre-existing call site — YAML
    specs, test files, drafts, docs), the prefix is only treated as
    discardable preamble when it's short and has no markdown heading — a
    real document that legitimately contains a fenced block partway through
    (e.g. an ASCII diagram inside a generated README, found on
    apps/classical_mechanics/conceptbook's README, 2026-08-13) has
    substantial content and its own headings before that fence, and must not
    be truncated down to just the fenced block. The previous version
    searched for the first fence *anywhere* unconditionally, which is what
    produced that truncation.

    `is_doc=False` (write_node_file/verify_node's non-doc code nodes) skips
    that length/heading guard and always discards the prefix: a code node's
    output should just *be* the code, so any text before its first fence is
    always leaked narration, never legitimate content to preserve — and a
    refined/repaired node's narration ("Looking at the feedback, the
    validator expects...") routinely runs past 200 chars, which the guarded
    heuristic wrongly kept, leaving prose+fence intact and failing the
    code-shape check downstream (found for real on todo2A's
    task_list/app_shell nodes, 2026-08-16 — the refined code silently never
    overwrote the stale file on disk).

    `is_doc=False` also truncates at the first *closing* fence rather than
    only stripping one if it happens to sit at the very end of the string —
    a single-file node's response can still leak a second, unrelated file
    after its own (e.g. "```ts\n...main.ts content...\n```\n\n**App.vue**\n
    ```vue\n..."), and the old trailing-only regex left that whole tail
    appended to the real file (found for real on todo2A's app_shell node,
    2026-08-16 — main.ts ended up with a stray ``` and a second component's
    source glued on after it, breaking the vite build). Doc nodes keep the
    old trailing-only strip since a real document can legitimately contain
    more than one fenced block (the README-with-diagram case above).
    """
    import re
    stripped = code.strip()
    m = re.search(r"```[a-zA-Z]*\n", stripped)
    if m:
        prefix = stripped[:m.start()]
        looks_like_real_content = is_doc and (len(prefix) >= 200 or bool(re.search(r"(?m)^#", prefix)))
        if not looks_like_real_content:
            stripped = stripped[m.end():]
            if is_doc:
                stripped = re.sub(r"\n?```\s*$", "", stripped)
            else:
                close_m = re.search(r"\n?```", stripped)
                stripped = stripped[:close_m.start()] if close_m else stripped
    return stripped.strip()


_CHAT_ARTIFACT_RE = None  # lazy-compiled below


def _strip_chat_artifacts(text: str) -> str:
    """Strip leaked chat-turn/tool-call artifacts from generated content.

    Two distinct incidents observed so far, both on `kind: doc` nodes (the
    only node kind with no other shape check — compile()/npm test would
    catch either of these in a code node; nothing does for Markdown, so both
    strips here are defensive regardless of root cause):

    1. (2026-08-12) a generated README ended with the literal text
       "Human: continue to generate: TodoItem" — a fragment of what looks
       like SPL.py's own GENERATE segment-chaining prompt, leaked into the
       visible output (see docs/DEV/BUILD/README.md §8.2).
    2. (2026-08-13, apps/dispatch/backend/README.md and
       apps/expense/blueprint/README.md) a generation leaked raw tool-call
       XML (`<function_calls><invoke name="Write"><parameter
       name="content">...`) around the real content, sometimes with preamble
       narration before it and commentary after — an explicit prompt
       instruction ("output ONLY the Markdown, no tool-call syntax") was
       added after the first occurrence but did NOT prevent the second, so
       this strip is the actual safety net, not the prompt wording.
    """
    import re
    global _CHAT_ARTIFACT_RE
    if _CHAT_ARTIFACT_RE is None:
        _CHAT_ARTIFACT_RE = re.compile(
            r"\n(Human|Assistant|User|System):\s.*\Z", re.DOTALL
        )
    text = _CHAT_ARTIFACT_RE.sub("", text).rstrip()

    if "<function_calls>" in text or "<invoke" in text:
        m = re.search(r'<parameter name="content">(.*?)</parameter>', text, re.DOTALL)
        if m:
            text = m.group(1)

    return text.strip()


# ── Module-level graph cache ──────────────────────────────────────────────────
_GRAPH_CACHE: dict[str, appgraph.GraphDomain] = {}


def _load_and_cache_graph(graph_yaml: str) -> appgraph.GraphDomain:
    graph = appgraph.load_domain(graph_yaml)
    appgraph.validate_full(graph)
    _GRAPH_CACHE[graph_yaml] = graph
    return graph


def _graph(graph_yaml: str) -> appgraph.GraphDomain:
    """Lazily loads+validates+caches on a cold cache — needed for SPL runtimes
    (e.g. dsh-spl's DshBackend) that execute each CALL in a fresh subprocess,
    where this module-level cache never survives from one CALL to the next.
    setup_graph() remains the explicit, spl3-visible first call (it still
    reports the build order), but is no longer the only path that populates
    the cache."""
    if graph_yaml not in _GRAPH_CACHE:
        return _load_and_cache_graph(graph_yaml)
    return _GRAPH_CACHE[graph_yaml]


def _app_name_from_path(graph_yaml: str) -> str:
    """Extract the app_name key used by tech_profiles.NODE_FILES from a
    graph.yaml path, e.g. apps/todo/blueprint/backend.graph.yaml -> "todo".

    Every *.graph.yaml lives under apps/<app_name>/... (blueprint/ subfolder
    convention, see docs/DEV/BUILD/blueprint-schema-v2.2.md §6), so this is a
    plain path lookup, not a new schema field — see
    docs/DEV/BUILD/refactoring-plan-v1.md §1.3.
    """
    parts = Path(graph_yaml).resolve().parts
    if "apps" in parts:
        idx = parts.index("apps")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    raise RuntimeError(f"Could not derive app_name from path: {graph_yaml!r} (expected .../apps/<app_name>/...)")


def _node_deps(graph: appgraph.GraphDomain, node_id: str) -> list[str]:
    """Mandatory dependencies of a form.nodes entry: composed_of + depends_on,
    de-duplicated, composed_of first. Primitives have no deps (leaf)."""
    ndata = graph.nodes.get(node_id) or {}
    deps = list(ndata.get("composed_of") or [])
    for dep in ndata.get("depends_on") or []:
        if dep not in deps:
            deps.append(dep)
    return deps


def _fmt_spec(spec: dict) -> str:
    parts = []
    for k, v in spec.items():
        parts.append(f"{k}:\n{v}")
    return "\n\n".join(parts)


# ── Graph setup and ordering ──────────────────────────────────────────────────

@spl_tool
def setup_graph(graph_yaml: str) -> str:
    """Load and validate graph.yaml; cache for subsequent calls.

    validate_full() raises ToolFailed for hard errors (cycles, undeclared
    events/transitions, Two-Radical violations if enforced) before any LLM
    call — this is appgraph's own contract, so no separate error-collection
    step is needed here (unlike the old graph_lib.validate(), which returned
    a list of strings that setup_graph then had to check and re-raise).
    """
    graph = _load_and_cache_graph(graph_yaml)
    order = appgraph.build_order(graph)
    return f"ok: {len(order)} nodes to build"


@spl_tool
def contract_warnings(graph_yaml: str) -> str:
    """Report declared call-contract mismatches in graph.yaml (function.calls
    entries where consumer_requires != provider_guarantees), joined one per
    line, or "" if none.

    Scope, stated plainly: this compares two strings *declared in the yaml
    itself* against each other. It does not inspect generated code, so it
    cannot catch a case where the yaml's own two sides already agree but the
    LLM generated code that doesn't follow either of them (e.g. the
    toggleTodo PATCH-vs-PUT bug documented in
    docs/DEV/BUILD/README.md §7.4.1 — both consumer_requires and
    provider_guarantees said "PUT", so this check would have reported zero
    violations even with that bug present). It catches yaml *authoring*
    drift — editing one side of a declared contract without the other — not
    code-vs-contract drift.
    """
    graph = _graph(graph_yaml)
    violations = appgraph.check_call_contracts(graph)
    return "\n".join(violations)


@spl_tool
def order_length(graph_yaml: str) -> str:
    return str(len(appgraph.build_order(_graph(graph_yaml))))


@spl_tool
def order_item(graph_yaml: str, index: str) -> str:
    return appgraph.build_order(_graph(graph_yaml))[int(index)]


@spl_tool
def order_last(graph_yaml: str) -> str:
    """Return the last node in topological order (the capstone)."""
    return appgraph.build_order(_graph(graph_yaml))[-1]


@spl_tool
def get_capstone(graph_yaml: str) -> str:
    """Return the declared capstone node from graph.yaml, falling back to order_last."""
    graph = _graph(graph_yaml)
    return graph.capstone or appgraph.build_order(graph)[-1]


@spl_tool
def identify_broken_node(test_output: str, graph_yaml: str) -> str:
    """Identify which node to repair from the failing test file name.

    Maps test file names to node IDs so the repair loop targets the actual
    broken node rather than always falling back to the capstone.
    Expense-specific patterns come first — they are longer and would match
    todo patterns as substrings if checked in the wrong order.

    Falls back (before the capstone fallback) to scanning the traceback for
    a *source* file path — via tech_profiles.NODE_FILES[app_name], reversed
    from rel_path back to node_id — since a collection-time ImportError
    (e.g. a bad import inside app/models.py, raised while loading
    conftest.py, before any individual test file even runs) never contains
    any "test_X" substring at all, so the hardcoded table below can never
    match it and every attempt used to silently repair the capstone instead
    of the actually-broken node (found for real on todo's orm_model ->
    app/models.py 'TodoSchema' ImportError, 2026-08-14 — 3 repair attempts
    all touched app/main.py, the capstone, while the real bug in
    app/models.py went untouched by any of them). Prefers the LAST matching
    file path in the traceback, since an import chain lists the innocent
    importer (app/main.py) before the actually-broken importee
    (app/models.py) — the broken file is the last frame before the error.
    """
    test_file_to_node = {
        # Dispatch incident core backend (most specific — before other apps)
        "test_crud_dispatch":       "incident_crud",
        "test_routes_dispatch":     "api_routes",
        # FastAPI example backend (most specific — before other apps)
        "test_crud_items":          "crud_operations",
        "test_routes_items":        "api_routes",
        # Conduit backend (most specific — before other apps; test_auth_schemas
        # is shared with fullstack, both map to the same "data_schema" node id)
        "test_auth_routes":         "api_routes",
        "test_profile_routes":      "api_routes",
        "test_article_routes":      "api_routes",
        # Fullstack backend (most specific — before other apps)
        "test_auth_schemas":        "data_schema",
        "test_security":            "security_module",
        "test_orm_models":          "orm_model",
        "test_auth_deps":           "auth_deps",
        "test_users_routes":        "api_routes",
        "test_items_routes":        "api_routes",
        "test_login_routes":        "api_routes",
        # Fullstack frontend
        "LoginForm.spec":           "LoginForm",
        "ItemForm.spec":            "ItemForm",
        "ItemList.spec":            "ItemList",
        "ItemDashboard.spec":       "ItemDashboard",
        # Mealie backend (most specific — longest patterns first)
        "test_organizer_schemas":   "organizer_schema",
        "test_recipe_schemas":      "recipe_schema",
        "test_organizer_models":    "organizer_orm_models",
        "test_recipe_models":       "recipe_orm_model",
        "test_organizer_crud":      "organizer_crud",
        "test_recipe_crud":         "recipe_crud",
        "test_recipe_routes":       "api_routes",
        # Mealie frontend
        "RecipeCard.spec":            "RecipeCard",
        "OrganizerFilter.spec":       "OrganizerFilter",
        "RecipeIngredientList.spec":  "RecipeIngredientList",
        "RecipeForm.spec":            "RecipeForm",
        "RecipeDetailView.spec":      "RecipeDetailView",
        "RecipeList.spec":            "RecipeList",
        "RecipeDashboard.spec":       "RecipeDashboard",
        # Kanban backend (most specific — before expense and todo)
        "test_card_schemas": "data_schema",
        "test_card_models":  "orm_model",
        "test_card_crud":    "crud_operations",
        "test_board_view":   "board_view",
        "test_card_routes":  "api_routes",
        # Kanban frontend
        "StatusSelect.spec":  "StatusSelect",
        "KanbanCard.spec":    "KanbanCard",
        "KanbanColumn.spec":  "KanbanColumn",
        "KanbanBoard.spec":   "KanbanBoard",
        "CardForm.spec":      "CardForm",
        # Expense backend (more specific — must precede shorter todo patterns)
        "test_expense_schemas": "data_schema",
        "test_expense_models":  "orm_model",
        "test_expense_crud":    "crud_operations",
        "test_reports":         "report_aggregator",
        "test_expense_routes":  "api_routes",
        # Expense frontend
        "ExpenseForm.spec":      "ExpenseForm",
        "ExpenseItem.spec":      "ExpenseItem",
        "CategoryFilter.spec":   "CategoryFilter",
        "ExpenseList.spec":      "ExpenseList",
        "SummaryView.spec":      "SummaryView",
        "ExpenseDashboard.spec": "ExpenseDashboard",
        # Todo backend
        "test_schemas":  "data_schema",
        "test_crud":     "crud_operations",
        "test_routes":   "api_routes",
        "test_database": "db_connection",
        "test_models":   "orm_model",
        # Todo frontend
        "test_api":      "api_client",
        "test_TodoList": "list_component",
        "test_TodoItem": "item_component",
    }
    graph = _graph(graph_yaml)
    all_nodes = set(graph.nodes) | set(graph.primitives)
    for test_file, node_id in test_file_to_node.items():
        if test_file in test_output and node_id in all_nodes:
            return node_id

    # Generic fallback: scan the traceback for a known source file path
    # (works for collection-time ImportErrors, which never match a "test_X"
    # substring above — see the docstring). Prefers the last match, since
    # the broken file is the last frame before the error, not the first.
    app_name = _app_name_from_path(graph_yaml)
    rel_to_node = {
        rel_path: node_id
        for node_id, rel_path in tech_profiles.NODE_FILES.get(app_name, {}).items()
        if node_id in all_nodes
    }
    last_match = None
    for line in test_output.splitlines():
        for rel_path, node_id in rel_to_node.items():
            if rel_path in line:
                last_match = node_id
    if last_match:
        return last_match

    # Fall back to the declared capstone when nothing else matches
    return graph.capstone or appgraph.build_order(graph)[-1]


@spl_tool
def order_bullets(graph_yaml: str) -> str:
    order = appgraph.build_order(_graph(graph_yaml))
    return "\n".join(f"  {i}. {n}" for i, n in enumerate(order))


@spl_tool
def node_spec_text(node: str, graph_yaml: str) -> str:
    spec = (_graph(graph_yaml).nodes.get(node) or {}).get("spec") or {}
    return _fmt_spec(spec) if spec else f"(no spec declared for {node})"


@spl_tool
def node_spec(node: str, graph_yaml: str) -> str:
    """Same as node_spec_text — used directly by build_component.spl."""
    spec = (_graph(graph_yaml).nodes.get(node) or {}).get("spec") or {}
    return _fmt_spec(spec) if spec else f"(no spec declared for {node})"


@spl_tool
def save_spec(node: str, spec: str, graph_yaml: str) -> str:
    """No-op: specs declared in graph.yaml are authoritative; LLM-generated specs are not persisted."""
    return f"ok: spec for {node} noted (not persisted)"


@spl_tool
def has_spec(node: str, graph_yaml: str) -> str:
    spec = (_graph(graph_yaml).nodes.get(node) or {}).get("spec") or {}
    return "yes" if spec else "no"


@spl_tool
def node_defines_text(node: str, graph_yaml: str) -> str:
    graph = _graph(graph_yaml)
    ndata = graph.nodes.get(node) or graph.primitives.get(node) or {}
    return ndata.get("defines", "")


@spl_tool
def node_composed_of(node: str, graph_yaml: str) -> str:
    deps = _node_deps(_graph(graph_yaml), node)
    return ", ".join(deps) if deps else "(none)"


@spl_tool
def node_context(node: str, graph_yaml: str, output_dir: str) -> str:
    """Return already-generated source files for this node's dependencies."""
    graph = _graph(graph_yaml)
    deps = _node_deps(graph, node)
    primitives = set(graph.primitives)
    app_name = _app_name_from_path(graph_yaml)
    mapping = tech_profiles.NODE_FILES.get(app_name, {})
    parts: list[str] = []
    for dep in deps:
        if dep in primitives:
            continue
        rel_path = mapping.get(dep)
        if not rel_path:
            continue
        fpath = Path(output_dir) / rel_path
        if fpath.exists():
            parts.append(f"# {rel_path}\n{fpath.read_text()}")
    return "\n\n".join(parts) if parts else "(no dependency files generated yet)"


# ── Tech profiles ─────────────────────────────────────────────────────────────

@spl_tool
def get_tech_profile(profile: str) -> str:
    return tech_profiles.get_profile(profile)


@spl_tool
def write_settings_config(graph_yaml: str, output_dir: str, profile: str) -> str:
    """Render this app's settings.yaml into a deterministic config module —
    app/config.py (python_fastapi/python_library) or src/config.ts
    (vue_typescript) — so generated code can import settings instead of
    having a literal value baked in by the LLM.

    No GENERATE/LLM call: plain templating from the already-resolved
    settings dict. Changing a value in settings.yaml and re-running only
    this tool is enough to propagate the change to every file that imports
    the config module — see docs/DEV/BUILD/refactoring-plan-v1.md §1.2 for
    why interpolating ${{ settings.X }} into the graph.yaml alone is not
    enough to avoid LLM regeneration.

    Not a graph node: doesn't go through write_node_file/NODE_FILES and
    isn't subject to verify_node — infra, like seed_component_scaffold's
    output. Called once per component, before node generation starts (same
    point in build_component.spl as seed_component_scaffold).
    """
    import json

    settings = _load_app_settings(graph_yaml)
    if not settings:
        return "skipped: no settings.yaml for this app"

    if profile in ("python_fastapi", "python_library"):
        rel_path = "app/config.py"
        lines = ["from __future__ import annotations", ""]
        lines += [f"{key} = {value!r}" for key, value in settings.items()]
    elif profile == "vue_typescript":
        rel_path = "src/config.ts"
        lines = [f"export const {key} = {json.dumps(value)};" for key, value in settings.items()]
    else:
        return f"skipped: no config module convention for profile {profile!r}"

    fpath = Path(output_dir) / rel_path
    fpath.parent.mkdir(parents=True, exist_ok=True)
    fpath.write_text("\n".join(lines) + "\n")
    return str(fpath)


# ── File writing ──────────────────────────────────────────────────────────────

def _looks_like_code(text: str, profile: str) -> bool:
    """Heuristic: reject prose/XML/tool-call output masquerading as code."""
    import re
    # Reject if it starts with prose sentences or XML tags
    prose_patterns = [
        r"^Let me\b", r"^I'll\b", r"^I will\b", r"^Looking at\b", r"^To fix\b",
        r"^<function_calls>", r"^<invoke\b", r"^<parameter\b",
    ]
    for pat in prose_patterns:
        if re.search(pat, text.strip(), re.IGNORECASE):
            return False
    if profile == "python_fastapi":
        # compile() rejects prose mixed with code; regex alone misses embedded code snippets in explanations
        try:
            compile(text.strip(), "<generated>", "exec")
            return True
        except SyntaxError:
            return False
    if profile == "vue_typescript":
        return bool(re.search(r"(export |import |<script|const |function )", text))
    return len(text.strip()) > 20


@spl_tool
def write_node_file(node: str, code: str, graph_yaml: str, output_dir: str, tech_profile: str = "") -> str:
    """Write generated code to the correct file path for this node.

    `tech_profile` should always be passed explicitly by the caller (it's
    already an INPUT to build_component.spl, the only caller) — the previous
    version of this function had no such parameter and instead *guessed* the
    profile from whether the literal substring "backend" appeared in
    `graph.domain`. That worked by coincidence for apps/todo, apps/dispatch,
    apps/expense (all use `domain: software/backend/...` for their backend
    component), but silently mis-detected any component whose domain doesn't
    happen to contain "backend" — e.g. apps/jwt_provider's
    `domain: software/security/jwt` guessed "vue_typescript", writing
    `app/jwt_schemas.py` instead of the `python_library` profile's declared
    `app/schemas.py` (found for real on jwt_provider's first build, 2026-08-13).
    The empty-string default below exists only so an old call site missing
    the argument fails loud (empty string isn't a registered profile in
    tech_profiles.PROFILES) rather than silently guessing wrong again.
    """
    graph = _graph(graph_yaml)
    profile = tech_profile
    is_doc = (graph.nodes.get(node) or {}).get("kind") == "doc"

    app_name = _app_name_from_path(graph_yaml)
    rel_path = tech_profiles.get_node_file(app_name, node)
    if not rel_path:
        rel_path = "README.md" if is_doc else f"app/{node}.py"  # fallback

    # _strip_chat_artifacts first, then _strip_fences(is_doc=is_doc) — a
    # code node's fence-stripping always discards any preamble (see
    # _strip_fences' is_doc docstring); only doc nodes get the
    # length/heading-guarded behavior, since only prose documents can
    # legitimately contain a fenced block partway through.
    clean = _strip_fences(_strip_chat_artifacts(code), is_doc=is_doc)
    # Doc nodes (e.g. a generated README) are prose, not source — the code-shape
    # heuristic below would reject valid Markdown outright (compile() on
    # python_fastapi, the export/import/const regex on vue_typescript).
    if not is_doc and not _looks_like_code(clean, profile):
        import logging
        logging.getLogger(__name__).warning(
            "SKIP WRITE: LLM output for %s does not look like code — file not overwritten. "
            "First 120 chars: %r", node, clean[:120]
        )
        return f"skip: LLM output for {node} does not look like code — file not overwritten"

    fpath = Path(output_dir) / rel_path
    fpath.parent.mkdir(parents=True, exist_ok=True)
    fpath.write_text(clean)
    return str(fpath)


# ── Verification ──────────────────────────────────────────────────────────────

@spl_tool
def verify_node(node: str, code: str, spec: str, graph_yaml: str, tech_profile: str) -> str:
    """Basic static checks: non-empty, no obvious syntax error.

    Doc-kind nodes (e.g. a generated README) are prose, not source — the
    compile() check below would reject valid Markdown as a syntax error.
    """
    is_doc = (_graph(graph_yaml).nodes.get(node) or {}).get("kind") == "doc"
    clean = _strip_fences(_strip_chat_artifacts(code), is_doc=is_doc)
    if not clean:
        return "fail: generated code is empty"
    if not is_doc and tech_profile == "python_fastapi":
        try:
            compile(clean, "<generated>", "exec")
        except SyntaxError as e:
            return f"fail: syntax error — {e}"
    return "ok"


_APP_SCOPED_DEP_SYMBOLS: dict[str, dict[str, list[str]]] = {
    # Some node ids (e.g. "api_client") are reused across many apps'
    # blueprints with genuinely different real content — the shared
    # dep_symbols table below is keyed only by node id, so its "api_client"
    # entry (getTodos/createExpense/moveCard/... — todo/expense/kanban's
    # shape) got applied to todo2A's api_client too, whose real src/api.ts
    # exports only a default `apiClient` axios instance. verify_edges
    # rejected the correctly-implemented task_api node for not containing
    # any of those unrelated symbol names, and refine_node's repair pass
    # then rewrote the ENTIRE file to implement a generic Todo/Expense/Card
    # /Board API just to satisfy the bogus check (real incident, 2026-08-17
    # — reproduced identically on a second independent regeneration,
    # confirming it was the edge-check feedback driving the rewrite, not
    # model hallucination). Checked before the shared dep_symbols table
    # below; app-scoped so it can't affect todo/expense/kanban's own
    # legitimate api_client usage of that shared entry.
    "todo2A": {
        "api_client": ["apiClient"],
    },
}


@spl_tool
def verify_edges(node: str, code: str, graph_yaml: str, tech_profile: str) -> str:
    """Check that all dependency imports appear in the generated code.

    Doc-kind nodes don't "import" their dependencies the way code does —
    skip the symbol check entirely rather than failing on a technicality.
    """
    graph = _graph(graph_yaml)
    if (graph.nodes.get(node) or {}).get("kind") == "doc":
        return "ok"
    deps = _node_deps(graph, node)
    primitives = set(graph.primitives)
    app_name = _app_name_from_path(graph_yaml)
    app_overrides = _APP_SCOPED_DEP_SYMBOLS.get(app_name, {})
    missing = []
    for dep in deps:
        if dep in primitives:
            continue
        # Rough check: at least one symbol from the dep appears in the code
        dep_symbols = {
            # Dispatch incident core backend — merged into the shared "data_schema"/
            # "orm_model" entries above (see the comment there for why).
            "reference_crud":      ["create_priority", "create_severity", "create_incident_type",
                                    "get_priority", "get_severity", "get_incident_type",
                                    "list_priorities", "list_severities", "list_incident_types"],
            "incident_crud":       ["create_incident", "get_incident", "list_incidents",
                                    "update_incident", "delete_incident"],
            # data_schema/orm_model are shared node ids across todo, expense,
            # kanban, dispatch, and fastapi (post-refactor de-prefixing — see
            # docs/DEV/BUILD/refactoring-plan-v1.md §1.4) — each app's symbol set
            # is merged into one list here, same over-inclusive-but-safe pattern
            # already used below for the shared "crud_operations" key: `any(s in
            # code for s in symbols)` only needs ONE match, so merging is a false
            # positive risk in theory but not in practice (these class names don't
            # collide across apps), and it avoids a collision where a later app's
            # entry would silently shadow an earlier one.
            "data_schema":         ["TodoCreate", "Todo", "ToggleRequest",
                                    "ExpenseCreate", "Expense", "ExpenseSummary", "CategorySummary",
                                    "KanbanStatus", "CardCreate", "Card", "MoveRequest", "BoardView",
                                    "PriorityCreate", "PriorityRead", "SeverityCreate", "SeverityRead",
                                    "IncidentTypeCreate", "IncidentTypeRead", "IncidentCreate",
                                    "IncidentRead", "IncidentStatus",
                                    "ItemCreate", "ItemUpdate", "ItemPublic", "ItemBase",
                                    "UserPublic", "UserCreate", "Token", "Message",
                                    "UserRegister", "UserLogin", "UserResponse", "ProfileResponse",
                                    "ArticleCreate", "ArticleUpdate", "ArticleResponse",
                                    "ArticleListResponse", "CommentCreate", "CommentResponse",
                                    "CommentListResponse", "TagListResponse"],
            # db_connection provides Session (type annotation in crud.py) and get_db/Base/SessionLocal
            # (imports in main.py); "Session" covers both cases since crud.py never imports get_db directly
            "db_connection":       ["get_db", "Base", "SessionLocal", "Session"],
            "orm_model":           ["TodoModel", "ExpenseModel", "CardModel",
                                    "IncidentPriority", "IncidentSeverity", "IncidentType", "Incident",
                                    "Item", "User"],
            "crud_operations":     ["get_todos", "create_todo", "toggle_todo", "delete_todo",
                                    "get_expenses", "create_expense", "delete_expense",
                                    "get_cards", "create_card", "move_card", "delete_card"],
            # Expense backend
            "report_aggregator":   ["get_summary"],
            # Kanban backend
            "board_view":          ["get_board"],
            # Shared frontend
            "api_client":          ["getTodos", "createTodo", "toggleTodo", "deleteTodo",
                                    "getExpenses", "createExpense", "deleteExpense", "getSummary",
                                    "getBoard", "getCards", "createCard", "moveCard", "deleteCard"],
            # Todo frontend
            "todo_item_component": ["TodoItem"],
            "todo_list_component": ["TodoList"],
            # Expense frontend
            "ExpenseForm":         ["ExpenseForm"],
            "ExpenseItem":         ["ExpenseItem"],
            "CategoryFilter":      ["CategoryFilter"],
            "ExpenseList":         ["ExpenseList"],
            "SummaryView":         ["SummaryView"],
            "ExpenseDashboard":    ["ExpenseDashboard"],
            # Kanban frontend
            "CardForm":            ["CardForm"],
            "KanbanCard":          ["KanbanCard"],
            "StatusSelect":        ["StatusSelect"],
            "KanbanColumn":        ["KanbanColumn"],
            "KanbanBoard":         ["KanbanBoard"],
            # Fullstack backend (before mealie — longer/more specific patterns).
            # data_schema/orm_model symbols merged into the shared entries above.
            # Conduit backend — two ORM-model modules and two CRUD modules per
            # component (not the single orm_model/crud_operations shape other
            # apps use), so these get their own dedicated entries rather than
            # being merged into a shared key.
            "user_orm_model":      ["UserModel", "follows"],
            "article_orm_model":   ["ArticleModel", "CommentModel", "articles_to_tags", "favorites"],
            "user_crud":           ["register_user", "login_user", "get_current_user_response",
                                    "update_user", "get_profile", "follow_user", "unfollow_user"],
            "article_crud":        ["create_article", "get_article", "list_articles", "get_feed",
                                    "update_article", "delete_article", "favorite_article",
                                    "unfavorite_article", "get_comments", "add_comment",
                                    "delete_comment", "get_all_tags"],
            # security_module/auth_deps symbol lists also cover conduit's shape
            # (create_access_token/get_password_hash/verify_password/get_current_user/
            # CurrentUser overlap directly; conduit's own get_username_from_token/
            # get_current_user_optional/OptionalUser added explicitly below).
            "security_module":     ["create_access_token", "verify_password", "get_password_hash",
                                    "generate_password_reset_token", "verify_password_reset_token",
                                    "get_username_from_token"],
            "auth_deps":           ["get_current_user", "get_current_active_superuser", "CurrentUser",
                                    "get_current_user_optional", "OptionalUser"],
            # Fullstack frontend
            "auth_store":          ["useAuth", "isLoggedIn", "login", "logout"],
            "LoginForm":           ["LoginForm"],
            "ItemForm":            ["ItemForm"],
            "ItemList":            ["ItemList"],
            "ItemDashboard":       ["ItemDashboard"],
            # Mealie backend
            "organizer_schema":    ["RecipeTag", "RecipeCategory", "RecipeTool", "TagSave", "CategorySave"],
            "recipe_schema":       ["CreateRecipe", "RecipeSummary", "Recipe", "RecipeIngredient",
                                    "RecipeStep", "PaginationBase"],
            "organizer_orm_models": ["TagModel", "CategoryModel", "ToolModel",
                                     "recipes_to_tags", "recipes_to_categories", "recipes_to_tools"],
            "recipe_orm_model":    ["RecipeModel", "RecipeIngredientModel", "RecipeInstructionModel"],
            "organizer_crud":      ["get_tags", "create_tag", "get_categories", "create_category",
                                    "get_tools", "create_tool"],
            "recipe_crud":         ["get_recipes", "get_recipe", "create_recipe", "update_recipe",
                                    "delete_recipe"],
            # Mealie frontend
            "recipe_api_client":        ["getRecipes", "getRecipe", "createRecipe", "updateRecipe",
                                         "deleteRecipe", "getTags", "getCategories"],
            "RecipeCard":               ["RecipeCard"],
            "OrganizerFilter":          ["OrganizerFilter"],
            "RecipeIngredientList":     ["RecipeIngredientList"],
            "RecipeForm":               ["RecipeForm"],
            "RecipeDetailView":         ["RecipeDetailView"],
            "RecipeList":               ["RecipeList"],
            "RecipeDashboard":          ["RecipeDashboard"],
            "App_vue":                  ["App"],
            # jwt_provider (node id != the symbol it defines — see the
            # position_event entry below for why an explicit entry matters)
            "jwt_schemas":         ["TokenPayload"],
            # physics_simulator: several node ids name a *concept*, not the
            # symbol they define (position_event defines PositionUpdate, not
            # a `position_event` importable name) — the [dep] default below
            # would otherwise tell refine_node "add the literal substring
            # 'position_event' to your code", which a compliant LLM then does
            # by inventing a bogus `from app.position_event import ...`,
            # corrupting an already-correct `from app.schemas import
            # PositionUpdate` (real incident, 2026-08-13, physics_simulator's
            # first build attempt — see apps/README.md).
            "position_event":      ["PositionUpdate"],
            "velocity_calculator": ["VelocityCalculator", "calculate"],
        }
        symbols = app_overrides.get(dep) or dep_symbols.get(dep, [dep])
        if not any(s in code for s in symbols):
            missing.append(f"{dep} (expected one of: {symbols})")
    if missing:
        return f"fail: missing references to dependencies: {', '.join(missing)}"
    return "ok"


# ── Recipe-79 style component test tools ─────────────────────────────────────
# Same JSON envelope as recipe 79: {passed, failed, returncode, output}
# Works for both python_fastapi (pytest) and vue_typescript (npm test).
# Note: build_component.spl defines its own inline TOOL_API versions of
# run_component_tests / all_tests_passed / get_test_status / get_test_output /
# get_test_summary (the "Recipe-79 style test gate tools" block at the top of
# the .spl file) — those inline definitions take precedence at runtime. The
# copies below exist for callers that use tools.py directly rather than
# through build_component.spl's inline TOOL_API block.

@spl_tool
def run_component_tests(output_dir: str, tech_profile: str) -> str:
    """Run the component test suite; return JSON {passed, failed, returncode, output}."""
    import json, re

    if tech_profile in ("python_fastapi", "python_library", "curriculum"):
        cmd = ["python", "-m", "pytest", "tests/", "-v", "--tb=short", "-q"]
    elif tech_profile == "vue_typescript":
        cmd = ["npm", "test"]
    else:
        return json.dumps({"passed": 0, "failed": 0, "returncode": -1,
                           "output": f"Unknown profile: {tech_profile}"})

    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=output_dir, timeout=120)
    out = (proc.stdout + proc.stderr)

    passed = failed = 0
    for line in out.splitlines():
        if m := re.search(r"(\d+) passed", line):
            passed = int(m.group(1))
        if m := re.search(r"(\d+) failed", line):
            failed = int(m.group(1))

    return json.dumps({"passed": passed, "failed": failed,
                       "returncode": proc.returncode, "output": out[-3000:]})


@spl_tool
def all_tests_passed(test_json: str) -> str:
    """Return 'true' if all tests passed; 'false' otherwise. Use with ASSERT."""
    import json
    try:
        d = json.loads(test_json)
        ok = (d.get("returncode", 1) == 0
              and d.get("failed", 1) == 0
              and d.get("passed", 0) > 0)
        return "true" if ok else "false"
    except Exception:
        return "false"


@spl_tool
def get_test_status(test_json: str) -> str:
    """Return 'passed' or 'failed' — clean string for EVALUATE branching."""
    import json
    try:
        d = json.loads(test_json)
        if (d.get("returncode", 1) == 0
                and d.get("failed", 1) == 0
                and d.get("passed", 0) > 0):
            return "passed"
        return "failed"
    except Exception:
        return "failed"


@spl_tool
def get_test_output(test_json: str) -> str:
    """Extract raw test output for feeding into a repair LLM prompt."""
    import json
    try:
        return json.loads(test_json).get("output", test_json)
    except Exception:
        return test_json


@spl_tool
def get_test_summary(test_json: str) -> str:
    """One-line human-readable summary for logging."""
    import json
    try:
        d = json.loads(test_json)
        return (f"{d.get('passed', 0)} passed, {d.get('failed', 0)} failed "
                f"(exit {d.get('returncode', 1)})")
    except Exception:
        return "unknown"


# ── Cache ─────────────────────────────────────────────────────────────────────
# Disk-backed, keyed on (node, spec, tech_profile) and colocated under
# @output_dir/.spl_cache/ — survives across separate `spl3 run` invocations
# (a plain in-process dict, the previous implementation, does not: a fresh
# CLI process means a fresh empty dict, so every node re-generates on every
# run regardless of unchanged output). Keying on the node's spec text (not
# just its id) means an edited graph.yaml spec correctly misses instead of
# serving stale code; keying on tech_profile separates a node's cache entry
# per profile if the same graph is ever built under two profiles.
#
# Known limitation: the cache key does not include this node's *dependencies'*
# generated content, so if a dependency's code changes but this node's own
# spec text does not, this node's cache entry is not invalidated even though
# node_context() would now feed it different context. Full dependency-aware
# invalidation would need to hash the dependency chain too — related to, but
# not solved by, the blueprint lineage/drift tracking this project is building
# toward (see docs/DEV/BUILD/blueprint-schema-v2.2.md); out of scope here.
#
# Also: cache_put is called after verify_node/verify_edges run (and at most
# one refine_node attempt each), but without re-verifying the refined code —
# a pre-existing gap in build_component.spl's Stage 2 loop. This means a node
# that failed verification, got "refined" once, and still isn't clean can be
# cached and later served as a hit indefinitely. Not fixed here since it's a
# workflow-logic change beyond "make the cache persistent" — flagging it
# because persistence raises the stakes of this gap (previously self-healed
# by every process starting with an empty cache; no longer does).

import hashlib


def _cache_key(node: str, spec: str, tech_profile: str) -> str:
    canonical = json_dumps_stable({"node": node, "spec": spec, "tech_profile": tech_profile})
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def json_dumps_stable(obj: dict) -> str:
    import json
    return json.dumps(obj, sort_keys=True)


def _cache_path(output_dir: str, key: str) -> Path:
    return Path(output_dir) / ".spl_cache" / f"{key}.json"


@spl_tool
def apply_use_cache(cached_value: str, use_cache: str) -> str:
    """Return 'miss' when use_cache=false, forcing regeneration regardless of cache state."""
    return "miss" if use_cache.strip().lower() == "false" else cached_value


@spl_tool
def cache_get(node: str, spec: str, tech_profile: str, output_dir: str, graph_yaml: str) -> str:
    """Return cached code for (node, spec, tech_profile) under output_dir, or 'miss'.

    Honors the node's own `use_cache` attribute in graph.yaml (default true,
    per app-graph's general "absent field = default" convention — see
    docs/DEV/BUILD/blueprint-schema-v2.2.md §4 for the same pattern applied to
    the blueprint: block). Setting `use_cache: false` on one specific node
    forces that node to always miss, independent of every other node's cache
    state and independent of the workflow's global --use_cache flag — the
    fine-grained per-node control the blueprint schema exists to enable:
    force one broken node to regenerate without discarding the whole build.

    Also honors `use_cache: false` on an *incoming* edge (explicit
    `form.edges:` entries only — see docs/DEV/BUILD/blueprint-schema-v2.2.md
    §8.2): forces this node to miss when a dependency it's connected to via
    such an edge is marked as having changed, without needing to also mark
    this node itself.
    """
    import json
    graph = _graph(graph_yaml)
    if not (graph.nodes.get(node) or {}).get("use_cache", True):
        return "miss"
    if any(data.get("use_cache") is False for _, _, data in graph.form_graph.in_edges(node, data=True)):
        return "miss"
    path = _cache_path(output_dir, _cache_key(node, spec, tech_profile))
    if not path.exists():
        return "miss"
    try:
        return json.loads(path.read_text()).get("code", "miss")
    except (json.JSONDecodeError, OSError):
        return "miss"


@spl_tool
def cache_put(node: str, code: str, spec: str, tech_profile: str, output_dir: str) -> str:
    """Persist code for (node, spec, tech_profile) under output_dir. Returns the cache key."""
    import json
    key = _cache_key(node, spec, tech_profile)
    path = _cache_path(output_dir, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "node": node,
        "tech_profile": tech_profile,
        "cached_at": datetime.now(timezone.utc).isoformat(),
        "code": code,
    }, indent=2))
    return key


# ── System-level orchestration (build_app.spl / integrate_system.spl) ────────
# A system graph.yaml (e.g. apps/todo/blueprint/main.graph.yaml) declares `imports:` — a list
# of {id, graph} pairs pointing at independent component graph.yaml files, in
# authored dependency order (backend before frontend). These tools read that
# list directly with yaml.safe_load rather than going through appgraph's
# GraphDomain/resolve_imports() machinery, because build_order/validate_full
# operate *within* one component's node graph — component ordering *between*
# components is a different, much smaller problem (there is no cross-component
# depends_on to topologically sort here, just the authored imports: order) and
# doesn't belong in the core schema library.

import yaml


def _load_yaml(path: str) -> dict:
    """Raw YAML read for orchestration metadata (tech_profile/port/ports) that
    has no field on GraphDomain — see backend.graph.yaml's own comment on why
    this exists as a separate reader from appgraph.load_domain(). Still
    resolves ${{ settings.KEY }} against the app's own settings.yaml (see
    docs/DEV/BUILD/refactoring-plan-v1.md §1.2) so this reader can't diverge
    from what appgraph.load_domain() would resolve for the same file.
    """
    raw = yaml.safe_load(Path(path).read_text())
    return _interpolate_settings(raw, _load_app_settings(path))


def _system_imports(system_yaml: str) -> list[dict]:
    return _load_yaml(system_yaml).get("imports") or []


def _component_graph_path(system_yaml: str, import_entry: dict) -> str:
    """Resolve an imports: entry's relative graph: path against system_yaml's directory."""
    base = Path(system_yaml).parent
    return str((base / import_entry["graph"]).as_posix())


def _component_output_dir(component_graph_path: str, output_dir_override: str = "") -> str:
    """backend.graph.yaml -> backend/ (sibling of the *app root*, same convention as
    tech_profiles.NODE_FILES), unless output_dir_override is set, in which case ->
    {output_dir_override}/backend/ — lets a generated app be saved and tested somewhere
    other than next to its blueprint (e.g. to compare two generations of the same
    graph.yaml side by side without overwriting either).

    Every *.graph.yaml lives under a blueprint/ subfolder (apps/<app>/blueprint/,
    mandatory since 2026-08-13, see docs/DEV/BUILD/blueprint-schema-v2.2.md §6's
    "blueprint/ subfolder convention") — generated code (FUNCTION) is meant to sit
    at the app root instead (apps/<app>/backend/), as a sibling of blueprint/
    (FORM), not nested inside it. Stripping one 'blueprint' path segment (if
    present) keeps that separation instead of writing generated code back into the
    blueprint folder it came from.
    """
    p = Path(component_graph_path)
    component_id = p.name.removesuffix(".graph.yaml")
    if output_dir_override.strip():
        return str(Path(output_dir_override) / component_id)
    app_root = p.parent.parent if p.parent.name == "blueprint" else p.parent
    return str(app_root / component_id)


@spl_tool
def system_components(system_yaml: str) -> str:
    """Newline-joined "id|component_graph_path" pairs, in authored imports: order."""
    lines = []
    for entry in _system_imports(system_yaml):
        gpath = _component_graph_path(system_yaml, entry)
        lines.append(f"{entry['id']}|{gpath}")
    return "\n".join(lines)


@spl_tool
def component_count(components: str) -> str:
    return str(len([l for l in components.splitlines() if l.strip()]))


@spl_tool
def component_item(components: str, index: str) -> str:
    return [l for l in components.splitlines() if l.strip()][int(index)]


@spl_tool
def component_id(item: str) -> str:
    return item.split("|", 1)[0]


@spl_tool
def component_graph(item: str) -> str:
    return item.split("|", 1)[1]


@spl_tool
def component_tech_profile(component_graph_path: str) -> str:
    return _load_yaml(component_graph_path).get("tech_profile", "")


@spl_tool
def component_port(component_graph_path: str) -> str:
    return str(_load_yaml(component_graph_path).get("port", ""))


@spl_tool
def ensure_component_metadata(candidate_yaml: str, tech_profile: str, port_settings_key: str) -> str:
    """Insert top-level `tech_profile:`/`port:` lines if the candidate is missing them.

    build_app.spl reads these via component_tech_profile()/component_port() above
    (plain yaml.safe_load, no default) — but decompose_intent's prompt example
    never demonstrates them, since they're orchestration metadata with no field
    on GraphDomain (see backend.graph.yaml's own comment on this), so an
    extraction-mode candidate reliably comes back without them, which fails
    build_app.spl with "Unknown tech profile ''" the first time anyone tries to
    build it (seen in practice on todo1). The correct values are already known
    deterministically here (the caller's own @profile_name / the fixed
    BACKEND_FASTAPI_PORT/FRONTEND_VITE_PORT convention appgraph extract itself
    uses when writing settings.yaml) — patching them in beats re-prompting the
    LLM to guess a value we already have.
    """
    import re
    clean = _strip_fences(_strip_chat_artifacts(candidate_yaml))
    if re.search(r"^tech_profile:", clean, re.MULTILINE):
        return clean  # already present — don't duplicate the key
    return f"tech_profile: {tech_profile}\nport: ${{{{ settings.{port_settings_key} }}}}\n{clean}"


@spl_tool
def component_output_dir(component_graph_path: str, output_dir: str = "") -> str:
    return _component_output_dir(component_graph_path, output_dir)


@spl_tool
def check_port_consistency(system_yaml: str) -> str:
    """Report any component whose own declared `port:` disagrees with the
    system graph.yaml's `ports:` block, joined one per line, or "" if none.

    Same class of check as contract_warnings() (§9.1) — compares two yaml-
    declared values against each other, catching authoring drift (editing one
    side without the other), not a live runtime port collision (e.g. a second
    Vite dev server instance silently falling back to a different port because
    the declared one was already taken — see apps/todo/blueprint/main.graph.yaml's `ports:`
    comment for the real incident that motivated this).
    """
    declared = _load_yaml(system_yaml).get("ports") or {}
    violations = []
    for entry in _system_imports(system_yaml):
        component_id = entry["id"]
        if component_id not in declared:
            continue
        gpath = _component_graph_path(system_yaml, entry)
        own_port = _load_yaml(gpath).get("port")
        if own_port is not None and own_port != declared[component_id]:
            violations.append(
                f"{component_id}: system declares port {declared[component_id]}, "
                f"{gpath} declares port {own_port}"
            )
    return "\n".join(violations)


@spl_tool
def check_components_verified(system_yaml: str, output_dir: str = "") -> str:
    """'ready' if every imported component's output dir exists and is non-empty, else 'not_ready: <ids>'.

    Deliberately lightweight: build_component.spl already ASSERTs its own test
    suite passes before returning (build_app.spl halts on a FAILED manifest
    before ever reaching integrate_system.spl), so by the time this runs, a
    populated output dir *is* the verification signal — this does not re-run
    each component's tests a second time.
    """
    not_ready = []
    for entry in _system_imports(system_yaml):
        gpath = _component_graph_path(system_yaml, entry)
        out_dir = Path(_component_output_dir(gpath, output_dir))
        if not out_dir.is_dir() or not any(out_dir.iterdir()):
            not_ready.append(entry["id"])
    return "ready" if not not_ready else f"not_ready: {', '.join(not_ready)}"


# Pre-authored scaffold — not generated by any blueprint node, manually
# copied in once from graph-driven-workflow's reference components during
# earlier prototyping (docs/DEV/BUILD/README.md §7.4). tests/ exists for both
# profiles; the rest is vue_typescript's npm/vite project scaffold (python_fastapi
# needs no equivalent — pytest/FastAPI need no project-level config file).
# node_modules/ is deliberately NOT copied (large, and copying a dependency
# tree instead of installing it risks silently drifting from package.json) —
# `npm install` must be run by hand in a redirected frontend output_dir.
_SCAFFOLD_PATHS: dict[str, list[str]] = {
    "python_fastapi": ["tests"],
    "vue_typescript": ["tests", "package.json", "package-lock.json",
                        "vite.config.ts", "tsconfig.json", "index.html", ".env"],
    "python_library": ["tests"],
}


@spl_tool
def _bootstrap_vue_scaffold(target_dir: Path) -> str:
    """Bootstrap a brand-new vue_typescript project shell — see
    appgraph.scaffolding.bootstrap_vue_scaffold for the full docstring;
    this is a thin @spl_tool-decorated wrapper so build_component.spl can
    call it, sharing the exact same implementation `appgraph tools
    scaffold-vue` uses.
    """
    from appgraph.scaffolding import bootstrap_vue_scaffold
    return bootstrap_vue_scaffold(target_dir)


@spl_tool
def _bootstrap_fastapi_scaffold(target_dir: Path) -> str:
    """Bootstrap a brand-new python_fastapi project shell — see
    appgraph.scaffolding.bootstrap_fastapi_scaffold for the full
    docstring; thin @spl_tool wrapper sharing the same implementation
    `appgraph tools scaffold-fastapi` uses.
    """
    from appgraph.scaffolding import bootstrap_fastapi_scaffold
    return bootstrap_fastapi_scaffold(target_dir)


@spl_tool
def seed_component_scaffold(component_graph_path: str, tech_profile: str, output_dir: str) -> str:
    """Copy this component's pre-authored scaffold (tests/, and for
    vue_typescript its npm/vite project files) into a redirected output_dir.

    Redirecting `output_dir` (§12.1) means a brand-new directory with none of
    this scaffold — build_component.spl's Stage 3 test gate then correctly
    halts (python_fastapi: "No tests/ directory ... nothing to verify", exit 4;
    vue_typescript: "No package.json ... nothing to verify", exit 254 — both
    confirmed on real runs, 2026-08-12). This seeds the default (non-redirected)
    location's scaffold into the redirected one before the build runs, since
    both share the same blueprint/spec and should be verified against the same
    fixtures/config. Per-path skip (not clobbered) if the destination already
    exists, per-path skip if the source doesn't exist to seed from. For
    vue_typescript, `npm install` must still be run by hand in the redirected
    dir afterward — node_modules/ is not copied.

    When `output_dir` is empty (no redirection — the common case for a new
    app's first build), a component whose default location has no scaffold
    yet gets one bootstrapped automatically instead of silently no-op'ing:
    vue_typescript via `npm create vue@latest` (see _bootstrap_vue_scaffold),
    python_fastapi via a hand-rolled minimal skeleton (see
    _bootstrap_fastapi_scaffold, since FastAPI ships no official
    "create-fastapi-app" CLI to wrap) — this is what used to require a human
    to hand-copy scaffold files in once per app before its first build.
    """
    if not output_dir.strip():
        default_dir = Path(_component_output_dir(component_graph_path))
        if tech_profile == "vue_typescript" and not (default_dir / "package.json").exists():
            return _bootstrap_vue_scaffold(default_dir)
        if tech_profile == "python_fastapi" and not (default_dir / "tests").exists():
            return _bootstrap_fastapi_scaffold(default_dir)
        return "no-op: no output_dir redirection"
    default_dir = Path(_component_output_dir(component_graph_path))
    target_dir = Path(_component_output_dir(component_graph_path, output_dir))
    if target_dir == default_dir:
        return "no-op: output_dir resolves to the default location"

    import shutil
    results = []
    for rel in _SCAFFOLD_PATHS.get(tech_profile, []):
        src = default_dir / rel
        dst = target_dir / rel
        if dst.exists():
            results.append(f"skip {rel} (exists)")
            continue
        if not src.exists():
            results.append(f"skip {rel} (no source)")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
        results.append(f"seeded {rel}")
    return "; ".join(results) if results else "no-op: no scaffold paths for this profile"


@spl_tool
def run_build_component(component_graph_path: str, tech_profile: str, output_dir: str,
                         log_dir: str, llm: str) -> str:
    """Build one component by shelling out to `spl3 run spl/build_component.spl`.

    There is no CALL-able workflow-composition primitive in spl3 (searched
    SPL.py/spl3/cli.py and the wider SPL.py source — the only `run_workflow`
    that exists is `_run_workflow`, an internal asyncio helper used by the CLI's
    own `run`/`resume` commands, not something a .spl script can invoke). The
    graph-driven-workflow project's original build_app.spl assumed a
    `CALL run_workflow("build_component", ...)` primitive that was never
    actually implemented anywhere. This subprocess call is the real mechanism —
    it does exactly what running `spl3 run spl/build_component.spl ...` by hand
    (as documented throughout docs/DEV/BUILD/README.md §7) already does, just
    invoked programmatically from within build_app.spl.
    """
    return _run_spl_subprocess("build_component.spl", {
        "component_graph": component_graph_path,
        "tech_profile": tech_profile,
        "output_dir": output_dir,
        "log_dir": log_dir,
    }, llm, log_dir)


@spl_tool
def run_integrate_system(system_yaml: str, log_dir: str, llm: str, output_dir: str = "") -> str:
    """Run system integration by shelling out to `spl3 run spl/integrate_system.spl`. See run_build_component."""
    params = {"system_yaml": system_yaml, "log_dir": log_dir}
    if output_dir.strip():
        params["output_dir"] = output_dir
    return _run_spl_subprocess("integrate_system.spl", params, llm, log_dir)


def _run_spl_subprocess(spl_file: str, params: dict[str, str], llm: str, log_dir: str) -> str:
    """Run one .spl workflow as a subprocess; return a short, unambiguous status
    string for EVALUATE branching, with the full transcript written to disk.

    The full stdout+stderr transcript is NOT returned here on purpose. An
    earlier version returned up to 4000 raw chars of subprocess log directly,
    which `build_app.spl`'s `EVALUATE @comp_manifest WHEN contains("FAILED")`
    then branched on — `spl3 explain` marks that EVALUATE `(semantic)`,
    meaning spl3 judges it via an LLM call rather than a literal substring
    match, and a multi-hundred-line dump containing phrases like "0 failed"
    and "Test attempt 1" got misjudged as a failure on a real run where the
    component actually built cleanly (22/22 tests, exit 0) — see
    docs/DEV/BUILD/README.md §12.2. Keeping the branched-on value to one
    short, unambiguous line avoids feeding the classifier something it can
    misread; the full transcript is still available in the log file for
    debugging either outcome.

    A non-zero exit code is NOT the only failure signal checked. spl3's CLI
    prints `Status:  complete` for any workflow that ran to completion
    without an engine-level crash — including one whose own `RETURN` value is
    a literal `"FAILED: ..."`/`"BLOCKED: ..."` string, e.g. integrate_system's
    `RETURN f"FAILED:{@report}"` when an acceptance test fails. That workflow
    still exits 0. Confirmed on a real run (2026-08-12, see
    docs/DEV/BUILD/README.md §12.2): a real `toggle_todo` acceptance-test
    failure inside `integrate_system.spl` was reported as `"ok"` here and
    `build_app.spl` then logged "System build complete" — a false negative.
    Fixed by also parsing the printed `Output:  ...` block (the workflow's own
    RETURN value, echoed verbatim by spl3's CLI) and treating a
    FAILED/BLOCKED/HALTED prefix there as failure too, independent of exit code.
    """
    repo_root = _SPL_DIR.parent
    cmd = [_spl3_bin(), "run", str(_SPL_DIR / spl_file), "--tools", str(_SPL_DIR / "tools.py")]
    if llm:
        cmd += ["--llm", llm]
    for k, v in params.items():
        cmd += ["-p", f"{k}={v}"]
    proc = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True, timeout=1800)
    full = proc.stdout + proc.stderr

    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    log_path = Path(log_dir) / f"{Path(spl_file).stem}.{ts}.subprocess.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(full)

    return_value = _extract_return_value(full)
    content_failed = return_value.strip().upper().startswith(("FAILED", "BLOCKED", "BUILD HALTED"))

    if proc.returncode != 0:
        last_line = next((l for l in reversed(full.splitlines()) if l.strip()), "")
        return f"FAILED (exit {proc.returncode}): {last_line} — full log: {log_path}"
    if content_failed:
        first_line = next((l for l in return_value.splitlines() if l.strip()), "")
        return f"FAILED (workflow returned failure): {first_line} — full log: {log_path}"
    return f"ok — full log: {log_path}"


def _extract_return_value(full_output: str) -> str:
    """Pull the workflow's own RETURN value out of spl3's `Output:  ...` block."""
    marker = "\nOutput:  "
    idx = full_output.rfind(marker)
    if idx == -1:
        return ""
    tail = full_output[idx + len(marker):]
    end = tail.find("\nLLM calls:")
    return tail[:end] if end != -1 else tail


# ── System-level applications (apps/todo/blueprint/main.graph.yaml's `applications:` block) ──

@spl_tool
def system_applications(system_yaml: str) -> str:
    """Newline-joined application ids, in declared order, excluding the capstone
    application (identified by `capstone: true`) — it composes the other four
    rather than adding an independent acceptance test of its own contract."""
    apps = _load_yaml(system_yaml).get("applications") or {}
    return "\n".join(app_id for app_id, spec in apps.items() if not spec.get("capstone"))


@spl_tool
def app_count(apps: str) -> str:
    return str(len([l for l in apps.splitlines() if l.strip()]))


@spl_tool
def app_item(apps: str, index: str) -> str:
    return [l for l in apps.splitlines() if l.strip()][int(index)]


@spl_tool
def app_spec_text(app_id: str, system_yaml: str) -> str:
    """user_story + contract for one application, for acceptance-test generation."""
    apps = _load_yaml(system_yaml).get("applications") or {}
    spec = (apps.get(app_id) or {}).get("spec") or {}
    return _fmt_spec(spec) if spec else f"(no spec declared for application {app_id})"


@spl_tool
def app_backend_endpoints(app_id: str, system_yaml: str) -> str:
    """Describe the live backend HTTP endpoints this application's acceptance
    test should hit, resolved from backend.graph.yaml's function.exports —
    scoped to backend only (see integrate_system.spl's module docstring for
    why acceptance tests here are HTTP-level against the live backend, not
    full browser E2E against the frontend).

    Also appends the spec.interface text of any backend node whose id or
    defines-text mentions 'schema' — export signatures only ever show a
    bare type name for request/response bodies (e.g. `body:TaskCreate`),
    never the field shape, so without this the generated test has to guess
    field names from scratch."""
    apps = _load_yaml(system_yaml).get("applications") or {}
    needs = (apps.get(app_id) or {}).get("needs") or {}
    # needs.backend entries carry a "backend." component prefix (e.g.
    # "backend.task_routes"), but function.exports[].from and form.nodes
    # keys are bare node ids within that component's own graph — strip it.
    backend_nodes = {n.split(".", 1)[-1] for n in (needs.get("backend") or [])}
    if not backend_nodes:
        return "(no backend nodes declared for this application)"

    entry = next((e for e in _system_imports(system_yaml) if e["id"] == "backend"), None)
    if entry is None:
        return "(no backend component imported by this system graph)"
    backend_yaml = _load_yaml(_component_graph_path(system_yaml, entry))
    exports = backend_yaml.get("function", {}).get("exports") or []
    lines = []
    for exp in exports:
        node_id = exp.get("from", "").split(".")[0]
        if node_id in backend_nodes:
            lines.append(f"{exp.get('name')}: {exp.get('signature')}")
    port = backend_yaml.get("port", 8000)
    header = f"Live backend base URL: http://localhost:{port}"
    body = header + "\n" + "\n".join(lines) if lines else header

    # Request/response body shapes are always included, regardless of
    # whether this application's own needs.backend happens to list the
    # schema node — an acceptance test that only *needs* task_routes/crud
    # for its own contract (e.g. delete_task, filter_tasks) still has to
    # seed data via POST first, and guesses generic field names without
    # this (see apps/todo1's original acceptance-test failures).
    nodes = backend_yaml.get("form", {}).get("nodes") or {}
    schema_blocks = []
    for node_id, node in nodes.items():
        if "schema" in node_id.lower() or "schema" in (node.get("defines") or "").lower():
            interface = (node.get("spec") or {}).get("interface")
            if interface:
                schema_blocks.append(f"# {node_id} request/response shapes\n{interface}")
    if schema_blocks:
        body += "\n\n" + "\n\n".join(schema_blocks)
    return body


@spl_tool
def system_readme_spec_text(system_yaml: str) -> str:
    """spec text for the system-level `readme` node in graph.yaml's form.nodes, for GENERATE."""
    nodes = _load_yaml(system_yaml).get("form", {}).get("nodes") or {}
    spec = (nodes.get("readme") or {}).get("spec") or {}
    return _fmt_spec(spec) if spec else "(no spec declared for the system-level readme node)"


@spl_tool
def write_system_readme_file(content: str, system_yaml: str, output_dir: str) -> str:
    """Write the generated system-level README.md at the app root, or under output_dir if set.

    Same 'strip one blueprint/ path segment' convention as _component_output_dir() — system_yaml
    lives under apps/<app>/blueprint/main.graph.yaml, but the product-level README belongs at
    apps/<app>/README.md (a sibling of blueprint/), not inside the blueprint/ folder it was
    authored from. Without this, the default (no -p output_dir) previously wrote the generated
    README back into blueprint/, alongside the graph.yaml sources instead of at the app root
    every other generated artifact uses — found while generating apps/mealie/README.md.
    """
    clean = _strip_chat_artifacts(_strip_fences(content))
    if output_dir.strip():
        base = Path(output_dir)
    else:
        p = Path(system_yaml).parent
        base = p.parent if p.name == "blueprint" else p
    fpath = base / "README.md"
    fpath.parent.mkdir(parents=True, exist_ok=True)
    fpath.write_text(clean)
    return str(fpath)


@spl_tool
def write_test_file(app_id: str, test_code: str, output_dir: str) -> str:
    clean = _strip_fences(_strip_chat_artifacts(test_code))
    fpath = Path(output_dir) / f"test_acceptance_{app_id}.py"
    fpath.parent.mkdir(parents=True, exist_ok=True)
    fpath.write_text(clean)
    return str(fpath)


@spl_tool
def run_acceptance_test(test_path: str) -> str:
    """Run one generated acceptance test script; return 'PASS' or 'FAIL: <output tail>'."""
    proc = subprocess.run(["python", test_path], capture_output=True, text=True, timeout=60)
    if proc.returncode == 0:
        return "PASS"
    return f"FAIL: {(proc.stdout + proc.stderr)[-2000:]}"


# ── Server lifecycle (integrate_system.spl) ───────────────────────────────────

@spl_tool
def start_backend_server(output_dir: str, port: str) -> str:
    """Start the generated FastAPI backend with uvicorn as a background process; return its PID."""
    log = open(Path(output_dir) / "server.log", "w")
    proc = subprocess.Popen(
        ["uvicorn", "app.main:app", "--port", port],
        cwd=output_dir, stdout=log, stderr=subprocess.STDOUT,
    )
    return str(proc.pid)


@spl_tool
def wait_for_http(url: str, timeout_s: str) -> str:
    """Poll a URL until it responds or timeout_s elapses; return 'ready' or 'timeout'."""
    import urllib.error
    import urllib.request
    deadline = time.time() + float(timeout_s)
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=2)
            return "ready"
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.5)
    return "timeout"


@spl_tool
def stop_process(pid: str) -> str:
    import os
    import signal
    try:
        os.kill(int(pid), signal.SIGTERM)
        return "stopped"
    except (ProcessLookupError, ValueError):
        return "not_running"


# ── Compile: NL intent -> blueprint graph.yaml (compile_blueprint.spl) ────────
# "compile" per README-TODO.md §1's action item 1b — deliberately checks only
# structural validity (parses, passes validate_full()), not intent fidelity;
# see compile_blueprint.spl's header comment and blueprint-schema-v2.2.md for
# why that's the right scope, not a shortcut.

@spl_tool
def validate_blueprint_yaml(candidate_yaml: str, settings_dir: str = "") -> str:
    """Return 'ok' if candidate_yaml parses and passes validate_full(), else 'error: <message>'.

    load_domain() only accepts a path, so the candidate is written to a
    throwaway temp file first — the same reject-before-generate pattern used
    everywhere else in this project (ToolFailed before any further work),
    just applied to a compile candidate instead of to an already-generated
    component's code.

    settings_dir, if given, is the app's blueprint/ dir (appgraph extract
    always writes blueprint/settings.yaml before the LLM pass runs) — the
    temp file is created *inside* it so load_domain()'s settings.py sibling
    lookup finds the real settings.yaml instead of resolving against a bare
    /tmp dir, where every ${{ settings.KEY }} reference (e.g. the ports:
    block decompose_main_graph's own prompt template teaches the LLM to
    write) would otherwise always fail as "unresolved".
    """
    import tempfile
    clean = _strip_fences(_strip_chat_artifacts(candidate_yaml))
    try:
        parsed = yaml.safe_load(clean)
    except yaml.YAMLError as e:
        return f"error: not valid YAML — {e}"
    if not isinstance(parsed, dict):
        return "error: candidate did not parse to a YAML mapping at the top level"

    tmp_dir = settings_dir if settings_dir and Path(settings_dir).is_dir() else None
    with tempfile.NamedTemporaryFile(mode="w", suffix=".graph.yaml", dir=tmp_dir, delete=False) as f:
        f.write(clean)
        tmp_path = f.name
    try:
        graph = appgraph.load_domain(tmp_path)
        appgraph.validate_full(graph)
        # composed_of/depends_on targets that were never declared under
        # form.nodes get silently auto-created as bare graph nodes by
        # networkx's add_edge (loader._build_form_graph) — validate_full()
        # doesn't catch this because the graph is still a valid DAG. Without
        # this check a candidate can reference e.g. 8 routers by name in
        # composed_of/function.exports/verification and pass validation while
        # actually only spec'ing 1 of them (seen in practice on a 55-route
        # extraction that came back "ok" with 2 real nodes).
        # imports: ids (e.g. `backend`/`frontend` in a main.graph.yaml) are
        # legitimately referenced by depends_on/composed_of without a
        # form.nodes entry of their own — they're declared under imports:
        # instead. Exclude them from both checks below.
        imported = {imp.get("id") for imp in graph.imports if imp.get("id")}
        dangling = sorted(
            nid for nid, data in graph.form_graph.nodes(data=True)
            if "_kind" not in data and nid not in imported
        )
        # Top-level verification: entries aren't wired into form_graph at all
        # (loader.py never turns them into edges), so they need their own
        # check against the declared id set.
        declared = set(graph.primitives) | set(graph.nodes) | imported
        dangling_verification = sorted(
            {v.get("node") for v in graph.verification if v.get("node") and v.get("node") not in declared}
        )
        dangling = sorted(set(dangling) | set(dangling_verification))
        if dangling:
            return (
                "error: these ids are referenced (composed_of/depends_on/exports/"
                "verification) but have no form.nodes entry of their own — add a "
                f"real node (kind/defines/tier/spec) for each: {', '.join(dangling)}"
            )
    except Exception as e:  # noqa: BLE001 - deliberately broad: any failure here is "invalid candidate"
        return f"error: {type(e).__name__}: {e}"
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    return "ok"


@spl_tool
def write_blueprint_file(candidate_yaml: str, output_path: str) -> str:
    """Write a validated compile candidate to output_path. Caller must have already confirmed 'ok'."""
    clean = _strip_fences(_strip_chat_artifacts(candidate_yaml))
    fpath = Path(output_path)
    fpath.parent.mkdir(parents=True, exist_ok=True)
    fpath.write_text(clean)
    return str(fpath)


# ── Compile from extraction: shape classification (compile_blueprint.spl's
# 'extraction' mode, used by `appgraph extract --llm`) ─────────────────────────
# classify_shape()'s prompt is contracted to output exactly two lines
# (`SHAPE: ...` / `PROFILE: ...`) specifically so these can be parsed with a
# literal line-prefix match instead of an EVALUATE ... WHEN contains(...)
# semantic (LLM-judged) branch — see _run_spl_subprocess's docstring above for
# a real false-positive incident caused by branching on fuzzy LLM-judged text.

@spl_tool
def classification_shape(classification: str) -> str:
    """Parse the 'SHAPE: ...' line out of classify_shape()'s output. Defaults to
    'NO_FIT' (the safe/conservative branch) if the line is missing or malformed."""
    for line in classification.splitlines():
        line = line.strip()
        if line.upper().startswith("SHAPE:"):
            value = line.split(":", 1)[1].strip().upper()
            if value in ("INTEGRATED", "SINGLE", "NO_FIT"):
                return value
    return "NO_FIT"


@spl_tool
def classification_profile(classification: str) -> str:
    """Parse the 'PROFILE: ...' line out of classify_shape()'s output."""
    for line in classification.splitlines():
        line = line.strip()
        if line.upper().startswith("PROFILE:"):
            return line.split(":", 1)[1].strip()
    return ""


@spl_tool
def is_known_tech_profile(profile_name: str) -> str:
    """'true' if profile_name is an existing key in tech_profiles.PROFILES, else 'false'."""
    return "true" if profile_name.strip() in tech_profiles.PROFILES else "false"


@spl_tool
def write_tech_profile_draft(draft_text: str, output_path: str) -> str:
    """Write a proposed-but-unmerged tech_profile writeup to output_path (Markdown).

    Deliberately NOT written into spl/tech_profiles.py's PROFILES/VERIFY_CMDS
    dicts — those are a shared, repo-wide style guide governing every future
    app of that shape, so a new one is a reviewable draft a human merges in,
    never an automatic write (confirmed with the user, 2026-08-14).
    """
    clean = _strip_fences(_strip_chat_artifacts(draft_text))
    fpath = Path(output_path)
    fpath.parent.mkdir(parents=True, exist_ok=True)
    fpath.write_text(clean)
    return str(fpath)


# ── Timing and logging ────────────────────────────────────────────────────────

@spl_tool
def now_float() -> str:
    return str(time.time())


@spl_tool
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@spl_tool
def sanitize_ts(ts: str) -> str:
    return ts.replace(":", "-").replace("+", "").replace(".", "_")[:23]


@spl_tool
def make_log_path(log_dir: str, ts_safe: str) -> str:
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    return str(Path(log_dir) / f"build_{ts_safe}.md")


@spl_tool
def write_file(path: str, content: str, mode: str = "w") -> str:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, mode) as f:
        f.write(content)
    return path


@spl_tool
def time_elapsed(start: str) -> str:
    return f"{time.time() - float(start):.1f}"
