# spl/

`.spl` workflows and their Python tool/profile support, run via the `spl3`
CLI (installed separately — see the sibling `SPL.py` repo). This is an
index only; each file's own header comment is the authoritative source.

| File | Purpose |
|---|---|
| `build_app.spl` | System orchestrator. Reads a system graph.yaml (e.g. `apps/todo/blueprint/main.graph.yaml`), builds each imported component in authored order via `build_component.spl`, halts on the first failed component, then runs `integrate_system.spl` once. |
| `build_component.spl` | Generic component build workflow. Reads one component graph.yaml, generates each node in topological order, verifies at node and edge level, and caches results (`use_cache`/`--use_cache`, see `docs/DEV/BUILD/blueprint-schema-v2.2.md`). |
| `compile_blueprint.spl` | Natural-language intent -> a well-formed component graph.yaml. Scoped to one `domain_type: software` component, not a multi-component system. |
| `integrate_system.spl` | System-level integration only — assumes every imported component is already built and verified. Starts the live backend, generates and runs one HTTP acceptance test per `applications:` entry, tears the backend down, writes the system README last so it reflects real results. |
| `tech_profiles.py` | Tech-stack style guides passed to the LLM as generation context, plus `NODE_FILES` (node id -> output file path, keyed by app_name — see `docs/DEV/BUILD/refactoring-plan-v1.md` §1.3) and `VERIFY_CMDS` per profile. |
| `tools.py` | `@spl_tool`-decorated Python functions callable from `.spl` scripts via `CALL` — graph loading/validation, node file writing, caching, settings interpolation, acceptance-test plumbing, etc. |

See `docs/DEV/BUILD/README.md` for the fuller build pipeline walkthrough and
`docs/DEV/BUILD/refactoring-plan-v1.md` for the current framework refactor
in progress.
