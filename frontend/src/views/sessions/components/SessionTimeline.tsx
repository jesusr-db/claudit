import { VStack, HStack, Button, Box, Text, Badge, Collapse } from "@chakra-ui/react";
import { useState, useMemo } from "react";
import type { TimelineEvent } from "@/types/api";
import { TimelineEventRow } from "./TimelineEvent";
import { PromptExecutionGraph } from "./PromptExecutionGraph";
import { formatTime } from "@/shared/utils/dates";

const FILTERS = [
  { label: "All", value: undefined },
  { label: "Prompts", value: ["user_prompt"] },
  { label: "API Calls", value: ["api_request"] },
  { label: "Tools", value: ["tool_decision", "tool_result"] },
  { label: "Errors", value: ["api_error"] },
] as const;

interface PromptGroup {
  promptId: string;
  firstEvent: TimelineEvent;
  events: TimelineEvent[];
  apiCalls: number;
  toolCalls: number;
  errors: number;
}

interface Props {
  events: TimelineEvent[];
  sessionId: string;
}

export function SessionTimeline({ events, sessionId }: Props) {
  const [filter, setFilter] = useState<string[] | undefined>(undefined);
  const [expandedPrompt, setExpandedPrompt] = useState<string | null>(null);

  const promptGroups = useMemo(() => {
    const groups = new Map<string, PromptGroup>();
    for (const e of events) {
      const pid = e.prompt_id;
      if (!pid) continue;
      if (!groups.has(pid)) {
        groups.set(pid, {
          promptId: pid,
          firstEvent: e,
          events: [],
          apiCalls: 0,
          toolCalls: 0,
          errors: 0,
        });
      }
      const g = groups.get(pid)!;
      g.events.push(e);
      if (e.event_name === "api_request") g.apiCalls++;
      if (e.event_name === "tool_result") g.toolCalls++;
      if (e.event_name === "api_error") g.errors++;
    }
    return Array.from(groups.values());
  }, [events]);

  const showPromptView = !filter || filter.includes("user_prompt");

  if (showPromptView && !filter) {
    return (
      <Box>
        <HStack spacing={2} mb={5}>
          {FILTERS.map((f) => {
            const isActive = JSON.stringify(filter) === JSON.stringify(f.value);
            return (
              <Button
                key={f.label}
                size="sm"
                variant={isActive ? "solid" : "softOutline"}
                onClick={() => setFilter(f.value as string[] | undefined)}
              >
                {f.label}
              </Button>
            );
          })}
        </HStack>
        <VStack spacing={2} align="stretch">
          {promptGroups.map((g) => {
            const isExpanded = expandedPrompt === g.promptId;
            const promptEvent = g.events.find((e) => e.event_name === "user_prompt");
            const ts = formatTime(g.firstEvent.timestamp);

            return (
              <Box key={g.promptId}>
                <Box
                  border="1px solid"
                  borderColor={isExpanded ? "brand.300" : "soft.border"}
                  borderRadius="soft"
                  p={3}
                  cursor="pointer"
                  bg={isExpanded ? "brand.50" : "surface.card"}
                  boxShadow={isExpanded ? "soft-md" : "soft"}
                  _hover={{
                    borderColor: "brand.300",
                    bg: isExpanded ? "brand.50" : "soft.hover",
                    boxShadow: "soft-hover",
                  }}
                  transition="all 0.2s ease"
                  onClick={() =>
                    setExpandedPrompt(isExpanded ? null : g.promptId)
                  }
                >
                  <HStack spacing={3}>
                    <Text fontSize="xs" color="gray.400" fontFamily="mono">
                      {ts}
                    </Text>
                    <Badge colorScheme="teal" variant="subtle" fontSize="xs">
                      PROMPT
                    </Badge>
                    <Badge variant="subtle" colorScheme="gray" fontSize="xs">
                      {g.events.length} events
                    </Badge>
                    {g.apiCalls > 0 && (
                      <Badge variant="subtle" colorScheme="blue" fontSize="xs">
                        {g.apiCalls} API
                      </Badge>
                    )}
                    {g.toolCalls > 0 && (
                      <Badge variant="subtle" colorScheme="green" fontSize="xs">
                        {g.toolCalls} tools
                      </Badge>
                    )}
                    {g.errors > 0 && (
                      <Badge colorScheme="red" variant="subtle" fontSize="xs">
                        {g.errors} errors
                      </Badge>
                    )}
                    <Text fontSize="xs" color="gray.400">
                      {isExpanded ? "▼" : "▶"}
                    </Text>
                  </HStack>
                  {promptEvent?.prompt && (
                    <Text
                      mt={1}
                      fontSize="sm"
                      color="gray.600"
                      noOfLines={isExpanded ? undefined : 1}
                      pl="70px"
                    >
                      &quot;{promptEvent.prompt}&quot;
                    </Text>
                  )}
                </Box>
                <Collapse in={isExpanded} animateOpacity>
                  <Box mt={2} ml={4}>
                    <PromptExecutionGraph
                      sessionId={sessionId}
                      promptId={g.promptId}
                    />
                  </Box>
                </Collapse>
              </Box>
            );
          })}
        </VStack>
      </Box>
    );
  }

  const filtered = filter
    ? events.filter((e) => filter.includes(e.event_name))
    : events;

  return (
    <Box>
      <HStack spacing={2} mb={5}>
        {FILTERS.map((f) => {
          const isActive = JSON.stringify(filter) === JSON.stringify(f.value);
          return (
            <Button
              key={f.label}
              size="sm"
              variant={isActive ? "solid" : "softOutline"}
              onClick={() => setFilter(f.value as string[] | undefined)}
            >
              {f.label}
            </Button>
          );
        })}
      </HStack>
      <VStack spacing={1} align="stretch">
        {filtered.map((e) => (
          <TimelineEventRow key={`${e.sequence}`} event={e} />
        ))}
      </VStack>
    </Box>
  );
}
