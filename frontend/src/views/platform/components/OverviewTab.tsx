import { Box, SimpleGrid, Text, Spinner, Center } from "@chakra-ui/react";
import {
  ResponsiveContainer, BarChart, Bar, LineChart, Line,
  XAxis, YAxis, Tooltip, CartesianGrid,
} from "recharts";
import { useAiGatewayOverview } from "@/shared/hooks/useApi";
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
function KpiCard({ label, value }: { label: string; value: string | number }) {
  return (
    <Box bg={DARK.card} borderRadius="10px" border="1px solid" borderColor={DARK.border} p={5}>
      <Text fontSize="11px" color={DARK.label} textTransform="uppercase" letterSpacing="0.5px">{label}</Text>
      <Text fontSize="28px" fontWeight="600" color={DARK.value} mt={1}>{value}</Text>
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

/* ── Table card ── */
function TableCard({ title, headers, rows }: {
  title: string;
  headers: string[];
  rows: React.ReactNode[][];
}) {
  return (
    <Box bg={DARK.card} borderRadius="10px" border="1px solid" borderColor={DARK.border} p={4}>
      <Text fontSize="12px" color={DARK.label} mb={3}>{title}</Text>
      <table style={{ width: "100%", fontSize: "11px", color: DARK.value, borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ color: DARK.muted, borderBottom: `1px solid ${DARK.border}` }}>
            {headers.map((h) => (
              <th key={h} style={{ textAlign: "left", padding: "4px 6px", fontWeight: 500 }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((cells, i) => (
            <tr key={i} style={{ borderBottom: `1px solid ${DARK.rowBorder}` }}>
              {cells.map((c, j) => (
                <td key={j} style={{ padding: "4px 6px" }}>{c}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </Box>
  );
}

/* ── Main component ── */
export default function OverviewTab({ days, endpoint }: { days: number; endpoint: string | null }) {
  const { data, isLoading } = useAiGatewayOverview(days, endpoint);

  if (isLoading) return <Center py={20}><Spinner color="cyan.400" /></Center>;
  if (!data) return <Center py={20}><Text color={DARK.label}>No data for selected time range</Text></Center>;

  const { kpis, daily, top_endpoints, top_models, top_users, latency_by_endpoint } = data;

  const dailyParsed = daily.map((d) => ({
    date: d.date,
    requests: Number(d.requests),
    tokens: Number(d.tokens),
    unique_users: Number(d.unique_users),
  }));

  const ttfbPivot = pivotByDay(latency_by_endpoint, "date", "endpoint_name", "avg_ttfb_ms");
  const latencyPivot = pivotByDay(latency_by_endpoint, "date", "endpoint_name", "avg_latency_ms");

  return (
    <Box>
      {/* KPI Cards */}
      <SimpleGrid columns={3} spacing={4} mb={4}>
        <KpiCard label="Total Requests" value={formatNum(Number(kpis.total_requests))} />
        <KpiCard label="Total Tokens" value={formatNum(Number(kpis.total_tokens))} />
        <KpiCard label="Total Unique Users" value={kpis.total_unique_users} />
      </SimpleGrid>

      {/* Charts Row 1 */}
      <SimpleGrid columns={3} spacing={4} mb={4}>
        <ChartCard title="Daily Requests">
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={dailyParsed}>
              <CartesianGrid {...axisProps.cartesianGrid} />
              <XAxis {...axisProps.xAxis} />
              <YAxis {...axisProps.yAxis} />
              <Tooltip {...axisProps.tooltip} />
              <Bar dataKey="requests" fill={CHART_COLORS[0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Daily Token Usage">
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={dailyParsed}>
              <CartesianGrid {...axisProps.cartesianGrid} />
              <XAxis {...axisProps.xAxis} />
              <YAxis {...axisProps.yAxis} />
              <Tooltip {...axisProps.tooltip} />
              <Bar dataKey="tokens" fill={CHART_COLORS[2]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Daily Unique Users">
          <ResponsiveContainer width="100%" height={160}>
            <LineChart data={dailyParsed}>
              <CartesianGrid {...axisProps.cartesianGrid} />
              <XAxis {...axisProps.xAxis} />
              <YAxis {...axisProps.yAxis} />
              <Tooltip {...axisProps.tooltip} />
              <Line type="monotone" dataKey="unique_users" stroke={CHART_COLORS[0]} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>
      </SimpleGrid>

      {/* Tables Row */}
      <SimpleGrid columns={3} spacing={4} mb={4}>
        <TableCard
          title="Top Endpoints"
          headers={["Endpoint", "Tokens", "Requests"]}
          rows={top_endpoints.map((r) => [r.endpoint_name, formatNum(Number(r.total_tokens)), r.requests])}
        />
        <TableCard
          title="Top Models"
          headers={["Model", "Tokens", "Requests"]}
          rows={top_models.map((r) => [r.model, formatNum(Number(r.total_tokens)), r.requests])}
        />
        <TableCard
          title="Top Users"
          headers={["User", "Requests", "Tokens"]}
          rows={top_users.map((r) => [
            r.requester.length > 20 ? r.requester.slice(0, 20) + "..." : r.requester,
            r.requests,
            formatNum(Number(r.total_tokens)),
          ])}
        />
      </SimpleGrid>

      {/* Multi-line Charts Row */}
      <SimpleGrid columns={2} spacing={4}>
        <ChartCard title="TTFB by Endpoint">
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={ttfbPivot.data}>
              <CartesianGrid {...axisProps.cartesianGrid} />
              <XAxis {...axisProps.xAxis} />
              <YAxis {...axisProps.yAxis} />
              <Tooltip {...axisProps.tooltip} />
              {ttfbPivot.keys.map((key, i) => (
                <Line key={key} type="monotone" dataKey={key} stroke={CHART_COLORS[i % CHART_COLORS.length]} dot={false} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Latency by Endpoint">
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={latencyPivot.data}>
              <CartesianGrid {...axisProps.cartesianGrid} />
              <XAxis {...axisProps.xAxis} />
              <YAxis {...axisProps.yAxis} />
              <Tooltip {...axisProps.tooltip} />
              {latencyPivot.keys.map((key, i) => (
                <Line key={key} type="monotone" dataKey={key} stroke={CHART_COLORS[i % CHART_COLORS.length]} dot={false} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>
      </SimpleGrid>
    </Box>
  );
}
