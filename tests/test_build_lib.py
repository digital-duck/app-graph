"""appgraph.build: the build helpers moved out of spl/tools.py (they had no tests in graph-code)."""
from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

import pytest

from appgraph.build import blueprint, cache, compile as bcompile, files, text, verify

REPO = Path(__file__).parent.parent
TODO = REPO / "apps/todo/blueprint"
BACKEND = TODO / "backend.graph.yaml"
FIXTURE = Path(__file__).parent / "fixtures/todo_backend"
RUN_TESTS = REPO / "src/appgraph/recipes/build_component/tools/run_tests.py"


@pytest.fixture
def app(tmp_path):
    """A copy of the todo blueprint under tmp/apps/todo/ (NODE_FILES is keyed by the apps/<name>/ segment)."""
    dst = tmp_path / "apps/todo/blueprint"
    shutil.copytree(TODO, dst)
    return dst / "backend.graph.yaml"


# ── text ────────────────────────────────────────────────────────────────────────────────────────────────────────────

class TestText:
    def test_code_fence_and_narration_removed(self):
        reply = "Looking at the spec, here it is:\n```python\nx = 1\n```\n\n**other.py**\n```python\ny = 2\n```"
        assert text.strip_fences(reply, is_doc=False) == "x = 1"

    def test_doc_keeps_a_fence_inside_real_content(self):
        doc = "# Title\n\nIntro.\n\n```\ndiagram\n```\n\nMore."
        assert text.strip_fences(doc) == doc

    def test_doc_short_preamble_dropped(self):
        assert text.strip_fences("Sure:\n```\npytest>=7.0.0") == "pytest>=7.0.0"

    def test_chat_tail_and_tool_xml(self):
        assert text.strip_chat_artifacts("# R\nbody\nHuman: continue to generate: X") == "# R\nbody"
        xml = 'ok <function_calls><invoke name="Write"><parameter name="content"># Real</parameter></invoke>'
        assert text.strip_chat_artifacts(xml) == "# Real"

    def test_looks_like_code(self):
        assert text.looks_like_code("x = 1\n", "python_fastapi")
        assert not text.looks_like_code("Let me fix that.", "python_fastapi")
        assert not text.looks_like_code("def broken(:\n", "python_fastapi")
        assert text.looks_like_code("export const a = 1", "vue_typescript")


# ── blueprint ───────────────────────────────────────────────────────────────────────────────────────────────────────

class TestBlueprint:
    def test_order_and_capstone(self):
        assert blueprint.order(BACKEND) == ["db_connection", "requirements", "data_schema", "orm_model",
                                            "crud_operations", "api_routes", "readme"]
        assert blueprint.capstone(BACKEND) == "api_routes"

    def test_app_name(self):
        assert blueprint.app_name(BACKEND) == "todo"
        with pytest.raises(RuntimeError):
            blueprint.app_name("/tmp/x.graph.yaml")

    def test_rel_paths(self):
        assert blueprint.node_rel_path(BACKEND, "orm_model") == "app/models.py"
        assert blueprint.node_rel_path(BACKEND, "readme") == "README.md"

    def test_spec_and_deps(self):
        assert blueprint.has_spec(BACKEND, "api_routes")
        assert "interface" in blueprint.node_spec(BACKEND, "api_routes")
        assert blueprint.node_spec(BACKEND, "nope") == "(no spec declared for nope)"

    def test_node_context_reads_written_deps(self, tmp_path):
        assert blueprint.node_context(BACKEND, "orm_model", tmp_path) == "(no dependency files generated yet)"
        ctx = blueprint.node_context(BACKEND, "crud_operations", FIXTURE)
        assert "# app/models.py" in ctx and "# app/schemas.py" in ctx

    def test_identify_broken_node(self):
        assert blueprint.identify_broken_node(BACKEND, "FAILED tests/test_crud.py::test_x") == "crud_operations"
        trace = 'File "app/main.py", line 3\nFile "app/models.py", line 9\nImportError: TodoSchema'
        assert blueprint.identify_broken_node(BACKEND, trace) == "orm_model"
        assert blueprint.identify_broken_node(BACKEND, "something else") == "api_routes"

    def test_components_of_a_system(self, tmp_path):
        comps = blueprint.components(TODO / "main.graph.yaml")
        assert [c["id"] for c in comps] == ["backend", "frontend"]
        assert comps[0]["tech_profile"] == "python_fastapi" and comps[0]["output_dir"].endswith("apps/todo/backend")
        assert blueprint.components(TODO / "main.graph.yaml", tmp_path)[1]["output_dir"] == str(tmp_path / "frontend")
        assert blueprint.check_port_consistency(TODO / "main.graph.yaml") == []

    def test_applications(self):
        apps = blueprint.applications(TODO / "main.graph.yaml")
        assert apps and all(isinstance(a, str) for a in apps)
        assert "Live backend base URL" in blueprint.app_backend_endpoints(TODO / "main.graph.yaml", apps[0])

    def test_system_readme_path(self, tmp_path):
        assert blueprint.system_readme_path(TODO / "main.graph.yaml") == REPO / "apps/todo/README.md"
        assert blueprint.system_readme_path(TODO / "main.graph.yaml", tmp_path) == tmp_path / "README.md"


# ── cache: compatible with graph-code's .spl_cache ──────────────────────────────────────────────────────────────────

