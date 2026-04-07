import { useState } from "react";
import {
  Box,
  VStack,
  HStack,
  Text,
  Spinner,
  Center,
  Badge,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Alert,
  AlertIcon,
  Button,
  Collapse,
  Icon,
} from "@chakra-ui/react";
import { Link } from "react-router-dom";
import { FiChevronDown, FiChevronUp, FiExternalLink } from "react-icons/fi";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RTooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import {
  useKpiEfficiencyMatrix,
  useKpiRightsizing,
  useKpiRightsizingDetails,
  useKpiModelRecommendations,
  useKpiSavingsCalculator,
} from "@/shared/hooks/useApi";
import { MetricTooltip, METRIC_METHODOLOGY } from "@/shared/components/MetricTooltip";

function formatCost(val: string | number | null | undefined): string {
  if (val == null) return "-";
  const n = typeof val === "string" ? parseFloat(val) : val;
  if (isNaN(n)) return "-";
  if (n >= 1) return `$${n.toFixed(2)}`;
  if (n >= 0.01) return `$${n.toFixed(3)}`;
  return `$${n.toFixed(4)}`;
}

function formatMs(val: string | number | null | undefined): string {
  if (val == null) return "-";
  const n = typeof val === "string" ? parseFloat(val) : val;
  if (isNaN(n)) return "-";
  if (n >= 1000) return `${(n / 1000).toFixed(1)}s`;
  return `${Math.round(n)}ms`;
}

