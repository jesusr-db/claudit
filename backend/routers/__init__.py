from backend.routers.metrics import router as metrics_router
from backend.routers.sessions import router as sessions_router
from backend.routers.mcp_tools import router as mcp_tools_router
from backend.routers.platform import router as platform_router
from backend.routers.mcp_servers import router as mcp_servers_router
from backend.routers.kpis import router as kpis_router
from backend.routers.introspection import router as introspection_router

__all__ = ["metrics_router", "sessions_router", "mcp_tools_router", "platform_router", "mcp_servers_router", "kpis_router", "introspection_router"]
