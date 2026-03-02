import {
  Box,
  Heading,
  VStack,
  HStack,
  Text,
  Spinner,
  Center,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
} from "@chakra-ui/react";
import { useKpiCostOverview } from "@/shared/hooks/useApi";
import { useTimeRange } from "@/shared/context/TimeRangeContext";
import { MetricTooltip, METRIC_METHODOLOGY } from "@/shared/components/MetricTooltip";
import CostTab from "./tabs/CostTab";
import EffectivenessTab from "./tabs/EffectivenessTab";
import FlowTab from "./tabs/FlowTab";
import ModelEfficiencyTab from "./tabs/ModelEfficiencyTab";

function StatCard({ label, value, sub, methodology }: { label: string; value: string; sub?: string; methodology?: string }) {
  return (
    <Box
      bg="surface.card"
      borderRadius="soft-lg"
      boxShadow="soft"
      border="1px solid"
      borderColor="soft.border"
      p={5}
      flex={1}
      minW="180px"
    >
      {methodology ? (
        <MetricTooltip label={label} methodology={methodology} />
      ) : (
        <Text fontSize="xs" color="gray.500" fontWeight="500">{label}</Text>
      )}
      <Text fontSize="2xl" fontWeight="700" color="gray.800" fontFamily="mono" mt={methodology ? 0 : 1}>{value}</Text>
      {sub && <Text fontSize="xs" color="gray.400" mt={1}>{sub}</Text>}
    </Box>
  );
}

export default function KpiHubPage() {
  const { days } = useTimeRange();
  const { data: overview, isLoading } = useKpiCostOverview(days);

  return (
    <Box p={8}>
      <VStack spacing={6} align="stretch">
        <Box>
          <Heading size="lg" mb={1}>KPI Hub</Heading>
          <Text color="gray.500" fontSize="sm">
            Cost intelligence, agent effectiveness, flow correlation, and model efficiency
          </Text>
        </Box>

        {/* Hero stat row */}
        {isLoading ? (
          <Center py={4}><Spinner color="brand.500" size="sm" /></Center>
        ) : overview ? (
          <HStack spacing={4} flexWrap="wrap">
            <StatCard
              label="Total Cost"
              value={`$${parseFloat(overview.total_cost || "0").toFixed(2)}`}
              methodology={METRIC_METHODOLOGY.totalCost}
            />
            <StatCard
              label="Cache Hit %"
              value={`${parseFloat(overview.cache_hit_pct || "0").toFixed(1)}%`}
              methodology={METRIC_METHODOLOGY.cacheHit}
            />
            <StatCard
              label="Avg Cost / Session"
              value={`$${parseFloat(overview.avg_cost_per_session || "0").toFixed(3)}`}
              methodology={METRIC_METHODOLOGY.avgCostPerSession}
            />
            <StatCard
              label="Avg Cost / Prompt"
              value={`$${parseFloat(overview.avg_cost_per_prompt || "0").toFixed(4)}`}
              methodology={METRIC_METHODOLOGY.avgCostPerPrompt}
            />
          </HStack>
        ) : null}

        <Tabs variant="soft-rounded" colorScheme="brand">
          <TabList>
            <Tab>Cost Intelligence</Tab>
            <Tab>Agent Effectiveness</Tab>
            <Tab>Flow Correlation</Tab>
            <Tab>Model Efficiency</Tab>
          </TabList>
          <TabPanels>
            <TabPanel px={0} pt={5}>
              <CostTab days={days} />
            </TabPanel>
            <TabPanel px={0} pt={5}>
              <EffectivenessTab days={days} />
            </TabPanel>
            <TabPanel px={0} pt={5}>
              <FlowTab days={days} />
            </TabPanel>
            <TabPanel px={0} pt={5}>
              <ModelEfficiencyTab days={days} />
            </TabPanel>
          </TabPanels>
        </Tabs>
      </VStack>
    </Box>
  );
}
