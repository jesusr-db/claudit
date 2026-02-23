import {
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Spinner,
  Text,
  Switch,
  FormControl,
  FormLabel,
  Box,
} from "@chakra-ui/react";
import { useState } from "react";
import { useToolStats } from "@/shared/hooks/useApi";

export function ToolUsageTable() {
  const [mcpOnly, setMcpOnly] = useState(false);
  const { data, isLoading, error } = useToolStats(mcpOnly);

  if (isLoading) return <Spinner />;
  if (error) return <Text color="red.500">Failed to load tool stats</Text>;

  return (
    <Box>
      <FormControl display="flex" alignItems="center" mb={3}>
        <FormLabel mb="0">MCP tools only</FormLabel>
        <Switch
          isChecked={mcpOnly}
          onChange={(e) => setMcpOnly(e.target.checked)}
        />
      </FormControl>
      <Table size="sm" variant="simple">
        <Thead>
          <Tr>
            <Th>Tool</Th>
            <Th isNumeric>Calls</Th>
            <Th isNumeric>Avg Duration (ms)</Th>
            <Th isNumeric>Success</Th>
            <Th isNumeric>Failures</Th>
          </Tr>
        </Thead>
        <Tbody>
          {(data?.tools || []).map((t) => (
            <Tr key={t.tool_name}>
              <Td>{t.tool_name}</Td>
              <Td isNumeric>{t.call_count}</Td>
              <Td isNumeric>{parseFloat(t.avg_duration_ms).toFixed(0)}</Td>
              <Td isNumeric>{t.success_count}</Td>
              <Td isNumeric>{t.failure_count}</Td>
            </Tr>
          ))}
        </Tbody>
      </Table>
    </Box>
  );
}
