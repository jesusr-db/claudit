import { useState } from "react";
import { useAiGatewayCodingAgents } from "@/shared/hooks/useApi";
import { CHART_COLORS, formatNum, fmtMs, pivotByDay, DARK } from "@/shared/utils/gatewayColors";
import { formatAxisLabel } from "@/shared/utils/dates";
import { Box, SimpleGrid, Text, Spinner, Center, VStack, HStack, Select } from "@chakra-ui/react";
import {
  ResponsiveContainer, LineChart, Line, PieChart, Pie, Cell,
  BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid,
} from "recharts";

/* ── axis / tooltip shared props ── */
const axisProps = {
  cartesianGrid: { strokeDasharray: "3 3", stroke: DARK.border, vertical: false } as const,
  xAxis: { dataKey: "date" as const, tick: { fontSize: 10, fill: DARK.muted }, tickFormatter: (v: string) => formatAxisLabel(String(v)) },
  yAxis: { tick: { fontSize: 10, fill: DARK.muted }, tickFormatter: (v: number) => formatNum(v) },
  yAxisMs: { tick: { fontSize: 10, fill: DARK.muted }, tickFormatter: (v: number) => fmtMs(v) },
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

/* ── Agent color badge ── */
function AgentBadge({ agent, agents }: { agent: string; agents: string[] }) {
  const idx = agents.indexOf(agent);
  const color = CHART_COLORS[idx >= 0 ? idx % CHART_COLORS.length : 0];
  return (
    <span style={{
      background: `${color}22`,
      color,
      padding: "2px 8px",
      borderRadius: "4px",
      fontSize: "10px",
    }}>
      {agent}
    </span>
  );
}

/* ── Main component ── */
export default function CodingAgentsTab({ days, endpoint }: { days: number; endpoint: string | null }) {
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const { data, isLoading } = useAiGatewayCodingAgents(days, endpoint, selectedAgent);

  if (isLoading) return <Center py={20}><Spinner color="cyan.400" /></Center>;
  if (!data) return <Center py={20}><Text color={DARK.label}>No data for selected time range</Text></Center>;

  const { kpis, summary, daily, by_endpoint, by_model, user_analytics } = data;

  const agents = summary.map((s) => s.coding_agent);

  /* ── Pivoted line chart data ── */
  const requestsPivot = pivotByDay(daily, "date", "coding_agent", "requests");
  const latencyPivot = pivotByDay(daily, "date", "coding_agent", "avg_latency_ms");

  /* ── Token distribution bar (single stacked horizontal bar) ── */
  const totalTokens = summary.reduce((acc, s) => acc + Number(s.total_tokens), 0);
  const tokenShares = summary.map((s) => ({
    name: s.coding_agent,
    value: Number(s.total_tokens),
    pct: totalTokens > 0 ? ((Number(s.total_tokens) / totalTokens) * 100).toFixed(1) : "0",
  }));

  /* ── By-endpoint pie data ── */
  const endpointPie = by_endpoint.map((e) => ({ name: e.endpoint_name, value: Number(e.requests) }));

  /* ── By-model grouped data: group by coding_agent, stack models ── */
  const modelByAgent = new Map<string, { model: string; tokens: number }[]>();
  for (const row of by_model) {
    const list = modelByAgent.get(row.coding_agent) || [];
    list.push({ model: row.model, tokens: Number(row.tokens) });
    modelByAgent.set(row.coding_agent, list);
  }
  const allModels = [...new Set(by_model.map((r) => r.model))];
  const modelBarData = agents
    .filter((a) => modelByAgent.has(a))
    .map((a) => {
      const entry: Record<string, string | number> = { agent: a };
      const items = modelByAgent.get(a) || [];
      for (const m of allModels) {
        const found = items.find((i) => i.model === m);
        entry[m] = found ? found.tokens : 0;
      }
      return entry;
    });

  /* ── User analytics bar data (top 10 by tokens) ── */
  const topUsers = [...user_analytics]
    .sort((a, b) => Number(b.total_tokens) - Number(a.total_tokens))
    .slice(0, 10)
    .map((u) => ({
      user: u.requester.length > 16 ? u.requester.slice(0, 16) + "..." : u.requester,
      tokens: Number(u.total_tokens),
    }));

  return (
    <Box>
      {/* Agent filter */}
      <HStack mb={4} spacing={3}>
        <Text fontSize="11px" color={DARK.label} textTransform="uppercase" letterSpacing="0.5px" whiteSpace="nowrap">
          Coding Agent
        </Text>
        <Select
          size="sm"
          maxW="260px"
          bg={DARK.card}
          border="1px solid"
          borderColor={DARK.border}
          color={DARK.value}
          value={selectedAgent ?? ""}
          onChange={(e) => setSelectedAgent(e.target.value || null)}
          _focus={{ borderColor: "cyan.500" }}
        >
          <option value="" style={{ background: DARK.card }}>All Agents</option>
          {agents.map((a) => (
            <option key={a} value={a} style={{ background: DARK.card }}>{a}</option>
          ))}
        </Select>
      </HStack>

      {/* KPI Cards */}
      <SimpleGrid columns={3} spacing={4} mb={4}>
        <KpiCard label="Total Requests" value={formatNum(Number(kpis.total_requests))} />
        <KpiCard label="Total Tokens Used" value={formatNum(Number(kpis.total_tokens))} />
        <KpiCard label="Unique Users" value={kpis.unique_users} />
      </SimpleGrid>

      {/* Row 1 */}
      <SimpleGrid columns={3} spacing={4} mb={4}>
        {/* Requests by Agent */}
        <ChartCard title="Requests by Agent">
          <ResponsiveContainer width="100%" height={170}>
            <LineChart data={requestsPivot.data}>
              <CartesianGrid {...axisProps.cartesianGrid} />
              <XAxis {...axisProps.xAxis} />
              <YAxis {...axisProps.yAxis} />
              <Tooltip {...axisProps.tooltip} />
              {requestsPivot.keys.map((key, i) => (
                <Line key={key} type="monotone" dataKey={key} stroke={CHART_COLORS[i % CHART_COLORS.length]} dot={false} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        {/* Token Distribution by Agent */}
        <ChartCard title="Token Distribution by Agent">
          <VStack spacing={2} align="stretch" pt={2}>
            {/* Stacked horizontal bar */}
            <Box borderRadius="6px" overflow="hidden" display="flex" h="28px">
              {tokenShares.map((s, i) => {
                const pctNum = totalTokens > 0 ? (s.value / totalTokens) * 100 : 0;
                if (pctNum === 0) return null;
                return (
                  <Box
                    key={s.name}
                    bg={CHART_COLORS[i % CHART_COLORS.length]}
                    w={`${pctNum}%`}
                    h="100%"
                    title={`${s.name}: ${s.pct}%`}
                    transition="width 0.3s"
                  />
                );
              })}
            </Box>
            {/* Legend */}
            <VStack spacing={1} align="stretch" mt={2}>
              {tokenShares.map((s, i) => (
                <HStack key={s.name} spacing={2} fontSize="10px">
                  <Box w="8px" h="8px" borderRadius="2px" bg={CHART_COLORS[i % CHART_COLORS.length]} flexShrink={0} />
                  <Text color={DARK.value} flex={1} isTruncated>{s.name}</Text>
                  <Text color={DARK.muted}>{s.pct}%</Text>
                  <Text color={DARK.label}>{formatNum(s.value)}</Text>
                </HStack>
              ))}
            </VStack>
          </VStack>
        </ChartCard>

        {/* Latency by Agent */}
        <ChartCard title="Latency by Agent">
          <ResponsiveContainer width="100%" height={170}>
            <LineChart data={latencyPivot.data}>
              <CartesianGrid {...axisProps.cartesianGrid} />
              <XAxis {...axisProps.xAxis} />
              <YAxis {...axisProps.yAxisMs} />
              <Tooltip {...axisProps.tooltip} formatter={(v: number) => fmtMs(v)} />
              {latencyPivot.keys.map((key, i) => (
                <Line key={key} type="monotone" dataKey={key} stroke={CHART_COLORS[i % CHART_COLORS.length]} dot={false} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>
      </SimpleGrid>

      {/* Row 2 */}
      <SimpleGrid columns={3} spacing={4} mb={4}>
        {/* Agent Usage by Endpoint — Donut */}
        <ChartCard title="Agent Usage by Endpoint">
          {endpointPie.length === 0 ? (
            <Center h="160px"><Text color={DARK.muted} fontSize="11px">No endpoint data</Text></Center>
          ) : (
            <ResponsiveContainer width="100%" height={170}>
              <PieChart>
                <Pie
                  data={endpointPie}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  innerRadius={40}
                  outerRadius={65}
                  paddingAngle={2}
                >
                  {endpointPie.map((_, i) => (
                    <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip {...axisProps.tooltip} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </ChartCard>

        {/* Agent Usage by Model — Stacked Bars */}
        <ChartCard title="Agent Usage by Model">
          {modelBarData.length === 0 ? (
            <Center h="160px"><Text color={DARK.muted} fontSize="11px">No model data</Text></Center>
          ) : (
            <ResponsiveContainer width="100%" height={170}>
              <BarChart data={modelBarData} layout="vertical">
                <CartesianGrid {...axisProps.cartesianGrid} />
                <XAxis type="number" tick={{ fontSize: 10, fill: DARK.muted }} tickFormatter={(v: number) => formatNum(v)} />
                <YAxis type="category" dataKey="agent" tick={{ fontSize: 10, fill: DARK.muted }} width={80} />
                <Tooltip {...axisProps.tooltip} />
                {allModels.map((model, i) => (
                  <Bar key={model} dataKey={model} stackId="models" fill={CHART_COLORS[i % CHART_COLORS.length]} />
                ))}
              </BarChart>
            </ResponsiveContainer>
          )}
        </ChartCard>

        {/* Agent Usage by User — Top users bar */}
        <ChartCard title="Top Users by Tokens">
          {topUsers.length === 0 ? (
            <Center h="160px"><Text color={DARK.muted} fontSize="11px">No user data</Text></Center>
          ) : (
            <ResponsiveContainer width="100%" height={170}>
              <BarChart data={topUsers} layout="vertical">
                <CartesianGrid {...axisProps.cartesianGrid} />
                <XAxis type="number" tick={{ fontSize: 10, fill: DARK.muted }} tickFormatter={(v: number) => formatNum(v)} />
                <YAxis type="category" dataKey="user" tick={{ fontSize: 10, fill: DARK.muted }} width={90} />
                <Tooltip {...axisProps.tooltip} />
                <Bar dataKey="tokens" fill={CHART_COLORS[0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </ChartCard>
      </SimpleGrid>

      {/* User Analytics Table */}
      <Box bg={DARK.card} borderRadius="10px" border="1px solid" borderColor={DARK.border} p={4}>
        <Text fontSize="12px" color={DARK.label} mb={3}>User Analytics</Text>
        {user_analytics.length === 0 ? (
          <Center py={6}><Text color={DARK.muted} fontSize="11px">No user analytics data</Text></Center>
        ) : (
          <table style={{ width: "100%", fontSize: "11px", color: DARK.value, borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ color: DARK.muted, borderBottom: `1px solid ${DARK.border}` }}>
                <th style={{ textAlign: "left", padding: "4px 6px", fontWeight: 500 }}>User</th>
                <th style={{ textAlign: "left", padding: "4px 6px", fontWeight: 500 }}>Agent</th>
                <th style={{ textAlign: "right", padding: "4px 6px", fontWeight: 500 }}>Total Tokens</th>
                <th style={{ textAlign: "right", padding: "4px 6px", fontWeight: 500 }}>Requests</th>
                <th style={{ textAlign: "right", padding: "4px 6px", fontWeight: 500 }}>Avg Latency</th>
              </tr>
            </thead>
            <tbody>
              {user_analytics.map((u, i) => (
                <tr key={i} style={{ borderBottom: `1px solid ${DARK.rowBorder}` }}>
                  <td style={{ padding: "4px 6px" }}>
                    {u.requester.length > 24 ? u.requester.slice(0, 24) + "..." : u.requester}
                  </td>
                  <td style={{ padding: "4px 6px" }}>
                    <AgentBadge agent={u.coding_agent} agents={agents} />
                  </td>
                  <td style={{ padding: "4px 6px", textAlign: "right" }}>{formatNum(Number(u.total_tokens))}</td>
                  <td style={{ padding: "4px 6px", textAlign: "right" }}>{u.requests}</td>
                  <td style={{ padding: "4px 6px", textAlign: "right" }}>{fmtMs(Number(u.avg_latency_ms))}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Box>
    </Box>
  );
}
