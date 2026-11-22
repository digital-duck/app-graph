# Lessons Learned — graph-code Framework

A self-reflection on building graph-code so far: what's working, what's fragile, and
what the pattern of real bugs found across ~15 app builds (per `apps/README.md`) plus
today's 2026-08-14 framework refactor (`refactoring-plan-v1.md`) says about where the
framework's actual risk lives. Written because the vision — one graph schema and one
build pipeline producing both curriculum prose (ConceptBook) and working software
(SPL apps) — is holding up in practice, and it's worth being precise about *why* it
holds up and *where* it still needs real vigilance, not blind trust.

---

## The good

**One schema, two genuinely different output kinds, same pipeline shape.**
`classical_mechanics` (curriculum: Markdown lesson prose) and `todo`/`dispatch`/
`expense`/... (software: FastAPI/Vue code) go through the same `load_domain()` →
`validate_full()` → `build_component.spl` → cache/verify/repair loop, differing only
in `tech_profile`. That's the core "unified" claim this project is built on, and it's
not just true on paper — both kinds have been built for real, tested, and produced
usable output. `physics_simulator` (`reactive_app`, event-driven) and `etl_workflow`
(`workflow`, action-routed transitions with a retry loop) extend this further —
four distinct `domain_type`s, one framework.

**Pre-LLM validation catches real structural errors for free.** `validate_full()`
(`acyclic()`, Two-Radical check, `validate_events()`, `check_call_contracts()`,
`validate_transitions()`) runs before any LLM call and has repeatedly caught real
authoring mistakes at zero cost — e.g. mealie's 11 frontend↔backend call contracts
were confirmed structurally correct before a single token was spent generating code.
`ToolFailed` raised before generation, not after, is the right place for this gate.

**The disk-backed cache + node/edge-level `use_cache` genuinely work as designed.**
Verified directly this session (§3 of `refactoring-plan-v1.md`): a node with its own
`use_cache: false` misses independent of its siblings; a node whose only *incoming
edge* is marked `use_cache: false` also correctly misses; everything else hits. This
is real, working fine-grained control — force one broken node to regenerate without
discarding an entire component's cache.

**The settings.yaml / config-module mechanism closes a real gap end-to-end.**
Interpolating `${{ settings.KEY }}` into the graph.yaml alone would not have been
enough (the LLM still bakes literal values into generated code) — the
`write_settings_config` → `app/config.py`/`src/config.ts` deterministic-templating
step, with node specs told to *import* from it, was verified today to actually let a
settings change propagate without any LLM regeneration. This is the kind of fix that
only became obvious by trying the naive version first and watching it fail to satisfy
the actual requirement ("change one key, no re-generation needed").

**The 3-attempt repair loop works — when it's pointed at the right file.** Once
`identify_broken_node()` was fixed (see below), the exact same repair mechanism that
had been silently editing the wrong file three times in a row worked correctly on the
first real retry. The mechanism itself was never the problem.

**Today's todo-app rebuild is proof the pipeline is sound when specs are precise
enough.** After eight real fixes (below), a completely fresh `spl3 run
spl/build_app.spl` — backend, frontend, system integration — passed clean in one run.
Nothing about that success was luck; every fix closed a specific, previously
demonstrated failure mode.

---

## The bad — and why it's productive, not discouraging

Eight real bugs surfaced during today's single todo-app rebuild cycle (see
`refactoring-plan-v1.md` §2.3/§2.4 for the full detail on each). None of them were
novel in *kind* — `apps/README.md` already documents the same handful of root causes
recurring across mealie, physics_simulator, etl_workflow, dispatch, fastapi, and
kanban builds going back to 2026-08-13. That repetition is itself the finding: this
isn't "todo had bad luck," it's "the framework has a small number of systemic soft
spots that show up in almost every app unless specifically guarded against."

### 1. Prose and structural metadata are invisible to the LLM — only `spec:` is real

`spl/tools.py::_fmt_spec()` formats *only* the node's `spec:` dict
(`interface`/`contract`/etc.) into the code-generation prompt. Nothing else on a node
— not `defines:`, not `ports:`, not `comment:` — reaches the LLM at all. This caused
two distinct, independent bugs today:

