import { Box, Text, Spinner, Center } from "@chakra-ui/react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { useEfficiencyFeedbackLatency } from "@/shared/hooks/useApi";

interface Props {
  days: number;
}

export default function FeedbackLatencyChart({ days }: Props) {
  const { data, isLoading, error } = useEfficiencyFeedbackLatency(days);

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
      <Text fontSize="sm" fontWeight="600" color="gray.700" mb={1}>
        Feedback Loop Latency by Tool
      </Text>
      <Text fontSize="xs" color="gray.400" mb={4}>
        p50 / p95 duration (ms) per tool_result event — lower = tighter feedback loop
      </Text>

      {isLoading && (
        <Center py={8}>
          <Spinner color="brand.500" />
        </Center>
      )}
      {error && (
        <Text color="red.500" fontSize="sm">
          Failed to load latency data
        </Text>
      )}

      {data && data.tools.length > 0 && (
        <ResponsiveContainer width="100%" height={300}>
          <BarChart
            data={data.tools.map((t) => ({
              name: t.tool_name,
              p50: t.p50_ms != null ? parseFloat(t.p50_ms) : 0,
              p95: t.p95_ms != null ? parseFloat(t.p95_ms) : 0,
              calls: parseInt(t.call_count, 10),
            }))}
            layout="vertical"
            margin={{ top: 0, right: 24, bottom: 0, left: 80 }}
          >
            <CartesianGrid strokeDasharray="3 3" horizontal={false} />
            <XAxis type="number" unit="ms" tick={{ fontSize: 11 }} />
            <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={80} />
            <Tooltip
              formatter={(value: number, name: string) => [`${value.toLocaleString()}ms`, name]}
              labelFormatter={(label: string, payload) => {
                const calls = payload?.[0]?.payload?.calls;
                return calls != null ? `${label} (${calls.toLocaleString()} calls)` : label;
              }}
            />
            <Legend />
            <Bar dataKey="p50" name="p50" fill="#4A90D9" radius={[0, 3, 3, 0]} />
            <Bar dataKey="p95" name="p95" fill="#E07B54" radius={[0, 3, 3, 0]} />
          </BarChart>
        </ResponsiveContainer>
      )}

      {data && data.tools.length === 0 && !isLoading && (
        <Text color="gray.400" fontSize="sm">
          No tool latency data for this period
        </Text>
      )}
    </Box>
  );
}
