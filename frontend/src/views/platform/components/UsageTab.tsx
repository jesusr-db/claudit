import { Box, SimpleGrid, Text, Spinner, Center, VStack } from "@chakra-ui/react";
import {
  ResponsiveContainer, BarChart, Bar, LineChart, Line,
  XAxis, YAxis, Tooltip, CartesianGrid,
} from "recharts";
import { useAiGatewayUsage } from "@/shared/hooks/useApi";
import { CHART_COLORS, formatNum, pivotByDay, DARK } from "@/shared/utils/gatewayColors";
import { formatAxisLabel } from "@/shared/utils/dates";

/* ── axis / tooltip shared props ── */
const axisProps = {
  cartesianGrid: { strokeDasharray: "3 3", stroke: DARK.border, vertical: false } as const,
  xAxis: { dataKey: "date" as const, tick: { fontSize: 10, fill: DARK.muted }, tickFormatter: (v: string) => formatAxisLabel(String(v)) },
  yAxis: { tick: { fontSize: 10, fill: DARK.muted }, tickFormatter: (v: number) => formatNum(v) },
  tooltip: { contentStyle: { background: DARK.card, border: `1px solid ${DARK.border}`, fontSize: 12, color: DARK.value } },
};

/* ── KPI card ── */
function KpiCard({ label, value, subtitle }: { label: string; value: string | number; subtitle?: string }) {
  return (
    <Box bg={DARK.card} borderRadius="10px" border="1px solid" borderColor={DARK.border} p={5}>
      <Text fontSize="11px" color={DARK.label} textTransform="uppercase" letterSpacing="0.5px">{label}</Text>
      <Text fontSize="28px" fontWeight="600" color={DARK.value} mt={1}>{value}</Text>
      {subtitle && <Text fontSize="10px" color={DARK.muted} mt={1}>{subtitle}</Text>}
    </Box>
  );
}

/* ── Chart wrapper ── */
function ChartCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Box bg={DARK.card} borderRadius="10px" border="1px solid" borderColor={DARK.border} p={4}>
      <Text fontSize="12px" color={DARK.label} mb={3}>{title}</Text>
      {children}
    </Box>
  );
}

