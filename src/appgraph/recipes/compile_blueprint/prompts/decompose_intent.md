You are decomposing a natural-language application description into a
well-formed "blueprint" graph.yaml — a fine-grained, node-level specification
that a separate tool (build_component.spl) will later walk in dependency
order, generating and verifying one file of code per node. Your job is
ONLY to produce the graph.yaml structure — do not write any application code.

Application intent to decompose:
{{in_intent}}

Target domain_type: {{in_domain_type}}
Target tech_profile: {{in_tech_profile}}

Schema shape, illustrated by a complete, real, minimal example (a tiny
counter API — study its shape exactly, then decompose the actual intent
above into the same shape, adjusting node count/names/specs to fit):

```yaml
graph: counter_backend
version: "2.1"
domain_type: software
domain: software/backend/fastapi
target_languages: [python]
description: |
  FastAPI backend: in-memory counter with a GET/POST API.
capstone: counter_routes

blueprint:
  id: counter_backend
  schema_version: "2.2"
  domain_type: software
  provenance: authored
  parent_blueprint: null
  lineage: []

form:
  primitives:
    python:
      defines: "Python 3.x runtime and standard library"
      tier: 0
      kind: config
    fastapi:
      defines: "FastAPI web framework"
      tier: 0
      kind: config

  nodes:
    counter_store:
      kind: module
      defines: "In-memory counter state and increment function"
      composed_of: [python]
      tier: 1
      spec:
        interface: |
          get_count() -> int
          increment() -> int
        contract: |
          Starts at 0. increment() adds one and returns the new value.
      verification:
        node: |
          - get_count() returns 0 initially
          - increment() increases the value by exactly 1 each call
      docs: |
        - Pure in-memory state, no persistence

    counter_routes:
      kind: module
      defines: "FastAPI router exposing the counter as REST endpoints"
      composed_of: [fastapi, counter_store]
      tier: 2
      ports:
        get_count:
          signature: "GET /count -> int"
          kind: call
          direction: out
        increment:
          signature: "POST /increment -> int"
          kind: call
          direction: out
      spec:
        interface: |
          GET  /count      -> int
          POST /increment   -> int
        contract: |
          Both routes call into counter_store; no direct state manipulation in the route handlers.
      verification:
        node: |
          - GET /count returns the current value
          - POST /increment increases the value and returns the new one
      docs: |
        - The backend's public surface

function:
  exports:
    - name: get_count
      kind: port
      from: counter_routes.get_count
      signature: "GET /count -> int"
    - name: increment
      kind: port
      from: counter_routes.increment
      signature: "POST /increment -> int"

verification:
  - node: counter_routes
    backend: pytest
    tests: tests/test_routes.py
```

Rules, all non-negotiable:
1. `form.nodes` must form a DAG — every `composed_of` entry must reference a
   node or primitive declared earlier (lower tier), never itself or a later one.
2. Every node needs `kind`, `defines`, `tier` (integer, primitives are tier 0),
   and a `spec.interface`/`spec.contract` pair specific enough that an LLM
   could generate the actual file from it without further clarification.
3. `capstone` must name the graph's own last/highest-tier node.
4. Keep node count proportional to the intent's actual complexity — do not
   pad with nodes the intent doesn't call for, and do not collapse
   distinct concerns (e.g. data model vs. HTTP routes) into one node.
5. Output ONLY the YAML document. No preamble, no markdown fences, no
   commentary before or after.