- `db_connection`'s `defines: "...bound to todos.db"` was never enforced — the
  generated `database.py` used the generic literal `sqlite:///./app.db` instead. This
  is almost certainly also the origin of the stray root-level `app.db` this session
  cleaned out of the repo.
- `api_client`'s `ports:` block correctly declared `PUT /todos/{id}`, but `ports:` is
  orchestration/contract-checking metadata, never part of `spec:` — the generated
  `toggleTodo` used `PATCH` instead, which would 405 against the real backend.

**The lesson generalizes past todo:** any fact that matters for correct code
generation has to live in `spec.interface`/`spec.contract`, restated explicitly, even
if it's "obviously" implied elsewhere in the node. Treat `defines:`/`ports:`/`comment:`
as documentation for humans and `check_call_contracts()`, never as instructions the
generator will see.

### 2. LLMs override even explicit, correct specs with training-prior convention

The most surprising bug: `crud_operations`' `spec.interface` said `-> Todo` four
separate times and never mentioned any other name — yet the generated `crud.py`
consistently used `TodoRead` everywhere, a very common FastAPI Create/Read naming
convention from the model's training data overriding an explicit, unambiguous,
repeated instruction. This means "the spec already says the right name" is not
sufficient on its own — specs for anything with a plausible "more idiomatic"
alternative need a defensive negative statement too ("there is no class named X, do
not invent one"), not just a positive example.

### 3. Node ids are part of the prompt surface, not just internal bookkeeping

Two variants of the same leak this session: `crud.py` got gratuitous module-level
aliases (`orm_model = TodoModel`, `data_schema = Todo`) and `TodoList.vue` got a
stray `<!-- item_component -->` comment — both are literal `composed_of`
dependency-list node ids bleeding into generated identifiers/comments. Fixed at the
right level (a general "never use a graph node id as a generated identifier" rule
added to all three `tech_profiles.py` style guides) rather than patched per node,
since the pattern is clearly systemic, not todo-specific.

This connects to a second, sharper finding from the de-prefixing work itself:
**renaming a node id is not a free refactor — the id is effectively part of the
prompt.** `todo_schema` → `db_schema` introduced a brand-new hallucination (a
spurious `ForeignKey` to a table matching the node's own name) that had never
happened under the old app-prefixed convention, and `sqlite_schema` (briefly
considered) would have been worse still — it collides with SQLite's own reserved
`sqlite_schema`/`sqlite_master` alias. A generic, de-prefixed node id has to be
sanity-checked against "could an LLM read this as an entity, a table, or a reserved
word," not just checked for collision-freedom against other node ids.

### 4. The repair loop can silently repair the wrong file

`identify_broken_node()` matched failing tests via a hardcoded table of `test_X.py`
filename substrings. A collection-time `ImportError` raised while loading
`conftest.py` — before any individual test file even runs — contains no such
substring, so the table never matched, and all 3 repair attempts silently fell back
to editing the *capstone* (`api_routes` → `app/main.py`) instead of the actually
broken node (`orm_model` → `app/models.py`). The logs gave no hint of this — "3 repair
attempts, still failing" looked identical whether or not the repair loop was even
touching the right file. This was only caught by reading the generated code by hand
and reasoning backward from the traceback. Fixed generically: scan the traceback for
any of `NODE_FILES[app_name]`'s known source paths and prefer the last match (the
actually-broken file, since an import chain lists the innocent importer before the
broken importee) — this is framework-wide, not todo-specific, and every app's repair
loop benefits immediately.

### 5. A passing build is not the same as a correct app

The PATCH/PUT bug passed `pytest`, passed `vitest`, and passed
`integrate_system.spl`'s acceptance suite — because none of those layers actually
drive the frontend against the real backend (`integrate_system.spl`'s own header
comment documents this scope decision explicitly: HTTP-level tests against the live
backend only, no browser automation). Every automated gate that exists today is
scoped correctly for what it checks, but the union of those gates still has a real
gap: nothing in the current pipeline exercises an actual frontend→backend round trip.
Reading the generated output — and eventually, clicking through the real app in a
browser — remains necessary after a "successful" build, not optional.

### 6. Each bug costs a full real build cycle to surface

There is currently no lighter-weight way to test whether a spec wording change closes
a hallucination before spending a real `spl3` run (LLM latency + cost) to find out.
Today's cycle was fix → clear cache → rebuild → read output → repeat, eight times.
Cheap and correct for a single app during active debugging; would not scale well as
the primary QA method across a dozen apps. Worth exploring later: a way to preview
what a spec produces without a full pipeline run, or at least a checklist derived from
§1–3 above that a spec gets run against *before* the first real build, not after the
first failure.

---

## A checklist, distilled from all of the above

Worth applying to every node being authored or migrated (see
`refactoring-plan-v1.md` §2.5 for the apps still ahead):

1. Any literal filename, class name, HTTP method, or symbol name the generated code
   must match — restate it explicitly in `spec.interface`/`spec.contract`, never rely
   on `defines:`/`ports:`/`comment:` alone.
2. For any name with a plausible "more idiomatic" alternative (Read/Out/Response/DTO
   variants, PATCH-vs-PUT, etc.) — add the negative statement too: "there is no X,
   do not invent one."
3. For any ORM/table-shaped node — state the exact, exhaustive column/field list and
   explicitly rule out inferred `ForeignKey`/`relationship()` from `composed_of`
   dependencies.
4. Before choosing a de-prefixed node id, ask whether an LLM generating code from it
   could plausibly read it as an entity, a table, or a language/database reserved
   word — not just whether it collides with another node id.
5. After a build passes, still read the generated files — a green test suite is not
   proof of correctness, only proof of what the existing tests happen to check.

---

## Is this actually more productive? An honest estimate

No stopwatch, no controlled study — this is a judgment call from watching the actual
editing/debugging cycles across ~15 app builds plus today's refactor propagation
across `todo`/`expense`/`kanban`/`dispatch`/`fastapi`/`fullstack`/`conduit`, cross-
checked against the real bug counts `apps/README.md` logs per app. Worth revisiting
once there's real wall-clock data from a fresh app family built by someone who wasn't
also building the framework at the same time.

**Where it does *not* save time: the first app in a family.** Writing `todo`'s three
`graph.yaml` files precisely enough to survive a real build cost eight real bug-fix
cycles (§"The bad" above) — spec-authoring plus LLM-fidelity debugging is a real skill
with a real learning curve, and a competent engineer could plausibly have hand-written
the same CRUD app faster than that iteration took. Nothing about the framework makes
the *first* generation of a genuinely novel pattern cheap. If the goal were "build one
app once," this would be a wash at best.

**Where it demonstrably compounds: every app after the first, and every cross-cutting
change.** This is the actual lever, and today's session is direct evidence of it, not
a projection. Once `todo`'s eight bugs closed a specific set of hallucination classes —
by policy, in `tech_profiles.py`'s shared style guides and in the node-naming
convention, not by a one-off patch — propagating the same convention change (app-scoped
`settings.yaml`, de-prefixed `data_schema`/`orm_model` node ids, the CORS-hardcode fix,
the `verify_edges()` `dep_symbols` merge) across `dispatch`, `fastapi`, `fullstack`, and
`conduit` took no new LLM debugging cycles at all: deterministic YAML edits, `pytest`
(85/85 every time), done. `conduit`'s two-ORM/two-CRUD shape needed one genuinely new
addition (dedicated `dep_symbols` entries, since it didn't fit the shared-node-id
pattern) — found by reasoning about the schema, not by a failed build. Compare that to
what the same convention change would cost against seven already-hand-written codebases:
touching N call sites × M apps by hand, re-testing each one, with no guarantee every
site was found. `expense`→`dispatch`'s bug count also visibly declines relative to
`todo`'s eight (three real bugs, mostly domain-specific — a `Decimal` serialization
gap, a fabricated acceptance-test shape) once the systemic classes were already closed,
though this isn't a clean monotonic trend — `mealie`, the largest app, still surfaced
seven bugs proportional to its own genuinely new structural surface (many-to-many
relationships, pagination) that nothing before it had exercised. The gain is per
*pattern*, not per *app number*: a new structural shape still costs real debugging the
first time it appears, but every app reusing an already-hardened pattern is nearly free.

