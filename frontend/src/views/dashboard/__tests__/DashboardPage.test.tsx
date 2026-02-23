import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import { QueryClientProvider, QueryClient } from "@tanstack/react-query";
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
  useToolStats: () => ({
    data: {
      tools: [
        {
          tool_name: "Bash",
          call_count: "15",
          avg_duration_ms: "2100.5",
          success_count: "14",
          failure_count: "1",
          total_result_bytes: "15000",
        },
      ],
    },
    isLoading: false,
    error: null,
  }),
  useErrorStats: () => ({
    data: {
      errors: [
        {
          model: "claude-haiku-4-5-20251001",
          status_code: "404",
          error: "endpoint not found",
          error_count: "22",
          avg_duration_ms: "344.0",
        },
      ],
    },
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
      <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
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

  it("renders tool usage table", () => {
    renderWithProviders(<DashboardPage />);
    expect(screen.getByText("Bash")).toBeDefined();
    expect(screen.getByText("15")).toBeDefined(); // call_count
  });

  it("renders errors table", () => {
    renderWithProviders(<DashboardPage />);
    expect(screen.getByText("404")).toBeDefined();
  });
});
