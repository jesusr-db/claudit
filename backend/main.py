from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import os
import logging

from backend.routers import metrics_router, sessions_router

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Claudit Observability",
    description="Claude Code Observability Dashboard API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(metrics_router)
app.include_router(sessions_router)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# Serve static files in production
# Try multiple paths where frontend dist might be
_candidates = [
    os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"),
    os.path.join(os.getcwd(), "frontend", "dist"),
    "/app/frontend/dist",
]

frontend_dist = None
for path in _candidates:
    resolved = os.path.realpath(path)
    exists = os.path.exists(resolved)
    print(f"[CLAUDIT] Checking frontend dist at: {resolved} exists={exists}", flush=True)
    if exists:
        frontend_dist = resolved
        break

if frontend_dist:
    print(f"[CLAUDIT] Mounting static files from: {frontend_dist}", flush=True)
    print(f"[CLAUDIT] Contents: {os.listdir(frontend_dist)}", flush=True)
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="static")
else:
    print(f"[CLAUDIT] No frontend dist found. CWD={os.getcwd()}, __file__={__file__}", flush=True)
    try:
        print(f"[CLAUDIT] CWD contents: {os.listdir(os.getcwd())}", flush=True)
        fe_path = os.path.join(os.getcwd(), "frontend")
        if os.path.exists(fe_path):
            print(f"[CLAUDIT] frontend/ contents: {os.listdir(fe_path)}", flush=True)
    except Exception as e:
        print(f"[CLAUDIT] Error listing dirs: {e}", flush=True)

    @app.get("/")
    async def root():
        return HTMLResponse(
            "<h1>Claudit</h1><p>Frontend not found. API available at /health, /api/v1/metrics/*, /api/v1/sessions/*</p>"
        )