function shortModel(model: string): string {
  return (model || "").replace(/^.*\//, "");
}

function CardBox({ children }: { children: React.ReactNode }) {
  return (
    <Box
      bg="surface.card"
      borderRadius="soft-lg"
      boxShadow="soft"
      border="1px solid"
      borderColor="soft.border"
      p={5}
    >
      {children}
    </Box>
  );
}

function HeroStat({ label, value, sub, color }: { label: string; value: string; sub?: string; color?: string }) {
  return (
    <Box flex={1} minW="140px" textAlign="center">
      <Text fontSize="xs" color="gray.500" fontWeight="500">{label}</Text>
      <Text fontSize="2xl" fontWeight="700" color={color || "gray.800"} fontFamily="mono" mt={1}>{value}</Text>
      {sub && <Text fontSize="xs" color="gray.400" mt={1}>{sub}</Text>}
    </Box>
  );
}

const OPPORTUNITY_COLORS: Record<string, string> = {
  high: "red",
  medium: "orange",
  low: "yellow",
  none: "green",
};

export default function ModelEfficiencyTab({ days = 30 }: { days?: number }) {
  const { data: matrixData, isLoading: matrixLoading } = useKpiEfficiencyMatrix(days);
  const { data: rightsizingData, isLoading: rightsizingLoading } = useKpiRightsizing(days);
  const { data: recsData, isLoading: recsLoading } = useKpiModelRecommendations(days);
  const { data: savingsData, isLoading: savingsLoading } = useKpiSavingsCalculator(days);

  // Drill-down state
  const [drillDown, setDrillDown] = useState<{ model: string; complexity: string } | null>(null);
  const { data: detailsData, isLoading: detailsLoading } = useKpiRightsizingDetails(
    days,
    drillDown?.model,
    drillDown?.complexity,
  );

  const matrix = matrixData?.matrix || [];
  const opportunities = rightsizingData?.opportunities || [];
  const recommendations = recsData?.recommendations || [];
  const savings = savingsData?.savings || [];
  const details = detailsData?.details || [];

  // Detect single-model scenario
  const uniqueModels = [...new Set(matrix.map((r) => r.model))];
  const singleModel = uniqueModels.length <= 1;

  // Savings chart data
  const savingsChart = savings.map((s) => ({
    complexity: s.complexity,
    actual: parseFloat(s.actual_cost || "0"),
    optimized: parseFloat(s.hypothetical_cost || "0"),
  }));

  // Total savings
  const totalActual = savings.reduce((sum, s) => sum + parseFloat(s.actual_cost || "0"), 0);
  const totalHypothetical = savings.reduce((sum, s) => sum + parseFloat(s.hypothetical_cost || "0"), 0);
  const totalSavings = totalActual - totalHypothetical;
  const savingsPct = totalActual > 0 ? (100 * totalSavings / totalActual) : 0;

  // Rightsizing bar chart aggregation
  const opportunityCounts = opportunities.reduce<Record<string, number>>((acc, o) => {
    const level = o.downgrade_opportunity || "none";
    acc[level] = (acc[level] || 0) + parseInt(o.call_count || "0", 10);
    return acc;
  }, {});
  const opportunityChart = ["high", "medium", "low", "none"]
    .filter((k) => opportunityCounts[k])
    .map((k) => ({ level: k, calls: opportunityCounts[k] || 0 }));

  // Group recommendations by complexity
  const recsByComplexity = recommendations.reduce<Record<string, typeof recommendations>>((acc, r) => {
    const c = r.complexity;
    if (!acc[c]) acc[c] = [];
    acc[c].push(r);
    return acc;
  }, {});

  function handleDrillToggle(model: string, complexity: string) {
    if (drillDown?.model === model && drillDown?.complexity === complexity) {
      setDrillDown(null);
    } else {
      setDrillDown({ model, complexity });
    }
  }

  const isDrillOpen = (model: string, complexity: string) =>
    drillDown?.model === model && drillDown?.complexity === complexity;

  return (
    <VStack spacing={5} align="stretch">
      {singleModel && (
        <Alert status="info" borderRadius="md" fontSize="sm">
          <AlertIcon />
          Only one model detected — add variety to enable meaningful comparisons and savings estimates.
        </Alert>
      )}

      {/* Savings Calculator Hero */}
      <CardBox>
        <MetricTooltip label="Savings Calculator" methodology={METRIC_METHODOLOGY.savingsCalculator} />
        <Box mt={2} />
        {savingsLoading ? (
          <Center py={8}><Spinner color="brand.500" size="sm" /></Center>
        ) : (
          <>
            <HStack spacing={4} flexWrap="wrap" mb={4}>
              <HeroStat label="Actual Spend" value={formatCost(totalActual)} />
              <HeroStat label="Optimized" value={formatCost(totalHypothetical)} color="green.600" />
              <HeroStat
                label="Potential Savings"
                value={formatCost(totalSavings)}
                sub={`${savingsPct.toFixed(1)}%`}
                color={totalSavings > 0 ? "orange.500" : "gray.500"}
              />
            </HStack>
            {savingsChart.length > 1 && (
              <Box h="200px">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={savingsChart}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" vertical={false} />
                    <XAxis dataKey="complexity" tick={{ fontSize: 11, fill: "#94A3B8" }} />
                    <YAxis tick={{ fontSize: 11, fill: "#94A3B8" }} tickFormatter={(v) => `$${v}`} width={55} />
                    <RTooltip
                      contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #E2E8F0" }}
                      formatter={(value: number, name: string) => [formatCost(value), name === "actual" ? "Actual" : "Optimized"]}
                    />
                    <Legend />
                    <Bar dataKey="actual" fill="#F97316" name="Actual" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="optimized" fill="#22C55E" name="Optimized" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </Box>
            )}
            {savings.length > 0 && (
              <Box overflowX="auto" mt={3}>
                <Table size="sm" variant="simple">
                  <Thead>
                    <Tr>
                      <Th>Complexity</Th>
                      <Th isNumeric>Calls</Th>
                      <Th isNumeric>Actual</Th>
                      <Th isNumeric>Optimized</Th>
                      <Th isNumeric>Savings</Th>
                      <Th>Best Model</Th>
                    </Tr>
                  </Thead>
                  <Tbody>
                    {savings.map((s) => (
                      <Tr key={s.complexity} _hover={{ bg: "soft.hover" }}>
                        <Td fontSize="xs" textTransform="capitalize">{s.complexity}</Td>
                        <Td isNumeric fontSize="xs">{s.call_count}</Td>
                        <Td isNumeric fontFamily="mono" fontSize="xs">{formatCost(s.actual_cost)}</Td>
                        <Td isNumeric fontFamily="mono" fontSize="xs" color="green.600">{formatCost(s.hypothetical_cost)}</Td>
                        <Td isNumeric fontFamily="mono" fontSize="xs" color="orange.500">
                          {formatCost(s.potential_savings)} ({parseFloat(s.savings_pct || "0").toFixed(1)}%)
                        </Td>
                        <Td fontSize="xs">{shortModel(s.cheapest_model)}</Td>
                      </Tr>
                    ))}
                  </Tbody>
                </Table>
              </Box>
            )}
          </>
        )}
      </CardBox>

      {/* Performance Matrix */}
      <CardBox>
        <MetricTooltip label="Performance Matrix" methodology={METRIC_METHODOLOGY.modelEfficiencyMatrix} />
        <Box mt={2} />
        {matrixLoading ? (
          <Center py={8}><Spinner color="brand.500" size="sm" /></Center>
        ) : matrix.length === 0 ? (
          <Text fontSize="sm" color="gray.400">No data available</Text>
        ) : (
          <Box overflowX="auto">
            <Table size="sm" variant="simple">
              <Thead>
                <Tr>
                  <Th>Model</Th>
                  <Th>Complexity</Th>
                  <Th isNumeric>Calls</Th>
                  <Th isNumeric>Avg Cost</Th>
                  <Th isNumeric>Total Cost</Th>
                  <Th isNumeric>Avg Latency</Th>
                  <Th isNumeric>P50</Th>
                  <Th isNumeric>P95</Th>
                  <Th isNumeric>Avg Output Tok</Th>
                  <Th isNumeric>Tool %</Th>
                  <Th isNumeric>Errors</Th>
                </Tr>
              </Thead>
              <Tbody>
                {matrix.map((r, i) => (
                  <Tr key={i} _hover={{ bg: "soft.hover" }}>
                    <Td fontSize="xs" fontWeight="500">{shortModel(r.model)}</Td>
                    <Td fontSize="xs" textTransform="capitalize">{r.complexity}</Td>
                    <Td isNumeric fontSize="xs">{r.call_count}</Td>
                    <Td isNumeric fontFamily="mono" fontSize="xs">{formatCost(r.avg_cost_per_call)}</Td>
                    <Td isNumeric fontFamily="mono" fontSize="xs">{formatCost(r.total_cost)}</Td>
                    <Td isNumeric fontSize="xs">{formatMs(r.avg_latency_ms)}</Td>
                    <Td isNumeric fontSize="xs">{formatMs(r.p50_latency_ms)}</Td>
                    <Td isNumeric fontSize="xs">{formatMs(r.p95_latency_ms)}</Td>
                    <Td isNumeric fontSize="xs">{parseInt(r.avg_output_tokens || "0", 10).toLocaleString()}</Td>
                    <Td isNumeric fontSize="xs">{parseFloat(r.tool_success_rate || "0").toFixed(1)}%</Td>
                    <Td isNumeric fontSize="xs">{r.error_count}</Td>
                  </Tr>
                ))}
              </Tbody>
            </Table>
          </Box>
        )}
      </CardBox>

      {/* Right-Sizing Opportunities with Drill-Down */}
      <CardBox>
        <MetricTooltip label="Right-Sizing Opportunities" methodology={METRIC_METHODOLOGY.rightsizing} />
        <Box mt={2} />
        {rightsizingLoading ? (
          <Center py={8}><Spinner color="brand.500" size="sm" /></Center>
        ) : opportunities.length === 0 ? (
          <Text fontSize="sm" color="gray.400">No data available</Text>
        ) : (
          <>
            {opportunityChart.length > 0 && (
              <Box h="180px" mb={3}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={opportunityChart}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" vertical={false} />
                    <XAxis dataKey="level" tick={{ fontSize: 11, fill: "#94A3B8" }} />
                    <YAxis tick={{ fontSize: 11, fill: "#94A3B8" }} width={50} />
                    <RTooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #E2E8F0" }} />
                    <Bar dataKey="calls" name="API Calls" radius={[4, 4, 0, 0]} fill="#6366F1" />
                  </BarChart>
                </ResponsiveContainer>
              </Box>
            )}
            <Box overflowX="auto">
              <Table size="sm" variant="simple">
                <Thead>
                  <Tr>
                    <Th>Opportunity</Th>
                    <Th>Model</Th>
                    <Th>Complexity</Th>
                    <Th isNumeric>Calls</Th>
                    <Th isNumeric>Cost</Th>
                    <Th w="40px"></Th>
                  </Tr>
                </Thead>
                <Tbody>
                  {opportunities.filter((o) => o.downgrade_opportunity !== "none").map((o, i) => {
                    const open = isDrillOpen(o.model, o.complexity);
                    return (
                      <>
                        <Tr
                          key={`row-${i}`}
                          _hover={{ bg: "soft.hover" }}
                          cursor="pointer"
                          onClick={() => handleDrillToggle(o.model, o.complexity)}
                        >
                          <Td>
                            <Badge colorScheme={OPPORTUNITY_COLORS[o.downgrade_opportunity] || "gray"} fontSize="10px">
                              {o.downgrade_opportunity}
                            </Badge>
                          </Td>
                          <Td fontSize="xs">{shortModel(o.model)}</Td>
                          <Td fontSize="xs" textTransform="capitalize">{o.complexity}</Td>
                          <Td isNumeric fontSize="xs">{o.call_count}</Td>
                          <Td isNumeric fontFamily="mono" fontSize="xs">{formatCost(o.total_cost)}</Td>
                          <Td>
                            <Icon
                              as={open ? FiChevronUp : FiChevronDown}
                              boxSize={4}
                              color="gray.400"
                            />
                          </Td>
                        </Tr>
                        {open && (
                          <Tr key={`detail-${i}`}>
                            <Td colSpan={6} p={0} borderBottom="none">
                              <Collapse in={open} animateOpacity>
                                <Box bg="gray.50" px={4} py={3} borderBottomRadius="md">
                                  {detailsLoading ? (
                                    <Center py={4}><Spinner color="brand.500" size="sm" /></Center>
                                  ) : details.length === 0 ? (
                                    <Text fontSize="xs" color="gray.400">No matching prompts found</Text>
                                  ) : (
                                    <>
                                      <Text fontSize="xs" fontWeight="600" color="gray.600" mb={2}>
                                        {details.length} prompt{details.length !== 1 ? "s" : ""} using {shortModel(o.model)} on {o.complexity} tasks
                                      </Text>
                                      <Table size="sm" variant="simple">
                                        <Thead>
                                          <Tr>
                                            <Th>Prompt</Th>
                                            <Th isNumeric>Cost</Th>
                                            <Th isNumeric>API Calls</Th>
                                            <Th isNumeric>Latency</Th>
                                            <Th isNumeric>Output Tok</Th>
                                            <Th>Session</Th>
                                          </Tr>
                                        </Thead>
                                        <Tbody>
                                          {details.map((d, j) => (
                                            <Tr key={j} _hover={{ bg: "white" }}>
                                              <Td fontSize="xs" maxW="250px" isTruncated title={d.prompt_preview || ""}>
                                                {d.prompt_preview || <Text as="span" color="gray.400">No prompt text</Text>}
                                              </Td>
                                              <Td isNumeric fontFamily="mono" fontSize="xs">{formatCost(d.prompt_cost)}</Td>
                                              <Td isNumeric fontSize="xs">{d.api_calls}</Td>
                                              <Td isNumeric fontSize="xs">{formatMs(d.avg_latency_ms)}</Td>
                                              <Td isNumeric fontSize="xs">{parseInt(d.total_output_tokens || "0", 10).toLocaleString()}</Td>
                                              <Td>
                                                <Link to={`/sessions/${d.session_id}`}>
                                                  <HStack spacing={1}>
                                                    <Text fontSize="xs" color="brand.600" fontFamily="mono">
                                                      {d.session_id.substring(0, 8)}
                                                    </Text>
                                                    <Icon as={FiExternalLink} boxSize={3} color="brand.400" />
                                                  </HStack>
                                                </Link>
                                              </Td>
                                            </Tr>
                                          ))}
                                        </Tbody>
                                      </Table>
                                    </>
                                  )}
                                </Box>
                              </Collapse>
                            </Td>
                          </Tr>
                        )}
                      </>
                    );
                  })}
                </Tbody>
              </Table>
            </Box>
          </>
        )}
      </CardBox>

      {/* Model Recommendations */}
      <CardBox>
        <Text fontSize="sm" fontWeight="600" color="gray.700" mb={3}>Model Recommendations</Text>
        {recsLoading ? (
          <Center py={8}><Spinner color="brand.500" size="sm" /></Center>
        ) : recommendations.length === 0 ? (
          <Text fontSize="sm" color="gray.400">Not enough data (need 5+ calls per model/complexity)</Text>
        ) : (
          <VStack spacing={3} align="stretch">
            {Object.entries(recsByComplexity).map(([complexity, recs]) => (
              <Box key={complexity}>
                <Text fontSize="xs" fontWeight="600" color="gray.600" textTransform="capitalize" mb={1}>
                  {complexity}
                </Text>
                <Table size="sm" variant="simple">
                  <Thead>
                    <Tr>
                      <Th>Model</Th>
                      <Th isNumeric>Avg Cost</Th>
                      <Th isNumeric>P50 Latency</Th>
                      <Th>Badges</Th>
                    </Tr>
                  </Thead>
                  <Tbody>
                    {recs.map((r, i) => (
                      <Tr key={i} _hover={{ bg: "soft.hover" }}>
                        <Td fontSize="xs" fontWeight="500">{shortModel(r.model)}</Td>
                        <Td isNumeric fontFamily="mono" fontSize="xs">{formatCost(r.avg_cost)}</Td>
                        <Td isNumeric fontSize="xs">{formatMs(r.p50_latency)}</Td>
                        <Td>
                          <HStack spacing={1}>
                            {String(r.is_cost_winner) === "true" && (
                              <Badge colorScheme="green" fontSize="9px">Cheapest</Badge>
                            )}
                            {String(r.is_speed_winner) === "true" && (
                              <Badge colorScheme="blue" fontSize="9px">Fastest</Badge>
                            )}
                          </HStack>
                        </Td>
                      </Tr>
                    ))}
                  </Tbody>
                </Table>
              </Box>
            ))}
          </VStack>
        )}
      </CardBox>
    </VStack>
  );
}
