import {
  SimpleGrid,
  Stat,
  StatLabel,
  StatNumber,
  Card,
  CardBody,
  Spinner,
  Text,
} from "@chakra-ui/react";
import { useSummary } from "@/shared/hooks/useApi";

export function SummaryCards() {
  const { data, isLoading, error } = useSummary();

  if (isLoading) return <Spinner />;
  if (error) return <Text color="red.500">Failed to load summary</Text>;
  if (!data) return null;

  const cards = [
    { label: "Sessions", value: data.total_sessions },
    { label: "Users", value: data.total_users },
    { label: "Events", value: data.total_events },
    { label: "Prompts", value: data.total_prompts },
    { label: "API Calls", value: data.total_api_calls },
    { label: "Errors", value: data.total_errors },
    {
      label: "Total Cost",
      value: `$${parseFloat(data.total_cost_usd || "0").toFixed(2)}`,
    },
  ];

  return (
    <SimpleGrid columns={{ base: 2, md: 4 }} spacing={4}>
      {cards.map((c) => (
        <Card key={c.label} size="sm">
          <CardBody>
            <Stat>
              <StatLabel>{c.label}</StatLabel>
              <StatNumber>{c.value}</StatNumber>
            </Stat>
          </CardBody>
        </Card>
      ))}
    </SimpleGrid>
  );
}
