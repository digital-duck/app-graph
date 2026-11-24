# `appgraph` User Guide

`appgraph` is the CLI for app-graph blueprint files (`*.graph.yaml`). It
validates, extracts, builds, and inspects blueprint graphs — the `Unified
Duality Graph Schema v2.1+` files that describe an app's structure before
any code exists. The commands that call a model (`extract --llm`, `build`,
`drift --llm`) run **GraphLang recipes** (`src/appgraph/recipes/`) through
a dd-llm adapter; everything else is the schema + algorithms library and
makes no model call.

This guide covers every `appgraph` subcommand with real examples. For the
schema itself (what goes *in* a `graph.yaml`), see
`docs/DEV/BUILD/blueprint-schema-v2.2.md` and the worked example at
`apps/todo/blueprint/`. For architecture/internals aimed at an AI coding
agent working in this repo, see the root `CLAUDE.md`.

## Install

```bash
conda create -n graf python=3.11
conda activate graf

pip install -e ".[dev]"   # from this repo's root (dev checkout)
# or: pip install app-graph  (release install)
appgraph --help            # sanity check
agr --help                 # same CLI, shorter name
```

This installs two console scripts — `appgraph` and `agr` (both point at
`appgraph.cli:main`) — and pulls in `graflang` (the recipe runtime) and
`dd-llm` (the model adapters). `appgraph ide`'s Vue frontend needs a
manual one-time `npm install` (see its section below), since `pip` can't
install npm packages.

### Docker, for `build`

`appgraph build` runs every component's tests in a container with no
network. Python components use one image; build it once from a checkout:

```bash
docker build -t appgraph-verify:py3.12 -f src/appgraph/docker/python.Dockerfile src/appgraph/docker
```

Vue components use an image made from their own `package-lock.json`
(`appgraph-verify-node:<hash>`, from `node:22`), built automatically the
first time it's needed — so a Vue component's folder needs a lockfile
(run `npm install` there once). Nothing from your disk is mounted into
either container: the code goes in on stdin.

### Verify your environment

```bash
appgraph --help
graf --version                                   # the GraphLang CLI, if you want to validate/draw a recipe
docker image inspect appgraph-verify:py3.12 >/dev/null && echo image-ok
```

### The `~/app-graph` workspace

Commands that write files default into named subfolders of `~/app-graph`
(created on first use, not eagerly) rather than into this repo's own
`apps/` — so a plain `pip install appgraph` user always has somewhere
writable to work, and repeat runs never silently collide with someone
else's checked-in apps:

| Subfolder | Used by |
|---|---|
| `~/app-graph/output/<app>` | `appgraph extract`'s default `--output-dir` |
| `~/app-graph/input/<app>` | `appgraph build`'s default `--input-dir` (when TARGET is an app name, not a direct path) |
| `~/app-graph/report/` | `appgraph report`/`compare`/`drift`'s `--out FILE`, for a bare filename |
| `~/app-graph/ide/` | `appgraph ide`'s default `--apps-root` |

Every one of these has an explicit override flag — pass this repo's own
`apps/<app>` (or any other path) instead when working inside a app-graph
checkout, which is what app-graph's own development does throughout this
guide's examples below.

## The convention every command assumes

Every app lives at `apps/<app>/`, with its blueprint source under
`apps/<app>/blueprint/*.graph.yaml` and (once built) generated code as a
*sibling* of `blueprint/`, never inside it:

```
apps/todo/
├── blueprint/
│   ├── main.graph.yaml       ← entry point: imports:, applications:, capstone
│   ├── backend.graph.yaml    ← domain_type: software
│   ├── frontend.graph.yaml   ← domain_type: software
│   └── settings.yaml         ← optional: ${{ settings.KEY }} values (ports, etc.)
├── backend/                  ← generated code (once built)
└── frontend/                 ← generated code (once built)
```

A standalone component with no system-level composition (e.g. a `workflow`
app, or a library like `jwt_provider`) just has a single
`apps/<app>/blueprint/<name>.graph.yaml` and no `main.graph.yaml`.

---

## Command reference

### `appgraph validate <graph.yaml>`

