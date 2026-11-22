You are producing the system-level main.graph.yaml for an INTEGRATED app —
the one file that imports a backend.graph.yaml and a frontend.graph.yaml
component (already compiled separately) and composes them into cross-
component applications. Do NOT re-specify the backend or frontend's own
internal nodes here — this file only imports them and describes the
use-cases that span both.

Reverse-engineered intent (from static analysis of an existing repo):
{{in_extraction_intent}}

App name: {{in_app_name}}

Schema shape, illustrated by a complete, real example (a to-do app's
main.graph.yaml — study its shape exactly, then produce the same shape for
the actual app above, adjusting domain/comment/imports/applications to fit):

```yaml
domain: software/apps/{{in_app_name}}
target_languages: [python, typescript]
comment: |
  One-paragraph description of the whole app and what it does for a user.
capstone: manage_{{in_app_name}}

blueprint:
  id: {{in_app_name}}_app
  schema_version: "2.2"
  graph_schema_version: "2.1"
  domain_type: integrated
  provenance: reverse
  parent_blueprint: null
  lineage: []

imports:
  - id: backend
    graph: ./backend.graph.yaml
    comment: |
      One sentence: what the backend serves, at what port, CORS policy.
  - id: frontend
    graph: ./frontend.graph.yaml
    comment: |
      One sentence: what the frontend is, at what port, what it calls.

ports:
  backend: ${{ settings.BACKEND_FASTAPI_PORT }}
  frontend: ${{ settings.FRONTEND_VITE_PORT }}

form:
  nodes:
    app_shell:
      kind: component
      defines: "System integration shell: frontend consuming backend REST API via CORS"
      tier: 1
      depends_on: [backend, frontend]

    readme:
      kind: doc
      defines: "README.md: product-level overview, setup, and run instructions"
      composed_of: [app_shell]
      tier: 2
      spec:
        interface: |
          Output: README.md at the system root — plain Markdown, not code.
        contract: |
          Title, one-paragraph description, Architecture, Running the full
          system, Applications (one line per applications: entry below).

function:
  exports:
    - name: manage_{{in_app_name}}
      kind: port
      from: app_shell.main
      signature: "() -> void"

applications:
  <one entry per real cross-component use-case found in the reverse-engineered
   intent — each needs backend: [<backend node ids>] and frontend: [<frontend
   node ids>], a user_story, and a contract. End with exactly one capstone:
   true entry (tier one higher than the rest) whose needs.applications lists
   every other application id — the manage_{{in_app_name}} entry above.>

verification:
  - node: app_shell
    tool: integrate_system.spl
    checks:
      - CORS headers present on all backend responses
      - frontend loads without console errors
      - every application passes acceptance tests against the live system
```

Rules, all non-negotiable:
1. `imports:` must reference exactly `./backend.graph.yaml` and
   `./frontend.graph.yaml` — those two files are compiled separately by this
   same pipeline, in this same output directory.
2. Do not declare `form.nodes` for anything backend or frontend already
   owns — only `app_shell` and `readme` (or their equivalents) belong here.
3. Every `applications:` entry needs at least one backend node id and one
   frontend node id under `needs`, a concrete `spec.user_story`, and a
   concrete `spec.contract` — derive these from the reverse-engineered
   intent above, don't invent unrelated use-cases.
4. Exactly one `applications:` entry has `capstone: true`, at the highest
   tier, with `needs.applications` listing every other application id.
5. Output ONLY the YAML document. No preamble, no markdown fences, no
   commentary before or after.