class TestCache:
    def test_reads_graph_code_cache_for_every_node(self):
        for node in blueprint.order(BACKEND):
            code = cache.get(BACKEND, node, blueprint.node_spec(BACKEND, node), "python_fastapi", FIXTURE)
            assert code, node

    def test_cached_code_is_what_was_written(self):
        for node in ["db_connection", "data_schema", "orm_model", "crud_operations", "api_routes"]:
            code = cache.get(BACKEND, node, blueprint.node_spec(BACKEND, node), "python_fastapi", FIXTURE)
            assert text.clean(code, is_doc=False) == (FIXTURE / blueprint.node_rel_path(BACKEND, node)).read_text()

    def test_put_get_and_misses(self, tmp_path):
        k = cache.put("orm_model", "code", "spec", "python_fastapi", tmp_path)
        assert (tmp_path / ".spl_cache" / f"{k}.json").exists()
        assert cache.get(BACKEND, "orm_model", "spec", "python_fastapi", tmp_path) == "code"
        assert cache.get(BACKEND, "orm_model", "other spec", "python_fastapi", tmp_path) is None
        assert cache.get(BACKEND, "orm_model", "spec", "python_fastapi", tmp_path, use_cache=False) is None


# ── files ───────────────────────────────────────────────────────────────────────────────────────────────────────────

class TestFiles:
    def test_write_node_file(self, app, tmp_path):
        out = tmp_path / "out"
        r = files.write_node_file(app, "orm_model", "```python\nx = 1\n```", out, "python_fastapi")
        assert r["written"] and (out / "app/models.py").read_text() == "x = 1"

    def test_prose_is_not_written(self, app, tmp_path):
        r = files.write_node_file(app, "orm_model", "Let me explain the model.", tmp_path, "python_fastapi")
        assert not r["written"] and not (tmp_path / "app/models.py").exists()

    def test_doc_node_written_as_markdown(self, app, tmp_path):
        r = files.write_node_file(app, "readme", "# Todo\n\nText.", tmp_path, "python_fastapi")
        assert r["written"] and (tmp_path / "README.md").read_text() == "# Todo\n\nText."

    def test_settings_config(self, tmp_path):
        p = files.write_settings_config(BACKEND, tmp_path, "python_fastapi")
        assert p.endswith("app/config.py") and "BACKEND_FASTAPI_PORT" in Path(p).read_text()
        assert files.write_settings_config(BACKEND, tmp_path, "other").startswith("skipped")


# ── verify ──────────────────────────────────────────────────────────────────────────────────────────────────────────

class TestVerify:
    def test_verify_node(self):
        assert verify.verify_node(BACKEND, "orm_model", "x = 1", "python_fastapi") == "ok"
        assert verify.verify_node(BACKEND, "orm_model", "", "python_fastapi").startswith("fail")
        assert "syntax" in verify.verify_node(BACKEND, "orm_model", "def (:", "python_fastapi")
        assert verify.verify_node(BACKEND, "readme", "# not python (:", "python_fastapi") == "ok"

    def test_verify_edges(self):
        good = (FIXTURE / "app/crud.py").read_text()
        assert verify.verify_edges(BACKEND, "crud_operations", good) == "ok"
        assert verify.verify_edges(BACKEND, "crud_operations", "x = 1").startswith("fail: missing references")

    @pytest.mark.parametrize("out,rc,status", [
        ("22 passed in 1.0s", 0, "passed"),
        ("1 failed, 21 passed", 1, "failed"),
        ("no tests ran", 5, "no_tests"),
        ("ImportError while loading conftest", 4, "failed"),
    ])
    def test_parse_and_status(self, out, rc, status):
        assert verify.test_status(verify.parse_test_output(out, rc)) == status

    def test_container_runner_counts_the_same_way(self):
        spec = importlib.util.spec_from_file_location("run_tests", RUN_TESTS)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        for out, rc in [("22 passed", 0), ("1 failed, 2 passed", 1), ("", 5), ("ModuleNotFoundError: x", 4)]:
            assert mod.parse_test_output(out, rc) == verify.parse_test_output(out, rc)

    def test_missing_suite_is_no_tests(self, tmp_path):
        assert verify.test_status(verify.run_component_tests(tmp_path, "python_fastapi")) == "no_tests"
        assert verify.test_status(verify.run_component_tests(tmp_path, "vue_typescript")) == "no_tests"


# ── compile ─────────────────────────────────────────────────────────────────────────────────────────────────────────

class TestCompile:
    def test_validate_good_and_bad(self):
        assert bcompile.validate_blueprint_yaml(BACKEND.read_text(), TODO) == "ok"
        assert bcompile.validate_blueprint_yaml("a: [", TODO).startswith("error: not valid YAML")
        assert bcompile.validate_blueprint_yaml("- a", TODO).startswith("error: candidate did not parse")

    def test_dangling_reference(self):
        bad = BACKEND.read_text().replace("composed_of: [python, sqlite, fastapi, sqlalchemy, pydantic]",
                                          "composed_of: [python, ghost_node]", 1)
        assert "ghost_node" in bcompile.validate_blueprint_yaml(bad, TODO)

    def test_metadata_and_classification(self):
        out = bcompile.ensure_component_metadata("form: {}\n", "python_fastapi", "BACKEND_FASTAPI_PORT")
        assert out.startswith("tech_profile: python_fastapi\nport: ${{ settings.BACKEND_FASTAPI_PORT }}")
        assert bcompile.ensure_component_metadata(out, "x", "Y") == out
        assert bcompile.classification_shape("SHAPE: integrated\nPROFILE: python_fastapi") == "INTEGRATED"
        assert bcompile.classification_shape("nonsense") == "NO_FIT"
        assert bcompile.classification_profile("SHAPE: SINGLE\nPROFILE: go_gin") == "go_gin"
        assert bcompile.is_known_tech_profile("python_fastapi") and not bcompile.is_known_tech_profile("go_gin")
