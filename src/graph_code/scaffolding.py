"""Shared project-scaffolding logic for tech profiles with an official (or
hand-authored) "create new project" story — `npm create vue@latest` for
vue_typescript, a minimal hand-rolled async-FastAPI skeleton for
python_fastapi (which has no equivalent official CLI; FastAPI itself ships
no "create-fastapi-app").

Used from two call sites that need the exact same behavior:
- `spl/tools.py`'s `seed_component_scaffold` tool, automatically, the first
  time a brand-new app's component has no scaffold yet at its default
  output location (see that function's docstring).
- `grafcode tools scaffold-vue` / `scaffold-fastapi`, for a human to run
  by hand against any target directory outside the build pipeline.

Both produce just enough project shell (package.json + vitest wiring, or
tests/ + pytest wiring) for build_component.spl's Stage 3 test gate to find
*a* project to run `npm test` / `pytest` in — not real test files matching
an app's actual behavior. Those still need authoring separately (Recipe-79:
tests are the correctness certificate, so the thing being certified can't
also write them).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


def bootstrap_vue_scaffold(target_dir: Path) -> str:
    """Bootstrap a brand-new vue_typescript project shell via the official
    `npm create vue@latest` scaffolding tool.

    Produces package.json, vite.config.ts, tsconfig*.json, index.html, and a
    vitest-wired (but test-file-empty) tests setup.

    Two non-obvious things learned getting this to run non-interactively
    (create-vue uses `@clack/prompts`, a raw-tty TUI that ignores piped
    stdin):
    - The target directory must be passed *after* `--`, or `npm create`
      swallows it as its own argument instead of forwarding it to create-vue,
      which then falls back to its interactive "Package name?" prompt.
    - create-vue derives the default package name from the raw target-dir
      string verbatim (not its basename), and prompts a second time if that
      string isn't a valid bare package name — which any path containing `/`
      or an app name with uppercase/digits (e.g. "todo2A") always is. Fixed
      by `cd`-ing into the parent dir first and passing a bare, already-valid
      kebab-case placeholder name, then merging the result into place.

    Merges rather than replaces: `target_dir` may already hold real content
    (e.g. src/config.ts from an earlier step, or partial node output from an
    interrupted build) that must survive — only files create-vue produces
    that don't already exist at the destination are copied over.
    """
    parent = target_dir.parent
    parent.mkdir(parents=True, exist_ok=True)
    scratch_name = "vue-scaffold-bootstrap"
    scratch_dir = parent / scratch_name
    if scratch_dir.exists():
        shutil.rmtree(scratch_dir)

    cmd = [
        "npm", "create", "vue@latest", "--",
        scratch_name, "--typescript", "--router", "--pinia", "--vitest", "--force",
    ]
    proc = subprocess.run(cmd, cwd=parent, capture_output=True, text=True, timeout=180)
    if proc.returncode != 0 or not (scratch_dir / "package.json").exists():
        if scratch_dir.exists():
            shutil.rmtree(scratch_dir)
        return f"failed: npm create vue@latest exited {proc.returncode} — {(proc.stdout + proc.stderr)[-1000:]}"

    # create-vue names its vitest script "test:unit" (bare `vitest`, watch
    # mode by default — would hang forever if run_component_tests invoked it
    # directly) rather than "test" (run_component_tests' `npm test`
    # convention, matching every hand-authored vue_typescript package.json
    # in this repo, e.g. todo1's). Rewrite before merging so the scaffold
    # matches what the rest of the pipeline expects, non-interactively.
    pkg_path = scratch_dir / "package.json"
    pkg = json.loads(pkg_path.read_text())
    pkg.setdefault("scripts", {})["test"] = "vitest run"
    pkg_path.write_text(json.dumps(pkg, indent=2) + "\n")

    merged = []
    for src in scratch_dir.rglob("*"):
        if src.is_dir():
            continue
        rel = src.relative_to(scratch_dir)
        dst = target_dir / rel
        if dst.exists():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        merged.append(str(rel))
    shutil.rmtree(scratch_dir)

    install = subprocess.run(["npm", "install"], cwd=target_dir, capture_output=True, text=True, timeout=300)
    install_status = "npm install ok" if install.returncode == 0 else (
        f"npm install FAILED (exit {install.returncode}) — {(install.stdout + install.stderr)[-500:]}"
    )
    return (
        f"bootstrapped {len(merged)} scaffold file(s) via npm create vue@latest: "
        f"{', '.join(merged)}; {install_status}"
    )


_FASTAPI_FILES: dict[str, str] = {
    "app/__init__.py": "",
    "app/config.py": '''from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "sqlite+aiosqlite:///./app.db"


settings = Settings()
''',
    "app/database.py": '''from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import settings

engine = create_async_engine(settings.DATABASE_URL)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


class BaseModel(DeclarativeBase):
    pass


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session
''',
    "app/main_app.py": '''from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .database import BaseModel, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(BaseModel.metadata.create_all)
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
''',
    "tests/__init__.py": "",
    "tests/conftest.py": '''from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

import pytest
from httpx import ASGITransport, AsyncClient

from app.database import BaseModel, engine
from app.main_app import app


@pytest.fixture(autouse=True)
async def reset_db():
    async with engine.begin() as conn:
        await conn.run_sync(BaseModel.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(BaseModel.metadata.drop_all)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
''',
    "tests/test_health.py": '''from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
''',
    "pytest.ini": "[pytest]\nasyncio_mode = auto\n",
    "requirements.txt": (
        "fastapi\n"
        "uvicorn\n"
        "sqlalchemy[asyncio]\n"
        "aiosqlite\n"
        "pydantic-settings\n"
        "httpx\n"
        "pytest\n"
        "pytest-asyncio\n"
    ),
    ".env": "DATABASE_URL=sqlite+aiosqlite:///./app.db\n",
}


def bootstrap_fastapi_scaffold(target_dir: Path) -> str:
    """Bootstrap a brand-new python_fastapi project shell.

    FastAPI ships no official "create-fastapi-app" CLI, so unlike
    bootstrap_vue_scaffold this is a hand-rolled minimal skeleton rather than
    a wrapped official tool: an async-SQLAlchemy `app/database.py`, a
    pydantic-settings `app/config.py` (the `Settings`-singleton convention
    documented in `spl/tech_profiles.py`'s python_fastapi profile), a
    `app/main_app.py` with a lifespan-managed table-create and one `/health`
    route, and a real passing `tests/test_health.py` (pytest-asyncio) so
    Stage 3's test gate has something genuine to run. Per-file skip-if-exists
    — safe to run against a directory that already has real generated
    content.
    """
    written = []
    for rel, content in _FASTAPI_FILES.items():
        dst = target_dir / rel
        if dst.exists():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(content)
        written.append(rel)
    return (
        f"bootstrapped {len(written)} scaffold file(s): {', '.join(written)}"
        if written else "no-op: all scaffold files already exist"
    )
