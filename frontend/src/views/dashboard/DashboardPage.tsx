import { Box, Heading, VStack, HStack, Text, Icon, Spinner, SimpleGrid, Tooltip } from "@chakra-ui/react";
import { Link } from "react-router-dom";
import { FiTrendingUp, FiTrendingDown, FiMinus, FiArrowRight } from "react-icons/fi";
import { MetricTooltip, METRIC_METHODOLOGY } from "@/shared/components/MetricTooltip";
import { formatAxisLabel } from "@/shared/utils/dates";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RTooltip,
  ResponsiveContainer,
} from "recharts";
import { SummaryCards } from "./components/SummaryCards";
import { useKpiBadges, useKpiCostTrend, useActivityClassification } from "@/shared/hooks/useApi";
import { useTimeRange } from "@/shared/context/TimeRangeContext";

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString();
}

function KpiBadge({ label, value, icon, color, methodology }: { label: string; value: string; icon?: React.ElementType; color?: string; methodology?: string }) {
  return (
    <Box
      bg="surface.card"
      borderRadius="soft-lg"
      boxShadow="soft"
      border="1px solid"
      borderColor="soft.border"
      px={4}
      py={3}
      flex={1}
      minW="150px"
    >
      <HStack spacing={2}>
        {icon && <Icon as={icon} color={color || "gray.500"} boxSize={3.5} />}
        {methodology ? (
          <MetricTooltip label={label} methodology={methodology} />
        ) : (
          <Text fontSize="xs" color="gray.500" fontWeight="500">{label}</Text>
        )}
      </HStack>
      <Text fontSize="lg" fontWeight="700" color="gray.800" fontFamily="mono" mt={0.5}>{value}</Text>
    </Box>
  );
}

function CostTrendChart({ days }: { days: number }) {
  const { data, isLoading } = useKpiCostTrend(days);

  if (isLoading) return <Spinner color="brand.500" size="sm" />;

  const trend = data?.trend || [];
  if (trend.length === 0) return <Text color="gray.400" fontSize="sm">No cost data</Text>;

  const chartData = trend.map((t) => ({
    date: formatAxisLabel(t.date),
    cost: parseFloat(t.daily_cost || "0"),
  }));

  return (
    <Box h="200px">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" vertical={false} />
          <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#94A3B8" }} tickLine={false} axisLine={{ stroke: "#E2E8F0" }} />
          <YAxis tick={{ fontSize: 11, fill: "#94A3B8" }} tickLine={false} axisLine={false} width={50} tickFormatter={(v) => `$${v}`} />
          <RTooltip
            contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #E2E8F0" }}
            formatter={(value: number) => [`$${value.toFixed(4)}`, "Cost"]}
          />
          <Area type="monotone" dataKey="cost" stroke="#6366F1" fill="#6366F1" fillOpacity={0.15} strokeWidth={2} />
        </AreaChart>
      </ResponsiveContainer>
    </Box>
  );
}

function TokenUsageChart({ days }: { days: number }) {
  const { data, isLoading } = useKpiCostTrend(days);

  if (isLoading) return <Spinner color="brand.500" size="sm" />;

  const trend = data?.trend || [];
  if (trend.length === 0) return <Text color="gray.400" fontSize="sm">No token data</Text>;

  const chartData = trend.map((t) => ({
    date: formatAxisLabel(t.date),
    input: parseInt(t.input_tokens || "0", 10),
    output: parseInt(t.output_tokens || "0", 10),
    cache: parseInt(t.cache_read_tokens || "0", 10),
  }));

  return (
    <Box h="200px">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" vertical={false} />
          <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#94A3B8" }} tickLine={false} axisLine={{ stroke: "#E2E8F0" }} />
          <YAxis tick={{ fontSize: 11, fill: "#94A3B8" }} tickLine={false} axisLine={false} width={55} tickFormatter={formatTokens} />
          <RTooltip
            contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #E2E8F0" }}
            formatter={(value: number, name: string) => [formatTokens(value), name]}
          />
          <Area type="monotone" dataKey="cache" stackId="1" stroke="#10B981" fill="#10B981" fillOpacity={0.2} strokeWidth={1.5} name="Cache Read" />
          <Area type="monotone" dataKey="input" stackId="1" stroke="#3B82F6" fill="#3B82F6" fillOpacity={0.2} strokeWidth={1.5} name="Input" />
          <Area type="monotone" dataKey="output" stackId="1" stroke="#8B5CF6" fill="#8B5CF6" fillOpacity={0.2} strokeWidth={1.5} name="Output" />
        </AreaChart>
      </ResponsiveContainer>
    </Box>
  );
}

