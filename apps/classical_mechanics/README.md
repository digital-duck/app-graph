# classical_mechanics

A ConceptBook curriculum tracing classical mechanics from four primitives (position, time, mass,
force) through five lessons to the normal-mode analysis of coupled oscillators. `graph-code`'s
reference fixture for the `curriculum` domain type: first/second-radical primitives,
`enforce_two_radical`, and an ordered concept-dependency chain to a capstone — the schema
machinery `enforce_two_radical`/`reducible(first_radical_only=True)` exist to check.

## Status

`curriculum` domain, `curriculum` tech profile (Markdown lesson prose, not source code), single
standalone component — **no `main.graph.yaml`**: a curriculum has no HTTP layer and nothing else
to integrate with, so it's built directly via `build_component.spl`. Built, **5/5 pytest passing**
against a hand-authored `tests/test_derivations.py` that independently re-derives each lesson's
result with `sympy` rather than parsing the generated prose. See [`apps/README.md`](../README.md)'s
`classical_mechanics` fixtures-table row for full build history.

`blueprint/classical_mechanics_flat.graph.yaml` sits alongside the real blueprint — it's the
legacy v1.0 flat format, kept deliberately un-buildable (no `blueprint:` block) to exercise
`load_domain()`'s backward-compatibility normalization; it is not part of this app's build.

## Quick setup

No install step — the curriculum's output is Markdown, not runnable code. Read the lessons
directly:

```bash
cd apps/classical_mechanics/conceptbook
cat README.md          # table of contents, in dependency order
cat lessons/velocity.md
```

See [`conceptbook/README.md`](conceptbook/README.md) for the full lesson-by-lesson table of
contents and the prerequisite graph (position/time → velocity → acceleration; mass + velocity →
momentum; force + mass + acceleration, enriched by momentum → Newton's second law → normal modes).

## How to verify

```bash
cd apps/classical_mechanics/conceptbook
pytest tests/
```

Expect `5 passed` — each test independently re-derives a lesson's physics result with `sympy` and
checks it against the corresponding generated lesson. To rebuild from the blueprint instead of
just running the existing tests:

```bash
spl3 run spl/build_component.spl --tools spl/tools.py \
    -p component_graph=apps/classical_mechanics/blueprint/classical_mechanics.graph.yaml \
    -p tech_profile=curriculum \
    -p output_dir=apps/classical_mechanics/conceptbook \
    --llm claude_cli
```
