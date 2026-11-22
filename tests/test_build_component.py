"""The build_component recipe against graph-code's verified todo backend (the Phase 3 parity guard).

A scripted model answers each write_node prompt with the code graph-code generated and verified for that node (its
.spl_cache, in tests/fixtures/todo_backend). The recipe must write the same files and the suite must pass in the test
container. Needs Docker and the appgraph-verify:py3.12 image (skipped otherwise).
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from appgraph.build import blueprint, cache
from appgraph.run import run_recipe

HERE = Path(__file__).parent
FIXTURE = HERE / "fixtures/todo_backend"
BACKEND = (HERE.parent / "apps/todo/blueprint/backend.graph.yaml").resolve()
IMAGE = "appgraph-verify:py3.12"


def _image_present() -> bool:
    try:
        return subprocess.run(["docker", "image", "inspect", IMAGE], capture_output=True, timeout=30).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


needs_docker = pytest.mark.skipif(not _image_present(), reason=f"needs Docker and the {IMAGE} image")


def verified_code() -> dict[str, str]:
    return {n: cache.get(BACKEND, n, blueprint.node_spec(BACKEND, n), "python_fastapi", FIXTURE) for n in blueprint.order(BACKEND)}


class Model:
    """Answers write_node with the verified code; refine/repair with whatever `fix` gives (default: the same code)."""
    name = "scripted"

    def __init__(self, code: dict[str, str], repair=None, refined=None):
        self.code, self.repair, self.refined, self.prompts = code, repair, refined, []

    def generate(self, prompt, model=None, **opts):
        self.prompts.append(prompt)
        if m := re.search(r"Generate a self-contained implementation for: (\w+)", prompt):
            return self.code[m.group(1)]
        if "Revise the code below based on the feedback" in prompt:
            return self.refined(prompt)
        if m := re.search(r"Module to repair: (\w+)", prompt):
            return self.repair(m.group(1)) if self.repair else self.code[m.group(1)]
        raise AssertionError(f"unexpected prompt: {prompt[:200]}")


def seeded(tmp_path: Path) -> Path:
    """An output folder with the scaffold build_app seeds before build_component runs: tests/ and app/config.py."""
    out = tmp_path / "backend"
    shutil.copytree(FIXTURE / "tests", out / "tests")
    (out / "app").mkdir(parents=True)
    shutil.copy2(FIXTURE / "app/__init__.py", out / "app/__init__.py")
    shutil.copy2(FIXTURE / "app/config.py", out / "app/config.py")
    return out


def build(out: Path, tmp_path: Path, llm, **inputs):
    return run_recipe("build_component", {"component_graph": str(BACKEND), "tech_profile": "python_fastapi",
                                          "output_dir": str(out), "log_dir": str(tmp_path / "logs"), **inputs},
                      llm=llm, max_steps=3000, log_dir=tmp_path / "runlog")


@needs_docker
def test_builds_the_todo_backend_like_graph_code(tmp_path):
    out = seeded(tmp_path)
    model = Model(verified_code())
    run = build(out, tmp_path, model, use_cache=False)
    assert run.outputs["tests"].startswith("passed: 22 passed, 0 failed"), run.outputs
    for node in blueprint.order(BACKEND):
        rel = blueprint.node_rel_path(BACKEND, node)
        if (FIXTURE / rel).exists():
            assert (out / rel).read_text() == (FIXTURE / rel).read_text(), rel
    assert len(model.prompts) == 7                                   # one write per node; no refine, no repair
    summary = Path(run.outputs["summary"]).read_text()
    assert "tests: **passed**" in summary and "app/models.py" in summary
    # the second run is served from the cache it wrote: no model calls at all
    again = build(out, tmp_path, Model({}))
    assert again.llm_calls == 0 and again.outputs["tests"].startswith("passed")
    assert again.outputs["manifest"].count("(cached)") == 7


@needs_docker
def test_a_failing_suite_is_repaired(tmp_path):
    out = seeded(tmp_path)
    code = verified_code()
    good_crud = code["crud_operations"]
    code["crud_operations"] = good_crud.replace("def toggle_todo", "def toggle_todo_broken")   # passes both checks, fails tests
    model = Model(code, repair=lambda node: good_crud)
    run = build(out, tmp_path, model, use_cache=False)
    assert run.outputs["tests"].startswith("passed"), run.outputs
    assert any("Module to repair: crud_operations" in p for p in model.prompts)


@needs_docker
def test_still_failing_ends_in_the_error_exit(tmp_path):
    out = seeded(tmp_path)
    code = verified_code()
    code["crud_operations"] = code["crud_operations"].replace("def toggle_todo", "def toggle_todo_broken")
    model = Model(code, repair=lambda node: code[node])               # the "repair" changes nothing
    run = build(out, tmp_path, model, use_cache=False, max_test_attempts=2)
    assert run.outputs.get("tests", "").startswith("failed"), run.outputs
    assert sum("Module to repair" in p for p in model.prompts) == 2
    assert "Last test output" in Path(run.outputs["summary"]).read_text()


def test_no_tests_and_a_refused_folder(tmp_path):
    """No Docker needed: without tests/ the container is still asked, so this one only checks the policy refusal."""
    run = run_recipe("build_component", {"component_graph": str(BACKEND), "tech_profile": "python_fastapi",
                                         "output_dir": "/etc/appgraph-test", "log_dir": str(tmp_path)},
                     llm=Model({}), log_dir=None)
    assert "refused by policies/build.cedar" in run.outputs["tests"]
    assert run.llm_calls == 0 and not Path("/etc/appgraph-test").exists()


@needs_docker
def test_a_node_check_failure_is_refined(tmp_path):
    out = seeded(tmp_path)
    code = verified_code()
    good_models = code["orm_model"]
    code["orm_model"] = "Looking at the spec:\n```python\nclass TodoModel(Base:\n```"        # does not compile
    model = Model(code, refined=lambda prompt: good_models)
    run = build(out, tmp_path, model, use_cache=False)
    assert run.outputs["tests"].startswith("passed"), run.outputs
    refines = [p for p in model.prompts if "Revise the code below" in p]
    assert len(refines) == 1 and "syntax error" in refines[0]
    assert (out / "app/models.py").read_text() == (FIXTURE / "app/models.py").read_text()


@needs_docker
def test_no_suite_ends_in_no_tests(tmp_path):
    out = tmp_path / "backend"                                         # nothing seeded: no tests/
    run = build(out, tmp_path, Model(verified_code()), use_cache=False)
    assert run.outputs["tests"].startswith("no_tests"), run.outputs
