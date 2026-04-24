import { Box, HStack, Text, Spinner, Center, Tooltip } from "@chakra-ui/react";
import {
  useEfficiencyAey,
  useEfficiencyCognitiveLoad,
  useEfficiencyReworkRatio,
} from "@/shared/hooks/useApi";

function StatCard({
  label,
  value,
  sub,
  tooltip,
  valueColor,
}: {
  label: string;
  value: string;
  sub?: string;
  tooltip?: string;
  valueColor?: string;
}) {
  return (
    <Box
      bg="surface.card"
      borderRadius="soft-lg"
      boxShadow="soft"
      border="1px solid"
      borderColor="soft.border"
      p={5}
      flex={1}
      minW="200px"
    >
      <Tooltip label={tooltip} isDisabled={!tooltip} placement="top" hasArrow>
        <Text fontSize="xs" color="gray.500" fontWeight="500" cursor={tooltip ? "help" : "default"}>
          {label} {tooltip && <span style={{ opacity: 0.5 }}>ⓘ</span>}
        </Text>
      </Tooltip>
      <Text
        fontSize="2xl"
        fontWeight="700"
        color={valueColor ?? "gray.800"}
        fontFamily="mono"
        mt={1}
      >
        {value}
      </Text>
      {sub && (
        <Text fontSize="xs" color="gray.400" mt={1}>
          {sub}
        </Text>
      )}
    </Box>
  );
}

function fmt(val: string | null | undefined, decimals = 2): string {
  if (val == null || val === "null") return "—";
  const n = parseFloat(val);
  return isNaN(n) ? "—" : n.toFixed(decimals);
}

function fmtCost(val: string | null | undefined): string {
  if (val == null || val === "null") return "—";
  const n = parseFloat(val);
  if (isNaN(n)) return "—";
  if (n < 0.001) return `$${(n * 1000).toFixed(3)}m`;
  return `$${n.toFixed(4)}`;
}

function cliColor(cli: string | null | undefined): string {
  if (cli == null || cli === "null") return "gray.800";
  const n = parseFloat(cli);
  if (isNaN(n)) return "gray.800";
  if (n < 1.5) return "green.600";
  if (n < 3.0) return "orange.500";
  return "red.500";
}

interface Props {
  days: number;
}

export default function EfficiencyKpiCards({ days }: Props) {
  const { data: aey, isLoading: aeyLoading } = useEfficiencyAey(days);
  const { data: cli, isLoading: cliLoading } = useEfficiencyCognitiveLoad(days);
  const { data: rework, isLoading: reworkLoading } = useEfficiencyReworkRatio(days);

  if (aeyLoading || cliLoading || reworkLoading) {
    return (
      <Center py={6}>
        <Spinner color="brand.500" />
      </Center>
    );
  }

  const reworkPct = rework?.avg_rework_ratio != null
    ? `${(parseFloat(rework.avg_rework_ratio) * 100).toFixed(1)}%`
    : "—";

  return (
    <HStack spacing={4} flexWrap="wrap" mb={6}>
      <StatCard
        label="AI-Effective Yield"
        value={fmtCost(aey?.cost_per_accepted_decision)}
        sub={`per accepted decision · ${parseInt(aey?.accepted_decisions ?? "0", 10).toLocaleString()} accepted · ${fmtCost(aey?.total_cost_usd)} total`}
        tooltip="In-session cost (USD) per tool decision the developer accepted. Lower = AI producing more accepted output per dollar spent. Labeled 'in-session' until git linkage is available."
      />
      <StatCard
        label="Cognitive Load Index"
        value={fmt(cli?.cognitive_load_index, 2)}
        sub={`${fmt(cli?.avg_tools_per_prompt)} tools/prompt · ${fmt(cli?.avg_context_thrash)} re-reads · ${(parseFloat(cli?.avg_reject_rate ?? "0") * 100).toFixed(1)}% reject`}
        tooltip="Composite: (tools/prompt) × (1 + context thrash/5) × (1 + reject rate). Lower is better. Green < 1.5, Orange < 3.0, Red ≥ 3.0."
        valueColor={cliColor(cli?.cognitive_load_index)}
      />
      <StatCard
        label="Rework Ratio"
        value={reworkPct}
        sub={`${parseInt(rework?.total_rework_writes ?? "0", 10).toLocaleString()} re-writes of ${parseInt(rework?.total_writes ?? "0", 10).toLocaleString()} total across ${parseInt(rework?.sessions_with_writes ?? "0", 10).toLocaleString()} sessions · global ${((parseFloat(rework?.overall_rework_ratio ?? "0")) * 100).toFixed(1)}%`}
        tooltip="Fraction of file edit/write operations that target a file already edited in the same session. High rework = AI produced output that needed correction."
      />
    </HStack>
  );
}
