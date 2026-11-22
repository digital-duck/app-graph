You are classifying the *shape* of an existing application, extracted from a
real repository by a static-analysis pass, before it gets decomposed into a
blueprint graph.yaml (or set of graph.yaml files).

Static analysis of the repo (routes/schemas/ORM models/services/Vue
components/API functions found):
{{in_analysis_json}}

Representative source file contents (a sample, not the whole repo):
{{in_source_context}}

Decide which of these three shapes best fits what you saw:

- INTEGRATED — a real HTTP backend AND a separate frontend that calls it
  over that HTTP API (e.g. FastAPI + Vue, Express + React). Two genuinely
  separate deployable processes with a client/server boundary between them.
- SINGLE — one process, one deployable component: a backend-only
  service/library with no separate frontend, a CLI tool, a static HTML page
  with no backend, or a single-process app with no client/server REST split
  at all (e.g. a Streamlit app, a Jupyter-notebook-driven tool). Do NOT
  force this into INTEGRATED just because the codebase happens to contain
  both Python and HTML/JS files — the test is whether there are two
  separately-running processes talking over HTTP, not which languages
  appear.
- NO_FIT — the analysis above is too thin or ambiguous to confidently
  classify either way (e.g. almost nothing was found by the static pass, or
  the source samples contradict the analysis).

Also name the best-fitting tech_profile for the code you actually saw,
choosing from EXACTLY this list if one genuinely fits: python_fastapi,
vue_typescript, python_library, curriculum. If none of these fit the actual
language/framework you observed, propose a new short snake_case profile
name instead (e.g. streamlit_app, static_html, express_typescript) — do not
force a bad fit just to reuse an existing name.

Output EXACTLY two lines, nothing else, no preamble, no commentary:
SHAPE: <INTEGRATED|SINGLE|NO_FIT>
PROFILE: <existing_profile_name_or_a_new_proposed_name>
