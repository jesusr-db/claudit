import { useAiGatewayPerformance } from "@/shared/hooks/useApi";
import { CHART_COLORS, formatNum, fmtMs, pivotByDay, DARK } from "@/shared/utils/gatewayColors";
import { formatAxisLabel } from "@/shared/utils/dates";
import { Box, SimpleGrid, Text, Spinner, Center, VStack } from "@chakra-ui/react";
import {
  ResponsiveContainer, BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, Tooltip, CartesianGrid, Legend,
} from "recharts";

const statusColorMap: Record<string, string> = {
  "200": "#22c55e",
  "429": "#f59e0b",
  "400": "#ef4444",
  "500": "#ef4444",
};

const axisProps = {
  tick: { fill: DARK.label, fontSize: 11 },
  axisLine: { stroke: DARK.border },
  tickLine: false as const,
};

const gridProps = { strokeDasharray: "3 3", stroke: DARK.border };

const tooltipStyle = {
  contentStyle: { background: DARK.card, border: `1px solid ${DARK.border}`, fontSize: 12, color: DARK.value },
};

function KpiCard({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <Box bg={DARK.card} border="1px solid" borderColor={DARK.border} borderRadius="xl" p={4}>
      <Text fontSize="xs" color={DARK.label} mb={1}>{label}</Text>
      <Text fontSize="2xl" fontWeight="bold" color={color ?? DARK.value}>{value}</Text>
    </Box>
  );
}

function ChartCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Box bg={DARK.card} border="1px solid" borderColor={DARK.border} borderRadius="xl" p={4}>
      <Text fontSize="xs" color={DARK.label} mb={2}>{title}</Text>
      {children}
    </Box>
  );
}

