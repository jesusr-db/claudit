import { useState } from "react";
import {
  Box,
  Heading,
  HStack,
  Text,
  Spinner,
  Badge,
  VStack,
  Center,
  Tabs,
  TabList,
  Tab,
  TabPanels,
  TabPanel,
  Button,
} from "@chakra-ui/react";
import { useParams } from "react-router-dom";
import { useSessionTimeline, useTurnaroundDetail, useIntrospectionAnalyze } from "@/shared/hooks/useApi";
import { SessionTimeline } from "./components/SessionTimeline";
import { InsightCardFeed } from "@/views/introspection/components/InsightCardFeed";
import type { IntrospectionResult } from "@/types/api";

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
  const mutation = useIntrospectionAnalyze();
  const [cachedInsights, setCachedInsights] = useState<IntrospectionResult | null>(null);

  if (!id) return <Text>No session ID</Text>;
  if (isLoading) return <Center h="50vh"><Spinner color="brand.500" size="lg" /></Center>;
  if (error) return <Text color="red.500">Failed to load session</Text>;

  const events = data?.events || [];
  const prompts = turnaroundData?.prompts || [];

  const handleAnalyze = () => {
    mutation.mutate(
      { session_id: id, cross_session_days: 30 },
      { onSuccess: (data) => setCachedInsights(data) }
    );
  };

  return (
    <Box p={8}>
      <VStack align="stretch" spacing={5}>
        <Box>
          <Heading size="lg" mb={2}>Session Detail</Heading>
          <HStack spacing={3}>
            <Text fontFamily="mono" fontSize="xs" color="gray.500" bg="surface.muted" px={2} py={1} borderRadius="md">
              {id}
            </Text>
            <Badge colorScheme="blue" variant="subtle">
              {events.length} events
            </Badge>
          </HStack>
        </Box>

        <Tabs colorScheme="blue" variant="enclosed" isLazy>
          <TabList>
            <Tab fontSize="sm">Timeline</Tab>
            <Tab fontSize="sm">Insights</Tab>
          </TabList>

          <TabPanels>
            {/* Timeline Tab */}
            <TabPanel px={0}>
              {/* Per-Prompt Turnaround Metrics */}
              {prompts.length > 0 && (
                <Box
                  bg="surface.card"
                  borderRadius="soft-lg"
                  boxShadow="soft"
                  border="1px solid"
                  borderColor="soft.border"
                  overflow="hidden"
                  mb={5}
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
            </TabPanel>

            {/* Insights Tab */}
            <TabPanel px={0}>
              <VStack align="stretch" spacing={4}>
                <HStack>
                  <Button
                    colorScheme="blue"
                    size="sm"
                    onClick={handleAnalyze}
                    isLoading={mutation.isPending}
                    loadingText="Analyzing..."
                  >
                    {cachedInsights ? "Re-analyze" : "Analyze"}
                  </Button>
                  {cachedInsights && (
                    <Badge variant="subtle" colorScheme="green" fontSize="xs">
                      {cachedInsights.cards.length} pattern
                      {cachedInsights.cards.length !== 1 ? "s" : ""} found
                    </Badge>
                  )}
                </HStack>

                {mutation.isPending && (
                  <Center py={8}>
                    <VStack spacing={3}>
                      <Spinner size="lg" color="brand.500" />
                      <Text fontSize="sm" color="gray.500">
                        Analyzing session patterns... this may take up to 60 seconds.
                      </Text>
                    </VStack>
                  </Center>
                )}

                {mutation.isError && !cachedInsights && (
                  <Box
                    bg="red.50"
                    border="1px solid"
                    borderColor="red.200"
                    borderRadius="md"
                    p={4}
                  >
                    <Text color="red.600" fontSize="sm">
                      {mutation.error?.message || "Analysis failed"}
                    </Text>
                  </Box>
                )}

                {cachedInsights && !mutation.isPending && (
                  <InsightCardFeed
                    cards={cachedInsights.cards}
                    analysisError={cachedInsights.analysis_error}
                    onRetry={handleAnalyze}
                  />
                )}

                {!cachedInsights && !mutation.isPending && !mutation.isError && (
                  <Center py={8}>
                    <Text fontSize="sm" color="gray.500">
                      Click "Analyze" to scan this session for failure patterns.
                    </Text>
                  </Center>
                )}
              </VStack>
            </TabPanel>
          </TabPanels>
        </Tabs>
      </VStack>
    </Box>
  );
}
