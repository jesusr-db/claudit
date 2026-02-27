import { Box, Heading, VStack, Text } from "@chakra-ui/react";
import { SummaryCards } from "./components/SummaryCards";
import { ErrorsTable } from "./components/ErrorsTable";

export default function DashboardPage() {
  return (
    <Box p={8}>
      <VStack spacing={8} align="stretch">
        <Box>
          <Heading size="lg" mb={1}>Analytics Dashboard</Heading>
          <Text fontSize="sm" color="gray.500">
            Claude Code usage overview and error insights
          </Text>
        </Box>
        <SummaryCards />
        <Box
          bg="surface.card"
          borderRadius="soft-lg"
          boxShadow="soft"
          border="1px solid"
          borderColor="soft.border"
          p={6}
        >
          <Heading size="sm" mb={4} color="gray.700">
            Recent Errors
          </Heading>
          <ErrorsTable />
        </Box>
      </VStack>
    </Box>
  );
}
