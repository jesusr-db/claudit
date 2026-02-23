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
];
