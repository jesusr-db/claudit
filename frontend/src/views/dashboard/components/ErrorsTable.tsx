import {
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Spinner,
  Text,
  Badge,
  Center,
} from "@chakra-ui/react";
import { useErrorStats } from "@/shared/hooks/useApi";

export function ErrorsTable() {
  const { data, isLoading, error } = useErrorStats();

  if (isLoading) return <Center py={4}><Spinner color="brand.500" size="sm" /></Center>;
  if (error) return <Text color="red.500">Failed to load error stats</Text>;

  if (!data?.errors?.length) {
    return <Text color="gray.400" fontSize="sm">No errors recorded</Text>;
  }

  return (
    <Table size="sm" variant="soft">
      <Thead>
        <Tr>
          <Th>Model</Th>
          <Th>Status</Th>
          <Th>Error</Th>
          <Th isNumeric>Count</Th>
          <Th isNumeric>Avg Duration</Th>
        </Tr>
      </Thead>
      <Tbody>
        {data.errors.map((e, i) => (
          <Tr key={i}>
            <Td fontWeight="500">{e.model}</Td>
            <Td>
              <Badge colorScheme="red" variant="subtle">
                {e.status_code}
              </Badge>
            </Td>
            <Td maxW="300px" isTruncated color="gray.600">{e.error}</Td>
            <Td isNumeric fontWeight="600">{e.error_count}</Td>
            <Td isNumeric fontFamily="mono" fontSize="xs">
              {parseFloat(e.avg_duration_ms).toFixed(0)}ms
            </Td>
          </Tr>
        ))}
      </Tbody>
    </Table>
  );
}
