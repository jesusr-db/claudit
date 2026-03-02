import {
  Box,
  Heading,
  HStack,
  Text,
  Spinner,
  Badge,
  VStack,
  Center,
} from "@chakra-ui/react";
import { useParams } from "react-router-dom";
import { useSessionTimeline, useTurnaroundDetail } from "@/shared/hooks/useApi";
import { SessionTimeline } from "./components/SessionTimeline";

function workColor(sec: number): string {
  if (sec < 30) return "green.600";
  if (sec <= 120) return "orange.500";
  return "red.500";
}

function formatSec(val: string | null | undefined): string {
  if (!val || val === "null") return "-";
  const n = parseFloat(val);
  if (isNaN(n)) return "-";
  if (n >= 60) return `${Math.floor(n / 60)}m ${Math.round(n % 60)}s`;
  return `${Math.round(n)}s`;
}

export default function SessionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data, isLoading, error } = useSessionTimeline(id || "");
  const { data: turnaroundData } = useTurnaroundDetail(id);

  if (!id) return <Text>No session ID</Text>;
  if (isLoading) return <Center h="50vh"><Spinner color="brand.500" size="lg" /></Center>;
  if (error) return <Text color="red.500">Failed to load session</Text>;

  const events = data?.events || [];
  const prompts = turnaroundData?.prompts || [];

  return (
    <Box p={8}>
      <VStack align="stretch" spacing={5}>
        <Box>
          <Heading size="lg" mb={2}>Session Timeline</Heading>
          <HStack spacing={3}>
            <Text fontFamily="mono" fontSize="xs" color="gray.500" bg="surface.muted" px={2} py={1} borderRadius="md">
              {id}
            </Text>
            <Badge colorScheme="blue" variant="subtle">
              {events.length} events
            </Badge>
          </HStack>
        </Box>

        {/* Per-Prompt Turnaround Metrics */}
        {prompts.length > 0 && (
          <Box
            bg="surface.card"
            borderRadius="soft-lg"
            boxShadow="soft"
            border="1px solid"
            borderColor="soft.border"
            overflow="hidden"
          >
            <Box px={5} py={4} borderBottom="1px solid" borderColor="soft.border">
              <Text fontSize="sm" fontWeight="600" color="gray.700">
                Agent Turnaround ({prompts.length} prompts)
              </Text>
            </Box>
            <Box overflowX="auto">
              <Box as="table" w="100%" fontSize="sm">
                <Box as="thead" bg="gray.50">
                  <Box as="tr">
                    {["Prompt Preview", "Agent Work", "API Calls", "Tool Calls", "Events", "Paused?"].map((h) => (
                      <Box
                        as="th"
                        key={h}
                        px={4}
                        py={3}
                        textAlign="left"
                        fontWeight="600"
                        color="gray.600"
                        fontSize="xs"
                        textTransform="uppercase"
                        letterSpacing="wider"
                      >
                        {h}
                      </Box>
                    ))}
                  </Box>
                </Box>
                <Box as="tbody">
                  {prompts.map((p, idx) => {
                    const agentSec = parseFloat(p.agent_work_sec || "0");
                    return (
                      <Box
                        as="tr"
                        key={`${p.prompt_id}-${idx}`}
                        _hover={{ bg: "soft.hover" }}
                        borderBottom="1px solid"
                        borderColor="soft.border"
                      >
                        <Box as="td" px={4} py={3} maxW="300px">
                          <Text noOfLines={1} color="gray.700" fontSize="xs">
                            {p.prompt_preview || "-"}
                          </Text>
                        </Box>
                        <Box as="td" px={4} py={3}>
                          <Text fontWeight="600" fontFamily="mono" color={workColor(agentSec)}>
                            {formatSec(p.agent_work_sec)}
                          </Text>
                        </Box>
                        <Box as="td" px={4} py={3} fontFamily="mono" color="gray.600">
                          {p.api_calls ?? "-"}
                        </Box>
                        <Box as="td" px={4} py={3} fontFamily="mono" color="gray.600">
                          {p.tool_calls ?? "-"}
                        </Box>
                        <Box as="td" px={4} py={3} fontFamily="mono" color="gray.600">
                          {p.events_in_prompt ?? "-"}
                        </Box>
                        <Box as="td" px={4} py={3}>
                          <HStack spacing={1}>
                            {p.has_question === "1" && (
                              <Badge colorScheme="purple" fontSize="10px" variant="subtle">
                                Question
                              </Badge>
                            )}
                            {p.has_plan_exit === "1" && (
                              <Badge colorScheme="blue" fontSize="10px" variant="subtle">
                                Plan
                              </Badge>
                            )}
                          </HStack>
                        </Box>
                      </Box>
                    );
                  })}
                </Box>
              </Box>
            </Box>
          </Box>
        )}

        <SessionTimeline events={events} sessionId={id} />
      </VStack>
    </Box>
  );
}
