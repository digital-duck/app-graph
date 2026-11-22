"""appgraph.run (a recipe from library code) and appgraph.judge (drift --mode semantic over dd-llm)."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from appgraph import judge
from appgraph.cli import main
from appgraph.run import RecipeError, recipe_path, run_recipe

HERE = Path(__file__).parent
ECHO = HERE / "recipes/echo/echo.graph.yaml"
TODO = HERE.parent / "apps/todo/blueprint"


class Scripted:
    """A model that answers from a function of the prompt, and records what it was asked."""
    name = "scripted"

    def __init__(self, answer):
        self.answer, self.prompts = answer, []

    def generate(self, prompt, model=None, **opts):
        self.prompts.append(prompt)
        return self.answer(prompt) if callable(self.answer) else self.answer


class TestRunRecipe:
    def test_runs_a_recipe_with_a_scripted_model(self, tmp_path):
        llm = Scripted("hello")
        run = run_recipe(ECHO, {"topic": "ducks", "folder": str(HERE / "fixtures/todo_backend")}, llm=llm, log_dir=tmp_path)
        assert run.outputs["answer"] == "hello"
        assert "app/main.py" in run.outputs["files"]["files"]       # the SOLVE step ran appgraph.build.tool
        assert llm.prompts == ["Say something about ducks.\n"]
        assert run.llm_calls == 1
        assert not (ECHO.parent / ".graf").exists()     # nothing written beside the recipe

    def test_call_cap_stops_the_run(self, tmp_path):
        with pytest.raises(RecipeError, match="max_llm_calls"):
            run_recipe(ECHO, {"topic": "x", "folder": "/nonexistent"}, llm=Scripted("hi"), max_llm_calls=0, log_dir=tmp_path)

    def test_unknown_recipe(self):
        with pytest.raises(RecipeError, match="no recipe"):
            run_recipe("no_such_recipe", {}, log_dir=None)

    def test_recipe_path(self):
        assert recipe_path("build_component").name == "build_component.graph.yaml"
        assert recipe_path(ECHO) == ECHO


class FakeAdapter:
    def __init__(self, reply, ok=True):
        self.reply, self.ok, self.calls = reply, ok, []

    def call(self, prompt, *, model="", **kw):
        self.calls.append((prompt, model, kw))
        return SimpleNamespace(success=self.ok, content=self.reply, error_history=[] if self.ok else [{"error": "quota"}])


class TestJudge:
    def test_prompt_is_filled(self):
        p = judge.judge_prompt("interface", "A-text", "B-text")
        assert '"interface" aspect' in p and "A-text" in p and "B-text" in p and "{{" not in p

    def test_parse(self):
        assert judge.parse_score(" 0.15\n") == 0.15
        with pytest.raises(judge.JudgeError):
            judge.parse_score("no idea")

    def test_make_judge_calls_the_adapter(self):
        fake = FakeAdapter("0.40")
        made = {}
        j = judge.make_judge("ollama:gemma4", timeout=30, max_output_tokens=4096,
                             adapter_factory=lambda name, **kw: made.update(name=name, **kw) or fake)
        assert j("intent", "a", "b") == 0.40
        assert made == {"name": "ollama", "timeout": 30}
        assert fake.calls[0][1] == "gemma4" and fake.calls[0][2] == {"max_tokens": 4096}

    def test_failed_call(self):
        j = judge.make_judge("claude_cli", adapter_factory=lambda name, **kw: FakeAdapter("", ok=False))
        with pytest.raises(judge.JudgeError, match="quota"):
            j("intent", "a", "b")

    def test_drift_command_semantic(self, monkeypatch):
        import dd_llm
        monkeypatch.setattr(dd_llm, "get_adapter", lambda name, **kw: FakeAdapter("0.25"))
        g = str(TODO / "backend.graph.yaml")
        result = CliRunner().invoke(main, ["drift", g, g, "--dims", "intent,interface", "--format", "json"])
        assert result.exit_code == 0, result.output
        report = json.loads(result.output)
        assert report["intent"] == 0.25 and report["interface"] == 0.25
