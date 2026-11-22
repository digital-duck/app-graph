Based on the spec and what I can derive from the repository structure and acceptance tests, I have enough information to write the README. Let me write it now.
<function_calls>
<invoke name="Write">
<parameter name="file_path">/home/gongai/projects/digital-duck/graph-code/apps/conduit/README.md</parameter>
<parameter name="file_content"># Conduit

A full-stack implementation of the [RealWorld](https://realworld-docs.netlify.app/) Conduit spec: a Medium-style social publishing platform with JWT-based authentication, user profiles with follow/unfollow, articles with tag filtering, per-article favorites and comment threads, and a personalized feed of articles from followed authors.

## Status

Acceptance tests from the most recent integration run:

| Test | Result | Time |
|---|---|---|
| register\_and\_login | PASS | 13.0s |
| browse\_articles | PASS | 12.2s |
| filter\_by\_tag | **FAIL** | — |
| create\_and\_view\_article | **FAIL** | — |
| favorite\_article | PASS | 19.3s |
| comment\_on\_article | **FAIL** | — |
| follow\_and\_feed | PASS | 20.6s |

Failure details:

- **filter\_by\_tag**: `POST /articles` returns `307` (redirect) instead of `200`/`201` when creating an article under a tag.
- **create\_and\_view\_article**: `POST /articles` returns `401 Authentication required` despite a valid JWT being present.
- **comment\_on\_article**: User registration endpoint returns `404 Not Found`.

## Architecture

The Vue.js frontend (`:5178`) communicates with the FastAPI backend (`:8007`) over a REST API with CORS enabled and JWT bearer-token authentication; see [backend/README.md](backend/README.md) and [frontend/README.md](frontend/README.md) for each component's own setup, run, and test instructions.

## Running the full system

**Build** (generates backend and frontend source from the graph):

```bash
spl3 run spl/build_app.spl apps/conduit/blueprint/frontend.graph.yaml --output_dir apps/conduit
```

**Start the backend** (from `apps/conduit/backend/`):

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8007 --reload
```

**Start the frontend** (from `apps/conduit/frontend/`):

```bash
npm install
npm run dev
```

The app is then available at `http://localhost:5178`.

## Applications

- **backend** — FastAPI REST API implementing the RealWorld Conduit spec: user registration/login, JWT issuance, profile management with follow/unfollow, article CRUD with slug-based addressing, tag index, per-article favorites and comment threads, and a followed-authors feed. Runs on port `8007`.
- **frontend** — Vue.js single-page application: global article feed, tag-filtered browsing, article detail with comments, auth forms (register/login), user profile pages, and article authoring. Runs on port `5178`.
</parameter>
</invoke>
</function_calls>

README written to `apps/conduit/README.md`. It includes the title and description, a Status section with the acceptance-test results verbatim (pass/fail per test with failure details), the Architecture section linking to each component's own README, the full-system run instructions, and the Applications section describing both the backend and frontend.