# jwt_provider

A standalone Python library for issuing and verifying JWT tokens (HMAC-SHA256). Pure library
code — no web framework, no database — meant to be consumed by other components (e.g. a future
real implementation of [`apps/physics_app`](../physics_app)'s `auth_middleware`, which today
takes `verify_token` as an injected callable rather than importing this library directly, since
each app-graph component builds and tests in complete isolation).

## Status

`software` domain, `python_library` tech profile, single standalone component — **no
`main.graph.yaml`**, by design (see the comment block at the top of
[`blueprint/jwt_provider.graph.yaml`](blueprint/jwt_provider.graph.yaml)): it has no HTTP layer
and nothing else to integrate with, so it's built directly with `appgraph build` (the `build_component` recipe) rather than
the `build_app` recipe the multi-component apps use. Built,
**10/10 pytest passing**. See [`apps/README.md`](../README.md)'s `jwt_provider` fixtures-table
row for full build history (including a data-integrity incident on the first build attempt,
since fixed).

## Quick setup

```bash
cd apps/jwt_provider/jwt_provider
pip install -r requirements.txt
```

```python
from app.core import issue_token, verify_token

token = issue_token({"user_id": 42, "role": "admin"}, secret="my-secret-key", expires_in=3600)
payload = verify_token(token, secret="my-secret-key")
# payload.claims      -> {"user_id": 42, "role": "admin"}
# payload.expires_at  -> datetime (UTC)
```

See [`jwt_provider/README.md`](jwt_provider/README.md) for the full API reference (`issue_token`/
`verify_token` signatures, error cases) and library-level usage details.

## How to verify

```bash
cd apps/jwt_provider/jwt_provider
pytest tests/
```

Expect `10 passed`. To rebuild from the blueprint instead of just running the existing tests:

```bash
appgraph build apps/jwt_provider/blueprint/jwt_provider.graph.yaml \
    --tech-profile python_library \
    --output-dir apps/jwt_provider/jwt_provider \
    --llm claude_cli
```
