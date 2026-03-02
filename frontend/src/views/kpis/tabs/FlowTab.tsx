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
  Badge,
  Icon,
} from "@chakra-ui/react";
import { useMemo } from "react";
import { FiArrowRight } from "react-icons/fi";
import {
  useKpiFlowSummary,
  useKpiAuditCorrelation,
} from "@/shared/hooks/useApi";
import { MetricTooltip, METRIC_METHODOLOGY } from "@/shared/components/MetricTooltip";
import type { KpiFlowRow } from "@/types/api";

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

function formatMs(val: string | number): string {
  const n = typeof val === "string" ? parseFloat(val) : val;
  if (isNaN(n) || n === 0) return "-";
  if (n >= 1000) return `${(n / 1000).toFixed(1)}s`;
  return `${Math.round(n)}ms`;
}

export default function FlowTab({ days = 30 }: { days?: number }) {
  const { data: flowData, isLoading: flowLoading } = useKpiFlowSummary(days);
  const { data: auditData, isLoading: auditLoading } = useKpiAuditCorrelation(days);

  const { tools, connections, externalApis } = useMemo(() => {
    const rows = flowData?.flows || [];
    return {
      tools: rows.filter((r: KpiFlowRow) => r.section === "tool"),
      connections: rows.filter((r: KpiFlowRow) => r.section === "connection"),
      externalApis: rows.filter((r: KpiFlowRow) => r.section === "external_api"),
    };
  }, [flowData]);

  return (
    <VStack spacing={5} align="stretch">
      {/* Visual Flow Indicator */}
      <CardBox>
        <Text fontSize="sm" fontWeight="600" color="gray.700" mb={4}>End-to-End Flow</Text>
        <HStack spacing={4} justify="center" py={3} flexWrap="wrap">
          {[
            { label: "Claude Code", color: "brand", desc: "Client OTEL" },
            { label: "MCP Server", color: "purple", desc: "Tool Spans" },
            { label: "UC Connection", color: "orange", desc: "HTTP to /mcp/external/*" },
            { label: "External API", color: "teal", desc: "HTTP Outbound" },
          ].map((step, i) => (
            <HStack key={step.label} spacing={3}>
              {i > 0 && <Icon as={FiArrowRight} color="gray.400" boxSize={4} />}
              <Box textAlign="center">
                <Badge colorScheme={step.color} fontSize="xs" px={3} py={1} borderRadius="full">
                  {step.label}
                </Badge>
                <Text fontSize="10px" color="gray.400" mt={1}>{step.desc}</Text>
              </Box>
            </HStack>
          ))}
        </HStack>
      </CardBox>

      {flowLoading ? (
        <Center py={8}><Spinner color="brand.500" size="sm" /></Center>
      ) : (flowData?.flows || []).length === 0 ? (
        <CardBox>
          <Text fontSize="sm" color="gray.400">No MCP flow data available</Text>
        </CardBox>
      ) : (
        <>
          {/* Tool Spans */}
          <CardBox>
            <Text fontSize="sm" fontWeight="600" color="gray.700" mb={3}>MCP Tool Calls</Text>
            <Box overflowX="auto">
              <Table size="sm" variant="simple">
                <Thead>
                  <Tr>
                    <Th>Server</Th>
                    <Th>Tool</Th>
                    <Th isNumeric>Calls</Th>
                    <Th isNumeric>
                      <MetricTooltip label="Avg Latency" methodology={METRIC_METHODOLOGY.avgLatency}>
                        <Text fontSize="xs" fontWeight="600" color="gray.600" textTransform="uppercase" letterSpacing="wider">Avg Latency</Text>
                      </MetricTooltip>
                    </Th>
                    <Th isNumeric>Success</Th>
                    <Th isNumeric>Errors</Th>
                  </Tr>
                </Thead>
                <Tbody>
                  {tools.map((f, i) => {
                    const errors = parseInt(f.errors || "0", 10);
                    return (
                      <Tr key={i} _hover={{ bg: "soft.hover" }}>
                        <Td fontSize="xs">{f.server_name}</Td>
                        <Td fontSize="xs" fontFamily="mono">{f.name.replace("mcp.tool.", "")}</Td>
                        <Td isNumeric fontSize="xs" fontWeight="600">{f.calls}</Td>
                        <Td isNumeric fontSize="xs" fontFamily="mono">{formatMs(f.avg_duration_ms)}</Td>
                        <Td isNumeric fontSize="xs">{f.success || "-"}</Td>
                        <Td isNumeric fontSize="xs">
                          {errors > 0 ? (
                            <Badge colorScheme="red" fontSize="10px">{errors}</Badge>
                          ) : (
                            <Text color="gray.400">0</Text>
                          )}
                        </Td>
                      </Tr>
                    );
                  })}
                </Tbody>
              </Table>
            </Box>
          </CardBox>

          {/* UC Connections via HTTP */}
          {connections.length > 0 && (
            <CardBox>
              <Text fontSize="sm" fontWeight="600" color="gray.700" mb={1}>UC Connections (via HTTP)</Text>
              <Text fontSize="xs" color="gray.400" mb={3}>
                HTTP calls to /api/2.0/mcp/external/&#123;connection&#125; with UC audit correlation
              </Text>
              <Box overflowX="auto">
                <Table size="sm" variant="simple">
                  <Thead>
                    <Tr>
                      <Th>Server</Th>
                      <Th>Connection</Th>
                      <Th isNumeric>HTTP Calls</Th>
                      <Th isNumeric>Avg Latency</Th>
                      <Th isNumeric>HTTP Errors</Th>
                      <Th isNumeric>UC Audit Events</Th>
                    </Tr>
                  </Thead>
                  <Tbody>
                    {connections.map((f, i) => {
                      const errors = parseInt(f.errors || "0", 10);
                      const auditEvents = parseInt(f.extra || "0", 10);
                      return (
                        <Tr key={i} _hover={{ bg: "soft.hover" }}>
                          <Td fontSize="xs">{f.server_name}</Td>
                          <Td>
                            <Badge colorScheme="purple" fontSize="xs" fontFamily="mono">
                              {f.name}
                            </Badge>
                          </Td>
                          <Td isNumeric fontSize="xs" fontWeight="600">{f.calls}</Td>
                          <Td isNumeric fontSize="xs" fontFamily="mono">{formatMs(f.avg_duration_ms)}</Td>
                          <Td isNumeric fontSize="xs">
                            {errors > 0 ? (
                              <Badge colorScheme="red" fontSize="10px">{errors}</Badge>
                            ) : (
                              <Text color="gray.400">0</Text>
                            )}
                          </Td>
                          <Td isNumeric fontSize="xs">
                            {auditEvents > 0 ? (
                              <Badge colorScheme="green" fontSize="10px">{auditEvents}</Badge>
                            ) : (
                              <Text color="gray.400">0</Text>
                            )}
                          </Td>
                        </Tr>
                      );
                    })}
                  </Tbody>
                </Table>
              </Box>
            </CardBox>
          )}

          {/* External APIs */}
          {externalApis.length > 0 && (
            <CardBox>
              <Text fontSize="sm" fontWeight="600" color="gray.700" mb={3}>External API Calls</Text>
              <Box overflowX="auto">
                <Table size="sm" variant="simple">
                  <Thead>
                    <Tr>
                      <Th>Server</Th>
                      <Th>Domain</Th>
                      <Th isNumeric>Calls</Th>
                      <Th isNumeric>Avg Latency</Th>
                    </Tr>
                  </Thead>
                  <Tbody>
                    {externalApis.map((f, i) => (
                      <Tr key={i} _hover={{ bg: "soft.hover" }}>
                        <Td fontSize="xs">{f.server_name}</Td>
                        <Td fontSize="xs" fontFamily="mono">{f.name}</Td>
                        <Td isNumeric fontSize="xs" fontWeight="600">{f.calls}</Td>
                        <Td isNumeric fontSize="xs" fontFamily="mono">{formatMs(f.avg_duration_ms)}</Td>
                      </Tr>
                    ))}
                  </Tbody>
                </Table>
              </Box>
            </CardBox>
          )}
        </>
      )}

      {/* UC Connection Summary */}
      <CardBox>
        <Text fontSize="sm" fontWeight="600" color="gray.700" mb={3}>Unity Catalog Connections</Text>
        {auditLoading ? (
          <Center py={8}><Spinner color="brand.500" size="sm" /></Center>
        ) : (auditData?.audit || []).length === 0 ? (
          <Text fontSize="sm" color="gray.400">No UC connection events found</Text>
        ) : (
          <Box overflowX="auto">
            <Table size="sm" variant="simple">
              <Thead>
                <Tr>
                  <Th>Connection</Th>
                  <Th>Action</Th>
                  <Th isNumeric>Calls</Th>
                  <Th isNumeric>Active Days</Th>
                  <Th isNumeric>Users</Th>
                  <Th>First Seen</Th>
                  <Th>Last Seen</Th>
                </Tr>
              </Thead>
              <Tbody>
                {(auditData?.audit || []).map((a, i) => (
                  <Tr key={i} _hover={{ bg: "soft.hover" }}>
                    <Td>
                      <Badge
                        colorScheme={a.connection_name === "(all connections)" ? "gray" : "purple"}
                        fontSize="xs"
                        fontFamily="mono"
                      >
                        {a.connection_name}
                      </Badge>
                    </Td>
                    <Td fontSize="xs">{a.action_name}</Td>
                    <Td isNumeric fontSize="xs" fontWeight="600">{a.call_count}</Td>
                    <Td isNumeric fontSize="xs">{a.active_days}</Td>
                    <Td isNumeric fontSize="xs">{a.distinct_users}</Td>
                    <Td fontSize="xs" fontFamily="mono" whiteSpace="nowrap">
                      {a.first_seen ? new Date(a.first_seen).toLocaleDateString() : "-"}
                    </Td>
                    <Td fontSize="xs" fontFamily="mono" whiteSpace="nowrap">
                      {a.last_seen ? new Date(a.last_seen).toLocaleString() : "-"}
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