export default function PerformanceTab({ days, endpoint }: { days: number; endpoint: string | null }) {
  const { data, isLoading } = useAiGatewayPerformance(days, endpoint);

  if (isLoading) {
    return <Center py={20}><Spinner color={DARK.label} /></Center>;
  }

  if (!data) {
    return <Center py={20}><Text color={DARK.label}>No data</Text></Center>;
  }

  const { kpis, latency_by_endpoint, status_codes, tpm_by_endpoint, ttfb_by_endpoint, ttft_loss, errors_by_endpoint } = data;

  const latencyPivot = pivotByDay(latency_by_endpoint, "date", "endpoint_name", "median_latency_ms");
  const tpmPivot = pivotByDay(tpm_by_endpoint, "date", "endpoint_name", "tpm");
  const ttfbPivot = pivotByDay(ttfb_by_endpoint, "date", "endpoint_name", "median_ttfb_ms");

  const pieData = status_codes.map(s => ({ name: s.status_code, value: Number(s.count) }));

  const errorData = errors_by_endpoint.map(e => ({
    endpoint_name: e.endpoint_name,
    errors: Number(e.error_count),
  }));

  const ttftData = ttft_loss.map(t => ({
    endpoint_name: t.endpoint_name,
    avg_ttfb_ms: Number(t.avg_ttfb_ms),
    avg_generation_ms: Number(t.avg_generation_ms),
  }));

  return (
    <VStack spacing={4} align="stretch">
      {/* KPI Cards */}
      <SimpleGrid columns={3} spacing={4}>
        <KpiCard label="Median Latency" value={fmtMs(Number(kpis.median_latency_ms))} />
        <KpiCard label="Median TTFB" value={fmtMs(Number(kpis.median_ttfb_ms))} />
        <KpiCard label="Error Count" value={formatNum(Number(kpis.error_count))} color="#ef4444" />
      </SimpleGrid>

      {/* Row 1 */}
      <SimpleGrid columns={3} spacing={4}>
        {/* Median Latency by Endpoint */}
        <ChartCard title="Median Latency by Endpoint">
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={latencyPivot.data}>
              <CartesianGrid {...gridProps} />
              <XAxis dataKey="date" {...axisProps} tickFormatter={formatAxisLabel} />
              <YAxis {...axisProps} tickFormatter={(v: number) => fmtMs(v)} />
              <Tooltip {...tooltipStyle} labelFormatter={formatAxisLabel} />
              <Legend wrapperStyle={{ fontSize: 10, color: DARK.label }} />
              {latencyPivot.keys.map((k, i) => (
                <Line key={k} type="monotone" dataKey={k} stroke={CHART_COLORS[i % CHART_COLORS.length]} dot={false} strokeWidth={2} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        {/* Status Code Distribution */}
        <ChartCard title="Status Code Distribution">
          <ResponsiveContainer width="100%" height={180}>
            <PieChart>
              <Pie
                data={pieData}
                cx="50%"
                cy="50%"
                innerRadius={40}
                outerRadius={70}
                dataKey="value"
                nameKey="name"
                label={({ name, percent }: { name: string; percent: number }) => `${name} (${(percent * 100).toFixed(0)}%)`}
                labelLine={false}
              >
                {pieData.map((entry, i) => (
                  <Cell key={i} fill={statusColorMap[entry.name] || DARK.muted} />
                ))}
              </Pie>
              <Tooltip {...tooltipStyle} />
            </PieChart>
          </ResponsiveContainer>
        </ChartCard>

        {/* TPM by Endpoint */}
        <ChartCard title="TPM by Endpoint">
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={tpmPivot.data}>
              <CartesianGrid {...gridProps} />
              <XAxis dataKey="date" {...axisProps} tickFormatter={formatAxisLabel} />
              <YAxis {...axisProps} tickFormatter={(v: number) => formatNum(v)} />
              <Tooltip {...tooltipStyle} labelFormatter={formatAxisLabel} />
              <Legend wrapperStyle={{ fontSize: 10, color: DARK.label }} />
              {tpmPivot.keys.map((k, i) => (
                <Line key={k} type="monotone" dataKey={k} stroke={CHART_COLORS[i % CHART_COLORS.length]} dot={false} strokeWidth={2} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>
      </SimpleGrid>

      {/* Row 2 */}
      <SimpleGrid columns={3} spacing={4}>
        {/* Median TTFB by Endpoint */}
        <ChartCard title="Median TTFB by Endpoint">
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={ttfbPivot.data}>
              <CartesianGrid {...gridProps} />
              <XAxis dataKey="date" {...axisProps} tickFormatter={formatAxisLabel} />
              <YAxis {...axisProps} tickFormatter={(v: number) => fmtMs(v)} />
              <Tooltip {...tooltipStyle} labelFormatter={formatAxisLabel} />
              <Legend wrapperStyle={{ fontSize: 10, color: DARK.label }} />
              {ttfbPivot.keys.map((k, i) => (
                <Line key={k} type="monotone" dataKey={k} stroke={CHART_COLORS[i % CHART_COLORS.length]} dot={false} strokeWidth={2} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        {/* TTFT Loss */}
        <ChartCard title="TTFT Loss">
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={ttftData}>
              <CartesianGrid {...gridProps} />
              <XAxis dataKey="endpoint_name" {...axisProps} />
              <YAxis {...axisProps} tickFormatter={(v: number) => fmtMs(v)} />
              <Tooltip {...tooltipStyle} />
              <Legend wrapperStyle={{ fontSize: 10, color: DARK.label }} />
              <Bar dataKey="avg_ttfb_ms" stackId="a" fill={CHART_COLORS[0]} name="TTFB" />
              <Bar dataKey="avg_generation_ms" stackId="a" fill={CHART_COLORS[1]} name="Generation" />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        {/* Error Rate by Endpoint */}
        <ChartCard title="Error Rate by Endpoint">
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={errorData}>
              <CartesianGrid {...gridProps} />
              <XAxis dataKey="endpoint_name" {...axisProps} />
              <YAxis {...axisProps} tickFormatter={(v: number) => formatNum(v)} />
              <Tooltip {...tooltipStyle} />
              <Bar dataKey="errors" fill="#ef4444" />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </SimpleGrid>
    </VStack>
  );
}
