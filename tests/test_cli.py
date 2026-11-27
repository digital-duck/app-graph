"""The `appgraph` developer CLI: validate (a file or a folder), the build order, -v / -h, and the full command list without cut-off summaries."""
from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from appgraph.cli import main
from tests.conftest import FLAT_V1_YAML

CYCLE = """domain: bad
primitives:
  a: {symbol: a, defines: x, tier: 0}
concepts:
  b: {composed_of: [c], defines: x, tier: 1}
  c: {composed_of: [b], defines: x, tier: 1}
"""


@pytest.fixture
def folder(tmp_path):
    (tmp_path / "ok.graph.yaml").write_text(FLAT_V1_YAML)
    (tmp_path / "bad.graph.yaml").write_text(CYCLE)
    return tmp_path


def run(*args):
    return CliRunner().invoke(main, list(args))


def test_validate_a_good_file_says_ok_and_exits_0(folder):
    r = run("validate", str(folder / "ok.graph.yaml"))
    assert r.exit_code == 0 and "is valid" in r.output


def test_validate_a_cyclic_file_names_the_cycle_and_exits_1(folder):
    r = run("validate", str(folder / "bad.graph.yaml"))
    assert r.exit_code == 1 and "cycle among: b, c" in r.output


def test_validate_a_folder_checks_every_graph_and_exits_1_if_any_fails(folder):
    r = run("validate", str(folder))
    assert r.exit_code == 1 and "OK   ok.graph.yaml" in r.output and "FAIL bad.graph.yaml" in r.output and "1 passed, 1 failed" in r.output
    assert run("validate", str(folder / "ok.graph.yaml")).exit_code == 0
    (folder / "bad.graph.yaml").unlink()
    assert run("validate", str(folder)).exit_code == 0


def test_validate_a_folder_can_report_json(folder):
    r = run("validate", str(folder), "--format", "json")
    rows = {row["path"]: row for row in json.loads(r.output)}
    assert rows["ok.graph.yaml"]["status"] == "OK" and rows["bad.graph.yaml"]["status"] == "FAIL" and "cycle" in rows["bad.graph.yaml"]["error"]


def test_validate_all_still_works_but_is_deprecated_and_hidden(folder):
    r = run("validate-all", str(folder))
    assert r.exit_code == 1 and "deprecated" in r.output and "FAIL bad.graph.yaml" in r.output
    assert "validate-all" not in run("-h").output


def test_order_prints_dependencies_before_what_needs_them(folder):
    names = [line.split()[-1] for line in run("order", str(folder / "ok.graph.yaml")).output.splitlines() if line.strip()]
    assert names.index("velocity") < names.index("acceleration") < names.index("newtons_second_law")


def test_dash_h_and_dash_v_work_and_no_summary_is_cut_off_with_dots():
    out = run("-h").output
    assert run("-v").output.startswith("appgraph, version ") and run("--version").exit_code == 0
    assert not [l for l in out.splitlines() if l.rstrip().endswith("...") and not l.startswith("Usage")]
