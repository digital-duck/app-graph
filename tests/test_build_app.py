"""The build_app recipe on graph-code's todo app (backend + frontend + integration), offline with a scripted model.

Needs Docker, the appgraph-verify:py3.12 image and (built on first use) the frontend's per-lockfile image.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

import yaml

from appgraph.build import blueprint, cache
from appgraph.run import run_recipe

from tests.test_build_component import needs_docker

HERE = Path(__file__).parent
REPO = HERE.parent
FX_BACK, FX_FRONT = HERE / "fixtures/todo_backend", HERE / "fixtures/todo_frontend"

GOOD_SCRIPT = """import json, urllib.request
r = urllib.request.urlopen("http://localhost:8000/todos")
assert r.status == 200, r.status
assert isinstance(json.loads(r.read()), list)
print("PASS")
"""


def todo_app(tmp_path: Path) -> Path:
    """tmp/apps/todo/: the blueprint, and graph-code's scaffolds where build_app looks for them (beside blueprint/)."""
    app = tmp_path / "apps/todo"
    shutil.copytree(REPO / "apps/todo/blueprint", app / "blueprint")
    shutil.copytree(FX_BACK / "tests", app / "backend/tests")
    (app / "backend/app").mkdir(parents=True)
    shutil.copy2(FX_BACK / "app/__init__.py", app / "backend/app/__init__.py")
    shutil.copytree(FX_FRONT, app / "frontend", ignore=shutil.ignore_patterns("src", "README.md"))
    return app / "blueprint/main.graph.yaml"


class AppModel:
    """write_node: graph-code's code for the node (backend from its cache, frontend from its files); refine: the code back;
    an acceptance script per application; a README."""
    name = "scripted"

    def __init__(self, script=GOOD_SCRIPT, broken_backend: bool = False):
        back = REPO / "apps/todo/blueprint/backend.graph.yaml"
        front = REPO / "apps/todo/blueprint/frontend.graph.yaml"
        self.back = {n: cache.get(back, n, blueprint.node_spec(back, n), "python_fastapi", FX_BACK) for n in blueprint.order(back)}
        self.front = {n: (FX_FRONT / blueprint.node_rel_path(front, n)).read_text() for n in blueprint.order(front)}
        if broken_backend:
            self.back["crud_operations"] = self.back["crud_operations"].replace("def toggle_todo", "def toggle_todo_broken")
        self.script, self.prompts = script, []

    def generate(self, prompt, model=None, **opts):
        self.prompts.append(prompt)
        if m := re.search(r"Generate a self-contained implementation for: (\w+)", prompt):
            return (self.front if "TECH PROFILE: Vue" in prompt else self.back)[m.group(1)]
        if "Revise the code below based on the feedback" in prompt or "Module to repair" in prompt:
            if "Module to repair: " in prompt:
                return self.back[re.search(r"Module to repair: (\w+)", prompt).group(1)]
            return prompt.split("CODE:\n", 1)[1].split("\n\nFEEDBACK:", 1)[0]
        if "HTTP-level acceptance test" in prompt:
            return "```python\n" + self.script + "```"
        if "product-level README" in prompt:
            return "# Todo\n\n## Status\n\n" + prompt.split("Acceptance-test results from the just-completed integration run:\n", 1)[1][:400]
        raise AssertionError(f"unexpected prompt: {prompt[:200]}")


def build_app(system: Path, tmp_path: Path, model, **inputs):
    return run_recipe("build_app", {"system_yaml": str(system), "log_dir": str(tmp_path / "logs"), "use_cache": False, **inputs},
                      llm=model, max_steps=6000, log_dir=None)


def test_catalogues_agree():
    """GraphLang reads the error catalogue beside the top graph only, so build_app repeats build_component's codes."""
    rec = REPO / "src/appgraph/recipes"
    comp = {e["code"]: e for e in yaml.safe_load((rec / "build_component/graflang.errors.yaml").read_text())["errors"]}
    app = {e["code"]: e for e in yaml.safe_load((rec / "build_app/graflang.errors.yaml").read_text())["errors"]}
    assert all(app[c] == e for c, e in comp.items())


@needs_docker
def test_builds_and_integrates_the_todo_app(tmp_path):
    system = todo_app(tmp_path)
    model = AppModel()
    run = build_app(system, tmp_path, model)
    assert run.outputs["status"] == "passed", run.outputs
    app = system.parent.parent
    assert (app / "backend/app/models.py").read_text() == (FX_BACK / "app/models.py").read_text()
    assert (app / "frontend/src/components/TodoList.vue").read_text() == (FX_FRONT / "src/components/TodoList.vue").read_text()
    assert (app / "backend/app/config.py").exists() and (app / "frontend/src/config.ts").exists()       # settings config
    apps = blueprint.applications(system)
    assert run.outputs["integration"].count("PASS") == len(apps)
    assert (app / "README.md").read_text().startswith("# Todo")
    summary = Path(run.outputs["summary"]).read_text()
    assert "status: **passed**" in summary and "## backend" in summary and "## frontend" in summary
    assert len(list((tmp_path / "logs").glob("acceptance-*/test_acceptance_*.py"))) == len(apps)


@needs_docker
def test_a_failed_component_halts_the_app(tmp_path):
    system = todo_app(tmp_path)
    model = AppModel(broken_backend=True)              # the "repair" returns the same broken code
    run = build_app(system, tmp_path, model, max_test_attempts=1)
    assert run.outputs["status"].startswith("component_failed: backend"), run.outputs
    assert not any("TECH PROFILE: Vue" in p for p in model.prompts)                  # the frontend was not built
    assert not any("acceptance test" in p for p in model.prompts)


@needs_docker
def test_a_failing_acceptance_test_ends_in_integration_failed(tmp_path):
    system = todo_app(tmp_path)
    run = build_app(system, tmp_path, AppModel(script="assert False, 'contract broken'\n"))
    assert run.outputs["status"] == "integration_failed", run.outputs
    assert "FAIL" in run.outputs["integration"] and "contract broken" in run.outputs["integration"]
    assert (system.parent.parent / "README.md").exists()                              # written anyway, with the real status
