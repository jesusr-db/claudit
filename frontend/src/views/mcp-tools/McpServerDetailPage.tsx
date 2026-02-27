import {
  Box,
  Heading,
  VStack,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Spinner,
  Text,
  Badge,
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  Link as ChakraLink,
  Center,
} from "@chakra-ui/react";
import { useParams, Link } from "react-router-dom";
import { useToolRecentCalls } from "@/shared/hooks/useApi";

function fmt(val: string | null | undefined): string {
  return parseFloat(val || "0").toFixed(0);
}

export default function ToolDetailPage() {
  const { server: toolName } = useParams<{ server: string }>();
  const decoded = decodeURIComponent(toolName || "");
  const { data, isLoading, error } = useToolRecentCalls(decoded);

  return (
    <Box p={8}>
      <VStack spacing={6} align="stretch">
        <Box>
          <Breadcrumb mb={2} fontSize="sm">
            <BreadcrumbItem>
              <BreadcrumbLink as={Link} to="/mcp-tools" color="brand.600">
                Tool Deep Dive
              </BreadcrumbLink>
            </BreadcrumbItem>
            <BreadcrumbItem isCurrentPage>
              <BreadcrumbLink color="gray.500">{decoded}</BreadcrumbLink>
            </BreadcrumbItem>
          </Breadcrumb>
          <Heading size="lg">{decoded}</Heading>
        </Box>

        <Box
          bg="surface.card"
          borderRadius="soft-lg"
          boxShadow="soft"
          border="1px solid"
          borderColor="soft.border"
          p={6}
        >
          <Heading size="sm" mb={4} color="gray.700">
            Recent Calls
          </Heading>
          {isLoading && <Center py={4}><Spinner color="brand.500" size="sm" /></Center>}
          {error && <Text color="red.500">Failed to load recent calls</Text>}
          {data && data.calls.length === 0 && (
            <Text color="gray.400" fontSize="sm">No calls found</Text>
          )}
          {data && data.calls.length > 0 && (
            <Table size="sm" variant="soft">
              <Thead>
                <Tr>
                  <Th>Time</Th>
                  <Th>Session</Th>
                  <Th isNumeric>Duration</Th>
                  <Th>Status</Th>
                  <Th isNumeric>Result Size</Th>
                </Tr>
              </Thead>
              <Tbody>
                {data.calls.map((c, i) => (
                  <Tr key={`${c.timestamp}-${i}`}>
                    <Td fontSize="xs" fontFamily="mono" color="gray.500">{c.timestamp}</Td>
                    <Td>
                      <ChakraLink
                        as={Link}
                        to={`/sessions/${c.session_id}`}
                        color="brand.600"
                        fontSize="xs"
                        fontWeight="500"
                      >
                        {c.session_id.slice(0, 8)}...
                      </ChakraLink>
                    </Td>
                    <Td isNumeric fontFamily="mono" fontSize="xs">{fmt(c.duration_ms)}ms</Td>
                    <Td>
                      <Badge colorScheme={c.success === "true" ? "green" : "red"} variant="subtle">
                        {c.success === "true" ? "OK" : "FAIL"}
                      </Badge>
                    </Td>
                    <Td isNumeric fontSize="xs">{fmt(c.result_size_bytes)} B</Td>
                  </Tr>
                ))}
              </Tbody>
            </Table>
          )}
        </Box>
      </VStack>
    </Box>
  );
}