**The real lever isn't "generates code faster than typing it."** It's that the graph
spec is the single source of truth for a requirement, so a requirement change is an
edit in one place instead of a hand-audit of every file it happened to touch. A port
renumbering, a naming convention, a defensive-guard rule — each of those turned an
`O(apps × files)` manual chore into `O(1)` policy edit + `O(apps)` mechanical
regeneration/re-validation. That shift is the actual productivity claim, and it's the
one part of this session that was measured directly rather than estimated: seven apps,
one convention change each, zero new debugging.

**A rough, explicitly-unmeasured multiplier**, for calibration only: first app in a new
structural family — call it break-even to maybe 1.5–2x *slower* than hand-coding, given
the spec-authoring and LLM-fidelity overhead. An app reusing an already-hardened
tech-profile and naming convention — very roughly 5–10x faster, since it's near-zero-
debugging YAML authoring plus one unattended build run. A cross-cutting change touching
every existing app — this is where the multiplier is largest and least apples-to-apples
against manual work, because the manual alternative doesn't just take longer, it
routinely misses call sites a systematic policy edit + revalidation doesn't.

**Does ingesting more apps make the *next new* app easier? Partly true today, partly
still a promise.** Two different effects hide under this one claim, and they're at very
different levels of maturity:

- *Pattern-library reuse — already real, already demonstrated.* Every app migrated
  this session got authored with defensive guards written proactively, not reactively,
  because the pattern was already known: `expense`'s FK-hallucination guard and
  exact-import-name guards were written into its very first draft, before any build
  failure, by transplanting the fix `todo` needed only after it broke. The node-naming
  vocabulary itself (`data_schema`, `orm_model`, `crud_operations`, `api_routes`) is
  now a settled default a new app just adopts instead of re-litigating; the framework-
  wide "never use a node id as a generated identifier" rule in `tech_profiles.py`
  protects every future app the moment it's written, not just the one that surfaced
  it. This part of the claim is not aspirational — it's the same compounding effect
  from the section above, just applied to *authoring* a new app instead of *migrating*
  an existing one.
