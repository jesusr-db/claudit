import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import { QueryClientProvider, QueryClient } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import DashboardPage from "../DashboardPage";

// Mock the API hooks
vi.mock("@/shared/hooks/useApi", () => ({
  useSummary: () => ({
    data: {
      total_sessions: "3",
      total_users: "1",
      total_events: "111",
      total_prompts: "8",
      total_api_calls: "24",
      total_errors: "22",
      total_cost_usd: "0.44",
    },
    isLoading: false,
    error: null,
  }),
  useKpiBadges: () => ({
    data: {
      cache_hit_pct: "72.5",
      tool_success_rate: "95.0",
      avg_turnaround_sec: "12",
      cost_trend_direction: "down",
    },
    isLoading: false,
    error: null,
  }),
  useKpiCostTrend: () => ({
    data: { trend: [], days: 7 },
    isLoading: false,
    error: null,
  }),
}));

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <ChakraProvider>
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>{ui}</MemoryRouter>
      </QueryClientProvider>
    </ChakraProvider>
  );
}

describe("DashboardPage", () => {
  it("renders the dashboard heading", () => {
    renderWithProviders(<DashboardPage />);
    expect(screen.getByText("Analytics Dashboard")).toBeDefined();
  });

  it("renders summary cards with data", () => {
    renderWithProviders(<DashboardPage />);
    expect(screen.getByText("3")).toBeDefined(); // total_sessions
    expect(screen.getByText("$0.44")).toBeDefined(); // total_cost
  });

  it("renders KPI badges", () => {
    renderWithProviders(<DashboardPage />);
    expect(screen.getByText("72.5%")).toBeDefined(); // cache_hit_pct
    expect(screen.getByText("95.0%")).toBeDefined(); // tool_success_rate
  });
});
