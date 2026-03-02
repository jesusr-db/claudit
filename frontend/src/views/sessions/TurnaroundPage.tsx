import {
  Box,
  Heading,
  VStack,
  HStack,
  Spinner,
  Text,
  Center,
  Badge,
} from "@chakra-ui/react";
import { Link } from "react-router-dom";
import { useTurnaroundSummary, useTurnaroundDetail } from "@/shared/hooks/useApi";
import { MetricTooltip, METRIC_METHODOLOGY } from "@/shared/components/MetricTooltip";

/* ── helpers ── */

function StatCard({
  label,
  value,
  sub,
  methodology,
}: {
  label: string;
  value: string;
  sub?: string;
  methodology?: string;
}) {
  return (
    <Box
      bg="surface.card"
      borderRadius="soft-lg"
      boxShadow="soft"
      border="1px solid"
      borderColor="soft.border"
      p={5}
      flex={1}
      minW="180px"
    >
      {methodology ? (
        <MetricTooltip label={label} methodology={methodology} />
      ) : (
        <Text fontSize="xs" color="gray.500" fontWeight="500">
          {label}
        </Text>
      )}
      <Text fontSize="2xl" fontWeight="700" color="gray.800" fontFamily="mono" mt={methodology ? 0 : 1}>
        {value}
      </Text>
      {sub && (
        <Text fontSize="xs" color="gray.400" mt={1}>
          {sub}
        </Text>
      )}
    </Box>
  );
}

function workColor(sec: number): string {
  if (sec < 30) return "green.600";
  if (sec <= 120) return "orange.500";
  return "red.500";
}

function formatSec(val: string | null | undefined): string {
  if (!val || val === "null") return "-";
  const n = parseFloat(val);
  if (isNaN(n)) return "-";
  if (n >= 60) return `${Math.floor(n / 60)}m ${Math.round(n % 60)}s`;
  return `${Math.round(n)}s`;
}

/* ── main page ── */

