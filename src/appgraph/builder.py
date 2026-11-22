"""Building from a blueprint: the Python entry points behind `appgraph build` (and the IDE's Build page).

build_component runs the build_component recipe (appgraph/recipes/build_component). The outcome is in `status`:
passed, no_tests, failed (the error exits of the recipe) or refused (the build policy).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from .build import blueprint
from .run import LOG_DIR, run_recipe


@dataclass
class BuildResult:
    status: str                       # passed | no_tests | failed | refused
    tests: str
    manifest: str
    summary_path: str
    llm_calls: int
    log_path: Optional[Path] = None
    outputs: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status == "passed"


def default_output_dir(component_graph: str | Path) -> Path:
    """apps/<app>/blueprint/backend.graph.yaml -> apps/<app>/backend."""
    return Path(blueprint.component_output_dir(Path(component_graph).resolve()))


def call_cap(n_nodes: int, max_test_attempts: int) -> int:
    """Spec + write + two refines per node at most, one repair per test attempt, and a little slack."""
    return 4 * n_nodes + max_test_attempts + 2


def build_component(component_graph: str | Path, *, tech_profile: Optional[str] = None, output_dir: str | Path | None = None,
                    llm: str | Any = "claude_cli", max_llm_calls: Optional[int] = None, use_cache: bool = True,
                    max_test_attempts: int = 3, log_dir: Path = LOG_DIR, llm_timeout: Optional[int] = None,
                    on_node: Optional[Callable[[dict], None]] = None) -> BuildResult:
    graph = Path(component_graph).resolve()
    profile = tech_profile or blueprint.load_yaml(graph).get("tech_profile") or "python_fastapi"
    out = Path(output_dir).resolve() if output_dir else default_output_dir(graph)
    n = len(blueprint.order(graph))                       # validates the blueprint; ToolFailed before any model call
    run = run_recipe("build_component", {"component_graph": str(graph), "tech_profile": profile, "output_dir": str(out),
                                         "use_cache": use_cache, "max_test_attempts": max_test_attempts,
                                         "log_dir": str(Path(log_dir).expanduser().resolve())},
                     llm=llm, max_llm_calls=max_llm_calls if max_llm_calls is not None else call_cap(n, max_test_attempts),
                     max_steps=300 + 30 * n, log_dir=log_dir, llm_timeout=llm_timeout, on_node=on_node)
    tests = str(run.outputs.get("tests", ""))
    status = tests.split(":", 1)[0] if tests.split(":", 1)[0] in ("passed", "no_tests", "failed") else ("refused" if tests.startswith("refused") else "failed")
    return BuildResult(status, tests, str(run.outputs.get("manifest", "")), str(run.outputs.get("summary", "")),
                       run.llm_calls, run.log_path, run.outputs)
