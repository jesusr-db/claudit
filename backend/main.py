from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from backend.routers import metrics_router, sessions_router, mcp_tools_router, platform_router, mcp_servers_router, kpis_router
from backend.executors import get_pg_executor

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
app.include_router(mcp_tools_router)
app.include_router(platform_router)
app.include_router(mcp_servers_router)
app.include_router(kpis_router)


@app.get("/health")
async def health_check():
    try:
        pg = get_pg_executor()
        pg.execute("SELECT 1")
        pg_status = "connected"
    except Exception as e:
        pg_status = f"error: {e}"
    return {"status": "healthy", "lakebase": pg_status}


@app.on_event("shutdown")
async def shutdown():
    try:
        from backend.executors import _pg_executor
        if _pg_executor is not None:
            _pg_executor.close()
    except Exception:
        pass


# Serve frontend static files in production
frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="static")
