import { useState } from "react";
import {
  Box,
  Heading,
  VStack,
  Text,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  Select,
  HStack,
  Spinner,
} from "@chakra-ui/react";
import { useTimeRange } from "@/shared/context/TimeRangeContext";
import { useAiGatewayEndpoints } from "@/shared/hooks/useApi";
import { DARK } from "@/shared/utils/gatewayColors";
import OverviewTab from "./components/OverviewTab";
import PerformanceTab from "./components/PerformanceTab";
import UsageTab from "./components/UsageTab";
import CodingAgentsTab from "./components/CodingAgentsTab";
import TokenConsumptionTab from "./components/TokenConsumptionTab";

export default function PlatformPage() {
  const { days } = useTimeRange();
  const [selectedEndpoint, setSelectedEndpoint] = useState<string | null>(null);
  const { data: endpointData, isLoading: loadingEndpoints } = useAiGatewayEndpoints(days);

  const endpoints = endpointData?.endpoints ?? [];

  return (
    <Box p={8}>
      <VStack spacing={6} align="stretch">
        <Box>
          <Heading size="lg" mb={1}>AI Gateway Analytics</Heading>
          <Text color="gray.500" fontSize="sm">
            Comprehensive AI Gateway usage, performance, and token analytics
          </Text>
        </Box>

        <Box bg={DARK.bg} borderRadius="soft-lg" p={6} minH="80vh">
          <HStack mb={5} spacing={3}>
            <Text fontSize="xs" color={DARK.label} textTransform="uppercase" letterSpacing="0.5px" whiteSpace="nowrap">
              AI Gateway Endpoint
            </Text>
            {loadingEndpoints ? (
              <Spinner size="xs" color="cyan.400" />
            ) : (
              <Select
                size="sm"
                maxW="300px"
                bg={DARK.card}
                border="1px solid"
                borderColor={DARK.border}
                color={DARK.value}
                value={selectedEndpoint ?? ""}
                onChange={(e) => setSelectedEndpoint(e.target.value || null)}
                _focus={{ borderColor: "cyan.500" }}
              >
                <option value="" style={{ background: DARK.card }}>All Endpoints</option>
                {endpoints.map((ep) => (
                  <option key={ep} value={ep} style={{ background: DARK.card }}>{ep}</option>
                ))}
              </Select>
            )}
          </HStack>

          <Tabs isLazy variant="soft-rounded" colorScheme="cyan">
            <TabList
              mb={5}
              sx={{
                "& .chakra-tabs__tab": { color: DARK.label, fontSize: "sm" },
                "& .chakra-tabs__tab[aria-selected=true]": { color: DARK.bg, bg: "cyan.400" },
              }}
            >
              <Tab>Overview</Tab>
              <Tab>Performance</Tab>
              <Tab>Usage</Tab>
              <Tab>Coding Agents</Tab>
              <Tab>Token Consumption</Tab>
            </TabList>
            <TabPanels>
              <TabPanel px={0} pt={2}>
                <OverviewTab days={days} endpoint={selectedEndpoint} />
              </TabPanel>
              <TabPanel px={0} pt={2}>
                <PerformanceTab days={days} endpoint={selectedEndpoint} />
              </TabPanel>
              <TabPanel px={0} pt={2}>
                <UsageTab days={days} endpoint={selectedEndpoint} />
              </TabPanel>
              <TabPanel px={0} pt={2}>
                <CodingAgentsTab days={days} endpoint={selectedEndpoint} />
              </TabPanel>
              <TabPanel px={0} pt={2}>
                <TokenConsumptionTab days={days} endpoint={selectedEndpoint} />
              </TabPanel>
            </TabPanels>
          </Tabs>
        </Box>
      </VStack>
    </Box>
  );
}
