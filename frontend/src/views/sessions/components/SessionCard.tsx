import {
  Card,
  CardBody,
  HStack,
  VStack,
  Text,
  Badge,
} from "@chakra-ui/react";
import type { SessionSummary } from "@/types/api";

interface Props {
  session: SessionSummary;
  isExpanded?: boolean;
  onClick?: () => void;
}

export function SessionCard({ session, isExpanded, onClick }: Props) {
  const ts = new Date(session.start_time).toLocaleString();
  const prompt = session.first_prompt || "No prompt recorded";
  const errors = parseInt(session.errors);
  const cost = parseFloat(session.total_cost_usd || "0");

  return (
    <Card
      cursor="pointer"
      onClick={onClick}
      borderColor={isExpanded ? "brand.300" : undefined}
      boxShadow={isExpanded ? "soft-md" : undefined}
      _hover={{
        boxShadow: "soft-md",
        borderColor: "brand.200",
        transform: isExpanded ? undefined : "translateY(-1px)",
      }}
      transition="all 0.2s ease"
    >
      <CardBody py={3} px={4}>
        <VStack align="stretch" spacing={2}>
          <HStack justify="space-between">
            <HStack spacing={2}>
              <Text fontSize="xs" color="gray.400" fontWeight="500">
                {ts}
              </Text>
              <Text fontSize="xs" color="gray.400">
                {isExpanded ? "▼" : "▶"}
              </Text>
            </HStack>
            <HStack spacing={2}>
              <Badge variant="subtle" colorScheme="blue" fontSize="xs">
                {session.prompt_count} prompts
              </Badge>
              <Badge variant="subtle" colorScheme="gray" fontSize="xs">
                {session.event_count} events
              </Badge>
              {errors > 0 && (
                <Badge colorScheme="red" variant="subtle" fontSize="xs">
                  {errors} errors
                </Badge>
              )}
              <Badge variant="subtle" colorScheme="green" fontSize="xs">
                ${cost.toFixed(2)}
              </Badge>
            </HStack>
          </HStack>
          <Text fontSize="sm" noOfLines={isExpanded ? undefined : 2} color="gray.700" fontWeight="500">
            {prompt}
          </Text>
        </VStack>
      </CardBody>
    </Card>
  );
}
