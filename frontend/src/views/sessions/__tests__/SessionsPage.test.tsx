import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import { QueryClientProvider, QueryClient } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import SessionsPage from "../SessionsPage";

vi.mock("@/shared/hooks/useApi", () => ({
  useSessions: () => ({
    data: {
      sessions: [
        {
          session_id: "996a6297-0787-454a-94b8-96191aa0a22c",
          user_id: "c35b69e8...",
          start_time: "2026-02-23T18:02:20Z",
          end_time: "2026-02-23T19:30:00Z",
          event_count: "111",
          prompt_count: "5",
          total_cost_usd: "0.44",
          tool_calls: "29",
          errors: "22",
        },
      ],
    },
    isLoading: false,
    error: null,
  }),
}));

function renderWithProviders(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <ChakraProvider>
      <QueryClientProvider client={qc}>
        <MemoryRouter>{ui}</MemoryRouter>
      </QueryClientProvider>
    </ChakraProvider>
  );
}

describe("SessionsPage", () => {
  it("renders sessions heading", () => {
    renderWithProviders(<SessionsPage />);
    expect(screen.getByText("Sessions")).toBeDefined();
  });

  it("renders session card with truncated id", () => {
    renderWithProviders(<SessionsPage />);
    expect(screen.getByText("996a6297...")).toBeDefined();
  });

  it("renders session stats", () => {
    renderWithProviders(<SessionsPage />);
    expect(screen.getByText("111")).toBeDefined();
    expect(screen.getByText("$0.44")).toBeDefined();
  });
});
