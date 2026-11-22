from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import build, drift, graphs, settings

app = FastAPI(title="graph-ide API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(graphs.router)
app.include_router(settings.router)
app.include_router(build.router)
app.include_router(drift.router)
