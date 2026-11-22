"""Running a shipped GraphLang recipe from library code: what `graf run` assembles, without its console or output folders.

    from appgraph.run import run_recipe
    result = run_recipe("build_component", {"component_graph": ..., ...}, llm="claude_cli:claude-sonnet-5-5", max_llm_calls=40)

Nothing is written beside the recipe (it may sit in a read-only site-packages): node outputs are not saved (`node_output`
is None) and FILES outputs are not materialized; the recipes write their real results themselves, through their steps.
The run log is GraphLang's (dd-logging, JSONL + text) under `log_dir` (default ~/app-graph/logs).

This mirrors graphlang/grafr/cli.py's cmd_run. It belongs in GraphLang (work-graph needs the same); see section 7 of
docs/DEV/graflang-refactor.md.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

RECIPES = Path(__file__).parent / "recipes"
DEFAULT_LLM = "claude_cli"
LOG_DIR = Path.home() / "app-graph" / "logs"


class RecipeError(RuntimeError):
    """The run stopped: a limit, a failed node, a refused graph. `summary` says what it did up to then."""

    def __init__(self, message: str, summary: Optional[dict] = None, log_path: Optional[Path] = None):
        super().__init__(message)
        self.summary, self.log_path = summary or {}, log_path


@dataclass
class RecipeRun:
    outputs: dict[str, Any]
    summary: dict[str, Any] = field(default_factory=dict)
    log_path: Optional[Path] = None

    @property
    def llm_calls(self) -> int:
        return int((self.summary.get("llm") or {}).get("calls") or 0)


def recipe_path(name: str | Path) -> Path:
    """A shipped recipe by name (recipes/<name>/<name>.graph.yaml), or a path to any recipe file."""
    p = Path(name)
    if p.suffix == ".yaml":
        return p
    return RECIPES / str(name) / f"{name}.graph.yaml"


def make_run_llm(llm: str | Any = DEFAULT_LLM, *, max_llm_calls: Optional[int] = None, record: Optional[Path] = None,
                 replay: Optional[Path] = None):
    """The run's LLM: an `ADAPTER[:MODEL]` string (dd-llm through GraphLang), or an object with `.name` and
    `.generate(prompt, model=None, **opts)` (tests pass a scripted one), wrapped in GraphLang's call meter."""
    from graphlang.grafr.adapters import make_llm
    from graphlang.grafr.metering import MeteredLLM, RecordingLLM, ReplayLLM
    if replay:
        inner = ReplayLLM(Path(replay))
    elif isinstance(llm, str):
        from dd_llm import parse_llm_spec
        adapter, model = parse_llm_spec(llm) if llm else (DEFAULT_LLM, None)
        inner = make_llm(adapter or DEFAULT_LLM, model)
    else:
        inner = llm
    if record:
        inner = RecordingLLM(inner, Path(record))
    return MeteredLLM(inner, max_llm_calls)


def run_recipe(name: str | Path, inputs: dict[str, Any], *, llm: str | Any = DEFAULT_LLM, max_llm_calls: Optional[int] = None,
               max_steps: int = 1000, workers: int = 1, wall_time_s: Optional[float] = None, checkpoint: Optional[Path] = None,
               resume: Optional[Path] = None, record: Optional[Path] = None, replay: Optional[Path] = None,
               log_dir: Optional[Path] = LOG_DIR, log_level: str = "info", on_node: Optional[Callable[[dict], None]] = None) -> RecipeRun:
    """Run a recipe to its end and return its outputs. Raises RecipeError when it stops early (a model-call or step
    limit, a node that failed, a policy that refuses the graph); a run that ends at no OUTPUT returns empty outputs."""
    from graphlang.grafr.capabilities import capability_errors
    from graphlang.grafr.metering import CassetteError, LimitExceeded
    from graphlang.grafr.resolver import ResourceResolver
    from graphlang.grafr.runtime import GraphLangRuntime, RunLimitExceeded, load_graph
    from graphlang.logging_config import setup_logging

    path = recipe_path(name)
    if not path.is_file():
        raise RecipeError(f"no recipe at {path}")
    log_path = None
    if log_dir is not None:
        run_llm_name = llm if isinstance(llm, str) else getattr(llm, "name", "custom")
        log_path = setup_logging(path.name.removesuffix(".graph.yaml"), adapter=str(run_llm_name).partition(":")[0],
                                 model=str(run_llm_name).partition(":")[2], log_dir=Path(log_dir), log_level=log_level, log_format="both")
    graph_data = load_graph(path)
    denied = capability_errors(graph_data, ResourceResolver(Path(graph_data.get("_source_dir", ".")), graph_data.get("resources")))
    if denied:
        raise RecipeError("the workflow policy does not allow this graph: " + "; ".join(denied), log_path=log_path)
    run_llm = make_run_llm(llm, max_llm_calls=max_llm_calls, record=record, replay=replay)
    runtime = GraphLangRuntime(graph_data, llm=run_llm, adapter=run_llm.name, max_steps=max_steps, wall_time_s=wall_time_s,
                               workers=workers, verbose=False, node_output=None, on_node=on_node)
    if checkpoint or resume:
        runtime.checkpoint_path = Path(checkpoint or resume)
    try:
        outputs = runtime.resume(Path(resume)) if resume else runtime.execute(inputs)
    except (ValueError, RuntimeError, NotImplementedError, CassetteError, LimitExceeded, RunLimitExceeded) as e:
        raise RecipeError(str(e), runtime.summary(), log_path) from e
    return RecipeRun(outputs, runtime.summary(), log_path)
