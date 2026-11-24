# etl_workflow

A three-step data pipeline (fetch → transform → load) with bounded retry logic on fetch failure
and a dedicated error-handling branch when retries are exhausted. It's app-graph's reference
fixture for the `workflow` domain type: `entry:`, `pre`/`execute`/`post` phases per step, a
bounded retry loop, and action-routed transitions (`function.transitions`) that may cycle, unlike
the acyclic `form_graph` every other domain type uses.

## Status

`workflow` domain, `python_library` tech profile, single standalone component — **no
`main.graph.yaml`**, by design (see the comment block at the top of
[`blueprint/etl_workflow.graph.yaml`](blueprint/etl_workflow.graph.yaml)): a workflow graph has no
other components to integrate with, so it's built directly with `appgraph build` (the `build_component` recipe) rather than
the `build_app` recipe the multi-component apps use. Built,
**23/23 pytest passing**. See [`apps/README.md`](../README.md)'s `etl_workflow` fixtures-table row
for full build history.

## Quick setup

```bash
cd apps/etl_workflow/etl_workflow
pip install -r requirements.txt
```

```python
from app.schemas import State
from app.fetch_data import fetch_data_pre, fetch_data_execute, fetch_data_post
from app.transform_data import transform_data_execute
from app.load_data import load_data_execute

shared = State(
    config={"api_url": "https://api.example.com/records", "auth_token": "<token>"},
    fetcher=my_fetcher,
    loader=my_loader,
)
shared = fetch_data_pre(shared)
exec_res = fetch_data_execute(shared)
action = fetch_data_post(shared, exec_res)  # "success" | "retry" | "error"
```

See [`etl_workflow/README.md`](etl_workflow/README.md) for the full step-by-step usage example
(all five steps wired together) and the complete function reference.

## How to verify

```bash
cd apps/etl_workflow/etl_workflow
pytest tests/
```

Expect `23 passed`. To rebuild from the blueprint instead of just running the existing tests:

```bash
appgraph build apps/etl_workflow/blueprint/etl_workflow.graph.yaml \
    --tech-profile python_library \
    --output-dir apps/etl_workflow/etl_workflow \
    --llm claude_cli
```
