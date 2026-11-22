#!/usr/bin/env python3
"""Batch build apps from their blueprint .graph.yaml files.

Discovers every app under an apps root that has a `blueprint/*.graph.yaml`
file and runs `appgraph build` on it, streaming output and collecting
pass/fail results.  Mirrors the role of `batch_generate.py` in the
conceptbook repos but targets code-generation apps rather than prose sections.

Prerequisites:
    appgraph on PATH  (pip install -e . from repo root)

Usage examples:
    # Dry-run: show what would be built
    python scripts/batch_build.py --dry-run

    # Build specific apps
    python scripts/batch_build.py --app todo --app expense

    # Force rebuild even when output already exists
    python scripts/batch_build.py --no-skip-existing

    # Override LLM
    python scripts/batch_build.py --llm claude_cli:claude-sonnet-5

    # Custom apps root
    python scripts/batch_build.py --apps-dir ~/my-apps

    # Abort immediately on first failure
    python scripts/batch_build.py --stop-on-error

    # Per-call LLM timeout (seconds)
    python scripts/batch_build.py --llm-timeout 300
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import click
import yaml

REPO_ROOT = Path(__file__).parent.parent
DEFAULT_APPS_DIR = REPO_ROOT / "apps"

# Substrings that indicate a session/rate limit rather than a code error.
# Mirrors batch_generate.py in the cb-* conceptbook repos.
_SESSION_LIMIT_MARKERS = (
    "session limit", "rate limit", "quota", "usage limit", "modeloverloaded",
)

_SKIP_DIR_NAMES = frozenset({"blueprint", "conceptbook", "node_modules", "__pycache__", ".git"})
_CODE_SUFFIXES = frozenset({".py", ".ts", ".go", ".js", ".rs", ".java", ".cpp", ".c"})


class SessionLimitHit(Exception):
    def __init__(self, line: str) -> None:
        self.line = line
        super().__init__(line)


# ---------------------------------------------------------------------------
# Discovery + output-existence helpers
# ---------------------------------------------------------------------------

def _discover_apps(apps_root: Path) -> list[tuple[str, Path]]:
    """Return (app_name, blueprint_path) for every buildable app under apps_root.

    Preference order for the blueprint file:
      1. main.graph.yaml   (system app — multi-component)
      2. component.graph.yaml  (explicit single-component convention)
      3. first *.graph.yaml alphabetically (single-component fallback)
    """
    results: list[tuple[str, Path]] = []
    for entry in sorted(apps_root.iterdir()):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        bp_dir = entry / "blueprint"
        if not bp_dir.is_dir():
            continue
        for candidate in (
            bp_dir / "main.graph.yaml",
            bp_dir / "component.graph.yaml",
        ):
            if candidate.exists():
                results.append((entry.name, candidate))
                break
        else:
            graphs = sorted(bp_dir.glob("*.graph.yaml"))
            if graphs:
                results.append((entry.name, graphs[0]))
    return results


def _has_output(app_root: Path) -> bool:
    """Return True if the app already has generated files outside blueprint/."""
    for child in app_root.iterdir():
        if child.name in _SKIP_DIR_NAMES or child.name.startswith("."):
            continue
        if child.name in ("README.md", "README-new-apps.md"):
            continue
        if child.is_dir():
            # Any non-skip directory is evidence of a prior build (e.g. backend/, frontend/)
            return True
        if child.is_file() and child.suffix in _CODE_SUFFIXES:
            return True
    return False


def _app_type(blueprint_path: Path) -> str:
    """Return 'system' if blueprint has an imports: block, otherwise 'component'."""
    try:
        raw = yaml.safe_load(blueprint_path.read_text()) or {}
        return "system" if raw.get("imports") else "component"
    except Exception:
        return "?"


# ---------------------------------------------------------------------------
# Build runner
# ---------------------------------------------------------------------------

def _run_build(blueprint_path: Path, llm: str, llm_timeout: int | None) -> bool:
    """Shell out to `appgraph build <path> --llm <llm>`, streaming output.

    Returns True on exit code 0. Raises SessionLimitHit as soon as any output
    line indicates an LLM session/rate limit so the batch can abort cleanly
    rather than letting every remaining job fail the same way.
    """
    cmd = ["appgraph", "build", str(blueprint_path), "--llm", llm]
    if llm_timeout is not None:
        cmd += ["--llm-timeout", str(llm_timeout)]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert proc.stdout is not None
    try:
        for line in proc.stdout:
            low = line.lower()
            if any(marker in low for marker in _SESSION_LIMIT_MARKERS):
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
                raise SessionLimitHit(line.strip())
            click.echo(line, nl=False)
    finally:
        if proc.stdout:
            proc.stdout.close()

    proc.wait()
    return proc.returncode == 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@click.command()
@click.option(
    "--app", "apps", multiple=True,
    help="App name to build (repeatable). Default: all discovered apps.",
)
@click.option(
    "--apps-dir", default=None, type=click.Path(path_type=Path),
    help=f"Root directory containing app subdirectories. Default: {DEFAULT_APPS_DIR}",
)
@click.option(
    "--llm", default="claude_cli", show_default=True,
    envvar="GC_LLM",
    help="Adapter[:model] string forwarded to `appgraph build --llm`.",
)
@click.option(
    "--llm-timeout", type=int, default=None, metavar="SECONDS",
    help="Per-LLM-call timeout forwarded to `appgraph build --llm-timeout`.",
)
@click.option(
    "--skip-existing/--no-skip-existing", default=True,
    help="Skip apps that already have generated output outside blueprint/ (default: on).",
)
@click.option(
    "--dry-run", is_flag=True,
    help="Print the planned build list without executing any builds.",
)
@click.option(
    "--stop-on-error", is_flag=True,
    help="Abort the batch immediately if any single build fails.",
)
def main(
    apps: tuple[str, ...],
    apps_dir: Path | None,
    llm: str,
    llm_timeout: int | None,
    skip_existing: bool,
    dry_run: bool,
    stop_on_error: bool,
) -> None:
    """Batch build apps from blueprint .graph.yaml files using appgraph build."""
    root = apps_dir or DEFAULT_APPS_DIR
    if not root.is_dir():
        click.echo(f"[error] apps dir not found: {root}", err=True)
        sys.exit(1)

    all_apps = _discover_apps(root)
    if not all_apps:
        click.echo(f"No apps with blueprint/*.graph.yaml found under {root}")
        sys.exit(1)

    # Filter by --app if given
    if apps:
        requested = set(apps)
        known = {name for name, _ in all_apps}
        missing = requested - known
        if missing:
            click.echo(f"[warn] Unknown app(s): {', '.join(sorted(missing))}", err=True)
        all_apps = [(name, bp) for name, bp in all_apps if name in requested]

    # Build job list, applying --skip-existing
    jobs: list[tuple[str, Path, str]] = []  # (app_name, bp_path, app_type)
    for app_name, bp_path in all_apps:
        app_root = bp_path.parent.parent  # blueprint/ → app root
        if skip_existing and _has_output(app_root):
            click.echo(f"[skip] {app_name}: output exists (--no-skip-existing to rebuild)")
            continue
        jobs.append((app_name, bp_path, _app_type(bp_path)))

    if not jobs:
        click.echo("No jobs to run.")
        return

    click.echo(f"\n{'DRY RUN — ' if dry_run else ''}Planned {len(jobs)} build job(s)  [llm={llm}]:\n")
    col = max(len(n) for n, _, _ in jobs) + 2
    for app_name, bp_path, kind in jobs:
        rel = bp_path.relative_to(root)
        click.echo(f"  {app_name:{col}s}  {kind:10s}  {rel}")
    click.echo()

    if dry_run:
        return

    succeeded, failed = 0, 0
    for idx, (app_name, bp_path, kind) in enumerate(jobs):
        sep = "=" * 70
        click.echo(sep)
        click.echo(f"BUILDING  app={app_name}  type={kind}  llm={llm}")
        click.echo(sep)

        try:
            ok = _run_build(bp_path, llm, llm_timeout)
        except SessionLimitHit as exc:
            click.echo(f"[FAIL] {app_name}: session/rate limit — {exc.line}", err=True)
            remaining = len(jobs) - idx - 1
            click.echo(
                f"\nAborting batch: LLM session/rate limit hit. "
                f"{succeeded} succeeded, {failed + 1} failed, {remaining} not attempted.",
                err=True,
            )
            sys.exit(1)

        if ok:
            click.echo(f"[ok] {app_name}")
            succeeded += 1
        else:
            click.echo(f"[FAIL] {app_name}", err=True)
            failed += 1
            if stop_on_error:
                click.echo("Aborting batch (--stop-on-error).", err=True)
                sys.exit(1)

    click.echo(f"\nBatch complete: {succeeded} succeeded, {failed} failed.")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
