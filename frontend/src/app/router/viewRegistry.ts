import { lazy } from "react";

const DashboardPage = lazy(
  () => import("@/views/dashboard/DashboardPage")
);
const SessionsPage = lazy(
  () => import("@/views/sessions/SessionsPage")
);
const SessionDetailPage = lazy(
  () => import("@/views/sessions/SessionDetailPage")
);
const McpToolsPage = lazy(
  () => import("@/views/mcp-tools/McpToolsPage")
);
const McpServerDetailPage = lazy(
  () => import("@/views/mcp-tools/McpServerDetailPage")
);
const PlatformPage = lazy(
  () => import("@/views/platform/PlatformPage")
);
const McpServersPage = lazy(
  () => import("@/views/mcp-servers/McpServersPage")
);
const KpiHubPage = lazy(
  () => import("@/views/kpis/KpiHubPage")
);

export interface ViewEntry {
  id: string;
  path: string;
  component: React.LazyExoticComponent<React.ComponentType>;
  label?: string;
  nav: boolean;
}

export const viewRegistry: ViewEntry[] = [
  {
    id: "dashboard",
    path: "/dashboard",
    component: DashboardPage,
    label: "Dashboard",
    nav: true,
  },
  {
    id: "sessions",
    path: "/sessions",
    component: SessionsPage,
    label: "Sessions",
    nav: true,
  },
  {
    id: "session-detail",
    path: "/sessions/:id",
    component: SessionDetailPage,
    nav: false,
  },
  {
    id: "mcp-tools",
    path: "/mcp-tools",
    component: McpToolsPage,
    nav: false,
  },
  {
    id: "mcp-server-detail",
    path: "/mcp-tools/:server",
    component: McpServerDetailPage,
    nav: false,
  },
  {
    id: "mcp-servers",
    path: "/mcp-servers",
    component: McpServersPage,
    label: "MCP Servers",
    nav: true,
  },
  {
    id: "kpis",
    path: "/kpis",
    component: KpiHubPage,
    label: "KPIs",
    nav: true,
  },
  {
    id: "platform",
    path: "/platform",
    component: PlatformPage,
    label: "Platform",
    nav: true,
  },
];
