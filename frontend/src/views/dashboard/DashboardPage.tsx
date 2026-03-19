import { Box, Heading, VStack, HStack, Text, Icon, Spinner, SimpleGrid } from "@chakra-ui/react";
import { Link } from "react-router-dom";
import { FiTrendingUp, FiTrendingDown, FiMinus, FiArrowRight } from "react-icons/fi";
import { MetricTooltip, METRIC_METHODOLOGY } from "@/shared/components/MetricTooltip";
import { formatAxisLabel } from "@/shared/utils/dates";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RTooltip,
  ResponsiveContainer,
} from "recharts";
import { SummaryCards } from "./components/SummaryCards";
import { useKpiBadges, useKpiCostTrend } from "@/shared/hooks/useApi";
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

      </VStack>
    </Box>
  );
}
