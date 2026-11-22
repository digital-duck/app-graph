"""graph_lib's algorithms now run on zinet (zinet.algorithms). These pin the behaviours that must not change in the move:
the order of ties, optional edges, the two-radical rule, and errors still being ToolFailed. Expected values are what graph_lib
returned before the move (frozen in zinet's tests/characterization/golden/appgraph.json)."""
import pytest

from appgraph.exceptions import ToolFailed
from appgraph.graph_lib import acyclic, build_order, gap, learning_path, productivity_order, reducible
from appgraph.loader import _build_graph_domain


def domain(primitives, nodes, first_radical=()):
    return _build_graph_domain({
        "form": {"primitives": {p: {} for p in primitives}, "nodes": nodes},
        "first_radical_primitives": list(first_radical),
    })


@pytest.fixture()
def ties():          # equal reach, declared out of alphabetical order: ties follow insertion order, as before
    return domain(["zp", "ap"], {
        "zeta": {"composed_of": ["zp"]}, "alpha": {"composed_of": ["ap"]}, "mid": {"composed_of": ["zp"]},
        "beta": {"composed_of": ["ap"]}, "omega": {"composed_of": ["zeta", "alpha"]}, "theta": {"composed_of": ["mid", "beta"]}})


def test_ties_keep_the_order_graph_lib_always_gave(ties):
    assert build_order(ties) == ["zeta", "mid", "alpha", "beta", "omega", "theta"]
    assert productivity_order(ties) == ["alpha", "beta", "mid", "zeta", "omega", "theta"]
    assert learning_path(ties, [], "omega") == ["zeta", "alpha", "omega"]
    assert gap(ties, [], "theta") == ["mid", "beta", "theta"]


def test_primitives_are_available_and_known_nodes_are_skipped():
    g = domain(["p"], {"a": {"composed_of": ["p"]}, "b": {"composed_of": ["a"]}, "c": {"composed_of": ["b"]}})
    assert learning_path(g, [], "c") == ["a", "b", "c"]
    assert learning_path(g, ["a"], "c") == ["b", "c"]
    assert learning_path(g, ["a", "b", "c"], "c") == []
    assert learning_path(g, [], "p") == []                      # a primitive needs nothing
    assert build_order(g) == ["a", "b", "c"]                    # primitives are not in a build order


def test_optional_edges_are_not_part_of_the_path():
    g = domain(["p"], {"a": {"composed_of": ["p"]}, "e": {"composed_of": ["p"]}, "b": {"composed_of": ["a"], "optionally_depends_on": ["e"]}})
    assert learning_path(g, [], "b") == ["a", "b"]
    assert "e" not in build_order(g)[:build_order(g).index("a")]


def test_reducible_rules_are_unchanged():
    g = domain(["x", "t", "m"], {"v": {"composed_of": ["x", "t"]}, "a": {"composed_of": ["v", "t"]}, "p": {"composed_of": ["m", "v"]}},
               first_radical=["x", "t"])
    assert reducible(g) is True
    assert reducible(g, first_radical_only=True) is False       # `p` needs the second radical `m`
    lonely = domain(["p"], {"root": {}, "a": {"composed_of": ["root"]}})
    assert reducible(lonely) is False                           # app-graph wants a primitive underneath every node
    dangling = domain(["p"], {"a": {"composed_of": ["p", "ghost"]}})
    assert reducible(dangling) is True                          # an undeclared name is not app-graph's concern here


def test_errors_are_still_tool_failed():
    cyc = domain(["p"], {"a": {"composed_of": ["p", "c"]}, "b": {"composed_of": ["a"]}, "c": {"composed_of": ["b"]}})
    with pytest.raises(ToolFailed, match="cycle among: a, b, c"):
        acyclic(cyc)
    for call in (lambda: build_order(cyc), lambda: productivity_order(cyc), lambda: learning_path(cyc, [], "c")):
        with pytest.raises(ToolFailed, match="cycle"):
            call()
    with pytest.raises(ToolFailed, match="Target 'nope' not in graph"):
        learning_path(domain(["p"], {"a": {"composed_of": ["p"]}}), [], "nope")


def test_a_long_cycle_is_reported_without_enumerating_every_cycle():
    """The old check listed every cycle (exponential on a dense cycle); this one only finds the nodes on it."""
    n = 14
    nodes = {f"n{i}": {"composed_of": [f"n{j}" for j in range(n) if j != i]} for i in range(n)}      # a complete graph: n! cycles
    with pytest.raises(ToolFailed, match="cycle"):
        acyclic(domain([], nodes))
