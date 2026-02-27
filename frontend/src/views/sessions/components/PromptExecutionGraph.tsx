import {
  Box,
  VStack,
  HStack,
  Text,
  Badge,
  Spinner,
  SimpleGrid,
  Stat,
  StatLabel,
  StatNumber,
  Card,
  CardBody,
  Code,
  Tooltip,
  Center,
} from "@chakra-ui/react";
import { useMemo } from "react";
import { usePromptEvents } from "@/shared/hooks/useApi";
import type { PromptEvent } from "@/types/api";

/* ── lane definitions ── */
interface LaneDef {
  key: string;
  label: string;
  color: string;
  border: string;
  badge: string;
  match: (e: PromptEvent) => boolean;
}

const LANES: LaneDef[] = [
  {
    key: "prompt",
    label: "Prompt",
    color: "teal.300",
    border: "teal.500",
    badge: "teal",
    match: (e) => e.event_name === "user_prompt",
  },
  {
    key: "api",
    label: "API",
    color: "blue.300",
    border: "blue.500",
    badge: "blue",
    match: (e) => e.event_name === "api_request",
  },
  {
    key: "tools",
    label: "Tools",
    color: "green.300",
    border: "green.500",
    badge: "green",
    match: (e) => e.event_name === "tool_result" || e.event_name === "tool_decision",
  },
  {
    key: "errors",
    label: "Errors",
    color: "red.300",
    border: "red.500",
    badge: "red",
    match: (e) => e.event_name === "api_error",
  },
];

/* ── helpers ── */
function parseBashParams(raw: string | null): string | null {
  if (!raw) return null;
  try {
    const p = JSON.parse(raw);
    return p.description || p.full_command || null;
  } catch {
    return null;
  }
}

function fmtDur(ms: number): string {
  if (ms < 1000) return `${ms.toFixed(0)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function barLabel(e: PromptEvent): string {
  if (e.event_name === "tool_result" || e.event_name === "tool_decision")
    return e.tool_name || "tool";
  if (e.event_name === "api_request") return e.model?.replace("claude-", "") || "api";
  if (e.event_name === "api_error") return `${e.status_code || "err"}`;
  return "prompt";
}

function tooltipText(e: PromptEvent): string {
  const dur = parseFloat(e.duration_ms || "0");
  const bash = e.tool_name === "Bash" ? parseBashParams(e.tool_parameters) : null;
  return [
    `#${e.sequence} ${e.event_name}`,
    dur > 0 ? `Duration: ${fmtDur(dur)}` : null,
    e.tool_name ? `Tool: ${e.tool_name}` : null,
    e.model ? `Model: ${e.model}` : null,
    e.cost_usd && e.cost_usd !== "0" ? `Cost: $${e.cost_usd}` : null,
    e.input_tokens ? `${e.input_tokens} in / ${e.output_tokens} out` : null,
    e.success ? `Success: ${e.success}` : null,
    bash ? `$ ${bash}` : null,
    e.error ? `Error: ${e.error}` : null,
  ]
    .filter(Boolean)
    .join("\n");
}

/* ── swimlane bar ── */
function SwimlaneBar({
  event,
  lane,
  startMs,
  totalMs,
  row,
}: {
  event: PromptEvent;
  lane: LaneDef;
  startMs: number;
  totalMs: number;
  row: number;
}) {
  const evStart = new Date(event.timestamp).getTime();
  const dur = parseFloat(event.duration_ms || "0");
  const offsetMs = evStart - startMs;

  const leftPct = totalMs > 0 ? (offsetMs / totalMs) * 100 : 0;
  const widthPct = totalMs > 0 ? Math.max((dur / totalMs) * 100, 1.5) : 2;

  const ROW_H = 26;
  const ROW_GAP = 2;
  const topPx = row * (ROW_H + ROW_GAP);

  return (
    <Tooltip label={tooltipText(event)} whiteSpace="pre-wrap" fontSize="xs" placement="top" hasArrow>
      <Box
        position="absolute"
        left={`${leftPct}%`}
        w={`${widthPct}%`}
        minW="20px"
        h={`${ROW_H}px`}
        top={`${topPx}px`}
        bg={lane.color}
        border="1px solid"
        borderColor={lane.border}
        borderRadius="8px"
        cursor="pointer"
        _hover={{ opacity: 0.85, boxShadow: "soft" }}
        transition="all 0.15s ease"
        overflow="hidden"
        px={1}
        display="flex"
        alignItems="center"
        gap={1}
      >
        <Text fontSize="10px" color="white" fontWeight="bold" noOfLines={1}>
          {barLabel(event)}
        </Text>
        {parseFloat(event.duration_ms || "0") > 0 && (
          <Text fontSize="9px" color="whiteAlpha.800" noOfLines={1}>
            {fmtDur(parseFloat(event.duration_ms || "0"))}
          </Text>
        )}
      </Box>
    </Tooltip>
  );
}

