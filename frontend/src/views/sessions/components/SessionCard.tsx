import {
  Card,
  CardBody,
  HStack,
  VStack,
  Text,
  Badge,
  Box,
} from "@chakra-ui/react";
import type { SessionSummary } from "@/types/api";

export interface SessionTurnaroundStats {
  avg: number;
  max: number;
  totalTools: number;
  totalApi: number;
  count: number;
}

interface Props {
  session: SessionSummary;
  isExpanded?: boolean;
  onClick?: () => void;
  turnaround?: SessionTurnaroundStats;
}

function formatSec(n: number): string {
  if (n >= 60) return `${Math.floor(n / 60)}m ${Math.round(n % 60)}s`;
  return `${Math.round(n)}s`;
}

function workColor(sec: number): string {
  if (sec < 30) return "green.600";
  if (sec <= 120) return "orange.500";
  return "red.500";
}

export function SessionCard({ session, isExpanded, onClick, turnaround }: Props) {
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

          {/* Turnaround metrics row */}
          {turnaround && turnaround.count > 0 && (
            <HStack
              spacing={4}
              pt={1}
              borderTop="1px solid"
              borderColor="soft.border"
              fontSize="xs"
              color="gray.500"
            >
              <HStack spacing={1}>
                <Text>Avg work:</Text>
                <Text fontWeight="600" fontFamily="mono" color={workColor(turnaround.avg)}>
                  {formatSec(turnaround.avg)}
                </Text>
              </HStack>
              <HStack spacing={1}>
                <Text>Max:</Text>
                <Text fontWeight="600" fontFamily="mono" color={workColor(turnaround.max)}>
                  {formatSec(turnaround.max)}
                </Text>
              </HStack>
              <Box w="1px" h="12px" bg="gray.200" />
              <HStack spacing={1}>
                <Text>Tools:</Text>
                <Text fontWeight="600" fontFamily="mono">{turnaround.totalTools}</Text>
              </HStack>
              <HStack spacing={1}>
                <Text>API:</Text>
                <Text fontWeight="600" fontFamily="mono">{turnaround.totalApi}</Text>
              </HStack>
            </HStack>
          )}
        </VStack>
      </CardBody>
    </Card>
  );
}
