import { Box, Heading, Text, HStack, Badge } from "@chakra-ui/react";
import { useTimeRange } from "@/shared/context/TimeRangeContext";
import EfficiencyKpiCards from "./components/EfficiencyKpiCards";
import FeedbackLatencyChart from "./components/FeedbackLatencyChart";
import HarnessConvergenceChart from "./components/HarnessConvergenceChart";

function FrameworkCard() {
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
      <HStack mb={2} spacing={2} flexWrap="wrap">
        <Badge colorScheme="purple" fontSize="xs">SPACE Framework</Badge>
        <Badge colorScheme="blue" fontSize="xs">DevEx</Badge>
        <Badge colorScheme="orange" fontSize="xs">AI-Native · v1</Badge>
      </HStack>
      <Text fontSize="xs" color="gray.500" lineHeight="1.7">
        This panel uses the <strong>SPACE</strong> (Satisfaction, Performance, Activity,
        Communication, Efficiency) framework augmented with <strong>DevEx</strong>'s three
        AI-native dimensions (Feedback Loops, Cognitive Load, Flow State). Metrics are derived
        from Claude Code session telemetry — no git or CI integration required.{" "}
        <strong>AI-Effective Yield</strong> measures in-session accepted decisions per dollar;
        it will gain a merged-PR denominator once git correlation is wired (phase 2).
      </Text>
    </Box>
  );
}

export default function EfficiencyPage() {
  const { days } = useTimeRange();

  return (
    <Box p={8}>
      <Box mb={6}>
        <Heading size="lg" mb={1}>
          Developer Efficiency
        </Heading>
        <Text fontSize="sm" color="gray.500">
          SPACE + DevEx metrics for AI-assisted coding — beyond tokenmaxxing
        </Text>
      </Box>

      <FrameworkCard />

      <EfficiencyKpiCards days={days} />

      <HarnessConvergenceChart days={days} />

      <FeedbackLatencyChart days={days} />
    </Box>
  );
}
