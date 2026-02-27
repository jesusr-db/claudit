import { Box, HStack, Text, Badge, VStack } from "@chakra-ui/react";
import type { TimelineEvent as TEvent } from "@/types/api";

const EVENT_COLORS: Record<string, string> = {
  user_prompt: "teal",
  api_request: "green",
  api_error: "red",
  tool_decision: "blue",
  tool_result: "cyan",
};

const EVENT_ICONS: Record<string, string> = {
  user_prompt: ">>>",
  api_request: "\u25CB",
  api_error: "\u26A0",
  tool_decision: "\u25C6",
  tool_result: "\u25C6",
};

interface Props {
  event: TEvent;
}

export function TimelineEventRow({ event }: Props) {
  const color = EVENT_COLORS[event.event_name] || "gray";
  const icon = EVENT_ICONS[event.event_name] || "\u2022";
  const ts = new Date(event.timestamp).toLocaleTimeString();

  return (
    <Box
      borderLeft="3px solid"
      borderColor={`${color}.400`}
      pl={4}
      py={2}
      bg="surface.card"
      borderRadius="0 10px 10px 0"
      transition="all 0.15s ease"
      _hover={{ bg: "soft.hover" }}
    >
      <HStack spacing={3} mb={1}>
        <Text fontSize="xs" color="gray.400" fontFamily="mono" minW="50px">
          #{event.sequence}
        </Text>
        <Text fontSize="xs" color="gray.400">
          {ts}
        </Text>
        <Badge colorScheme={color} variant="subtle" fontSize="xs">
          {icon} {event.event_name.toUpperCase()}
        </Badge>
        {event.model && (
          <Badge variant="subtle" colorScheme="gray" fontSize="xs">
            {event.model}
          </Badge>
        )}
        {event.tool_name && (
          <Badge variant="subtle" colorScheme="gray" fontSize="xs">
            {event.tool_name}
          </Badge>
        )}
      </HStack>

      <VStack align="stretch" spacing={0} pl="62px" fontSize="sm">
        {event.event_name === "user_prompt" && event.prompt && (
          <Text noOfLines={2} color="gray.600">
            &quot;{event.prompt}&quot;
          </Text>
        )}
        {event.event_name === "api_request" && (
          <>
            <HStack spacing={4}>
              <Text color="gray.700">Duration: {event.duration_ms}ms</Text>
              <Text color="gray.700">Cost: ${event.cost_usd}</Text>
            </HStack>
            <Text fontSize="xs" color="gray.500">
              Tokens: {event.input_tokens} in / {event.output_tokens} out /{" "}
              {event.cache_read_tokens} cache_read
            </Text>
          </>
        )}
        {event.event_name === "api_error" && (
          <Text color="red.600">
            {event.status_code}: {event.error}
          </Text>
        )}
        {event.event_name === "tool_decision" && (
          <Text color="gray.600">
            {event.decision} via {event.source}
          </Text>
        )}
        {event.event_name === "tool_result" && (
          <HStack spacing={4}>
            <Text color="gray.700">
              Duration: {event.duration_ms}ms
            </Text>
            <Badge colorScheme={event.success === "true" ? "green" : "red"} variant="subtle">
              {event.success === "true" ? "success" : "failed"}
            </Badge>
            {event.tool_result_size_bytes && (
              <Text fontSize="xs" color="gray.500">{event.tool_result_size_bytes} bytes</Text>
            )}
          </HStack>
        )}
      </VStack>
    </Box>
  );
}
