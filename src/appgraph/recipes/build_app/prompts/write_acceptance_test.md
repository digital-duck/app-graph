You are an expert software engineer writing an HTTP-level acceptance test.

Write a self-contained Python script (stdlib `urllib.request`/`json` only — no
`requests`, no `pytest`, no imports beyond the standard library) for the
application: {{in_application}}

Start with this exact `request()` helper, unmodified — several endpoints in
this API return `204 No Content` (an empty body) on success, and calling
`json.loads()` on an empty body raises `json.decoder.JSONDecodeError`, which
several previously-generated acceptance tests got wrong:

```python
import json
import urllib.error
import urllib.request

def request(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{{BASE}}{{path}}", data=data, method=method,
        headers={{"Content-Type": "application/json"}} if data else {{}},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
            return resp.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raw = e.read()
        return e.code, json.loads(raw) if raw else None
```

Specification:
{{in_spec}}

Live backend endpoints available to call directly:
{{in_endpoints}}

The script must:
1. Exercise the exact user story in the spec by making real HTTP requests
   against the live backend base URL given above
2. Assert every condition in the contract (status codes, response shape,
   values) using plain `assert` statements with descriptive messages. When
   the spec/endpoints text states an explicit status code for an operation
   (e.g. `status_code=201`, "-> 201 + slug"), assert that EXACT code — do
   NOT default to assuming 200 for a POST/create just because it is the most
   common REST convention; many contracts in this API intentionally return
   201 on creation.
3. Clean up any data it creates (e.g. DELETE what it POSTed) so the script is
   safe to re-run against the same live server
4. Cover the primary edge case mentioned in the spec (e.g. empty input,
   unknown id, empty-list state) as a second assertion block. For an
   "unknown id" case: use a syntactically valid id of the correct type that
   simply does not exist (e.g. a large integer like 999999 if ids are
   integers) — a wrong-typed id (a string where the route expects an int)
   gets rejected by FastAPI's own path-param validation as 422 before the
   route's own not-found logic ever runs, testing request validation
   instead of the 404 behavior the spec actually describes.
5. Use the EXACT path shown in the spec/endpoints above, including trailing
   slashes — e.g. if the contract says `POST /api/v1/items/`, request
   `/api/v1/items/`, not `/api/v1/items`. A missing trailing slash on a
   POST/PUT/DELETE triggers FastAPI's redirect_slashes 307 response, which
   the `request()` helper above does NOT follow (urllib does not reliably
   re-send a POST body across a redirect), so the test sees status 307
   instead of the real response and fails on an assertion that has nothing
   to do with the actual bug.
6. Match field names EXACTLY as declared in the spec/endpoints above, including
   case — do NOT convert a snake_case field (e.g. `recipe_category`,
   `recipe_ingredient`) to camelCase, and do NOT invent, rename, or drop a
   field. If the spec is ambiguous about a field's exact name, look it up in
   the endpoints text above rather than guessing a JS-style convention.
7. When a field's type is a nested object or a list of nested objects that
   the API itself returned earlier (e.g. a tag/category/item fetched or
   created via a prior request in this same script), reuse that FULL object
   exactly as returned — do NOT construct a new partial object with only
   some of its fields (e.g. `{{"name": "x"}}` when the real object also has a
   required `id`/`slug`). Building request bodies for update/PUT calls,
   include every field the corresponding GET response has, not just the
   ones you intend to change.
8. On success, print "PASS" and exit 0. On any AssertionError, let it
   propagate (non-zero exit) — do not catch and swallow it.

Output only the Python script. No preamble, no markdown fences.
