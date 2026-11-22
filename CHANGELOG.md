# Changelog

## 0.2.0 (unreleased)

- **New name: app-graph** (PyPI `app-graph`, package `appgraph`, commands `appgraph` and `agr`), continuing grafcode 0.1.1 from the graph-code repository, which stays as it was. `grafcode`/`gfc` are not installed by this package, so both can live in one environment. Work folders move from `~/graph-code/` to `~/app-graph/`; the extract cache from `.grafcode_cache/` to `.appgraph_cache/`.
- `drift --mode semantic` calls the model through dd-llm directly (one call per dimension, the same prompt); no `spl3` subprocess. The default `--llm` is `claude_cli:claude-sonnet-5-5`.
- **`appgraph build` of a component runs a GraphLang recipe** (`appgraph/recipes/build_component`), not `spl3`: the same prompts, checks, cache and repair loop; the tests run in a Docker container (`appgraph-verify:py3.12`, build it from `src/appgraph/docker/python.Dockerfile`); the result is `passed`, `no_tests`, `failed` or `refused`, with a markdown summary under `~/app-graph/logs/`. New options `--max-llm-calls`, `--max-test-attempts`, `--no-cache`. A node whose spec is generated now hits the cache on the next run. A system target (`imports:`) runs the `build_app` recipe: every component, stopping at the first that fails (`component_failed`), then one acceptance script per application run against the live backend **inside the test container** (the server cannot be left running), then the README (`passed` or `integration_failed`). Vue components are tested in an image built once per lockfile. `build` no longer needs `spl3`.
- **`extract --llm` runs the `compile_blueprint` recipe** (same prompts, the same 16000-token budget, the same validate-and-repair loop). `--persistence` now means a GraphLang checkpoint (`checkpoint`, default, or `none`; `sqlite` still accepted; `postgres`/`dbos` removed); new `--max-llm-calls`.
- **Removed: `spl-llm` and the `.spl` workflows** (`src/appgraph/spl/`), `appgraph tools spl-lint`. Nothing calls `spl3`.
- **Test containers.** A test step that writes files is allowed only under your home folder or the temporary folder (a Cedar policy). Nothing from disk is mounted into a test container. The containers have no network.
- **Prompts** are graph-code's, byte for byte, now one file each under `recipes/*/prompts/`.
- **Docs.** README, CLAUDE.md and the User Guide are rewritten for the recipes. The User Guide corrects `extract --llm`'s repair count: the code always allowed 2 repairs, though the docs said it was fail-fast with 0.
- New core dependencies: `graflang` and `dd-llm` (see `docs/DEV/graflang-refactor.md`); `zinet>=0.2.2`. Removed: `spl-llm`.

## 0.1.1

- The fief example (`apps/fief/blueprint/component.graph.yaml`) now has a `blueprint:` id, so every bundled example graph loads (fixes `test_example_files_load`). No code changes.

## 0.1.0

First release on PyPI, as `grafcode` (`pip install grafcode`; the import package is `graph_code`). `graph.yaml` as an app or curriculum blueprint (Unified Duality Graph Schema v2.1+): form and function spaces, events, transitions, call contracts, aliased imports, drift and clustering, with the `grafcode` / `gfc` command line.

- The form-space algorithms (`acyclic`, `reducible`, `productivity_order`, `learning_path`, `gap`, `build_order`) run on [zinet](https://pypi.org/project/zinet/) (>=0.2.0), shared with GraphLang and work-graph. Results are unchanged; `acyclic` no longer enumerates every cycle (it was exponential on dense cycles).
- Requires Python 3.11 or newer (spl-llm needs it).
