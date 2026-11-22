import json
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, HTTPException

from api.graph_discovery import build_graph
from api.graph_writer import InvalidField, NodeNotFound, WriteFailed, update_node

router = APIRouter(prefix="/api/graphs", tags=["graphs"])

# Same ~/app-graph workspace convention as the rest of appgraph (see
# _workspace_root() in cli.py) — the apps root a user picks in Settings
# persists here across `appgraph ide` restarts.
_DEFAULT_APPS_ROOT = Path.home() / "app-graph" / "ide"
_SETTINGS_PATH = Path.home() / "app-graph" / ".ide_settings.json"


def _load_saved_apps_root() -> Path | None:
    try:
        data = json.loads(_SETTINGS_PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    saved = data.get("apps_root")
    if saved and Path(saved).is_dir():
        return Path(saved)
    return None


def _save_apps_root_setting(path: Path) -> None:
    _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _SETTINGS_PATH.write_text(json.dumps({"apps_root": str(path)}, indent=2))


def _find_checkout_apps_root() -> Path | None:
    """Walk up from this file looking for a app-graph checkout's own apps/
    (a directory with both pyproject.toml and apps/ alongside it) — used as
    the very first default, before ~/app-graph/ide, when this Graph IDE is
    itself running from inside a checkout. Depth-independent by design: a
    fixed `.parents[N]` count previously broke silently when spl/graph-ide
    moved a level deeper under src/appgraph/."""
    here = Path(__file__).resolve()
    for candidate in (here, *here.parents):
        if (candidate / "pyproject.toml").is_file() and (candidate / "apps").is_dir():
            return candidate / "apps"
    return None


# Precedence: `appgraph ide --apps-root ...` (sets APPGRAPH_APPS_ROOT, an
# explicit choice for *this* launch) > the last root saved via the Settings
# page (persists across restarts) > this checkout's own apps/, if Graph IDE
# is running from inside one > ~/app-graph/ide.
_env_root = os.environ.get("APPGRAPH_APPS_ROOT")
if _env_root:
    APPS_ROOT = Path(_env_root).resolve()
else:
    APPS_ROOT = _load_saved_apps_root() or _find_checkout_apps_root() or _DEFAULT_APPS_ROOT
APPS_ROOT.mkdir(parents=True, exist_ok=True)


def set_apps_root(path: Path) -> None:
    """Change the apps root at runtime and persist it for future launches."""
    global APPS_ROOT
    APPS_ROOT = path
    _save_apps_root_setting(path)


def _resolve_root(root: str) -> Path:
    app_root = (APPS_ROOT / root).resolve()
    if APPS_ROOT not in app_root.parents and app_root != APPS_ROOT:
        raise HTTPException(400, "root must be inside the apps root")
    if not app_root.is_dir():
        raise HTTPException(404, f"no such directory: {root}")
    return app_root


@router.get("/roots")
def list_roots():
    """Every app under APPS_ROOT with a blueprint/ subfolder containing at
    least one *.graph.yaml, as paths relative to APPS_ROOT — powers the
    dropdown. Convention since 2026-08-14 (see
    docs/DEV/BUILD/blueprint-schema-v2.2.md's "blueprint/ subfolder
    convention" addendum): every graph.yaml lives under
    <app>/blueprint/, generated code as a sibling of blueprint/.
    Generated-target dirs (e.g. todo-v2, expense-v2 — the build *output* of
    an app, not its blueprint source) have no blueprint/ and are correctly
    excluded here; there is nothing for graph-ide to render for them.
    """
    if not APPS_ROOT.is_dir():
        return []
    roots = sorted(
        {
            str(p.parent.parent.relative_to(APPS_ROOT))
            for p in APPS_ROOT.glob("*/blueprint/*.graph.yaml")
        }
    )
    return roots


@router.get("")
def get_graph(root: str):
    """root is a path relative to APPS_ROOT, e.g. todo"""
    return build_graph(_resolve_root(root))


@router.patch("/nodes/{node_id}")
def patch_node(node_id: str, root: str, fields: dict[str, Any] = Body(...)):
    """Update a node's editable prose fields (defines, docs, spec.interface,
    spec.contract, spec.user_story, verification.node, verification.edge) in
    its owning graph.yaml. `fields` is a partial patch, e.g.
    {"defines": "...", "spec": {"contract": "..."}}. Structural fields
    (composed_of, depends_on, needs, tier, capstone) aren't editable yet.
    """
    app_root = _resolve_root(root)
    try:
        return update_node(app_root, node_id, fields)
    except NodeNotFound:
        raise HTTPException(404, f"no such node: {node_id}")
    except InvalidField as e:
        raise HTTPException(422, str(e))
    except WriteFailed as e:
        raise HTTPException(422, str(e))