/* ── main component ── */
interface Props {
  sessionId: string;
  promptId: string;
}

export function PromptExecutionGraph({ sessionId, promptId }: Props) {
  const { data, isLoading, error } = usePromptEvents(sessionId, promptId);

  const { laneData, totalMs, firstTs, ticks } = useMemo(() => {
    const events = data?.events || [];
    if (events.length === 0)
      return { laneData: [], totalMs: 0, firstTs: 0, ticks: [] };

    const first = new Date(events[0].timestamp).getTime();
    const lastEv = events[events.length - 1];
    const lastEnd =
      new Date(lastEv.timestamp).getTime() + parseFloat(lastEv.duration_ms || "0");
    const total = Math.max(lastEnd - first, 1);

    const result = LANES.map((lane) => {
      const laneEvents = events.filter(lane.match);
      const rows: { end: number }[] = [];
      const positioned = laneEvents.map((e) => {
        const eStart = new Date(e.timestamp).getTime();
        const eDur = parseFloat(e.duration_ms || "0");
        const eEnd = eStart + eDur;
        let row = 0;
        for (row = 0; row < rows.length; row++) {
          if (eStart >= rows[row].end) {
            rows[row].end = eEnd;
            break;
          }
        }
        if (row === rows.length) rows.push({ end: eEnd });
        return { event: e, row };
      });
      return { lane, events: positioned, rowCount: Math.max(rows.length, 1) };
    }).filter((l) => l.events.length > 0);

    const tickCount = 5;
    const tickArr = Array.from({ length: tickCount + 1 }, (_, i) => (i / tickCount) * total);

    return { laneData: result, totalMs: total, firstTs: first, ticks: tickArr };
  }, [data]);

  if (isLoading) return <Center py={4}><Spinner size="sm" color="brand.500" /></Center>;
  if (error) return <Text fontSize="sm" color="red.500">Failed to load prompt events</Text>;

  const events = data?.events || [];
  if (events.length === 0) return <Text fontSize="sm" color="gray.400">No events</Text>;

  const apiCalls = events.filter((e) => e.event_name === "api_request");
  const apiErrors = events.filter((e) => e.event_name === "api_error");
  const toolResults = events.filter((e) => e.event_name === "tool_result");
  const totalCost = apiCalls.reduce((s, e) => s + parseFloat(e.cost_usd || "0"), 0);
  const totalTokens = apiCalls.reduce(
    (s, e) => s + parseInt(e.input_tokens || "0", 10) + parseInt(e.output_tokens || "0", 10),
    0
  );

  const ROW_H = 26;
  const ROW_GAP = 2;
  const LANE_LABEL_W = "64px";

  return (
    <Box bg="surface.card" border="1px solid" borderColor="soft.border" borderRadius="soft-lg" p={4} boxShadow="soft">
      {/* Summary stats */}
      <SimpleGrid columns={{ base: 2, md: 5 }} spacing={3} mb={4}>
        {[
          { label: "Wall Time", value: fmtDur(totalMs) },
          { label: "API Calls", value: apiCalls.length },
          { label: "Tool Calls", value: toolResults.length },
          { label: "Errors", value: apiErrors.length, color: apiErrors.length > 0 ? "red.500" : undefined },
          { label: "Cost / Tokens", value: `$${totalCost.toFixed(3)} / ${totalTokens.toLocaleString()}` },
        ].map((s) => (
          <Card key={s.label} size="sm">
            <CardBody py={2}>
              <Stat size="sm">
                <StatLabel fontSize="xs">{s.label}</StatLabel>
                <StatNumber fontSize="sm" color={s.color}>
                  {s.value}
                </StatNumber>
              </Stat>
            </CardBody>
          </Card>
        ))}
      </SimpleGrid>

      {/* Swimlane chart */}
      <Box bg="surface.muted" borderRadius="soft" p={3} overflowX="auto" boxShadow="soft-inset">
        {/* Time axis */}
        <HStack spacing={0} ml={LANE_LABEL_W} position="relative" h="18px" mb={1}>
          {ticks.map((t, i) => (
            <Text
              key={i}
              position="absolute"
              left={`${(t / totalMs) * 100}%`}
              fontSize="10px"
              color="gray.400"
              fontFamily="mono"
              transform="translateX(-50%)"
              whiteSpace="nowrap"
            >
              {fmtDur(t)}
            </Text>
          ))}
        </HStack>

        {/* Lanes */}
        <VStack spacing={0} align="stretch">
          {laneData.map(({ lane, events: positioned, rowCount }) => {
            const laneH = rowCount * (ROW_H + ROW_GAP);
            return (
              <HStack
                key={lane.key}
                spacing={0}
                borderBottom="1px solid"
                borderColor="soft.border"
                _last={{ borderBottom: "none" }}
              >
                <Box
                  w={LANE_LABEL_W}
                  minH={`${laneH}px`}
                  display="flex"
                  alignItems="center"
                  pr={2}
                >
                  <Badge colorScheme={lane.badge} fontSize="xs" variant="subtle">
                    {lane.label}
                  </Badge>
                </Box>
                <Box flex={1} position="relative" minH={`${laneH}px`} py={1}>
                  {ticks.map((t, i) => (
                    <Box
                      key={`g-${i}`}
                      position="absolute"
                      left={`${(t / totalMs) * 100}%`}
                      top={0}
                      bottom={0}
                      w="1px"
                      bg="soft.border"
                      pointerEvents="none"
                    />
                  ))}
                  {positioned.map(({ event, row }) => (
                    <SwimlaneBar
                      key={event.sequence}
                      event={event}
                      lane={lane}
                      startMs={firstTs}
                      totalMs={totalMs}
                      row={row}
                    />
                  ))}
                </Box>
              </HStack>
            );
          })}
        </VStack>
      </Box>

      {/* Detail callouts */}
      {events.some(
        (e) =>
          e.event_name === "api_error" ||
          (e.event_name === "tool_result" && e.tool_name === "Bash")
      ) && (
        <VStack spacing={1} align="stretch" mt={3}>
          {events
            .filter(
              (e) =>
                e.event_name === "api_error" ||
                (e.event_name === "tool_result" &&
                  e.tool_name === "Bash" &&
                  parseBashParams(e.tool_parameters))
            )
            .map((e) => (
              <HStack key={`detail-${e.sequence}`} fontSize="xs" spacing={2} pl={2}>
                <Badge
                  colorScheme={e.event_name === "api_error" ? "red" : "green"}
                  variant="subtle"
                  fontSize="10px"
                >
                  #{e.sequence}
                </Badge>
                {e.event_name === "api_error" && (
                  <Text color="red.600">
                    {e.status_code}: {e.error}
                  </Text>
                )}
                {e.event_name === "tool_result" && (
                  <Code fontSize="xs" maxW="600px" noOfLines={1} bg="surface.muted" px={2} borderRadius="md">
                    $ {parseBashParams(e.tool_parameters)}
                  </Code>
                )}
              </HStack>
            ))}
        </VStack>
      )}
    </Box>
  );
}
