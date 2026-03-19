import {
  Box,
  VStack,
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
  Code,
} from "@chakra-ui/react";
import {
  useMcpHttpDetail,
  useMcpAudit,
  useMcpErrors,
} from "@/shared/hooks/useApi";
import { useTimeRange } from "@/shared/context/TimeRangeContext";
import { formatTimestamp } from "@/shared/utils/dates";

function fmtMs(ms: number): string {
  if (ms < 1000) return `${ms.toFixed(0)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function fmtTime(ts: string): string {
  if (!ts) return "\u2014";
  try {
    return formatTimestamp(ts);
  } catch {
    return ts;
  }
}

export default function SecurityTab({ server }: { server?: string }) {
  const { days } = useTimeRange();
  const { data: httpData, isLoading: loadingHttp } = useMcpHttpDetail(server, 200, days);
  const { data: auditData, isLoading: loadingAudit } = useMcpAudit(server, 200, days);
  const { data: errorData, isLoading: loadingErrors } = useMcpErrors(server, 200, days);

  if (loadingHttp || loadingAudit || loadingErrors) {
    return <Center py={8}><Spinner color="brand.500" /></Center>;
  }

  const httpCalls = httpData?.calls || [];
  const invocations = auditData?.invocations || [];
  const errors = errorData?.errors || [];

  return (
    <VStack spacing={5} align="stretch">
      {/* HTTP Audit Log */}
      <Box bg="surface.card" borderRadius="soft-lg" boxShadow="soft" border="1px solid" borderColor="soft.border" overflow="hidden">
        <Box px={5} pt={4} pb={2}>
          <Text fontSize="sm" fontWeight="600" color="gray.700">HTTP Outbound Audit Log</Text>
          <Text fontSize="xs" color="gray.400">Every external API call made by the MCP server</Text>
        </Box>
        <Box overflowX="auto">
          <Table size="sm" variant="soft">
            <Thead>
              <Tr>
                <Th>Timestamp</Th>
                <Th>Method</Th>
                <Th>URL</Th>
                <Th>Status</Th>
                <Th isNumeric>Duration</Th>
              </Tr>
            </Thead>
            <Tbody>
              {httpCalls.length === 0 ? (
                <Tr><Td colSpan={5}><Text color="gray.400" fontSize="sm">No HTTP calls recorded</Text></Td></Tr>
              ) : httpCalls.map((h, i) => {
                const statusCode = parseInt(h.status_code || "0", 10);
                const statusColor = statusCode >= 400 ? "red" : statusCode >= 300 ? "yellow" : "green";
                return (
                  <Tr key={i}>
                    <Td fontSize="xs" fontFamily="mono" whiteSpace="nowrap" color="gray.500">{fmtTime(h.timestamp)}</Td>
                    <Td>
                      <Badge colorScheme="blue" variant="subtle" fontSize="xs">{h.method}</Badge>
                    </Td>
                    <Td maxW="400px" isTruncated>
                      <Code fontSize="xs" bg="transparent" color="gray.700">{h.url}</Code>
                    </Td>
                    <Td>
                      <Badge colorScheme={statusColor} variant="subtle" fontSize="xs">{h.status_code}</Badge>
                    </Td>
                    <Td isNumeric fontFamily="mono" fontSize="xs">{fmtMs(parseFloat(h.duration_ms || "0"))}</Td>
                  </Tr>
                );
              })}
            </Tbody>
          </Table>
        </Box>
      </Box>

      {/* Tool Invocation Audit */}
      <Box bg="surface.card" borderRadius="soft-lg" boxShadow="soft" border="1px solid" borderColor="soft.border" overflow="hidden">
        <Box px={5} pt={4} pb={2}>
          <Text fontSize="sm" fontWeight="600" color="gray.700">Tool Invocation Log</Text>
          <Text fontSize="xs" color="gray.400">Every MCP tool execution with trace correlation</Text>
        </Box>
        <Box overflowX="auto">
          <Table size="sm" variant="soft">
            <Thead>
              <Tr>
                <Th>Timestamp</Th>
                <Th>Tool</Th>
                <Th>Status</Th>
                <Th isNumeric>Duration</Th>
                <Th>Trace ID</Th>
              </Tr>
            </Thead>
            <Tbody>
              {invocations.length === 0 ? (
                <Tr><Td colSpan={5}><Text color="gray.400" fontSize="sm">No invocations recorded</Text></Td></Tr>
              ) : invocations.map((inv, i) => (
                <Tr key={i}>
                  <Td fontSize="xs" fontFamily="mono" whiteSpace="nowrap" color="gray.500">{fmtTime(inv.timestamp)}</Td>
                  <Td fontWeight="500">
                    <Text fontSize="sm" fontFamily="mono">{inv.tool_name.replace("mcp.tool.", "")}</Text>
                  </Td>
                  <Td>
                    <Badge
                      colorScheme={inv.status === "ERROR" ? "red" : "green"}
                      variant="subtle" fontSize="xs"
                    >
                      {inv.status}
                    </Badge>
                  </Td>
                  <Td isNumeric fontFamily="mono" fontSize="xs">{fmtMs(parseFloat(inv.duration_ms || "0"))}</Td>
                  <Td>
                    <Code fontSize="xs" bg="transparent" color="gray.400">{inv.trace_id?.slice(0, 16)}...</Code>
                  </Td>
                </Tr>
              ))}
            </Tbody>
          </Table>
        </Box>
      </Box>

      {/* Error Events */}
      {errors.length > 0 && (
        <Box bg="surface.card" borderRadius="soft-lg" boxShadow="soft" border="1px solid" borderColor="soft.border" overflow="hidden">
          <Box px={5} pt={4} pb={2}>
            <Text fontSize="sm" fontWeight="600" color="gray.700">Error Events</Text>
            <Text fontSize="xs" color="gray.400">Spans with error status or HTTP 4xx/5xx</Text>
          </Box>
          <Box overflowX="auto">
            <Table size="sm" variant="soft">
              <Thead>
                <Tr>
                  <Th>Timestamp</Th>
                  <Th>Span</Th>
                  <Th>Kind</Th>
                  <Th>Status</Th>
                  <Th>HTTP</Th>
                  <Th>Message</Th>
                  <Th isNumeric>Duration</Th>
                </Tr>
              </Thead>
              <Tbody>
                {errors.map((e, i) => (
                  <Tr key={i}>
                    <Td fontSize="xs" fontFamily="mono" whiteSpace="nowrap" color="gray.500">{fmtTime(e.timestamp)}</Td>
                    <Td fontWeight="500" fontSize="sm" fontFamily="mono">{e.span_name}</Td>
                    <Td>
                      <Badge colorScheme="gray" variant="subtle" fontSize="xs">{e.kind}</Badge>
                    </Td>
                    <Td>
                      <Badge colorScheme="red" variant="subtle" fontSize="xs">{e.status}</Badge>
                    </Td>
                    <Td>
                      {e.http_status ? (
                        <Badge colorScheme="red" variant="subtle" fontSize="xs">{e.http_status}</Badge>
                      ) : (
                        <Text color="gray.400">{"\u2014"}</Text>
                      )}
                    </Td>
                    <Td maxW="200px" isTruncated fontSize="xs" color="gray.500">{e.status_message || "\u2014"}</Td>
                    <Td isNumeric fontFamily="mono" fontSize="xs">{fmtMs(parseFloat(e.duration_ms || "0"))}</Td>
                  </Tr>
                ))}
              </Tbody>
            </Table>
          </Box>
        </Box>
      )}
    </VStack>
  );
}
