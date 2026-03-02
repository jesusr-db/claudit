import {
  Box,
  VStack,
  HStack,
  Text,
  Spinner,
  Center,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
} from "@chakra-ui/react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RTooltip,
  ResponsiveContainer,
} from "recharts";
import {
  useKpiEffectivenessOverview,
  useKpiToolRetries,
  useKpiOrphanDecisions,
  useKpiErrorRecovery,
  useKpiPromptComplexity,
} from "@/shared/hooks/useApi";
import { ErrorsTable } from "@/views/dashboard/components/ErrorsTable";
import { MetricTooltip, METRIC_METHODOLOGY } from "@/shared/components/MetricTooltip";

function StatCard({ label, value, sub, methodology }: { label: string; value: string; sub?: string; methodology?: string }) {
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
        <Text fontSize="xs" color="gray.500" fontWeight="500">{label}</Text>
      )}
      <Text fontSize="2xl" fontWeight="700" color="gray.800" fontFamily="mono" mt={methodology ? 0 : 1}>{value}</Text>
      {sub && <Text fontSize="xs" color="gray.400" mt={1}>{sub}</Text>}
    </Box>
  );
}

function CardBox({ children }: { children: React.ReactNode }) {
  return (
    <Box
      bg="surface.card"
      borderRadius="soft-lg"
      boxShadow="soft"
      border="1px solid"
      borderColor="soft.border"
      p={5}
    >
      {children}
    </Box>
  );
}