- *Component reuse across apps — aspirational, and today's evidence cuts against it
  happening automatically.* The deeper version of this claim is that a new app could
  *import* a previously-built component (an auth library, a CRUD primitive) instead of
  re-specifying it. `apps/jwt_provider/` exists specifically to test this, and the
  result so far is a real counter-data-point: both `fullstack` and `conduit` — the two
  apps that most needed a JWT+bcrypt auth layer — independently built their own
  self-contained `security_module` rather than importing `jwt_provider`, each with a
  different JWT payload key convention (`sub` vs `username`) and a different token
  lifetime. `fullstack`'s own blueprint comment says this reuse comparison is
  deliberately deferred to "a later refactor once both shapes have been built and
  compared for real" — which as of this session still hasn't happened. So: a registry
  of *specified conventions and guard-rails* compounds for free, right now. A registry
  of *importable, composable components* is the more valuable version of this claim and
  is architecturally supported (`imports:`, `function.exports`/`function.calls`,
  `check_call_contracts()`), but hasn't yet been exercised for real reuse — the honest
  status is "designed for, not yet proven."

---

## Where this leaves the "book + app" vision

The framework-shape risk is close to zero at this point — four domain types built for
real, graph-of-graphs composition working, curriculum and software sharing one
pipeline. The actual risk to the vision is prompt-fidelity, and it applies exactly as
much to curriculum generation as to code generation: `classical_mechanics`'s own build
needed a generic `_strip_fences()` fix for the same underlying class of problem (a
generation artifact — a leaked non-content fragment — silently corrupting what should
have been final output). An LLM given a graph node will fill any spec gap with
whatever is most statistically common for that domain, whether or not that's what the
author meant, whether the node produces Python or Markdown. The fix is the same in
both cases: specs precise enough to leave nothing that matters unstated, and always
reading the actual output before trusting it.
