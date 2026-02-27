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

// Color palette for sessions
const SESSION_COLORS = [
  "#3B82F6", "#8B5CF6", "#10B981", "#F59E0B", "#EF4444",
  "#06B6D4", "#EC4899", "#14B8A6", "#F97316", "#6366F1",
  "#84CC16", "#A855F7", "#22D3EE", "#FB923C", "#4ADE80",
];

/** Metadata for each unique session (color, label, short key for recharts) */
interface SessionMeta {
  sessionId: string;
  key: string;       // short key like "s0", "s1" for recharts dataKey
  label: string;
  color: string;
}

/**
 * Chart data row — ONLY primitive values.
 * recharts iterates all properties, so no arrays/objects allowed.
 * Shape: { date, displayDate, session_count, s0: 1234, s1: 5678, ... }
 */
interface ChartRow {
  date: string;
  displayDate: string;
  session_count: number;
  [shortKey: string]: string | number;
}

/* ── custom tooltip ── */
function ChartTooltip({ active, payload, label, sessionMetaByKey }: {
  active?: boolean;
  payload?: Array<{ value: number; name: string; color: string; dataKey: string }>;
  label?: string;
  sessionMetaByKey?: Map<string, SessionMeta>;
}) {
  if (!active || !payload?.length) return null;
  const visible = payload.filter((p) => (p.value || 0) > 0);
  if (!visible.length) return null;
  const total = visible.reduce((s, p) => s + (p.value || 0), 0);
  return (
    <Box bg="gray.800" color="white" px={3} py={2} borderRadius="8px" boxShadow="soft-md" fontSize="xs" maxW="300px">
      <Text fontWeight="600" mb={1}>{label}</Text>
      {visible.map((p) => {
        const meta = sessionMetaByKey?.get(p.dataKey);
        return (
          <HStack key={p.dataKey} justify="space-between" spacing={4}>
            <HStack spacing={1} minW={0} flex={1}>
              <Box w="8px" h="8px" borderRadius="2px" bg={p.color} flexShrink={0} />
              <Text noOfLines={1}>{meta?.label || p.name}</Text>
            </HStack>
            <Text fontFamily="mono" flexShrink={0}>{formatTokens(p.value)}</Text>
          </HStack>
        );
      })}
      <Box borderTop="1px solid" borderColor="whiteAlpha.300" mt={1} pt={1}>
        <HStack justify="space-between">
          <Text>Total</Text>
          <Text fontWeight="600" fontFamily="mono">{formatTokens(total)}</Text>
        </HStack>
        <Text color="whiteAlpha.600">{visible.length} session{visible.length !== 1 ? "s" : ""}</Text>
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

  console.log("[SessionsPage] render", { isLoading, error, sessionCount: data?.sessions?.length });

  const sessions = data?.sessions || [];

  // Build metadata for each unique session: short key, label, color
  const sessionMetaList = useMemo<SessionMeta[]>(() => {
    const seen = new Set<string>();
    const list: SessionMeta[] = [];
    for (const s of sessions) {
      const sid = s.session_id || "";
      if (!sid || seen.has(sid)) continue;
      seen.add(sid);
      const idx = list.length;
      let label: string;
      if (s.first_prompt) {
        label = s.first_prompt.length > 30 ? s.first_prompt.substring(0, 30) + "..." : s.first_prompt;
      } else {
        label = sid.substring(0, 8);
      }
      list.push({
        sessionId: sid,
        key: `s${idx}`,
        label,
        color: SESSION_COLORS[idx % SESSION_COLORS.length],
      });
    }
    return list;
  }, [sessions]);

  // Lookup maps
  const sessionMetaById = useMemo(() => {
    const m = new Map<string, SessionMeta>();
    for (const sm of sessionMetaList) m.set(sm.sessionId, sm);
    return m;
  }, [sessionMetaList]);

  const sessionMetaByKey = useMemo(() => {
    const m = new Map<string, SessionMeta>();
    for (const sm of sessionMetaList) m.set(sm.key, sm);
    return m;
  }, [sessionMetaList]);

  // Sessions grouped by date (for filtering — kept separate from chart data)
  const sessionsByDate = useMemo(() => {
    const m = new Map<string, SessionSummary[]>();
    for (const s of sessions) {
      const dk = dateKey(s.start_time);
      if (!m.has(dk)) m.set(dk, []);
      m.get(dk)!.push(s);
    }
    return m;
  }, [sessions]);

  // Chart data: one row per date, each session's tokens as a short-keyed property
  const chartData = useMemo<ChartRow[]>(() => {
    const rowMap = new Map<string, ChartRow>();

    for (const s of sessions) {
      const dk = dateKey(s.start_time);
      if (!rowMap.has(dk)) {
        const d = new Date(dk + "T00:00:00");
        rowMap.set(dk, {
          date: dk,
          displayDate: d.toLocaleDateString("en-US", { month: "short", day: "numeric" }),
          session_count: 0,
        });
      }
      const row = rowMap.get(dk)!;
      const meta = sessionMetaById.get(s.session_id);
      if (!meta) continue;

      const totalTokens =
        parseInt(s.total_input_tokens || "0", 10) +
        parseInt(s.total_output_tokens || "0", 10) +
        parseInt(s.total_cache_read_tokens || "0", 10);

      row[meta.key] = ((row[meta.key] as number) || 0) + totalTokens;
      row.session_count = (row.session_count as number) + 1;
    }

    return Array.from(rowMap.values()).sort((a, b) =>
      (a.date as string).localeCompare(b.date as string)
    );
  }, [sessions, sessionMetaById]);

  // Filter sessions based on selected date
  const filteredSessions = useMemo(() => {
    if (!selectedDate) return sessions;
    return sessionsByDate.get(selectedDate) || [];
  }, [selectedDate, sessionsByDate, sessions]);

  // Pre-build Bar elements — recharts needs stable children
  const sessionBars = useMemo(() =>
    sessionMetaList.map((meta) => (
      <Bar
        key={meta.key}
        dataKey={meta.key}
        name={meta.label}
        stackId="sessions"
        fill={meta.color}
      >
        {chartData.map((row) => (
          <Cell
            key={row.date as string}
            fill={meta.color}
            opacity={selectedDate && selectedDate !== row.date ? 0.3 : 1}
            style={{ cursor: "pointer" }}
          />
        ))}
      </Bar>
    )),
    [sessionMetaList, chartData, selectedDate]
  );

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
          {/* Token Time Chart — stacked by session */}
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
                Token Usage by Day (stacked by session)
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
            <Box h="220px">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={chartData}
                  onClick={(state) => {
                    if (!state?.activePayload?.length) return;
                    const row = state.activePayload[0].payload as ChartRow;
                    handleBarClick({ date: row.date as string });
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
                  <RTooltip
                    content={<ChartTooltip sessionMetaByKey={sessionMetaByKey} />}
                  />
                  {sessionBars}
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
            {filteredSessions.map((s, idx) => {
              const sid = s.session_id || `unknown-${idx}`;
              const isExpanded = expandedSession === sid;
              return (
                <Box key={sid}>
                  <SessionCard
                    session={s}
                    isExpanded={isExpanded}
                    onClick={() =>
                      setExpandedSession(isExpanded ? null : sid)
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
                      {isExpanded && sid !== `unknown-${idx}` && (
                        <InlineTimeline sessionId={sid} />
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