Loads one file and runs `validate_full()`: `acyclic()` always; the
Two-Radical check if `enforce_two_radical: true`; `validate_events()` if the
function space is non-empty; `check_call_contracts()`; and
`validate_transitions()` if `function.transitions` is non-empty. One command
for both levels — it looks at whether the file has an `imports:` block, no
separate command needed:

```bash
appgraph validate apps/todo/blueprint/backend.graph.yaml
# OK — apps/todo/blueprint/backend.graph.yaml is valid (0 warning(s))
```

A **component** graph (no `imports:`) just runs the check above on itself.
A **system** graph (`imports:` present, e.g. `main.graph.yaml`) additionally
validates every imported component (recursively, each with its own
`validate_full()`) and cross-component call contracts (`function.calls` — a
consumer's `consumer_requires` vs. the provider's `provider_guarantees`)
after merging imports via `resolve_imports()`:

```bash
appgraph validate apps/todo/blueprint/main.graph.yaml
```

An `optional: true` import whose file is missing produces a warning, not an
error; a required import that's missing does. Run the system form before
every real build — it's the check that catches a frontend calling a backend
endpoint that doesn't actually exist, or with a mismatched contract.

Warnings (e.g. `UNREACHABLE_STEP`) print but don't fail the command;
`ToolFailed` (a hard error — a cycle, a broken call contract) exits 1.

### `appgraph order <graph.yaml>`

Prints the topological build order — the same order the `build_component` recipe
generates nodes in (mandatory-edge subgraph only; `enriched_by`/
`optionally_depends_on` are ignored for ordering purposes).

```bash
appgraph order apps/todo/blueprint/backend.graph.yaml
#   0  python
#   1  fastapi
#   2  requirements
#   ...
```

### `appgraph report <graph.yaml> [--out FILE]`

Quick counts — node/edge/import/event totals, without validating.

```bash
appgraph report apps/todo/blueprint/main.graph.yaml
```

`--out FILE` writes to a file instead of stdout (a bare filename with no
directory component resolves under `~/app-graph/report/`) — same flag on
`compare` and `drift`, below.

### `appgraph prettify <path> [--write]`

Normalizes `*.graph.yaml` prose scalars (`defines`, `spec.interface`,
`spec.contract`, `docs`, ...) into `|` block literals with one bullet per
`; `-split clause, and leaves bare identifiers/paths unquoted. `PATH` is a
single file or a directory searched recursively (e.g. `apps/`).

```bash
appgraph prettify apps/todo/blueprint/backend.graph.yaml   # dry run: prints a diff
appgraph prettify apps/ --write                             # rewrites every *.graph.yaml under apps/
```

Always dry-runs first (no `--write`) before rewriting a directory you
haven't checked in yet — it touches every matching file under `PATH`.

### `appgraph new-app <app_name> <backend_port> <frontend_port> [--apps-dir DIR]`

Scaffolds a new integrated (backend+frontend) app skeleton: `apps/<app_name>/blueprint/{settings,main,backend,frontend}.graph.yaml`
stubs (each with `TODO:` markers and a worked-example pointer to
`apps/todo/blueprint/`), plus backend/frontend test directories and the
frontend's npm/vite project scaffold.

```bash
appgraph new-app inventory 8020 5190
```

Fails loudly (no silent overwrite) if `apps/inventory/` already exists and
is non-empty. Next steps after scaffolding: fill in the `TODO:`s, author the
real nodes (data_schema → db_connection → orm_model → crud_operations →
api_routes is the established shape — see `apps/todo/blueprint/backend.graph.yaml`),
then `appgraph validate apps/inventory/blueprint/main.graph.yaml`.

### `appgraph extract` — reverse-engineer a blueprint from an existing repo

The most involved command: AST/regex-analyzes an existing FastAPI+Vue-shaped
repo and drafts blueprint artifacts from it, instead of hand-authoring from
scratch.

```bash
appgraph extract \
  --repo-path ~/projects/wgong/app-graph-apps/fief \
  --output-dir apps/fief \
  --app-name fief \
  --backend-routes-dir fief/apps/api/routers \
  --backend-schema-dir fief/schemas \
  --backend-models-dir fief/models \
  --backend-services-dir fief/services \
  --backend-port 8010 --frontend-port 5180 \
  --llm claude_cli:claude-sonnet-5-5 \
  --llm-timeout 900
```

