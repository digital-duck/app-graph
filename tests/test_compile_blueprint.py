"""The compile_blueprint recipe (intent and extraction modes) with a scripted model, on fief's real extraction inputs.

fief's backend, frontend and main blueprints are structurally valid; its component.graph.yaml is not (ids referenced but
never declared), which makes a ready-made bad draft. No Docker needed.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest

from appgraph.build.compile import validate_blueprint_yaml
from appgraph.run import RecipeError, run_recipe

REPO = Path(__file__).parent.parent
FIEF = REPO / "apps/fief"
BP = {n: (FIEF / f"blueprint/{n}.graph.yaml").read_text() for n in ("backend", "frontend", "main", "component")}
# intent mode has no settings folder, so a ${{ settings.KEY }} reference cannot resolve there (as in graph-code)
BP["plain"] = re.sub(r"\$\{\{ settings\.\w+ \}\}", "8000", BP["backend"])


class CompileModel:
    """Answers by which prompt it is: shape, a component, main, a repair, a profile draft."""
    name = "scripted"

    def __init__(self, shape="SINGLE", profile="python_fastapi", first="plain", repaired="plain"):
        self.shape, self.profile, self.first, self.repaired, self.prompts = shape, profile, first, repaired, []

    def generate(self, prompt, model=None, **opts):
        self.prompts.append((prompt, opts))
        if "classifying the *shape*" in prompt:
            return f"SHAPE: {self.shape}\nPROFILE: {self.profile}"
        if "failed structural validation" in prompt:
            return BP[self.repaired]
        if "Proposed tech_profile" in prompt:
            return f"# Proposed tech_profile: {self.profile}\n\n## Style guide\nWrite Streamlit pages."
        if "system-level main.graph.yaml" in prompt:
            return BP["main"]
        if "Produce ONLY the FRONTEND component" in prompt:
            return "```yaml\n" + BP["frontend"] + "```"
        if "Produce ONLY the BACKEND component" in prompt:
            return BP["backend"]
        if "decomposing a natural-language application description" in prompt:
            return BP[self.first]
        raise AssertionError(f"unexpected prompt: {prompt[:200]}")

    def count(self, text):
        return sum(text in p for p, _ in self.prompts)


def compile_(tmp_path, model, **inputs):
    return run_recipe("compile_blueprint", {**inputs}, llm=model, log_dir=None, max_steps=2000, max_tokens=16000)


def extraction_inputs(tmp_path):
    bp = tmp_path / "out/blueprint"
    bp.mkdir(parents=True)
    shutil.copy2(FIEF / "blueprint/settings.yaml", bp / "settings.yaml")
    return bp, {"mode": "extraction", "analysis_json": (FIEF / "analysis.json").read_text(),
                "source_context": (FIEF / "source_context.txt").read_text()[:4000], "app_name": "fief",
                "output_dir": str(bp), "output_path": str(bp / "component.graph.yaml")}


class TestIntent:
    def test_valid_first_draft_is_written(self, tmp_path):
        out = tmp_path / "x/backend.graph.yaml"
        model = CompileModel()
        run = compile_(tmp_path, model, mode="intent", intent="a counter API", output_path=str(out), max_repair_attempts=2)
        assert run.outputs == {"result": str(out), "shape": "intent"}
        assert out.read_text() == BP["plain"].strip()
        assert len(model.prompts) == 1 and model.prompts[0][1]["max_tokens"] == 16000     # the old 16000-token budget
        assert "a counter API" in model.prompts[0][0]

    def test_invalid_draft_is_repaired(self, tmp_path):
        out = tmp_path / "x/c.graph.yaml"
        model = CompileModel(first="component", repaired="plain")
        run = compile_(tmp_path, model, mode="intent", intent="x", output_path=str(out), max_repair_attempts=2)
        assert run.outputs["result"] == str(out)
        assert model.count("failed structural validation") == 1
        assert "have no form.nodes entry" in [p for p, _ in model.prompts if "failed structural" in p][0]
        assert validate_blueprint_yaml(out.read_text()) == "ok"

    def test_still_invalid_ends_in_the_error_exit(self, tmp_path):
        out = tmp_path / "x/c.graph.yaml"
        model = CompileModel(first="component", repaired="component")
        run = compile_(tmp_path, model, mode="intent", intent="x", output_path=str(out), max_repair_attempts=2)
        assert run.outputs["result"].startswith("FAILED: error: these ids are referenced")
        assert model.count("failed structural validation") == 2 and not out.exists()

    def test_fail_fast_with_no_repairs(self, tmp_path):
        model = CompileModel(first="component")
        run = compile_(tmp_path, model, mode="intent", intent="x", output_path=str(tmp_path / "c.graph.yaml"), max_repair_attempts=0)
        assert run.outputs["result"].startswith("FAILED") and model.count("failed structural validation") == 0

    def test_refused_folder(self, tmp_path):
        model = CompileModel()
        run = compile_(tmp_path, model, mode="intent", intent="x", output_path="/etc/appgraph-test.graph.yaml")
        assert run.outputs["result"].startswith("refused") and model.prompts == []


class TestExtraction:
    def test_integrated_writes_three_blueprints(self, tmp_path):
        bp, inputs = extraction_inputs(tmp_path)
        model = CompileModel(shape="INTEGRATED", first="backend", repaired="backend")
        run = compile_(tmp_path, model, **inputs)
        assert run.outputs["shape"] == "INTEGRATED", run.outputs
        for name in ("backend", "frontend", "main"):
            assert validate_blueprint_yaml((bp / f"{name}.graph.yaml").read_text(), bp) == "ok", name
        assert (bp / "main.graph.yaml").read_text() == BP["main"].strip()
        assert not (bp / "TECH_PROFILE_DRAFT.md").exists()
        assert model.count("Produce ONLY the BACKEND") == 1 and model.count("Produce ONLY the FRONTEND") == 1
        assert '"routes"' in model.prompts[0][0]                      # the analysis reached classify_shape

    def test_single_with_an_unknown_profile_drafts_one(self, tmp_path):
        bp, inputs = extraction_inputs(tmp_path)
        model = CompileModel(shape="SINGLE", profile="streamlit_app")
        run = compile_(tmp_path, model, **inputs)
        assert run.outputs == {"result": str(bp / "component.graph.yaml"), "shape": "SINGLE"}
        assert (bp / "TECH_PROFILE_DRAFT.md").read_text().startswith("# Proposed tech_profile: streamlit_app")
        decompose = [p for p, _ in model.prompts if "decomposing a natural-language" in p]
        assert len(decompose) == 1 and "Target tech_profile: streamlit_app" in decompose[0]

    def test_no_fit_falls_back_to_one_blueprint(self, tmp_path):
        bp, inputs = extraction_inputs(tmp_path)
        run = compile_(tmp_path, CompileModel(shape="NO_FIT"), **inputs)
        assert run.outputs["shape"] == "NO_FIT" and (bp / "component.graph.yaml").exists()


def test_prompts_keep_spl3s_text():
    """The prompt files are graph-code's .spl function bodies, converted by scripts/spl_prompts.py (only each function's
    own parameters renamed; spl3 had no brace escape, so `${{ settings.KEY }}` is what the model saw and still sees)."""
    main = (REPO / "src/appgraph/recipes/compile_blueprint/prompts/decompose_main_graph.md").read_text()
    assert "${{ settings.BACKEND_FASTAPI_PORT }}" in main and "manage_{{in_app_name}}" in main
    assert re.findall(r"\{\{in_(\w+)\}\}", main) and set(re.findall(r"\{\{in_(\w+)\}\}", main)) == {"extraction_intent", "app_name"}
    accept = (REPO / "src/appgraph/recipes/build_app/prompts/write_acceptance_test.md").read_text()
    assert 'f"{{BASE}}{{path}}"' in accept


class Flaky(CompileModel):
    """Dies on the decompose call (a quota stop, a crash) until told not to."""
    die = True

    def generate(self, prompt, model=None, **opts):
        if self.die and "decomposing a natural-language" in prompt:
            raise RuntimeError("session limit reached")
        return super().generate(prompt, model, **opts)


def test_extract_llm_runs_the_recipe_and_resumes(tmp_path, monkeypatch):
    """`appgraph extract --llm`: the AST pass, then the recipe; a run that dies after classifying resumes without
    classifying again (the checkpoint), and a finished run leaves no checkpoint behind."""
    from click.testing import CliRunner

    import appgraph.run as run_mod
    from appgraph.cli import main

    model = Flaky(shape="SINGLE")
    real = run_mod.make_run_llm
    monkeypatch.setattr(run_mod, "make_run_llm", lambda llm, **kw: real(model, **kw))
    out = tmp_path / "todo_extract"
    args = ["extract", "--repo-path", str(REPO / "tests/fixtures/todo_backend"), "--app-name", "todo_x",
            "--output-dir", str(out), "--llm", "claude_cli:claude-sonnet-5-5"]
    first = CliRunner().invoke(main, args)
    assert first.exit_code != 0 and "resumable" in first.output, first.output
    assert list((out / ".appgraph_cache").glob("llm-*.checkpoint.json"))
    assert model.count("classifying the *shape*") == 1

    model.die = False
    second = CliRunner().invoke(main, args)
    assert second.exit_code == 0, second.output
    assert "resuming the semantic pass" in second.output
    assert model.count("classifying the *shape*") == 1                  # not paid for again
    assert validate_blueprint_yaml((out / "blueprint/component.graph.yaml").read_text(), out / "blueprint") == "ok"
    assert not list((out / ".appgraph_cache").glob("llm-*.checkpoint.json"))