/* ── Main component ── */
export default function UsageTab({ days, endpoint }: { days: number; endpoint: string | null }) {
  const { data, isLoading } = useAiGatewayUsage(days, endpoint);

  if (isLoading) return <Center py={20}><Spinner color="cyan.400" /></Center>;
  if (!data) return <Center py={20}><Text color={DARK.label}>No data for selected time range</Text></Center>;

  const { kpis, tokens_by_endpoint, tokens_by_model, tokens_by_user, input_output, cache_hit_by_endpoint } = data;

  // Pivot data for stacked/multi-line charts
  const epPivot = pivotByDay(tokens_by_endpoint, "date", "endpoint_name", "tokens");
  const modelPivot = pivotByDay(tokens_by_model, "date", "model", "tokens");
  const userPivot = pivotByDay(tokens_by_user, "date", "requester", "tokens");

  // Input vs Output daily data
  const ioParsed = input_output.map((d) => ({
    date: d.date,
    input: Number(d.input_tokens),
    output: Number(d.output_tokens),
  }));

  // Input/Output ratio
  const totalInput = input_output.reduce((sum, d) => sum + Number(d.input_tokens), 0);
  const totalOutput = input_output.reduce((sum, d) => sum + Number(d.output_tokens), 0);
  const totalIO = totalInput + totalOutput;
  const inputPct = totalIO > 0 ? (totalInput / totalIO) * 100 : 0;
  const outputPct = totalIO > 0 ? (totalOutput / totalIO) * 100 : 0;

  // Cache hit data
  const cacheData = cache_hit_by_endpoint.map((c) => ({
    endpoint_name: c.endpoint_name,
    cache_hit_pct: Number(c.cache_hit_pct),
  }));

  return (
    <Box>
      {/* KPI Cards */}
      <SimpleGrid columns={3} spacing={4} mb={4}>
        <KpiCard label="Total Endpoints" value={kpis.total_endpoints} />
        <KpiCard label="Active Endpoints" value={kpis.total_endpoints} subtitle="with traffic in window" />
        <KpiCard label="Active Users" value={kpis.active_users} />
      </SimpleGrid>

      {/* Row 1: Token breakdowns */}
      <SimpleGrid columns={3} spacing={4} mb={4}>
        <ChartCard title="Token Usage by Endpoint">
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={epPivot.data}>
              <CartesianGrid {...axisProps.cartesianGrid} />
              <XAxis {...axisProps.xAxis} />
              <YAxis {...axisProps.yAxis} />
              <Tooltip {...axisProps.tooltip} />
              {epPivot.keys.map((key, i) => (
                <Bar key={key} dataKey={key} stackId="ep" fill={CHART_COLORS[i % CHART_COLORS.length]} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Token Usage by Model">
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={modelPivot.data}>
              <CartesianGrid {...axisProps.cartesianGrid} />
              <XAxis {...axisProps.xAxis} />
              <YAxis {...axisProps.yAxis} />
              <Tooltip {...axisProps.tooltip} />
              {modelPivot.keys.map((key, i) => (
                <Bar key={key} dataKey={key} stackId="model" fill={CHART_COLORS[i % CHART_COLORS.length]} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Token Usage by User">
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={userPivot.data}>
              <CartesianGrid {...axisProps.cartesianGrid} />
              <XAxis {...axisProps.xAxis} />
              <YAxis {...axisProps.yAxis} />
              <Tooltip {...axisProps.tooltip} />
              {userPivot.keys.map((key, i) => (
                <Line
                  key={key}
                  type="monotone"
                  dataKey={key}
                  stroke={CHART_COLORS[i % CHART_COLORS.length]}
                  dot={false}
                  name={key.length > 20 ? key.slice(0, 20) + "..." : key}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>
      </SimpleGrid>

      {/* Row 2: I/O and Cache */}
      <SimpleGrid columns={3} spacing={4}>
        <ChartCard title="Daily Input vs Output">
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={ioParsed}>
              <CartesianGrid {...axisProps.cartesianGrid} />
              <XAxis {...axisProps.xAxis} />
              <YAxis {...axisProps.yAxis} />
              <Tooltip {...axisProps.tooltip} />
              <Bar dataKey="input" stackId="io" fill={CHART_COLORS[0]} name="Input" />
              <Bar dataKey="output" stackId="io" fill={CHART_COLORS[1]} name="Output" />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Input / Output Ratio">
          <VStack spacing={4} align="stretch" pt={2}>
            <Box>
              <Text fontSize="11px" color={DARK.muted} mb={1}>Input Tokens</Text>
              <Box display="flex" alignItems="center" gap={2}>
                <Box flex="1" bg={DARK.bg} borderRadius="4px" h="18px" overflow="hidden">
                  <Box bg={CHART_COLORS[0]} h="100%" w={`${inputPct}%`} borderRadius="4px" />
                </Box>
                <Text fontSize="12px" color={DARK.value} minW="60px" textAlign="right">{formatNum(totalInput)}</Text>
              </Box>
            </Box>
            <Box>
              <Text fontSize="11px" color={DARK.muted} mb={1}>Output Tokens</Text>
              <Box display="flex" alignItems="center" gap={2}>
                <Box flex="1" bg={DARK.bg} borderRadius="4px" h="18px" overflow="hidden">
                  <Box bg={CHART_COLORS[1]} h="100%" w={`${outputPct}%`} borderRadius="4px" />
                </Box>
                <Text fontSize="12px" color={DARK.value} minW="60px" textAlign="right">{formatNum(totalOutput)}</Text>
              </Box>
            </Box>
            <Box textAlign="center" pt={2}>
              <Text fontSize="24px" fontWeight="600" color={DARK.value}>
                {totalOutput > 0 ? (totalInput / totalOutput).toFixed(2) : "N/A"}
              </Text>
              <Text fontSize="10px" color={DARK.muted}>input : output</Text>
            </Box>
          </VStack>
        </ChartCard>

        <ChartCard title="Cache Hit Rate by Endpoint">
          {cacheData.length > 0 ? (
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={cacheData} layout="vertical">
                <CartesianGrid {...axisProps.cartesianGrid} />
                <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 10, fill: DARK.muted }} tickFormatter={(v: number) => `${v}%`} />
                <YAxis type="category" dataKey="endpoint_name" width={120} tick={{ fontSize: 10, fill: DARK.muted }} />
                <Tooltip {...axisProps.tooltip} formatter={(v: number) => `${v.toFixed(1)}%`} />
                <Bar dataKey="cache_hit_pct" fill={CHART_COLORS[0]} name="Cache Hit %" />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <Center h="180px"><Text fontSize="12px" color={DARK.muted}>No cache data</Text></Center>
          )}
        </ChartCard>
      </SimpleGrid>
    </Box>
  );
}
