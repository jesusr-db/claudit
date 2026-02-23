import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import { TimelineEventRow } from "../components/TimelineEvent";
import type { TimelineEvent } from "@/types/api";

function renderEvent(event: Partial<TimelineEvent>) {
  const defaults: TimelineEvent = {
    event_name: "user_prompt",
    timestamp: "2026-02-23T18:02:20.757Z",
    sequence: 1,
    session_id: "996a6297",
    prompt_id: null,
    user_id: null,
    tool_name: null,
    model: null,
    duration_ms: null,
    cost_usd: null,
    input_tokens: null,
    output_tokens: null,
    cache_read_tokens: null,
    cache_creation_tokens: null,
    error: null,
    status_code: null,
    success: null,
    decision: null,
    source: null,
    prompt: null,
    prompt_length: null,
    tool_result_size_bytes: null,
    speed: null,
    ...event,
  };
  return render(
    <ChakraProvider>
      <TimelineEventRow event={defaults} />
    </ChakraProvider>
  );
}

describe("TimelineEventRow", () => {
  it("renders user_prompt with prompt text", () => {
    renderEvent({
      event_name: "user_prompt",
      prompt: "review my config",
    });
    expect(screen.getByText(/review my config/)).toBeDefined();
    expect(screen.getByText(/USER_PROMPT/)).toBeDefined();
  });

  it("renders api_request with model and cost", () => {
    renderEvent({
      event_name: "api_request",
      model: "claude-opus-4-6",
      duration_ms: "7221",
      cost_usd: "0.039",
      input_tokens: "1",
      output_tokens: "470",
      cache_read_tokens: "47356",
    });
    expect(screen.getByText("claude-opus-4-6")).toBeDefined();
    expect(screen.getByText(/\$0.039/)).toBeDefined();
  });

  it("renders api_error with status and message", () => {
    renderEvent({
      event_name: "api_error",
      model: "claude-haiku-4-5",
      status_code: "404",
      error: "endpoint not found",
    });
    expect(screen.getByText(/404: endpoint not found/)).toBeDefined();
  });

  it("renders tool_result with success badge", () => {
    renderEvent({
      event_name: "tool_result",
      tool_name: "Bash",
      duration_ms: "2330",
      success: "true",
      tool_result_size_bytes: "1274",
    });
    expect(screen.getByText("Bash")).toBeDefined();
    expect(screen.getByText("success")).toBeDefined();
  });
});
