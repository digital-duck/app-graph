import asyncio
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, HTTPException

from api.routers.graphs import APPS_ROOT, _resolve_root

router = APIRouter(prefix="/api/build", tags=["build"])

# Single in-flight build at a time — Graph IDE is a single-user local tool,
# no need for a job queue. State is polled by the frontend, not pushed.
_state: dict[str, Any] = {"status": "idle", "root": None, "returncode": None, "output": ""}
_process: asyncio.subprocess.Process | None = None


def _resolve_output_dir(output_dir: str) -> Path:
    """A relative path is resolved against APPS_ROOT, same convention as
    `root` — so typing e.g. "todo2A-test" writes generated code next to the
    other apps, not relative to the backend's own cwd (tools/graph-ide),
    which is what a bare relative path passed straight to the `grafcode
    build` subprocess would otherwise resolve against."""
    p = Path(output_dir)
    return p if p.is_absolute() else (APPS_ROOT / p).resolve()


def _resolve_graph_path(app_dir: Path) -> Path:
    blueprint = app_dir / "blueprint"
    for name in ("main.graph.yaml", "component.graph.yaml"):
        p = blueprint / name
        if p.exists():
            return p
    raise HTTPException(404, f"no main.graph.yaml or component.graph.yaml under {blueprint}")


async def _run_build(root: str, graph_path: Path, output_dir: Path | None) -> None:
    global _process
    _state.update(status="running", root=root, returncode=None, output="")
    try:
        cmd = ["grafcode", "build", str(graph_path)]
        if output_dir is not None:
            cmd += ["--output-dir", str(output_dir)]
        _process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
        )
        chunks: list[str] = []
        assert _process.stdout is not None
        async for line in _process.stdout:
            chunks.append(line.decode(errors="replace"))
            _state["output"] = "".join(chunks)[-8000:]
        returncode = await _process.wait()
        _state.update(status="done" if returncode == 0 else "error", returncode=returncode)
    except Exception as exc:
        # Covers spawn failures too (e.g. `grafcode` not on PATH) — without
        # this, an exception here leaves status stuck at "running" forever,
        # with no _process for /cancel to act on and no way for the UI to
        # recover short of restarting the server.
        _state.update(status="error", returncode=None, output=f"[graph-ide] failed to run build: {exc}")
    finally:
        _process = None


@router.post("")
async def start_build(payload: dict[str, Any] = Body(...)):
    root = str(payload.get("root", "")).strip()
    if not root:
        raise HTTPException(400, "root is required")
    if _state["status"] == "running":
        raise HTTPException(409, f"a build is already running (root={_state['root']})")
    app_dir = _resolve_root(root)
    graph_path = _resolve_graph_path(app_dir)
    output_dir_raw = str(payload.get("output_dir", "")).strip()
    output_dir = _resolve_output_dir(output_dir_raw) if output_dir_raw else None
    asyncio.create_task(_run_build(root, graph_path, output_dir))
    return {"status": "started", "root": root, "graph_path": str(graph_path),
            "output_dir": str(output_dir) if output_dir else None}


@router.get("/status")
def build_status():
    return dict(_state)


@router.post("/cancel")
def cancel_build():
    if _process is None:
        raise HTTPException(400, "no build running")
    _process.terminate()
    return {"status": "cancelling"}
