import asyncio
import json
from typing import Any

from fastapi import APIRouter, Body, HTTPException

from api.routers.graphs import APPS_ROOT

router = APIRouter(prefix="/api/drift", tags=["drift"])

# appgraph ide runs this backend with cwd=tools/graph-ide, not the repo
# root, so a UI-typed relative path like "apps/todo/blueprint/main.graph.yaml"
# must be resolved (via subprocess cwd) against APPS_ROOT.parent, the
# actual repo root.
_REPO_ROOT = APPS_ROOT.parent


@router.post("")
async def run_drift(payload: dict[str, Any] = Body(...)):
    """Thin wrapper over `appgraph drift GRAPH_A GRAPH_B --format json`."""
    graph_a = str(payload.get("graph_a", "")).strip()
    graph_b = str(payload.get("graph_b", "")).strip()
    if not graph_a or not graph_b:
        raise HTTPException(400, "graph_a and graph_b are required")
    llm = str(payload.get("llm") or "").strip()
    dims = str(payload.get("dims") or "").strip()
    mode = str(payload.get("mode") or "semantic").strip()
    llm_max_output_tokens = str(payload.get("llm_max_output_tokens") or "").strip()

    cmd = ["appgraph", "drift", graph_a, graph_b, "--format", "json", "--mode", mode]
    if llm:
        cmd += ["--llm", llm]
    if dims:
        cmd += ["--dims", dims]
    if llm_max_output_tokens:
        cmd += ["--llm-max-output-tokens", llm_max_output_tokens]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            cwd=_REPO_ROOT,
        )
        # --llm adds a real LLM-as-judge call — allow more headroom than compare.
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
    except FileNotFoundError as exc:
        raise HTTPException(500, f"failed to run appgraph: {exc}") from exc
    except asyncio.TimeoutError as exc:
        raise HTTPException(504, "drift timed out after 300s") from exc

    if proc.returncode != 0:
        raise HTTPException(500, f"appgraph drift failed: {stderr.decode(errors='replace')[-1500:]}")

    text = stdout.decode(errors="replace")
    try:
        report = json.loads(text[text.index("{"):])
    except (ValueError, json.JSONDecodeError):
        raise HTTPException(500, f"could not parse appgraph drift output: {text[-1500:]!r}")

    return {"report": report}
