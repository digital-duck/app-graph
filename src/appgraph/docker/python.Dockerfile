# The image a generated Python component's tests run in (recipes: build_component's `test` step; no network, read-only
# root, the project arrives as JSON on stdin and is written to /tmp). Every library a generated backend may import must be
# here, because the container has no network. Build it once (or `appgraph tools build-image`):
#   docker build -t appgraph-verify:py3.12 -f src/appgraph/docker/python.Dockerfile src/appgraph/docker
# The list is what graph-code's generated backends asked for in their requirements.txt (2026-11-22). Add to it and rebuild.
FROM python:3.12-slim
RUN pip install --no-cache-dir pytest httpx "fastapi[standard]" "uvicorn[standard]" sqlalchemy "pydantic[email]" \
        pyjwt bcrypt python-slugify passlib python-jose python-multipart aiosqlite pytest-asyncio