const ACTIVITY_DESCRIPTIONS: Record<string, string> = {
  Coding: "Prompts where Edit or Write tools were used. The agent was actively modifying files.",
  Debugging: "Prompt text mentions debug, error, fix, bug, stacktrace, or exception.",
  Testing: "Prompt text mentions test, pytest, jest, spec, or coverage.",
  "Git Ops": "Prompt text mentions git, commit, branch, merge, rebase, or cherry-pick.",
  "Build/Deploy": "Prompt text mentions build, deploy, docker, npm run, yarn, make, webpack, or vite.",
  Delegation: "MCP tool calls detected — the agent delegated work to an external service.",
  Planning: "Prompt text mentions plan, design, architect, approach, or strategy.",
  Exploration: "Prompt text mentions find, search, or explore AND Read/Glob/Grep tools were used.",
  Conversation: "No tool calls in the prompt — pure text exchange between user and agent.",
  General: "Activity that didn't match any other category. Includes Skill invocations and misc tool use.",
};

const ACTIVITY_COLORS: Record<string, string> = {
  Coding: "#6366F1",
  Debugging: "#EF4444",
  Testing: "#10B981",
  "Git Ops": "#F59E0B",
  "Build/Deploy": "#8B5CF6",
  Delegation: "#EC4899",
  Planning: "#06B6D4",
  Exploration: "#14B8A6",
  Conversation: "#94A3B8",
  General: "#78716C",
};