export default function EffectivenessTab({ days = 30 }: { days?: number }) {
  const { data: overview, isLoading: overviewLoading } = useKpiEffectivenessOverview(days);
  const { data: retriesData, isLoading: retriesLoading } = useKpiToolRetries(days);
  const { data: orphansData, isLoading: orphansLoading } = useKpiOrphanDecisions(days);
  const { data: recoveryData, isLoading: recoveryLoading } = useKpiErrorRecovery(days);
  const { data: complexityData, isLoading: complexityLoading } = useKpiPromptComplexity(days);

  const complexityChart = (complexityData?.complexity || []).map((c) => ({
    bucket: c.bucket,
    prompt_count: parseInt(c.prompt_count || "0", 10),
    avg_tool_calls: parseFloat(c.avg_tool_calls || "0"),
    avg_agent_work_sec: parseFloat(c.avg_agent_work_sec || "0"),
  }));

  return (
    <VStack spacing={5} align="stretch">
      {/* Hero Cards */}
      {overviewLoading ? (
        <Center py={4}><Spinner color="brand.500" size="sm" /></Center>
      ) : overview ? (
        <HStack spacing={4} flexWrap="wrap">
          <StatCard
            label="Tool Success Rate"
            value={`${parseFloat(overview.tool_success_rate || "0").toFixed(1)}%`}
            sub={`${overview.total_tool_calls} total calls`}
            methodology={METRIC_METHODOLOGY.toolSuccess}
          />
          <StatCard
            label="Avg Tools / Prompt"
            value={parseFloat(overview.avg_tools_per_prompt || "0").toFixed(1)}
            sub={`API calls: ${overview.avg_api_calls_per_prompt}`}
            methodology={METRIC_METHODOLOGY.avgToolsPerPrompt}
          />
          <StatCard
            label="Total Errors"
            value={parseInt(overview.total_errors || "0", 10).toLocaleString()}
          />
          <StatCard
            label="Total Prompts"
            value={parseInt(overview.total_prompts || "0", 10).toLocaleString()}
          />
        </HStack>
      ) : null}

      {/* Prompt Complexity Distribution */}
      <CardBox>
        <MetricTooltip label="Prompt Complexity Distribution" methodology={METRIC_METHODOLOGY.promptComplexity}>
          <Text fontSize="sm" fontWeight="600" color="gray.700">Prompt Complexity Distribution</Text>
        </MetricTooltip>
        <Box mb={3} />
        {complexityLoading ? (
          <Center py={8}><Spinner color="brand.500" size="sm" /></Center>
        ) : (
          <Box h="220px">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={complexityChart}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" vertical={false} />
                <XAxis dataKey="bucket" tick={{ fontSize: 11, fill: "#94A3B8" }} tickLine={false} axisLine={{ stroke: "#E2E8F0" }} label={{ value: "Events per prompt", position: "insideBottom", offset: -3, fontSize: 11, fill: "#94A3B8" }} />
                <YAxis tick={{ fontSize: 11, fill: "#94A3B8" }} tickLine={false} axisLine={false} width={50} />
                <RTooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #E2E8F0" }} />
                <Bar dataKey="prompt_count" fill="#8B5CF6" name="Prompts" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Box>
        )}
      </CardBox>

      <HStack spacing={5} align="start" flexWrap={{ base: "wrap", lg: "nowrap" }}>
        {/* Tool Retries */}
        <CardBox>
          <MetricTooltip label="Tool Retries" methodology={METRIC_METHODOLOGY.toolRetries}>
            <Text fontSize="sm" fontWeight="600" color="gray.700">Tool Retries</Text>
          </MetricTooltip>
          <Box mb={3} />
          {retriesLoading ? (
            <Center py={4}><Spinner color="brand.500" size="sm" /></Center>
          ) : (retriesData?.retries || []).length === 0 ? (
            <Text fontSize="sm" color="gray.400">No retries detected</Text>
          ) : (
            <Box overflowX="auto">
              <Table size="sm" variant="simple">
                <Thead>
                  <Tr>
                    <Th>Tool</Th>
                    <Th isNumeric>Retries</Th>
                    <Th isNumeric>Sessions</Th>
                  </Tr>
                </Thead>
                <Tbody>
                  {(retriesData?.retries || []).map((r) => (
                    <Tr key={r.tool_name} _hover={{ bg: "soft.hover" }}>
                      <Td fontSize="xs" fontFamily="mono">{r.tool_name}</Td>
                      <Td isNumeric fontSize="xs">{r.retry_count}</Td>
                      <Td isNumeric fontSize="xs">{r.sessions_affected}</Td>
                    </Tr>
                  ))}
                </Tbody>
              </Table>
            </Box>
          )}
        </CardBox>

        {/* Orphan Decisions */}
        <CardBox>
          <MetricTooltip label="Orphan Decisions" methodology={METRIC_METHODOLOGY.orphanDecisions}>
            <Text fontSize="sm" fontWeight="600" color="gray.700">Orphan Decisions</Text>
          </MetricTooltip>
          <Box mb={3} />
          {orphansLoading ? (
            <Center py={4}><Spinner color="brand.500" size="sm" /></Center>
          ) : (orphansData?.orphans || []).length === 0 ? (
            <Text fontSize="sm" color="gray.400">No orphan decisions detected</Text>
          ) : (
            <Box overflowX="auto">
              <Table size="sm" variant="simple">
                <Thead>
                  <Tr>
                    <Th>Tool</Th>
                    <Th isNumeric>Orphans</Th>
                    <Th isNumeric>Sessions</Th>
                  </Tr>
                </Thead>
                <Tbody>
                  {(orphansData?.orphans || []).map((o) => (
                    <Tr key={o.tool_name} _hover={{ bg: "soft.hover" }}>
                      <Td fontSize="xs" fontFamily="mono">{o.tool_name}</Td>
                      <Td isNumeric fontSize="xs">{o.orphan_count}</Td>
                      <Td isNumeric fontSize="xs">{o.sessions_affected}</Td>
                    </Tr>
                  ))}
                </Tbody>
              </Table>
            </Box>
          )}
        </CardBox>
      </HStack>

      {/* Recent Errors */}
      <CardBox>
        <Text fontSize="sm" fontWeight="600" color="gray.700" mb={3}>Recent Errors</Text>
        <ErrorsTable />
      </CardBox>

      {/* Error Recovery */}
      <CardBox>
        <MetricTooltip label="Error Recovery Patterns" methodology={METRIC_METHODOLOGY.errorRecovery}>
          <Text fontSize="sm" fontWeight="600" color="gray.700">Error Recovery Patterns</Text>
        </MetricTooltip>
        <Box mb={3} />
        {recoveryLoading ? (
          <Center py={4}><Spinner color="brand.500" size="sm" /></Center>
        ) : (recoveryData?.recovery || []).length === 0 ? (
          <Text fontSize="sm" color="gray.400">No error recovery data</Text>
        ) : (
          <Box overflowX="auto">
            <Table size="sm" variant="simple">
              <Thead>
                <Tr>
                  <Th>Model</Th>
                  <Th isNumeric>Recoveries</Th>
                  <Th isNumeric>Total Errors</Th>
                  <Th isNumeric>Recovery Rate</Th>
                </Tr>
              </Thead>
              <Tbody>
                {(recoveryData?.recovery || []).map((r) => (
                  <Tr key={r.model} _hover={{ bg: "soft.hover" }}>
                    <Td fontSize="xs">{(r.model || "").replace(/^.*\//, "")}</Td>
                    <Td isNumeric fontSize="xs">{r.recovery_count}</Td>
                    <Td isNumeric fontSize="xs">{r.total_errors}</Td>
                    <Td isNumeric fontSize="xs" fontWeight="600" color={parseFloat(r.recovery_rate || "0") > 50 ? "green.600" : "orange.500"}>
                      {parseFloat(r.recovery_rate || "0").toFixed(1)}%
                    </Td>
                  </Tr>
                ))}
              </Tbody>
            </Table>
          </Box>
        )}
      </CardBox>
    </VStack>
  );
}
