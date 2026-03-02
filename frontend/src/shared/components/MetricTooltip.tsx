import { Tooltip, Icon, HStack, Text } from "@chakra-ui/react";
import { FiInfo } from "react-icons/fi";

interface MetricTooltipProps {
  label: string;
  methodology: string;
  children?: React.ReactNode;
}

/**
 * Inline info icon with a hover tooltip explaining how a metric is calculated.
 * Use next to any efficiency/KPI label so users understand the methodology.
 */
export function MetricTooltip({ label, methodology, children }: MetricTooltipProps) {
  return (
    <HStack spacing={1} display="inline-flex" alignItems="center">
      {children || <Text fontSize="xs" color="gray.500" fontWeight="500">{label}</Text>}
      <Tooltip
        label={methodology}
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
        <span style={{ display: "inline-flex", cursor: "help" }}>
          <Icon as={FiInfo} boxSize={3} color="gray.400" />
        </span>
      </Tooltip>
    </HStack>
  );
}

/**
 * Central registry of methodology descriptions for all efficiency metrics.
 */
export const METRIC_METHODOLOGY = {
  // Turnaround
  avgTurnaround:
    "Time from user prompt to the last agent event before the next human input. Measures autonomous work duration per prompt.",
  p95Turnaround:
    "95th percentile turnaround: 95% of prompts complete within this time. Highlights tail latency outliers.",
  agentWork:
    "Elapsed seconds from prompt submission to the agent's final event (tool call, API response, or output). Color: green <30s, orange 30-120s, red >120s.",

  // Cost
  totalCost:
    "Sum of API call costs based on model pricing (input + output tokens). Derived from OTEL span attributes.",
  avgCostPerSession:
    "Total cost divided by the number of distinct sessions in the time range.",
  avgCostPerPrompt:
    "Total cost divided by total prompt count. Lower values indicate more cost-efficient interactions.",
  costTrend:
    "Compares the latter-half cost vs the first-half cost in the selected period. Up = costs rising, Down = costs falling.",

  // Cache
  cacheHit:
    "Percentage of tokens served from cache: cache_read_tokens / (cache_read_tokens + input_tokens). Higher is better — reduces API costs.",

  // Tool effectiveness
  toolSuccess:
    "Percentage of tool calls that returned a result (vs errored or timed out). Calculated from OTEL tool span status codes.",
  avgToolsPerPrompt:
    "Average number of tool calls per user prompt. High values may indicate retry loops or complex multi-step workflows.",
  toolRetries:
    "Consecutive calls to the same tool within a single prompt turn. May indicate flaky tools or incorrect parameters.",
  orphanDecisions:
    "Tool decision events (agent chose a tool) with no corresponding result event. May indicate timeouts or dropped executions.",
  errorRecovery:
    "Percentage of error events followed by a retry attempt within the same session. Higher = agent is better at self-healing.",

  // Token waste
  tokenWaste:
    "Flagged when input_tokens > 50K but output_tokens < 500. Indicates large context sent with minimal useful output — potential prompt optimization opportunity.",

  // Prompt complexity
  promptComplexity:
    "Prompts bucketed by event count (1-5, 6-15, 16-50, 50+). Shows distribution of simple vs complex autonomous workflows.",

  // Flow
  avgLatency:
    "Average duration of the span in milliseconds, from span start to span end as reported by OTEL instrumentation.",

  // Model Efficiency
  modelEfficiencyMatrix:
    "Compares model performance across prompt complexity levels. Complexity is determined by event count per prompt: simple (1-5), moderate (6-15), complex (16-50), very_complex (50+).",
  rightsizing:
    "Identifies where expensive models (Opus) were used for simple tasks. Opportunity levels: high = tier mismatch >= 2 (e.g., Opus on simple), medium = mismatch of 1, low/none = appropriate.",
  savingsCalculator:
    "Estimates potential savings by comparing actual spend to the hypothetical cost if the cheapest model (with 5+ calls) were used for each complexity bucket.",
} as const;
