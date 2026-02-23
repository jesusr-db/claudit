import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import App from "../App";

vi.mock("@/views/dashboard/DashboardPage", () => ({
  default: () => <div>DashboardPage</div>,
}));
vi.mock("@/views/sessions/SessionsPage", () => ({
  default: () => <div>SessionsPage</div>,
}));
vi.mock("@/views/sessions/SessionDetailPage", () => ({
  default: () => <div>SessionDetailPage</div>,
}));

describe("App", () => {
  it("renders without crashing", () => {
    render(<App />);
    expect(document.querySelector("body")).toBeDefined();
  });

  it("redirects / to /dashboard", async () => {
    render(<App />);
    expect(await screen.findByText("DashboardPage")).toBeDefined();
  });
});
