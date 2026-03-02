import { useState } from "react";
import {
  Box,
  VStack,
  SimpleGrid,
  Card,
  CardBody,
  Stat,
  StatLabel,
  StatNumber,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Badge,
  Spinner,
  Text,
  Center,
  Collapse,
  IconButton,
  HStack,
} from "@chakra-ui/react";
import { FiChevronDown, FiChevronRight } from "react-icons/fi";
import {
  useMcpServerSummary,
  useMcpServerDetail,
  useMcpToolStats,
  useMcpHttpSummary,
} from "@/shared/hooks/useApi";
import { useTimeRange } from "@/shared/context/TimeRangeContext";

function fmtMs(ms: number): string {
  if (ms < 1000) return `${ms.toFixed(0)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function ServerDetailPanel({ server }: { server: string }) {
  const { days } = useTimeRange();
  const { data, isLoading } = useMcpServerDetail(server, days);

  if (isLoading) {
    return (
      <Box py={4} px={6}>
        <Spinner size="sm" color="brand.500" />
      </Box>
    );
  }

  const toolCalls = data?.tool_calls || [];
  const toolLatency = data?.tool_latency || [];
  const httpDuration = data?.http_duration || [];

  return (
    <Box py={4} px={6} bg="gray.50" borderBottom="1px solid" borderColor="soft.border">
      <VStack spacing={4} align="stretch">
        {/* Tool Call Metrics */}
        {toolCalls.length > 0 && (
          <Box>
            <Text fontSize="xs" fontWeight="600" color="gray.600" mb={2}>
              Tool Call Counts (from mcp.tool.calls metric)
            </Text>
            <Table size="sm" variant="simple">
              <Thead>
                <Tr>
                  <Th fontSize="xs">Tool</Th>
                  <Th fontSize="xs">Status</Th>
                  <Th fontSize="xs" isNumeric>Calls</Th>
                </Tr>
              </Thead>
              <Tbody>
                {toolCalls.map((tc, i) => (
                  <Tr key={i}>
                    <Td fontFamily="mono" fontSize="xs">{tc.tool_name}</Td>
                    <Td>
                      <Badge
                        colorScheme={tc.status === "success" ? "green" : "red"}
                        variant="subtle"
                        fontSize="xs"
                      >
                        {tc.status}
                      </Badge>
                    </Td>
                    <Td isNumeric fontWeight="600" fontSize="xs">
                      {parseFloat(tc.total_calls || "0").toFixed(0)}
                    </Td>
                  </Tr>
                ))}
              </Tbody>
            </Table>
          </Box>
        )}

        {/* Tool Latency Metrics */}
        {toolLatency.length > 0 && (
          <Box>
            <Text fontSize="xs" fontWeight="600" color="gray.600" mb={2}>
              Tool Latency (from mcp.tool.latency histogram)
            </Text>
            <Table size="sm" variant="simple">
              <Thead>
                <Tr>
                  <Th fontSize="xs">Tool</Th>
                  <Th fontSize="xs" isNumeric>Samples</Th>
                  <Th fontSize="xs" isNumeric>Avg</Th>
                  <Th fontSize="xs" isNumeric>Min</Th>
                  <Th fontSize="xs" isNumeric>Max</Th>
                </Tr>
              </Thead>
              <Tbody>
                {toolLatency.map((tl, i) => (
                  <Tr key={i}>
                    <Td fontFamily="mono" fontSize="xs">{tl.tool_name}</Td>
                    <Td isNumeric fontSize="xs">{tl.samples}</Td>
                    <Td isNumeric fontFamily="mono" fontSize="xs" fontWeight="600">
                      {fmtMs(parseFloat(tl.avg_latency_ms || "0"))}
                    </Td>
                    <Td isNumeric fontFamily="mono" fontSize="xs">
                      {fmtMs(parseFloat(tl.min_latency_ms || "0"))}
                    </Td>
                    <Td isNumeric fontFamily="mono" fontSize="xs">
                      {fmtMs(parseFloat(tl.max_latency_ms || "0"))}
                    </Td>
                  </Tr>
                ))}
              </Tbody>
            </Table>
          </Box>
        )}

        {/* HTTP Duration Metrics */}
        {httpDuration.length > 0 && (
          <Box>
            <Text fontSize="xs" fontWeight="600" color="gray.600" mb={2}>
              HTTP Client Duration (from http.client.duration histogram)
            </Text>
            <Table size="sm" variant="simple">
              <Thead>
                <Tr>
                  <Th fontSize="xs">Method</Th>
                  <Th fontSize="xs">Status</Th>
                  <Th fontSize="xs" isNumeric>Samples</Th>
                  <Th fontSize="xs" isNumeric>Avg</Th>
                  <Th fontSize="xs" isNumeric>Min</Th>
                  <Th fontSize="xs" isNumeric>Max</Th>
                </Tr>
              </Thead>
              <Tbody>
                {httpDuration.map((hd, i) => {
                  const sc = parseInt(hd.status_code || "0", 10);
                  const color = sc >= 400 ? "red" : sc >= 300 ? "yellow" : "green";
                  return (
                    <Tr key={i}>
                      <Td>
                        <Badge colorScheme="blue" variant="subtle" fontSize="xs">{hd.method}</Badge>
                      </Td>
                      <Td>
                        <Badge colorScheme={color} variant="subtle" fontSize="xs">{hd.status_code}</Badge>
                      </Td>
                      <Td isNumeric fontSize="xs">{hd.samples}</Td>
                      <Td isNumeric fontFamily="mono" fontSize="xs" fontWeight="600">
                        {fmtMs(parseFloat(hd.avg_duration_ms || "0"))}
                      </Td>
                      <Td isNumeric fontFamily="mono" fontSize="xs">
                        {fmtMs(parseFloat(hd.min_duration_ms || "0"))}
                      </Td>
                      <Td isNumeric fontFamily="mono" fontSize="xs">
                        {fmtMs(parseFloat(hd.max_duration_ms || "0"))}
                      </Td>
                    </Tr>
                  );
                })}
              </Tbody>
            </Table>
          </Box>
        )}

        {toolCalls.length === 0 && toolLatency.length === 0 && httpDuration.length === 0 && (
          <Text fontSize="sm" color="gray.400">No metric data available for this server</Text>
        )}
      </VStack>
    </Box>
  );
}

function ServerRow({ sv }: { sv: { service_name: string; tool_count: string; total_spans: string; tool_spans: string; http_spans: string; total_log_entries: string } }) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      <Tr cursor="pointer" onClick={() => setIsOpen(!isOpen)} _hover={{ bg: "soft.hover" }}>
        <Td w="30px" px={1}>
          <IconButton
            aria-label="toggle"
            icon={isOpen ? <FiChevronDown /> : <FiChevronRight />}
            size="xs"
            variant="ghost"
            onClick={(e) => { e.stopPropagation(); setIsOpen(!isOpen); }}
          />
        </Td>
        <Td fontWeight="500">
          <Badge colorScheme="purple" variant="subtle" fontSize="xs">{sv.service_name}</Badge>
        </Td>
        <Td isNumeric>{sv.tool_count}</Td>
        <Td isNumeric fontWeight="600">{parseInt(sv.total_spans || "0", 10).toLocaleString()}</Td>
        <Td isNumeric>{parseInt(sv.tool_spans || "0", 10).toLocaleString()}</Td>
        <Td isNumeric>{parseInt(sv.http_spans || "0", 10).toLocaleString()}</Td>
        <Td isNumeric>{parseInt(sv.total_log_entries || "0", 10).toLocaleString()}</Td>
      </Tr>
      <Tr>
        <Td colSpan={7} p={0} border={isOpen ? undefined : "none"}>
          <Collapse in={isOpen}>
            {isOpen && <ServerDetailPanel server={sv.service_name} />}
          </Collapse>
        </Td>
      </Tr>
    </>
  );
}

export default function OpsTab({ server }: { server?: string }) {
  const { days } = useTimeRange();
  const { data: summaryData, isLoading: loadingSummary } = useMcpServerSummary(server, days);
  const { data: toolData, isLoading: loadingTools } = useMcpToolStats(server, days);
  const { data: httpData, isLoading: loadingHttp } = useMcpHttpSummary(server, days);

  if (loadingSummary || loadingTools || loadingHttp) {
    return <Center py={8}><Spinner color="brand.500" /></Center>;
  }

  const servers = summaryData?.servers || [];
  const tools = toolData?.tools || [];
  const http = httpData?.http || [];

  // Compute totals from the summary endpoint (which has the correct counts)
  const totalSpans = servers.reduce((s, sv) => s + parseInt(sv.total_spans || "0", 10), 0);
  const totalToolCount = servers.reduce((s, sv) => s + parseInt(sv.tool_count || "0", 10), 0);
  const totalHttpCalls = servers.reduce((s, sv) => s + parseInt(sv.http_spans || "0", 10), 0);

  return (
    <VStack spacing={5} align="stretch">
      {/* Summary Cards */}
      <SimpleGrid columns={{ base: 1, md: 4 }} spacing={4}>
        {[
          { label: "MCP Servers", value: servers.length },
          { label: "Distinct Tools", value: totalToolCount },
          { label: "Total Spans", value: totalSpans.toLocaleString() },
          { label: "HTTP Outbound Calls", value: totalHttpCalls.toLocaleString() },
        ].map((s) => (
          <Card key={s.label}>
            <CardBody py={3}>
              <Stat size="sm">
                <StatLabel>{s.label}</StatLabel>
                <StatNumber fontSize="lg">{s.value}</StatNumber>
              </Stat>
            </CardBody>
          </Card>
        ))}
      </SimpleGrid>

      {/* Server Summary — expandable */}
      {servers.length > 0 && (
        <Box bg="surface.card" borderRadius="soft-lg" boxShadow="soft" border="1px solid" borderColor="soft.border" overflow="hidden">
          <Box px={5} pt={4} pb={2}>
            <HStack justify="space-between">
              <Box>
                <Text fontSize="sm" fontWeight="600" color="gray.700">Server Overview</Text>
                <Text fontSize="xs" color="gray.400">Click a row to expand metrics detail</Text>
              </Box>
            </HStack>
          </Box>
          <Table size="sm" variant="soft">
            <Thead>
              <Tr>
                <Th w="30px" px={1}></Th>
                <Th>Service Name</Th>
                <Th isNumeric>Tools</Th>
                <Th isNumeric>Total Spans</Th>
                <Th isNumeric>Tool Spans</Th>
                <Th isNumeric>HTTP Spans</Th>
                <Th isNumeric>Log Entries</Th>
              </Tr>
            </Thead>
            <Tbody>
              {servers.map((sv) => (
                <ServerRow key={sv.service_name} sv={sv} />
              ))}
            </Tbody>
          </Table>
        </Box>
      )}

      {/* Tool Performance */}
      {tools.length > 0 && (
        <Box bg="surface.card" borderRadius="soft-lg" boxShadow="soft" border="1px solid" borderColor="soft.border" overflow="hidden">
          <Box px={5} pt={4} pb={2}>
            <Text fontSize="sm" fontWeight="600" color="gray.700">Tool Performance (from spans)</Text>
          </Box>
          <Box overflowX="auto">
            <Table size="sm" variant="soft">
              <Thead>
                <Tr>
                  <Th>Tool</Th>
                  <Th isNumeric>Calls</Th>
                  <Th isNumeric>Success</Th>
                  <Th isNumeric>Failures</Th>
                  <Th isNumeric>Avg Latency</Th>
                  <Th isNumeric>P50</Th>
                  <Th isNumeric>P95</Th>
                </Tr>
              </Thead>
              <Tbody>
                {tools.map((t) => {
                  const total = parseInt(t.call_count || "0", 10);
                  const failures = parseInt(t.failure_count || "0", 10);
                  const successRate = total > 0 ? ((total - failures) / total * 100).toFixed(1) : "0";
                  return (
                    <Tr key={t.tool_name}>
                      <Td fontWeight="500">
                        <Text fontSize="sm" fontFamily="mono">{t.tool_name.replace("mcp.tool.", "")}</Text>
                      </Td>
                      <Td isNumeric fontWeight="600">{total}</Td>
                      <Td isNumeric>
                        <Badge colorScheme="green" variant="subtle" fontSize="xs">{successRate}%</Badge>
                      </Td>
                      <Td isNumeric>
                        <Text color={failures > 0 ? "red.500" : "gray.500"} fontWeight={failures > 0 ? "600" : "normal"}>
                          {failures}
                        </Text>
                      </Td>
                      <Td isNumeric fontFamily="mono" fontSize="xs">{fmtMs(parseFloat(t.avg_duration_ms || "0"))}</Td>
                      <Td isNumeric fontFamily="mono" fontSize="xs">{fmtMs(parseFloat(t.p50_duration_ms || "0"))}</Td>
                      <Td isNumeric fontFamily="mono" fontSize="xs">{fmtMs(parseFloat(t.p95_duration_ms || "0"))}</Td>
                    </Tr>
                  );
                })}
              </Tbody>
            </Table>
          </Box>
        </Box>
      )}

      {/* HTTP Outbound Summary */}
      {http.length > 0 && (
        <Box bg="surface.card" borderRadius="soft-lg" boxShadow="soft" border="1px solid" borderColor="soft.border" overflow="hidden">
          <Box px={5} pt={4} pb={2}>
            <Text fontSize="sm" fontWeight="600" color="gray.700">HTTP Outbound Dependencies (from spans)</Text>
          </Box>
          <Box overflowX="auto">
            <Table size="sm" variant="soft">
              <Thead>
                <Tr>
                  <Th>Domain</Th>
                  <Th>Method</Th>
                  <Th>Status</Th>
                  <Th isNumeric>Count</Th>
                  <Th isNumeric>Avg Latency</Th>
                  <Th isNumeric>P95</Th>
                </Tr>
              </Thead>
              <Tbody>
                {http.map((h, i) => {
                  const statusCode = parseInt(h.status_code || "0", 10);
                  const statusColor = statusCode >= 400 ? "red" : statusCode >= 300 ? "yellow" : "green";
                  return (
                    <Tr key={i}>
                      <Td maxW="250px" isTruncated fontSize="xs" fontFamily="mono">{h.domain}</Td>
                      <Td>
                        <Badge colorScheme="blue" variant="subtle" fontSize="xs">{h.method}</Badge>
                      </Td>
                      <Td>
                        <Badge colorScheme={statusColor} variant="subtle" fontSize="xs">{h.status_code}</Badge>
                      </Td>
                      <Td isNumeric fontWeight="600">{parseInt(h.call_count || "0", 10)}</Td>
                      <Td isNumeric fontFamily="mono" fontSize="xs">{fmtMs(parseFloat(h.avg_duration_ms || "0"))}</Td>
                      <Td isNumeric fontFamily="mono" fontSize="xs">{fmtMs(parseFloat(h.p95_duration_ms || "0"))}</Td>
                    </Tr>
                  );
                })}
              </Tbody>
            </Table>
          </Box>
        </Box>
      )}
    </VStack>
  );
}