**Input**: `--repo-path DIR` (a local checkout) or `--repo-url URL`
(shallow-cloned for you) — mutually exclusive, pass exactly one. Backend/frontend
subdirectory options (`--backend-routes-dir`, `--backend-schema-dir`,
`--backend-models-dir`, `--backend-services-dir`, `--frontend-components-dir`,
`--frontend-api-dir`) are auto-detected against common conventions
(`routes/`, `api/`, `app/routes/`, ...) if omitted — pass them explicitly
when the repo doesn't match. `--scope a,b` filters extraction to routes/files
matching those tokens.

**Output** (always written, no `--llm` needed): `analysis.json` (every
route/schema/ORM model/service/component/API function found, with source
file), `EXTRACTION.md` (a companion planning doc with `TODO:` sections for
the functional description, use cases, and data model), and
`blueprint/{settings,main,backend,frontend}.graph.yaml` stubs with `TODO:`
markers wherever human or LLM judgment is required. Nothing is buildable
until those are resolved and `appgraph validate` passes clean.
`--output-dir` defaults to `~/app-graph/output/<app-name>` (created if
missing) if you don't pass it — so a repeat extraction never silently
overwrites an existing app; pass an explicit path (e.g. this repo's own
`apps/<app-name>`) to write elsewhere, as the example above does.

**`--llm ADAPTER:MODEL`** (e.g. `claude_cli:claude-sonnet-5-5`) adds a
semantic pass after the AST pass: the **`compile_blueprint`** recipe
classifies the app's shape (integrated / single-component / no fit) and
drafts *real* `spec.interface`/`spec.contract` content instead of `TODO:`
stubs, tagging its output `provenance: reverse` in the `blueprint:` block.

- **INTEGRATED** writes `blueprint/backend.graph.yaml`, `frontend.graph.yaml`
  and `main.graph.yaml` (replacing the AST-only stubs).
- **SINGLE** or **NO_FIT** writes one `blueprint/component.graph.yaml`;
  review it and rename/merge by hand.
- If no existing tech profile fits, it also writes `TECH_PROFILE_DRAFT.md`
  — a draft for you to review, never merged into
  `appgraph/build/tech_profiles.py` automatically.

Each drafted blueprint is validated (YAML parses, no cycle, no id referenced
but undeclared, settings resolve) and, while invalid, sent back to the model
with the error for repair — up to **2** repairs per blueprint. One still
invalid after that ends the pass with `FAILED: <the validation message>`; for
an integrated app, the components after it are not drafted. "Valid" is
structural only, not a claim of correctness — **review the output before
building either way**.

`--llm-timeout SECONDS` overrides the adapter's per-call timeout — bump it
for a large repo or a slow model. `--max-llm-calls N` (default 20) stops the
pass before N model calls; an integrated app with no repairs needs 5.

#### Resumability

`extract` can be interrupted (a large `--repo-url` clone, a long AST scan,
or — most commonly — a `--llm` pass that dies to a session limit or a
transient provider error). Rerunning the exact same command resumes instead
of restarting from scratch, at two granularities:

1. **Coarse** — `<output-dir>/.appgraph_cache/` persists the cloned repo
   (for `--repo-url`), the AST-extraction results, and a marker for a
   *fully-completed* `--llm` pass. A rerun with the same inputs skips
   whichever stages already finished. It invalidates automatically if the
   source repo's scanned directories change (content signature, not just a
   flag).
2. **Fine** — while the `--llm` pass runs, a GraphLang checkpoint
   (`.appgraph_cache/llm-<key>.checkpoint.json`, the key a hash of the
   model and the inputs) is written after every top-level step. If the pass
   dies, the rerun resumes after the last finished step — the shape
   classification and every blueprint already drafted are not paid for
   again. A pass that died *inside* a repair loop restarts that loop. The
   checkpoint is deleted when the pass finishes.

```bash
appgraph extract ... --llm claude_cli:claude-sonnet-5-5   # dies at the frontend draft

appgraph extract ... --llm claude_cli:claude-sonnet-5-5   # same command — resumes there
```

Pass **`--skip-cache`** to force a fresh run at both granularities (ignores
`.appgraph_cache/`, re-clones/re-scans, deletes any old checkpoint and runs
the `--llm` pass fresh). It still *writes* a fresh cache and checkpoint as
it goes, so a crash partway through a `--skip-cache` run is resumable too.