function ActivityBreakdownChart({ days }: { days: number }) {
  const { data, isLoading } = useActivityClassification(days);

  if (isLoading) return <Spinner color="brand.500" size="sm" />;

  const activities = data?.activities || [];
  if (activities.length === 0)
    return (
      <Text color="gray.400" fontSize="sm">
        No activity data
      </Text>
    );

  const chartData = activities.map((a) => ({
    activity: a.activity,
    cost: parseFloat(a.total_cost || "0"),
    prompts: parseInt(a.prompt_count || "0", 10),
    tokens: parseInt(a.total_tokens || "0", 10),
  }));

  const totalCost = chartData.reduce((sum, d) => sum + d.cost, 0);

  return (
    <VStack spacing={4} align="stretch">
      <Box h={`${Math.max(chartData.length * 36, 180)}px`}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} layout="vertical" margin={{ left: 10, right: 20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" horizontal={false} />
            <XAxis
              type="number"
              tick={{ fontSize: 11, fill: "#94A3B8" }}
              tickLine={false}
              axisLine={{ stroke: "#E2E8F0" }}
              tickFormatter={(v: number) => `$${v.toFixed(0)}`}
            />
            <YAxis
              type="category"
              dataKey="activity"
              tick={{ fontSize: 12, fill: "#475569" }}
              tickLine={false}
              axisLine={false}
              width={90}
            />
            <RTooltip
              contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #E2E8F0" }}
              formatter={(value: number, _name: string, entry: { payload?: { prompts: number; tokens: number } }) => [
                `$${value.toFixed(4)}  (${entry.payload?.prompts ?? 0} prompts, ${formatTokens(entry.payload?.tokens ?? 0)} tokens)`,
                "Cost",
              ]}
            />
            <Bar dataKey="cost" radius={[0, 4, 4, 0]} barSize={20}>
              {chartData.map((entry) => (
                <Cell key={entry.activity} fill={ACTIVITY_COLORS[entry.activity] || "#94A3B8"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </Box>
      <HStack spacing={3} flexWrap="wrap" px={2}>
        {chartData.map((a) => (
          <Tooltip
            key={a.activity}
            label={ACTIVITY_DESCRIPTIONS[a.activity] || "Uncategorized activity."}
            fontSize="xs"
            bg="gray.800"
            color="white"
            px={3}
            py={2}
            borderRadius="md"
            maxW="280px"
            hasArrow
            placement="top"
          >
            <HStack spacing={1.5} cursor="help">
              <Box w={2} h={2} borderRadius="full" bg={ACTIVITY_COLORS[a.activity] || "#94A3B8"} />
              <Text fontSize="xs" color="gray.500">
                {a.activity}{" "}
                <Text as="span" fontWeight="600" color="gray.700">
                  {totalCost > 0 ? `${((a.cost / totalCost) * 100).toFixed(0)}%` : "0%"}
                </Text>
              </Text>
            </HStack>
          </Tooltip>
        ))}
      </HStack>
    </VStack>
  );
}

export default function DashboardPage() {
  const { days } = useTimeRange();
  const { data: badges, isLoading: badgesLoading } = useKpiBadges(days);

  const trendIcon = badges?.cost_trend_direction === "up" ? FiTrendingUp
    : badges?.cost_trend_direction === "down" ? FiTrendingDown
    : FiMinus;
  const trendColor = badges?.cost_trend_direction === "up" ? "red.500"
    : badges?.cost_trend_direction === "down" ? "green.500"
    : "gray.500";

  return (
    <Box p={8}>
      <VStack spacing={8} align="stretch">
        <Box>
          <Heading size="lg" mb={1}>Analytics Dashboard</Heading>
          <Text fontSize="sm" color="gray.500">
            Claude Code usage overview and error insights
          </Text>
        </Box>
        <SummaryCards />

        {/* KPI Badges */}
        {badgesLoading ? (
          <Spinner color="brand.500" size="sm" />
        ) : badges ? (
          <Box>
            <HStack spacing={3} mb={2} flexWrap="wrap">
              <KpiBadge
                label="Cache Hit %"
                value={`${parseFloat(badges.cache_hit_pct || "0").toFixed(1)}%`}
                methodology={METRIC_METHODOLOGY.cacheHit}
              />
              <KpiBadge
                label="Tool Success"
                value={`${parseFloat(badges.tool_success_rate || "0").toFixed(1)}%`}
                methodology={METRIC_METHODOLOGY.toolSuccess}
              />
              <KpiBadge
                label="Avg Turnaround"
                value={`${parseFloat(badges.avg_turnaround_sec || "0").toFixed(0)}s`}
                methodology={METRIC_METHODOLOGY.avgTurnaround}
              />
              <KpiBadge
                label="Cost Trend"
                value={badges.cost_trend_direction || "flat"}
                icon={trendIcon}
                color={trendColor}
                methodology={METRIC_METHODOLOGY.costTrend}
              />
            </HStack>
            <Link to="/kpis">
              <HStack spacing={1} color="brand.600" fontSize="xs" fontWeight="500" _hover={{ color: "brand.700" }}>
                <Text>View KPI Details</Text>
                <Icon as={FiArrowRight} boxSize={3} />
              </HStack>
            </Link>
          </Box>
        ) : null}

        {/* Time-series Charts */}
        <SimpleGrid columns={{ base: 1, lg: 2 }} spacing={5}>
          <Box
            bg="surface.card"
            borderRadius="soft-lg"
            boxShadow="soft"
            border="1px solid"
            borderColor="soft.border"
            p={5}
          >
            <Text fontSize="sm" fontWeight="600" color="gray.700" mb={3}>Cost Trend</Text>
            <CostTrendChart days={days} />
          </Box>
          <Box
            bg="surface.card"
            borderRadius="soft-lg"
            boxShadow="soft"
            border="1px solid"
            borderColor="soft.border"
            p={5}
          >
            <Text fontSize="sm" fontWeight="600" color="gray.700" mb={3}>Token Usage</Text>
            <TokenUsageChart days={days} />
          </Box>
        </SimpleGrid>

        {/* Activity Breakdown */}
        <Box
          bg="surface.card"
          borderRadius="soft-lg"
          boxShadow="soft"
          border="1px solid"
          borderColor="soft.border"
          p={5}
        >
          <MetricTooltip
            label="Activity Breakdown"
            methodology="Each prompt is classified by its tool usage and keywords. Rules are applied in priority order: Delegation (MCP tools) > Testing > Git Ops > Build/Deploy > Debugging > Planning > Exploration > Coding > Conversation > General. Cost and tokens are summed per category."
          >
            <Text fontSize="sm" fontWeight="600" color="gray.700">Activity Breakdown</Text>
          </MetricTooltip>
          <Box mb={3} />
          <ActivityBreakdownChart days={days} />
        </Box>

      </VStack>
    </Box>
  );
}
