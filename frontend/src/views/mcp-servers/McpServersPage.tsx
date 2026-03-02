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
} from "@chakra-ui/react";
import OpsTab from "./tabs/OpsTab";
import McpToolsTab from "./tabs/McpToolsTab";
import LocalToolsTab from "./tabs/LocalToolsTab";
import SecurityTab from "./tabs/SecurityTab";
import LogsTab from "./tabs/LogsTab";

export default function McpServersPage() {
  return (
    <Box p={8}>
      <VStack spacing={6} align="stretch">
        <Box>
          <Heading size="lg" mb={1}>MCP Servers</Heading>
          <Text color="gray.500" fontSize="sm">
            Server-side observability: tool performance, HTTP dependencies, security audit, and logs
          </Text>
        </Box>
        <Tabs variant="soft-rounded" colorScheme="brand">
          <TabList>
            <Tab>Operations</Tab>
            <Tab>MCP Tools</Tab>
            <Tab>Local Tools</Tab>
            <Tab>Security & Audit</Tab>
            <Tab>Logs</Tab>
          </TabList>
          <TabPanels>
            <TabPanel px={0} pt={5}>
              <OpsTab />
            </TabPanel>
            <TabPanel px={0} pt={5}>
              <McpToolsTab />
            </TabPanel>
            <TabPanel px={0} pt={5}>
              <LocalToolsTab />
            </TabPanel>
            <TabPanel px={0} pt={5}>
              <SecurityTab />
            </TabPanel>
            <TabPanel px={0} pt={5}>
              <LogsTab />
            </TabPanel>
          </TabPanels>
        </Tabs>
      </VStack>
    </Box>
  );
}
