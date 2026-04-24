import { Box, Text, Spinner, Center, HStack, Badge } from "@chakra-ui/react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import { useEfficiencyHarnessConvergence } from "@/shared/hooks/useApi";

interface Props {
  days: number;
}

export default function HarnessConvergenceChart({ days }: Props) {
  const { data, isLoading, error } = useEfficiencyHarnessConvergence(days);

  const trend = data?.trend ?? [];
  const latest = trend.length > 0
    ? parseFloat(trend[trend.length - 1].avg_convergence_score ?? "0")
    : null;
  const earliest = trend.length > 1
    ? parseFloat(trend[0].avg_convergence_score ?? "0")
    : null;
  const direction =
    latest != null && earliest != null
      ? latest > earliest + 0.01
        ? "↑ improving"
        : latest < earliest - 0.01
        ? "↓ declining"
        : "→ stable"
      : null;

  return (
    <Box
      bg="surface.card"
      borderRadius="soft-lg"
      boxShadow="soft"
      border="1px solid"
      borderColor="soft.border"
      p={5}
      mb={6}
    >
      <HStack mb={1} justify="space-between">
        <Text fontSize="sm" fontWeight="600" color="gray.700">
          Harness Convergence Score
        </Text>
        {direction && (
          <Badge
            colorScheme={
              direction.startsWith("↑") ? "green" : direction.startsWith("↓") ? "red" : "gray"
            }
            fontSize="xs"
          >
            {direction}
          </Badge>
        )}
      </HStack>
      <Text fontSize="xs" color="gray.400" mb={4}>
        Daily average: (1 − error rate) ÷ (1 + tools/prompt/10). Rising = harness more efficient.
        Formula tooltip: higher score means fewer errors AND fewer tool calls per prompt.
      </Text>

      {isLoading && (
        <Center py={8}>
          <Spinner color="brand.500" />
        </Center>
      )}
      {error && (
        <Text color="red.500" fontSize="sm">
          Failed to load convergence data
        </Text>
      )}

      {trend.length > 0 && (
        <ResponsiveContainer width="100%" height={220}>
          <LineChart
            data={trend.map((p) => ({
              date: p.date,
              score: p.avg_convergence_score != null ? parseFloat(p.avg_convergence_score) : null,
              sessions: parseInt(p.session_count, 10),
            }))}
            margin={{ top: 4, right: 16, bottom: 0, left: 0 }}
          >
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 10 }}
              tickFormatter={(d: string) => d.slice(5)}
            />
            <YAxis domain={[0, 1]} tick={{ fontSize: 11 }} tickFormatter={(v) => v.toFixed(2)} />
            <Tooltip
              formatter={(v: number) => [v.toFixed(3), "Convergence Score"]}
              labelFormatter={(l: string) => `Date: ${l}`}
            />
            <ReferenceLine y={0.5} stroke="#ccc" strokeDasharray="4 2" label={{ value: "0.5", fontSize: 10 }} />
            <Line
              type="monotone"
              dataKey="score"
              stroke="#4A90D9"
              strokeWidth={2}
              dot={false}
              connectNulls
            />
          </LineChart>
        </ResponsiveContainer>
      )}

      {trend.length === 0 && !isLoading && (
        <Text color="gray.400" fontSize="sm">
          No convergence data for this period
        </Text>
      )}
    </Box>
  );
}
