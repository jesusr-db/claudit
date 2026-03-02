import { useState } from "react";
import {
  Box,
  VStack,
  HStack,
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
} from "@chakra-ui/react";
import { FiChevronDown, FiChevronRight } from "react-icons/fi";
import { useMcpServerLogs } from "@/shared/hooks/useApi";
import { useTimeRange } from "@/shared/context/TimeRangeContext";

function fmtTime(ts: string): string {
  if (!ts) return "\u2014";
  try {
    return new Date(ts).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return ts;
  }
}

function severityColor(severity: string): string {
  const s = (severity || "").toUpperCase();
  if (s === "ERROR" || s === "FATAL") return "red";
  if (s === "WARN" || s === "WARNING") return "orange";
  if (s === "INFO") return "blue";
  if (s === "DEBUG" || s === "TRACE") return "gray";
  return "gray";
}

function parseAttrs(raw: string | Record<string, string>): Record<string, string> {
  try {
    return typeof raw === "string" ? JSON.parse(raw) : raw || {};
  } catch {
    return {};
  }
}

function extractToolName(attrs: Record<string, string>): string | null {
  return attrs["tool_name"] || attrs["mcp.tool.name"] || null;
}

function LogRow({ log }: { log: { timestamp: string; severity: string; body: string; attributes: string; tool_name?: string } }) {
  const [isOpen, setIsOpen] = useState(false);

  const attrs = parseAttrs(log.attributes);
  const hasAttrs = Object.keys(attrs).length > 0;
  const toolName = log.tool_name || extractToolName(attrs);

  return (
    <>
      <Tr cursor={hasAttrs ? "pointer" : undefined} onClick={() => hasAttrs && setIsOpen(!isOpen)}>
        <Td w="30px" px={1}>
          {hasAttrs && (
            <IconButton
              aria-label="toggle"
              icon={isOpen ? <FiChevronDown /> : <FiChevronRight />}
              size="xs"
              variant="ghost"
              onClick={(e) => { e.stopPropagation(); setIsOpen(!isOpen); }}
            />
          )}
        </Td>
        <Td fontSize="xs" fontFamily="mono" whiteSpace="nowrap" color="gray.500">{fmtTime(log.timestamp)}</Td>
        <Td>
          <Badge colorScheme={severityColor(log.severity)} variant="subtle" fontSize="xs">
            {log.severity || "UNKNOWN"}
          </Badge>
        </Td>
        <Td fontSize="xs" fontFamily="mono" color="purple.600" maxW="150px" isTruncated>
          {toolName || "\u2014"}
        </Td>
        <Td>
          <Text fontSize="sm" noOfLines={2}>{log.body || "\u2014"}</Text>
        </Td>
      </Tr>
      {hasAttrs && (
        <Tr>
          <Td colSpan={5} p={0} border="none">
            <Collapse in={isOpen}>
              <Box bg="gray.50" px={6} py={3} borderBottom="1px solid" borderColor="soft.border">
                <Text fontSize="xs" fontWeight="600" color="gray.600" mb={2}>Attributes</Text>
                <VStack spacing={1} align="stretch">
                  {Object.entries(attrs).map(([key, val]) => (
                    <HStack key={key} spacing={2} fontSize="xs">
                      <Text color="gray.500" fontWeight="600" minW="140px" fontFamily="mono">{key}</Text>
                      <Text color="gray.700" wordBreak="break-all">{String(val)}</Text>
                    </HStack>
                  ))}
                </VStack>
              </Box>
            </Collapse>
          </Td>
        </Tr>
      )}
    </>
  );
}

export default function LogsTab({ server }: { server?: string }) {
  const { days } = useTimeRange();
  const { data, isLoading } = useMcpServerLogs(server, 200, days);

  if (isLoading) {
    return <Center py={8}><Spinner color="brand.500" /></Center>;
  }

  const logs = data?.logs || [];

  return (
    <VStack spacing={5} align="stretch">
      <Box bg="surface.card" borderRadius="soft-lg" boxShadow="soft" border="1px solid" borderColor="soft.border" overflow="hidden">
        <Box px={5} pt={4} pb={2}>
          <Text fontSize="sm" fontWeight="600" color="gray.700">Server Logs</Text>
          <Text fontSize="xs" color="gray.400">{logs.length} log entries (click rows with attributes to expand)</Text>
        </Box>
        <Box overflowX="auto">
          <Table size="sm" variant="soft">
            <Thead>
              <Tr>
                <Th w="30px" px={1}></Th>
                <Th>Timestamp</Th>
                <Th>Severity</Th>
                <Th>Tool</Th>
                <Th>Body</Th>
              </Tr>
            </Thead>
            <Tbody>
              {logs.length === 0 ? (
                <Tr><Td colSpan={5}><Text color="gray.400" fontSize="sm">No logs recorded</Text></Td></Tr>
              ) : logs.map((log, i) => (
                <LogRow key={i} log={log} />
              ))}
            </Tbody>
          </Table>
        </Box>
      </Box>
    </VStack>
  );
}
