import {
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Spinner,
  Text,
} from "@chakra-ui/react";
import { useErrorStats } from "@/shared/hooks/useApi";

export function ErrorsTable() {
  const { data, isLoading, error } = useErrorStats();

  if (isLoading) return <Spinner />;
  if (error) return <Text color="red.500">Failed to load error stats</Text>;

  return (
    <Table size="sm" variant="simple">
      <Thead>
        <Tr>
          <Th>Model</Th>
          <Th>Status</Th>
          <Th>Error</Th>
          <Th isNumeric>Count</Th>
          <Th isNumeric>Avg Duration (ms)</Th>
        </Tr>
      </Thead>
      <Tbody>
        {(data?.errors || []).map((e, i) => (
          <Tr key={i}>
            <Td>{e.model}</Td>
            <Td>{e.status_code}</Td>
            <Td maxW="300px" isTruncated>{e.error}</Td>
            <Td isNumeric>{e.error_count}</Td>
            <Td isNumeric>{parseFloat(e.avg_duration_ms).toFixed(0)}</Td>
          </Tr>
        ))}
      </Tbody>
    </Table>
  );
}
