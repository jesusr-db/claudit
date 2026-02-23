import {
  Card,
  CardBody,
  HStack,
  VStack,
  Text,
  Stat,
  StatLabel,
  StatNumber,
  SimpleGrid,
} from "@chakra-ui/react";
import { useNavigate } from "react-router-dom";
import type { SessionSummary } from "@/types/api";

interface Props {
  session: SessionSummary;
}

export function SessionCard({ session }: Props) {
  const navigate = useNavigate();

  return (
    <Card
      cursor="pointer"
      onClick={() => navigate(`/sessions/${session.session_id}`)}
      _hover={{ shadow: "md" }}
      size="sm"
    >
      <CardBody>
        <VStack align="stretch" spacing={2}>
          <HStack justify="space-between">
            <Text fontFamily="mono" fontSize="sm" fontWeight="bold">
              {session.session_id.slice(0, 8)}...
            </Text>
            <Text fontSize="xs" color="gray.500">
              {new Date(session.start_time).toLocaleString()}
            </Text>
          </HStack>
          <SimpleGrid columns={4} spacing={2}>
            <Stat size="sm">
              <StatLabel>Events</StatLabel>
              <StatNumber fontSize="md">{session.event_count}</StatNumber>
            </Stat>
            <Stat size="sm">
              <StatLabel>Prompts</StatLabel>
              <StatNumber fontSize="md">{session.prompt_count}</StatNumber>
            </Stat>
            <Stat size="sm">
              <StatLabel>Cost</StatLabel>
              <StatNumber fontSize="md">
                ${parseFloat(session.total_cost_usd || "0").toFixed(2)}
              </StatNumber>
            </Stat>
            <Stat size="sm">
              <StatLabel>Errors</StatLabel>
              <StatNumber
                fontSize="md"
                color={parseInt(session.errors) > 0 ? "red.500" : "green.500"}
              >
                {session.errors}
              </StatNumber>
            </Stat>
          </SimpleGrid>
        </VStack>
      </CardBody>
    </Card>
  );
}
