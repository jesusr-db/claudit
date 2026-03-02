import {
  Box,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Spinner,
  Text,
  Badge,
  Link as ChakraLink,
  Center,
} from "@chakra-ui/react";
import { Link } from "react-router-dom";
import { useToolPerformance } from "@/shared/hooks/useApi";
import { useTimeRange } from "@/shared/context/TimeRangeContext";

function fmt(val: string | null | undefined): string {
  return parseFloat(val || "0").toFixed(0);
}

function fmtBytes(val: string | null | undefined): string {
  const bytes = parseInt(val || "0", 10);
  if (bytes > 1_000_000) return `${(bytes / 1_000_000).toFixed(1)} MB`;
  if (bytes > 1_000) return `${(bytes / 1_000).toFixed(1)} KB`;
  return `${bytes} B`;
}

export function isMcpTool(name: string): boolean {
  return name === "mcp_tool" || name.startsWith("mcp__") || name === "ListMcpResourcesTool";
}

export default function McpToolsTab() {
  const { days } = useTimeRange();
  const { data, isLoading, error } = useToolPerformance(days);

  if (isLoading) return <Center py={8}><Spinner color="brand.500" /></Center>;
  if (error) return <Text color="red.500">Failed to load tool performance</Text>;

  const tools = (data?.tools || []).filter((t) => isMcpTool(t.tool_name));

  if (tools.length === 0) {
    return <Text color="gray.400" fontSize="sm">No MCP tool calls recorded</Text>;
  }

  return (
    <Box bg="surface.card" borderRadius="soft-lg" boxShadow="soft" border="1px solid" borderColor="soft.border" overflow="hidden">
      <Table size="sm" variant="soft">
        <Thead>
          <Tr>
            <Th>Tool</Th>
            <Th isNumeric>Calls</Th>
            <Th isNumeric>Success %</Th>
            <Th isNumeric>Avg</Th>
            <Th isNumeric>p50</Th>
            <Th isNumeric>p95</Th>
            <Th isNumeric>p99</Th>
            <Th isNumeric>Failures</Th>
            <Th isNumeric>Data</Th>
          </Tr>
        </Thead>
        <Tbody>
          {tools.map((t) => {
            const rate = parseFloat(t.success_rate || "0");
            return (
              <Tr key={t.tool_name}>
                <Td>
                  <ChakraLink
                    as={Link}
                    to={`/mcp-tools/${encodeURIComponent(t.tool_name)}`}
                    color="brand.600"
                    fontWeight="500"
                    _hover={{ color: "brand.700" }}
                  >
                    {t.tool_name}
                  </ChakraLink>
                  <Badge ml={2} colorScheme="purple" variant="subtle" fontSize="xs">
                    MCP
                  </Badge>
                </Td>
                <Td isNumeric fontWeight="600">{t.call_count}</Td>
                <Td isNumeric>
                  <Text
                    color={rate >= 95 ? "green.600" : rate >= 80 ? "yellow.600" : "red.600"}
                    fontWeight="600"
                  >
                    {rate.toFixed(1)}%
                  </Text>
                </Td>
                <Td isNumeric fontFamily="mono" fontSize="xs">{fmt(t.avg_duration_ms)}ms</Td>
                <Td isNumeric fontFamily="mono" fontSize="xs">{fmt(t.p50_duration_ms)}ms</Td>
                <Td isNumeric fontFamily="mono" fontSize="xs">{fmt(t.p95_duration_ms)}ms</Td>
                <Td isNumeric fontFamily="mono" fontSize="xs">{fmt(t.p99_duration_ms)}ms</Td>
                <Td isNumeric>{t.failure_count}</Td>
                <Td isNumeric fontSize="xs">{fmtBytes(t.total_result_bytes)}</Td>
              </Tr>
            );
          })}
        </Tbody>
      </Table>
    </Box>
  );
}
