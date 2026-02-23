import { Box, Heading, VStack } from "@chakra-ui/react";
import { SummaryCards } from "./components/SummaryCards";
import { ToolUsageTable } from "./components/ToolUsageTable";
import { ErrorsTable } from "./components/ErrorsTable";

export default function DashboardPage() {
  return (
    <Box p={6}>
      <VStack spacing={8} align="stretch">
        <Heading size="lg">Analytics Dashboard</Heading>
        <SummaryCards />
        <Box>
          <Heading size="md" mb={4}>
            Tool Usage
          </Heading>
          <ToolUsageTable />
        </Box>
        <Box>
          <Heading size="md" mb={4}>
            Errors
          </Heading>
          <ErrorsTable />
        </Box>
      </VStack>
    </Box>
  );
}
