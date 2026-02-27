import {
  Box,
  Heading,
  VStack,
  HStack,
  Spinner,
  Text,
  Center,
  Badge,
  Button,
  Collapse,
} from "@chakra-ui/react";
import { useMemo, useState, useCallback } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RTooltip,
  ResponsiveContainer,
  Cell,
  Legend,
} from "recharts";
import { useSessions, useSessionTimeline } from "@/shared/hooks/useApi";
import { SessionCard } from "./components/SessionCard";
import { SessionTimeline } from "./components/SessionTimeline";
import type { SessionSummary } from "@/types/api";

/* ── helpers ── */

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString();
}

function dateKey(ts: string | null | undefined): string {
  if (!ts) return "unknown";
  return ts.slice(0, 10); // "YYYY-MM-DD"
}

interface DailyBucket {
  date: string;
  displayDate: string;
  input_tokens: number;
  output_tokens: number;
  cache_read_tokens: number;
  session_count: number;
  sessions: SessionSummary[];
}

/* ── custom tooltip ── */
function ChartTooltip({ active, payload, label }: {
  active?: boolean;
  payload?: Array<{ value: number; name: string; color: string }>;
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  const total = payload.reduce((s, p) => s + (p.value || 0), 0);
  const sessionCount = (payload[0] as unknown as { payload: DailyBucket })?.payload?.session_count || 0;
  return (
    <Box bg="gray.800" color="white" px={3} py={2} borderRadius="8px" boxShadow="soft-md" fontSize="xs">
      <Text fontWeight="600" mb={1}>{label}</Text>
      {payload.map((p) => (
        <HStack key={p.name} justify="space-between" spacing={4}>
          <HStack spacing={1}>
            <Box w="8px" h="8px" borderRadius="2px" bg={p.color} />
            <Text>{p.name}</Text>
          </HStack>
          <Text fontFamily="mono">{formatTokens(p.value)}</Text>
        </HStack>
      ))}
      <Box borderTop="1px solid" borderColor="whiteAlpha.300" mt={1} pt={1}>
        <HStack justify="space-between">
          <Text>Total</Text>
          <Text fontWeight="600" fontFamily="mono">{formatTokens(total)}</Text>
        </HStack>
        <Text color="whiteAlpha.600">{sessionCount} session{sessionCount !== 1 ? "s" : ""}</Text>
      </Box>
    </Box>
  );
}

/* ── inline timeline wrapper (loads data when expanded) ── */
function InlineTimeline({ sessionId }: { sessionId: string }) {
  const { data, isLoading, error } = useSessionTimeline(sessionId);

  if (isLoading) return <Center py={6}><Spinner color="brand.500" size="sm" /></Center>;
  if (error) return <Text color="red.500" fontSize="sm">Failed to load timeline</Text>;

  const events = data?.events || [];
  if (events.length === 0) return <Text color="gray.400" fontSize="sm">No events</Text>;

  return <SessionTimeline events={events} sessionId={sessionId} />;
}

/* ── main page ── */

export default function SessionsPage() {
  const { data, isLoading, error } = useSessions();
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [expandedSession, setExpandedSession] = useState<string | null>(null);

  console.log("[SessionsPage] render", { isLoading, error, data, sessionCount: data?.sessions?.length });

  const sessions = data?.sessions || [];

  // Aggregate sessions by date
  const dailyBuckets = useMemo(() => {
    const bucketMap = new Map<string, DailyBucket>();

    for (const s of sessions) {
      const dk = dateKey(s.start_time);
      if (!bucketMap.has(dk)) {
        const d = new Date(dk + "T00:00:00");
        bucketMap.set(dk, {
          date: dk,
          displayDate: d.toLocaleDateString("en-US", { month: "short", day: "numeric" }),
          input_tokens: 0,
          output_tokens: 0,
          cache_read_tokens: 0,
          session_count: 0,
          sessions: [],
        });
      }
      const bucket = bucketMap.get(dk)!;
      bucket.input_tokens += parseInt(s.total_input_tokens || "0", 10);
      bucket.output_tokens += parseInt(s.total_output_tokens || "0", 10);
      bucket.cache_read_tokens += parseInt(s.total_cache_read_tokens || "0", 10);
      bucket.session_count++;
      bucket.sessions.push(s);
    }

    return Array.from(bucketMap.values()).sort((a, b) =>
      a.date.localeCompare(b.date)
    );
  }, [sessions]);

  // Filter sessions based on selected date
  const filteredSessions = useMemo(() => {
    if (!selectedDate) return sessions;
    const bucket = dailyBuckets.find((b) => b.date === selectedDate);
    return bucket?.sessions || [];
  }, [selectedDate, dailyBuckets, sessions]);

  const handleBarClick = useCallback(
    (data: { date: string }) => {
      if (!data) return;
      setSelectedDate((prev) => (prev === data.date ? null : data.date));
    },
    []
  );

  return (
    <Box p={8}>
      <Box mb={6}>
        <Heading size="lg" mb={1}>
          Sessions
        </Heading>
        <Text fontSize="sm" color="gray.500">
          Claude Code conversation sessions and their token usage over time
        </Text>
      </Box>

      {isLoading && (
        <Center py={8}>
          <Spinner color="brand.500" />
        </Center>
      )}
      {error && <Text color="red.500">Failed to load sessions</Text>}

      {!isLoading && sessions.length > 0 && (
        <VStack spacing={5} align="stretch">
          {/* Token Time Chart */}
          <Box
            bg="surface.card"
            borderRadius="soft-lg"
            boxShadow="soft"
            border="1px solid"
            borderColor="soft.border"
            p={5}
          >
            <HStack justify="space-between" mb={3}>
              <Text fontSize="sm" fontWeight="600" color="gray.700">
                Token Usage by Day
              </Text>
              {selectedDate && (
                <Button
                  size="xs"
                  variant="ghost"
                  color="brand.600"
                  onClick={() => setSelectedDate(null)}
                >
                  Clear filter
                </Button>
              )}
            </HStack>
            <Box h="200px">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={dailyBuckets}
                  onClick={(state) => {
                    if (state?.activePayload?.[0]?.payload) {
                      handleBarClick(state.activePayload[0].payload);
                    }
                  }}
                  style={{ cursor: "pointer" }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" vertical={false} />
                  <XAxis
                    dataKey="displayDate"
                    tick={{ fontSize: 11, fill: "#94A3B8" }}
                    tickLine={false}
                    axisLine={{ stroke: "#E2E8F0" }}
                  />
                  <YAxis
                    tick={{ fontSize: 11, fill: "#94A3B8" }}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={formatTokens}
                    width={50}
                  />
                  <RTooltip content={<ChartTooltip />} />
                  <Legend
                    iconType="square"
                    iconSize={8}
                    wrapperStyle={{ fontSize: 11, paddingTop: 8 }}
                  />
                  <Bar
                    dataKey="input_tokens"
                    name="Input"
                    stackId="tokens"
                    radius={[0, 0, 0, 0]}
                  >
                    {dailyBuckets.map((entry) => (
                      <Cell
                        key={entry.date}
                        fill={selectedDate === entry.date ? "#1D4ED8" : "#3B82F6"}
                        opacity={selectedDate && selectedDate !== entry.date ? 0.35 : 1}
                        style={{ cursor: "pointer" }}
                      />
                    ))}
                  </Bar>
                  <Bar
                    dataKey="output_tokens"
                    name="Output"
                    stackId="tokens"
                    radius={[0, 0, 0, 0]}
                  >
                    {dailyBuckets.map((entry) => (
                      <Cell
                        key={entry.date}
                        fill={selectedDate === entry.date ? "#7C3AED" : "#A78BFA"}
                        opacity={selectedDate && selectedDate !== entry.date ? 0.35 : 1}
                        style={{ cursor: "pointer" }}
                      />
                    ))}
                  </Bar>
                  <Bar
                    dataKey="cache_read_tokens"
                    name="Cache Read"
                    stackId="tokens"
                    radius={[4, 4, 0, 0]}
                  >
                    {dailyBuckets.map((entry) => (
                      <Cell
                        key={entry.date}
                        fill={selectedDate === entry.date ? "#059669" : "#34D399"}
                        opacity={selectedDate && selectedDate !== entry.date ? 0.35 : 1}
                        style={{ cursor: "pointer" }}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </Box>
          </Box>

          {/* Session filter indicator */}
          {selectedDate && (
            <HStack spacing={2}>
              <Badge variant="subtle" colorScheme="brand" fontSize="xs" px={2} py={1}>
                Filtered: {new Date(selectedDate + "T00:00:00").toLocaleDateString("en-US", {
                  weekday: "short",
                  month: "short",
                  day: "numeric",
                })}
              </Badge>
              <Text fontSize="xs" color="gray.500">
                {filteredSessions.length} session{filteredSessions.length !== 1 ? "s" : ""}
              </Text>
            </HStack>
          )}

          {/* Session cards with inline timeline */}
          <VStack spacing={3} align="stretch">
            {filteredSessions.map((s) => {
              const isExpanded = expandedSession === s.session_id;
              return (
                <Box key={s.session_id}>
                  <SessionCard
                    session={s}
                    isExpanded={isExpanded}
                    onClick={() =>
                      setExpandedSession(isExpanded ? null : s.session_id)
                    }
                  />
                  <Collapse in={isExpanded} animateOpacity>
                    <Box
                      mt={-1}
                      mx={1}
                      p={5}
                      bg="surface.card"
                      border="1px solid"
                      borderColor="brand.200"
                      borderTop="none"
                      borderRadius="0 0 14px 14px"
                      boxShadow="soft"
                    >
                      {isExpanded && (
                        <InlineTimeline sessionId={s.session_id} />
                      )}
                    </Box>
                  </Collapse>
                </Box>
              );
            })}
            {filteredSessions.length === 0 && (
              <Text color="gray.400" fontSize="sm">
                No sessions found
              </Text>
            )}
          </VStack>
        </VStack>
      )}

      {!isLoading && sessions.length === 0 && (
        <Text color="gray.400" fontSize="sm">
          No sessions found
        </Text>
      )}
    </Box>
  );
}
