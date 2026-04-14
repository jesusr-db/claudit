import { Box, SimpleGrid, Text, Spinner, Center } from "@chakra-ui/react";
import {
  ResponsiveContainer, AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, Tooltip, CartesianGrid,
} from "recharts";
import { useAiGatewayTokenConsumption } from "@/shared/hooks/useApi";
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

/* ── Section header ── */
function SectionHeader({ label }: { label: string }) {
  return (
    <Text fontSize="13px" color={DARK.label} textTransform="uppercase" letterSpacing="1px" mb={4} borderBottom={`1px solid ${DARK.border}`} pb={2}>
      {label}
    </Text>
  );
}

/* ── Main component ── */
export default function TokenConsumptionTab({ days, endpoint }: { days: number; endpoint: string | null }) {
  const { data, isLoading } = useAiGatewayTokenConsumption(days, endpoint);

  if (isLoading) return <Center py={20}><Spinner color="cyan.400" /></Center>;
  if (!data) return <Center py={20}><Text color={DARK.label}>No data for selected time range</Text></Center>;

  const { kpis, daily = [], by_destination_type = [], weekly_by_endpoint = [], top_endpoints = [], top_models = [], top_users = [] } = data;

  const dailyParsed = daily.map((d) => ({ date: d.date, tokens: Number(d.tokens) }));
  const destData = by_destination_type.map((d) => ({ type: d.destination_type ?? "Unknown", tokens: Number(d.tokens) }));
  const weeklyPivot = pivotByDay(weekly_by_endpoint, "week", "endpoint_name", "tokens");

  return (
    <Box>
      {/* KPI Cards */}
      <SimpleGrid columns={3} spacing={4} mb={4}>
        <KpiCard label="Total Tokens" value={formatNum(Number(kpis.total_tokens))} />
        <KpiCard label="Total Requests" value={formatNum(Number(kpis.total_requests))} />
        <KpiCard label="Avg Tokens per Request" value={formatNum(Number(kpis.avg_tokens_per_request))} />
      </SimpleGrid>

      {/* Token Overview */}
      <SectionHeader label="Token Overview" />

      <SimpleGrid columns={2} spacing={4} mb={4}>
        <ChartCard title="Token Consumption over Time">
          <ResponsiveContainer width="100%" height={180}>
            <AreaChart data={dailyParsed}>
              <defs>
                <linearGradient id="tokenGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#6366f1" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="#6366f1" stopOpacity={0.05} />
                </linearGradient>
              </defs>
              <CartesianGrid {...axisProps.cartesianGrid} />
              <XAxis {...axisProps.xAxis} />
              <YAxis {...axisProps.yAxis} />
              <Tooltip {...axisProps.tooltip} />
              <Area type="monotone" dataKey="tokens" stroke="#6366f1" fill="url(#tokenGrad)" />
            </AreaChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Tokens by Destination Type">
          <ResponsiveContainer width="100%" height={160}>
            <BarChart layout="vertical" data={destData}>
              <CartesianGrid {...axisProps.cartesianGrid} />
              <YAxis type="category" dataKey="type" width={140} tick={{ fontSize: 10, fill: DARK.muted }} />
              <XAxis type="number" tick={{ fontSize: 10, fill: DARK.muted }} tickFormatter={(v: number) => formatNum(v)} />
              <Tooltip {...axisProps.tooltip} />
              <Bar dataKey="tokens" fill={CHART_COLORS[0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </SimpleGrid>

      {/* Token Breakdown */}
      <SectionHeader label="Token Breakdown" />

      {/* Full-width: Weekly Token Consumption by Endpoint */}
      <Box mb={4}>
        <ChartCard title="Weekly Token Consumption by Endpoint">
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={weeklyPivot.data}>
              <CartesianGrid {...axisProps.cartesianGrid} />
              <XAxis dataKey="date" tick={{ fontSize: 10, fill: DARK.muted }} tickFormatter={(v: string) => formatAxisLabel(String(v))} />
              <YAxis tick={{ fontSize: 10, fill: DARK.muted }} tickFormatter={(v: number) => formatNum(v)} />
              <Tooltip {...axisProps.tooltip} />
              {weeklyPivot.keys.map((key, i) => (
                <Bar key={key} stackId="weekly" dataKey={key} fill={CHART_COLORS[i % CHART_COLORS.length]} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </Box>

      {/* Top tables */}
      <SimpleGrid columns={3} spacing={4}>
        <TableCard
          title="Top Endpoints"
          headers={["Endpoint", "Tokens"]}
          rows={top_endpoints.map((r) => [r.endpoint_name, formatNum(Number(r.tokens))])}
        />
        <TableCard
          title="Top Models"
          headers={["Model", "Tokens"]}
          rows={top_models.map((r) => [r.model, formatNum(Number(r.tokens))])}
        />
        <TableCard
          title="Top Users"
          headers={["User", "Tokens"]}
          rows={top_users.map((r) => [
            r.requester.length > 20 ? r.requester.slice(0, 20) + "..." : r.requester,
            formatNum(Number(r.tokens)),
          ])}
        />
      </SimpleGrid>
    </Box>
  );
}
