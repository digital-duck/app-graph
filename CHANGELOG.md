# Changelog

## 0.2.0 (unreleased)

- **New name: app-graph** (PyPI `app-graph`, package `appgraph`, commands `appgraph` and `agr`), continuing grafcode 0.1.1 from the graph-code repository, which stays as it was. `grafcode`/`gfc` are not installed by this package, so both can live in one environment. Work folders move from `~/graph-code/` to `~/app-graph/`; the extract cache from `.grafcode_cache/` to `.appgraph_cache/`.
- `drift --mode semantic` calls the model through dd-llm directly (one call per dimension, the same prompt); no `spl3` subprocess. The default `--llm` is `claude_cli:claude-sonnet-5-5`.
- New core dependencies: `graflang` and `dd-llm` (the build workflows are moving onto GraphLang, see `docs/DEV/graflang-refactor.md`); `zinet>=0.2.2`.

## 0.1.1

- The fief example (`apps/fief/blueprint/component.graph.yaml`) now has a `blueprint:` id, so every bundled example graph loads (fixes `test_example_files_load`). No code changes.

## 0.1.0

First release on PyPI, as `grafcode` (`pip install grafcode`; the import package is `graph_code`). `graph.yaml` as an app or curriculum blueprint (Unified Duality Graph Schema v2.1+): form and function spaces, events, transitions, call contracts, aliased imports, drift and clustering, with the `grafcode` / `gfc` command line.

- The form-space algorithms (`acyclic`, `reducible`, `productivity_order`, `learning_path`, `gap`, `build_order`) run on [zinet](https://pypi.org/project/zinet/) (>=0.2.0), shared with GraphLang and work-graph. Results are unchanged; `acyclic` no longer enumerates every cycle (it was exponential on dense cycles).
- Requires Python 3.11 or newer (spl-llm needs it).
