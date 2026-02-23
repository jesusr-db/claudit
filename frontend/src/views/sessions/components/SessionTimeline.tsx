import { VStack, HStack, Button, Box } from "@chakra-ui/react";
import { useState } from "react";
import type { TimelineEvent } from "@/types/api";
import { TimelineEventRow } from "./TimelineEvent";

const FILTERS = [
  { label: "All", value: undefined },
  { label: "Prompts", value: ["user_prompt"] },
  { label: "API Calls", value: ["api_request"] },
  { label: "Tools", value: ["tool_decision", "tool_result"] },
  { label: "Errors", value: ["api_error"] },
] as const;

interface Props {
  events: TimelineEvent[];
}

export function SessionTimeline({ events }: Props) {
  const [filter, setFilter] = useState<string[] | undefined>(undefined);

  const filtered = filter
    ? events.filter((e) => filter.includes(e.event_name))
    : events;

  return (
    <Box>
      <HStack spacing={2} mb={4}>
        {FILTERS.map((f) => (
          <Button
            key={f.label}
            size="sm"
            variant={
              JSON.stringify(filter) === JSON.stringify(f.value)
                ? "solid"
                : "outline"
            }
            onClick={() => setFilter(f.value as string[] | undefined)}
          >
            {f.label}
          </Button>
        ))}
      </HStack>
      <VStack spacing={1} align="stretch">
        {filtered.map((e) => (
          <TimelineEventRow key={`${e.sequence}`} event={e} />
        ))}
      </VStack>
    </Box>
  );
}