export default function TurnaroundPage() {
  const { data: summary, isLoading: summaryLoading, error: summaryError } = useTurnaroundSummary();
  const { data: detail, isLoading: detailLoading, error: detailError } = useTurnaroundDetail();

  const prompts = detail?.prompts || [];

  return (
    <Box p={8}>
      <Box mb={6}>
        <Heading size="lg" mb={1}>
          Agent Turnaround
        </Heading>
        <Text fontSize="sm" color="gray.500">
          How long the agent works autonomously per prompt before needing human input
        </Text>
      </Box>

      {/* Summary Cards */}
      {summaryLoading && (
        <Center py={6}>
          <Spinner color="brand.500" />
        </Center>
      )}
      {summaryError && <Text color="red.500" fontSize="sm" mb={4}>Failed to load summary</Text>}

      {summary && (
        <HStack spacing={4} mb={6} flexWrap="wrap">
          <StatCard
            label="Avg Turnaround"
            value={formatSec(summary.avg_turnaround_sec)}
            sub={`Median: ${formatSec(summary.p50_turnaround_sec)}`}
            methodology={METRIC_METHODOLOGY.avgTurnaround}
          />
          <StatCard
            label="P95 Turnaround"
            value={formatSec(summary.p95_turnaround_sec)}
            sub={`Max: ${formatSec(summary.max_turnaround_sec)}`}
            methodology={METRIC_METHODOLOGY.p95Turnaround}
          />
          <StatCard
            label="Avg Tool Calls / Prompt"
            value={summary.avg_tool_calls ?? "-"}
            sub={`API calls: ${summary.avg_api_calls ?? "-"}`}
            methodology={METRIC_METHODOLOGY.avgToolsPerPrompt}
          />
          <StatCard
            label="Total Prompts Analyzed"
            value={parseInt(summary.total_prompts || "0", 10).toLocaleString()}
            sub={`Across ${summary.total_sessions ?? "-"} sessions`}
          />
        </HStack>
      )}

      {/* Prompt Table */}
      {detailLoading && (
        <Center py={6}>
          <Spinner color="brand.500" />
        </Center>
      )}
      {detailError && <Text color="red.500" fontSize="sm">Failed to load detail</Text>}

      {!detailLoading && prompts.length > 0 && (
        <Box
          bg="surface.card"
          borderRadius="soft-lg"
          boxShadow="soft"
          border="1px solid"
          borderColor="soft.border"
          overflow="hidden"
        >
          <Box px={5} py={4} borderBottom="1px solid" borderColor="soft.border">
            <Text fontSize="sm" fontWeight="600" color="gray.700">
              Per-Prompt Turnaround ({prompts.length} prompts)
            </Text>
          </Box>

          <Box overflowX="auto">
            <Box as="table" w="100%" fontSize="sm">
              <Box as="thead" bg="gray.50">
                <Box as="tr">
                  {["Session", "Prompt Preview", "Agent Work", "API Calls", "Tool Calls", "Events", "Paused?"].map(
                    (h) => (
                      <Box
                        as="th"
                        key={h}
                        px={4}
                        py={3}
                        textAlign="left"
                        fontWeight="600"
                        color="gray.600"
                        fontSize="xs"
                        textTransform="uppercase"
                        letterSpacing="wider"
                      >
                        {h === "Agent Work" ? (
                          <MetricTooltip label={h} methodology={METRIC_METHODOLOGY.agentWork}>
                            <Text fontSize="xs" fontWeight="600" color="gray.600" textTransform="uppercase" letterSpacing="wider">{h}</Text>
                          </MetricTooltip>
                        ) : h}
                      </Box>
                    )
                  )}
                </Box>
              </Box>
              <Box as="tbody">
                {prompts.map((p, idx) => {
                  const agentSec = parseFloat(p.agent_work_sec || "0");
                  return (
                    <Box
                      as="tr"
                      key={`${p.session_id}-${p.prompt_id}-${idx}`}
                      _hover={{ bg: "soft.hover" }}
                      borderBottom="1px solid"
                      borderColor="soft.border"
                    >
                      <Box as="td" px={4} py={3}>
                        <Text
                          as={Link}
                          to={`/sessions/${p.session_id}`}
                          color="brand.600"
                          fontFamily="mono"
                          fontSize="xs"
                          _hover={{ textDecoration: "underline" }}
                        >
                          {p.session_id?.substring(0, 8)}...
                        </Text>
                      </Box>
                      <Box as="td" px={4} py={3} maxW="300px">
                        <Text noOfLines={1} color="gray.700" fontSize="xs">
                          {p.prompt_preview || "-"}
                        </Text>
                      </Box>
                      <Box as="td" px={4} py={3}>
                        <Text
                          fontWeight="600"
                          fontFamily="mono"
                          color={workColor(agentSec)}
                        >
                          {formatSec(p.agent_work_sec)}
                        </Text>
                      </Box>
                      <Box as="td" px={4} py={3} fontFamily="mono" color="gray.600">
                        {p.api_calls ?? "-"}
                      </Box>
                      <Box as="td" px={4} py={3} fontFamily="mono" color="gray.600">
                        {p.tool_calls ?? "-"}
                      </Box>
                      <Box as="td" px={4} py={3} fontFamily="mono" color="gray.600">
                        {p.events_in_prompt ?? "-"}
                      </Box>
                      <Box as="td" px={4} py={3}>
                        <HStack spacing={1}>
                          {p.has_question === "1" && (
                            <Badge
                              colorScheme="purple"
                              fontSize="10px"
                              variant="subtle"
                            >
                              Question
                            </Badge>
                          )}
                          {p.has_plan_exit === "1" && (
                            <Badge
                              colorScheme="blue"
                              fontSize="10px"
                              variant="subtle"
                            >
                              Plan
                            </Badge>
                          )}
                        </HStack>
                      </Box>
                    </Box>
                  );
                })}
              </Box>
            </Box>
          </Box>
        </Box>
      )}

      {!detailLoading && prompts.length === 0 && !detailError && (
        <Text color="gray.400" fontSize="sm">
          No turnaround data available
        </Text>
      )}
    </Box>
  );
}