`--persistence {checkpoint|none}` (default `checkpoint`; `sqlite` is
accepted as the old name) turns the checkpoint off with `none`.

### `appgraph build TARGET [--input-dir DIR] [--output-dir DIR] [--tech-profile NAME] [--llm ADAPTER[:MODEL]]`

Generates and tests code for an app or component from its blueprint.

```bash
appgraph build apps/todo/blueprint/main.graph.yaml
appgraph build inventory --input-dir apps          # resolve by app name instead
```

`TARGET` is either a direct path to a `*.graph.yaml` file, or an app name
resolved as `INPUT_DIR/<name>/blueprint/main.graph.yaml` (falling back to
`component.graph.yaml` if there's no `main.graph.yaml`) — `--input-dir`
defaults to `~/app-graph/input`.

- A target **without** `imports:` (one component) runs the
  **`build_component`** recipe. For each node in build order, it writes
  the node's code (or takes it from `<output>/.spl_cache/`), checks the node
  and its edges, and refines it once if a check fails. Then it runs the
  component's tests in Docker. On a failure, it repairs the node the failure
  points at and runs the tests again, up to `--max-test-attempts` (default
  3) test runs. `--tech-profile` overrides the graph's own `tech_profile:`.
- A target **with** `imports:` (a system) runs the **`build_app`** recipe.
  It builds every imported component as above, each with its own tech
  profile, and stops at the first that fails. Then it writes one HTTP
  acceptance test per application, runs them against the live backend in a
  container, and writes the app's `README.md` with the real results.

The build ends **passed**, **no_tests** (the code was written, but no tests
were found), **failed**, **integration_failed**, **component_failed: NAME**
or **refused**. Refused means the output folder is not under your home or
the temporary folder, so the policy would not let it write.

The build prints a summary and the path of its log. Every run is logged
under `~/app-graph/logs/`.

| Option | Effect |
|---|---|
| `--llm ADAPTER[:MODEL]` | the model for the run (default `claude_cli`) |
| `--max-llm-calls N` | stops the build before N model calls (default: 4 per node + 1 per test attempt + 2) |
| `--no-cache` | regenerates every node instead of reusing `.spl_cache/`. The cache is the same one graph-code wrote, so an app built by graph-code rebuilds here with no model calls. |
| `--output-dir` | writes the code somewhere other than next to each component's `graph.yaml` (useful for a fresh generation beside an existing build) |

### `appgraph ide [--api-port PORT] [--dev-port PORT] [--no-frontend] [--apps-root DIR]`

Launches **Graph IDE**: a browser viewer *and editor* for an app's
blueprint graph. Shortcut for the two-terminal `uvicorn` + `npm run dev`
dance in `src/appgraph/graph-ide/README.md` — starts the FastAPI backend
(`:8880` default) and the Vite dev server (`:8881` default), and opens with
Ctrl-C stopping both.

```bash
appgraph ide --apps-root apps   # browse this repo's own example apps
# open http://localhost:8881
```

Requires the graph-ide deps installed once: `pip install "appgraph[ide]"`
(or `pip install -r tools/graph-ide/requirements.txt` in a repo checkout)
for the FastAPI backend, and `npm install` in `tools/graph-ide/frontend/`
for the Vite frontend — the one piece a plain `pip install` genuinely can't
provide, since it's npm packages, not Python ones. Use `--api-port`/
`--dev-port` if the defaults are taken, `--no-frontend` to run the API
alone (e.g. for scripted access to `GET /api/graphs?root=<app>`).

`--apps-root DIR` sets the root directory Graph IDE browses `<app>/blueprint/`
graphs under — defaults to `~/app-graph/ide` (created if missing, matching
the rest of the `~/app-graph` workspace convention above). Pass this
repo's `apps/` (as above) to browse app-graph's own example apps instead.

**In the browser**: pick an app from the dropdown (only apps with a
`blueprint/*.graph.yaml` show up), click a node to see its full spec and
transitive dependencies, drag nodes to untangle a dense graph, zoom
in/out, and — with the **Edit** toggle on — change a node's `defines`/
`spec.interface`/`spec.contract`/`spec.user_story`/`verification.node`/
`verification.edge`/`docs` and **Save** straight back to the owning
`graph.yaml`. Structural fields (`composed_of`, `depends_on`, `needs`,
`tier`, `capstone`) aren't editable through the UI yet — edit those in the
YAML directly. **⚙ Settings** holds a font-size control and a placeholder
LLM provider/model/key section (not wired to anything yet); **ℹ About**
has the node-kind legend plus the currently-loaded app's files/components.

### `appgraph drift <graph_a.graph.yaml> <graph_b.graph.yaml> [--llm ADAPTER:MODEL] [--llm-timeout SECONDS] [--dims DIM,DIM,...] [--format text|json] [--out FILE]`

Computes a **drift report** between two blueprint graphs — the 5-component
vector `docs/DEV/BUILD/blueprint-schema-v2.2.md` §3 defines for
`blueprint.drift`, one function per component (`graph_lib.py`'s
`structural_drift`/`interface_drift`/`intent_drift`/`behavior_drift`/
`implementation_drift`, each partitioning a distinct aspect of the schema),
plus an `overall` aggregate — the mean of whichever components were
computed, a convenience rollup only; the individual numbers are the report,
never summed away as a substitute for them. Report-only: prints the report,
doesn't write into either file.

```bash
appgraph drift apps/todo/blueprint/backend.graph.yaml apps/kanban/blueprint/backend.graph.yaml --format json
```
```json
{
  "structural": 0.0582,
  "interface": 1.0,
  "intent": null,
  "behavior": 0.25,
  "implementation": 0.0,
  "overall": 0.3271
}
```

Four components are free graph-diffs, matched by node id (correct for this
codebase's actual use — comparing two versions of *the same* component,
which share a node-id convention, not general unlabeled graph isomorphism):

| Component | What changed | Metric |
|---|---|---|
| `structural` | Graph topology | Reach-weighted node/edge diff over `form.nodes`/`form.edges` — losing a foundational (high-`reach`) node costs more than losing a leaf |
| `interface` | Signatures/contracts | Jaccard distance over `function.exports`/`calls`/`emitters`/`listeners` |
| `behavior` | Tests/verifiers | Jaccard distance over the top-level `verification:` list |
| `implementation` | Dependency stack | Jaccard distance over each graph's `primitives` set (e.g. sqlite → postgres) |

The fifth, **`intent`**, needs `--llm ADAPTER:MODEL` — without it, `intent`
is absent from the report (`null` in the printed output). Intent here means
the free-text *rationale* for each node — not its technical spec, but how a
human actually explained the node: `defines`/`comment`/`spec.user_story`
**and** the node's `docs` field, which is where README-style prose lives
(`graph_lib.intent_text()` builds this text; see the node-kind legend in
Graph IDE's **ℹ About** modal — `doc`-kind nodes are exactly this). In a
vibe-coding sense, this is the closest thing the schema has to "the
prompt": humans express intent by writing prose, so that's what gets
compared. Rather than the schema doc's original "embedding distance"
(which would need a separate, hardcoded embeddings-API dependency this
repo otherwise has none of), it's scored by **LLM-as-judge**: the exact
model named by `--llm` reads both graphs' intent text
(`graph_lib.intent_drift()`, given a judge callable) and scores
meaning-drift directly (`appgraph/judge.py`: one dd-llm call with
`appgraph/prompts/intent_drift.md`, whose reply must be one number). A faithful paraphrase should score near 0; a contradicted
or missing rationale should score near 1.

```bash
appgraph drift apps/fief/blueprint/backend.graph.yaml apps/fief/blueprint/backend.graph.yaml \
  --llm claude_cli:claude-sonnet-5-5 --llm-timeout 300
```

Use `--dims` to restrict the report to specific components — comma-separated,
from `structural,interface,intent,behavior,implementation`. Dimensions not
selected are skipped entirely, not just hidden from the output: `--dims`
without `intent` means no LLM call happens even if `--llm` is also passed.

```bash
# only the two cheapest/most stable signals, no LLM call
appgraph drift a.graph.yaml b.graph.yaml --dims structural,implementation

# just intent, isolated from the graph-diff components
appgraph drift a.graph.yaml b.graph.yaml --dims intent --llm claude_cli:claude-sonnet-5-5
```

Use this once a `reverse`-provenance blueprint exists to compare against an
`authored` one — e.g. after mining a blueprint back out of `apps/todo`'s own
generated code via `appgraph extract --repo-path apps/todo/backend
--output-dir /tmp/todo-reversed --app-name todo_backend_reversed`, then
`appgraph drift apps/todo/blueprint/backend.graph.yaml
/tmp/todo-reversed/blueprint/component.graph.yaml`.

### `appgraph tools clean-port <port> [port ...]`

Kills whatever process is listening on the given port(s) — SIGTERM every
PID found via `lsof -t -i :PORT`, wait a second, SIGKILL anything still
alive. Handy after a `appgraph ide`/dev server that didn't exit cleanly.

```bash
appgraph tools clean-port 8880 8881
```

---

## `${{ settings.KEY }}` — app-scoped settings

Any `*.graph.yaml` under `apps/<app>/blueprint/` can reference
`${{ settings.KEY }}` (e.g. for a port number), resolved from an optional
sibling `apps/<app>/blueprint/settings.yaml`:

```yaml
# apps/todo/blueprint/settings.yaml
settings:
  - key: BACKEND_FASTAPI_PORT
    value: 8000
    comment: FastAPI backend port
```

```yaml
# apps/todo/blueprint/backend.graph.yaml
port: ${{ settings.BACKEND_FASTAPI_PORT }}
```

A token that's the *entire* string value resolves to the setting's own type
(so an int stays an int); embedded in a larger string, it's stringified. A
referenced key with no matching entry raises `ToolFailed` — never silently
passes the literal `${{ ... }}` through. Settings are per-app: two apps'
`settings.yaml` files never share a namespace. `appgraph new-app` scaffolds
this file automatically.

## Typical workflows

**Author a new app from scratch**: `appgraph new-app` → fill in the
`TODO:`s in each `blueprint/*.graph.yaml`, using `apps/todo/blueprint/` as a
worked example → `appgraph validate` until clean → `appgraph build
apps/<app>/blueprint/main.graph.yaml`.

**Reverse-engineer a blueprint from an existing repo**: `appgraph extract`
(AST-only first, to see what it finds in `analysis.json`/`EXTRACTION.md`) →
review/fill the `TODO:`s → optionally rerun with `--llm` for a first-draft
spec pass → `appgraph validate` → review before building with `appgraph
build`. See `apps/README-new-apps.md` for a real example (the `fief`
extraction).

**Browse or hand-edit any app's graph**: `appgraph ide`, pick the app,
click around. Turn on Edit for small prose fixes without opening a YAML
editor; drop back to the file directly for structural changes.

**Keep prose formatting consistent**: `appgraph prettify apps/ --write`
after a batch of manual edits, before committing.

## Troubleshooting

- **`appgraph: command not found`** — the install didn't put its console
  scripts on `PATH` (check `pip show -f app-graph | grep Location`), or
  you're in a different environment than the one you installed into. In a
  repo checkout doing dev work, make sure it was `pip install -e ".[dev]"`.
- **`extract --llm` stops with `semantic pass stopped: ...`** — a wrong
  adapter/model string, a provider error, or the `--max-llm-calls` cap.
  Fix the cause and rerun the same command: it resumes from the checkpoint
  (see Resumability). `semantic pass did not produce a valid blueprint:
  FAILED: ...` means a draft was still invalid after its repairs; the
  message is the validator's.
- **`build` ends `failed`** — the summary names the tests that failed and
  the log has every prompt and reply. **`refused`** — choose an output
  folder under your home. **`needs Docker`/image errors** — build the
  `appgraph-verify:py3.12` image (see Install).
- **A specific app doesn't show up in `appgraph ide`'s dropdown** — it
  needs at least one `*.graph.yaml` directly under
  `<app>/blueprint/` under whatever `--apps-root` is in effect (default
  `~/app-graph/ide`, or pass `--apps-root apps` for this repo's own
  examples). A generated-output-only directory (no `blueprint/`) is
  correctly excluded, not a bug.
- **`ToolFailed` on `appgraph validate`** — read the message; it's raised
  before any LLM call by design (the signal to abort generation rather than
  spend tokens on a broken graph), most commonly a cycle in `form_graph`
  (should never happen — mandatory edges are always a DAG) or a call
  contract mismatch. Running it against the system's `main.graph.yaml`
  gives more context than a single component when the failure is
  cross-component.
