from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, HTTPException

from api.routers import graphs

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/apps-root")
def get_apps_root():
    return {"apps_root": str(graphs.APPS_ROOT)}


@router.put("/apps-root")
def set_apps_root(payload: dict[str, Any] = Body(...)):
    raw = str(payload.get("apps_root", "")).strip()
    if not raw:
        raise HTTPException(400, "apps_root is required")
    new_root = Path(raw).expanduser().resolve()
    if not new_root.is_dir():
        raise HTTPException(404, f"not a directory: {new_root}")
    graphs.set_apps_root(new_root)
    return {"apps_root": str(graphs.APPS_ROOT)}
