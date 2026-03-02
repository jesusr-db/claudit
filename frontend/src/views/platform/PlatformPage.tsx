import {
  Box,
  Heading,
  VStack,
  HStack,
  Spinner,
  Text,
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
  Tooltip,
  Center,
} from "@chakra-ui/react";
import {
  useAiGatewayModels,
  useAiGatewayDaily,
  useAiGatewayErrors,
} from "@/shared/hooks/useApi";
import { useTimeRange } from "@/shared/context/TimeRangeContext";

function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString();
}

function fmtMs(ms: number): string {
  if (ms < 1000) return `${ms.toFixed(0)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function fmtDateLabel(raw?: string): string {
  if (!raw) return "";
  if (raw.length <= 10) return raw; // "2026-03-02"
  return raw.slice(11, 16); // "HH:MM" from "yyyy-MM-dd HH:mm" or "yyyy-MM-dd HH:00"
}

/* ── AI Gateway Section ── */

function AiGatewaySection({ days }: { days: number }) {
  const { data: modelData, isLoading: loadingModels } = useAiGatewayModels(days);
  const { data: dailyData, isLoading: loadingDaily } = useAiGatewayDaily(days);
  const { data: errorData, isLoading: loadingErrors } = useAiGatewayErrors(days);

  if (loadingModels || loadingDaily || loadingErrors) return <Center py={8}><Spinner color="brand.500" /></Center>;

  const models = modelData?.models || [];
  const daily = dailyData?.daily || [];
  const errors = errorData?.errors || [];

  const totalRequests = models.reduce((s, m) => s + parseInt(m.call_count || "0", 10), 0);
  const totalErrors = models.reduce((s, m) => s + parseInt(m.error_count || "0", 10), 0);
  const totalTokens = models.reduce((s, m) => s + parseInt(m.total_tokens || "0", 10), 0);
  const totalCacheRead = models.reduce(
    (s, m) => s + parseInt(m.total_cache_read_tokens || "0", 10), 0
  );
  const totalCacheCreation = models.reduce(
    (s, m) => s + parseInt(m.total_cache_creation_tokens || "0", 10), 0
  );
  const cacheHitRate = totalTokens > 0 ? (totalCacheRead / totalTokens) * 100 : 0;

  const sortedDaily = [...daily].sort((a, b) => (a.request_date || "").localeCompare(b.request_date || ""));
  const maxReqs = Math.max(...sortedDaily.map((d) => parseInt(d.total_requests || "0", 10)), 1);

  return (
    <VStack spacing={5} align="stretch">
      <SimpleGrid columns={{ base: 2, md: 5 }} spacing={4}>
        {[
          { label: "Requests", value: formatNumber(totalRequests) },
          { label: "Errors", value: totalErrors, color: totalErrors > 0 ? "red.500" : undefined },
          { label: "Total Tokens", value: formatNumber(totalTokens) },
          { label: "Cache Hit Rate", value: `${cacheHitRate.toFixed(1)}%` },
          { label: "Cache Created", value: formatNumber(totalCacheCreation) },
        ].map((s) => (
          <Card key={s.label}>
            <CardBody py={3}>
              <Stat size="sm">
                <StatLabel>{s.label}</StatLabel>
                <StatNumber fontSize="lg" color={s.color}>{s.value}</StatNumber>
              </Stat>
            </CardBody>
          </Card>
        ))}
      </SimpleGrid>

      <Box bg="surface.card" borderRadius="soft-lg" boxShadow="soft" border="1px solid" borderColor="soft.border" p={5}>
        <Text fontSize="sm" fontWeight="600" mb={3} color="gray.700">
          {days < 1 ? "Request Volume (5 min)" : days <= 1 ? "Hourly Request Volume" : "Daily Request Volume"}
        </Text>
        <HStack spacing="4px" align="end" h="80px">
          {sortedDaily.map((d) => {
            const reqs = parseInt(d.total_requests || "0", 10);
            const failed = parseInt(d.failed || "0", 10);
            return (
              <Tooltip
                key={d.request_date}
                label={`${fmtDateLabel(d.request_date) || d.request_date}\n${reqs} requests, ${failed} failed\nAvg: ${fmtMs(parseFloat(d.avg_latency_ms || "0"))}, TTFB: ${fmtMs(parseFloat(d.avg_ttfb_ms || "0"))}, P95: ${fmtMs(parseFloat(d.p95_latency_ms || "0"))}`}
                whiteSpace="pre-wrap" fontSize="xs" hasArrow
              >
                <Box flex={1} position="relative" cursor="pointer">
                  <Box
                    bg="purple.400" borderRadius="4px"
                    h={`${Math.max((reqs / maxReqs) * 80, 2)}px`}
                    _hover={{ bg: "purple.500" }}
                    transition="all 0.15s ease"
                  />
                  {failed > 0 && (
                    <Box position="absolute" bottom={0} left={0} right={0}
                      bg="red.400" borderRadius="4px"
                      h={`${Math.max((failed / maxReqs) * 80, 1)}px`}
                      pointerEvents="none"
                    />
                  )}
                </Box>
              </Tooltip>
            );
          })}
        </HStack>
        <HStack justify="space-between" mt={1}>
          <Text fontSize="10px" color="gray.400" fontFamily="mono">{fmtDateLabel(sortedDaily[0]?.request_date)}</Text>
          <Text fontSize="10px" color="gray.400" fontFamily="mono">{fmtDateLabel(sortedDaily[sortedDaily.length - 1]?.request_date)}</Text>
        </HStack>
      </Box>

      <Box bg="surface.card" borderRadius="soft-lg" boxShadow="soft" border="1px solid" borderColor="soft.border" overflow="hidden">
        <Box px={5} pt={4} pb={2}>
          <Text fontSize="sm" fontWeight="600" color="gray.700">Model Performance</Text>
        </Box>
        <Box overflowX="auto">
          <Table size="sm" variant="soft">
            <Thead>
              <Tr>
                <Th>Model</Th>
                <Th>Endpoint</Th>
                <Th isNumeric>Calls</Th>
                <Th isNumeric>Errors</Th>
                <Th isNumeric>Avg Latency</Th>
                <Th isNumeric>P95</Th>
                <Th isNumeric>Avg TTFB</Th>
                <Th isNumeric>Tokens</Th>
                <Th isNumeric>Cache Read</Th>
              </Tr>
            </Thead>
            <Tbody>
              {models.map((m, i) => {
                const errs = parseInt(m.error_count || "0", 10);
                const cacheRead = parseInt(m.total_cache_read_tokens || "0", 10);
                const mTokens = parseInt(m.total_tokens || "0", 10);
                const mCacheRate = mTokens > 0 ? (cacheRead / mTokens) * 100 : 0;
                return (
                  <Tr key={i}>
                    <Td maxW="180px" isTruncated>
                      <Badge
                        colorScheme={
                          m.model?.includes("Claude") ? "purple"
                            : m.model?.includes("GPT") ? "green"
                            : m.model?.includes("Gemini") ? "blue"
                            : "gray"
                        }
                        variant="subtle"
                        fontSize="xs"
                      >
                        {m.model}
                      </Badge>
                    </Td>
                    <Td maxW="150px" isTruncated fontSize="xs" color="gray.500">
                      {m.endpoint_name}
                    </Td>
                    <Td isNumeric fontWeight="600">{m.call_count}</Td>
                    <Td isNumeric>
                      <Text color={errs > 0 ? "red.500" : "gray.500"} fontWeight={errs > 0 ? "600" : "normal"}>
                        {errs}
                      </Text>
                    </Td>
                    <Td isNumeric fontFamily="mono" fontSize="xs">{fmtMs(parseFloat(m.avg_latency_ms || "0"))}</Td>
                    <Td isNumeric fontFamily="mono" fontSize="xs">{fmtMs(parseFloat(m.p95_latency_ms || "0"))}</Td>
                    <Td isNumeric fontFamily="mono" fontSize="xs">{fmtMs(parseFloat(m.avg_ttfb_ms || "0"))}</Td>
                    <Td isNumeric fontFamily="mono" fontSize="xs">{formatNumber(mTokens)}</Td>
                    <Td isNumeric>
                      {cacheRead > 0 ? (
                        <Tooltip label={`${formatNumber(cacheRead)} tokens cached`} fontSize="xs" hasArrow>
                          <Text color="green.600" fontWeight="600" cursor="help">{mCacheRate.toFixed(0)}%</Text>
                        </Tooltip>
                      ) : (
                        <Text color="gray.400">{"\u2014"}</Text>
                      )}
                    </Td>
                  </Tr>
                );
              })}
            </Tbody>
          </Table>
        </Box>
      </Box>

      {errors.length > 0 && (
        <Box bg="surface.card" borderRadius="soft-lg" boxShadow="soft" border="1px solid" borderColor="soft.border" overflow="hidden">
          <Box px={5} pt={4} pb={2}>
            <Text fontSize="sm" fontWeight="600" color="gray.700">Gateway Errors</Text>
          </Box>
          <Table size="sm" variant="soft">
            <Thead>
              <Tr>
                <Th>Model</Th>
                <Th>Endpoint</Th>
                <Th>Status</Th>
                <Th isNumeric>Count</Th>
                <Th isNumeric>Avg Latency</Th>
              </Tr>
            </Thead>
            <Tbody>
              {errors.map((e, i) => (
                <Tr key={i}>
                  <Td maxW="180px" isTruncated fontWeight="500">{e.model}</Td>
                  <Td maxW="150px" isTruncated fontSize="xs" color="gray.500">{e.endpoint_name}</Td>
                  <Td>
                    <Badge colorScheme="red" variant="subtle" fontSize="xs">{e.status_code}</Badge>
                  </Td>
                  <Td isNumeric fontWeight="600">{e.error_count}</Td>
                  <Td isNumeric fontFamily="mono" fontSize="xs">{fmtMs(parseFloat(e.avg_latency_ms || "0"))}</Td>
                </Tr>
              ))}
            </Tbody>
          </Table>
        </Box>
      )}
    </VStack>
  );
}

/* ── Main Page ── */

export default function PlatformPage() {
  const { days } = useTimeRange();

  return (
    <Box p={8}>
      <VStack spacing={6} align="stretch">
        <Box>
          <Heading size="lg" mb={1}>Platform Usage</Heading>
          <Text color="gray.500" fontSize="sm">
            Databricks AI Gateway performance and usage
          </Text>
        </Box>
        <AiGatewaySection days={days} />
      </VStack>
    </Box>
  );
}
