You are an expert software engineer. A component test suite failed. Repair the module below.

{{in_guide}}

Module to repair: {{in_node}}
Specification:
{{in_spec}}

Surrounding context (already-generated dependency files):
{{in_context}}

Test failure output:
{{in_test_failure}}

Common causes in this stack:
- Wrong HTTP verb (PATCH vs PUT, GET vs POST)
- Missing schema field (ToggleRequest, completed default, etc.)
- Re-defining something already declared in a dependency (e.g. get_db in main.py when it lives in database.py)
- Raising ValueError where the test expects HTTPException (or vice versa)
- Import path wrong (relative vs absolute, wrong module name)
- Missing Base.metadata.create_all(bind=engine) in main.py — causes OperationalError: no such table on every request;
  fix: import models, then call Base.metadata.create_all(bind=engine) before app = FastAPI()

CRITICAL: Output ONLY the corrected source code.
Do NOT use any tools. Do NOT call any functions. Do NOT read files. Do NOT explore the codebase.
No preamble, no explanation, no markdown fences. Just the raw corrected code.
