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
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  Progress,
  Tooltip,
  Center,
} from "@chakra-ui/react";
import {
  useBillingSummary,
  useBillingDaily,
  useQueryStats,
  useQueryDaily,
  useAiGatewayModels,
  useAiGatewayDaily,
  useAiGatewayErrors,
} from "@/shared/hooks/useApi";

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`;
}

function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString();
}

function fmtMs(ms: number): string {
  if (ms < 1000) return `${ms.toFixed(0)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

/* ── Billing Tab ── */

function BillingSection() {
  const { data: summary, isLoading: loadingSummary } = useBillingSummary(30);
  const { data: daily, isLoading: loadingDaily } = useBillingDaily(30);

  if (loadingSummary || loadingDaily) return <Center py={8}><Spinner color="brand.500" /></Center>;

  const products = summary?.products || [];
  const dailyData = daily?.daily || [];
  const totalDBU = products.reduce((s, p) => s + parseFloat(p.total_usage || "0"), 0);

  const dailyByDate = new Map<string, number>();
  for (const d of dailyData) {
    const cur = dailyByDate.get(d.usage_date) || 0;
    dailyByDate.set(d.usage_date, cur + parseFloat(d.total_usage || "0"));
  }
  const sortedDates = Array.from(dailyByDate.entries()).sort(
    (a, b) => a[0].localeCompare(b[0])
  );
  const maxDaily = Math.max(...sortedDates.map(([, v]) => v), 1);

  return (
    <VStack spacing={5} align="stretch">
      <SimpleGrid columns={{ base: 1, md: 3 }} spacing={4}>
        {[
          { label: "Total DBU (30d)", value: formatNumber(totalDBU) },
          { label: "Products", value: products.length },
          { label: "Avg DBU/day", value: sortedDates.length > 0 ? formatNumber(totalDBU / sortedDates.length) : "\u2014" },
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

      <Box bg="surface.card" borderRadius="soft-lg" boxShadow="soft" border="1px solid" borderColor="soft.border" p={5}>
        <Text fontSize="sm" fontWeight="600" mb={3} color="gray.700">Daily DBU Consumption (30d)</Text>
        <HStack spacing="2px" align="end" h="80px">
          {sortedDates.map(([date, val]) => (
            <Tooltip key={date} label={`${date}: ${formatNumber(val)} DBU`} fontSize="xs" hasArrow>
              <Box
                flex={1} bg="brand.400" borderRadius="4px"
                h={`${Math.max((val / maxDaily) * 100, 2)}%`}
                _hover={{ bg: "brand.500" }} cursor="pointer"
                transition="all 0.15s ease"
              />
            </Tooltip>
          ))}
        </HStack>
        <HStack justify="space-between" mt={1}>
          <Text fontSize="10px" color="gray.400" fontFamily="mono">{sortedDates[0]?.[0] || ""}</Text>
          <Text fontSize="10px" color="gray.400" fontFamily="mono">{sortedDates[sortedDates.length - 1]?.[0] || ""}</Text>
        </HStack>
      </Box>

      <Box bg="surface.card" borderRadius="soft-lg" boxShadow="soft" border="1px solid" borderColor="soft.border" overflow="hidden">
        <Box px={5} pt={4} pb={2}>
          <Text fontSize="sm" fontWeight="600" color="gray.700">DBU by Product</Text>
        </Box>
        <Table size="sm" variant="soft">
          <Thead>
            <Tr>
              <Th>Product</Th>
              <Th isNumeric>DBU</Th>
              <Th w="200px">Share</Th>
              <Th isNumeric>Active Days</Th>
            </Tr>
          </Thead>
          <Tbody>
            {products.map((p) => {
              const usage = parseFloat(p.total_usage || "0");
              const pct = totalDBU > 0 ? (usage / totalDBU) * 100 : 0;
              return (
                <Tr key={p.product}>
                  <Td>
                    <Badge colorScheme={
                      p.product === "MODEL_SERVING" ? "purple"
                        : p.product === "SQL" ? "blue"
                        : p.product === "APPS" ? "teal" : "gray"
                    } variant="subtle" fontSize="xs">{p.product}</Badge>
                  </Td>
                  <Td isNumeric fontWeight="600">{formatNumber(usage)}</Td>
                  <Td>
                    <HStack spacing={2}>
                      <Progress value={pct} size="sm" flex={1} borderRadius="full" colorScheme="blue" bg="surface.muted" />
                      <Text fontSize="xs" color="gray.500" minW="36px" fontFamily="mono">{pct.toFixed(1)}%</Text>
                    </HStack>
                  </Td>
                  <Td isNumeric>{p.active_days}</Td>
                </Tr>
              );
            })}
          </Tbody>
        </Table>
      </Box>
    </VStack>
  );
}

/* ── Query History Tab ── */

function QuerySection() {
  const { data: stats, isLoading: loadingStats } = useQueryStats(7);
  const { data: daily, isLoading: loadingDaily } = useQueryDaily(7);

  if (loadingStats || loadingDaily) return <Center py={8}><Spinner color="brand.500" /></Center>;

  const queryStats = stats?.stats || [];
  const dailyData = daily?.daily || [];

  const totalQueries = dailyData.reduce((s, d) => s + parseInt(d.total_queries || "0", 10), 0);
  const totalFailed = dailyData.reduce((s, d) => s + parseInt(d.failed || "0", 10), 0);
  const avgP95 = dailyData.length > 0
    ? dailyData.reduce((s, d) => s + parseFloat(d.p95_duration_ms || "0"), 0) / dailyData.length
    : 0;

  const maxQueries = Math.max(...dailyData.map((d) => parseInt(d.total_queries || "0", 10)), 1);

  return (
    <VStack spacing={5} align="stretch">
      <SimpleGrid columns={{ base: 1, md: 3 }} spacing={4}>
        {[
          { label: "Total Queries (7d)", value: formatNumber(totalQueries) },
          { label: "Failed", value: formatNumber(totalFailed), color: totalFailed > 0 ? "red.500" : undefined },
          { label: "Avg P95 Latency", value: `${(avgP95 / 1000).toFixed(1)}s` },
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
        <Text fontSize="sm" fontWeight="600" mb={3} color="gray.700">Daily Query Volume (7d)</Text>
        <HStack spacing="4px" align="end" h="80px">
          {dailyData
            .sort((a, b) => a.query_date.localeCompare(b.query_date))
            .map((d) => {
              const count = parseInt(d.total_queries || "0", 10);
              const failed = parseInt(d.failed || "0", 10);
              return (
                <Tooltip key={d.query_date} label={`${d.query_date}: ${count} queries, ${failed} failed`} fontSize="xs" hasArrow>
                  <Box flex={1} position="relative" cursor="pointer">
                    <Box bg="brand.400" borderRadius="4px"
                      h={`${Math.max((count / maxQueries) * 80, 2)}px`}
                      _hover={{ bg: "brand.500" }}
                      transition="all 0.15s ease"
                    />
                    {failed > 0 && (
                      <Box position="absolute" bottom={0} left={0} right={0}
                        bg="red.400" borderRadius="4px"
                        h={`${Math.max((failed / maxQueries) * 80, 1)}px`}
                        pointerEvents="none"
                      />
                    )}
                  </Box>
                </Tooltip>
              );
            })}
        </HStack>
      </Box>

      <Box bg="surface.card" borderRadius="soft-lg" boxShadow="soft" border="1px solid" borderColor="soft.border" overflow="hidden">
        <Box px={5} pt={4} pb={2}>
          <Text fontSize="sm" fontWeight="600" color="gray.700">Queries by Client Application (7d)</Text>
        </Box>
        <Table size="sm" variant="soft">
          <Thead>
            <Tr>
              <Th>Client</Th>
              <Th>Status</Th>
              <Th isNumeric>Count</Th>
              <Th isNumeric>Avg Duration</Th>
              <Th isNumeric>Avg Exec</Th>
              <Th isNumeric>Avg Queue</Th>
              <Th isNumeric>Data Read</Th>
            </Tr>
          </Thead>
          <Tbody>
            {queryStats.map((q, i) => (
              <Tr key={i}>
                <Td maxW="200px" isTruncated fontWeight="500">{q.client_application}</Td>
                <Td>
                  <Badge colorScheme={
                    q.execution_status === "FINISHED" ? "green"
                      : q.execution_status === "FAILED" ? "red" : "yellow"
                  } variant="subtle" fontSize="xs">{q.execution_status}</Badge>
                </Td>
                <Td isNumeric fontWeight="600">{formatNumber(parseInt(q.query_count, 10))}</Td>
                <Td isNumeric fontFamily="mono" fontSize="xs">{(parseFloat(q.avg_total_ms || "0") / 1000).toFixed(1)}s</Td>
                <Td isNumeric fontFamily="mono" fontSize="xs">{(parseFloat(q.avg_exec_ms || "0") / 1000).toFixed(1)}s</Td>
                <Td isNumeric fontFamily="mono" fontSize="xs">{(parseFloat(q.avg_queue_ms || "0") / 1000).toFixed(1)}s</Td>
                <Td isNumeric fontSize="xs">{formatBytes(parseInt(q.total_bytes_read || "0", 10))}</Td>
              </Tr>
            ))}
          </Tbody>
        </Table>
      </Box>
    </VStack>
  );
}

/* ── AI Gateway Tab ── */

function AiGatewaySection() {
  const { data: modelData, isLoading: loadingModels } = useAiGatewayModels(7);
  const { data: dailyData, isLoading: loadingDaily } = useAiGatewayDaily(7);
  const { data: errorData, isLoading: loadingErrors } = useAiGatewayErrors(7);

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

  const sortedDaily = [...daily].sort((a, b) => a.request_date.localeCompare(b.request_date));
  const maxReqs = Math.max(...sortedDaily.map((d) => parseInt(d.total_requests || "0", 10)), 1);

  return (
    <VStack spacing={5} align="stretch">
      <SimpleGrid columns={{ base: 2, md: 5 }} spacing={4}>
        {[
          { label: "Requests (7d)", value: formatNumber(totalRequests) },
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
        <Text fontSize="sm" fontWeight="600" mb={3} color="gray.700">Daily Request Volume (7d)</Text>
        <HStack spacing="4px" align="end" h="80px">
          {sortedDaily.map((d) => {
            const reqs = parseInt(d.total_requests || "0", 10);
            const failed = parseInt(d.failed || "0", 10);
            return (
              <Tooltip
                key={d.request_date}
                label={`${d.request_date}\n${reqs} requests, ${failed} failed\nAvg: ${fmtMs(parseFloat(d.avg_latency_ms || "0"))}, TTFB: ${fmtMs(parseFloat(d.avg_ttfb_ms || "0"))}, P95: ${fmtMs(parseFloat(d.p95_latency_ms || "0"))}`}
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
          <Text fontSize="10px" color="gray.400" fontFamily="mono">{sortedDaily[0]?.request_date || ""}</Text>
          <Text fontSize="10px" color="gray.400" fontFamily="mono">{sortedDaily[sortedDaily.length - 1]?.request_date || ""}</Text>
        </HStack>
      </Box>

      <Box bg="surface.card" borderRadius="soft-lg" boxShadow="soft" border="1px solid" borderColor="soft.border" overflow="hidden">
        <Box px={5} pt={4} pb={2}>
          <Text fontSize="sm" fontWeight="600" color="gray.700">Model Performance (7d)</Text>
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
                        <Text color="gray.400">\u2014</Text>
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
            <Text fontSize="sm" fontWeight="600" color="gray.700">Gateway Errors (7d)</Text>
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
  return (
    <Box p={8}>
      <VStack spacing={6} align="stretch">
        <Box>
          <Heading size="lg" mb={1}>Platform Usage</Heading>
          <Text color="gray.500" fontSize="sm">
            Databricks system tables: billing, query performance, and AI Gateway
          </Text>
        </Box>
        <Tabs variant="soft-rounded" colorScheme="brand">
          <TabList>
            <Tab>Billing</Tab>
            <Tab>Query History</Tab>
            <Tab>AI Gateway</Tab>
          </TabList>
          <TabPanels>
            <TabPanel px={0} pt={5}>
              <BillingSection />
            </TabPanel>
            <TabPanel px={0} pt={5}>
              <QuerySection />
            </TabPanel>
            <TabPanel px={0} pt={5}>
              <AiGatewaySection />
            </TabPanel>
          </TabPanels>
        </Tabs>
      </VStack>
    </Box>
  );
}
