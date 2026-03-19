import {
  Box,
  VStack,
  HStack,
  Text,
  Spinner,
  Center,
  Badge,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
} from "@chakra-ui/react";
import { Link } from "react-router-dom";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RTooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import {
  useKpiCostTrend,
  useKpiModelComparison,
  useKpiCostSessions,
  useKpiTokenWaste,
} from "@/shared/hooks/useApi";
import { MetricTooltip, METRIC_METHODOLOGY } from "@/shared/components/MetricTooltip";
import { formatAxisLabel } from "@/shared/utils/dates";

function formatCost(val: string | number): string {
  const n = typeof val === "string" ? parseFloat(val) : val;
  if (isNaN(n)) return "-";
  if (n >= 1) return `$${n.toFixed(2)}`;
  if (n >= 0.01) return `$${n.toFixed(3)}`;
  return `$${n.toFixed(4)}`;
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString();
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

export default function CostTab({ days = 30 }: { days?: number }) {
  const { data: trendData, isLoading: trendLoading } = useKpiCostTrend(days);
  const { data: modelsData, isLoading: modelsLoading } = useKpiModelComparison(days);
  const { data: sessionsData, isLoading: sessionsLoading } = useKpiCostSessions(days);
  const { data: wasteData, isLoading: wasteLoading } = useKpiTokenWaste(days);

  const trendChart = (trendData?.trend || []).map((t) => {
    const raw = t.date || "";
    const label = formatAxisLabel(raw);
    return {
      date: label,
      daily_cost: parseFloat(t.daily_cost || "0"),
      input_tokens: parseInt(t.input_tokens || "0", 10),
      output_tokens: parseInt(t.output_tokens || "0", 10),
      cache_read_tokens: parseInt(t.cache_read_tokens || "0", 10),
    };
  });

  const modelChart = (modelsData?.models || []).map((m) => ({
    model: (m.model || "").replace(/^.*\//, ""),
    total_cost: parseFloat(m.total_cost || "0"),
    cache_hit_pct: parseFloat(m.cache_hit_pct || "0"),
    request_count: parseInt(m.request_count || "0", 10),
  }));

  return (
    <VStack spacing={5} align="stretch">
      {/* Cost Trend */}
      <CardBox>
        <Text fontSize="sm" fontWeight="600" color="gray.700" mb={3}>Daily Cost Trend</Text>
        {trendLoading ? (
          <Center py={8}><Spinner color="brand.500" size="sm" /></Center>
        ) : (
          <Box h="250px">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={trendChart}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" vertical={false} />
                <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#94A3B8" }} tickLine={false} axisLine={{ stroke: "#E2E8F0" }} />
                <YAxis tick={{ fontSize: 11, fill: "#94A3B8" }} tickLine={false} axisLine={false} tickFormatter={(v) => `$${v}`} width={55} />
                <RTooltip
                  contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #E2E8F0" }}
                  formatter={(value: number, name: string) => {
                    if (name === "daily_cost") return [formatCost(value), "Cost"];
                    return [formatTokens(value), name.replace("_", " ")];
                  }}
                />
                <Area type="monotone" dataKey="daily_cost" stroke="#6366F1" fill="#6366F1" fillOpacity={0.15} strokeWidth={2} name="daily_cost" />
              </AreaChart>
            </ResponsiveContainer>
          </Box>
        )}
      </CardBox>

      {/* Model Comparison */}
      <CardBox>
        <Text fontSize="sm" fontWeight="600" color="gray.700" mb={3}>Model Cost Comparison</Text>
        {modelsLoading ? (
          <Center py={8}><Spinner color="brand.500" size="sm" /></Center>
        ) : (
          <Box h="220px">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={modelChart} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 11, fill: "#94A3B8" }} tickFormatter={(v) => `$${v}`} />
                <YAxis dataKey="model" type="category" tick={{ fontSize: 11, fill: "#94A3B8" }} width={120} />
                <RTooltip
                  contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #E2E8F0" }}
                  formatter={(value: number, name: string) => {
                    if (name === "total_cost") return [formatCost(value), "Total Cost"];
                    return [`${value}%`, "Cache Hit %"];
                  }}
                />
                <Legend />
                <Bar dataKey="total_cost" fill="#6366F1" name="Total Cost" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Box>
        )}
      </CardBox>

      <HStack spacing={5} align="start" flexWrap={{ base: "wrap", lg: "nowrap" }}>
        {/* Top Sessions by Cost */}
        <CardBox>
          <Text fontSize="sm" fontWeight="600" color="gray.700" mb={3}>Top Sessions by Cost</Text>
          {sessionsLoading ? (
            <Center py={8}><Spinner color="brand.500" size="sm" /></Center>
          ) : (
            <Box overflowX="auto">
              <Table size="sm" variant="simple">
                <Thead>
                  <Tr>
                    <Th>Session</Th>
                    <Th isNumeric>Cost</Th>
                    <Th isNumeric>Prompts</Th>
                    <Th isNumeric>Cache %</Th>
                    <Th isNumeric>$/Prompt</Th>
                  </Tr>
                </Thead>
                <Tbody>
                  {(sessionsData?.sessions || []).map((s) => (
                    <Tr key={s.session_id} _hover={{ bg: "soft.hover" }}>
                      <Td>
                        <Link to={`/sessions/${s.session_id}`}>
                          <Text fontSize="xs" color="brand.600" fontFamily="mono" _hover={{ textDecoration: "underline" }}>
                            {s.first_prompt ? (s.first_prompt.length > 30 ? s.first_prompt.substring(0, 30) + "..." : s.first_prompt) : s.session_id.substring(0, 12)}
                          </Text>
                        </Link>
                      </Td>
                      <Td isNumeric fontFamily="mono" fontSize="xs">{formatCost(s.total_cost)}</Td>
                      <Td isNumeric fontSize="xs">{s.prompt_count}</Td>
                      <Td isNumeric fontSize="xs">{parseFloat(s.cache_hit_pct || "0").toFixed(1)}%</Td>
                      <Td isNumeric fontFamily="mono" fontSize="xs">{formatCost(s.cost_per_prompt)}</Td>
                    </Tr>
                  ))}
                </Tbody>
              </Table>
            </Box>
          )}
        </CardBox>

        {/* Token Waste Alerts */}
        <CardBox>
          <MetricTooltip label="Token Waste Signals" methodology={METRIC_METHODOLOGY.tokenWaste}>
            <Text fontSize="sm" fontWeight="600" color="gray.700">Token Waste Signals</Text>
          </MetricTooltip>
          <Box mb={3} />
          {wasteLoading ? (
            <Center py={8}><Spinner color="brand.500" size="sm" /></Center>
          ) : (wasteData?.waste || []).length === 0 ? (
            <Text fontSize="sm" color="gray.400">No waste signals detected</Text>
          ) : (
            <Box overflowX="auto">
              <Table size="sm" variant="simple">
                <Thead>
                  <Tr>
                    <Th>Severity</Th>
                    <Th isNumeric>Input Tokens</Th>
                    <Th isNumeric>Output</Th>
                    <Th isNumeric>Cost</Th>
                    <Th>Model</Th>
                  </Tr>
                </Thead>
                <Tbody>
                  {(wasteData?.waste || []).slice(0, 15).map((w, i) => {
                    const cost = parseFloat(w.cost_usd || "0");
                    const severity = cost > 0.5 ? "red" : "yellow";
                    return (
                      <Tr key={i} _hover={{ bg: "soft.hover" }}>
                        <Td>
                          <Badge colorScheme={severity} fontSize="10px">{severity === "red" ? "High" : "Medium"}</Badge>
                        </Td>
                        <Td isNumeric fontFamily="mono" fontSize="xs">{formatTokens(parseInt(w.input_tokens || "0", 10))}</Td>
                        <Td isNumeric fontFamily="mono" fontSize="xs">{formatTokens(parseInt(w.output_tokens || "0", 10))}</Td>
                        <Td isNumeric fontFamily="mono" fontSize="xs">{formatCost(w.cost_usd)}</Td>
                        <Td fontSize="xs">{(w.model || "").replace(/^.*\//, "")}</Td>
                      </Tr>
                    );
                  })}
                </Tbody>
              </Table>
            </Box>
          )}
        </CardBox>
      </HStack>
    </VStack>
  );
}
