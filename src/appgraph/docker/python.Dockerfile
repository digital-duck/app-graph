# The image a generated Python component's tests run in (build_component's `run` step; build_app's `integrate` step: no network, read-only root, no
# folder mounted; the project arrives as JSON on stdin and is written to /tmp). Every library a generated backend may
# import must be here, because the container has no network. Build it once, from the repository root:
#   docker build -t appgraph-verify:py3.12 -f src/appgraph/docker/python.Dockerfile src/appgraph/docker
# The libraries are what graph-code's generated backends list in their requirements.txt (2026-11-22). Add yours and rebuild.
FROM python:3.12-slim
RUN pip install --no-cache-dir pytest httpx "fastapi[standard]" "uvicorn[standard]" sqlalchemy "pydantic[email]" \
        pyjwt bcrypt python-slugify passlib python-jose python-multipart aiosqlite pytest-asyncio
COPY run_tests.py /usr/local/bin/appgraph-run-tests
COPY integrate.py /usr/local/bin/appgraph-integrate
