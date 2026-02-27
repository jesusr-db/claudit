import {
  SimpleGrid,
  Stat,
  StatLabel,
  StatNumber,
  Card,
  CardBody,
  Spinner,
  Text,
  Box,
  Center,
  Icon,
} from "@chakra-ui/react";
import {
  FiUsers,
  FiActivity,
  FiMessageSquare,
  FiZap,
  FiAlertTriangle,
  FiDollarSign,
  FiLayers,
} from "react-icons/fi";
import { useSummary } from "@/shared/hooks/useApi";

const CARD_ICONS: Record<string, { icon: React.ElementType; color: string; bg: string }> = {
  Sessions: { icon: FiLayers, color: "brand.600", bg: "brand.50" },
  Users: { icon: FiUsers, color: "purple.600", bg: "purple.50" },
  Events: { icon: FiActivity, color: "teal.600", bg: "teal.50" },
  Prompts: { icon: FiMessageSquare, color: "blue.600", bg: "blue.50" },
  "API Calls": { icon: FiZap, color: "green.600", bg: "green.50" },
  Errors: { icon: FiAlertTriangle, color: "red.500", bg: "red.50" },
  "Total Cost": { icon: FiDollarSign, color: "accent.600", bg: "accent.50" },
};

export function SummaryCards() {
  const { data, isLoading, error } = useSummary();

  if (isLoading) return <Center py={8}><Spinner color="brand.500" /></Center>;
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
      {cards.map((c) => {
        const meta = CARD_ICONS[c.label] || CARD_ICONS.Sessions;
        return (
          <Card key={c.label}>
            <CardBody py={4} px={5}>
              <Box display="flex" alignItems="flex-start" gap={3}>
                <Box
                  p={2}
                  borderRadius="soft"
                  bg={meta.bg}
                  display="flex"
                  alignItems="center"
                  justifyContent="center"
                >
                  <Icon as={meta.icon} boxSize={4} color={meta.color} />
                </Box>
                <Stat size="sm">
                  <StatLabel>{c.label}</StatLabel>
                  <StatNumber fontSize="xl">{c.value}</StatNumber>
                </Stat>
              </Box>
            </CardBody>
          </Card>
        );
      })}
    </SimpleGrid>
  );
}
