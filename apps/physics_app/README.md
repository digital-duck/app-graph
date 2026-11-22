# physics_app

An `integrated` system that composes a reactive physics simulator with optional JWT-verifying
auth middleware — `graph-code`'s reference fixture for graph-of-graphs composition: `imports:`,
`optionally_depends_on:` (auth is optional, required only for the web deployment), and a real
cross-graph `function.calls` contract (`app_shell.render_simulator` → `simulator.
calculate_velocity`), verified with zero warnings by `check_call_contracts()`.

## Architecture

```
main.graph.yaml (app_shell)
    depends_on:            simulator  (physics_simulator.graph.yaml, mandatory)
    optionally_depends_on:  auth       (auth_middleware.graph.yaml, optional)
```

- **[physics_simulator](physics_simulator/README.md)** — `reactive_app` domain. A position slider
  emits `PositionUpdate` events; a velocity calculator and graph subscribe and react. Pure Python,
  no GUI toolkit. Built, 12/12 pytest passing.
- **[auth_middleware](auth_middleware/README.md)** — `software` domain. Framework-agnostic
  Bearer-token middleware; takes `verify_token` as an injected callable rather than importing
  [`jwt_provider`](../jwt_provider) directly (each component builds and tests in isolation — this
  is a *contract* dependency, checked by `check_call_contracts()`, not a literal import). Built,
  9/9 pytest passing.

## Status

`integrated` domain at the system level, but **deliberately never run through `build_app.spl`**
(see the comment block at the top of [`blueprint/main.graph.yaml`](blueprint/main.graph.yaml)):
unlike the ported reference apps (`todo`, `kanban`, ...), this system has no HTTP server anywhere
in its component tree — both components are plain Python libraries — and `build_app.spl`
unconditionally runs `integrate_system.spl` last, which assumes a live backend to start and REST
`applications:` to acceptance-test. `main.graph.yaml`'s own `app_shell` node has no `spec:` (same
convention as `todo`'s `todo_app_shell`) — system-shell nodes aren't independently code-generated,
so each component is built directly via its own `build_component.spl` run instead. See
[`apps/README.md`](../README.md)'s `physics_app`/`physics_simulator`/`auth_middleware`
fixtures-table rows for full build history.

## Quick setup

```bash
cd apps/physics_app/physics_simulator && pip install -r requirements.txt && cd -
cd apps/physics_app/auth_middleware && pip install -r requirements.txt && cd -
```

```python
from app.position_slider import PositionSlider
from app.calculator import VelocityCalculator
from app.velocity_graph import VelocityGraph

calculator = VelocityCalculator()
graph = VelocityGraph(calculator, dt=1.0)
slider = PositionSlider()
slider.subscribe(graph.redraw_curve)

slider.set_position(0.0)
slider.set_position(5.0)
print(graph.history)   # [(datetime, velocity), ...]
```

Wrapping calls behind auth (optional, web-deployment only) — see
[`auth_middleware/README.md`](auth_middleware/README.md) for the full `Middleware.require_auth`
example, and [`jwt_provider`](../jwt_provider) for a `verify_token` implementation to inject.

## How to verify

```bash
cd apps/physics_app/physics_simulator && pytest tests/   # expect 12 passed
cd apps/physics_app/auth_middleware && pytest tests/      # expect 9 passed
```

To rebuild either component from its blueprint instead of just running the existing tests:

```bash
spl3 run spl/build_component.spl --tools spl/tools.py \
    -p component_graph=apps/physics_app/blueprint/physics_simulator.graph.yaml \
    -p tech_profile=python_library \
    -p output_dir=apps/physics_app/physics_simulator \
    --llm claude_cli

spl3 run spl/build_component.spl --tools spl/tools.py \
    -p component_graph=apps/physics_app/blueprint/auth_middleware.graph.yaml \
    -p tech_profile=python_library \
    -p output_dir=apps/physics_app/auth_middleware \
    --llm claude_cli
```

To check the system-level graph itself (imports, contracts, acyclicity) without generating any
code:

```bash
grafcode validate-system apps/physics_app/blueprint/main.graph.yaml
```
